"""Presentation: the two dashboard views (state map and district examples)."""

from __future__ import annotations

import math
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BLUE = "#2166ac"
RED = "#b2182b"
WHITE = "#ffffff"
NOT_IN_USE_TAN = "#e6d6a2"
OUTLINE = "#8a8a8a"
VACANT_GREY = "#bdbdbd"
DIVERGING = [[0.0, RED], [0.5, WHITE], [1.0, BLUE]]

BALLOTPEDIA_TITLE = "Redistricting ahead of the 2026 elections"
BALLOTPEDIA_URL = "https://ballotpedia.org/Redistricting_ahead_of_the_2026_elections"
CENSUS_TITLE = "2025 Cartographic Boundary Files, States (1:5,000,000)"
CENSUS_URL = "https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html"
RDH_UTAH_TITLE = "Redistricting Data Hub - Utah"
RDH_FLORIDA_TITLE = "Redistricting Data Hub - Florida"
RDH_UTAH_URL = "https://redistrictingdatahub.org/state/utah/"
RDH_FLORIDA_URL = "https://redistrictingdatahub.org/state/florida/"
DOWNLOAD_LABEL = "Download filtered data"
DATE_LABEL = "Based on snapshots on"
INDEPENDENT_GREY = "#7a7f87"
HISTORIAN_TITLE = "Party Divisions of the House of Representatives, 1789 to Present"
HISTORIAN_URL = "https://history.house.gov/Institution/Party-Divisions/Party-Divisions/"
PRESS_GALLERY_TITLE = "Party breakdown"
PRESS_GALLERY_URL = "https://pressgallery.house.gov/member-data/party-breakdown"
HOUSE_TITLE = "In each of the last three Congresses, the House majority was 10 seats or fewer"
ADVANTAGE_TITLE = "Democratic seat advantage in the House by Congress: the margin has narrowed in each of the last three Congresses"
MAJORITY_LINE = 218
MAP_NOTE = "The maps need an internet connection to display (Plotly loads its base map online)."


def _latest(data: pd.DataFrame, column: str) -> str:
    return str(data[column].dropna().max())


def _int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series).astype("Int64")


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _signed(value: int) -> str:
    return f"+{value}" if value > 0 else ("−" + str(abs(value)) if value < 0 else "0")


# ------------------------------------------------------------- geometry helpers
def _ring_centroid(ring: list) -> tuple[float, float, float]:
    area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1], strict=True):
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if area == 0:
        return ring[0][0], ring[0][1], 0.0
    return cx / (3 * area), cy / (3 * area), abs(area) / 2


def _label_point(geometry: dict) -> tuple[float, float]:
    """Centroid of the largest polygon (good enough for a label)."""
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    best = max((_ring_centroid([tuple(p[:2]) for p in poly[0]]) for poly in polygons), key=lambda c: c[2])
    return best[0], best[1]


