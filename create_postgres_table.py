"""
Seed the brainrot_radio PostgreSQL table from a Spinitron CSV export.

Usage:
    python create_postgres_table.py path/to/brainrot_backfill.csv

The table is created with if_exists="replace", so existing data is overwritten.
After loading, a nullable spin_id column with a UNIQUE constraint is added for
use by sync_spins_to_postgres.py (backfill rows will have spin_id = NULL).
"""
import argparse
import os
import sys

import pandas as pd
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

EXPECTED_COLUMNS = [
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed brainrot_radio table from a Spinitron CSV export",
    )
    parser.add_argument("csv_path", help="Path to the backfill CSV file")
    args = parser.parse_args()

    load_dotenv(find_dotenv())

    if not os.path.isfile(args.csv_path):
        print(f"Error: file not found: {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(args.csv_path, encoding="utf-8-sig")
    df.columns = EXPECTED_COLUMNS

    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    if not user or not password:
        raise ValueError(
            "Set POSTGRES_USER and POSTGRES_PASSWORD (e.g. in a .env file)."
        )

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=user,
        password=password,
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "postgres"),
    )

    engine = create_engine(url)
    schema = os.environ.get("POSTGRES_SCHEMA", "public")

    df.to_sql(
        "brainrot_radio",
        engine,
        schema=schema,
        if_exists="replace",
        index=False,
    )
    print(f"Loaded {len(df):,} rows into {schema}.brainrot_radio")

    with engine.begin() as conn:
        conn.execute(text(
            f'ALTER TABLE "{schema}".brainrot_radio '
            f"ADD COLUMN IF NOT EXISTS spin_id INTEGER UNIQUE"
        ))
    print("Added spin_id column (nullable, unique)")


if __name__ == "__main__":
    main()
