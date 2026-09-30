from src.bike_analysis import add_features, aggregate_bike_files, complete_calendar


def test_analysis_module_exports_public_api():
    assert callable(aggregate_bike_files)
    assert callable(complete_calendar)
    assert callable(add_features)
