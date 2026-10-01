from pathlib import Path

import pandas as pd
import pytest

from analysis import run_pipeline
from src.bike_analysis import (
    add_features,
    aggregate_bike_files,
    complete_calendar,
    flag_outliers,
    make_baseline_forecast,
    make_plots,
    merge_weather,
    normalize_bike_columns,
    normalize_weather_columns,
    summarize_forecast,
    summarize_analysis,
)


def test_analysis_module_exports_public_api():
    assert callable(aggregate_bike_files)
    assert callable(complete_calendar)
    assert callable(add_features)
    assert callable(make_baseline_forecast)


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


def test_normalize_bike_columns_accepts_daily_rental_count_alias():
    frame = pd.DataFrame(
        {"대여일자": ["2023-01-01"], "대여건수": [7]}
    )

    normalized = normalize_bike_columns(frame)

    assert normalized["rental_count"].tolist() == [7]


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


def test_aggregate_bike_files_accepts_cp949_source(tmp_path: Path):
    source = tmp_path / "bike_cp949.csv"
    pd.DataFrame(
        [{"대여일자": "2023-01-01", "이용건수": 7}]
    ).to_csv(source, index=False, encoding="cp949")

    daily, _ = aggregate_bike_files(
        [source], start="2023-01-01", end="2023-01-01"
    )

    assert daily["rental_count"].tolist() == [7]


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


def test_normalize_weather_columns_accepts_open_meteo_names():
    frame = pd.DataFrame(
        {
            "time": ["2023-01-01"],
            "temperature_2m_mean": [2.5],
            "precipitation_sum": [0.0],
        }
    )

    normalized = normalize_weather_columns(frame)

    assert normalized["date"].tolist() == ["2023-01-01"]
    assert normalized["mean_temp_c"].tolist() == [2.5]
    assert normalized["precip_mm"].tolist() == [0.0]


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


def test_flag_outliers_does_not_mark_missing_rental_counts():
    frame = pd.DataFrame({"rental_count": [pd.NA, pd.NA]})

    flagged = flag_outliers(frame)

    assert flagged["outlier_flag"].tolist() == [False, False]


def _featured_frame(days: int = 35) -> pd.DataFrame:
    base = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=days, freq="D"),
            "rental_count": [100 + index * 3 for index in range(days)],
            "mean_temp_c": [5 + (index % 20) for index in range(days)],
            "precip_mm": [0.0 if index % 3 else 2.0 for index in range(days)],
            "record_missing": [False] * days,
        }
    )
    return add_features(base)


def test_summarize_analysis_reports_period_and_point_count():
    summary = summarize_analysis(_featured_frame(days=14))

    assert summary["start_date"] == "2023-01-01"
    assert summary["end_date"] == "2023-01-14"
    assert summary["point_count"] == 14


def test_summarize_analysis_reports_spearman_weather_correlations():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=4, freq="D"),
            "rental_count": [10, 20, 30, 40],
            "mean_temp_c": [1, 2, 3, 4],
            "precip_mm": [4, 3, 2, 1],
        }
    )

    summary = summarize_analysis(frame)

    assert summary["spearman_mean_temp_c_rental"] == pytest.approx(1.0)
    assert summary["spearman_precip_mm_rental"] == pytest.approx(-1.0)


def test_make_baseline_forecast_repeats_last_week_without_peeking():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=14, freq="D"),
            "rental_count": list(range(10, 150, 10)),
        }
    )

    forecast = make_baseline_forecast(frame, horizon=7, seasonal_period=7)
    metrics = summarize_forecast(forecast)

    assert forecast["actual"].tolist() == [80, 90, 100, 110, 120, 130, 140]
    assert forecast["forecast"].tolist() == [10, 20, 30, 40, 50, 60, 70]
    assert metrics["horizon"] == 7
    assert metrics["mae"] == pytest.approx(70.0)


def test_make_plots_creates_required_pngs(tmp_path: Path):
    paths = make_plots(_featured_frame(), tmp_path, include_stl=False)

    names = {path.name for path in paths}
    assert {
        "01_daily_trend.png",
        "02_month_weekday_heatmap.png",
        "03_weather_effect.png",
        "05_correlation.png",
        "06_baseline_forecast.png",
    }.issubset(names)
    assert all(path.exists() for path in paths)


def test_make_plots_handles_missing_weather_values(tmp_path: Path):
    frame = _featured_frame()
    frame.loc[0:4, ["mean_temp_c", "precip_mm", "rain_flag", "temperature_bin"]] = pd.NA

    paths = make_plots(frame, tmp_path, include_stl=False)

    assert (tmp_path / "01_daily_trend.png").exists()
    assert len(paths) >= 3


def test_run_pipeline_writes_processed_csv_and_five_images(tmp_path: Path):
    bike_dir = tmp_path / "bike"
    bike_dir.mkdir()
    bike_source = bike_dir / "bike_2023.csv"
    dates = pd.date_range("2023-01-01", periods=14, freq="D")
    pd.DataFrame(
        {
            "대여일자": dates.strftime("%Y-%m-%d"),
            "대여소번호": list(range(14)),
            "이용건수": list(range(100, 114)),
        }
    ).to_csv(bike_source, index=False, encoding="utf-8-sig")
    weather_path = tmp_path / "weather.csv"
    pd.DataFrame(
        {
            "일시": dates.strftime("%Y-%m-%d"),
            "평균기온(℃)": [5.0] * 14,
            "강수량(mm)": [0.0] * 14,
        }
    ).to_csv(weather_path, index=False, encoding="utf-8-sig")

    summary = run_pipeline(
        bike_dir=bike_dir,
        weather_path=weather_path,
        output_dir=tmp_path,
        start="2023-01-01",
        end="2023-01-14",
    )

    assert summary["point_count"] == 14
    assert (tmp_path / "data" / "processed_daily_rentals.csv").exists()
    assert len(list((tmp_path / "images").glob("*.png"))) >= 5


def test_run_pipeline_rejects_missing_bike_directory(tmp_path: Path):
    missing_dir = tmp_path / "missing-bike"

    with pytest.raises(FileNotFoundError, match="missing-bike"):
        run_pipeline(
            bike_dir=missing_dir,
            weather_path=None,
            output_dir=tmp_path,
            start="2023-01-01",
            end="2023-01-14",
        )
