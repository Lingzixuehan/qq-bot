import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("steam_store_api", Path(__file__).parent / "plugins/steam/steam_store_api.py")
steam_store_api = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(steam_store_api)
_parse_low_timestamp = steam_store_api._parse_low_timestamp


@pytest.mark.parametrize(
    "timestamp, expected",
    [
        ("2024-10-01T15:25:52+02:00", "2024-10-01"),
        (1725100800000, "2024-08-31"),  # 毫秒级时间戳
        ("2024-09-15", "2024-09-15"),
    ],
)
def test_parse_low_timestamp(timestamp, expected):
    assert _parse_low_timestamp(timestamp) == expected
