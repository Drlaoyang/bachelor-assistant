from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from .errors import CalculationError
from .points import ZERO, D, to_decimal

Params = dict[str, Any]
Inputs = dict[str, Any]
Calculator = Callable[[Params, Inputs], Decimal]


def _value(inputs: Inputs, key: str, required: bool = True, default: Any = None) -> Any:
    if key in inputs and inputs[key] is not None:
        return inputs[key]
    if required:
        raise CalculationError(f"缺少输入字段: {key}")
    return default


def _decimal(value: Any, field: str) -> Decimal:
    try:
        return to_decimal(value, field)
    except ValueError as exc:
        raise CalculationError(str(exc)) from exc


def _int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise CalculationError(f"字段 {field} 必须是整数: {value!r}") from exc


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "是"}
    return bool(value)


def _compare(actual: Decimal, op: str, threshold: Decimal) -> bool:
    if op == "gt":
        return actual > threshold
    if op == "gte":
        return actual >= threshold
    if op == "lt":
        return actual < threshold
    if op == "lte":
        return actual <= threshold
    if op == "eq":
        return actual == threshold
    raise CalculationError(f"不支持的门槛比较符: {op}")


def _lookup(table: Any, keys: list[Any], default: Any = 0) -> Decimal:
    current = table
    for key in keys:
        if not isinstance(current, dict):
            return _decimal(default, "default")
        if key in current:
            current = current[key]
        elif str(key) in current:
            current = current[str(key)]
        else:
            return _decimal(default, "default")
    if isinstance(current, dict):
        return _decimal(default, "default")
    return _decimal(current, "table")


def calc_per_occurrence(params: Params, inputs: Inputs) -> Decimal:
    return _decimal(params.get("points", 0), "points")


def calc_boolean(params: Params, inputs: Inputs) -> Decimal:
    field = str(params.get("field", "value"))
    value = _value(inputs, field, required=False, default=False)
    return _decimal(params.get("points", 0), "points") if _bool(value) else ZERO


def calc_lookup(params: Params, inputs: Inputs) -> Decimal:
    field = str(params["field"])
    value = _value(inputs, field)
    return _lookup(params["table"], [value], params.get("default", 0))


def calc_threshold(params: Params, inputs: Inputs) -> Decimal:
    field = str(params["field"])
    actual = _decimal(_value(inputs, field), field)
    threshold = _decimal(params["threshold"], "threshold")
    if _compare(actual, str(params.get("op", "gte")), threshold):
        return _decimal(params.get("points", 0), "points")
    return ZERO


def calc_matrix(params: Params, inputs: Inputs) -> Decimal:
    dimensions = params["dimensions"]
    values = [_value(inputs, str(dimension)) for dimension in dimensions]
    return _lookup(params["table"], values, params.get("default", 0))


def calc_gated_matrix(params: Params, inputs: Inputs) -> Decimal:
    gate_field = str(params["gate_field"])
    actual = _decimal(_value(inputs, gate_field), gate_field)
    if not _compare(
        actual,
        str(params.get("gate_op", "gte")),
        _decimal(params["gate_value"], "gate_value"),
    ):
        return ZERO
    return calc_matrix(params, inputs)


def calc_tiered_award(params: Params, inputs: Inputs) -> Decimal:
    region = str(_value(inputs, "region"))
    track = str(_value(inputs, "track"))
    result_type = str(_value(inputs, "result_type", required=False, default="rank"))
    result = str(_value(inputs, "result", required=False, default="other"))
    rank_number = inputs.get("rank_number")

    if result_type == "rank" and rank_number not in (None, ""):
        rank = _int(rank_number, "rank_number")
        level = None
        for item in params.get("rank_number_mapping", []):
            if rank <= _int(item["max"], "rank_number_mapping.max"):
                level = str(item["level"])
                break
        if level is None:
            return ZERO
    else:
        mapping_key = "rank_mapping" if result_type == "rank" else "prize_mapping"
        level = params.get(mapping_key, {}).get(result)
        if level is None:
            return ZERO

    points = _lookup(params["table"], [region, track, level], params.get("default", 0))
    if _bool(inputs.get("fun", False)):
        modifier = _decimal(params.get("modifiers", {}).get("fun", 1), "modifier")
        points *= modifier
    return points


