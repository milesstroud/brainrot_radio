"""The Rot Report -- Genre Web."""
from __future__ import annotations

import html as html_mod

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shared import (
    NEON_GREEN, PURPLE, WHITE, DARK_GRAY, PLOT_TEMPLATE,
    inject_css, render_page_header, load_data,
    render_sidebar_settings, apply_user_tz,
    apply_genre_filter, genres_enabled,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="The Rot Report — Genre Web", page_icon="📻", layout="wide")
inject_css()


def _esc(text: str) -> str:
    return html_mod.escape(str(text))


# ---------------------------------------------------------------------------
# Load data & header
# ---------------------------------------------------------------------------
df_raw = load_data()
render_sidebar_settings(df_raw)
df_raw = apply_user_tz(df_raw)
df_raw = apply_genre_filter(df_raw)

render_page_header("GENRE WEB")

# ---------------------------------------------------------------------------
# Genre gate
# ---------------------------------------------------------------------------
if not genres_enabled() or "genre_family" not in df_raw.columns:
    st.info("Enable **Show genre information** in the sidebar settings to use this page.")
    st.stop()

gdf = df_raw[df_raw["genre_family"].notna() & (df_raw["genre_family"] != "Other")].copy()
if gdf.empty:
    st.warning("No genre data available yet. Run the genre backfill first.")
    st.stop()

# ---------------------------------------------------------------------------
# View selector
# ---------------------------------------------------------------------------
view = st.radio(
    "View",
    ["DJ \u2192 Genre Sankey", "Genre Heatmap"],
    horizontal=True,
    key="genre_web_view",
)


# ===========================================================================
# Shared data prep
# ===========================================================================
station_total = len(gdf)
station_genre_counts = gdf["genre_family"].value_counts()
station_genre_share = station_genre_counts / station_total

dj_genre = (
    gdf.groupby(["dj_name", "genre_family"])
    .size()
    .reset_index(name="plays")
)
dj_totals = gdf.groupby("dj_name").size().reset_index(name="dj_total")
dj_genre = dj_genre.merge(dj_totals, on="dj_name")
dj_genre["dj_share"] = dj_genre["plays"] / dj_genre["dj_total"]
dj_genre["station_share"] = dj_genre["genre_family"].map(station_genre_share)
dj_genre["over_index"] = dj_genre["dj_share"] / dj_genre["station_share"]


# ===========================================================================
# View 1: DJ -> Genre Sankey
# ===========================================================================
if view == "DJ \u2192 Genre Sankey":

    ctrl_l, ctrl_r = st.columns(2)
    with ctrl_l:
        min_oi = st.slider("Min genre affinity", 1.0, 8.0, 2.5, 0.25, key="sankey_oi")
    with ctrl_r:
        top_n = st.slider("Max connections per DJ", 1, 5, 2, 1, key="sankey_topn")
    min_plays = 10

    edges = dj_genre[(dj_genre["over_index"] >= min_oi) & (dj_genre["plays"] >= min_plays)].copy()

    if not edges.empty:
        edges = (
            edges.sort_values("over_index", ascending=False)
            .groupby("dj_name")
            .head(top_n)
            .reset_index(drop=True)
        )

    if edges.empty:
        st.info("No connections meet the threshold. Try lowering the minimum affinity.")
        st.stop()

    active_djs = sorted(edges["dj_name"].unique())
    active_genres = sorted(edges["genre_family"].unique())

    dj_idx = {name: i for i, name in enumerate(active_djs)}
    genre_idx = {name: len(active_djs) + i for i, name in enumerate(active_genres)}

    node_labels = list(active_djs) + list(active_genres)
    node_colors = [NEON_GREEN] * len(active_djs) + [PURPLE] * len(active_genres)

    sources, targets, values, link_colors, link_hovers = [], [], [], [], []
    for _, row in edges.iterrows():
        sources.append(dj_idx[row["dj_name"]])
        targets.append(genre_idx[row["genre_family"]])
        values.append(row["over_index"])
        link_colors.append("rgba(57, 255, 20, 0.25)")
        link_hovers.append(
            f"{row['dj_name']} → {row['genre_family']}<br>"
            f"{row['over_index']:.1f}x vs. station avg<br>"
            f"{row['dj_share']:.0%} of plays ({int(row['plays']):,})"
        )

    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20,
            thickness=20,
            label=node_labels,
            color=node_colors,
            line=dict(color="rgba(0,0,0,0.3)", width=0.5),
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            customdata=link_hovers,
            hovertemplate="%{customdata}<extra></extra>",
        ),
    )])

    fig.update_layout(
        template=PLOT_TEMPLATE,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11, color="#ccc"),
        margin=dict(l=10, r=10, t=20, b=20),
        height=max(500, len(active_djs) * 28),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        f'<div style="text-align:center;color:#888;font-size:0.8rem;margin-top:-10px;">'
        f'<span style="color:{NEON_GREEN};">DJs</span> on the left, '
        f'<span style="color:{PURPLE};">Genres</span> on the right. '
        f'Thicker ribbon = stronger genre lean. '
        f'Showing top {top_n} per DJ, &ge; {min_oi:.1f}x vs. avg with &ge; {min_plays} plays.'
        f'</div>',
        unsafe_allow_html=True,
    )

# ===========================================================================
# View 2: DJ x Genre Heatmap
# ===========================================================================
elif view == "Genre Heatmap":

    dj_order = (
        dj_totals.sort_values("dj_total", ascending=False)["dj_name"].tolist()
    )
    genre_order = [g for g in station_genre_counts.index if g in dj_genre["genre_family"].unique()]

    oi_pivot = dj_genre.pivot_table(
        index="dj_name", columns="genre_family", values="over_index", fill_value=0
    )
    dj_order = [d for d in dj_order if d in oi_pivot.index]
    genre_order = [g for g in genre_order if g in oi_pivot.columns]
    z = oi_pivot.loc[dj_order, genre_order].values

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=genre_order,
        y=dj_order,
        colorscale=[
            [0.0, DARK_GRAY],
            [0.25, "#333"],
            [0.5, PURPLE],
            [1.0, NEON_GREEN],
        ],
        zmin=0, zmax=4,
        hovertemplate="DJ: %{y}<br>Genre: %{x}<br>Affinity: %{z:.1f}x vs. avg<extra></extra>",
        colorbar=dict(
            title=dict(text="Genre<br>Affinity", font=dict(color="#aaa")),
            tickfont=dict(color="#aaa"),
        ),
    ))

    fig.update_layout(
        template=PLOT_TEMPLATE,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickangle=-45, tickfont=dict(size=10, color="#ccc"), side="bottom"),
        yaxis=dict(autorange="reversed", tickfont=dict(size=10, color="#ccc")),
        margin=dict(l=10, r=10, t=20, b=10),
        height=max(500, len(dj_order) * 24),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div style="text-align:center;color:#888;font-size:0.8rem;margin-top:-10px;">'
        'How much each DJ leans into each genre compared to the station average. '
        'Brighter = stronger lean (4x+ is max scale).'
        '</div>',
        unsafe_allow_html=True,
    )
