"""Core analysis helpers for the Seoul public-bike time series."""

from pathlib import Path
from typing import Sequence

import pandas as pd


_BIKE_COLUMN_ALIASES = {
    "date": ("date", "대여일자", "대여일시"),
    "rental_count": ("rental_count", "이용건수", "이용 건수"),
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


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return an empty feature result until feature engineering is added."""

    return pd.DataFrame()