# ---------------------------------------------------------------- state view
def _state_map_figure(frame: pd.DataFrame, geo: dict, selected_fips: str | None) -> go.Figure:
    names = {f["properties"]["state_fips"]: f["properties"]["state_name"] for f in geo["features"]}
    rows = frame.set_index("state_fips")
    net = {fips: int(r["net_change_dem"]) for fips, r in rows.iterrows()
           if r["used_in_2026"] == "true" and pd.notna(r["net_change_dem"])}
    unused = [fips for fips, r in rows.iterrows() if r["used_in_2026"] != "true"]
    groups = {
        "gain": [f for f, v in net.items() if v > 0],
        "loss": [f for f, v in net.items() if v < 0],
        "zero": [f for f, v in net.items() if v == 0],
        "unused": unused,
    }
    other = [f for f in names if f not in net and f not in unused]
    colours = {"gain": BLUE, "loss": RED, "zero": WHITE, "unused": NOT_IN_USE_TAN, "other": WHITE}
    groups["other"] = other

    def hover(fips: str) -> str:
        if fips in net:
            r = rows.loc[fips]
            vacant = "" if r["vacant_old"] == "0" else f", {r['vacant_old']} vacant"
            return (f"<b>{r['state_name']}</b><br>{r['reason']}<br>{r['map_status']}"
                    f"<br>Old delegation: {r['dem_seats_old']} D, {r['rep_seats_old']} R{vacant} of {r['total_seats']}"
                    f"<br>Projected net change for Democrats: {_signed(net[fips])} seats")
        if fips in unused:
            r = rows.loc[fips]
            return f"<b>{r['state_name']}</b><br>{r['reason']}<br>{r['map_status']}<br>Not used in 2026: no seat change counted"
        return f"<b>{names[fips]}</b><br>No mid-decade map change in Ballotpedia's table"

    fig = go.Figure()
    for key in ("other", "unused", "zero", "loss", "gain"):
        fips_list = groups[key]
        if not fips_list:
            continue
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey="properties.state_fips", locations=fips_list, z=[0] * len(fips_list),
            colorscale=[[0, colours[key]], [1, colours[key]]], showscale=False,
            marker_line_color=OUTLINE, marker_line_width=0.7,
            customdata=[[f, names[f]] for f in fips_list], text=[hover(f) for f in fips_list],
            hovertemplate="%{text}<extra></extra>",
            selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
        ))
    if selected_fips:
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey="properties.state_fips", locations=[selected_fips], z=[0],
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
            marker_line_color="#111111", marker_line_width=3, hoverinfo="skip",
        ))
    label_lon, label_lat, label_text = [], [], []
    for feature in geo["features"]:
        fips = feature["properties"]["state_fips"]
        if fips in net and net[fips] != 0:
            lon, lat = _label_point(feature["geometry"])
            label_lon.append(lon)
            label_lat.append(lat)
            label_text.append(_signed(net[fips]))
    if label_text:
        fig.add_trace(go.Scattergeo(lon=label_lon, lat=label_lat, text=label_text, mode="text",
                                    textfont=dict(color="white", size=15, family="Arial Black"),
                                    hoverinfo="skip", showlegend=False))
    fig.update_geos(scope="usa", projection_type="albers usa", showlakes=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=470, paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
    return fig


def _state_bar_figure(frame: pd.DataFrame) -> go.Figure:
    in_use = frame[frame["used_in_2026"] == "true"].copy()
    net = _int(in_use["net_change_dem"]).astype(float)
    # Positive = Democratic gain, negative = Republican gain, as % of the state's seats.
    in_use["pct"] = net / _int(in_use["total_seats"]).astype(float) * 100
    in_use["net"] = net
    in_use = in_use.sort_values(["pct", "state_name"])
    fig = go.Figure()
    for name, mask, colour in (("Republican gain", in_use["pct"] < 0, RED), ("Democratic gain", in_use["pct"] > 0, BLUE)):
        part = in_use[mask]
        fig.add_trace(go.Bar(
            y=part["state_name"], x=part["pct"], orientation="h", name=name, marker_color=colour,
            text=[f"{abs(p):.1f}% ({int(abs(n))} seat{'' if abs(n) == 1 else 's'})" for p, n in zip(part["pct"], part["net"])],
            textposition="outside", cliponaxis=False,
            hovertemplate="%{y}: %{text}<extra>" + name + "</extra>",
        ))
    limit = max(5, int(abs(in_use["pct"]).max() // 5 * 5 + 5)) if len(in_use) else 5
    ticks = list(range(-limit, limit + 1, 5))
    fig.update_layout(
        height=max(260, 34 * len(in_use) + 100), margin=dict(l=0, r=30, t=10, b=0),
        xaxis=dict(title="Net seats gained, % of the state's House seats (left: Republican gain, right: Democratic gain)",
                   range=[-limit - 4, limit + 4], tickvals=ticks, ticktext=[f"{abs(t)}%" for t in ticks],
                   zeroline=True, zerolinecolor="#31333f", gridcolor="rgba(128,128,128,0.2)"),
        yaxis=dict(title="", automargin=True), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.12, x=0), bargap=0.35,
    )
    return fig


def _dots(count: int, colour: str, hollow: bool = False) -> str:
    fill = "transparent" if hollow else colour
    dot = (f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;margin:1px;'
           f'background:{fill};border:2px solid {colour};box-sizing:border-box"></span>')
    return dot * count


def _state_panel(row: pd.Series | None) -> None:
    if row is None:
        st.markdown("#### State details")
        st.info("Click a state on the map, or choose one in the list, to see its old delegation and projected change.")
        return
    st.markdown(f"#### {row['state_name']}")
    st.markdown(f"**{row['reason']}** · {row['map_status']}" + (f" · drawn by: {row['method']}" if pd.notna(row["method"]) else ""))
    dem, rep, vac = int(row["dem_seats_old"]), int(row["rep_seats_old"]), int(row["vacant_old"])
    st.markdown(f"**Old delegation** ({row['total_seats']} seats): {dem} Democratic, {rep} Republican"
                + (f", {vac} vacant" if vac else ""))
    st.markdown(f'<div style="line-height:0">{_dots(dem, BLUE)}{_dots(rep, RED)}{_dots(vac, VACANT_GREY, True)}</div>',
                unsafe_allow_html=True)
    if row["used_in_2026"] != "true" or pd.isna(row["net_change_dem"]):
        st.markdown("**New delegation (projection)**")
        st.write("No seat change counted: this state's new map is not being used in 2026.")
    else:
        net = int(row["net_change_dem"])
        new_dem, new_rep = dem + net, rep - net
        if new_dem < 0 or new_rep < 0:
            st.markdown("**New delegation (projection)**")
            st.write(f"Net change: Democrats {_signed(net)} seats (a full composition cannot be drawn from these figures).")
        else:
            st.markdown(f"**New delegation (projection)**: {new_dem} Democratic, {new_rep} Republican"
                        + (f", {vac} vacant" if vac else ""))
            st.markdown(f'<div style="line-height:0">{_dots(new_dem, BLUE)}{_dots(new_rep, RED)}{_dots(vac, VACANT_GREY, True)}</div>',
                        unsafe_allow_html=True)
            if net == 0:
                st.write("No net change projected.")
            elif net > 0:
                st.write(f"Net change: Democrats {_signed(net)}, Republicans {_signed(-net)}")
            else:
                st.write(f"Net change: Republicans {_signed(-net)}, Democrats {_signed(net)}")
    st.caption("Blue circle = Democratic seat, red circle = Republican seat, hollow grey = vacant. "
               "The new delegation applies Ballotpedia's projected net change to the old delegation, assuming the number of seats stays the same. These are projections, not actual results.")


def _clicked_fips(event) -> str | None:
    try:
        points = event.selection.points
    except AttributeError:
        return None
    for point in points or []:
        data = point.get("customdata")
        if isinstance(data, (list, tuple)) and data:
            return str(data[0])
        if point.get("location"):
            return str(point["location"])
    return None


# ------------------------------------------------------------- House composition
def _hemicycle_points(total: int, rows: int = 8) -> list[tuple[float, float]]:
    """Seat positions for a semicircle, ordered left to right (top of each arc first)."""
    radii = [0.45 + 0.55 * k / (rows - 1) for k in range(rows)]
    counts = [round(total * r / sum(radii)) for r in radii]
    counts[-1] += total - sum(counts)
    seats = []
    for radius, count in zip(radii, counts, strict=True):
        for j in range(count):
            angle = math.pi * (1 - j / (count - 1))
            seats.append((angle, radius))
    seats.sort(key=lambda a: (-a[0], -a[1]))
    return [(r * math.cos(a), r * math.sin(a)) for a, r in seats]


def _hemicycle_figure(now: pd.Series) -> go.Figure:
    dem, rep, ind, vac = (int(now[c]) for c in ("democrats", "republicans", "independents", "vacancies"))
    points = _hemicycle_points(dem + rep + ind + vac)
    groups = [
        (f"Democrats ({dem})", dem, BLUE, "circle"),
        (f"Independent ({ind})", ind, INDEPENDENT_GREY, "circle"),
        (f"Vacant ({vac})", vac, "white", "circle"),
        (f"Republicans ({rep})", rep, RED, "circle"),
    ]
    fig = go.Figure()
    start = 0
    for name, count, colour, symbol in groups:
        chunk = points[start:start + count]
        start += count
        if not chunk:
            continue
        fig.add_trace(go.Scatter(
            x=[p[0] for p in chunk], y=[p[1] for p in chunk], mode="markers", name=name,
            marker=dict(size=9, color=colour, symbol=symbol, line=dict(width=1.4, color="#6b6b6b" if colour == "white" else colour)),
            hovertemplate=f"{name}<extra></extra>",
        ))
    fig.add_annotation(x=0, y=0.12, showarrow=False, align="center",
                       text=f"<b>{MAJORITY_LINE}</b> seats needed<br>for a majority", font=dict(size=13, color="#3b4a5a"))
    fig.update_xaxes(visible=False, range=[-1.1, 1.1])
    fig.update_yaxes(visible=False, range=[-0.02, 1.08], scaleanchor="x", scaleratio=1)
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor="white",
                      legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5, font=dict(size=12)))
    return fig


