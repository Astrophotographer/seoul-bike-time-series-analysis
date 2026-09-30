"""Core analysis helpers for the Seoul public-bike time series."""

from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

try:
    from statsmodels.tsa.seasonal import STL
except ImportError:  # pragma: no cover - depends on the local environment
    STL = None  # type: ignore[assignment,misc]


_BIKE_COLUMN_ALIASES = {
    "date": ("date", "대여일자", "대여일시"),
    "rental_count": (
        "rental_count",
        "이용건수",
        "이용 건수",
        "대여건수",
        "대여 건수",
    ),
}

_WEATHER_COLUMN_ALIASES = {
    "date": ("date", "time", "일시", "일자", "날짜", "관측일자"),
    "mean_temp_c": (
        "mean_temp_c",
        "temperature_2m_mean",
        "평균기온",
        "평균기온(℃)",
        "평균기온(°C)",
    ),
    "precip_mm": (
        "precip_mm",
        "precipitation_sum",
        "일강수량",
        "일강수량(mm)",
        "강수량",
        "강수량(mm)",
    ),
}


def normalize_bike_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize the source date and rental-count columns."""

    normalized = frame.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]

    rename_map: dict[str, str] = {}
    missing: list[str] = []
    for target, aliases in _BIKE_COLUMN_ALIASES.items():
        match = next((column for column in normalized.columns if column in aliases), None)
        if match is None:
            missing.append(aliases[1] if target == "date" else aliases[1])
        else:
            rename_map[match] = target

    if missing:
        columns = ", ".join(map(str, normalized.columns))
        missing_columns = ", ".join(missing)
        raise ValueError(
            f"필수 컬럼이 없습니다: {missing_columns}; 현재 컬럼: {columns}"
        )

    return normalized.rename(columns=rename_map)


def _normalize_columns(
    frame: pd.DataFrame, aliases: dict[str, tuple[str, ...]]
) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]

    rename_map: dict[str, str] = {}
    missing: list[str] = []
    for target, candidates in aliases.items():
        match = next(
            (column for column in normalized.columns if column in candidates), None
        )
        if match is None:
            missing.append(candidates[1] if len(candidates) > 1 else target)
        else:
            rename_map[match] = target

    if missing:
        columns = ", ".join(map(str, normalized.columns))
        missing_columns = ", ".join(missing)
        raise ValueError(
            f"필수 컬럼이 없습니다: {missing_columns}; 현재 컬럼: {columns}"
        )
    return normalized.rename(columns=rename_map)


def normalize_weather_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize weather export columns to date, temperature, and precipitation."""

    return _normalize_columns(frame, _WEATHER_COLUMN_ALIASES)


def _empty_daily_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "rental_count": pd.Series(dtype="float64"),
        }
    )


def read_source_csv(path: Path) -> pd.DataFrame:
    """Read UTF-8 or Korean legacy-encoded source CSV files."""

    decode_errors: list[UnicodeDecodeError] = []
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False)
        except UnicodeDecodeError as error:
            decode_errors.append(error)
    raise decode_errors[-1]


