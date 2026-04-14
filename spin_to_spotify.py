"""
Fetch recent spins from Spinitron, resolve tracks on Spotify, append to a playlist.
"""
from __future__ import annotations

import logging
import os
import sys
import time as _time
from datetime import datetime as dt, time, timedelta

import pandas as pd
import pytz
import requests
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


def generate_show_times(start_time: str = "00:30:00", interval: int = 90, count: int = 16) -> list[dict]:
    show_times = []
    time_format = "%H:%M:%S"
    current_time = dt.strptime(start_time, time_format)
    for _ in range(count):
        next_time = current_time + timedelta(minutes=interval)
        show_times.append(
            {
                "start": f"T{current_time.strftime(time_format)}",
                "end": f"T{next_time.strftime(time_format)}",
            }
        )
        current_time = next_time
    return show_times


def _slot_time_bounds(slot: dict) -> tuple[time, time]:
    start = slot["start"]
    end = slot["end"]
    return (
        time(int(start[1:3]), int(start[4:6])),
        time(int(end[1:3]), int(end[4:6])),
    )


def find_active_show_index(show_times: list[dict], eastern_now_time: time) -> int | None:
    for i, slot in enumerate(show_times):
        start_time, end_time = _slot_time_bounds(slot)
        if start_time <= end_time:
            is_active = start_time <= eastern_now_time < end_time
        else:
            is_active = eastern_now_time >= start_time or eastern_now_time < end_time
        if is_active:
            return i
    return None


def prior_show_window_datetimes(
    show_times: list[dict],
    active_index: int,
    eastern_today_str: str,
    eastern_yesterday_str: str,
) -> tuple[dt, dt]:
    n = len(show_times)
    prior_index = (active_index - 1) % n
    prior = show_times[prior_index]
    start, end = prior["start"], prior["end"]
    start_time, end_time = _slot_time_bounds(prior)
    if start_time <= end_time:
        start_date = dt.strptime(eastern_today_str + start, "%Y-%m-%dT%H:%M:%S")
        end_date = dt.strptime(eastern_today_str + end, "%Y-%m-%dT%H:%M:%S")
    else:
        start_date = dt.strptime(eastern_yesterday_str + start, "%Y-%m-%dT%H:%M:%S")
        end_date = dt.strptime(eastern_today_str + end, "%Y-%m-%dT%H:%M:%S")
    return start_date, end_date


def fetch_spinitron_spins(api_key: str, max_pages: int, delay_sec: float) -> list[dict]:
    spins: list[dict] = []
    page = 1
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            while page <= max_pages:
                url = f"https://spinitron.com/api/spins?access-token={api_key}&page={page}"
                r = requests.get(url, timeout=60)
                r.raise_for_status()
                payload = r.json()
                items = payload.get("items") or []
                if not items:
                    logger.info("Spinitron page %d empty; stopping pagination", page)
                    break
                for spin in items:
                    spins.append(
                        {
                            "Title": spin["song"],
                            "Album": spin["release"],
                            "Artist": spin["artist"],
                            "Time_Played": spin["start"][:19],
                        }
                    )
                logger.info("Fetched Spinitron page %d (%d spins on page)", page, len(items))
                page += 1
                if page <= max_pages and delay_sec > 0:
                    _time.sleep(delay_sec)
            return spins
        except (requests.RequestException, KeyError, ValueError) as e:
            last_error = e
            logger.warning("Spinitron fetch error on attempt %s: %s", attempt + 1, e)
            if attempt == 0:
                _time.sleep(30)
                page = 1
                spins = []

    raise RuntimeError(f"Failed to fetch Spinitron spins after retries: {last_error}") from last_error


