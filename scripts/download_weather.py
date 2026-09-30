"""Download daily Seoul weather from the Open-Meteo archive API."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_weather(
    start: str,
    end: str,
    latitude: float = 37.5665,
    longitude: float = 126.9780,
) -> list[dict[str, object]]:
    """Fetch and validate daily mean temperature and precipitation rows."""

    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start,
            "end_date": end,
            "daily": "temperature_2m_mean,precipitation_sum",
            "timezone": "Asia/Seoul",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
        }
    )
    request = Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": "seoul-bike-time-series-analysis/1.0"},
    )
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)

    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    temperatures = daily.get("temperature_2m_mean", [])
    precipitation = daily.get("precipitation_sum", [])
    if not (len(dates) == len(temperatures) == len(precipitation)):
        raise ValueError("Open-Meteo 응답의 일별 컬럼 길이가 서로 다릅니다.")

    return [
        {
            "date": date,
            "mean_temp_c": temperature,
            "precip_mm": rain,
        }
        for date, temperature, rain in zip(dates, temperatures, precipitation)
    ]


def write_weather(rows: list[dict[str, object]], output: Path) -> None:
    """Write canonical weather columns for the analysis pipeline."""

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "mean_temp_c", "precip_mm"],
        )
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download daily Seoul weather for the bike analysis."
    )
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/weather_seoul_open_meteo.csv"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rows = fetch_weather(args.start, args.end)
    write_weather(rows, args.output)
    print(f"Wrote {len(rows)} daily weather rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
