from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

D = Decimal
ZERO = D("0")
POINTS_QUANT = D("0.0001")


def to_decimal(value: Any, field: str = "value") -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return D("1") if value else ZERO
    if value is None:
        raise ValueError(f"{field} 不能为空")
    try:
        return D(str(value))
    except Exception as exc:  # noqa: BLE001 - 统一转成可读错误
        raise ValueError(f"{field} 不是有效数字: {value!r}") from exc


def quantize_points(value: Any) -> Decimal:
    return to_decimal(value).quantize(POINTS_QUANT, rounding=ROUND_HALF_UP)


def points_to_1e4(value: Any) -> int:
    return int((to_decimal(value) * D("10000")).quantize(D("1"), rounding=ROUND_HALF_UP))


def points_from_1e4(value: int | str) -> Decimal:
    return D(int(value)) / D("10000")


def format_points(value: Any) -> str:
    text = format(quantize_points(value), "f").rstrip("0").rstrip(".")
    return text or "0"
