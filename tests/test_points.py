from __future__ import annotations

from core.points import D, format_points, points_from_1e4, points_to_1e4


def test_points_roundtrip_1e4():
    for value in ("0.3125", "1.3333", "5.25", "0.0625", "10"):
        assert points_from_1e4(points_to_1e4(value)) == D(value)


def test_format_points_trims_trailing_zeroes():
    assert format_points("5.2500") == "5.25"
    assert format_points("0.3125") == "0.3125"
    assert format_points("0") == "0"
