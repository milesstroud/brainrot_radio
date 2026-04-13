"""
Shared Spotify matching and playlist helpers for spin_to_spotify and backfill scripts.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Iterable, Optional

import pandas as pd
from rapidfuzz import fuzz
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from unidecode import unidecode

logger = logging.getLogger(__name__)

SPOTIFY_CHUNK_SIZE = 100


def normalize_text(text: Any) -> Any:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return text
    s = str(text)
    return unidecode(s).lower().strip()


def fuzzy_match_spotify(
    song: str,
    artist: str,
    spotify_results: Optional[dict],
    threshold: float = 80,
) -> Optional[str]:
    best_match = None
    best_score = 0.0
    tracks = (
        (spotify_results or {}).get("tracks", {}).get("items", [])
        if isinstance(spotify_results, dict)
        else []
    )
    for track in tracks:
        track_name = track.get("name", "")
        track_artists = [a.get("name", "") for a in track.get("artists", [])]
        if not track_name or not track_artists:
            continue
        song_score = fuzz.ratio(str(song).lower(), track_name.lower())
        artist_score = max(fuzz.ratio(str(artist).lower(), a.lower()) for a in track_artists)
        total_score = (song_score * 0.6) + (artist_score * 0.4)
        if total_score > best_score and total_score >= threshold:
            best_score = total_score
            best_match = track.get("id")
    return best_match


def search_spotify_tracks(sp: Spotify, song: str, artist: str, limit: int = 10) -> dict:
    query = f"{song} {artist}"
    return sp.search(q=query, type="track", limit=limit)


def search_track_by_isrc(sp: Spotify, isrc: str) -> Optional[str]:
    isrc = str(isrc).strip().upper()
    if len(isrc) < 12:
        return None
    results = sp.search(q=f"isrc:{isrc}", type="track", limit=5)
    items = (results or {}).get("tracks", {}).get("items", []) or []
    if not items:
        return None
    return items[0].get("id")


def resolve_spotify_track_id(
    sp: Spotify,
    title: Any,
    artist: Any,
    isrc: Any = None,
    fuzzy_threshold: float = 80,
) -> Optional[str]:
    if pd.isna(title) or pd.isna(artist) or not str(title).strip() or not str(artist).strip():
        return None
    isrc_clean: Optional[str] = None
    if isrc is not None:
        try:
            if not pd.isna(isrc):
                isrc_clean = str(isrc).strip() or None
        except (TypeError, ValueError):
            isrc_clean = str(isrc).strip() or None
    if isrc_clean:
        tid = search_track_by_isrc(sp, isrc_clean)
        if tid:
            return tid
    try:
        spotify_results = search_spotify_tracks(sp, str(title), str(artist))
    except Exception:
        logger.exception("Spotify search failed for %s / %s", artist, title)
        return None
    return fuzzy_match_spotify(str(title), str(artist), spotify_results, threshold=fuzzy_threshold)


def get_spotify_client_from_env() -> Spotify:
    scope = os.getenv("SPOTIPY_SCOPE")
    username = os.getenv("SPOTIFY_USERNAME")
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_SECRET")
    redirect_uri = os.getenv("REDIRECT_URI")
    cache_path = os.getenv("SPOTIPY_CACHE_PATH") or os.path.join(
        tempfile.gettempdir(), ".spotify_token_cache"
    )

    missing = [
        name
        for name, val in [
            ("SPOTIPY_SCOPE", scope),
            ("SPOTIFY_USERNAME", username),
            ("SPOTIPY_CLIENT_ID", client_id),
            ("SPOTIPY_SECRET", client_secret),
            ("REDIRECT_URI", redirect_uri),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    auth = SpotifyOAuth(
        scope=scope,
        username=username,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        cache_path=cache_path,
        open_browser=False,
    )
    return Spotify(auth_manager=auth)


def get_playlist_track_id_set(sp: Spotify, playlist_id: str) -> set[str]:
    ids: set[str] = set()
    results = sp.playlist_items(playlist_id, additional_types=("track",))
    while True:
        for item in results.get("items", []) or []:
            track = item.get("track") or {}
            tid = track.get("id")
            if tid:
                ids.add(tid)
        next_url = results.get("next")
        if not next_url:
            break
        results = sp.next(results)
    return ids


def add_tracks_to_playlist_batched(
    sp: Spotify,
    playlist_id: str,
    track_ids: Iterable[str],
    dry_run: bool = False,
) -> int:
    ids = [t for t in track_ids if t]
    if not ids:
        return 0
    added = 0
    for i in range(0, len(ids), SPOTIFY_CHUNK_SIZE):
        chunk = ids[i : i + SPOTIFY_CHUNK_SIZE]
        if dry_run:
            logger.info("Dry-run: would add %d tracks to playlist", len(chunk))
            added += len(chunk)
        else:
            sp.playlist_add_items(playlist_id, chunk)
            added += len(chunk)
    return added


def _needs_translation(s: str) -> bool:
    return any(ord(c) > 127 for c in s)


def apply_normalize_and_translate(
    df: pd.DataFrame,
    cols: list[str],
) -> None:
    """
    Normalize text columns; optionally run googletrans.
    Translation runs only for non-ASCII strings unless ENABLE_GOOGLETRANS=1 (all strings).
    Set ENABLE_GOOGLETRANS=0 to disable translation entirely.
    """
    for c in cols:
        if c in df.columns:
            df[c] = df[c].map(normalize_text)

    enable = os.getenv("ENABLE_GOOGLETRANS", "").strip().lower()
    if enable == "0":
        return

    force_all = enable == "1"
    try:
        from googletrans import Translator
    except ImportError:
        logger.warning("googletrans not installed; skipping translation")
        return

    translator = Translator()
    translation_map: dict[Any, Any] = {}
    unique_vals = pd.unique(df[cols].values.ravel())

    for text in unique_vals:
        if pd.isna(text):
            translation_map[text] = text
            continue
        st = str(text)
        if not force_all and not _needs_translation(st):
            translation_map[text] = text
            continue
        try:
            translation_map[text] = translator.translate(st, dest="en").text
        except Exception:
            logger.debug("Translation failed for %r; keeping normalized text", st)
            translation_map[text] = text

    for col in cols:
        if col in df.columns:
            df[col] = df[col].map(translation_map)