def _advantage_figure(history: pd.DataFrame, now: pd.Series) -> go.Figure:
    """Democratic seats minus Republican seats at the start of each Congress, plus the House now."""
    points = [(str(r.start_year), int(r.democrats) - int(r.republicans), f"{r.congress} Congress ({r.start_year}\u2013{int(r.start_year) + 2})",
               f"Democrats {r.democrats}, Republicans {r.republicans}") for r in history.itertuples()]
    points.append(("Now", int(now["democrats"]) - int(now["republicans"]), "Now (House Press Gallery)",
                   f"Democrats {now['democrats']}, Republicans {now['republicans']}, vacant {now['vacancies']}"))
    labels = [p[0] for p in points]
    values = [p[1] for p in points]
    fig = go.Figure()
    fig.add_hline(y=0, line_color="#3b4a5a", line_width=1)
    fig.add_vrect(x0=len(history) - 3.5, x1=len(history) - 0.5, fillcolor="#f1ece0", opacity=0.8, line_width=0, layer="below")
    fig.add_trace(go.Scatter(
        x=labels, y=values, mode="lines+markers", name="Democratic seat advantage",
        line=dict(color="#3b4a5a", width=2),
        marker=dict(size=9, color=[BLUE if v > 0 else RED if v < 0 else INDEPENDENT_GREY for v in values],
                    line=dict(width=1.5, color="white"), symbol=["circle"] * (len(values) - 1) + ["diamond"]),
        customdata=[[p[2], p[3]] for p in points],
        hovertemplate="%{customdata[0]}<br>%{customdata[1]}<br>Democratic seat advantage: %{y:+d}<extra></extra>",
    ))
    top = max(max(values), 10)
    fig.add_annotation(xref="paper", yref="paper", x=(len(history) - 2 + 0.5) / len(labels), y=0.99, xanchor="center", yanchor="top",
                       showarrow=False, text="Last three<br>Congresses", font=dict(size=11, color="#3b4a5a"))
    fig.add_annotation(xref="paper", yref="y", x=0.5, y=top * 0.95, xanchor="center", yanchor="top", showarrow=False,
                       text="Democratic majority", font=dict(size=11, color=BLUE))
    fig.add_annotation(xref="paper", yref="y", x=0.3, y=min(min(values), -10) * 0.85, xanchor="center", yanchor="bottom", showarrow=False,
                       text="Republican majority", font=dict(size=11, color=RED))
    fig.update_layout(height=340, margin=dict(l=10, r=0, t=0, b=0), plot_bgcolor="white", showlegend=False)
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=labels, range=[-0.5, len(labels) - 0.5],
                     tickangle=-90, tickfont=dict(size=10), title_text="Congress (start year)")
    fig.update_yaxes(title_text="Democratic seats minus Republican seats", gridcolor="#ececec", zeroline=False, automargin=True)
    return fig


