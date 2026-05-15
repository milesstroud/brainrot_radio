"""
Backfill artist genres from the last.fm API into the artist_genres table.

Fetches the top tags for each unique artist in brainrot_radio that doesn't
already have a cached genre, then stores the cleaned top tag via
pick_top_genre().

Idempotent — safe to re-run; existing artists are skipped.

Usage:
    python backfill_genres.py                 # fetch missing artists only
    python backfill_genres.py --retry-unknown  # re-fetch artists stored as 'unknown'
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time as _time
import unicodedata

import ftfy
import requests
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from shared import pick_top_genre

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LASTFM_BASE = "https://ws.audioscrobbler.com/2.0/"
REQUEST_DELAY = 0.2
PROGRESS_EVERY = 50

_FEAT_SPLIT = re.compile(
    r"\s*(?:&|feat\.?|ft\.?|\+|/|\bx\b|\bvs\.?\b)\s*",
    re.IGNORECASE,
)


def _primary_artist(name: str) -> str | None:
    """Extract the primary artist from a collaborative name, or None."""
    parts = _FEAT_SPLIT.split(name, maxsplit=1)
    primary = parts[0].strip()
    return primary if primary and primary.lower() != name.lower().strip() else None


def _build_engine():
    load_dotenv(find_dotenv())
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "postgres"),
    )
    return create_engine(url)


def _normalize(val: str) -> str:
    return unicodedata.normalize("NFC", ftfy.fix_text(str(val))).strip()


def ensure_table(engine, schema: str) -> None:
    ddl = text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}".artist_genres (
            artist_name TEXT PRIMARY KEY,
            top_genre   TEXT,
            tags_json   TEXT,
            fetched_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    with engine.begin() as conn:
        conn.execute(ddl)
    logger.info("Ensured artist_genres table exists in schema '%s'", schema)


def get_distinct_artists(engine, schema: str) -> list[str]:
    q = text(f'SELECT DISTINCT artist FROM "{schema}".brainrot_radio WHERE artist IS NOT NULL')
    with engine.connect() as conn:
        rows = conn.execute(q).fetchall()
    return [_normalize(r[0]) for r in rows]


def get_cached_artists(engine, schema: str) -> set[str]:
    q = text(f'SELECT artist_name FROM "{schema}".artist_genres')
    with engine.connect() as conn:
        rows = conn.execute(q).fetchall()
    return {r[0] for r in rows}


def get_unknown_artists(engine, schema: str) -> list[str]:
    """Return artists currently stored with top_genre = 'unknown'."""
    q = text(f"""SELECT artist_name FROM "{schema}".artist_genres WHERE top_genre = 'unknown'""")
    with engine.connect() as conn:
        rows = conn.execute(q).fetchall()
    return [r[0] for r in rows]


def fetch_artist_tags(artist: str, api_key: str) -> list[dict]:
    """Call last.fm artist.getTopTags and return the tag list."""
    params = {
        "method": "artist.gettoptags",
        "artist": artist,
        "api_key": api_key,
        "format": "json",
        "autocorrect": "1",
    }
    resp = requests.get(LASTFM_BASE, params=params, timeout=15)
    if resp.status_code == 429:
        raise RateLimitError
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        return []
    return data.get("toptags", {}).get("tag", []) or []


def fetch_artist_tags_with_fallback(artist: str, api_key: str) -> list[dict]:
    """Fetch tags, falling back to primary artist name for collaborations."""
    tags = fetch_artist_tags(artist, api_key)
    if not tags:
        primary = _primary_artist(artist)
        if primary:
            tags = fetch_artist_tags(primary, api_key)
    return tags


class RateLimitError(Exception):
    pass


def insert_genre(engine, schema: str, artist: str, top_genre: str, tags_json: str) -> None:
    q = text(f"""
        INSERT INTO "{schema}".artist_genres (artist_name, top_genre, tags_json)
        VALUES (:artist, :genre, :tags)
        ON CONFLICT (artist_name) DO NOTHING
    """)
    with engine.begin() as conn:
        conn.execute(q, {"artist": artist, "genre": top_genre, "tags": tags_json})


def update_genre(engine, schema: str, artist: str, top_genre: str, tags_json: str) -> None:
    """Overwrite an existing row (used by --retry-unknown)."""
    q = text(f"""
        UPDATE "{schema}".artist_genres
        SET top_genre = :genre, tags_json = :tags, fetched_at = NOW()
        WHERE artist_name = :artist
    """)
    with engine.begin() as conn:
        conn.execute(q, {"artist": artist, "genre": top_genre, "tags": tags_json})


def _fetch_and_store(artist: str, api_key: str, engine, schema: str,
                     *, update: bool = False) -> bool:
    """Fetch tags for one artist, store result. Returns True on success."""
    tags = fetch_artist_tags_with_fallback(artist, api_key)
    top = pick_top_genre(tags)
    tags_data = [{"name": t.get("name", ""), "count": int(t.get("count", 0))}
                 for t in tags[:20]]
    if update:
        update_genre(engine, schema, artist, top, json.dumps(tags_data))
    else:
        insert_genre(engine, schema, artist, top, json.dumps(tags_data))
    return True


def backfill(engine, schema: str, api_key: str) -> int:
    ensure_table(engine, schema)
    all_artists = get_distinct_artists(engine, schema)
    cached = get_cached_artists(engine, schema)
    missing = [a for a in all_artists if a not in cached]

    logger.info(
        "Total unique artists: %d | Already cached: %d | To fetch: %d",
        len(all_artists), len(cached), len(missing),
    )

    if not missing:
        logger.info("Nothing to backfill.")
        return 0

    fetched = 0
    backoff = 0
    for i, artist in enumerate(missing, 1):
        try:
            _fetch_and_store(artist, api_key, engine, schema)
            fetched += 1
            backoff = 0
        except RateLimitError:
            wait = [10, 30, 60][min(backoff, 2)]
            logger.warning("Rate limited — sleeping %ds", wait)
            _time.sleep(wait)
            backoff += 1
            continue
        except requests.RequestException as exc:
            logger.warning("HTTP error for '%s': %s — skipping", artist, exc)
            insert_genre(engine, schema, artist, "unknown", "[]")
            fetched += 1
        except Exception as exc:
            logger.warning("Unexpected error for '%s': %s — skipping", artist, exc)
            insert_genre(engine, schema, artist, "unknown", "[]")
            fetched += 1

        if i % PROGRESS_EVERY == 0:
            logger.info("Progress: %d / %d fetched", i, len(missing))

        _time.sleep(REQUEST_DELAY)

    logger.info("Backfill complete. Fetched genres for %d artists.", fetched)
    return fetched


def retry_unknown(engine, schema: str, api_key: str) -> int:
    """Re-fetch artists whose genre is currently 'unknown'."""
    ensure_table(engine, schema)
    unknowns = get_unknown_artists(engine, schema)
    logger.info("Found %d artists with genre 'unknown' to retry", len(unknowns))

    if not unknowns:
        return 0

    fixed = 0
    backoff = 0
    for i, artist in enumerate(unknowns, 1):
        try:
            _fetch_and_store(artist, api_key, engine, schema, update=True)
            fixed += 1
            backoff = 0
        except RateLimitError:
            wait = [10, 30, 60][min(backoff, 2)]
            logger.warning("Rate limited — sleeping %ds", wait)
            _time.sleep(wait)
            backoff += 1
            continue
        except requests.RequestException as exc:
            logger.warning("HTTP error for '%s': %s — skipping", artist, exc)
        except Exception as exc:
            logger.warning("Unexpected error for '%s': %s — skipping", artist, exc)

        if i % PROGRESS_EVERY == 0:
            logger.info("Retry progress: %d / %d", i, len(unknowns))

        _time.sleep(REQUEST_DELAY)

    logger.info("Retry complete. Updated %d artists.", fixed)
    return fixed


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill artist genres from last.fm")
    parser.add_argument(
        "--retry-unknown",
        action="store_true",
        help="Re-fetch artists stored as 'unknown', trying featured-artist splitting",
    )
    args = parser.parse_args()

    load_dotenv(find_dotenv())
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        logger.error("Missing LASTFM_API_KEY in environment")
        sys.exit(1)

    engine = _build_engine()
    schema = os.environ.get("POSTGRES_SCHEMA", "public")

    backfill(engine, schema, api_key)

    if args.retry_unknown:
        retry_unknown(engine, schema, api_key)


if __name__ == "__main__":
    main()