def aggregate_bike_files(
    paths: Sequence[Path], start: str, end: str
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Read source files and aggregate valid rental counts by calendar date."""

    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()
    if start_ts > end_ts:
        raise ValueError("start must be earlier than or equal to end")

    audit = {
        "files_read": 0,
        "rows_read": 0,
        "duplicate_rows": 0,
        "invalid_date_rows": 0,
        "invalid_count_rows": 0,
        "negative_count_rows": 0,
        "rows_used": 0,
    }
    daily_parts: list[pd.DataFrame] = []

    for source_path in paths:
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"따릉이 원본 파일을 찾을 수 없습니다: {path}")

        raw = read_source_csv(path)
        audit["files_read"] += 1
        audit["rows_read"] += len(raw)

        deduplicated = raw.drop_duplicates(ignore_index=True)
        audit["duplicate_rows"] += len(raw) - len(deduplicated)
        normalized = normalize_bike_columns(deduplicated)

        parsed_dates = pd.to_datetime(normalized["date"], errors="coerce")
        parsed_counts = pd.to_numeric(normalized["rental_count"], errors="coerce")
        audit["invalid_date_rows"] += int(parsed_dates.isna().sum())
        audit["invalid_count_rows"] += int(parsed_counts.isna().sum())

        negative_mask = parsed_counts.notna() & parsed_counts.lt(0)
        audit["negative_count_rows"] += int(negative_mask.sum())

        valid_mask = (
            parsed_dates.notna()
            & parsed_counts.notna()
            & ~negative_mask
            & parsed_dates.dt.normalize().between(start_ts, end_ts)
        )
        if not valid_mask.any():
            continue

        part = pd.DataFrame(
            {
                "date": parsed_dates.loc[valid_mask].dt.normalize(),
                "rental_count": parsed_counts.loc[valid_mask].astype(float),
            }
        )
        audit["rows_used"] += len(part)
        daily_parts.append(
            part.groupby("date", as_index=False, sort=True)["rental_count"].sum()
        )

    if not daily_parts:
        return _empty_daily_frame(), audit

    daily = (
        pd.concat(daily_parts, ignore_index=True)
        .groupby("date", as_index=False, sort=True)["rental_count"]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )
    return daily, audit


def complete_calendar(
    daily: pd.DataFrame, start: str, end: str
) -> pd.DataFrame:
    """Add every date in the requested range and flag absent source records."""

    calendar = pd.DataFrame(
        {"date": pd.date_range(start=start, end=end, freq="D")}
    )
    prepared = daily.copy()
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce").dt.normalize()
    prepared = prepared.dropna(subset=["date"])
    if prepared["date"].duplicated().any():
        prepared = prepared.groupby("date", as_index=False, sort=True)["rental_count"].sum()

    completed = calendar.merge(prepared, on="date", how="left", validate="one_to_one")
    completed["record_missing"] = completed["rental_count"].isna()
    return completed


def merge_weather(daily: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Left join normalized weather observations onto the bike date series."""

    bike = daily.copy()
    bike["date"] = pd.to_datetime(bike["date"], errors="coerce").dt.normalize()

    observations = weather.copy()
    observations["date"] = pd.to_datetime(
        observations["date"], errors="coerce"
    ).dt.normalize()
    observations["mean_temp_c"] = pd.to_numeric(
        observations["mean_temp_c"], errors="coerce"
    )
    observations["precip_mm"] = pd.to_numeric(
        observations["precip_mm"], errors="coerce"
    )
    observations = observations.dropna(subset=["date"])
    observations = observations.groupby("date", as_index=False, sort=True).agg(
        mean_temp_c=("mean_temp_c", "mean"),
        precip_mm=("precip_mm", "mean"),
    )

    return bike.merge(observations, on="date", how="left", validate="one_to_one")


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add calendar, rolling, weather, and change-rate features."""

    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result = result.sort_values("date").reset_index(drop=True)
    counts = pd.to_numeric(result["rental_count"], errors="coerce")

    result["rolling_7d"] = counts.rolling(window=7, min_periods=7).mean()
    result["pct_change"] = counts.pct_change()
    result["rolling_std_7d"] = counts.rolling(window=7, min_periods=7).std()
    result["weekday"] = result["date"].dt.weekday
    weekday_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    result["weekday_name"] = result["weekday"].map(
        dict(enumerate(weekday_names))
    )
    result["month"] = result["date"].dt.month

    if "precip_mm" in result:
        result["rain_flag"] = result["precip_mm"].map(
            lambda value: pd.NA if pd.isna(value) else bool(value > 0)
        ).astype("boolean")
    else:
        result["rain_flag"] = pd.Series(pd.NA, index=result.index, dtype="boolean")

    if "mean_temp_c" in result:
        temperature = pd.to_numeric(result["mean_temp_c"], errors="coerce")
        result["temperature_bin"] = pd.cut(
            temperature,
            bins=[-float("inf"), 0, 10, 20, 30, float("inf")],
            labels=["<=0", "0~10", "10~20", "20~30", ">30"],
            include_lowest=True,
        )
    else:
        result["temperature_bin"] = pd.Categorical(
            [pd.NA] * len(result), categories=["<=0", "0~10", "10~20", "20~30", ">30"]
        )
    return result


def flag_outliers(frame: pd.DataFrame, threshold: float = 3.5) -> pd.DataFrame:
    """Flag robust outliers without removing any input rows."""

    result = frame.copy()
    values = pd.to_numeric(result["rental_count"], errors="coerce")
    median = values.median()
    deviations = (values - median).abs()
    mad = deviations.median()

    if pd.notna(mad) and mad > 0:
        robust_z = 0.6745 * (values - median) / mad
        flags = robust_z.abs().gt(threshold)
    else:
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1
        if pd.notna(iqr) and iqr > 0:
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            flags = values.lt(lower) | values.gt(upper)
        else:
            flags = values.ne(median)

    result["outlier_flag"] = flags.fillna(False).astype(bool)
    return result


def _date_string(value: object) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _numeric_dict(series: pd.Series) -> dict[str, float]:
    values = series.dropna()
    return {str(key): float(value) for key, value in values.items()}


def summarize_analysis(frame: pd.DataFrame) -> dict[str, object]:
    """Return JSON-serializable summary statistics for the analysis frame."""

    dates = pd.to_datetime(frame["date"], errors="coerce")
    counts = pd.to_numeric(frame["rental_count"], errors="coerce")
    summary: dict[str, object] = {
        "start_date": _date_string(dates.min()),
        "end_date": _date_string(dates.max()),
        "point_count": int(len(frame)),
        "valid_rental_count": int(counts.notna().sum()),
        "record_missing_count": int(
            frame.get("record_missing", pd.Series(False, index=frame.index))
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "outlier_count": int(
            frame.get("outlier_flag", pd.Series(False, index=frame.index))
            .fillna(False)
            .astype(bool)
            .sum()
        ),
    }

    if {"mean_temp_c", "precip_mm"}.issubset(frame.columns):
        summary["weather_missing_count"] = int(
            frame[["mean_temp_c", "precip_mm"]].isna().any(axis=1).sum()
        )
    else:
        summary["weather_missing_count"] = int(len(frame))

    working = pd.DataFrame(
        {
            "date": dates,
            "rental_count": counts,
        }
    ).dropna(subset=["date", "rental_count"])
    working["month"] = working["date"].dt.month
    working["weekday"] = working["date"].dt.weekday
    summary["monthly_mean"] = _numeric_dict(
        working.groupby("month")["rental_count"].mean()
    )
    summary["weekday_mean"] = _numeric_dict(
        working.groupby("weekday")["rental_count"].mean()
    )

    if "rain_flag" in frame.columns:
        rain_frame = pd.DataFrame(
            {"rental_count": counts, "rain_flag": frame["rain_flag"]}
        ).dropna()
        summary["rain_comparison"] = _numeric_dict(
            rain_frame.groupby("rain_flag")["rental_count"].mean()
        )
    else:
        summary["rain_comparison"] = {}

    for column in ("mean_temp_c", "precip_mm"):
        if column in frame.columns:
            valid = pd.DataFrame({column: frame[column], "rental_count": counts}).dropna()
            correlation = valid[column].corr(valid["rental_count"], method="spearman")
            summary[f"spearman_{column}_rental"] = (
                None if pd.isna(correlation) else float(correlation)
            )
        else:
            summary[f"spearman_{column}_rental"] = None

    return summary


def _add_source_footer(fig: plt.Figure) -> None:
    fig.text(
        0.01,
        0.01,
        "Sources: Seoul public bike usage data; Open-Meteo weather when available",
        ha="left",
        va="bottom",
        fontsize=8,
        color="dimgray",
    )


def _save_figure(fig: plt.Figure, path: Path) -> Path:
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def _plot_daily_trend(frame: pd.DataFrame, output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(12, 5))
    dates = pd.to_datetime(frame["date"], errors="coerce")
    counts = pd.to_numeric(frame["rental_count"], errors="coerce")
    ax.plot(dates, counts, color="#9aa6b2", linewidth=0.8, label="Daily rentals")
    rolling = frame.get("rolling_7d", counts.rolling(7, min_periods=7).mean())
    ax.plot(dates, rolling, color="#1565c0", linewidth=2, label="7-day moving average")
    ax.set_title("Seoul public bike daily rentals and 7-day moving average")
    ax.set_xlabel("Date")
    ax.set_ylabel("Rental count")
    ax.legend()
    ax.grid(alpha=0.2)
    fig.autofmt_xdate()
    _add_source_footer(fig)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    return _save_figure(fig, output_dir / "01_daily_trend.png")


def _plot_seasonality_heatmap(frame: pd.DataFrame, output_dir: Path) -> Path:
    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working["rental_count"] = pd.to_numeric(working["rental_count"], errors="coerce")
    working["month"] = working["date"].dt.month
    working["weekday"] = working["date"].dt.weekday
    pivot = working.pivot_table(
        index="month",
        columns="weekday",
        values="rental_count",
        aggfunc="mean",
    ).reindex(index=range(1, 13), columns=range(7))

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(pivot, cmap="YlGnBu", annot=False, linewidths=0.3, ax=ax)
    ax.set_title("Mean bike rentals by month and weekday")
    ax.set_xlabel("Weekday (Monday=0)")
    ax.set_ylabel("Month")
    _add_source_footer(fig)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    return _save_figure(fig, output_dir / "02_month_weekday_heatmap.png")


def _plot_weather_effect(frame: pd.DataFrame, output_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    weather_available = {"rental_count", "rain_flag", "temperature_bin"}.issubset(
        frame.columns
    )

    if weather_available:
        weather_frame = frame[["rental_count", "rain_flag", "temperature_bin"]].copy()
        weather_frame["rental_count"] = pd.to_numeric(
            weather_frame["rental_count"], errors="coerce"
        )
        rain_frame = weather_frame.dropna(subset=["rental_count", "rain_flag"])
        temp_frame = weather_frame.dropna(subset=["rental_count", "temperature_bin"])

        if not rain_frame.empty:
            sns.boxplot(
                data=rain_frame,
                x="rain_flag",
                y="rental_count",
                ax=axes[0],
                color="#90caf9",
            )
            axes[0].set_xlabel("Rain flag (False = no rain)")
            axes[0].set_ylabel("Rental count")
        else:
            axes[0].text(0.5, 0.5, "No valid precipitation data", ha="center", va="center")
            axes[0].set_axis_off()

        if not temp_frame.empty:
            order = ["<=0", "0~10", "10~20", "20~30", ">30"]
            sns.boxplot(
                data=temp_frame,
                x="temperature_bin",
                y="rental_count",
                order=order,
                ax=axes[1],
                color="#ffcc80",
            )
            axes[1].set_xlabel("Mean temperature bin (C)")
            axes[1].set_ylabel("Rental count")
            axes[1].tick_params(axis="x", rotation=20)
        else:
            axes[1].text(0.5, 0.5, "No valid temperature data", ha="center", va="center")
            axes[1].set_axis_off()
    else:
        for axis in axes:
            axis.text(0.5, 0.5, "No weather data", ha="center", va="center")
            axis.set_axis_off()

    fig.suptitle("Bike rentals by weather condition")
    _add_source_footer(fig)
    fig.tight_layout(rect=[0, 0.04, 1, 0.94])
    return _save_figure(fig, output_dir / "03_weather_effect.png")


def _plot_stl(frame: pd.DataFrame, output_dir: Path) -> Path | None:
    if STL is None:
        print("STL skipped: statsmodels is not installed")
        return None

    series = frame[["date", "rental_count"]].copy()
    series["date"] = pd.to_datetime(series["date"], errors="coerce")
    series["rental_count"] = pd.to_numeric(series["rental_count"], errors="coerce")
    series = series.dropna().drop_duplicates("date").sort_values("date")
    if len(series) < 14:
        print("STL skipped: at least 14 valid daily observations are required")
        return None

    indexed = series.set_index("date")["rental_count"].asfreq("D")
    indexed = indexed.interpolate(limit_direction="both")
    result = STL(indexed, period=7, robust=True).fit()
    components = {
        "Observed": result.observed,
        "Trend": result.trend,
        "Weekly seasonality": result.seasonal,
        "Residual": result.resid,
    }
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    for axis, (label, values) in zip(axes, components.items()):
        axis.plot(values.index, values.values, linewidth=0.8)
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    axes[-1].set_xlabel("Date")
    fig.suptitle("STL decomposition of daily bike rentals (weekly period)")
    _add_source_footer(fig)
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    return _save_figure(fig, output_dir / "04_stl_decomposition.png")


def make_plots(
    frame: pd.DataFrame, output_dir: Path, include_stl: bool = True
) -> list[Path]:
    """Create required analysis charts and return the generated paths."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    paths = [
        _plot_daily_trend(frame, output_path),
        _plot_seasonality_heatmap(frame, output_path),
        _plot_weather_effect(frame, output_path),
    ]
    if include_stl:
        stl_path = _plot_stl(frame, output_path)
        if stl_path is not None:
            paths.append(stl_path)
    return paths
