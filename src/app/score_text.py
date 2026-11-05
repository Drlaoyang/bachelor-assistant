from __future__ import annotations

from core.models import ScoreResult
from core.points import format_score
from core.rules import RuleSet


def _category_id(rules: RuleSet, rule_node_id: str) -> str | None:
    node = rules.get(rule_node_id)
    while node.parent_id:
        if node.parent_id == rules.root_id:
            return node.id
        node = rules.get(node.parent_id)
    return None


def _remaining(result: ScoreResult, node_id: str):
    node = result.find(node_id)
    return node.remaining if node and node.remaining is not None else None


def _full_ancestor(rules: RuleSet, result: ScoreResult, rule_node_id: str):
    node = rules.get(rule_node_id)
    while node.parent_id:
        node = rules.get(node.parent_id)
        if node.cap is None:
            continue
        remaining = _remaining(result, node.id)
        if remaining is not None and remaining == 0:
            return node
    return None


def _candidate_reason(result: ScoreResult, candidate_uuid: str) -> str | None:
    for node in result.root.walk():
        for item in node.activity_scores:
            if item.activity.uuid == candidate_uuid:
                return item.reason
    return None


def describe_gain(
    rules: RuleSet,
    result: ScoreResult,
    candidate_uuid: str,
    rule_node_id: str,
    base,
    current_total,
) -> str:
    gain = result.total - current_total
    reason = _candidate_reason(result, candidate_uuid)

    if gain < 0:
        return (
            f"本项应得 {format_score(base)} 分；修改后总分减少 "
            f"{format_score(-gain)} 分。"
        )

    if gain == 0:
        if reason and ("取最高" in reason or "限项" in reason):
            clean = reason.replace("，未计入", "").replace("未计入", "")
            return f"本项未计入：{clean}。"
        category_id = _category_id(rules, rule_node_id)
        category = rules.get(category_id) if category_id else None
        category_remaining = _remaining(result, category_id) if category_id else None
        if category and category_remaining == 0:
            others = [
                child
                for child in rules.children_of(rules.root_id)
                if child.id != category_id
            ]
            rooms = [
                child.name for child in others if (_remaining(result, child.id) or 0) > 0
            ]
            suffix = "其他分类仍可加分。" if rooms else "所有分类都已加满。"
            return f"「{category.name}」已加满；{suffix}"
        failing = _full_ancestor(rules, result, rule_node_id)
        if failing:
            room_siblings = []
            for sibling in rules.children_of(failing.parent_id):
                if sibling.id == failing.id or sibling.cap is None:
                    continue
                remaining = _remaining(result, sibling.id)
                if remaining is not None and remaining > 0:
                    room_siblings.append(
                        f"{sibling.name}还可加 {format_score(remaining)} 分"
                    )
            suffix = "；".join(room_siblings[:2]) if room_siblings else "本项不再加分。"
            return f"所属的「{failing.name}」已加满；{suffix}"
        return f"本项应得 {format_score(base)} 分，但实际不再增加总分。"

    if gain > base:
        return (
            f"本项应得 {format_score(base)} 分；同时计入基础参与分，"
            f"实际增加 {format_score(gain)} 分。"
            f"加入后总分 {format_score(result.total)} 分。"
        )

    if gain < base:
        return (
            f"本项应得 {format_score(base)} 分；受上限或取最高影响，"
            f"实际增加 {format_score(gain)} 分。"
            f"加入后总分 {format_score(result.total)} 分。"
        )

    return (
        f"本项应得 {format_score(base)} 分，实际增加 {format_score(gain)} 分。"
        f"加入后总分 {format_score(result.total)} 分。"
    )
