"""Core analysis helpers for the Seoul public-bike time series."""

from pathlib import Path
from typing import Sequence

import pandas as pd


_BIKE_COLUMN_ALIASES = {
    "date": ("date", "대여일자", "대여일시"),
    "rental_count": ("rental_count", "이용건수", "이용 건수"),
}

_WEATHER_COLUMN_ALIASES = {
    "date": ("date", "일시", "일자", "날짜", "관측일자"),
    "mean_temp_c": (
        "mean_temp_c",
        "평균기온",
        "평균기온(℃)",
        "평균기온(°C)",
    ),
    "precip_mm": (
        "precip_mm",
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

        raw = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
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
