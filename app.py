from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.views import render_district_overlay, render_district_table, render_house_context, render_state_map


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


@st.cache_data
def load_table(path: str) -> pd.DataFrame:
    # Contract semantics: everything is text, only empty fields are missing.
    return pd.read_csv(path, dtype=object, keep_default_na=False, na_values=[""])


@st.cache_data
def load_geojson(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def data_path(sample_name: str, processed_name: str) -> Path:
    sample_mode = os.getenv("DASHBOARD_SAMPLE_MODE", "0") == "1"
    processed = DATA / processed_name
    if sample_mode or not processed.exists():
        return DATA / sample_name
    return processed


st.set_page_config(page_title="Redistricting and the 2026 US midterms", layout="wide")
st.title("Redistricting and the 2026 US House midterms")
st.write(
    "**Question:** "
    "To what extent could mid-decade redistricting ahead of the 2026 US midterm elections shift the balance of power "
    "in the US House of Representatives? How is this projected to affect representation in states that redrew district boundaries, and what does this look like in practice?"
)
st.caption(
    "Audience: Non-specialist observers interested in the 2026 US midterm elections who want to understand the potential electoral impacts of redistricting. "
    "The dashboard displays projected seat changes based on a dated snapshot, not election outcomes."
)

states = load_table(str(data_path("sample_states.csv", "processed_states.csv")))
districts = load_table(str(data_path("sample_districts.csv", "processed_districts.csv")))
house = load_table(str(data_path("sample_house.csv", "processed_house.csv")))
state_geo = load_geojson(str(DATA / "us_states.geojson"))
district_geo = load_geojson(str(DATA / "districts_examples.geojson"))

with st.container(key="house_context"):
    render_house_context(house, states)

with st.container(key="state_map"):
    render_state_map(states, state_geo)

with st.container(key="district_overlay"):
    render_district_overlay(districts, district_geo, states)

with st.container(key="district_table"):
    render_district_table(districts)

with st.expander("Data and limitations"):
    st.markdown(
        "**Sources:** Ballotpedia (state table, status as of 2026-09-28); U.S. House Office of the Historian and House Press Gallery (House party composition); Redistricting Data Hub (Utah and Florida "
        "district vote shares and plan shapefiles); U.S. Census Bureau (state outlines). Full titles, links and "
        "licence notes are in the README and `dashboard.yml`."
    )
    st.markdown(
        "Seat changes are projections that compare each new map with the current delegation. District vote shares "
        "re-add up the 2024 presidential vote and are not House results. Court cases may still change maps."
    )
