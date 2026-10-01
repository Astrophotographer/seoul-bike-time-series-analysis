"""Core analysis helpers for the Seoul public-bike time series."""

from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
import seaborn as sns
import pandas as pd

try:
    from statsmodels.tsa.seasonal import STL
except ImportError:  # pragma: no cover - depends on the local environment
    STL = None  # type: ignore[assignment,misc]


def _configure_korean_font() -> None:
    """Prefer an installed Korean font so generated chart text is readable."""

    font_paths = (
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
        Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    )
    for font_path in font_paths:
        if not font_path.exists():
            continue
        try:
            font_manager.fontManager.addfont(str(font_path))
            font_name = font_manager.FontProperties(fname=str(font_path)).get_name()
            plt.rcParams["font.family"] = font_name
            break
        except (OSError, RuntimeError):
            continue
    else:
        plt.rcParams["font.family"] = [
            "Apple SD Gothic Neo",
            "Noto Sans CJK KR",
            "Noto Sans KR",
            "Arial Unicode MS",
            "DejaVu Sans",
        ]
    plt.rcParams["axes.unicode_minus"] = False


_configure_korean_font()


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
    valid_mask = values.notna()
    if not valid_mask.any():
        result["outlier_flag"] = False
        return result

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

    result["outlier_flag"] = (flags.fillna(False) & valid_mask).astype(bool)
    return result


def _date_string(value: object) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _numeric_dict(series: pd.Series) -> dict[str, float]:
    values = series.dropna()
    return {str(key): float(value) for key, value in values.items()}