def render_house_context(data: pd.DataFrame, states: pd.DataFrame) -> None:
    st.header(HOUSE_TITLE)
    st.caption("Unit: House seats. Democratic seat advantage = Democratic seats minus Republican seats (below zero = Republican majority).")
    st.caption(f"{DATE_LABEL}: {_latest(data, 'as_of')} (House Press Gallery party breakdown; earlier Congresses show "
               "initial election results from the House Historian)")

    history = data[data["row_type"] == "start_of_congress"].assign(
        congress_number=lambda f: _int(f["congress_number"]), start_year=lambda f: _int(f["start_year"])
    ).sort_values("congress_number")
    now = data[data["row_type"] == "current"].iloc[0]
    recent = (_int(history["republicans"]) - _int(history["democrats"])).abs().tolist()[-3:]
    current_margin = int(now["republicans"]) - int(now["democrats"])

    left, right = st.columns(2)
    with left:
        st.markdown("**The House now: 435 seats**")
        st.plotly_chart(_hemicycle_figure(now), width="stretch", key="house_hemicycle", config={"displayModeBar": False})
    with right:
        st.markdown(f"**{ADVANTAGE_TITLE}**")
        st.plotly_chart(_advantage_figure(history, now), width="stretch", key="house_margin",
                        config={"displayModeBar": False})

    first, second = st.columns(2)
    leader = "Republicans" if current_margin > 0 else ("Democrats" if current_margin < 0 else "Neither party")
    first.metric("Margin in the House now", f"{leader} +{abs(current_margin)}" if current_margin else "Tied")
    second.metric(f"Margin at the start of the {history['congress'].iloc[-3]}, {history['congress'].iloc[-2]} and "
                  f"{history['congress'].iloc[-1]} Congresses", ", ".join(str(m) for m in recent) + " seats")

    st.caption(
        "Independents and vacant seats are shown separately, so the margin uses Democratic and Republican seats only. "
        "Earlier Congresses show seats at the start of each Congress."
    )
    st.caption(
        f"Sources: U.S. House Press Gallery, [{PRESS_GALLERY_TITLE}]({PRESS_GALLERY_URL}) (current membership, page updated 2026-09-02); "
        f"U.S. House Office of the Historian, [{HISTORIAN_TITLE}]({HISTORIAN_URL}) (initial election results for each Congress, retrieved 2026-10-10)."
    )
    with st.expander("What this does not show"):
        st.markdown(
            "- **Start of each Congress only.** Earlier bars use initial election results, so later deaths, resignations, "
            "special elections and party switches are not included. The 116th and 117th each began with one unfilled seat.\n"
            "- **Not predictions of results.** The projected House gain from redistricting does not predict who wins the House. Seat "
            "numbers could also change in states that did not redistrict, depending on how the polls and the election go.\n"
            "- **Margins do not indicate leadership.** Who elects the Speaker also depends on attendance, vacancies and "
            "how independents vote."
        )


