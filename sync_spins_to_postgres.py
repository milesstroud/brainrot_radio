"""
Continuously sync Spinitron spins into the brainrot_radio PostgreSQL table.

Fetches recent spins from the Spinitron API, resolves playlist and persona
details for show/DJ metadata, and INSERTs only new rows (deduped by spin_id).

Designed to run as a scheduled task (e.g. hourly on PythonAnywhere).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time as _time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SPINITRON_BASE = "https://spinitron.com/api"
SPINS_PER_PAGE = 200
DEFAULT_MAX_PAGES = 50
REQUEST_DELAY = 1.0


# ---------------------------------------------------------------------------
# Spinitron API helpers
# ---------------------------------------------------------------------------

def _api_get(api_key: str, path: str, params: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{SPINITRON_BASE}{path}"
    r = requests.get(url, headers=headers, params=params or {}, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_full_spins(
    api_key: str,
    *,
    start: str | None = None,
    end: str | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[dict]:
    """Paginate GET /spins and return all spin objects."""
    spins: list[dict] = []
    for page in range(1, max_pages + 1):
        params: dict = {"count": SPINS_PER_PAGE, "page": page}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        data = _api_get(api_key, "/spins", params)
        items = data.get("items") or []
        if not items:
            break
        spins.extend(items)
        logger.info("Fetched spins page %d (%d items)", page, len(items))
        total_pages = data.get("_meta", {}).get("pageCount", max_pages)
        if page >= total_pages:
            break
        _time.sleep(REQUEST_DELAY)
    return spins


_playlist_cache: dict[int, dict] = {}
_persona_cache: dict[int, dict] = {}


def fetch_playlist(api_key: str, playlist_id: int) -> dict:
    if playlist_id in _playlist_cache:
        return _playlist_cache[playlist_id]
    data = _api_get(api_key, f"/playlists/{playlist_id}")
    _playlist_cache[playlist_id] = data
    _time.sleep(REQUEST_DELAY)
    return data


def fetch_persona(api_key: str, persona_id: int) -> dict:
    if persona_id in _persona_cache:
        return _persona_cache[persona_id]
    data = _api_get(api_key, f"/personas/{persona_id}")
    _persona_cache[persona_id] = data
    _time.sleep(REQUEST_DELAY)
    return data


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

def _fmt_duration(seconds: int | None) -> str | None:
    """Convert duration in seconds to MM:SS string."""
    if seconds is None:
        return None
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _parse_dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _empty_to_none(v):
    return None if v == "" else v


def map_spin_to_row(spin: dict, playlist: dict, persona: dict) -> dict:
    """Map Spinitron API objects to a dict matching the DB columns."""
    play_dt = _parse_dt(spin.get("start"))
    pl_dt = _parse_dt(playlist.get("start"))

    row = {
        "spin_id": spin.get("id"),
        "playlist_date": pl_dt.strftime("%Y-%m-%d") if pl_dt else None,
        "playlist_time": pl_dt.strftime("%H:%M:%S") if pl_dt else None,
        "playlist_datetime": pl_dt.isoformat() if pl_dt else None,
        "playlist_title": playlist.get("title"),
        "playlist_category": playlist.get("category"),
        "playlist_duration": playlist.get("duration"),
        "dj_id": persona.get("id"),
        "dj_name": persona.get("name"),
        "play_date": play_dt.strftime("%Y-%m-%d") if play_dt else None,
        "play_time": play_dt.strftime("%H:%M:%S") if play_dt else None,
        "play_datetime": play_dt.isoformat() if play_dt else None,
        "artist": spin.get("artist"),
        "song": spin.get("song"),
        "release": spin.get("release"),
        "duration": _fmt_duration(spin.get("duration")),
        "request": spin.get("request"),
        "is_new": spin.get("new"),
        "song_custom_field": spin.get("artist-custom"),
        "local": spin.get("local"),
        "genre": spin.get("genre"),
        "medium": spin.get("medium"),
        "released": spin.get("released"),
        "added": None,
        "catalog": spin.get("catalog-number"),
        "release_custom_field": spin.get("release-custom"),
        "song_note": spin.get("note"),
        "label": spin.get("label"),
        "upc": spin.get("upc"),
    }
    return {k: _empty_to_none(v) for k, v in row.items()}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def build_engine():
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


def get_existing_spin_ids(engine, schema: str) -> set[int]:
    query = text(
        f'SELECT spin_id FROM "{schema}".brainrot_radio '
        f"WHERE spin_id IS NOT NULL"
    )
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    return {r[0] for r in rows}


def get_existing_fingerprints(engine, schema: str) -> set[tuple]:
    """Return a set of (play_datetime, artist, song, dj_name) tuples for all
    rows in the table.  Used as a secondary dedup check so that CSV-seeded
    rows (NULL spin_id) are recognised as already existing."""
    query = text(
        f'SELECT play_datetime, artist, song, dj_name '
        f'FROM "{schema}".brainrot_radio'
    )
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    return {(str(r[0]), r[1], r[2], r[3]) for r in rows}


def insert_rows(engine, schema: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    df = pd.DataFrame(rows)
    df.to_sql(
        "brainrot_radio",
        engine,
        schema=schema,
        if_exists="append",
        index=False,
    )
    return len(df)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def sync(
    engine,
    schema: str,
    api_key: str,
    lookback_hours: int = 6,
    *,
    start_override: datetime | None = None,
    end_override: datetime | None = None,
) -> int:
    """Fetch recent spins, resolve metadata, dedup, and insert new rows."""
    end_dt = end_override or datetime.now(timezone.utc)
    start_dt = start_override or (end_dt - timedelta(hours=lookback_hours))
    start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S+0000")
    end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S+0000")

    logger.info("Fetching spins from %s to %s", start_iso, end_iso)
    spins = fetch_full_spins(api_key, start=start_iso, end=end_iso)
    if not spins:
        logger.info("No spins returned from Spinitron")
        return 0

    existing_ids = get_existing_spin_ids(engine, schema)
    logger.info("Found %d existing spin_ids in DB", len(existing_ids))

    existing_fps = get_existing_fingerprints(engine, schema)
    logger.info("Loaded %d fingerprints for secondary dedup", len(existing_fps))

    new_rows: list[dict] = []
    skipped_fp = 0
    for spin in spins:
        spin_id = spin.get("id")
        if spin_id in existing_ids:
            continue

        play_dt = _parse_dt(spin.get("start"))
        fp = (
            play_dt.isoformat() if play_dt else None,
            spin.get("artist"),
            spin.get("song"),
            None,  # dj_name resolved below only if needed
        )

        playlist_id = spin.get("playlist_id")
        playlist: dict = {}
        persona: dict = {}
        if playlist_id:
            try:
                playlist = fetch_playlist(api_key, playlist_id)
                persona_id = playlist.get("persona_id")
                if persona_id:
                    persona = fetch_persona(api_key, persona_id)
            except requests.RequestException as exc:
                logger.warning("Failed to fetch playlist/persona for spin %s: %s", spin_id, exc)

        dj_name = persona.get("name")
        fp = (fp[0], fp[1], fp[2], dj_name)
        if fp in existing_fps:
            skipped_fp += 1
            continue

        new_rows.append(map_spin_to_row(spin, playlist, persona))

    if skipped_fp:
        logger.info("Skipped %d spin(s) via fingerprint match (likely CSV-seeded)", skipped_fp)

    if not new_rows:
        logger.info("No new spins to insert (all %d already in DB)", len(spins))
        return 0

    inserted = insert_rows(engine, schema, new_rows)
    logger.info("Inserted %d new spins into %s.brainrot_radio", inserted, schema)
    return inserted


def get_latest_play_datetime(engine, schema: str) -> datetime | None:
    """Return the most recent play_datetime already in the DB."""
    query = text(
        f'SELECT MAX(play_datetime) FROM "{schema}".brainrot_radio'
    )
    with engine.connect() as conn:
        row = conn.execute(query).scalar()
    if row is None:
        return None
    if isinstance(row, str):
        try:
            return datetime.fromisoformat(row.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return row.replace(tzinfo=timezone.utc) if row.tzinfo is None else row


def backfill(engine, schema: str, api_key: str) -> int:
    """Walk day-by-day from the latest DB row to now, inserting missing spins."""
    latest = get_latest_play_datetime(engine, schema)
    now = datetime.now(timezone.utc)

    if latest is None:
        logger.error("No rows in the table — seed with create_postgres_table.py first")
        sys.exit(1)

    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)

    gap = now - latest
    logger.info(
        "Latest spin in DB: %s  (%.1f days ago)",
        latest.isoformat(),
        gap.total_seconds() / 86400,
    )

    if gap < timedelta(hours=1):
        logger.info("Already up-to-date, nothing to backfill")
        return 0

    total_inserted = 0
    chunk_start = latest
    while chunk_start < now:
        chunk_end = min(chunk_start + timedelta(days=1), now)
        inserted = sync(
            engine,
            schema,
            api_key,
            start_override=chunk_start,
            end_override=chunk_end,
        )
        total_inserted += inserted
        logger.info(
            "Backfill chunk %s → %s: %d inserted (running total: %d)",
            chunk_start.strftime("%Y-%m-%d %H:%M"),
            chunk_end.strftime("%Y-%m-%d %H:%M"),
            inserted,
            total_inserted,
        )
        chunk_start = chunk_end

    return total_inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Spinitron spins to Postgres")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Fill the gap from the latest DB row to now (day-by-day)",
    )
    args = parser.parse_args()

    load_dotenv(find_dotenv())

    api_key = os.getenv("SPINITRON_API_KEY")
    if not api_key:
        logger.error("Missing SPINITRON_API_KEY")
        sys.exit(1)

    engine = build_engine()
    schema = os.environ.get("POSTGRES_SCHEMA", "public")

    if args.backfill:
        inserted = backfill(engine, schema, api_key)
        logger.info("Backfill complete. %d total rows inserted.", inserted)
    else:
        lookback = int(os.getenv("SYNC_LOOKBACK_HOURS", "6"))
        inserted = sync(engine, schema, api_key, lookback_hours=lookback)
        logger.info("Done. %d rows inserted.", inserted)


if __name__ == "__main__":
    main()
