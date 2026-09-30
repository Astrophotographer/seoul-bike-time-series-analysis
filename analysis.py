"""Command-line pipeline for the Seoul public-bike time-series analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import pandas as pd

from src.bike_analysis import (
    add_features,
    aggregate_bike_files,
    complete_calendar,
    flag_outliers,
    make_plots,
    merge_weather,
    normalize_weather_columns,
    summarize_analysis,
)


def run_pipeline(
    bike_dir: Path,
    weather_path: Path | None,
    output_dir: Path,
    start: str,
    end: str,
) -> dict[str, object]:
    """Run ingestion, feature engineering, visualization, and output writing."""

    bike_dir = Path(bike_dir)
    output_dir = Path(output_dir)
    if not bike_dir.exists() or not bike_dir.is_dir():
        raise FileNotFoundError(f"따릉이 원본 폴더를 찾을 수 없습니다: {bike_dir}")

    bike_paths = sorted(bike_dir.glob("*.csv"))
    if not bike_paths:
        raise FileNotFoundError(f"따릉이 CSV 파일이 없습니다: {bike_dir}")

    daily, audit = aggregate_bike_files(bike_paths, start=start, end=end)
    frame = complete_calendar(daily, start=start, end=end)

    if weather_path is not None:
        weather_path = Path(weather_path)
        if not weather_path.exists():
            raise FileNotFoundError(f"기상 원본 파일을 찾을 수 없습니다: {weather_path}")
        weather_raw = pd.read_csv(weather_path, encoding="utf-8-sig", low_memory=False)
        weather = normalize_weather_columns(weather_raw)
        frame = merge_weather(frame, weather)

    frame = add_features(frame)
    frame = flag_outliers(frame)

    processed_dir = output_dir / "data"
    image_dir = output_dir / "images"
    processed_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    processed_path = processed_dir / "processed_daily_rentals.csv"
    frame.to_csv(processed_path, index=False, encoding="utf-8-sig")

    summary = summarize_analysis(frame)
    summary["ingestion_audit"] = audit
    summary["generated_plots"] = [
        str(path.relative_to(output_dir))
        for path in make_plots(frame, image_dir, include_stl=True)
    ]
    summary["processed_csv"] = str(processed_path.relative_to(output_dir))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze daily Seoul public-bike rentals from CSV files."
    )
    parser.add_argument("--bike-dir", type=Path, required=True)
    parser.add_argument("--weather", dest="weather_path", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2024-12-31")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_pipeline(
        bike_dir=args.bike_dir,
        weather_path=args.weather_path,
        output_dir=args.output_dir,
        start=args.start,
        end=args.end,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
