from pathlib import Path

import pandas as pd
import pytest

from src.bike_analysis import add_features, aggregate_bike_files, complete_calendar
from src.bike_analysis import normalize_bike_columns


def test_analysis_module_exports_public_api():
    assert callable(aggregate_bike_files)
    assert callable(complete_calendar)
    assert callable(add_features)


def test_normalize_bike_columns_maps_korean_names():
    frame = pd.DataFrame(
        {
            " 대여일자 ": ["2023-01-01"],
            "이용건수": [3],
            "대여소번호": [1],
        }
    )

    normalized = normalize_bike_columns(frame)

    assert "date" in normalized.columns
    assert "rental_count" in normalized.columns


def test_normalize_bike_columns_rejects_missing_required_column():
    frame = pd.DataFrame({"대여일자": ["2023-01-01"]})

    with pytest.raises(ValueError, match="이용건수"):
        normalize_bike_columns(frame)


def test_aggregate_bike_files_sums_by_date_and_removes_exact_duplicates(
    tmp_path: Path,
):
    source = tmp_path / "bike.csv"
    pd.DataFrame(
        [
            {"대여일자": "2023-01-01", "대여소번호": 1, "이용건수": 3},
            {"대여일자": "2023-01-01", "대여소번호": 2, "이용건수": 4},
            {"대여일자": "2023-01-01", "대여소번호": 1, "이용건수": 3},
            {"대여일자": "2023-01-02", "대여소번호": 1, "이용건수": 5},
        ]
    ).to_csv(source, index=False, encoding="utf-8-sig")

    daily, audit = aggregate_bike_files(
        [source], start="2023-01-01", end="2023-01-02"
    )

    assert daily["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2023-01-01",
        "2023-01-02",
    ]
    assert daily["rental_count"].tolist() == [7, 5]
    assert audit["duplicate_rows"] == 1


def test_complete_calendar_marks_missing_dates_without_zero_fill():
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-01-01", "2023-01-03"]),
            "rental_count": [7, 5],
        }
    )

    completed = complete_calendar(daily, start="2023-01-01", end="2023-01-03")

    missing_row = completed.loc[completed["date"] == pd.Timestamp("2023-01-02")].iloc[0]
    assert pd.isna(missing_row["rental_count"])
    assert bool(missing_row["record_missing"])