def render_state_map(data: pd.DataFrame, geo: dict) -> None:
    st.header("Projections for House seat gains in states that redrew their district maps")
    st.caption("Unit: net change in Democratic House seats (projected). Positive = Democratic gain, negative = Republican gain.")
    st.caption(f"{DATE_LABEL}: {_latest(data, 'status_as_of')} (Ballotpedia's status date)")

    # Containers let the filter row sit under the map while its values are read first.
    top = st.container()
    filter_row = st.container()
    rest = st.container()

    with filter_row:
        st.markdown("**Display states by reason for redistricting:**")
        reasons = sorted(data["reason"].unique())
        columns = st.columns(len(reasons))
        selected = []
        for column, reason in zip(columns, reasons, strict=True):
            if column.checkbox(reason, value=True, key=f"reason_{_slug(reason)}"):
                selected.append(reason)

    filtered = data[data["reason"].isin(selected)]
    if filtered.empty:
        with top:
            st.info("No states match the selected filters.")
    else:
        in_use = filtered[filtered["used_in_2026"] == "true"]
        net = int(_int(in_use["net_change_dem"]).sum()) if len(in_use) else 0
        with top:
            left, middle, right = st.columns(3)
            if net < 0:
                left.metric("Projected net seat change", f"Republicans +{-net}")
            elif net > 0:
                left.metric("Projected net seat change", f"Democrats +{net}")
            else:
                left.metric("Projected net seat change", "No net change")
            middle.metric("States with a new map in use", f"{len(in_use)} of {len(filtered)}")
            right.metric("House seats in these states", f"{int(_int(filtered['total_seats']).sum())}")

            by_state = in_use.assign(net=_int(in_use["net_change_dem"]))
            gains = [f"{r.state_name} ({_signed(int(r.net))})" for r in by_state[by_state["net"] > 0].itertuples()]
            losses = [f"{r.state_name} ({int(-r.net)})" for r in by_state[by_state["net"] < 0].itertuples()]
            st.markdown(
                f"**Projected Democratic gains:** {', '.join(gains) or 'none'}.  \n"
                f"**Projected Republican gains:** {', '.join(losses) or 'none'}.  "
            )

            map_col, panel_col = st.columns([2, 1])
            options = sorted(filtered["state_name"])
            if st.session_state.get("state_inspect") not in options:
                st.session_state.pop("state_inspect", None)
            current = st.session_state.get("state_inspect")
            current_fips = None
            if current:
                current_fips = filtered.loc[filtered["state_name"] == current, "state_fips"].iloc[0]
            with map_col:
                event = st.plotly_chart(_state_map_figure(filtered, geo, current_fips), width="stretch",
                                        key="state_map_chart", on_select="rerun", selection_mode="points",
                                        config={"displayModeBar": False})
            clicked = _clicked_fips(event)
            if clicked is None:
                st.session_state.pop("_last_click", None)
            elif clicked != st.session_state.get("_last_click"):
                st.session_state["_last_click"] = clicked
                match = filtered.loc[filtered["state_fips"] == clicked, "state_name"]
                if len(match):
                    st.session_state["state_inspect"] = match.iloc[0]
            with panel_col:
                st.selectbox("Inspect a state", options, index=None, placeholder="Choose a state", key="state_inspect")
                chosen = st.session_state.get("state_inspect")
                _state_panel(filtered[filtered["state_name"] == chosen].iloc[0] if chosen else None)

            st.caption("Blue: Democrats projected to gain seats. Red: Republicans projected to gain seats (net). White: no mid-decade "
                       "map change in Ballotpedia's table"
                       + (f"; tan: map enacted or proposed but not used in 2026 ({', '.join(filtered[filtered['used_in_2026'] != 'true']['state_name'])})."
                          if (filtered["used_in_2026"] != "true").any() else ".")
                       + f" The number on a state is the projected net change in Democratic seats. {MAP_NOTE}")

        with rest:
            if net < 0:
                title = f"Projected net change by state: so far, redistricting leans towards Republican gains (net +{-net} seats)"
            elif net > 0:
                title = f"Projected net change by state: so far, redistricting leans towards Democratic gains (net +{net} seats)"
            else:
                title = "Projected net change by state: Democratic and Republican gains roughly offset"
            st.subheader(title)
            st.caption("On Ballotpedia's projections for the selected states; a projection, not a result, and maps may still change in court.")
            st.plotly_chart(_state_bar_figure(filtered), width="stretch", key="state_bar_chart",
                            config={"displayModeBar": False})

            st.subheader("State table")
            table = filtered[["state_name", "reason", "method", "map_status", "total_seats",
                              "rep_seats_old", "dem_seats_old", "vacant_old", "net_change_dem"]].rename(columns={
                "state_name": "State", "reason": "Reason", "method": "Who drew the map", "map_status": "Map status",
                "total_seats": "Seats", "rep_seats_old": "Old R seats", "dem_seats_old": "Old D seats",
                "vacant_old": "Vacant", "net_change_dem": "Projected net change (D)"})
            st.dataframe(table, hide_index=True, width="stretch")

    st.download_button(DOWNLOAD_LABEL, data=_csv_bytes(filtered), file_name="filtered_state_redistricting.csv",
                       mime="text/csv", key="state_download")
    st.caption(
        f"Source: Ballotpedia, [{BALLOTPEDIA_TITLE}]({BALLOTPEDIA_URL}) (status as of "
        f"{_latest(data, 'status_as_of')}; table compiled by hand, text under the GNU Free Documentation License). "
        f"State outlines: U.S. Census Bureau, [{CENSUS_TITLE}]({CENSUS_URL})."
    )
    with st.expander("What this does not show"):
        st.markdown(
            "- **Projections, not results.** No votes have been cast for the 2026 elections. The estimated seat changes shown "
            "are based on Ballotpedia's assessment of how proposed district maps may affect representation compared to the current delegation. "
            "Small differences should be interpreted with caution.\n"
            "- **How the projections work.** In its \"New maps enacted before the 2026 elections\" section, Ballotpedia shades the new congressional districts by 2024 presidential results. "
            "Its seat projections appear to rest on that basis, but Ballotpedia's method for the projected net change is not fully documented.\n"
            "- **Net seat change.** Reported Republican gains reflect the inverse of the projected Democratic net change. "
            "Vacancies, independents, and third parties are not modelled.\n"
            "- **District boundaries can still change.** Ongoing litigation and legislative actions may alter district maps after the date of the snapshot used.\n"
            "- **Mid-decade restructuring cases only.** States without mid-decade changes are shown in white and excluded from the analysis.\n"
            "- **Missouri and Virginia** show no projected seat change because their revised district maps are not expected to be used in the 2026 cycle.\n"
            "- **Seat projections do not measure competitiveness.** Changes in projected seat totals do not reflect the actual competition dynamics or voter turnout."
        )


