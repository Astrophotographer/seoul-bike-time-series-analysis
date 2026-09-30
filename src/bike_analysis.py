"""Core analysis helpers for the Seoul public-bike time series."""

from pathlib import Path
from typing import Sequence

import pandas as pd


def aggregate_bike_files(
    paths: Sequence[Path], start: str, end: str
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return an empty daily result until the ingestion implementation is added."""

    return pd.DataFrame(), {}


def complete_calendar(
    daily: pd.DataFrame, start: str, end: str
) -> pd.DataFrame:
    """Return an empty calendar result until calendar completion is added."""

    return pd.DataFrame()


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return an empty feature result until feature engineering is added."""

    return pd.DataFrame()
