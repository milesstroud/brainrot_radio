"""
Backfill a Spotify playlist from a Spinitron CSV export (e.g. Spins-search-results).

Maps columns: Artist, Song -> artist/title; Release -> album context (search uses title+artist).
Sorts by spin time using Date-time (ISO) when present, else Date + Time.
If an ISRC column exists (case-insensitive header match), it is tried before fuzzy search.

Use --limit N with --dry-run to test on the first N chronological rows without modifying the playlist.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

import pandas as pd
from dotenv import find_dotenv, load_dotenv

from spotify_spin_common import (
    add_tracks_to_playlist_batched,
    apply_normalize_and_translate,
    get_playlist_track_id_set,
    get_spotify_client_from_env,
    resolve_spotify_track_id,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    lower = {c.lower().strip(): c for c in df.columns}

    def pick(*names: str) -> str | None:
        for n in names:
            if n.lower() in lower:
                return lower[n.lower()]
        return None

    col_artist = pick("Artist")
    col_song = pick("Song", "Title")
    col_dt = pick("Date-time", "Date-Time", "Datetime")
    col_date = pick("Date")
    col_time = pick("Time")
    col_isrc = pick("ISRC", "isrc")
    col_album = pick("Release", "Album")

    if not col_artist or not col_song:
        raise ValueError("CSV must include Artist and Song (or Title) columns")

    n = len(df)
    out = pd.DataFrame(
        {
            "Artist": df[col_artist],
            "Title": df[col_song],
            "Album": df[col_album] if col_album else pd.Series([pd.NA] * n, dtype=object),
        }
    )
    if col_isrc:
        out["ISRC"] = df[col_isrc]
    else:
        out["ISRC"] = pd.Series([pd.NA] * n, dtype=object)

    if col_dt and col_dt in df.columns:
        out["played_at"] = pd.to_datetime(df[col_dt], utc=True, errors="coerce")
    elif col_date and col_time:
        combined = df[col_date].astype(str).str.strip() + " " + df[col_time].astype(str).str.strip()
        out["played_at"] = pd.to_datetime(combined, errors="coerce")
    else:
        raise ValueError("CSV must include Date-time or both Date and Time for ordering")

    out = out.dropna(subset=["played_at"])
    out = out.sort_values("played_at", ascending=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Spotify playlist from Spinitron CSV export")
    parser.add_argument("csv_path", help="Path to spins CSV file")
    parser.add_argument("--dry-run", action="store_true", help="Resolve matches but do not modify playlist")
    parser.add_argument("--playlist-id", default=None, help="Override SPOTIFY_PLAYLIST_ID")
    parser.add_argument(
        "--no-skip-duplicates",
        action="store_true",
        help="Add tracks even if already on the playlist (default: skip duplicates)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N rows after sorting by play time (for testing)",
    )
    args = parser.parse_args()

    load_dotenv(find_dotenv())
    playlist_id = args.playlist_id or os.getenv("SPOTIFY_PLAYLIST_ID")
    if not playlist_id:
        logger.error("Set SPOTIFY_PLAYLIST_ID or pass --playlist-id")
        sys.exit(1)

    df = pd.read_csv(args.csv_path)
    work = _normalize_columns(df)
    logger.info("Loaded %d rows with valid play times", len(work))
    if args.limit is not None:
        if args.limit < 1:
            logger.error("--limit must be at least 1")
            sys.exit(1)
        work = work.head(args.limit)
        logger.info("Limited to first %d rows after sort", len(work))

    sp = get_spotify_client_from_env()
    existing_ids: set[str] = set()
    if not args.no_skip_duplicates:
        existing_ids = get_playlist_track_id_set(sp, playlist_id)

    text_cols = ["Title", "Album", "Artist"]
    apply_normalize_and_translate(work, text_cols)

    new_track_ids: list[str] = []
    unresolved = 0
    for row in work.itertuples(index=False):
        title = row.Title
        artist = row.Artist
        if pd.isna(title) or pd.isna(artist) or not str(title).strip() or not str(artist).strip():
            unresolved += 1
            continue
        isrc = getattr(row, "ISRC", None)
        tid = resolve_spotify_track_id(sp, title, artist, isrc=isrc)
        if not tid:
            unresolved += 1
            continue
        if not args.no_skip_duplicates and tid in existing_ids:
            continue
        new_track_ids.append(tid)
        if not args.no_skip_duplicates:
            existing_ids.add(tid)

    logger.info(
        "Resolved %d new tracks to add (%d unresolved or duplicate skipped)",
        len(new_track_ids),
        unresolved,
    )
    add_tracks_to_playlist_batched(sp, playlist_id, new_track_ids, dry_run=args.dry_run)
    if args.dry_run:
        logger.info("Dry-run complete; no playlist changes made")
    else:
        logger.info("Done; added %d tracks", len(new_track_ids))


if __name__ == "__main__":
    main()