# ------------------------------------------------------------- district view
STEPS = 10


def _district_figure(subset: pd.DataFrame, geo: dict, state: str, labels: dict) -> go.Figure:
    """Old plan underneath, new plan on top; a slider/animation fades the top layer in."""
    def layer(plan: str) -> dict:
        features = [f for f in geo["features"] if f["properties"]["state_abbr"] == state and f["properties"]["plan"] == plan]
        ids = [f["properties"]["district"] for f in features]
        shares = subset[subset["plan"] == plan].set_index("district")["dem_share_2party_2024"].astype(float)
        value = [float(shares[d]) for d in ids]
        return dict(
            geojson={"type": "FeatureCollection", "features": features}, featureidkey="properties.district",
            locations=ids, z=value, zmin=25, zmax=75, zmid=50, colorscale=DIVERGING,
            marker_line_color="#555555", marker_line_width=0.8,
            text=[f"{labels[plan]}<br>District {d}: {v:.1f}% Democratic" for d, v in zip(ids, value)],
        )

    old = go.Choropleth(**layer("old"), hovertemplate="%{text}<extra></extra>", marker_opacity=1.0,
                        colorbar=dict(title=dict(text="Democratic share, %"), thickness=10, len=0.8, tickvals=[25, 50, 75]))
    new = go.Choropleth(**layer("new"), hovertemplate="%{text}<extra></extra>", marker_opacity=0.0, showscale=False,
                        hoverinfo="skip")
    fig = go.Figure(data=[old, new])
    names = [f"step{i}" for i in range(STEPS + 1)]
    frames = []
    for i, name in enumerate(names):
        fade = i / STEPS
        frames.append(go.Frame(name=name, traces=[0, 1], data=[
            go.Choropleth(marker_opacity=1.0, hoverinfo="skip" if fade >= 0.5 else "text"),
            go.Choropleth(marker_opacity=fade, hoverinfo="text" if fade >= 0.5 else "skip"),
        ]))
    fig.frames = frames

    def play(order: list, duration: int) -> list:
        return [order, dict(mode="immediate", frame=dict(duration=duration, redraw=True), transition=dict(duration=0),
                            fromcurrent=False)]

    fig.update_layout(
        updatemenus=[dict(
            type="buttons", direction="left", x=0.0, y=0.0, xanchor="left", yanchor="top", pad=dict(t=10, r=8),
            buttons=[
                dict(label="Play: before \u2192 after", method="animate", args=play(names, 160)),
                dict(label="Reverse: after \u2192 before", method="animate", args=play(names[::-1], 160)),
            ],
        )],
        sliders=[dict(
            active=0, x=0.0, y=-0.02, len=1.0, pad=dict(t=50, b=0), currentvalue=dict(visible=False),
            steps=[dict(method="animate", label="Before" if i == 0 else ("After" if i == STEPS else ""),
                        args=[[name], dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))])
                   for i, name in enumerate(names)],
        )],
    )
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    # Side margins keep the centred "Before"/"After" slider labels from being clipped at the edges.
    fig.update_layout(margin=dict(l=36, r=36, t=0, b=0), height=560, paper_bgcolor="rgba(0,0,0,0)")
    return fig