def main() -> None:
    load_dotenv(find_dotenv())

    api_key = os.getenv("SPINITRON_API_KEY")
    playlist_id = os.getenv("SPOTIFY_PLAYLIST_ID")
    max_pages = int(os.getenv("SPINITRON_MAX_PAGES", "10"))
    delay_sec = float(os.getenv("SPINITRON_PAGE_DELAY_SEC", "10"))

    if not api_key:
        logger.error("Missing SPINITRON_API_KEY")
        sys.exit(1)
    if not playlist_id:
        logger.error("Missing SPOTIFY_PLAYLIST_ID")
        sys.exit(1)

    show_times = generate_show_times()
    spins = fetch_spinitron_spins(api_key, max_pages=max_pages, delay_sec=delay_sec)
    if not spins:
        logger.info("No spins returned from Spinitron — nothing to do")
        return

    spins_df = pd.DataFrame(spins)
    eastern_tz = pytz.timezone("America/New_York")
    eastern_now = dt.now(pytz.utc).astimezone(eastern_tz)
    eastern_now_time = eastern_now.time()
    eastern_today_str = eastern_now.strftime("%Y-%m-%d")
    eastern_yesterday_str = (eastern_now - timedelta(days=1)).strftime("%Y-%m-%d")

    active_idx = find_active_show_index(show_times, eastern_now_time)
    if active_idx is None:
        logger.info("Could not determine active show slot for time %s — nothing to do", eastern_now_time)
        return

    start_date, end_date = prior_show_window_datetimes(
        show_times, active_idx, eastern_today_str, eastern_yesterday_str
    )
    logger.info("Prior show window: %s .. %s (active slot index %s)", start_date, end_date, active_idx)

    spins_df["Time_Played_Dt"] = pd.to_datetime(spins_df["Time_Played"])
    mask = (spins_df["Time_Played_Dt"] > start_date) & (spins_df["Time_Played_Dt"] < end_date)
    last_show_spins = spins_df.loc[mask].sort_values("Time_Played_Dt")

    if last_show_spins.empty:
        logger.info("No spins during last show block — nothing to do")
        return

    sp = get_spotify_client_from_env()
    # #region agent log
    import json as _json, time as _dbg_time
    _log_path = r"c:\Users\Miles\Documents\GitHub\brainrot_radio\debug-2e0268.log"
    _token_info = sp.auth_manager.get_cached_token() if hasattr(sp, 'auth_manager') else None
    _me = sp.current_user() or {}
    with open(_log_path, "a") as _f:
        _f.write(_json.dumps({"sessionId":"2e0268","hypothesisId":"H1","location":"spin_to_spotify.py:175","message":"token_scope","data":{"scope":(_token_info or {}).get("scope"),"expires_at":(_token_info or {}).get("expires_at")},"timestamp":int(_dbg_time.time()*1000)})+"\n")
        _f.write(_json.dumps({"sessionId":"2e0268","hypothesisId":"H2","location":"spin_to_spotify.py:176","message":"current_user_vs_playlist","data":{"user_id":_me.get("id"),"user_name":_me.get("display_name"),"playlist_id":playlist_id},"timestamp":int(_dbg_time.time()*1000)})+"\n")
    try:
        _pl = sp.playlist(playlist_id, fields="owner.id,collaborative,public")
        with open(_log_path, "a") as _f:
            _f.write(_json.dumps({"sessionId":"2e0268","hypothesisId":"H2","location":"spin_to_spotify.py:180","message":"playlist_owner","data":{"owner_id":(_pl.get("owner") or {}).get("id"),"collaborative":_pl.get("collaborative"),"public":_pl.get("public"),"user_is_owner":_me.get("id")==(_pl.get("owner") or {}).get("id")},"timestamp":int(_dbg_time.time()*1000)})+"\n")
    except Exception as _e:
        with open(_log_path, "a") as _f:
            _f.write(_json.dumps({"sessionId":"2e0268","hypothesisId":"H2","location":"spin_to_spotify.py:183","message":"playlist_fetch_error","data":{"error":str(_e)},"timestamp":int(_dbg_time.time()*1000)})+"\n")
    # #endregion
    existing_ids = get_playlist_track_id_set(sp, playlist_id)

    text_cols = ["Title", "Album", "Artist"]
    apply_normalize_and_translate(spins_df, text_cols)

    new_track_ids: list[str] = []
    for row in last_show_spins.itertuples(index=False):
        title = row.Title
        artist = row.Artist
        if pd.isna(title) or not str(title).strip():
            continue
        tid = resolve_spotify_track_id(sp, title, artist, isrc=None)
        if tid and tid not in existing_ids:
            new_track_ids.append(tid)
            existing_ids.add(tid)

    if not new_track_ids:
        logger.info("No new tracks to add")
        return

    add_tracks_to_playlist_batched(sp, playlist_id, new_track_ids, dry_run=False)
    logger.info("Added %d tracks to playlist", len(new_track_ids))


if __name__ == "__main__":
    main()
