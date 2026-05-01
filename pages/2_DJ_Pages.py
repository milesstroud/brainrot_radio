"""The Rot Report -- DJ Pages."""
from __future__ import annotations

import html as html_mod
import random

import pandas as pd
import streamlit as st

from shared import (
    NEON_GREEN, PURPLE,
    DARK_GRAY, WHITE,
    inject_css, render_page_header, load_data,
    get_spotify_metadata, get_spotify_url_for_artist,
    dj_page_url, dj_link_html,
    render_sidebar_settings, get_user_timezone,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="The Rot Report — DJ Pages", page_icon="📻", layout="wide")
inject_css()

st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" />',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    /* ---- profile header ---- */
    .dj-header {{
        display: flex;
        align-items: center;
        gap: 28px;
        flex-wrap: wrap;
    }}
    .dj-header .dj-name {{
        font-size: 2.4rem;
        font-weight: 800;
        color: {NEON_GREEN};
        margin: 0;
        line-height: 1.1;
    }}
    .dj-stat-row {{
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        margin-top: 8px;
    }}
    .dj-stat {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 8px;
        padding: 12px 18px;
        min-width: 120px;
        text-align: center;
    }}
    .dj-stat .stat-val {{
        font-size: 1.5rem;
        font-weight: bold;
        color: {NEON_GREEN};
    }}
    .dj-stat .stat-label {{
        font-size: 0.75rem;
        color: #999;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 2px;
    }}

    /* ---- signature artist ---- */
    .sig-artist {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 10px;
        padding: 16px;
        display: flex;
        align-items: center;
        gap: 16px;
    }}
    .sig-artist img {{
        width: 80px;
        height: 80px;
        border-radius: 8px;
        object-fit: cover;
        flex-shrink: 0;
    }}
    .sig-artist .sig-info {{
        flex: 1;
        min-width: 0;
    }}
    .sig-artist .sig-label {{
        font-size: 0.7rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .sig-artist .sig-name {{
        font-size: 1.15rem;
        font-weight: bold;
        color: {WHITE};
    }}
    .sig-artist .sig-name a {{
        color: {WHITE};
        text-decoration: none;
    }}
    .sig-artist .sig-name a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}
    .sig-artist .sig-stat {{
        font-size: 0.8rem;
        color: #aaa;
        margin-top: 2px;
    }}

    /* ---- only found here ---- */
    .ofh-box {{
        margin-top: 12px;
    }}
    .ofh-label {{
        font-size: 0.7rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 6px;
    }}
    .ofh-row {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }}
    .ofh-card {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 8px;
        padding: 8px;
        text-align: center;
        width: 100px;
    }}
    .ofh-card img {{
        width: 80px;
        height: 80px;
        border-radius: 6px;
        object-fit: cover;
    }}
    .ofh-card .ofh-name {{
        font-size: 0.7rem;
        color: {WHITE};
        margin-top: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .ofh-card .ofh-name a {{
        color: {WHITE};
        text-decoration: none;
    }}
    .ofh-card .ofh-name a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}
    .ofh-card .ofh-plays {{
        font-size: 0.65rem;
        color: #888;
    }}

    /* ---- fingerprint slider cards ---- */
    .fp-card {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }}
    .fp-card .fp-icon {{
        font-size: 1.4rem;
        color: {NEON_GREEN};
        margin-bottom: 8px;
    }}
    .fp-card .fp-labels {{
        display: flex;
        justify-content: space-between;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 6px;
    }}
    .fp-card .fp-labels .fp-lo {{ color: #888; }}
    .fp-card .fp-labels .fp-hi {{ color: #888; }}
    .fp-card .fp-labels .fp-active {{ color: {NEON_GREEN}; }}
    .fp-track {{
        position: relative;
        height: 8px;
        background: #333;
        border-radius: 4px;
        margin-bottom: 6px;
    }}
    .fp-track .fp-fill {{
        position: absolute;
        left: 0;
        top: 0;
        height: 100%;
        border-radius: 4px;
        background: linear-gradient(90deg, {PURPLE}, {NEON_GREEN});
    }}
    .fp-track .fp-dot {{
        position: absolute;
        top: 50%;
        width: 16px;
        height: 16px;
        background: {NEON_GREEN};
        border: 2px solid {DARK_GRAY};
        border-radius: 50%;
        transform: translate(-50%, -50%);
        box-shadow: 0 0 6px {NEON_GREEN};
    }}
    .fp-card .fp-stat {{
        font-size: 0.78rem;
        color: #999;
        text-align: center;
    }}

    /* best friend card */
    .bf-card {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        margin-bottom: 12px;
    }}
    .bf-card .bf-icon {{
        font-size: 1.6rem;
        color: {NEON_GREEN};
        margin-bottom: 6px;
    }}
    .bf-card .bf-title {{
        font-size: 0.72rem;
        color: {NEON_GREEN};
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 700;
    }}
    .bf-card .bf-name {{
        font-size: 1.1rem;
        font-weight: bold;
        color: {WHITE};
        margin: 4px 0;
    }}
    .bf-card .bf-name a {{
        color: {WHITE};
        text-decoration: none;
    }}
    .bf-card .bf-name a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}
    .bf-card .bf-overlap {{
        font-size: 0.85rem;
        color: #aaa;
    }}
    .bf-card .bf-mutuals {{
        font-size: 0.8rem;
        color: #888;
        margin-top: 6px;
    }}
    .bf-card .bf-mutuals a {{
        color: #bbb;
        text-decoration: none;
    }}
    .bf-card .bf-mutuals a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}

    /* ---- canon section ---- */
    .canon-hero {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 10px;
        overflow: hidden;
        margin-bottom: 12px;
    }}
    .canon-hero img {{
        width: 100%;
        aspect-ratio: 1 / 1;
        object-fit: cover;
        display: block;
    }}
    .canon-hero .ch-body {{
        padding: 14px 16px;
    }}
    .canon-hero .ch-rank {{
        display: inline-block;
        background: {NEON_GREEN};
        color: #000;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 3px 8px;
        border-radius: 4px;
        margin-bottom: 4px;
    }}
    .canon-hero .ch-exclusive {{
        display: inline-block;
        background: {PURPLE};
        color: {WHITE};
        font-size: 0.6rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 2px 7px;
        border-radius: 4px;
        margin-left: 6px;
    }}
    .canon-hero .ch-name {{
        font-size: 1.1rem;
        font-weight: bold;
        color: {WHITE};
        margin: 4px 0 2px 0;
    }}
    .canon-hero .ch-name a {{
        color: {WHITE};
        text-decoration: none;
    }}
    .canon-hero .ch-name a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}
    .canon-hero .ch-plays {{
        color: {NEON_GREEN};
        font-size: 0.85rem;
    }}

    .canon-runner {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 8px;
    }}
    .canon-runner .cr-rank {{
        color: #666;
        font-size: 0.8rem;
        margin-right: 6px;
    }}
    .canon-runner .cr-name {{
        font-weight: bold;
        color: {WHITE};
    }}
    .canon-runner .cr-name a {{
        color: {WHITE};
        text-decoration: none;
    }}
    .canon-runner .cr-name a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}
    .canon-runner .cr-exclusive {{
        display: inline-block;
        background: {PURPLE};
        color: {WHITE};
        font-size: 0.55rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 1px 5px;
        border-radius: 3px;
        margin-left: 6px;
        vertical-align: middle;
    }}
    .canon-runner .cr-stat {{
        float: right;
        color: #888;
        font-size: 0.82rem;
    }}

    /* release list */
    .release-row {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    .release-row .rr-name {{
        font-weight: bold;
        color: {WHITE};
        font-size: 0.9rem;
    }}
    .release-row .rr-name a {{
        color: {WHITE};
        text-decoration: none;
    }}
    .release-row .rr-name a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}
    .release-row .rr-stat {{
        color: #888;
        font-size: 0.8rem;
        white-space: nowrap;
        margin-left: 12px;
    }}

    /* dotted decade circle */
    .decade-circle-wrap {{
        text-align: center;
        padding: 10px 0;
    }}
    .decade-circle-wrap .dc-caption {{
        font-size: 0.85rem;
        color: #999;
        margin-bottom: 12px;
    }}
    .decade-circle {{
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        width: 160px;
        height: 160px;
        border: 3px dashed {NEON_GREEN};
        border-radius: 50%;
    }}
    .decade-circle .dc-val {{
        font-size: 2rem;
        font-weight: 800;
        color: {NEON_GREEN};
        line-height: 1.1;
    }}
    .decade-circle .dc-pct {{
        font-size: 1rem;
        color: #aaa;
        margin-top: 2px;
    }}

    /* ---- badges ---- */
    .badge-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 12px;
    }}
    .badge-card {{
        background: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 10px;
        padding: 14px;
        text-align: center;
        transition: opacity 0.2s;
    }}
    .badge-card.earned {{
        border-color: {NEON_GREEN}44;
    }}
    .badge-card.unearned {{
        opacity: 0.35;
    }}
    .badge-card i {{
        font-size: 1.8rem;
        display: block;
        margin-bottom: 8px;
    }}
    .badge-card.earned i {{
        color: {NEON_GREEN};
    }}
    .badge-card.unearned i {{
        color: #555;
    }}
    .badge-card .badge-title {{
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 4px;
    }}
    .badge-card.earned .badge-title {{
        color: {NEON_GREEN};
    }}
    .badge-card.unearned .badge-title {{
        color: #666;
    }}
    .badge-card .badge-sub {{
        font-size: 0.75rem;
        color: #888;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _esc(text: str) -> str:
    return html_mod.escape(str(text))


NUMBER_WORDS = {
    1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
    6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
    11: "Eleven", 12: "Twelve",
}

MIN_PLAYS = 5


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df_raw = load_data()
render_sidebar_settings()

render_page_header("DJ PAGES")

all_djs = sorted(df_raw["dj_name"].dropna().unique())

# ---------------------------------------------------------------------------
# DJ selection via query param or picker
# ---------------------------------------------------------------------------
if "_random_dj_target" in st.session_state:
    _target = st.session_state.pop("_random_dj_target")
    st.query_params["dj"] = _target
    if "dj_pick" in st.session_state:
        del st.session_state["dj_pick"]

qp = st.query_params
preselected = qp.get("dj", None)

if preselected and preselected in all_djs:
    default_idx = all_djs.index(preselected)
else:
    default_idx = 0

pick_col, rand_col = st.columns([3, 1])
with pick_col:
    selected_dj = st.selectbox("Select a DJ", all_djs, index=default_idx, key="dj_pick")
with rand_col:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🎲 Random DJ!"):
        others = [dj for dj in all_djs if dj != selected_dj]
        if others:
            st.session_state["_random_dj_target"] = random.choice(others)
            st.rerun()

if selected_dj != qp.get("dj", None):
    st.query_params["dj"] = selected_dj

dj_df = df_raw[df_raw["dj_name"] == selected_dj].copy()

if dj_df.empty:
    st.warning("No data for this DJ.")
    st.stop()

# ===================================================================
# SECTION 1 — Header / Profile Strip
# ===================================================================
st.markdown("---")

total_plays = len(dj_df)
dur_sum = dj_df["duration_min"].sum()
total_airtime_hrs = dur_sum / 60 if pd.notna(dur_sum) and dur_sum > 0 else 0
unique_artists = dj_df["artist"].nunique()

hdr_left, hdr_right = st.columns([3, 2])

with hdr_left:
    st.markdown(
        f'<div class="dj-header"><h1 class="dj-name">{_esc(selected_dj)}</h1></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="dj-stat-row">'
        f'<div class="dj-stat"><div class="stat-val">{total_plays:,}</div><div class="stat-label">Total Plays</div></div>'
        f'<div class="dj-stat"><div class="stat-val">{total_airtime_hrs:,.1f}h</div><div class="stat-label">Total Airtime</div></div>'
        f'<div class="dj-stat"><div class="stat-val">{unique_artists:,}</div><div class="stat-label">Unique Artists</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# Signature Artist
with hdr_right:
    station_artist_counts = df_raw["artist"].value_counts()
    station_total = len(df_raw)
    dj_artist_counts = dj_df["artist"].value_counts()

    volume_floor = max(3, int(total_plays * 0.01))

    qualified = dj_artist_counts[dj_artist_counts >= volume_floor]
    if qualified.empty:
        qualified = dj_artist_counts.head(1)

    best_artist = None
    best_oi = 0.0
    for artist_name, dj_count in qualified.items():
        dj_share = dj_count / total_plays
        station_share = station_artist_counts.get(artist_name, 1) / station_total
        oi = dj_share / station_share if station_share > 0 else 0
        if oi > best_oi:
            best_oi = oi
            best_artist = artist_name

    if best_artist is None and not dj_artist_counts.empty:
        best_artist = dj_artist_counts.index[0]
        best_oi = 1.0

    if best_artist:
        sig_meta = get_spotify_metadata(best_artist)
        sig_img = sig_meta.get("artist_img") if sig_meta else None
        sig_url = sig_meta.get("artist_url") if sig_meta else None

        img_html = ""
        if sig_img:
            img_tag = f'<img src="{_esc(sig_img)}" alt="{_esc(best_artist)}" />'
            img_html = f'<a href="{_esc(sig_url)}" target="_blank">{img_tag}</a>' if sig_url else img_tag

        name_inner = _esc(best_artist)
        if sig_url:
            name_inner = f'<a href="{_esc(sig_url)}" target="_blank">{_esc(best_artist)}</a>'

        st.markdown(
            f'<div class="sig-artist">'
            f'{img_html}'
            f'<div class="sig-info">'
            f'<div class="sig-label">Signature Artist</div>'
            f'<div class="sig-name">{name_inner}</div>'
            f'<div class="sig-stat">{best_oi:.1f}x over-index &middot; '
            f'{int(dj_artist_counts.get(best_artist, 0)):,} plays</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    _station_artist_dj_n = df_raw.groupby("artist")["dj_name"].nunique()
    _exclusive_rows = [
        (name, int(cnt))
        for name, cnt in dj_artist_counts.items()
        if _station_artist_dj_n.get(name, 0) == 1
    ]
    _exclusive_rows.sort(key=lambda x: x[1], reverse=True)
    if _exclusive_rows:
        cards_parts: list[str] = []
        for _art_name, _nplays in _exclusive_rows[:3]:
            _meta = get_spotify_metadata(_art_name)
            _img = _meta.get("artist_img") if _meta else None
            _url = _meta.get("artist_url") if _meta else None
            _img_html = ""
            if _img:
                _img_tag = (
                    f'<img src="{_esc(_img)}" alt="{_esc(_art_name)}" />'
                )
                _img_html = (
                    f'<a href="{_esc(_url)}" target="_blank">{_img_tag}</a>'
                    if _url
                    else _img_tag
                )
            else:
                _img_html = (
                    f'<div style="width:80px;height:80px;margin:0 auto;'
                    f'background:#333;border-radius:6px;"></div>'
                )
            _name_inner = _esc(_art_name)
            if _url:
                _name_inner = (
                    f'<a href="{_esc(_url)}" target="_blank">'
                    f'{_esc(_art_name)}</a>'
                )
            cards_parts.append(
                f'<div class="ofh-card">{_img_html}'
                f'<div class="ofh-name">{_name_inner}</div>'
                f'<div class="ofh-plays">{_nplays:,} plays</div></div>'
            )
        st.markdown(
            '<div class="ofh-box">'
            '<div class="ofh-label">Only Found Here</div>'
            f'<div class="ofh-row">{"".join(cards_parts)}</div>'
            "</div>",
            unsafe_allow_html=True,
        )

# ===================================================================
# SECTION 2 — Fingerprint Cards
# ===================================================================
st.markdown("---")
st.markdown(f"### {_esc(selected_dj)}'s Fingerprint")

dj_groups = df_raw.groupby("dj_name", dropna=True)
qualified_djs = [name for name, grp in dj_groups if len(grp) >= MIN_PLAYS]

_FALSY_NEW = frozenset(("", "0", "false", "no", "nan", "none"))
artist_dj_counts = df_raw.groupby("artist")["dj_name"].nunique()

dj_metrics: dict[str, dict] = {}
per_dj_stats: dict[str, dict] = {}
for dj_n in qualified_djs:
    g = dj_groups.get_group(dj_n)
    plays = len(g)
    uniq_songs = g["song"].nunique()
    uniq_artists = g["artist"].nunique()
    med_year = g["release_year"].dropna().median()
    avg_dur = g["duration_min"].dropna().mean()
    dur_total = g["duration_min"].dropna().sum()
    n_decades = g["decade"].dropna().nunique()

    is_new_flags = g["is_new"].fillna("").astype(str).str.strip().str.lower()
    new_track_count = (~is_new_flags.isin(_FALSY_NEW)).sum()
    new_pct = new_track_count / plays * 100 if plays > 0 else 0

    per_artists = set(g["artist"].dropna().unique())
    excl_artists = sum(1 for a in per_artists if artist_dj_counts.get(a, 0) == 1)
    excl_share = excl_artists / len(per_artists) if per_artists else 0
    top_artist_plays = int(g["artist"].value_counts().iloc[0]) if uniq_artists > 0 else 0

    dj_metrics[dj_n] = {
        "med_year": med_year,
        "new_pct": new_pct,
        "repeat_rate": plays / uniq_songs if uniq_songs > 0 else 0,
        "avg_dur": avg_dur if pd.notna(avg_dur) else 0,
        "n_decades": n_decades,
    }
    per_dj_stats[dj_n] = {
        "repeat_rate": plays / uniq_songs if uniq_songs > 0 else 0,
        "avg_dur": avg_dur if pd.notna(avg_dur) else 0,
        "total_airtime": dur_total / 60 if pd.notna(dur_total) else 0,
        "artist_variety": uniq_artists / plays if plays > 0 else 0,
        "new_pct": new_pct,
        "excl_share": excl_share,
        "tracks_per_artist": uniq_songs / uniq_artists if uniq_artists > 0 else 0,
        "top_artist_plays": top_artist_plays,
        "plays": plays,
        "unique_songs": uniq_songs,
    }

# Cross-DJ artist rankings for Fan Club badges
_artist_dj_matrix = df_raw.groupby(["artist", "dj_name"]).size().reset_index(name="_plays")
artist_dj_rankings: dict[str, list[tuple[str, int]]] = {}
for _art, _grp in _artist_dj_matrix.groupby("artist"):
    _ranked = _grp.sort_values("_plays", ascending=False)
    artist_dj_rankings[_art] = list(zip(_ranked["dj_name"], _ranked["_plays"].astype(int)))


def _percentile_of(metric_key: str, dj_name: str, invert: bool = False) -> float:
    vals = [m[metric_key] for m in dj_metrics.values() if pd.notna(m[metric_key])]
    dj_val = dj_metrics.get(dj_name, {}).get(metric_key)
    if not vals or dj_val is None or pd.isna(dj_val):
        return 50.0
    below = sum(1 for v in vals if v < dj_val)
    equal = sum(1 for v in vals if v == dj_val)
    pctl = (below + 0.5 * equal) / len(vals) * 100
    return 100 - pctl if invert else pctl


def _render_fp_card(icon: str, lo_label: str, hi_label: str, pctl: float, stat_text: str) -> str:
    lo_cls = "fp-active" if pctl < 50 else "fp-lo"
    hi_cls = "fp-active" if pctl >= 50 else "fp-hi"
    pct = max(2, min(98, pctl))
    return (
        f'<div class="fp-card">'
        f'<div class="fp-icon"><i class="{icon}"></i></div>'
        f'<div class="fp-labels">'
        f'<span class="{lo_cls}">{_esc(lo_label)}</span>'
        f'<span class="{hi_cls}">{_esc(hi_label)}</span>'
        f'</div>'
        f'<div class="fp-track">'
        f'<div class="fp-fill" style="width:{pct:.0f}%"></div>'
        f'<div class="fp-dot" style="left:{pct:.0f}%"></div>'
        f'</div>'
        f'<div class="fp-stat">{stat_text}</div>'
        f'</div>'
    )


if selected_dj in dj_metrics:
    m = dj_metrics[selected_dj]

    old_soul_pctl = _percentile_of("med_year", selected_dj)
    crate_pctl = _percentile_of("new_pct", selected_dj)
    habit_pctl = _percentile_of("repeat_rate", selected_dj)
    slow_pctl = _percentile_of("avg_dur", selected_dj)
    hopper_pctl = _percentile_of("n_decades", selected_dj)

    fp_col1, fp_col2, fp_col3 = st.columns(3)

    with fp_col1:
        med_yr_str = f"{int(m['med_year'])}" if pd.notna(m["med_year"]) else "N/A"
        st.markdown(
            _render_fp_card(
                "fa-solid fa-compact-disc", "Old Soul", "New Age",
                old_soul_pctl, f"Median release year: {med_yr_str}",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            _render_fp_card(
                "fa-solid fa-repeat", "Variety Maxxer", "Creature of Habit",
                habit_pctl, f"Repeat rate: {m['repeat_rate']:.2f}x",
            ),
            unsafe_allow_html=True,
        )

    with fp_col2:
        st.markdown(
            _render_fp_card(
                "fa-solid fa-box-open", "Crate Digger", "Tapped In",
                crate_pctl, f"{m['new_pct']:.0f}% new tracks",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            _render_fp_card(
                "fa-solid fa-fire", "Quick Hitter", "Slow Burner",
                slow_pctl, f"Avg duration: {m['avg_dur']:.1f} min",
            ),
            unsafe_allow_html=True,
        )

    with fp_col3:
        st.markdown(
            _render_fp_card(
                "fa-solid fa-timeline", "Era Loyalist", "Decade Hopper",
                hopper_pctl, f"{int(m['n_decades'])} decades",
            ),
            unsafe_allow_html=True,
        )

        # Best Friend card
        dj_artist_set = set(dj_df["artist"].dropna().unique())
        best_friend = None
        best_jacc = 0.0
        for other_dj in qualified_djs:
            if other_dj == selected_dj:
                continue
            other_set = set(
                df_raw.loc[df_raw["dj_name"] == other_dj, "artist"].dropna().unique()
            )
            union = dj_artist_set | other_set
            if not union:
                continue
            jacc = len(dj_artist_set & other_set) / len(union)
            if jacc > best_jacc:
                best_jacc = jacc
                best_friend = other_dj

        if best_friend:
            overlap_pct = best_jacc * 100
            shared = dj_artist_set & set(
                df_raw.loc[df_raw["dj_name"] == best_friend, "artist"].dropna().unique()
            )
            shared_plays = (
                df_raw[
                    df_raw["artist"].isin(shared)
                    & df_raw["dj_name"].isin([selected_dj, best_friend])
                ]
                .groupby("artist").size()
                .sort_values(ascending=False)
            )
            top3 = shared_plays.head(3).index.tolist()

            mutual_links = []
            for a in top3:
                url = get_spotify_url_for_artist(a)
                if url:
                    mutual_links.append(f'<a href="{_esc(url)}" target="_blank">{_esc(a)}</a>')
                else:
                    mutual_links.append(_esc(a))
            mutual_str = ", ".join(mutual_links) if mutual_links else "—"

            bf_url = dj_page_url(best_friend)
            st.markdown(
                f'<div class="bf-card">'
                f'<div class="bf-icon"><i class="fa-solid fa-heart"></i></div>'
                f'<div class="bf-title">Best Friend</div>'
                f'<div class="bf-name"><a href="{_esc(bf_url)}" target="_self">{_esc(best_friend)}</a></div>'
                f'<div class="bf-overlap">{overlap_pct:.0f}% artist overlap</div>'
                f'<div class="bf-mutuals">Some mutual favs: {mutual_str}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="bf-card">'
                f'<div class="bf-icon"><i class="fa-solid fa-heart"></i></div>'
                f'<div class="bf-title">Best Friend</div>'
                f'<div class="bf-name">—</div>'
                f'<div class="bf-overlap">Not enough data</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ===================================================================
# SECTION 3 — Topline Canon
# ===================================================================
st.markdown("---")
st.markdown(f"### {_esc(selected_dj)}'s Favorites")

canon_left, canon_mid, canon_right = st.columns([2, 2, 1])

# -- Top 3 Artists --
top_artists = dj_df["artist"].value_counts().head(3)
with canon_left:
    st.markdown(f"**Top Artists** <span style='color:#888;font-size:0.8rem;'>plays</span>",
                unsafe_allow_html=True)
    for rank_idx, (artist_name, play_count) in enumerate(top_artists.items(), start=1):
        is_exclusive = artist_dj_counts.get(artist_name, 0) == 1
        pct_of_plays = play_count / total_plays * 100

        if rank_idx == 1:
            meta = get_spotify_metadata(artist_name)
            a_img = meta.get("artist_img") if meta else None
            a_url = meta.get("artist_url") if meta else None

            img_html = ""
            if a_img:
                img_t = f'<img src="{_esc(a_img)}" alt="{_esc(artist_name)}" />'
                img_html = f'<a href="{_esc(a_url)}" target="_blank">{img_t}</a>' if a_url else img_t

            name_inner = _esc(artist_name)
            if a_url:
                name_inner = f'<a href="{_esc(a_url)}" target="_blank">{_esc(artist_name)}</a>'

            excl_html = '<span class="ch-exclusive">Exclusive</span>' if is_exclusive else ""

            st.markdown(
                f'<div class="canon-hero">'
                f'{img_html}'
                f'<div class="ch-body">'
                f'<span class="ch-rank">#1 Artist</span>{excl_html}'
                f'<div class="ch-name">{name_inner}</div>'
                f'<div class="ch-plays">{play_count:,} plays &middot; {pct_of_plays:.1f}% of plays</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        else:
            a_url = get_spotify_url_for_artist(artist_name)
            name_inner = _esc(artist_name)
            if a_url:
                name_inner = f'<a href="{_esc(a_url)}" target="_blank">{_esc(artist_name)}</a>'
            excl_html = '<span class="cr-exclusive">Exclusive</span>' if is_exclusive else ""

            st.markdown(
                f'<div class="canon-runner">'
                f'<span class="cr-rank">#{rank_idx}</span>'
                f'<span class="cr-name">{name_inner}</span>'
                f'{excl_html}'
                f'<span class="cr-stat">{play_count:,} plays &middot; {pct_of_plays:.1f}%</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

# -- Top Releases --
with canon_mid:
    st.markdown(f"**Top Releases** <span style='color:#888;font-size:0.8rem;'>plays &middot; distinct tracks</span>",
                unsafe_allow_html=True)
    top_releases = dj_df["release"].dropna().value_counts().head(5)
    for release_name, rel_plays in top_releases.items():
        rel_rows = dj_df[dj_df["release"] == release_name]
        distinct_tracks = rel_rows["song"].nunique()
        top_artist_for_rel = rel_rows["artist"].mode()
        artist_str = str(top_artist_for_rel.iloc[0]) if not top_artist_for_rel.empty else ""

        rel_song = rel_rows["song"].dropna()
        song_for_lookup = str(rel_song.iloc[0]) if not rel_song.empty else None
        rel_url = None
        if artist_str and song_for_lookup:
            meta = get_spotify_metadata(artist_str, song_for_lookup)
            rel_url = meta.get("album_url") if meta else None

        display_text = f"{_esc(release_name)} — {_esc(artist_str)}" if artist_str else _esc(release_name)
        if rel_url:
            label_text = f'<a href="{_esc(rel_url)}" target="_blank">{display_text}</a>'
        else:
            label_text = display_text

        st.markdown(
            f'<div class="release-row">'
            f'<div class="rr-name">{label_text}</div>'
            f'<div class="rr-stat">{rel_plays:,} play{"s" if rel_plays != 1 else ""}, '
            f'{distinct_tracks} track{"s" if distinct_tracks != 1 else ""}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# -- Top Decade --
with canon_right:
    decade_counts = dj_df["decade"].dropna().value_counts()
    if not decade_counts.empty:
        top_decade = decade_counts.index[0]
        top_decade_plays = int(decade_counts.iloc[0])
        decade_total = int(decade_counts.sum())
        decade_pct = top_decade_plays / decade_total * 100 if decade_total > 0 else 0

        st.markdown(
            f'<div class="decade-circle-wrap">'
            f'<div class="dc-caption">{_esc(selected_dj)}\'s favorite decade of music is the&hellip;</div>'
            f'<div class="decade-circle">'
            f'<div class="dc-val">{_esc(str(top_decade))}</div>'
            f'<div class="dc-pct">{decade_pct:.0f}% of plays</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("No decade data available.")


# ===================================================================
# SECTION 4 — Badges
# ===================================================================
st.markdown("---")
st.markdown("### Badges")

# --- Station benchmarks (per_dj_stats computed above in merged loop) ---
all_stats_df = pd.DataFrame(per_dj_stats).T

station_repeat_rate = all_stats_df["repeat_rate"].mean()
station_avg_dur = all_stats_df["avg_dur"].mean()
station_variety = all_stats_df["artist_variety"].mean()
new_pct_p75 = all_stats_df["new_pct"].quantile(0.75)
station_excl_share = all_stats_df["excl_share"].mean()
station_tpa = all_stats_df["tracks_per_artist"].mean()
station_airtime_p90 = all_stats_df["total_airtime"].quantile(0.90)
repeat_rate_median = all_stats_df["repeat_rate"].median()
top_artist_p75 = all_stats_df["top_artist_plays"].quantile(0.75)

release_years = df_raw["release_year"].dropna()
year_p5 = release_years.quantile(0.05) if not release_years.empty else 1960

dj_s = per_dj_stats.get(selected_dj, {})

# --- Individual badge checks ---
badges: list[dict] = []


def _add(title: str, icon: str, earned: bool, sub: str = ""):
    badges.append({"title": title, "icon": icon, "earned": earned, "sub": sub})


# Brainrot DJ
_first_spin = dj_df["play_datetime"].min()
_first_spin_str = _first_spin.strftime("%B %-d, %Y") if pd.notna(_first_spin) else "Unknown"
_add("Brainrot DJ", "fa-solid fa-radio", True,
     f"Welcome to Brainrot!<br>First spin: {_first_spin_str}")

# The OG
_dj_first_spins = df_raw.groupby("dj_name")["play_datetime"].min()
_the_og_dj = _dj_first_spins.idxmin() if not _dj_first_spins.empty else None
_add("The OG", "fa-solid fa-trophy",
     selected_dj == _the_og_dj,
     "First DJ to spin a track on Brainrot")

# Brainrot OG
_og_top5 = set(_dj_first_spins.nsmallest(5).index) if not _dj_first_spins.empty else set()
_add("Brainrot OG", "fa-solid fa-medal",
     selected_dj in _og_top5,
     "Among the first 5 DJs on Brainrot")

# Low Repeat
dj_rr = dj_s.get("repeat_rate", 0)
_add(
    "Low Repeat", "fa-solid fa-arrows-spin",
    dj_rr <= station_repeat_rate * 1.1,
    f"{dj_rr:.2f}x repeat rate",
)

# No Repeats
plays_eq_songs = dj_s.get("plays", 0) == dj_s.get("unique_songs", -1)
_add("No Repeats", "fa-solid fa-fingerprint", plays_eq_songs, "Every track unique")

# Time Traveler
oldest_year = dj_df["release_year"].dropna().min()
time_traveler = pd.notna(oldest_year) and oldest_year < year_p5
oldest_str = str(int(oldest_year)) if pd.notna(oldest_year) else "N/A"
_add("Time Traveler", "fa-solid fa-clock-rotate-left", time_traveler, f"Oldest: {oldest_str}")

# Long Form
dj_avg_dur = dj_s.get("avg_dur", 0)
_add(
    "Long Form", "fa-solid fa-hourglass-half",
    dj_avg_dur > station_avg_dur * 1.15,
    f"Avg {dj_avg_dur:.1f} min",
)

# Short Form
_add(
    "Short Form", "fa-solid fa-forward",
    dj_avg_dur < station_avg_dur * 0.85,
    f"Avg {dj_avg_dur:.1f} min",
)

# Deep Bag
dj_variety = dj_s.get("artist_variety", 0)
_add(
    "Deep Bag", "fa-solid fa-bag-shopping",
    dj_variety > station_variety * 1.2,
    f"{dj_variety:.2f} artists/play",
)

# Finger on the Pulse
dj_new = dj_s.get("new_pct", 0)
_add(
    "Finger on the Pulse", "fa-solid fa-bolt",
    dj_new >= new_pct_p75,
    f"{dj_new:.0f}% new tracks",
)

# Locked In
dj_excl = dj_s.get("excl_share", 0)
_add(
    "Locked In", "fa-solid fa-lock",
    dj_excl > station_excl_share * 1.2,
    f"{dj_excl * 100:.0f}% exclusive artists",
)

# Discog Diver
dj_tpa = dj_s.get("tracks_per_artist", 0)
_add(
    "Discog Diver", "fa-solid fa-record-vinyl",
    dj_tpa > station_tpa * 1.3 and dj_rr < repeat_rate_median,
    f"{dj_tpa:.1f} tracks/artist",
)

# Fan Club President / Member (cross-DJ ranking per artist)
dj_top_a_plays = dj_s.get("top_artist_plays", 0)
fan_club_artist = dj_df["artist"].value_counts().index[0] if not dj_df["artist"].value_counts().empty else "?"
fan_club_rank = None
if fan_club_artist in artist_dj_rankings:
    for _fc_rank, (_fc_dj, _) in enumerate(artist_dj_rankings[fan_club_artist], 1):
        if _fc_dj == selected_dj:
            fan_club_rank = _fc_rank
            break
if fan_club_rank == 1:
    _add("Fan Club President", "fa-solid fa-crown", True,
         f"{_esc(fan_club_artist)}: {dj_top_a_plays} plays")
elif fan_club_rank is not None and fan_club_rank <= 3:
    _add("Fan Club Member", "fa-solid fa-id-card", True,
         f"{_esc(fan_club_artist)}: {dj_top_a_plays} plays")

# Keep It Locked
dj_airtime = dj_s.get("total_airtime", 0)
_add(
    "Keep It Locked", "fa-solid fa-tower-broadcast",
    dj_airtime >= station_airtime_p90,
    f"{dj_airtime:.1f}h airtime",
)

# Weekend Spinnin'
weekend_mask = pd.Series(False, index=dj_df.index)
if pd.api.types.is_datetime64_any_dtype(dj_df["play_datetime"]):
    dt_local = dj_df["play_datetime"].dt.tz_convert(get_user_timezone())
    is_weekend = dt_local.dt.dayofweek.isin([5, 6])
    after_9am = dt_local.dt.hour >= 9
    weekend_mask = is_weekend & after_9am
_add("Weekend Spinnin'", "fa-solid fa-sun", weekend_mask.any(), "Played a weekend set")

# N Decade Span
n_decades = int(dj_df["decade"].dropna().nunique())
decade_word = NUMBER_WORDS.get(n_decades, str(n_decades))
_add(
    f"{decade_word} Decade Span", "fa-solid fa-layer-group",
    n_decades >= 2,
    f"{n_decades} decades covered",
)

# A-Z
_AZ = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
song_initials = dj_df["song"].dropna().str.strip().str[0].str.upper()
letters_covered = {c for c in song_initials.unique() if c in _AZ}
all_26 = len(letters_covered) == 26
az_sub = "Tracks starting with every letter A-Z" if all_26 else f"{len(letters_covered)}/26 letters"
_add("A-Z", "fa-solid fa-font", all_26, az_sub)

# 10-Minute Club
has_10 = (dj_df["duration_min"].dropna() >= 10).any()
_add("10-Minute Club", "fa-solid fa-stopwatch", has_10, "Played a track over 10 minutes long")

# 20-Minute Club
has_20 = (dj_df["duration_min"].dropna() >= 20).any()
_add("20-Minute Club", "fa-solid fa-stopwatch", has_20, "Played a track over 20 minutes long")

# Sub-Minute
has_sub1 = (dj_df["duration_min"].dropna() < 1).any()
_add("Sub-Minute", "fa-solid fa-gauge-high", has_sub1, "Played a track under a minute long")

# --- Render badge grid ---
earned_badges = [b for b in badges if b["earned"]]

cards_html = ""
for b in earned_badges:
    cls = "earned"
    sub_html = f'<div class="badge-sub">{b["sub"]}</div>' if b["sub"] else ""
    cards_html += (
        f'<div class="badge-card {cls}">'
        f'<i class="{b["icon"]}"></i>'
        f'<div class="badge-title">{b["title"]}</div>'
        f'{sub_html}'
        f'</div>'
    )

st.markdown(f'<div class="badge-grid">{cards_html}</div>', unsafe_allow_html=True)