DISTRICT_STATES = ["Utah", "Florida"]


def render_district_overlay(data: pd.DataFrame, geo: dict, states: pd.DataFrame) -> None:
    st.header("District-level view of potential seat changes due to redistricting in Utah and Florida")
    st.caption("Unit: percent (two-party Democratic share of the 2024 presidential vote), measured per district.")
    st.caption(f"{DATE_LABEL}: {_latest(data, 'measure_date')} (2024 election date; district shares as published by the Redistricting Data Hub)")
    st.markdown(
        "According to Ballotpedia's 2026 projections, Utah could see a seat gain for Democrats, "
        "while Florida could see Republicans strengthen their representation. "
        "Use the slider or Play button to transition between old and new district boundaries."
    )

    projected = states.set_index("state_name")["net_change_dem"]
    present = [s for s in DISTRICT_STATES if s in set(data["state_name"])]
    for column, state in zip(st.columns(len(present)), present, strict=True):
        with column:
            part = data[data["state_name"] == state]
            abbr = part["state_abbr"].iloc[0]
            net = int(projected[state]) if state in projected.index and pd.notna(projected[state]) else None
            if net is not None:
                who = "Democrats" if net > 0 else "Republicans"
                st.caption(f"{state}: Ballotpedia projects a net change of {_signed(net)} Democratic seats"
                           + (f" ({who} +{abs(net)})" if net else "") + ".")
            labels = {plan: part[part["plan"] == plan]["plan_label"].iloc[0] for plan in ("old", "new")}
            st.markdown(f"**Before:** {labels['old']}  \n**After:** {labels['new']}")

            shares = part["dem_share_2party_2024"].astype(float)
            seats = int((part["plan"] == "new").sum())
            old_n, new_n = int(((shares > 50) & (part["plan"] == "old")).sum()), int(((shares > 50) & (part["plan"] == "new")).sum())
            near = (shares - 50).abs() <= 2
            old_c, new_c = int((near & (part["plan"] == "old")).sum()), int((near & (part["plan"] == "new")).sum())
            left, right = st.columns(2)
            left.metric("Democratic-majority districts (old \u2192 new plan)", f"{old_n} \u2192 {new_n} (of {seats})")
            right.metric("Close districts, within 2 points (old \u2192 new plan)", f"{old_c} \u2192 {new_c}")
            st.plotly_chart(_district_figure(part, geo, abbr, labels), width="stretch",
                            key=f"district_map_{abbr}", config={"displayModeBar": False})
            row = states[states["state_name"] == state]
            if len(row):
                st.caption(
                    f"Two different measures: Ballotpedia's projection compares the new map with the current delegation "
                    f"({row['dem_seats_old'].iloc[0]} Democratic of {row['total_seats'].iloc[0]} seats), while the counts above "
                    f"re-add the 2024 presidential vote inside each district. A district counts as a Democratic majority only "
                    f"above 50.0%."
                )
    st.caption(MAP_NOTE)

    st.caption(
        f"Sources: Redistricting Data Hub, [{RDH_UTAH_TITLE}]({RDH_UTAH_URL}) and [{RDH_FLORIDA_TITLE}]({RDH_FLORIDA_URL}) (change reports and plan shapefiles; both retrieved 2026-10-10). Used under RDH's "
        "noncommercial, nonpartisan terms of use with credit; district outlines come from the plan shapefiles "
        "distributed by RDH and are simplified for display. Seat projections: Ballotpedia, "
        f"[{BALLOTPEDIA_TITLE}]({BALLOTPEDIA_URL})."
    )
    with st.expander("What this does not show"):
        st.markdown(
            "- **Not House election results.** Vote shares used come from the 2024 presidential two-party vote reallocated to the proposed district boundaries. "
            "Actual House races also depend on candidates, incumbency, turnout and broader political conditions in 2026.\n"
            "- **Illustrative cases only.** Utah and Florida are presented as examples of potential redistricting impacts because both have old and new district plans, "
            "published change reports, and represent contrasting scenarios of projected Democratic and Republican gains.\n"
            "- **Districts are not directly comparable.** Districts with the same number in the old and new plans may not "
            "represent the same geographic area or population, numbers are retained for reference only.\n"
            "- **Simplified map boundaries.** District outlines are generalised for web display and are not official legal boundaries."
        )


