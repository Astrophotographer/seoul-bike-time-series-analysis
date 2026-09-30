from pathlib import Path

import pandas as pd
import pytest

from src.bike_analysis import (
    add_features,
    aggregate_bike_files,
    complete_calendar,
    flag_outliers,
    merge_weather,
    normalize_bike_columns,
    normalize_weather_columns,
)


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


def test_merge_weather_keeps_bike_dates_when_weather_is_missing():
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "rental_count": [10, 20, 30],
        }
    )
    weather = normalize_weather_columns(
        pd.DataFrame(
            {
                "일시": ["2023-01-01", "2023-01-03"],
                "평균기온(℃)": [1.0, 3.0],
                "강수량(mm)": [0.0, 2.0],
            }
        )
    )

    merged = merge_weather(daily, weather)

    assert len(merged) == 3
    missing_weather = merged.loc[
        merged["date"] == pd.Timestamp("2023-01-02")
    ].iloc[0]
    assert pd.isna(missing_weather["mean_temp_c"])
    assert missing_weather["rental_count"] == 20


def test_add_features_computes_weekly_metrics():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=8, freq="D"),
            "rental_count": [10, 20, 30, 40, 50, 60, 70, 80],
        }
    )

    featured = add_features(frame)

    assert {"rolling_7d", "pct_change", "rolling_std_7d"}.issubset(featured)
    assert featured.loc[6, "rolling_7d"] == 40
    assert featured.loc[1, "pct_change"] == 1.0
    assert pd.notna(featured.loc[6, "rolling_std_7d"])


def test_add_features_labels_weekday_month_and_rain():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
            "rental_count": [10, 20],
            "mean_temp_c": [5.0, 25.0],
            "precip_mm": [0.0, 1.0],
        }
    )

    featured = add_features(frame)

    assert featured["weekday"].tolist() == [6, 0]
    assert featured["month"].tolist() == [1, 1]
    assert featured["rain_flag"].tolist() == [False, True]
    assert featured["temperature_bin"].tolist() == ["0~10", "20~30"]


def test_flag_outliers_marks_but_does_not_drop_extreme_row():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=7, freq="D"),
            "rental_count": [10, 11, 10, 12, 9, 10, 1000],
        }
    )

    flagged = flag_outliers(frame)

    assert len(flagged) == len(frame)
    assert bool(flagged.loc[flagged["rental_count"] == 1000, "outlier_flag"].iloc[0])