def calc_competition(params: Params, inputs: Inputs) -> Decimal:
    competition_class = str(_value(inputs, "competition_class"))
    award = str(_value(inputs, "award"))
    team_size = _int(_value(inputs, "team_size", required=False, default=1), "team_size")
    threshold = _int(params.get("team_size_threshold", 3), "team_size_threshold")
    rank_value = _value(inputs, "undergraduate_rank", required=False, default=None)
    if rank_value is None:
        if team_size > threshold:
            raise CalculationError("团队人数超过 3 人时必须填写本科生位次")
        rank = 1
    else:
        rank = _int(rank_value, "undergraduate_rank")

    divisors = params["class_divisors"]
    if competition_class not in divisors:
        raise CalculationError(f"未知竞赛类别: {competition_class}")

    limit = params.get("rank_limits", {}).get(competition_class)
    if limit is not None and rank > _int(limit, "rank_limits"):
        return ZERO

    base_table = params["base_table"]
    if award not in base_table:
        raise CalculationError(f"未知获奖等级: {award}")
    row = base_table[award]
    if not isinstance(row, list) or not row:
        raise CalculationError(f"竞赛基础分值表格式错误: {award}")

    if team_size <= threshold:
        column = 0
    elif rank <= 3:
        column = 1
    elif rank <= 5:
        column = 2
    elif rank <= 7:
        column = 3
    elif rank <= 9:
        column = 4
    else:
        column = 5
    if column >= len(row):
        return ZERO

    base = _decimal(row[column], "competition.base")
    divisor = _decimal(divisors[competition_class], "class_divisor")
    if divisor == 0:
        raise CalculationError(f"竞赛类别系数不能为 0: {competition_class}")
    return base / divisor


def calc_breakthrough_competition(params: Params, inputs: Inputs) -> Decimal:
    if not _bool(_value(inputs, "is_main_member", required=False, default=False)):
        return ZERO
    competition_class = str(_value(inputs, "competition_class"))
    award = str(_value(inputs, "award"))
    table = params.get("awards", {}).get(competition_class, {})
    return _decimal(table.get(award, params.get("default", 0)), "breakthrough_competition")


def calc_research_defense(params: Params, inputs: Inputs) -> Decimal:
    score = _decimal(_value(inputs, "score"), "score")
    max_score = _decimal(params.get("max_score", 40), "max_score")
    if score < 0 or score > max_score:
        raise CalculationError(f"答辩分数必须在 0 至 {max_score} 之间")
    co_first_count = _int(
        _value(inputs, "co_first_count", required=False, default=1),
        "co_first_count",
    )
    if co_first_count < 1:
        raise CalculationError("共同第一作者人数必须大于等于 1")
    return score / D(co_first_count)


def calc_internship(params: Params, inputs: Inputs) -> Decimal:
    region = str(_value(inputs, "region"))
    months = _decimal(_value(inputs, "months"), "months")
    online = _bool(_value(inputs, "online", required=False, default=False))

    if region == "overseas":
        points = _decimal(params.get("overseas_3m", 40), "overseas_3m") if months >= 3 else ZERO
    elif region == "domestic":
        if months >= 6:
            points = _decimal(params.get("domestic_6m", 32), "domestic_6m")
        elif months >= 3:
            points = _decimal(params.get("domestic_3m", 24), "domestic_3m")
        else:
            points = ZERO
    else:
        raise CalculationError(f"未知实习地区: {region}")

    if online:
        points = max(ZERO, points - _decimal(params.get("online_penalty", 8), "online_penalty"))
    return points


def calc_literature(params: Params, inputs: Inputs) -> Decimal:
    platform = str(_value(inputs, "platform"))
    article_index = _int(_value(inputs, "article_index"), "article_index")
    is_staff = _bool(_value(inputs, "is_staff", required=False, default=False))
    if article_index < 1:
        raise CalculationError("文章序号必须大于等于 1")
    if is_staff and article_index <= _int(params.get("staff_min_count", 5), "staff_min_count"):
        return ZERO
    return _decimal(params.get("platform_points", {}).get(platform, 0), "platform_points")


def calc_team_award(params: Params, inputs: Inputs) -> Decimal:
    region = str(_value(inputs, "region"))
    award = str(_value(inputs, "award"))
    position = _int(_value(inputs, "position", required=False, default=1), "position")
    base = _lookup(params["base_table"], [region, award], params.get("default", 0))
    if base == 0:
        return ZERO
    decrement = _decimal(params.get("decrement", 0), "decrement")
    points = base - decrement * D(max(0, position - 1))
    return max(ZERO, points)