def render_district_table(data: pd.DataFrame) -> None:
    st.header("District data for the example states")
    st.caption("Unit: percent (two-party Democratic share of the 2024 presidential vote), measured per district.")
    st.caption(f"{DATE_LABEL}: {_latest(data, 'measure_date')} (2024 election date; district shares as published by the Redistricting Data Hub)")

    selected = st.multiselect("States", DISTRICT_STATES, default=DISTRICT_STATES, key="district_state_filter")
    st.write(f"Selected states: {', '.join(selected) if selected else 'none'}")

    filtered = data[data["state_name"].isin(selected)]
    if filtered.empty:
        st.info("No districts match the selected filters.")
    else:
        table = filtered[["state_name", "plan_label", "district", "dem_share_2party_2024"]].rename(columns={
            "state_name": "State", "plan_label": "Plan", "district": "District",
            "dem_share_2party_2024": "Democratic share of two-party 2024 presidential vote (%)"})
        st.dataframe(table, hide_index=True, width="stretch")

    st.download_button(DOWNLOAD_LABEL, data=_csv_bytes(filtered), file_name="filtered_district_shares.csv",
                       mime="text/csv", key="district_download")
    st.caption(
        f"Sources: Redistricting Data Hub, [{RDH_UTAH_TITLE}]({RDH_UTAH_URL}) and [{RDH_FLORIDA_TITLE}]({RDH_FLORIDA_URL}) (change reports and plan shapefiles; both retrieved 2026-10-10), used under RDH's noncommercial, "
        f"nonpartisan terms of use with credit. Seat projections: Ballotpedia, [{BALLOTPEDIA_TITLE}]({BALLOTPEDIA_URL})."
    )
