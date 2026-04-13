"""The Rot Report -- Spinboard."""
from __future__ import annotations

import html as html_mod
import math
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from shared import (
    NEON_GREEN, PURPLE, WHITE, DARK_GRAY, PALETTE, PLOT_TEMPLATE,
    ITALIC_TICK, HBAR_HEIGHT_PER, DJ_PAGE_SIZE,
    inject_css, render_page_header, add_plays_label, load_data,
    get_spotify_metadata,
)

HOUR_LABELS = [
    "12 AM", "1 AM", "2 AM", "3 AM", "4 AM", "5 AM",
    "6 AM", "7 AM", "8 AM", "9 AM", "10 AM", "11 AM",
    "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM",
    "6 PM", "7 PM", "8 PM", "9 PM", "10 PM", "11 PM",
]

TZ_MAP = {"UTC": "UTC", "EST": "US/Eastern", "PST": "US/Pacific"}


def _esc(text: str) -> str:
    return html_mod.escape(str(text))


# ---------------------------------------------------------------------------
# Page config & custom CSS
# ---------------------------------------------------------------------------
st.set_page_config(page_title="The Rot Report — Spinboard", page_icon="📻", layout="wide")
inject_css()

st.markdown(
    f"""
    <style>
    .decade-card {{
        display: flex;
        align-items: center;
        gap: 14px;
        background-color: {DARK_GRAY};
        border: 1px solid #333;
        border-radius: 8px;
        padding: 12px 14px;
        margin-top: 8px;
    }}
    .decade-card img {{
        width: 64px;
        height: 64px;
        border-radius: 6px;
        object-fit: cover;
        flex-shrink: 0;
    }}
    .decade-card .dc-info {{
        flex: 1;
        min-width: 0;
    }}
    .decade-card .dc-label {{
        font-size: 0.7rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .decade-card .dc-title {{
        font-size: 0.95rem;
        font-weight: bold;
        color: {WHITE};
    }}
    .decade-card .dc-title a {{
        color: {WHITE};
        text-decoration: none;
    }}
    .decade-card .dc-title a:hover {{
        color: {NEON_GREEN};
        text-decoration: underline;
    }}
    .decade-card .dc-sub {{
        font-size: 0.8rem;
        color: #aaa;
    }}
    .clock-callout {{
        padding: 10px 0 0 0;
    }}
    .clock-callout .clock-label {{
        font-size: 0.75rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .clock-callout .clock-value {{
        font-size: 1.8rem;
        font-weight: bold;
        color: {WHITE};
        line-height: 1.2;
    }}
    .clock-callout .clock-sub {{
        font-size: 0.8rem;
        color: #888;
        margin-top: 2px;
    }}
    .clock-callout .clock-plays {{
        font-size: 1.4rem;
        font-weight: bold;
        color: {NEON_GREEN};
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
df_raw = load_data()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.markdown("## 📻 Filters")

all_djs = sorted(df_raw["dj_name"].dropna().unique())
sel_djs = st.sidebar.multiselect("DJ", all_djs, default=[])

date_min = df_raw["play_date_parsed"].min()
date_max = df_raw["play_date_parsed"].max()
if pd.notna(date_min) and pd.notna(date_max):
    sel_dates = st.sidebar.date_input(
        "Date range",
        value=(date_min.date(), date_max.date()),
        min_value=date_min.date(),
        max_value=date_max.date(),
    )
else:
    sel_dates = None

all_shows = sorted(df_raw["playlist_title"].dropna().unique())
sel_shows = st.sidebar.multiselect("Show", all_shows, default=[])

all_decades = sorted(df_raw["decade"].dropna().unique())
sel_decades = st.sidebar.multiselect("Release decade", all_decades, default=[])

all_labels = sorted(df_raw["label"].dropna().unique())
sel_labels = st.sidebar.multiselect("Label", all_labels, default=[])

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
all_dows = [d for d in DOW_ORDER if d in df_raw["play_dow"].dropna().unique()]
sel_dows = st.sidebar.multiselect("Day of week", all_dows, default=[])

# Apply filters
df = df_raw.copy()
if sel_djs:
    df = df[df["dj_name"].isin(sel_djs)]
if sel_dates and len(sel_dates) == 2:
    d_start, d_end = pd.Timestamp(sel_dates[0]), pd.Timestamp(sel_dates[1])
    mask = df["play_date_parsed"].between(d_start, d_end)
    df = df[mask | df["play_date_parsed"].isna()]
if sel_shows:
    df = df[df["playlist_title"].isin(sel_shows)]
if sel_decades:
    df = df[df["decade"].isin(sel_decades)]
if sel_labels:
    df = df[df["label"].isin(sel_labels)]
if sel_dows:
    df = df[df["play_dow"].isin(sel_dows)]

multi_dj = len(sel_djs) >= 2

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
render_page_header("SPINBOARD")
st.caption(f"Showing **{len(df):,}** plays after filters")

# ---------------------------------------------------------------------------
# Section 1 — Key metrics
# ---------------------------------------------------------------------------
st.markdown("---")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Plays", f"{len(df):,}")
c2.metric("Unique Artists", f"{df['artist'].nunique():,}")
c3.metric("Unique Songs", f"{df['song'].nunique():,}")
total_min = df["duration_min"].sum()
if pd.notna(total_min) and total_min > 0:
    hours = total_min / 60
    c4.metric("Total Hours Played", f"{hours:,.1f}")
else:
    c4.metric("Total Hours Played", "N/A")

# ---------------------------------------------------------------------------
# Section 2 — Top artists
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Top Artists")
top_n_artists = st.slider("Number of artists", 5, 50, 25, key="top_n_artists")
artist_modes = ["Overall", "By DJ"]
if multi_dj:
    artist_modes.append("Compare DJs")
artist_mode = st.radio("View", artist_modes, horizontal=True, key="artist_mode")

if artist_mode == "Overall":
    artist_counts = add_plays_label(
        df.groupby("artist", dropna=True)
        .size()
        .reset_index(name="plays")
        .nlargest(top_n_artists, "plays")
        .sort_values("plays")
    )
    fig = px.bar(
        artist_counts, x="plays", y="artist", orientation="h",
        text="plays_label",
        color_discrete_sequence=[NEON_GREEN], template=PLOT_TEMPLATE,
    )
    fig.update_traces(textposition="outside", textfont_size=11)
    fig.update_layout(
        yaxis_title=None, xaxis_title="Play count",
        yaxis=dict(automargin=True, tickfont=ITALIC_TICK),
        height=max(400, top_n_artists * HBAR_HEIGHT_PER),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
elif artist_mode == "By DJ":
    sel_dj_artist = st.selectbox("Select DJ", sorted(df["dj_name"].dropna().unique()), key="dj_art")
    dj_df = df[df["dj_name"] == sel_dj_artist]
    artist_counts = add_plays_label(
        dj_df.groupby("artist", dropna=True)
        .size()
        .reset_index(name="plays")
        .nlargest(top_n_artists, "plays")
        .sort_values("plays")
    )
    fig = px.bar(
        artist_counts, x="plays", y="artist", orientation="h",
        text="plays_label",
        color_discrete_sequence=[PURPLE], template=PLOT_TEMPLATE,
        title=f"Top artists — {sel_dj_artist}",
    )
    fig.update_traces(textposition="outside", textfont_size=11)
    fig.update_layout(
        yaxis_title=None, xaxis_title="Play count",
        yaxis=dict(automargin=True, tickfont=ITALIC_TICK),
        height=max(400, top_n_artists * HBAR_HEIGHT_PER),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    top_artists_overall = (
        df.groupby("artist", dropna=True).size()
        .nlargest(top_n_artists).index
    )
    cmp_df = add_plays_label(
        df[df["artist"].isin(top_artists_overall)]
        .groupby(["artist", "dj_name"], dropna=True)
        .size()
        .reset_index(name="plays")
    )
    artist_order = (
        cmp_df.groupby("artist")["plays"].sum()
        .sort_values().index.tolist()
    )
    fig = px.bar(
        cmp_df, x="plays", y="artist", orientation="h",
        text="plays_label",
        color="dj_name", barmode="stack",
        color_discrete_sequence=PALETTE, template=PLOT_TEMPLATE,
        category_orders={"artist": artist_order},
    )
    fig.update_traces(textposition="inside", textfont_size=10)
    fig.update_layout(
        yaxis_title=None, xaxis_title="Play count",
        legend_title_text="DJ",
        yaxis=dict(automargin=True, tickfont=ITALIC_TICK),
        height=max(400, top_n_artists * HBAR_HEIGHT_PER),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Section 3 — Top songs
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Top Songs")
top_n_songs = st.slider("Number of songs", 5, 50, 25, key="top_n_songs")

songs_ctrl_cols = st.columns([2, 1])
with songs_ctrl_cols[0]:
    song_decade_filter = st.multiselect(
        "Filter by release decade", all_decades, default=[], key="song_decade"
    )
with songs_ctrl_cols[1]:
    songs_compare_dj = multi_dj and st.checkbox("Compare DJs", key="songs_cmp")

songs_df = df.copy()
if song_decade_filter:
    songs_df = songs_df[songs_df["decade"].isin(song_decade_filter)]

songs_df["song_label"] = songs_df["artist"].fillna("") + " — " + songs_df["song"].fillna("")

if songs_compare_dj:
    top_song_labels = (
        songs_df.groupby("song_label", dropna=True).size()
        .nlargest(top_n_songs).index
    )
    song_cmp = add_plays_label(
        songs_df[songs_df["song_label"].isin(top_song_labels)]
        .groupby(["song_label", "dj_name"], dropna=True)
        .size()
        .reset_index(name="plays")
    )
    song_order = (
        song_cmp.groupby("song_label")["plays"].sum()
        .sort_values().index.tolist()
    )
    fig = px.bar(
        song_cmp, x="plays", y="song_label", orientation="h",
        text="plays_label",
        color="dj_name", barmode="stack",
        color_discrete_sequence=PALETTE, template=PLOT_TEMPLATE,
        category_orders={"song_label": song_order},
    )
    fig.update_traces(textposition="inside", textfont_size=10)
    fig.update_layout(
        yaxis_title=None, xaxis_title="Play count",
        legend_title_text="DJ",
        yaxis=dict(automargin=True, tickfont=ITALIC_TICK),
        height=max(400, top_n_songs * HBAR_HEIGHT_PER),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
else:
    song_counts = add_plays_label(
        songs_df.groupby("song_label", dropna=True)
        .size()
        .reset_index(name="plays")
        .nlargest(top_n_songs, "plays")
        .sort_values("plays")
    )
    fig = px.bar(
        song_counts, x="plays", y="song_label", orientation="h",
        text="plays_label",
        color_discrete_sequence=[NEON_GREEN], template=PLOT_TEMPLATE,
    )
    fig.update_traces(textposition="outside", textfont_size=11)
    fig.update_layout(
        yaxis_title=None, xaxis_title="Play count",
        yaxis=dict(automargin=True, tickfont=ITALIC_TICK),
        height=max(400, top_n_songs * HBAR_HEIGHT_PER),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Section 4 — DJ leaderboard
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## DJ Leaderboard")
dj_plays = add_plays_label(
    df.groupby("dj_name", dropna=True)
    .size()
    .reset_index(name="plays")
    .sort_values("plays", ascending=False)
)
fig = px.bar(
    dj_plays, x="dj_name", y="plays",
    text="plays_label",
    color_discrete_sequence=[PURPLE], template=PLOT_TEMPLATE,
)
fig.update_traces(textposition="outside", textfont_size=11)
fig.update_layout(
    xaxis_title=None, yaxis_title="Play count",
    xaxis_tickangle=-45,
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig, use_container_width=True)

if "dj_show_count" not in st.session_state:
    st.session_state.dj_show_count = DJ_PAGE_SIZE

visible_djs = dj_plays["dj_name"].head(st.session_state.dj_show_count)
for dj in visible_djs:
    dj_sub = df[df["dj_name"] == dj]
    plays = len(dj_sub)
    artists = dj_sub["artist"].nunique()
    songs = dj_sub["song"].nunique()
    mins = dj_sub["duration_min"].sum()
    hrs_label = f"{mins / 60:.1f} hrs" if pd.notna(mins) and mins > 0 else "N/A"
    with st.expander(f"{dj} — {plays:,} plays"):
        ec1, ec2, ec3 = st.columns(3)
        ec1.metric("Unique Artists", f"{artists:,}")
        ec2.metric("Unique Songs", f"{songs:,}")
        ec3.metric("Total Hours", hrs_label)

if st.session_state.dj_show_count < len(dj_plays):
    if st.button("See more DJs"):
        st.session_state.dj_show_count += DJ_PAGE_SIZE
        st.rerun()

# ---------------------------------------------------------------------------
# Section 4b — DJ Similarity
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## DJ Similarity")

all_djs_in_data = sorted(df["dj_name"].dropna().unique())
if len(all_djs_in_data) < 2:
    st.info("Need at least 2 DJs in the current filter to compute similarity.")
else:
    sim_dj = st.selectbox("Select a DJ", all_djs_in_data, key="sim_dj")

    dj_artist_sets: dict[str, set[str]] = {}
    for dj_name in all_djs_in_data:
        dj_artist_sets[dj_name] = set(
            df.loc[df["dj_name"] == dj_name, "artist"].dropna().unique()
        )

    base_set = dj_artist_sets[sim_dj]
    sim_rows: list[dict] = []
    for other_dj, other_set in dj_artist_sets.items():
        if other_dj == sim_dj:
            continue
        union = base_set | other_set
        if not union:
            continue
        intersection = base_set & other_set
        jaccard = len(intersection) / len(union)
        sim_rows.append({
            "dj": other_dj,
            "similarity": round(jaccard * 100, 1),
            "shared": len(intersection),
        })

    if sim_rows:
        sim_df = (
            pd.DataFrame(sim_rows)
            .sort_values("similarity", ascending=False)
            .head(10)
        )
        sim_df = sim_df.reset_index(drop=True)

        n = len(sim_df)
        angles = [2 * math.pi * i / n for i in range(n)]

        sims = sim_df["similarity"].values
        max_sim = sims.max() if sims.max() > 0 else 1
        min_sim = sims.min()
        span = max_sim - min_sim if max_sim != min_sim else 1
        radii = [0.35 + 0.65 * (1 - (s - min_sim) / span) for s in sims]

        spoke_x = [r * math.cos(a) for r, a in zip(radii, angles)]
        spoke_y = [r * math.sin(a) for r, a in zip(radii, angles)]

        fig = go.Figure()

        for idx, row in sim_df.iterrows():
            sx, sy = spoke_x[idx], spoke_y[idx]
            width = 1 + row["similarity"] / 100 * 8
            opacity = 0.3 + row["similarity"] / 100 * 0.7
            fig.add_trace(go.Scatter(
                x=[0, sx], y=[0, sy], mode="lines",
                line=dict(width=width, color=f"rgba(155,48,255,{opacity})"),
                hoverinfo="skip", showlegend=False,
            ))

        fig.add_trace(go.Scatter(
            x=spoke_x, y=spoke_y, mode="markers+text",
            marker=dict(size=25, color=PURPLE, line=dict(width=1, color="#222")),
            text=[f"{r['dj']}" for _, r in sim_df.iterrows()],
            textposition="top center",
            textfont=dict(color=WHITE, size=11),
            customdata=[[r["dj"], r["similarity"], r["shared"]] for _, r in sim_df.iterrows()],
            hovertemplate="<b>%{customdata[0]}</b><br>Similarity: %{customdata[1]:.0f}%<br>Shared artists: %{customdata[2]}<extra></extra>",
            showlegend=False,
        ))

        fig.add_trace(go.Scatter(
            x=[0], y=[0], mode="markers+text",
            marker=dict(size=40, color=NEON_GREEN, line=dict(width=2, color="#222")),
            text=[sim_dj], textposition="bottom center",
            textfont=dict(color=NEON_GREEN, size=13, family="monospace"),
            hovertemplate=f"<b>{_esc(sim_dj)}</b><extra></extra>",
            showlegend=False,
        ))

        r_max = max(radii) if radii else 1
        pad = 0.35
        fig.update_layout(
            template=PLOT_TEMPLATE,
            xaxis=dict(visible=False, range=[-r_max - pad, r_max + pad]),
            yaxis=dict(visible=False, range=[-r_max - pad, r_max + pad], scaleanchor="x"),
            height=520,
            margin=dict(l=20, r=20, t=20, b=20),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

        spoke_djs = sim_df["dj"].tolist()
        selected_spoke = st.selectbox(
            "Shared favorites with",
            spoke_djs,
            index=0,
            key="sim_spoke_sel",
        )
        shared_artists = base_set & dj_artist_sets[selected_spoke]
        if shared_artists:
            shared_plays = (
                df[df["artist"].isin(shared_artists) &
                   df["dj_name"].isin([sim_dj, selected_spoke])]
                .groupby("artist").size()
                .sort_values(ascending=False)
                .head(5)
            )
            fav_cols = st.columns(min(5, len(shared_plays)))
            for i, (artist, plays) in enumerate(shared_plays.items()):
                with fav_cols[i]:
                    st.markdown(
                        f'<div style="background:{DARK_GRAY};border:1px solid #333;'
                        f'border-radius:8px;padding:12px;text-align:center;">'
                        f'<div style="font-size:0.95rem;font-weight:bold;'
                        f'color:{WHITE}">{_esc(artist)}</div>'
                        f'<div style="font-size:0.8rem;color:{NEON_GREEN}">'
                        f'{int(plays):,} plays</div></div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.info("No similarity data available for this DJ.")

# ---------------------------------------------------------------------------
# Section 5 — Temporal trends
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Temporal Trends")

temporal_ctrl = st.columns([2, 1])
with temporal_ctrl[0]:
    granularity = st.radio("Granularity", ["Day", "Week", "Month"], horizontal=True, key="gran")
with temporal_ctrl[1]:
    temporal_split_dj = multi_dj and st.checkbox("Split by DJ", key="temporal_split")

time_df = df.dropna(subset=["play_date_parsed"]).copy()

if granularity == "Day":
    time_df["period"] = time_df["play_date_parsed"].dt.date
elif granularity == "Week":
    time_df["period"] = time_df["play_date_parsed"].dt.to_period("W").apply(lambda p: p.start_time.date())
else:
    time_df["period"] = time_df["play_date_parsed"].dt.to_period("M").apply(lambda p: p.start_time.date())

if temporal_split_dj:
    plays_over_time = (
        time_df.groupby(["period", "dj_name"]).size()
        .reset_index(name="plays").sort_values("period")
    )
    fig = px.line(
        plays_over_time, x="period", y="plays", color="dj_name",
        line_shape="spline",
        color_discrete_sequence=PALETTE, template=PLOT_TEMPLATE,
        title=f"Plays per {granularity.lower()} by DJ",
    )
    fig.update_layout(
        xaxis_title=None, yaxis_title="Plays",
        legend_title_text="DJ",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
else:
    plays_over_time = time_df.groupby("period").size().reset_index(name="plays")
    plays_over_time = plays_over_time.sort_values("period")
    fig = px.line(
        plays_over_time, x="period", y="plays",
        line_shape="spline",
        color_discrete_sequence=[NEON_GREEN], template=PLOT_TEMPLATE,
        title=f"Plays per {granularity.lower()}",
    )
    fig.update_layout(
        xaxis_title=None, yaxis_title="Plays",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
st.plotly_chart(fig, use_container_width=True)

# Listening Clock
st.markdown("### Listening Clock")
clock_df = df.dropna(subset=["play_datetime"]).copy()
if not clock_df.empty and pd.api.types.is_datetime64_any_dtype(clock_df["play_datetime"]):
    tz_sel = st.radio("Timezone", list(TZ_MAP.keys()), horizontal=True, key="clock_tz")
    local_dt = clock_df["play_datetime"].dt.tz_convert(TZ_MAP[tz_sel])
    local_hour = local_dt.dt.hour

    hour_counts = local_hour.value_counts().reindex(range(24), fill_value=0).sort_index()
    counts = hour_counts.values.astype(float)
    theta_vals = [h * 15 for h in range(24)]

    busiest_hour = int(hour_counts.idxmax())
    busiest_plays = int(hour_counts.max())

    col_chart, col_stat = st.columns([3, 1])
    with col_chart:
        fig = go.Figure(go.Barpolar(
            r=counts,
            theta=theta_vals,
            width=[14] * 24,
            marker=dict(color=PURPLE, line=dict(width=0)),
            hovertemplate="%{customdata[0]}<br>%{r:.0f} plays<extra></extra>",
            customdata=[[HOUR_LABELS[h]] for h in range(24)],
        ))
        fig.update_layout(
            template=PLOT_TEMPLATE,
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                angularaxis=dict(
                    tickvals=[0, 90, 180, 270],
                    ticktext=["00", "06", "12", "18"],
                    direction="clockwise",
                    tickfont=dict(color="#888", size=11),
                    showline=False,
                    gridcolor="rgba(255,255,255,0.08)",
                ),
                radialaxis=dict(
                    showticklabels=False,
                    showline=False,
                    gridcolor="rgba(255,255,255,0.06)",
                ),
            ),
            height=380,
            margin=dict(l=40, r=40, t=20, b=20),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
    with col_stat:
        st.markdown(
            f'<div class="clock-callout">'
            f'<div class="clock-label">Busiest hour</div>'
            f'<div class="clock-value">{HOUR_LABELS[busiest_hour]}</div>'
            f'<div class="clock-sub">Plays in busiest hour</div>'
            f'<div class="clock-plays">{busiest_plays:,}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
else:
    st.info("No datetime data available for listening clock.")

# ---------------------------------------------------------------------------
# Section 6 — Music by Decade
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Music by Decade")
decade_compare_dj = multi_dj and st.checkbox("Compare DJs", key="decade_cmp")

decade_df_base = df.dropna(subset=["decade"])

if not decade_df_base.empty:
    if decade_compare_dj:
        decade_dj = add_plays_label(
            decade_df_base.groupby(["decade", "dj_name"])
            .size()
            .reset_index(name="plays")
            .sort_values("decade")
        )
        if not decade_dj.empty:
            dec_order = sorted(decade_dj["decade"].unique())
            fig = px.bar(
                decade_dj, x="plays", y="decade", orientation="h",
                text="plays_label", color="dj_name", barmode="group",
                color_discrete_sequence=PALETTE, template=PLOT_TEMPLATE,
                category_orders={"decade": dec_order},
            )
            fig.update_traces(textposition="outside", textfont_size=10)
            fig.update_layout(
                yaxis_title=None, xaxis_title="Play count",
                legend_title_text="DJ",
                yaxis=dict(automargin=True, tickfont=ITALIC_TICK),
                height=max(300, len(dec_order) * 40),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        dec_counts = add_plays_label(
            decade_df_base.groupby("decade")
            .size()
            .reset_index(name="plays")
            .sort_values("decade")
        )
        fig = px.bar(
            dec_counts, x="plays", y="decade", orientation="h",
            text="plays_label",
            color_discrete_sequence=[NEON_GREEN], template=PLOT_TEMPLATE,
        )
        fig.update_traces(textposition="outside", textfont_size=11)
        fig.update_layout(
            yaxis_title=None, xaxis_title="Play count",
            yaxis=dict(automargin=True, tickfont=ITALIC_TICK),
            height=max(300, len(dec_counts) * 36),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Decade drill-down
    decade_list = sorted(decade_df_base["decade"].dropna().unique())
    sel_decade = st.radio(
        "Select a decade", decade_list, horizontal=True, key="app_dec_sel",
    )

    dec_sub = decade_df_base[decade_df_base["decade"] == sel_decade]
    if not dec_sub.empty:
        dc1, dc2, dc3 = st.columns(3)

        # --- Top Artist ---
        top_artist_s = dec_sub["artist"].value_counts()
        with dc1:
            if not top_artist_s.empty:
                art_name = str(top_artist_s.index[0])
                art_plays = int(top_artist_s.iloc[0])
                art_meta = get_spotify_metadata(art_name)
                art_img = art_meta.get("artist_img") if art_meta else None
                art_url = art_meta.get("artist_url") if art_meta else None
                img_tag = ""
                if art_img:
                    img_el = f'<img src="{_esc(art_img)}" alt="{_esc(art_name)}" />'
                    img_tag = f'<a href="{_esc(art_url)}" target="_blank">{img_el}</a>' if art_url else img_el
                title_inner = _esc(art_name)
                if art_url:
                    title_inner = f'<a href="{_esc(art_url)}" target="_blank">{_esc(art_name)}</a>'
                st.markdown(
                    f'<div class="decade-card">'
                    f'{img_tag}'
                    f'<div class="dc-info">'
                    f'<div class="dc-label">Top Artist · {_esc(sel_decade)}</div>'
                    f'<div class="dc-title">{title_inner}</div>'
                    f'<div class="dc-sub">{art_plays:,} plays</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

        # --- Top Release ---
        top_release_s = dec_sub["release"].value_counts()
        with dc2:
            if not top_release_s.empty:
                rel_name = str(top_release_s.index[0])
                rel_plays = int(top_release_s.iloc[0])
                rel_rows = dec_sub[dec_sub["release"] == rel_name]
                rel_artist = rel_rows["artist"].mode()
                rel_artist_name = str(rel_artist.iloc[0]) if not rel_artist.empty else ""
                rel_song = rel_rows["song"].iloc[0] if not rel_rows["song"].dropna().empty else None
                rel_meta = get_spotify_metadata(rel_artist_name, str(rel_song)) if rel_artist_name and rel_song else None
                rel_img = rel_meta.get("album_img") if rel_meta else None
                rel_url = rel_meta.get("album_url") if rel_meta else None
                img_tag = ""
                if rel_img:
                    img_el = f'<img src="{_esc(rel_img)}" alt="{_esc(rel_name)}" />'
                    img_tag = f'<a href="{_esc(rel_url)}" target="_blank">{img_el}</a>' if rel_url else img_el
                title_inner = _esc(rel_name)
                if rel_url:
                    title_inner = f'<a href="{_esc(rel_url)}" target="_blank">{_esc(rel_name)}</a>'
                st.markdown(
                    f'<div class="decade-card">'
                    f'{img_tag}'
                    f'<div class="dc-info">'
                    f'<div class="dc-label">Top Release · {_esc(sel_decade)}</div>'
                    f'<div class="dc-title">{title_inner}</div>'
                    f'<div class="dc-sub">{_esc(rel_artist_name)} · {rel_plays:,} plays</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

        # --- Top Track ---
        dec_sub_tracks = dec_sub.copy()
        dec_sub_tracks["track_label"] = dec_sub_tracks["artist"].fillna("") + " — " + dec_sub_tracks["song"].fillna("")
        top_track_s = dec_sub_tracks["track_label"].value_counts()
        with dc3:
            if not top_track_s.empty:
                trk_label = str(top_track_s.index[0])
                trk_plays = int(top_track_s.iloc[0])
                trk_parts = trk_label.split(" — ", 1)
                trk_artist = trk_parts[0].strip() if len(trk_parts) == 2 else ""
                trk_song = trk_parts[1].strip() if len(trk_parts) == 2 else trk_label
                trk_meta = get_spotify_metadata(trk_artist, trk_song) if trk_artist else None
                trk_img = trk_meta.get("track_img") if trk_meta else None
                trk_url = trk_meta.get("track_url") if trk_meta else None
                img_tag = ""
                if trk_img:
                    img_el = f'<img src="{_esc(trk_img)}" alt="{_esc(trk_label)}" />'
                    img_tag = f'<a href="{_esc(trk_url)}" target="_blank">{img_el}</a>' if trk_url else img_el
                title_inner = _esc(trk_label)
                if trk_url:
                    title_inner = f'<a href="{_esc(trk_url)}" target="_blank">{_esc(trk_label)}</a>'
                st.markdown(
                    f'<div class="decade-card">'
                    f'{img_tag}'
                    f'<div class="dc-info">'
                    f'<div class="dc-label">Top Track · {_esc(sel_decade)}</div>'
                    f'<div class="dc-title">{title_inner}</div>'
                    f'<div class="dc-sub">{trk_plays:,} plays</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
else:
    st.info("No release year data available.")

# ---------------------------------------------------------------------------
# Section 7 — Top Labels
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Top Labels")
labels_compare_dj = multi_dj and st.checkbox("Compare DJs", key="labels_cmp")

if labels_compare_dj:
    top_labels = (
        df.groupby("label", dropna=True).size()
        .nlargest(20).index
    )
    label_dj = add_plays_label(
        df[df["label"].isin(top_labels)]
        .groupby(["label", "dj_name"], dropna=True)
        .size()
        .reset_index(name="plays")
    )
    label_order = (
        label_dj.groupby("label")["plays"].sum()
        .sort_values().index.tolist()
    )
    if not label_dj.empty:
        fig = px.bar(
            label_dj, x="plays", y="label", orientation="h",
            text="plays_label",
            color="dj_name", barmode="stack",
            color_discrete_sequence=PALETTE, template=PLOT_TEMPLATE,
            category_orders={"label": label_order},
            title="Top 20 Labels by DJ",
        )
        fig.update_traces(textposition="inside", textfont_size=10)
        fig.update_layout(
            yaxis_title=None, xaxis_title="Play count",
            legend_title_text="DJ",
            yaxis=dict(automargin=True, tickfont=ITALIC_TICK),
            height=max(400, 20 * HBAR_HEIGHT_PER),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No label data.")
else:
    label_counts = add_plays_label(
        df.groupby("label", dropna=True)
        .size()
        .reset_index(name="plays")
        .nlargest(20, "plays")
        .sort_values("plays")
    )
    if not label_counts.empty:
        fig = px.bar(
            label_counts, x="plays", y="label", orientation="h",
            text="plays_label",
            color_discrete_sequence=[PURPLE], template=PLOT_TEMPLATE,
            title="Top 20 Labels",
        )
        fig.update_traces(textposition="outside", textfont_size=11)
        fig.update_layout(
            yaxis_title=None, xaxis_title="Play count",
            yaxis=dict(automargin=True, tickfont=ITALIC_TICK),
            height=max(400, len(label_counts) * HBAR_HEIGHT_PER),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No label data.")

# ---------------------------------------------------------------------------
# Section 8 — Data explorer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Data Explorer")

search_term = st.text_input("Search (filters artist, song, release, label)", key="search")
explorer_df = df.copy()
if search_term:
    pattern = re.escape(search_term)
    mask = (
        explorer_df["artist"].astype(str).str.contains(pattern, case=False, na=False)
        | explorer_df["song"].astype(str).str.contains(pattern, case=False, na=False)
        | explorer_df["release"].astype(str).str.contains(pattern, case=False, na=False)
        | explorer_df["label"].astype(str).str.contains(pattern, case=False, na=False)
    )
    explorer_df = explorer_df[mask]

display_cols = [
    "play_datetime", "dj_name", "playlist_title", "artist", "song",
    "release", "label", "duration", "release_year", "decade",
]
display_cols = [c for c in display_cols if c in explorer_df.columns]

st.dataframe(explorer_df[display_cols], use_container_width=True, height=500)

csv = explorer_df[display_cols].to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", csv, "brainrot_radio_export.csv", "text/csv")