def _spearman_correlation(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns or "rental_count" not in frame.columns:
        return None

    valid = pd.DataFrame(
        {
            column: pd.to_numeric(frame[column], errors="coerce"),
            "rental_count": pd.to_numeric(frame["rental_count"], errors="coerce"),
        }
    ).dropna()
    if (
        len(valid) < 2
        or valid[column].nunique(dropna=True) < 2
        or valid["rental_count"].nunique(dropna=True) < 2
    ):
        return None

    correlation = valid[column].corr(valid["rental_count"], method="spearman")
    return None if pd.isna(correlation) else float(correlation)


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
        summary[f"spearman_{column}_rental"] = _spearman_correlation(frame, column)

    return summary


def make_baseline_forecast(
    frame: pd.DataFrame, horizon: int = 28, seasonal_period: int = 7
) -> pd.DataFrame:
    """Forecast the final horizon by repeating the last observed seasonal cycle."""

    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if seasonal_period <= 0:
        raise ValueError("seasonal_period must be positive")

    series = frame[["date", "rental_count"]].copy()
    series["date"] = pd.to_datetime(series["date"], errors="coerce")
    series["rental_count"] = pd.to_numeric(series["rental_count"], errors="coerce")
    series = (
        series.dropna()
        .drop_duplicates("date")
        .sort_values("date")
        .reset_index(drop=True)
    )
    if len(series) <= horizon or len(series) - horizon < seasonal_period:
        raise ValueError(
            "at least horizon + seasonal_period valid observations are required"
        )

    train = series.iloc[:-horizon]
    test = series.iloc[-horizon:]
    seasonal_values = train["rental_count"].to_numpy()[-seasonal_period:]
    forecast_values = [
        seasonal_values[index % seasonal_period] for index in range(horizon)
    ]
    return pd.DataFrame(
        {
            "date": test["date"].to_numpy(),
            "actual": test["rental_count"].to_numpy(),
            "forecast": forecast_values,
        }
    )


def summarize_forecast(forecast: pd.DataFrame) -> dict[str, object]:
    """Return holdout metrics for a baseline forecast table."""

    valid = forecast[["actual", "forecast"]].apply(
        pd.to_numeric, errors="coerce"
    ).dropna()
    if valid.empty:
        return {"horizon": 0, "mae": None, "mape": None}

    absolute_error = (valid["actual"] - valid["forecast"]).abs()
    nonzero_actual = valid["actual"].ne(0)
    if nonzero_actual.any():
        mape = (
            (absolute_error[nonzero_actual] / valid.loc[nonzero_actual, "actual"])
            .mul(100)
            .mean()
        )
    else:
        mape = None
    return {
        "horizon": int(len(valid)),
        "mae": float(absolute_error.mean()),
        "mape": None if pd.isna(mape) else float(mape),
    }


def _add_source_footer(fig: plt.Figure) -> None:
    fig.text(
        0.01,
        0.01,
        "출처: 서울시 따릉이 이용 데이터 · 기상 보조자료는 Open-Meteo",
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
    ax.plot(dates, counts, color="#9aa6b2", linewidth=0.8, label="일별 대여건수")
    rolling = frame.get("rolling_7d", counts.rolling(7, min_periods=7).mean())
    ax.plot(dates, rolling, color="#1565c0", linewidth=2, label="7일 이동평균")
    ax.set_title("서울시 따릉이 일별 이용량과 7일 이동평균")
    ax.set_xlabel("X축: 날짜")
    ax.set_ylabel("Y축: 일별 대여건수")
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
    ax.set_title("월·요일별 따릉이 평균 이용량")
    ax.set_xlabel("X축: 요일")
    ax.set_ylabel("Y축: 월")
    ax.set_xticklabels(["월", "화", "수", "목", "금", "토", "일"])
    ax.set_yticklabels([f"{month}월" for month in range(1, 13)], rotation=0)
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
        rain_frame = weather_frame.dropna(subset=["rental_count", "rain_flag"]).copy()
        rain_frame["rain_label"] = rain_frame["rain_flag"].map(
            {False: "비 없음", True: "비 있음"}
        )
        temp_frame = weather_frame.dropna(subset=["rental_count", "temperature_bin"])

        if not rain_frame.empty:
            sns.boxplot(
                data=rain_frame,
                x="rain_label",
                y="rental_count",
                ax=axes[0],
                color="#90caf9",
            )
            axes[0].set_xlabel("X축: 강수 여부")
            axes[0].set_ylabel("Y축: 일별 대여건수")
        else:
            axes[0].text(0.5, 0.5, "유효한 강수 데이터 없음", ha="center", va="center")
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
            axes[1].set_xlabel("X축: 평균기온 구간 (℃)")
            axes[1].set_ylabel("Y축: 일별 대여건수")
            axes[1].set_xticklabels(
                ["0℃ 이하", "0~10℃", "10~20℃", "20~30℃", "30℃ 초과"]
            )
            axes[1].tick_params(axis="x", rotation=20)
        else:
            axes[1].text(0.5, 0.5, "유효한 기온 데이터 없음", ha="center", va="center")
            axes[1].set_axis_off()
    else:
        for axis in axes:
            axis.text(0.5, 0.5, "기상 데이터 없음", ha="center", va="center")
            axis.set_axis_off()

    fig.suptitle("날씨 조건별 따릉이 이용량")
    _add_source_footer(fig)
    fig.tight_layout(rect=[0, 0.04, 1, 0.94])
    return _save_figure(fig, output_dir / "03_weather_effect.png")


def _plot_correlation(frame: pd.DataFrame, output_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    plots = (
        ("mean_temp_c", "X축: 평균기온 (℃)", "평균기온과 대여량", "#f6a64b"),
        ("precip_mm", "X축: 강수량 (mm)", "강수량과 대여량", "#4cb6c5"),
    )

    for axis, (column, xlabel, title, color) in zip(axes, plots):
        if column not in frame.columns:
            valid = pd.DataFrame()
        else:
            valid = pd.DataFrame(
                {
                    column: pd.to_numeric(frame[column], errors="coerce"),
                    "rental_count": pd.to_numeric(
                        frame["rental_count"], errors="coerce"
                    ),
                }
            ).dropna()

        if valid.empty:
            axis.text(0.5, 0.5, "유효한 기상 데이터 없음", ha="center", va="center")
            axis.set_axis_off()
            continue

        axis.scatter(
            valid[column],
            valid["rental_count"],
            alpha=0.34,
            color=color,
            edgecolors="none",
            s=24,
        )
        correlation = _spearman_correlation(frame, column)
        rho_text = "n/a" if correlation is None else f"{correlation:+.3f}"
        axis.text(
            0.04,
            0.95,
            f"스피어만 상관계수 ρ = {rho_text}",
            transform=axis.transAxes,
            va="top",
            fontsize=10,
            bbox={"facecolor": "white", "alpha": 0.82, "edgecolor": "none"},
        )
        axis.set_title(title)
        axis.set_xlabel(xlabel)
        axis.set_ylabel("Y축: 일별 대여건수")
        axis.grid(alpha=0.2)

    fig.suptitle("날씨와 일별 따릉이 이용량: 연관성과 인과관계는 다름")
    _add_source_footer(fig)
    fig.tight_layout(rect=[0, 0.04, 1, 0.94])
    return _save_figure(fig, output_dir / "05_correlation.png")


def _plot_baseline_forecast(
    frame: pd.DataFrame,
    output_dir: Path,
    horizon: int = 28,
    seasonal_period: int = 7,
) -> Path | None:
    try:
        forecast = make_baseline_forecast(
            frame, horizon=horizon, seasonal_period=seasonal_period
        )
    except ValueError as error:
        print(f"기준선 예측 생략: {error}")
        return None

    series = frame[["date", "rental_count"]].copy()
    series["date"] = pd.to_datetime(series["date"], errors="coerce")
    series["rental_count"] = pd.to_numeric(series["rental_count"], errors="coerce")
    series = (
        series.dropna()
        .drop_duplicates("date")
        .sort_values("date")
        .reset_index(drop=True)
    )
    train = series.iloc[:-horizon].tail(max(56, horizon * 2))
    metrics = summarize_forecast(forecast)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(
        train["date"],
        train["rental_count"],
        color="#9aa6b2",
        linewidth=1.1,
        label="실제값 · 학습 구간",
    )
    ax.plot(
        forecast["date"],
        forecast["actual"],
        color="#1565c0",
        linewidth=2,
        label="실제값 · 검증 구간",
    )
    ax.plot(
        forecast["date"],
        forecast["forecast"],
        color="#e67e22",
        linewidth=2,
        linestyle="--",
        marker="o",
        markersize=3,
        label="7일 계절성 기준선",
    )
    ax.axvspan(
        forecast["date"].iloc[0],
        forecast["date"].iloc[-1],
        color="#f6b85f",
        alpha=0.09,
        label="28일 검증 구간",
    )
    mape = metrics["mape"]
    mape_text = "계산 불가" if mape is None else f"{mape:.1f}%"
    metric_text = (
        f"평균절대오차(MAE) {metrics['mae']:,.0f} · "
        f"평균절대백분율오차(MAPE) {mape_text}"
    )
    ax.text(
        0.98,
        0.96,
        metric_text,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        bbox={"facecolor": "white", "alpha": 0.82, "edgecolor": "none"},
    )
    ax.set_title("28일 기준선 예측 (7일 계절성 반복)")
    ax.set_xlabel("X축: 날짜")
    ax.set_ylabel("Y축: 일별 대여건수")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.2)
    fig.autofmt_xdate()
    _add_source_footer(fig)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    return _save_figure(fig, output_dir / "06_baseline_forecast.png")


def _plot_stl(frame: pd.DataFrame, output_dir: Path) -> Path | None:
    if STL is None:
        print("STL 생략: statsmodels가 설치되지 않았습니다")
        return None

    series = frame[["date", "rental_count"]].copy()
    series["date"] = pd.to_datetime(series["date"], errors="coerce")
    series["rental_count"] = pd.to_numeric(series["rental_count"], errors="coerce")
    series = series.dropna().drop_duplicates("date").sort_values("date")
    if len(series) < 14:
        print("STL 생략: 유효한 일별 관측값이 14개 이상 필요합니다")
        return None

    indexed = series.set_index("date")["rental_count"].asfreq("D")
    indexed = indexed.interpolate(limit_direction="both")
    result = STL(indexed, period=7, robust=True).fit()
    components = {
        "관측값": result.observed,
        "추세": result.trend,
        "주간 계절성": result.seasonal,
        "잔차": result.resid,
    }
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    for axis, (label, values) in zip(axes, components.items()):
        axis.plot(values.index, values.values, linewidth=0.8)
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    axes[-1].set_xlabel("X축: 날짜")
    fig.suptitle("일별 따릉이 이용량 STL 분해 (주간 주기)")
    _add_source_footer(fig)
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    return _save_figure(fig, output_dir / "04_stl_decomposition.png")


def make_plots(
    frame: pd.DataFrame,
    output_dir: Path,
    include_stl: bool = True,
    include_forecast: bool = True,
) -> list[Path]:
    """Create required analysis charts and return the generated paths."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    paths = [
        _plot_daily_trend(frame, output_path),
        _plot_seasonality_heatmap(frame, output_path),
        _plot_weather_effect(frame, output_path),
        _plot_correlation(frame, output_path),
    ]
    if include_forecast:
        forecast_path = _plot_baseline_forecast(frame, output_path)
        if forecast_path is not None:
            paths.append(forecast_path)
    if include_stl:
        stl_path = _plot_stl(frame, output_path)
        if stl_path is not None:
            paths.append(stl_path)
    return paths
