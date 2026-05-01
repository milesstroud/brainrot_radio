"""
One-time (or repeatable) deduplication of the brainrot_radio table.

Identifies rows that are identical across ALL 28 content columns (everything
except spin_id).  When duplicates exist the row with a non-NULL spin_id is
kept; ties are broken by ctid (earliest inserted wins).

Usage:
    python dedupe_postgres.py              # dry-run — show what would be deleted
    python dedupe_postgres.py --execute    # actually delete duplicates
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

CONTENT_COLUMNS = [
    "playlist_date",
    "playlist_time",
    "playlist_datetime",
    "playlist_title",
    "playlist_category",
    "playlist_duration",
    "dj_id",
    "dj_name",
    "play_date",
    "play_time",
    "play_datetime",
    "artist",
    "song",
    "release",
    "duration",
    "request",
    "is_new",
    "song_custom_field",
    "local",
    "genre",
    "medium",
    "released",
    "added",
    "catalog",
    "release_custom_field",
    "song_note",
    "label",
    "upc",
]

_PARTITION_COLS = ", ".join(CONTENT_COLUMNS)

_RANKED_CTE = """
WITH ranked AS (
    SELECT ctid,
           spin_id,
           artist,
           song,
           play_datetime,
           dj_name,
           ROW_NUMBER() OVER (
               PARTITION BY {partition}
               ORDER BY (spin_id IS NULL), ctid
           ) AS rn
    FROM "{schema}".brainrot_radio
)
""".strip()


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Deduplicate brainrot_radio table")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete duplicates (default is dry-run)",
    )
    args = parser.parse_args()

    engine = build_engine()
    schema = os.environ.get("POSTGRES_SCHEMA", "public")

    cte = _RANKED_CTE.format(partition=_PARTITION_COLS, schema=schema)

    # --- Dry-run: count and preview ---
    count_sql = text(f"{cte}\nSELECT COUNT(*) FROM ranked WHERE rn > 1")
    with engine.connect() as conn:
        dup_count = conn.execute(count_sql).scalar()

    print(f"Found {dup_count} duplicate row(s) to remove.")

    if dup_count == 0:
        print("Nothing to do.")
        return

    preview_sql = text(
        f"{cte}\n"
        f"SELECT spin_id, artist, song, play_datetime, dj_name, rn "
        f"FROM ranked WHERE rn > 1 "
        f"ORDER BY play_datetime LIMIT 20"
    )
    with engine.connect() as conn:
        sample = conn.execute(preview_sql).fetchall()
    print("\nSample of rows that will be DELETED (rn > 1 = duplicate):")
    print(f"  {'spin_id':>8}  {'artist':<30}  {'song':<30}  {'play_datetime':<26}  {'dj_name':<20}")
    print(f"  {'--------':>8}  {'-----':<30}  {'----':<30}  {'--------------':<26}  {'-------':<20}")
    for row in sample:
        sid = str(row[0]) if row[0] is not None else "NULL"
        print(f"  {sid:>8}  {str(row[1]):<30.30}  {str(row[2]):<30.30}  {str(row[3]):<26}  {str(row[4]):<20}")

    if not args.execute:
        print(f"\nDry-run complete. Re-run with --execute to delete {dup_count} row(s).")
        return

    # --- Execute: delete duplicates ---
    delete_sql = text(
        f"{cte}\n"
        f'DELETE FROM "{schema}".brainrot_radio '
        f"WHERE ctid IN (SELECT ctid FROM ranked WHERE rn > 1)"
    )
    with engine.begin() as conn:
        result = conn.execute(delete_sql)
        deleted = result.rowcount

    print(f"\nDeleted {deleted} duplicate row(s).")


if __name__ == "__main__":
    main()
