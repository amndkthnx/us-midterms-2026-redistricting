"""Provenance script: how the district and state-outline files were built by hand.

NOT part of the offline pipeline (`python -m src.data`) and not run by the
tests: it needs the raw downloads, which are too large to ship, plus
geopandas/shapely, poppler's `pdftotext` and a Python that can import them.

Raw inputs (download manually, put them in one folder, pass it as argv[1]):
  * Redistricting Data Hub change reports (PDF) for Utah and Florida:
      ut_cong_120_district_changes.pdf, fl_cong_120_district_changes.pdf
  * RDH plan shapefiles (Utah and Florida pages on redistrictingdatahub.org). RDH retrieved each from the
    publisher named below and re-hosted it without modifying the data:
      - Utah old plan: 2021 Adopted Congressional Plan (Utah Legislative Redistricting Committee,
        retrieved by RDH 30 November 2021): ut_cong_2021/ut_cong_2021.shp
      - Utah new plan: 2025 Congressional Districts Approved Plan (Utah SGID, retrieved by RDH 8 December 2025):
        ut_cong_adopted_2025/us_congress_districts_2026_to_2032.shp
      - Florida old plan: Congressional Districts Plan Approved 2022 (Florida Redistricting 2022,
        retrieved by RDH 25 April 2022): fl_cong_adopted_2022/P000C0109.shp
      - Florida new plan: 2026 Congressional Districts Approved Plan (Florida Senate, retrieved by RDH 30 April 2026):
        fl_cong_adopted_2026/EOGPCRP2026/EOGPCRP2026.shp
  * Census cartographic boundary geodatabase cb_2025_us_all_5m.gdb
      (layer cb_2025_us_state_5m)

Outputs written next to the inputs, then copied into data/ (the CSV was then
renamed to sample_districts.csv with a `state_name` column added):
  districts_examples.geojson, district_shares_examples.csv, us_states.geojson

    python src/acquire_districts.py /path/to/raw_folder [/path/to/output_folder]
"""

from __future__ import annotations

import os
import subprocess
import sys

import geopandas as gpd
import pandas as pd
from shapely import set_precision

D = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else D


def parse_report(pdf: str, n_districts: int) -> dict[int, tuple[float, float]]:
    """Read (old %, new %) two-party Democratic share per district from an RDH report."""
    text = subprocess.run(
        ["pdftotext", "-layout", "-f", "1", "-l", "6", os.path.join(D, pdf), "-"],
        capture_output=True, text=True, check=True,
    ).stdout
    rows: dict[int, tuple[float, float]] = {}
    for line in text.splitlines():
        t = line.split()
        if len(t) == 11 and t[0].isdigit() and all(x.endswith("%") for x in t[1:]):
            rows.setdefault(int(t[0]), (float(t[5].rstrip("%")), float(t[10].rstrip("%"))))
    assert sorted(rows) == list(range(1, n_districts + 1)), (pdf, sorted(rows))
    return rows


ut = parse_report("ut_cong_120_district_changes.pdf", 4)
fl = parse_report("fl_cong_120_district_changes.pdf", 28)
# Spot checks against values read by eye from the PDFs.
assert ut[1] == (39.7, 62.2) and ut[3] == (40.1, 28.8) and fl[1] == (31.2, 31.2) and fl[9] == (51.8, 41.0) and fl[25] == (52.7, 45.4)

SPECS = [  # state, fips, plan, label, shapefile, district column, report, report index, simplify tolerance
    ("UT", "49", "old", "2021 enacted map", "ut_cong_2021/ut_cong_2021.shp", "DISTRICTNO", ut, 0, 0.002),
    ("UT", "49", "new", "2025 court-ordered map", "ut_cong_adopted_2025/us_congress_districts_2026_to_2032.shp", "DISTRICT", ut, 1, 0.002),
    ("FL", "12", "old", "2022 enacted map", "fl_cong_adopted_2022/P000C0109.shp", "DISTRICT", fl, 0, 0.004),
    ("FL", "12", "new", "2026 enacted map", "fl_cong_adopted_2026/EOGPCRP2026/EOGPCRP2026.shp", "DISTRICT", fl, 1, 0.004),
]
NAMES = {"UT": "Utah", "FL": "Florida"}

features, records = [], []
for st, fips, plan, label, shp, col, report, idx, tol in SPECS:
    g = gpd.read_file(os.path.join(D, shp)).to_crs(4326)
    g["district"] = g[col].astype(int).map(lambda x: f"{x:02d}")
    g["geometry"] = g.geometry.simplify(tol, preserve_topology=True).apply(lambda s: set_precision(s, 1e-5))
    if g.district.duplicated().any():
        g = g.dissolve(by="district", as_index=False)
    g["state_abbr"], g["plan"], g["plan_label"] = st, plan, label
    features.append(g[["state_abbr", "plan", "plan_label", "district", "geometry"]])
    for district, values in report.items():
        records.append(dict(
            state_name=NAMES[st], state_abbr=st, state_fips=fips, plan=plan, plan_label=label,
            district=f"{district:02d}", dem_share_2party_2024=values[idx], measure_date="2024-11-05",
            source=f"Redistricting Data Hub, {NAMES[st]} Congressional Redistricting Change Analysis (119th vs 120th plans)",
        ))

districts = gpd.GeoDataFrame(pd.concat(features, ignore_index=True), crs=4326)
table = pd.DataFrame(records)
assert set(zip(table.state_abbr, table.plan, table.district)) == set(zip(districts.state_abbr, districts.plan, districts.district))
assert districts.geometry.is_valid.all()
districts.to_file(os.path.join(OUT, "districts_examples.geojson"), driver="GeoJSON")
table.to_csv(os.path.join(OUT, "district_shares_examples.csv"), index=False, encoding="utf-8")

# State outlines (50 states + DC) for the choropleth.
states = gpd.read_file(os.path.join(D, "cb_2025_us_all_5m.gdb"), layer="cb_2025_us_state_5m")
states = states[~states.STUSPS.isin(["VI", "AS", "GU", "MP", "PR"])].to_crs(4326)
states["geometry"] = states.geometry.simplify(0.02, preserve_topology=True)
states = states.rename(columns={"STATEFP": "state_fips", "STUSPS": "state_abbr", "NAME": "state_name"})
states[["state_fips", "state_abbr", "state_name", "geometry"]].sort_values("state_fips").to_file(
    os.path.join(OUT, "us_states.geojson"), driver="GeoJSON", COORDINATE_PRECISION=4)
print("Wrote districts_examples.geojson, district_shares_examples.csv, us_states.geojson")