def calc_paper(params: Params, inputs: Inputs) -> Decimal:
    journal_level = str(_value(inputs, "journal_level"))
    author_role = str(_value(inputs, "author_role"))
    co_first_count = _int(
        _value(inputs, "co_first_count", required=False, default=1),
        "co_first_count",
    )
    if co_first_count < 1:
        raise CalculationError("共同第一作者人数必须大于等于 1")

    max_points = _decimal(params.get("max_points", 5), "max_points")
    if journal_level == "core":
        if author_role == "first":
            return _decimal(params.get("core_first_points", 5), "core_first_points")
        if author_role == "co_first":
            total = _decimal(params.get("core_cofirst_total", 5), "core_cofirst_total")
            return total / D(co_first_count)
        return ZERO

    if author_role in {"first", "co_first"}:
        points = _decimal(
            _value(inputs, "manual_points", required=False, default=max_points),
            "manual_points",
        )
        return max(ZERO, min(points, max_points))
    return ZERO


def calc_entrepreneurship(params: Params, inputs: Inputs) -> Decimal:
    role = str(_value(inputs, "role"))
    months = _decimal(_value(inputs, "months"), "months")
    equity = _decimal(_value(inputs, "equity"), "equity")
    profitable = _bool(_value(inputs, "profitable", required=False, default=False))

    full_months = _decimal(params.get("full_months", 12), "full_months")
    half_months = _decimal(params.get("half_months", 6), "half_months")
    legal_min = _decimal(params.get("legal_rep_min_equity", 30), "legal_rep_min_equity")
    shareholder_min = _decimal(
        params.get("shareholder_min_equity", 10),
        "shareholder_min_equity",
    )

    if role == "legal_rep":
        if equity < legal_min:
            return ZERO
        if months >= full_months:
            if profitable:
                return _decimal(
                    params.get("legal_rep_points_full", 4),
                    "legal_rep_points_full",
                )
            return ZERO
        if months >= half_months:
            return _decimal(params.get("legal_rep_points_half", 2), "legal_rep_points_half")
        return ZERO

    if role == "shareholder":
        if months >= full_months and profitable and equity >= shareholder_min:
            return _decimal(params.get("shareholder_points", 1), "shareholder_points")
        return ZERO

    raise CalculationError(f"未知创业角色: {role}")


def calc_overseas(params: Params, inputs: Inputs) -> Decimal:
    days = _decimal(_value(inputs, "duration_days"), "duration_days")
    long_days = _decimal(params.get("long_days", 90), "long_days")
    max_points = _decimal(
        params.get("long_max", 5) if days > long_days else params.get("short_max", 3),
        "max_points",
    )
    raw_points = _value(inputs, "points", required=False, default=None)
    if raw_points is None:
        return max_points
    return max(ZERO, min(_decimal(raw_points, "points"), max_points))


def calc_manual(params: Params, inputs: Inputs) -> Decimal:
    points = _decimal(_value(inputs, "points"), "points")
    max_points = params.get("max_points")
    if max_points is not None:
        points = min(points, _decimal(max_points, "max_points"))
    return max(ZERO, points)


CALCULATORS: dict[str, Calculator] = {
    "per_occurrence": calc_per_occurrence,
    "boolean": calc_boolean,
    "lookup": calc_lookup,
    "threshold": calc_threshold,
    "matrix": calc_matrix,
    "gated_matrix": calc_gated_matrix,
    "tiered_award": calc_tiered_award,
    "competition": calc_competition,
    "breakthrough_competition": calc_breakthrough_competition,
    "research_defense": calc_research_defense,
    "internship": calc_internship,
    "literature": calc_literature,
    "team_award": calc_team_award,
    "paper": calc_paper,
    "entrepreneurship": calc_entrepreneurship,
    "overseas": calc_overseas,
    "manual": calc_manual,
}


def calculate(calculator: str, params: Params, inputs: Inputs) -> Decimal:
    try:
        func = CALCULATORS[calculator]
    except KeyError as exc:
        raise CalculationError(f"未知计算器: {calculator}") from exc
    return func(params, inputs)
