"""Shared constants, CSS, helpers, and data loading for The Rot Report."""
from __future__ import annotations

import html as _html_mod
import logging
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import quote

import ftfy
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Restore Spotify token cache from env / Streamlit secrets (for Cloud deploy)
# ---------------------------------------------------------------------------
_token_json = os.environ.get("SPOTIFY_TOKEN_CACHE", "").strip()
if _token_json:
    _cache_path = os.environ.get(
        "SPOTIPY_CACHE_PATH",
        os.path.join(tempfile.gettempdir(), ".spotify_token_cache"),
    )
    try:
        Path(_cache_path).write_text(_token_json, encoding="utf-8")
    except OSError:
        pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NEON_GREEN = "#39FF14"
PURPLE = "#9B30FF"
WHITE = "#FFFFFF"
DARK_GRAY = "#1A1A1A"
PALETTE = [NEON_GREEN, PURPLE, "#FF6EC7", "#00FFFF", "#FFD700", "#FF4500",
           "#1E90FF", "#FF1493", "#7FFF00", "#FF8C00"]
PLOT_TEMPLATE = "plotly_dark"
ITALIC_TICK = dict(family="monospace", size=11)
HBAR_HEIGHT_PER = 28
DJ_PAGE_SIZE = 10

TIMEZONE_OPTIONS = {
    "Eastern (ET)": "US/Eastern",
    "Central (CT)": "US/Central",
    "Mountain (MT)": "US/Mountain",
    "Pacific (PT)": "US/Pacific",
    "UTC": "UTC",
    "London (GMT/BST)": "Europe/London",
    "Central Europe (CET)": "Europe/Berlin",
    "Japan (JST)": "Asia/Tokyo",
}


def get_user_timezone() -> str:
    """Return the IANA timezone string from session state, defaulting to US/Eastern."""
    return st.session_state.get("user_tz", "US/Eastern")


def apply_user_tz(df: pd.DataFrame, col: str = "play_datetime") -> pd.DataFrame:
    """Add play_hour, play_dow, month columns converted to the user's timezone."""
    if col not in df.columns or not pd.api.types.is_datetime64_any_dtype(df[col]):
        df = df.copy()
        df["play_hour"] = pd.NA
        df["play_dow"] = pd.NA
        df["month"] = pd.NA
        return df
    tz = get_user_timezone()
    local = df[col].dt.tz_convert(tz)
    df = df.copy()
    df["play_hour"] = local.dt.hour
    df["play_dow"] = local.dt.day_name()
    df["month"] = local.dt.to_period("M").astype(str)
    return df


def render_sidebar_settings() -> None:
    """Render a Settings expander in the sidebar with a timezone selector."""
    with st.sidebar.expander("⚙ Settings", expanded=False):
        labels = list(TIMEZONE_OPTIONS.keys())
        idx = labels.index("Eastern (ET)")
        sel = st.selectbox("Timezone", labels, index=idx, key="tz_label")
        st.session_state["user_tz"] = TIMEZONE_OPTIONS[sel]


