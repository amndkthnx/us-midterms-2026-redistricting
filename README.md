# Redistricting and the 2026 US House midterms

Streamlit dashboard (subject `usa_elections_2026`). It asks: *which states changed their congressional maps ahead of the 2026 midterms, how many House seats could each side gain or lose, and how did the new lines reshape districts in Utah and Florida?*

Four sections, each with its own heading, sources and CSV download where relevant:

1. **In each of the last three Congresses, the House majority was 10 seats or fewer** (opens the dashboard): two panels side by side. Left, a 435-seat hemicycle of the House now (214 Democrats, 218 Republicans, 1 independent in a neutral grey, 2 vacant, with the 218-seat majority marked). Right, a line chart of the Democratic seat advantage (Democratic minus Republican seats) at the start of each of the last 25 Congresses (95th to 119th) plus today; the last three Congresses are shaded because the margin narrowed in each (36, then 10, 9 and 5 seats). The tests check that claim against the data.
2. **Projections for House seat gains in states that redrew their district maps**: a US map (blue = Democrats projected to gain seats, red = Republicans projected to gain seats, white = no change, number = projected net change in Democratic seats), with the reason-for-redistricting tick boxes in one row under it; a panel that opens when you click a state (or pick it in the list) showing the old delegation and the projected new delegation as red/blue circles; a bar chart of net gain as % of each state's seats; a table and metrics. The date line reads "Based on snapshots on".
3. **District-level view of potential seat changes due to redistricting in Utah and Florida**: the two states side by side under one title (Utah: Democrats could potentially gain a seat; Florida: Republicans could potentially strengthen their position), each with a slider (or Play/Reverse buttons) that fades gradually from the old plan to the new plan. Districts are shaded by 2024 two-party Democratic share.
4. **District data table**: both states' districts, with a state filter (both selected by default) and a CSV download.

Seat changes are Ballotpedia projections, not results. District shares re-add the 2024 presidential vote to the district lines; they are not House results.

**Internet required to view the maps:** the choropleths use Plotly's geo maps, which load their base map from the internet (cdn.plot.ly). Offline, the maps appear blank; the charts, tables and downloads still work.

## Run (Python 3.11 required)

```bash
pip install -r requirements.txt
export DASHBOARD_SAMPLE_MODE=1      # on Windows PowerShell: $env:DASHBOARD_SAMPLE_MODE = "1"
streamlit run app.py
```

Without `DASHBOARD_SAMPLE_MODE` the app reads `data/processed_*.csv` when present, otherwise the samples.

## Rebuild and validate the processed data

```bash
export DASHBOARD_SAMPLE_MODE=1
python -m src.data              # reads data/sample_*.csv, validates, writes data/processed_*.csv
python -m src.data --validate   # validates the existing processed files
pytest                          # app and interaction tests
```

The transform writes only the two declared processed outputs. There is no network step.

## Data files

| File | What it is |
| --- | --- |
| `data/sample_states.csv` / `processed_states.csv` | 11 states from Ballotpedia's mid-decade redistricting table (status as of 2026-09-28) |
| `data/sample_districts.csv` / `processed_districts.csv` | 64 district rows: Utah (4) and Florida (28), old and new plans, 2024 two-party Democratic share |
| `data/sample_house.csv` / `processed_house.csv` | 26 rows: party seats at the start of the 95th to 119th Congresses (House Historian, initial election results) plus the current 119th Congress membership (House Press Gallery, page updated 2026-09-02) |
| `data/us_states.geojson` | State outlines (50 states + DC), simplified from the Census cartographic boundary file |
| `data/districts_examples.geojson` | Simplified district outlines for the old and new Utah and Florida plans |

The sample *is* the full snapshot (all three tables are small hand-compiled extracts), so processed output equals the sample after normalisation (row order, number formats).

## Acquisition (manual)

All sources were downloaded or manually compiled; `src/acquire_districts.py` documents exactly how the district table and outlines were derived (it needs the large raw files, which are not shipped).

1. **Ballotpedia**, [Redistricting ahead of the 2026 elections](https://ballotpedia.org/Redistricting_ahead_of_the_2026_elections): status table transcribed to `sample_states.csv`; Missouri's row follows Ballotpedia's Missouri page. `net_change_dem` is Ballotpedia's "potential result", expressed as a net change in Democratic seats. Missouri (enacted, not used in 2026) and Virginia (blocked by court) have no counted change.
2. **U.S. House Office of the Historian**, [Party Divisions of the House of Representatives](https://history.house.gov/Institution/Party-Divisions/Party-Divisions/): seats per party for the 95th to 119th Congresses, transcribed by hand; vacant seats are 435 minus the party counts (the 116th and 117th each began with one seat lacking a certificate). **U.S. House Press Gallery**, [Party breakdown](https://pressgallery.house.gov/member-data/party-breakdown): current membership. Neither page states reuse terms; credit and links are shown beside the view.
3. **Redistricting Data Hub** ([Utah](https://redistrictingdatahub.org/state/utah/) and [Florida](https://redistrictingdatahub.org/state/florida/) pages): *Congressional Redistricting Change Analysis* PDFs (119th vs 120th Congress plans) for the district shares, and the following plan shapefiles for the district outlines. Utah: *2021 Adopted Congressional Plan* (Utah Legislative Redistricting Committee, uploaded 7 December 2021) as the old plan and *2025 Congressional Districts Approved Plan* (Utah SGID, uploaded 12 November 2025) as the new plan. Florida: *Congressional Districts Plan Approved 2022* (Florida Redistricting 2022, uploaded 25 April 2022) as the old plan and *2026 Congressional Districts Approved Plan* (Florida Senate, uploaded 30 April 2026) as the new plan.
4. **U.S. Census Bureau**, 2025 Cartographic Boundary Files, States (1:5,000,000) for state outlines.

## Licences and credit

- Ballotpedia: text and tables under the GNU Free Documentation License; credit and link are shown beside the view.
- Redistricting Data Hub: use is noncommercial and nonpartisan, with credit (shown beside the view). Free registration is required to download the data
- U.S. Census Bureau: public domain.

## Limitations

- The House Historian's counts are initial election results: later deaths, resignations, special elections and party switches are not in the historical bars. The Press Gallery page does not say which caucus the independent belongs to, so the independent is shown on its own.
- Ballotpedia's projection method is not fully documented and may mix presidential-vote and current-delegation assumptions.
- District numbers in the old and new plans are not comparable.
- Boundaries are simplified for display.
