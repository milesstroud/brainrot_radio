"""The Rot Report -- Snapshots."""
from __future__ import annotations

import datetime
import html as html_mod

import pandas as pd
import plotly.express as px
import streamlit as st

from shared import (
    NEON_GREEN, PURPLE, PALETTE, PLOT_TEMPLATE,
    DARK_GRAY, WHITE,
    inject_css, render_page_header, add_plays_label, load_data,
    get_spotify_metadata, get_cross_platform_links,
    get_spotify_url_for_artist, get_spotify_url_for_track,
    dj_link_html,
    render_sidebar_settings, apply_user_tz,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="The Rot Report — Snapshots", page_icon="📻", layout="wide")
inject_css()

# Snapshot-specific CSS
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" />',
    unsafe_allow_html=True,
)
st.markdown(
    f"""
    <style>
    .snapshot-card {{
        background-color: {DARK_GRAY};
        border: 1px solid #333333;
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 12px;
    }}
    .snapshot-card h4 {{
        margin: 0 0 6px 0;
        font-size: 0.85rem;
        color: #999 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .snapshot-card .top-entry {{
        font-size: 1.25rem;
        font-weight: bold;
        color: {WHITE};
    }}
    .snapshot-card .top-entry .plays {{
        color: {NEON_GREEN};
        font-size: 0.9rem;
        font-weight: normal;
    }}
    .snapshot-card .runner-up {{
        font-size: 0.85rem;
        color: #bbb;
        padding: 2px 0;
    }}
    .snapshot-card .runner-up .rank {{
        color: #666;
        margin-right: 6px;
    }}
    .snapshot-card .runner-up .count {{
        float: right;
        color: #888;
    }}
    .snapshot-card .runner-up a {{
        color: #bbb;
        text-decoration: none;
    }}
    .snapshot-card .runner-up a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}
    .pct-big {{
        font-size: 2.2rem;
        font-weight: bold;
        color: {NEON_GREEN};
        line-height: 1.1;
    }}
    .pct-delta {{
        font-size: 0.9rem;
        margin-left: 6px;
    }}
    .pct-delta.positive {{ color: {NEON_GREEN}; }}
    .pct-delta.negative {{ color: #FF4500; }}
    .pct-new-link a {{
        color: #888;
        text-decoration: none;
    }}
    .pct-new-link a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}

    /* ---- hero card with artwork ---- */
    .hero-card {{
        background-color: {DARK_GRAY};
        border: 1px solid #333333;
        border-radius: 10px;
        overflow: hidden;
        margin-bottom: 12px;
        position: relative;
    }}
    .hero-card .hero-img {{
        width: 100%;
        aspect-ratio: 1 / 1;
        object-fit: cover;
        display: block;
    }}
    .hero-card .hero-body {{
        padding: 14px 16px;
    }}
    .hero-card .hero-label {{
        display: inline-block;
        background: {NEON_GREEN};
        color: #000;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 3px 8px;
        border-radius: 4px;
        margin-bottom: 6px;
    }}
    .hero-card .hero-title {{
        font-size: 1.1rem;
        font-weight: bold;
        color: {WHITE};
        margin: 4px 0 2px 0;
    }}
    .hero-card .hero-title a {{
        color: {WHITE};
        text-decoration: none;
    }}
    .hero-card .hero-title a:hover {{
        text-decoration: underline;
        color: {NEON_GREEN};
    }}
    .hero-card .hero-plays {{
        color: {NEON_GREEN};
        font-size: 0.85rem;
    }}
    .hero-card .hero-cmp {{
        color: #888;
        font-size: 0.7rem;
    }}
    .hero-card .hero-runners {{
        padding: 0 16px 12px 16px;
    }}
    .hero-card .hero-runners .runner-up {{
        font-size: 0.82rem;
        color: #bbb;
        padding: 2px 0;
    }}
    .hero-card .hero-runners .rank {{
        color: #666;
        margin-right: 6px;
    }}
    .hero-card .hero-runners .count {{
        float: right;
        color: #888;
    }}
    .hero-card .hero-runners a {{
        color: #bbb;
        text-decoration: none;
    }}
    .hero-card .hero-runners a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}
    .platform-links {{
        margin-top: 6px;
    }}
    .platform-links a {{
        display: inline-block;
        font-size: 0.72rem;
        color: #aaa;
        text-decoration: none;
        margin-right: 10px;
        padding: 2px 6px;
        border: 1px solid #444;
        border-radius: 4px;
    }}
    .platform-links a:hover {{
        color: {NEON_GREEN};
        border-color: {NEON_GREEN};
    }}

    /* ---- decade timeline ---- */
    .tl-wrap {{
        overflow-x: auto;
        padding: 20px 0 10px 0;
    }}
    .tl-track {{
        display: flex;
        align-items: center;
        position: relative;
        min-width: max-content;
        padding: 0 24px;
    }}
    .tl-line {{
        position: absolute;
        top: 50%;
        left: 24px;
        right: 24px;
        height: 3px;
        background: {PURPLE};
        transform: translateY(-50%);
        z-index: 0;
    }}
    .tl-node {{
        display: flex;
        flex-direction: column;
        align-items: center;
        position: relative;
        z-index: 1;
        flex: 1 1 0;
        min-width: 130px;
    }}
    .tl-node.above .tl-bubble {{
        order: 1;
    }}
    .tl-node.above .tl-connector {{
        order: 2;
    }}
    .tl-node.above .tl-pill {{
        order: 3;
    }}
    .tl-node.below .tl-pill {{
        order: 1;
    }}
    .tl-node.below .tl-connector {{
        order: 2;
    }}
    .tl-node.below .tl-bubble {{
        order: 3;
    }}
    .tl-pill {{
        background: {PURPLE};
        color: {WHITE};
        font-size: 0.75rem;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: 14px;
        letter-spacing: 1px;
        white-space: nowrap;
    }}
    .tl-connector {{
        width: 2px;
        height: 28px;
        border-left: 2px dashed #555;
    }}
    .tl-bubble {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 10px;
        overflow: hidden;
        width: 120px;
        text-align: center;
    }}
    .tl-bubble img {{
        width: 120px;
        height: 120px;
        object-fit: cover;
        display: block;
    }}
    .tl-bubble .tl-placeholder {{
        width: 120px;
        height: 120px;
        background: #222;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #555;
        font-size: 0.7rem;
    }}
    .tl-bubble .tl-info {{
        padding: 8px 8px 10px 8px;
    }}
    .tl-bubble .tl-name {{
        font-size: 0.78rem;
        font-weight: bold;
        color: {WHITE};
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .tl-bubble .tl-name a {{
        color: {WHITE};
        text-decoration: none;
    }}
    .tl-bubble .tl-name a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}
    .tl-bubble .tl-plays {{
        font-size: 0.7rem;
        color: {NEON_GREEN};
        margin-top: 2px;
    }}

    /* ---- superlative award cards ---- */
    .superlative-card {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 10px;
        padding: 14px;
        text-align: center;
        margin-bottom: 12px;
    }}
    .superlative-card i {{
        font-size: 2rem;
        color: {NEON_GREEN};
        margin-bottom: 10px;
        display: block;
    }}
    .superlative-card .sup-title {{
        font-size: 0.7rem;
        color: {NEON_GREEN};
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 700;
    }}
    .superlative-card .sup-dj {{
        font-size: 1rem;
        font-weight: bold;
        color: {WHITE};
        margin: 4px 0;
    }}
    .superlative-card .sup-stat {{
        font-size: 0.8rem;
        color: #888;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Period definitions
# ---------------------------------------------------------------------------
PERIOD_OPTIONS = [
    "Yesterday",
    "This Week",
    "Last Week",
    "This Month",
    "Last Month",
    "This Year",
    "Last Year",
]


def _get_period_range(label: str) -> tuple[datetime.date, datetime.date]:
    today = datetime.date.today()
    if label == "Yesterday":
        d = today - datetime.timedelta(days=1)
        return d, d
    if label == "This Week":
        mon = today - datetime.timedelta(days=today.weekday())
        return mon, today
    if label == "Last Week":
        mon = today - datetime.timedelta(days=today.weekday() + 7)
        return mon, mon + datetime.timedelta(days=6)
    if label == "This Month":
        return today.replace(day=1), today
    if label == "Last Month":
        first_this = today.replace(day=1)
        last_day = first_this - datetime.timedelta(days=1)
        return last_day.replace(day=1), last_day
    if label == "This Year":
        return today.replace(month=1, day=1), today
    if label == "Last Year":
        return datetime.date(today.year - 1, 1, 1), datetime.date(today.year - 1, 12, 31)
    return today, today


def _filter_period(df: pd.DataFrame, start: datetime.date, end: datetime.date) -> pd.DataFrame:
    mask = df["play_date_parsed"].between(pd.Timestamp(start), pd.Timestamp(end))
    return df[mask].copy()


# ---------------------------------------------------------------------------
# Snapshot stats helpers
# ---------------------------------------------------------------------------
def _top_n(series: pd.Series, n: int = 5) -> list[tuple[str, int]]:
    counts = series.dropna().value_counts().head(n)
    return list(zip(counts.index, counts.values))


def _esc(text: str) -> str:
    return html_mod.escape(str(text))


PLATFORM_LABELS = {
    "spotify": "Spotify",
    "appleMusic": "Apple Music",
    "youtube": "YouTube",
    "youtubeMusic": "YouTube Music",
    "tidal": "Tidal",
    "soundcloud": "SoundCloud",
    "amazonMusic": "Amazon Music",
    "deezer": "Deezer",
}


# ---------------------------------------------------------------------------
# Batch Spotify URL lookups
# ---------------------------------------------------------------------------
def _batch_artist_urls(entries: list[tuple[str, int]]) -> list[str | None]:
    urls: list[str | None] = []
    for name, _ in entries:
        urls.append(get_spotify_url_for_artist(name))
    return urls


def _batch_track_urls(entries: list[tuple[str, int]]) -> list[str | None]:
    urls: list[str | None] = []
    for label, _ in entries:
        parts = label.split(" — ", 1)
        if len(parts) == 2:
            urls.append(get_spotify_url_for_track(parts[0].strip(), parts[1].strip()))
        else:
            urls.append(None)
    return urls


def _batch_release_urls(entries: list[tuple[str, int]], df: pd.DataFrame) -> list[str | None]:
    urls: list[str | None] = []
    for release_name, _ in entries:
        rows = df[df["release"] == release_name]
        if rows.empty:
            urls.append(None)
            continue
        top = rows.groupby(["artist", "song"]).size().idxmax()
        artist, song = top
        if pd.isna(artist) or pd.isna(song):
            urls.append(None)
            continue
        meta = get_spotify_metadata(str(artist), str(song))
        urls.append(meta.get("album_url") if meta else None)
    return urls


# ---------------------------------------------------------------------------
# Card renderers
# ---------------------------------------------------------------------------
def _render_hero_card(
    label: str,
    entries: list[tuple[str, int]],
    image_url: str | None,
    primary_url: str | None,
    platform_links: dict[str, str] | None,
    entry_urls: list[str | None] | None = None,
    cmp_entries: list[tuple[str, int]] | None = None,
) -> None:
    if not entries:
        st.markdown(
            f'<div class="snapshot-card"><h4>{_esc(label)}</h4>'
            '<span style="color:#666">No data</span></div>',
            unsafe_allow_html=True,
        )
        return

    name, count = entries[0]
    safe_name = _esc(name)

    cmp_html = ""
    if cmp_entries:
        cmp_names = [e[0] for e in cmp_entries]
        if name in cmp_names:
            prev_rank = cmp_names.index(name) + 1
            if prev_rank > 1:
                cmp_html = f'<div class="hero-cmp">was #{prev_rank}</div>'
        else:
            cmp_html = '<div class="hero-cmp">new entry</div>'

    img_html = ""
    if image_url:
        img_tag = f'<img class="hero-img" src="{_esc(image_url)}" alt="{safe_name}" />'
        img_html = (
            f'<a href="{_esc(primary_url)}" target="_blank">{img_tag}</a>'
            if primary_url else img_tag
        )

    title_inner = safe_name
    if primary_url:
        title_inner = f'<a href="{_esc(primary_url)}" target="_blank">{safe_name}</a>'

    links_html = ""
    if platform_links:
        link_items = ""
        for plat_key, plat_label in PLATFORM_LABELS.items():
            url = platform_links.get(plat_key)
            if url:
                link_items += f'<a href="{_esc(url)}" target="_blank">{plat_label}</a>'
        if link_items:
            links_html = f'<div class="platform-links">{link_items}</div>'

    runners_html = ""
    for i, (rname, rcount) in enumerate(entries[1:5], start=2):
        rname_safe = _esc(rname)
        rurl = entry_urls[i - 1] if entry_urls and i - 1 < len(entry_urls) else None
        name_part = (
            f'<a href="{_esc(rurl)}" target="_blank">{rname_safe}</a>'
            if rurl else rname_safe
        )
        runners_html += (
            f'<div class="runner-up">'
            f'<span class="rank">#{i}</span>{name_part}'
            f'<span class="count">{rcount:,}</span>'
            f'</div>'
        )

    parts = [
        '<div class="hero-card">',
        img_html,
        '<div class="hero-body">',
        f'<span class="hero-label">{_esc(label)}</span>',
        f'<div class="hero-title">#1 {title_inner}</div>',
        f'<div class="hero-plays">{count:,} plays</div>',
        cmp_html,
        links_html,
        '</div>',
    ]
    if runners_html:
        parts.append(f'<div class="hero-runners">{runners_html}</div>')
    parts.append('</div>')

    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_top_card(
    title: str,
    entries: list[tuple[str, int]],
    cmp_entries: list[tuple[str, int]] | None = None,
    as_dj_links: bool = False,
) -> None:
    if not entries:
        st.markdown(
            f'<div class="snapshot-card"><h4>{_esc(title)}</h4>'
            '<span style="color:#666">No data</span></div>',
            unsafe_allow_html=True,
        )
        return

    name, count = entries[0]
    cmp_note = ""
    if cmp_entries:
        cmp_names = [e[0] for e in cmp_entries]
        if name in cmp_names:
            prev_rank = cmp_names.index(name) + 1
            if prev_rank > 1:
                cmp_note = f' <span style="color:#888;font-size:0.75rem">(was #{prev_rank})</span>'
        else:
            cmp_note = ' <span style="color:#888;font-size:0.75rem">(new)</span>'

    name_html = dj_link_html(name, "font-size:inherit;font-weight:inherit;") if as_dj_links else _esc(name)

    runners_html = ""
    for i, (rname, rcount) in enumerate(entries[1:5], start=2):
        rname_html = dj_link_html(rname) if as_dj_links else _esc(rname)
        runners_html += (
            f'<div class="runner-up">'
            f'<span class="rank">#{i}</span>{rname_html}'
            f'<span class="count">{rcount:,}</span>'
            f'</div>'
        )

    st.markdown(
        f'<div class="snapshot-card">'
        f'<h4>{_esc(title)}</h4>'
        f'<div class="top-entry">#1 {name_html}{cmp_note} '
        f'<span class="plays">{count:,} plays</span></div>'
        f'{runners_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _compute_new_pct(period_df: pd.DataFrame, full_df: pd.DataFrame,
                     col: str, start: datetime.date) -> tuple[float, str | None]:
    period_vals = set(period_df[col].dropna().unique())
    if not period_vals:
        return 0.0, None
    before = full_df[full_df["play_date_parsed"] < pd.Timestamp(start)]
    historical_vals = set(before[col].dropna().unique())
    new_vals = period_vals - historical_vals
    pct = len(new_vals) / len(period_vals) * 100 if period_vals else 0
    top_new = None
    if new_vals:
        new_mask = period_df[col].isin(new_vals)
        top_new_series = period_df.loc[new_mask, col].value_counts()
        if not top_new_series.empty:
            top_new = top_new_series.index[0]
    return pct, top_new


def _render_pct_card(title: str, pct: float, top_new: str | None,
                     cmp_pct: float | None = None,
                     top_new_url: str | None = None) -> None:
    delta_html = ""
    if cmp_pct is not None:
        diff = pct - cmp_pct
        sign = "+" if diff >= 0 else ""
        cls = "positive" if diff >= 0 else "negative"
        delta_html = f'<span class="pct-delta {cls}">{sign}{diff:.0f}pp</span>'

    sub = ""
    if top_new:
        name_part = _esc(top_new)
        if top_new_url:
            name_part = f'<a href="{_esc(top_new_url)}" target="_blank">{name_part}</a>'
        sub = f'<div class="pct-new-link" style="font-size:0.8rem;margin-top:4px;color:#888">Top new: {name_part}</div>'

    st.markdown(
        f'<div class="snapshot-card">'
        f'<h4>{_esc(title)}</h4>'
        f'<span class="pct-big">{pct:.0f}%</span>{delta_html}'
        f'{sub}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Spotify metadata helpers
# ---------------------------------------------------------------------------
def _lookup_artist_meta(artist: str) -> tuple[str | None, str | None, dict]:
    meta = get_spotify_metadata(artist)
    if not meta:
        return None, None, {}
    img = meta.get("artist_img")
    url = meta.get("artist_url")
    plat = get_cross_platform_links(url) if url else {}
    return img, url, plat


def _lookup_track_meta(track_label: str) -> tuple[str | None, str | None, dict]:
    parts = track_label.split(" — ", 1)
    if len(parts) != 2:
        return None, None, {}
    artist, song = parts
    meta = get_spotify_metadata(artist.strip(), song.strip())
    if not meta:
        return None, None, {}
    img = meta.get("track_img")
    url = meta.get("track_url")
    plat = get_cross_platform_links(url) if url else {}
    return img, url, plat


def _lookup_release_meta(release_name: str, p_df: pd.DataFrame) -> tuple[str | None, str | None, dict]:
    release_rows = p_df[p_df["release"] == release_name]
    if release_rows.empty:
        return None, None, {}
    top_song_row = release_rows.groupby(["artist", "song"]).size().idxmax()
    artist, song = top_song_row
    if pd.isna(artist) or pd.isna(song):
        return None, None, {}
    meta = get_spotify_metadata(str(artist), str(song))
    if not meta:
        return None, None, {}
    img = meta.get("album_img")
    url = meta.get("album_url")
    plat = get_cross_platform_links(url) if url else {}
    return img, url, plat


def _get_new_entry_spotify_url(top_new: str | None, kind: str,
                               p_df: pd.DataFrame | None = None) -> str | None:
    if not top_new:
        return None
    if kind == "artist":
        return get_spotify_url_for_artist(top_new)
    if kind == "song":
        rows = p_df[p_df["song"] == top_new] if p_df is not None else pd.DataFrame()
        if rows.empty:
            return None
        artist = rows["artist"].mode()
        if artist.empty:
            return None
        return get_spotify_url_for_track(str(artist.iloc[0]), top_new)
    if kind == "release":
        if p_df is None:
            return None
        rows = p_df[p_df["release"] == top_new]
        if rows.empty:
            return None
        top = rows.groupby(["artist", "song"]).size().idxmax()
        artist, song = top
        if pd.isna(artist) or pd.isna(song):
            return None
        meta = get_spotify_metadata(str(artist), str(song))
        return meta.get("album_url") if meta else None
    return None


# ---------------------------------------------------------------------------
# Timeline helpers
# ---------------------------------------------------------------------------
def _build_timeline_data(
    decade_data: pd.DataFrame, mode: str, p_df: pd.DataFrame,
) -> list[dict]:
    """Build a list of dicts for each decade: {decade, name, plays, img, url}."""
    decades = sorted(decade_data["decade"].dropna().unique())
    items: list[dict] = []
    for dec in decades:
        dec_sub = decade_data[decade_data["decade"] == dec]
        if dec_sub.empty:
            continue

        if mode == "Top Artist":
            top_s = dec_sub["artist"].value_counts()
            if top_s.empty:
                continue
            name = str(top_s.index[0])
            plays = int(top_s.iloc[0])
            meta = get_spotify_metadata(name)
            img = meta.get("artist_img") if meta else None
            url = meta.get("artist_url") if meta else None

        elif mode == "Top Release":
            top_s = dec_sub["release"].value_counts()
            if top_s.empty:
                continue
            name = str(top_s.index[0])
            plays = int(top_s.iloc[0])
            rel_rows = dec_sub[dec_sub["release"] == name]
            rel_artist = rel_rows["artist"].mode()
            artist_name = str(rel_artist.iloc[0]) if not rel_artist.empty else ""
            rel_song = rel_rows["song"].dropna()
            song_name = str(rel_song.iloc[0]) if not rel_song.empty else ""
            meta = get_spotify_metadata(artist_name, song_name) if artist_name and song_name else None
            img = meta.get("album_img") if meta else None
            url = meta.get("album_url") if meta else None

        else:
            dec_sub_t = dec_sub.copy()
            dec_sub_t["_lbl"] = dec_sub_t["artist"].fillna("") + " — " + dec_sub_t["song"].fillna("")
            top_s = dec_sub_t["_lbl"].value_counts()
            if top_s.empty:
                continue
            name = str(top_s.index[0])
            plays = int(top_s.iloc[0])
            parts = name.split(" — ", 1)
            if len(parts) == 2:
                meta = get_spotify_metadata(parts[0].strip(), parts[1].strip())
            else:
                meta = None
            img = meta.get("track_img") if meta else None
            url = meta.get("track_url") if meta else None

        items.append(dict(decade=dec, name=name, plays=plays, img=img, url=url))
    return items


def _render_timeline(items: list[dict]) -> None:
    """Render the decade timeline as a single HTML block."""
    if not items:
        st.info("No release year data available.")
        return

    nodes_html = ""
    for idx, it in enumerate(items):
        pos_class = "above" if idx % 2 == 0 else "below"

        if it["img"]:
            img_el = f'<img src="{_esc(it["img"])}" alt="{_esc(it["name"])}" />'
            img_part = (
                f'<a href="{_esc(it["url"])}" target="_blank">{img_el}</a>'
                if it["url"] else img_el
            )
        else:
            img_part = '<div class="tl-placeholder">No image</div>'

        name_inner = _esc(it["name"])
        if it["url"]:
            name_inner = f'<a href="{_esc(it["url"])}" target="_blank" title="{_esc(it["name"])}">{name_inner}</a>'

        nodes_html += (
            f'<div class="tl-node {pos_class}">'
            f'<div class="tl-bubble">'
            f'{img_part}'
            f'<div class="tl-info">'
            f'<div class="tl-name">{name_inner}</div>'
            f'<div class="tl-plays">{it["plays"]:,} plays</div>'
            f'</div></div>'
            f'<div class="tl-connector"></div>'
            f'<div class="tl-pill">{_esc(it["decade"])}</div>'
            f'</div>'
        )

    html = (
        f'<div class="tl-wrap">'
        f'<div class="tl-track">'
        f'<div class="tl-line"></div>'
        f'{nodes_html}'
        f'</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df_raw = load_data()
render_sidebar_settings()
df_raw = apply_user_tz(df_raw)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
render_page_header("SNAPSHOTS")

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
ctrl_cols = st.columns([2, 1, 2])
with ctrl_cols[0]:
    primary_period = st.selectbox("Period", PERIOD_OPTIONS, index=0, key="snap_primary")
with ctrl_cols[1]:
    compare_on = st.checkbox("Compare?", key="snap_compare")
with ctrl_cols[2]:
    if compare_on:
        cmp_options = [p for p in PERIOD_OPTIONS if p != primary_period]
        cmp_period = st.selectbox("Compare to", cmp_options, index=0, key="snap_cmp")
    else:
        cmp_period = None

p_start, p_end = _get_period_range(primary_period)
p_df = apply_user_tz(_filter_period(df_raw, p_start, p_end))

if cmp_period:
    c_start, c_end = _get_period_range(cmp_period)
    c_df = apply_user_tz(_filter_period(df_raw, c_start, c_end))
else:
    c_start = c_end = None
    c_df = None

st.caption(
    f"**{primary_period}**: {p_start.strftime('%b %d, %Y')} — {p_end.strftime('%b %d, %Y')}  "
    f"({len(p_df):,} plays)"
    + (f"  ·  **{cmp_period}**: {c_start.strftime('%b %d, %Y')} — {c_end.strftime('%b %d, %Y')}  "
       f"({len(c_df):,} plays)" if c_df is not None else "")
)

if p_df.empty:
    st.warning(f"No plays found for **{primary_period}** ({p_start} — {p_end}).")
    st.stop()

# ---------------------------------------------------------------------------
# Row 1 — Key metrics
# ---------------------------------------------------------------------------
st.markdown("---")
m1, m2, m3, m4 = st.columns(4)

plays_val = len(p_df)
artists_val = p_df["artist"].nunique()
tracks_val = p_df["song"].nunique()
dur_min = p_df["duration_min"].sum()
hours_val = dur_min / 60 if pd.notna(dur_min) and dur_min > 0 else None

if c_df is not None and not c_df.empty:
    plays_delta = plays_val - len(c_df)
    artists_delta = artists_val - c_df["artist"].nunique()
    tracks_delta = tracks_val - c_df["song"].nunique()
    c_dur = c_df["duration_min"].sum()
    c_hours = c_dur / 60 if pd.notna(c_dur) and c_dur > 0 else None
    hours_delta = (hours_val - c_hours) if hours_val and c_hours else None
else:
    plays_delta = artists_delta = tracks_delta = hours_delta = None

m1.metric("Total Plays", f"{plays_val:,}",
          delta=f"{plays_delta:+,}" if plays_delta is not None else None)
m2.metric("Artists", f"{artists_val:,}",
          delta=f"{artists_delta:+,}" if artists_delta is not None else None)
m3.metric("Tracks", f"{tracks_val:,}",
          delta=f"{tracks_delta:+,}" if tracks_delta is not None else None)
m4.metric("Hours Played", f"{hours_val:,.1f}" if hours_val else "N/A",
          delta=f"{hours_delta:+,.1f}" if hours_delta is not None else None)

# ---------------------------------------------------------------------------
# Row 2 — Top Artist / Top Release / Top Track  (with artwork + links)
# ---------------------------------------------------------------------------
st.markdown("---")
t1, t2, t3 = st.columns(3)

p_artists = _top_n(p_df["artist"])
p_releases = _top_n(p_df["release"])
p_tracks = _top_n(p_df["artist"].fillna("") + " — " + p_df["song"].fillna(""))

c_artists = _top_n(c_df["artist"]) if c_df is not None else None
c_releases = _top_n(c_df["release"]) if c_df is not None else None
c_tracks = (
    _top_n(c_df["artist"].fillna("") + " — " + c_df["song"].fillna(""))
    if c_df is not None else None
)

art_img, art_url, art_plat = (
    _lookup_artist_meta(p_artists[0][0]) if p_artists else (None, None, {})
)
rel_img, rel_url, rel_plat = (
    _lookup_release_meta(p_releases[0][0], p_df) if p_releases else (None, None, {})
)
trk_img, trk_url, trk_plat = (
    _lookup_track_meta(p_tracks[0][0]) if p_tracks else (None, None, {})
)

art_entry_urls = _batch_artist_urls(p_artists) if p_artists else []
rel_entry_urls = _batch_release_urls(p_releases, p_df) if p_releases else []
trk_entry_urls = _batch_track_urls(p_tracks) if p_tracks else []

with t1:
    _render_hero_card("Top Artist", p_artists, art_img, art_url, art_plat,
                      entry_urls=art_entry_urls, cmp_entries=c_artists)
with t2:
    _render_hero_card("Top Release", p_releases, rel_img, rel_url, rel_plat,
                      entry_urls=rel_entry_urls, cmp_entries=c_releases)
with t3:
    _render_hero_card("Top Track", p_tracks, trk_img, trk_url, trk_plat,
                      entry_urls=trk_entry_urls, cmp_entries=c_tracks)

# ---------------------------------------------------------------------------
# Row 3 — "New" percentages (with Spotify links on top new entry)
# ---------------------------------------------------------------------------
st.markdown("---")
n1, n2, n3 = st.columns(3)

p_new_art_pct, p_new_art_top = _compute_new_pct(p_df, df_raw, "artist", p_start)
p_new_rel_pct, p_new_rel_top = _compute_new_pct(p_df, df_raw, "release", p_start)
p_new_trk_pct, p_new_trk_top = _compute_new_pct(p_df, df_raw, "song", p_start)

new_art_url = _get_new_entry_spotify_url(p_new_art_top, "artist")
new_rel_url = _get_new_entry_spotify_url(p_new_rel_top, "release", p_df)
new_trk_url = _get_new_entry_spotify_url(p_new_trk_top, "song", p_df)

if c_df is not None and c_start is not None:
    c_new_art_pct, _ = _compute_new_pct(c_df, df_raw, "artist", c_start)
    c_new_rel_pct, _ = _compute_new_pct(c_df, df_raw, "release", c_start)
    c_new_trk_pct, _ = _compute_new_pct(c_df, df_raw, "song", c_start)
else:
    c_new_art_pct = c_new_rel_pct = c_new_trk_pct = None

with n1:
    _render_pct_card("New Artists", p_new_art_pct, p_new_art_top,
                     c_new_art_pct, top_new_url=new_art_url)
with n2:
    _render_pct_card("New Releases", p_new_rel_pct, p_new_rel_top,
                     c_new_rel_pct, top_new_url=new_rel_url)
with n3:
    _render_pct_card("New Tracks", p_new_trk_pct, p_new_trk_top,
                     c_new_trk_pct, top_new_url=new_trk_url)

# ---------------------------------------------------------------------------
# Row 4 — Top DJ and Top Label
# ---------------------------------------------------------------------------
st.markdown("---")
d1, d2 = st.columns(2)

p_djs = _top_n(p_df["dj_name"])
p_labels = _top_n(p_df["label"])
c_djs = _top_n(c_df["dj_name"]) if c_df is not None else None
c_labels = _top_n(c_df["label"]) if c_df is not None else None

with d1:
    _render_top_card("Top DJ", p_djs, c_djs, as_dj_links=True)
with d2:
    _render_top_card("Top Label", p_labels, c_labels)

# ---------------------------------------------------------------------------
# Row 4b — Superlatives
# ---------------------------------------------------------------------------
MIN_PLAYS_FOR_SUPERLATIVE = 5

SUPERLATIVE_ICONS = {
    "The Old Soul": "fa-solid fa-compact-disc",
    "The Crate Digger": "fa-solid fa-box-open",
    "The Creature of Habit": "fa-solid fa-repeat",
    "The Slow Burner": "fa-solid fa-fire",
    "The Decade Hopper": "fa-solid fa-timeline",
    "Best Friends": "fa-solid fa-heart",
}

dj_groups = p_df.groupby("dj_name", dropna=True)
qualified_djs = [name for name, grp in dj_groups if len(grp) >= MIN_PLAYS_FOR_SUPERLATIVE]

if len(qualified_djs) >= 1:
    sup_results: list[tuple[str, str, str]] = []

    # 1) The Old Soul -- lowest median release year
    median_years = (
        p_df.dropna(subset=["release_year"])
        .groupby("dj_name")["release_year"]
        .median()
    )
    median_years = median_years[median_years.index.isin(qualified_djs)]
    if not median_years.empty:
        winner = median_years.idxmin()
        val = int(median_years.min())
        sup_results.append(("The Old Soul", str(winner), f"Median year: {val}"))
    else:
        sup_results.append(("The Old Soul", "—", "No data"))

    # 2) The Crate Digger -- highest % new artists
    best_crate, best_crate_pct = "—", 0.0
    for dj in qualified_djs:
        dj_df = p_df[p_df["dj_name"] == dj]
        pct, _ = _compute_new_pct(dj_df, df_raw, "artist", p_start)
        if pct > best_crate_pct:
            best_crate_pct = pct
            best_crate = dj
    sup_results.append(("The Crate Digger",
                        str(best_crate), f"{best_crate_pct:.0f}% new artists"))

    # 3) The Creature of Habit -- highest plays / unique songs
    repeat_rates = {}
    for dj in qualified_djs:
        dj_df = p_df[p_df["dj_name"] == dj]
        unique_songs = dj_df["song"].nunique()
        if unique_songs > 0:
            repeat_rates[dj] = len(dj_df) / unique_songs
    if repeat_rates:
        winner = max(repeat_rates, key=repeat_rates.get)
        sup_results.append(("The Creature of Habit",
                            str(winner), f"{repeat_rates[winner]:.1f}x repeat rate"))
    else:
        sup_results.append(("The Creature of Habit", "—", "No data"))

    # 4) The Slow Burner -- longest avg duration
    avg_dur = (
        p_df.dropna(subset=["duration_min"])
        .groupby("dj_name")["duration_min"]
        .mean()
    )
    avg_dur = avg_dur[avg_dur.index.isin(qualified_djs)]
    if not avg_dur.empty:
        winner = avg_dur.idxmax()
        val = avg_dur.max()
        sup_results.append(("The Slow Burner",
                            str(winner), f"Avg {val:.1f} min/track"))
    else:
        sup_results.append(("The Slow Burner", "—", "No data"))

    # 5) The Decade Hopper -- most distinct decades
    dec_counts = (
        p_df.dropna(subset=["decade"])
        .groupby("dj_name")["decade"]
        .nunique()
    )
    dec_counts = dec_counts[dec_counts.index.isin(qualified_djs)]
    if not dec_counts.empty:
        winner = dec_counts.idxmax()
        val = int(dec_counts.max())
        sup_results.append(("The Decade Hopper",
                            str(winner), f"{val} decades"))
    else:
        sup_results.append(("The Decade Hopper", "—", "No data"))

    # 6) Best Friends -- most compatible DJ pair (Jaccard on artist sets)
    if len(qualified_djs) >= 2:
        best_pair, best_jacc = ("—", "—"), 0.0
        for i_dj, dj_a in enumerate(qualified_djs):
            set_a = set(p_df.loc[p_df["dj_name"] == dj_a, "artist"].dropna().unique())
            for dj_b in qualified_djs[i_dj + 1:]:
                set_b = set(p_df.loc[p_df["dj_name"] == dj_b, "artist"].dropna().unique())
                union = set_a | set_b
                if union:
                    jacc = len(set_a & set_b) / len(union)
                    if jacc > best_jacc:
                        best_jacc = jacc
                        best_pair = (dj_a, dj_b)
        sup_results.append((
            "Best Friends",
            f"{best_pair[0]} \u2665 {best_pair[1]}",
            f"{best_jacc * 100:.0f}% artist overlap",
        ))
    else:
        sup_results.append(("Best Friends", "—", "Need 2+ DJs"))

    st.markdown("---")
    st.markdown("### Superlatives")
    sup_cols = st.columns(len(sup_results))
    for i, (title, dj_name, stat) in enumerate(sup_results):
        icon_class = SUPERLATIVE_ICONS.get(title, "fa-solid fa-star")
        if title == "Best Friends" and "\u2665" in dj_name:
            parts = dj_name.split(" \u2665 ")
            dj_html = " &hearts; ".join(
                dj_link_html(p.strip(), "font-size:inherit;font-weight:inherit;")
                for p in parts
            )
        elif dj_name != "—":
            dj_html = dj_link_html(dj_name, "font-size:inherit;font-weight:inherit;")
        else:
            dj_html = _esc(dj_name)
        with sup_cols[i]:
            st.markdown(
                f'<div class="superlative-card">'
                f'<i class="{icon_class}"></i>'
                f'<div class="sup-title">{_esc(title)}</div>'
                f'<div class="sup-dj">{dj_html}</div>'
                f'<div class="sup-stat">{_esc(stat)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Row 5 — Day-of-week comparison (compare mode)
# ---------------------------------------------------------------------------
if c_df is not None:
    st.markdown("---")
    st.markdown("### Plays by Day of Week")
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    p_dow = (
        p_df.dropna(subset=["play_dow"])
        .groupby("play_dow").size()
        .reindex(dow_order, fill_value=0)
        .reset_index(name="plays")
    )
    p_dow["period"] = primary_period

    c_dow = (
        c_df.dropna(subset=["play_dow"])
        .groupby("play_dow").size()
        .reindex(dow_order, fill_value=0)
        .reset_index(name="plays")
    )
    c_dow["period"] = cmp_period

    combined = add_plays_label(pd.concat([p_dow, c_dow], ignore_index=True))

    fig = px.bar(
        combined, x="play_dow", y="plays", color="period",
        text="plays_label", barmode="group",
        color_discrete_sequence=[NEON_GREEN, PURPLE], template=PLOT_TEMPLATE,
        category_orders={"play_dow": dow_order},
    )
    fig.update_traces(textposition="outside", textfont_size=10)
    fig.update_layout(
        xaxis_title=None, yaxis_title="Plays",
        legend_title_text="Period",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Row 6 — Music by Decade Timeline
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Music by Decade")

decade_data = p_df.dropna(subset=["decade"])
if not decade_data.empty:
    tl_mode = st.radio(
        "Show", ["Top Artist", "Top Release", "Top Track"],
        horizontal=True, key="tl_mode",
    )
    tl_items = _build_timeline_data(decade_data, tl_mode, p_df)
    _render_timeline(tl_items)
else:
    st.info("No release year data available.")