# ---------------------------------------------------------------------------
# CSS injection
# ---------------------------------------------------------------------------
def inject_css() -> None:
    """Inject the Rot Report custom CSS into the current page."""
    st.markdown(
        f"""
        <style>
        [data-testid="stMetric"] {{
            background-color: {DARK_GRAY};
            border: 1px solid #333333;
            border-radius: 8px;
            padding: 12px 16px;
        }}
        [data-testid="stMetricValue"] {{
            color: {NEON_GREEN};
        }}
        [data-testid="stMetricLabel"] {{
            color: {WHITE};
        }}
        div[data-testid="stExpander"] details {{
            border-color: #333333;
        }}
        section[data-testid="stSidebar"] {{
            background-color: {DARK_GRAY};
        }}
        h1, h2, h3 {{
            color: {NEON_GREEN} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(subtitle: str) -> None:
    """Main title row with optional station logo in the right column (~25% width)."""
    logo = Path(__file__).resolve().parent / "assets" / "logo" / "brainrot_logo.png"
    title_md = f"# THE ROT REPORT\n##### {subtitle}"
    if not logo.is_file():
        st.markdown(title_md)
        return
    left, right = st.columns([3, 1], gap="large", vertical_alignment="center")
    with left:
        st.markdown(title_md)
    with right:
        st.image(logo, use_container_width=True, link="https://brainrotradio.com")


# ---------------------------------------------------------------------------
# DJ page linking helpers
# ---------------------------------------------------------------------------
def dj_page_url(dj_name: str) -> str:
    """Return relative URL for a DJ's profile page."""
    return f"/DJ_Pages?dj={quote(dj_name)}"


def dj_link_html(dj_name: str, extra_style: str = "") -> str:
    """Return an <a> tag linking to the DJ's profile page."""
    safe = _html_mod.escape(dj_name)
    url = _html_mod.escape(dj_page_url(dj_name))
    style = f"color:inherit;text-decoration:none;{extra_style}"
    return (
        f'<a href="{url}" target="_self" '
        f'style="{style}" '
        f'onmouseover="this.style.color=\'{NEON_GREEN}\';this.style.textDecoration=\'underline\'" '
        f'onmouseout="this.style.color=\'inherit\';this.style.textDecoration=\'none\'"'
        f'>{safe}</a>'
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def add_plays_label(frame: pd.DataFrame, col: str = "plays") -> pd.DataFrame:
    """Add a human-readable plays label column for bar chart text."""
    frame = frame.copy()
    frame["plays_label"] = frame[col].apply(lambda v: f"{v:,} plays")
    return frame


def _parse_duration_minutes(s: object) -> float | None:
    """Convert a duration value to minutes. Handles MM:SS, H:MM:SS, and numeric seconds."""
    if pd.isna(s):
        return None
    text = str(s).strip()
    m = re.match(r"^(\d+):(\d{2}):(\d{2})$", text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 60
    m = re.match(r"^(\d+):(\d{2})$", text)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60
    try:
        val = float(text)
        return val / 60 if val > 300 else val
    except ValueError:
        return None


def _normalize_text_col(series: pd.Series) -> pd.Series:
    """Fix mojibake, apply NFC normalization, and strip whitespace."""
    return series.apply(
        lambda v: unicodedata.normalize("NFC", ftfy.fix_text(str(v))).strip()
        if pd.notna(v) else v
    )


def _extract_year(s: object) -> int | None:
    if pd.isna(s):
        return None
    try:
        year = int(float(s))
        if 1900 <= year <= 2099:
            return year
    except (ValueError, TypeError):
        pass
    m = re.search(r"((?:19|20)\d{2})", str(s))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_resource
def _get_engine():
    load_dotenv()
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "postgres"),
    )
    return create_engine(url, pool_pre_ping=True)


def _name_matches(expected: str, actual: str) -> bool:
    """Case-insensitive containment check to validate Spotify search results."""
    e, a = expected.lower().strip(), actual.lower().strip()
    return e in a or a in e


def _build_track_result(sp, track: dict) -> dict:
    """Extract metadata dict from a Spotify track object."""
    album_images = track.get("album", {}).get("images", [])
    artist_id = track["artists"][0]["id"]
    artist_info = sp.artist(artist_id)
    artist_images = artist_info.get("images", [])
    return {
        "track_img": album_images[0]["url"] if album_images else None,
        "album_img": album_images[0]["url"] if album_images else None,
        "artist_img": artist_images[0]["url"] if artist_images else None,
        "track_url": track.get("external_urls", {}).get("spotify"),
        "album_url": track.get("album", {}).get("external_urls", {}).get("spotify"),
        "artist_url": track["artists"][0].get("external_urls", {}).get("spotify"),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def get_spotify_metadata(artist: str, song: str | None = None) -> dict | None:
    """Look up Spotify images and URLs for an artist + optional song.

    Returns a dict with keys:
      track_img, album_img, artist_img,
      track_url, album_url, artist_url
    or None on failure.
    """
    try:
        from spotify_spin_common import get_spotify_client_from_env
    except ImportError:
        logger.debug("spotify_spin_common not available; skipping metadata lookup")
        return None

    try:
        sp = get_spotify_client_from_env()
    except Exception:
        logger.debug("Could not initialise Spotify client", exc_info=True)
        return None

    try:
        if song:
            # Try field-filtered search first
            results = sp.search(
                q=f'track:"{song}" artist:"{artist}"', type="track", limit=1,
            )
            items = (results or {}).get("tracks", {}).get("items", [])

            # Validate the artist name on the result
            if items and _name_matches(artist, items[0]["artists"][0]["name"]):
                return _build_track_result(sp, items[0])

            # Fallback: freetext search
            results = sp.search(q=f"{song} {artist}", type="track", limit=1)
            items = (results or {}).get("tracks", {}).get("items", [])
            if items and _name_matches(artist, items[0]["artists"][0]["name"]):
                return _build_track_result(sp, items[0])

            return None
        else:
            # Try field-filtered artist search first
            results = sp.search(
                q=f'artist:"{artist}"', type="artist", limit=1,
            )
            items = (results or {}).get("artists", {}).get("items", [])

            if items and _name_matches(artist, items[0]["name"]):
                art = items[0]
            else:
                # Fallback: freetext search
                results = sp.search(q=artist, type="artist", limit=1)
                items = (results or {}).get("artists", {}).get("items", [])
                if not items or not _name_matches(artist, items[0]["name"]):
                    return None
                art = items[0]

            images = art.get("images", [])
            return {
                "track_img": None,
                "album_img": None,
                "artist_img": images[0]["url"] if images else None,
                "track_url": None,
                "album_url": None,
                "artist_url": art.get("external_urls", {}).get("spotify"),
            }
    except Exception:
        logger.debug("Spotify metadata lookup failed for %s / %s", artist, song, exc_info=True)
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_spotify_url_for_artist(artist: str) -> str | None:
    """Quick lookup returning just the Spotify artist page URL."""
    meta = get_spotify_metadata(artist)
    return meta.get("artist_url") if meta else None


@st.cache_data(ttl=3600, show_spinner=False)
def get_spotify_url_for_track(artist: str, song: str) -> str | None:
    """Quick lookup returning just the Spotify track URL."""
    meta = get_spotify_metadata(artist, song)
    return meta.get("track_url") if meta else None


@st.cache_data(ttl=3600, show_spinner=False)
def get_cross_platform_links(spotify_url: str) -> dict:
    """Use the Songlink / Odesli API to get links for other platforms.

    Returns a dict mapping platform name -> URL, e.g.
    {"appleMusic": "https://...", "youtube": "https://...", ...}
    """
    if not spotify_url:
        return {}
    try:
        resp = requests.get(
            "https://api.song.link/v1-alpha.1/links",
            params={"url": spotify_url, "userCountry": "US"},
            timeout=8,
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        links: dict[str, str] = {}
        for platform, info in data.get("linksByPlatform", {}).items():
            url = info.get("url")
            if url:
                links[platform] = url
        return links
    except Exception:
        logger.debug("Songlink lookup failed for %s", spotify_url, exc_info=True)
        return {}


@st.cache_data(ttl=300, show_spinner="Loading data …")
def load_data() -> pd.DataFrame:
    engine = _get_engine()
    schema = os.environ.get("POSTGRES_SCHEMA", "public")
    try:
        df = pd.read_sql_table("brainrot_radio", engine, schema=schema)
    except Exception:
        engine.dispose()
        df = pd.read_sql_table("brainrot_radio", engine, schema=schema)

    for col in ("artist", "song", "release", "label"):
        if col in df.columns:
            df[col] = _normalize_text_col(df[col])

    df = df[~df["artist"].str.lower().str.contains("brainrot radio", na=False)]

    df["play_datetime"] = pd.to_datetime(df["play_datetime"], utc=True, errors="coerce")
    if pd.api.types.is_datetime64_any_dtype(df["play_datetime"]):
        df["play_datetime"] = df["play_datetime"].dt.tz_convert("US/Eastern")

    df["play_date_parsed"] = pd.to_datetime(df["play_date"], errors="coerce")
    df["duration_min"] = df["duration"].apply(_parse_duration_minutes)
    df["release_year"] = df["released"].apply(_extract_year).astype("Int64")
    df["decade"] = df["release_year"].apply(
        lambda y: f"{int((y // 10) * 10)}s" if pd.notna(y) else None
    )

    return df
