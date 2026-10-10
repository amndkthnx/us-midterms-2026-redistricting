"""Data pipeline for the redistricting dashboard.

Both datasets are manually assembled snapshots (see README.md for the manual
acquisition steps and src/acquire_districts.py for how the district table was
built), so `transform()` re-reads the bundled samples, 
`validate()` enforces the documented expectations, and
`main()` writes the declared processed outputs only.

    python -m src.data              # rebuild data/processed_*.csv
    python -m src.data --validate   # validate the existing processed files
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

DATASETS = {
    "states": (DATA / "sample_states.csv", DATA / "processed_states.csv"),
    "districts": (DATA / "sample_districts.csv", DATA / "processed_districts.csv"),
    "house": (DATA / "sample_house.csv", DATA / "processed_house.csv"),
}

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

STATE_COLUMNS = [
    "state_name", "state_abbr", "state_fips", "total_seats", "reason", "method",
    "map_status", "used_in_2026", "action_date", "rep_seats_old", "dem_seats_old",
    "vacant_old", "net_change_dem", "source_url", "status_as_of",
]
DISTRICT_COLUMNS = [
    "state_name", "state_abbr", "state_fips", "plan", "plan_label", "district",
    "dem_share_2party_2024", "measure_date", "source",
]
HOUSE_COLUMNS = [
    "congress", "congress_number", "start_year", "row_type", "total_seats", "democrats",
    "republicans", "independents", "vacancies", "as_of", "source",
]
HOUSE_INTS = ["congress_number", "start_year", "total_seats", "democrats", "republicans", "independents", "vacancies"]
HOUSE_ROW_TYPES = {"start_of_congress", "current"}
STATE_INTS = ["total_seats", "rep_seats_old", "dem_seats_old", "vacant_old", "net_change_dem"]
STATE_DATES = ["action_date", "status_as_of"]

STATE_NAMES = {
    "AL": "Alabama", "CA": "California", "FL": "Florida", "LA": "Louisiana",
    "MO": "Missouri", "NC": "North Carolina", "OH": "Ohio", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VA": "Virginia",
}
FIPS = {
    "AL": "01", "CA": "06", "FL": "12", "LA": "22", "MO": "29", "NC": "37",
    "OH": "39", "TN": "47", "TX": "48", "UT": "49", "VA": "51",
}
REASONS = {"Changed due to litigation", "Required by law to redistrict", "Voluntary redistricting"}
METHODS = {"Commission", "Legislature-dominant"}
MAP_STATUSES = {"New map in effect", "Enacted but not in use", "Blocked by court"}
PLANS = {"old": "district_old", "new": "district_new"}
# Districts per plan: Utah 4, Florida 28 (matches total_seats in the state table).
DISTRICTS_PER_STATE = {"UT": 4, "FL": 28}


def read_csv(path: Path) -> pd.DataFrame:
    """Read with the contract semantics: all text, only empty fields missing."""
    return pd.read_csv(path, dtype=object, keep_default_na=False, na_values=[""])


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _check_dates(series: pd.Series, name: str, low: str, high: str, nullable: bool) -> None:
    present = series.dropna()
    _require(nullable or len(present) == len(series), f"{name}: missing dates")
    _require(present.map(lambda v: bool(ISO_DATE.match(v))).all(), f"{name}: dates must be YYYY-MM-DD")
    parsed = pd.to_datetime(present, errors="raise")
    _require(parsed.min() >= pd.Timestamp(low) and parsed.max() <= pd.Timestamp(high),
             f"{name}: date outside {low}..{high}")


def validate_states(frame: pd.DataFrame) -> None:
    _require(list(frame.columns) == STATE_COLUMNS, f"Unexpected state columns: {list(frame.columns)}")
    _require(len(frame) >= 10, "The state table must contain at least ten rows")
    _require(not frame.duplicated("state_abbr").any(), "Duplicate state_abbr")
    required = [c for c in STATE_COLUMNS if c not in {"method", "action_date", "net_change_dem"}]
    _require(not frame[required].isna().any().any(), "Unexpected missing values in required state columns")
    _require(set(frame["state_abbr"]) <= set(STATE_NAMES), "Unexpected state_abbr")
    _require((frame["state_abbr"].map(STATE_NAMES) == frame["state_name"]).all(), "state_name does not match state_abbr")
    _require((frame["state_abbr"].map(FIPS) == frame["state_fips"]).all(), "state_fips does not match state_abbr")
    _require(set(frame["reason"]) <= REASONS, "Unexpected reason")
    _require(set(frame["method"].dropna()) <= METHODS, "Unexpected method")
    _require(set(frame["map_status"]) <= MAP_STATUSES, "Unexpected map_status")
    _require(set(frame["used_in_2026"]) <= {"true", "false"}, "used_in_2026 must be true/false")
    for column in STATE_INTS:
        values = frame[column].dropna()
        _require(values.map(lambda v: bool(re.fullmatch(r"-?\d+", v))).all(), f"{column}: not an integer")
    ints = {c: pd.to_numeric(frame[c]) for c in STATE_INTS}
    _require(ints["total_seats"].between(1, 60).all(), "total_seats outside 1..60")
    _require(ints["rep_seats_old"].between(0, 60).all() and ints["dem_seats_old"].between(0, 60).all()
             and ints["vacant_old"].between(0, 60).all(), "Seat counts outside 0..60")
    _require((ints["rep_seats_old"] + ints["dem_seats_old"] + ints["vacant_old"] == ints["total_seats"]).all(),
             "Old seats (R + D + vacant) do not add up to total_seats")
    _require(ints["net_change_dem"].dropna().between(-20, 20).all(), "net_change_dem outside -20..20")
    in_use = frame["used_in_2026"] == "true"
    _require(not frame.loc[in_use, "net_change_dem"].isna().any(), "Maps in use must have a projected net change")
    _require(frame.loc[~in_use, "net_change_dem"].isna().all(), "Maps not in use must not carry a net change")
    _check_dates(frame["action_date"], "action_date", "2025-01-01", "2026-12-31", True)
    _check_dates(frame["status_as_of"], "status_as_of", "2026-01-01", "2026-12-31", False)
    _require(frame["source_url"].str.startswith("https://ballotpedia.org/").all(), "source_url must be a Ballotpedia URL")


def validate_districts(frame: pd.DataFrame, states: pd.DataFrame | None = None) -> None:
    _require(list(frame.columns) == DISTRICT_COLUMNS, f"Unexpected district columns: {list(frame.columns)}")
    _require(len(frame) >= 10, "The district table must contain at least ten rows")
    _require(not frame.isna().any().any(), "Unexpected missing values in district table")
    _require(not frame.duplicated(["state_abbr", "plan", "district"]).any(), "Duplicate state/plan/district keys")
    _require(set(frame["state_abbr"]) <= set(DISTRICTS_PER_STATE), "Unexpected state_abbr in district table")
    _require((frame["state_abbr"].map(STATE_NAMES) == frame["state_name"]).all(), "state_name does not match state_abbr")
    _require((frame["state_abbr"].map(FIPS) == frame["state_fips"]).all(), "state_fips does not match state_abbr")
    _require(set(frame["plan"]) <= set(PLANS), "plan must be old or new")
    _require(frame["district"].map(lambda v: bool(re.fullmatch(r"\d{2}", v))).all(), "district must be a zero-padded 2-digit string")
    for (abbr, plan), group in frame.groupby(["state_abbr", "plan"]):
        expected = [f"{n:02d}" for n in range(1, DISTRICTS_PER_STATE[abbr] + 1)]
        _require(sorted(group["district"]) == expected, f"{abbr} {plan}: expected districts {expected[0]}..{expected[-1]}")
        _require(group["plan_label"].nunique() == 1, f"{abbr} {plan}: inconsistent plan_label")
    _require(frame.groupby("state_abbr")["plan"].nunique().eq(2).all(), "Each state needs both old and new plans")
    share = pd.to_numeric(frame["dem_share_2party_2024"], errors="raise")
    _require(share.between(0, 100).all(), "dem_share_2party_2024 outside 0..100")
    _check_dates(frame["measure_date"], "measure_date", "2024-11-05", "2024-11-05", False)
    if states is not None:
        seats = states.set_index("state_abbr")["total_seats"].astype(int)
        for abbr, group in frame.groupby("state_abbr"):
            _require(abbr in seats.index and seats[abbr] == DISTRICTS_PER_STATE[abbr],
                     f"{abbr}: district count does not match total_seats in the state table")


def validate_house(frame: pd.DataFrame) -> None:
    _require(list(frame.columns) == HOUSE_COLUMNS, f"Unexpected house columns: {list(frame.columns)}")
    _require(len(frame) >= 10, "The House composition table must contain at least ten rows")
    _require(not frame.isna().any().any(), "Unexpected missing values in House composition table")
    _require(not frame.duplicated(["congress_number", "row_type"]).any(), "Duplicate congress/row_type keys")
    _require(set(frame["row_type"]) <= HOUSE_ROW_TYPES, "Unexpected row_type")
    _require((frame["row_type"] == "current").sum() == 1, "Exactly one current row is expected")
    for column in HOUSE_INTS:
        _require(frame[column].map(lambda v: bool(re.fullmatch(r"\d+", v))).all(), f"{column}: not a non-negative integer")
    ints = {c: pd.to_numeric(frame[c]) for c in HOUSE_INTS}
    _require((ints["total_seats"] == 435).all(), "total_seats must be 435")
    _require((ints["democrats"] + ints["republicans"] + ints["independents"] + ints["vacancies"] == ints["total_seats"]).all(),
             "Democrats + Republicans + independents + vacancies must equal total_seats")
    _require(ints["start_year"].between(1977, 2026).all(), "start_year outside 1977..2026")
    _check_dates(frame["as_of"], "as_of", "1977-01-01", "2026-12-31", False)


def transform(sample: Path, kind: str) -> pd.DataFrame:
    """Normalise formats and order rows deterministically (no rows are dropped)."""
    frame = read_csv(sample)
    if kind == "states":
        for column in STATE_INTS:
            frame[column] = frame[column].map(lambda v: v if pd.isna(v) else str(int(v)))
        return frame.sort_values("state_abbr").reset_index(drop=True)
    if kind == "house":
        for column in HOUSE_INTS:
            frame[column] = frame[column].map(lambda v: str(int(v)))
        order = frame.assign(_n=frame["congress_number"].astype(int)).sort_values(["_n", "row_type"], ascending=[True, False])
        return order.drop(columns="_n").reset_index(drop=True)
    frame["dem_share_2party_2024"] = frame["dem_share_2party_2024"].map(lambda v: f"{float(v):.1f}")
    return frame.sort_values(["state_abbr", "plan", "district"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--validate", action="store_true", help="Validate the processed files and stop")
    args = parser.parse_args()
    if args.validate:
        states, districts, house = (read_csv(DATASETS[k][1]) for k in ("states", "districts", "house"))
        validate_states(states)
        validate_districts(districts, states)
        validate_house(house)
        print("Processed data valid")
        return
    frames = {kind: transform(sample, kind) for kind, (sample, _) in DATASETS.items()}
    validate_states(frames["states"])
    validate_districts(frames["districts"], frames["states"])
    validate_house(frames["house"])
    for kind, (_, output) in DATASETS.items():
        output.parent.mkdir(parents=True, exist_ok=True)
        frames[kind].to_csv(output, index=False, lineterminator="\n")
        print(f"Validated and wrote {len(frames[kind])} rows to {output}")


if __name__ == "__main__":
    main()
