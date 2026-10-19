from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from .calculators import calculate
from .errors import RuleError
from .models import Activity, ActivityScore, NodeScore, ScoreResult
from .points import ZERO, to_decimal
from .rules import RuleSet

DEFAULT_STATUSES = ("confirmed",)
EXCLUDED_STATUSES = {"rejected"}


class Scorer:
    def __init__(self, rules: RuleSet):
        self.rules = rules
        self._activities_by_rule: dict[str, list[Activity]] = defaultdict(list)

    def score(
        self,
        activities: Iterable[Activity],
        include_statuses: Iterable[str] | None = DEFAULT_STATUSES,
    ) -> ScoreResult:
        self._activities_by_rule = defaultdict(list)
        statuses = None if include_statuses is None else set(include_statuses)
        filtered: list[Activity] = []
        for activity in activities:
            if activity.status in EXCLUDED_STATUSES:
                continue
            if statuses is not None and activity.status not in statuses:
                continue
            node = self.rules.get(activity.rule_node_id)
            if not self.rules.is_leaf(node.id):
                raise RuleError(f"活动 {activity.uuid} 关联的不是叶子规则: {activity.rule_node_id}")
            self._activities_by_rule[node.id].append(activity)
            filtered.append(activity)

        assert self.rules.root_id is not None
        root = self._score_node(self.rules.root_id)
        return ScoreResult(root=root, total=root.counted, activity_count=len(filtered))

    def marginal_gain(
        self,
        candidate: Activity,
        activities: Iterable[Activity],
        include_statuses: Iterable[str] | None = DEFAULT_STATUSES,
    ) -> Decimal:
        activities = list(activities)
        current = self.score(activities, include_statuses).total
        statuses = None if include_statuses is None else set(include_statuses)
        if statuses is not None:
            statuses.add(candidate.status)
            include_statuses = tuple(sorted(statuses))
        simulated = self.score([*activities, candidate], include_statuses).total
        return simulated - current

    def _score_node(self, node_id: str) -> NodeScore:
        node = self.rules.get(node_id)
        children = self.rules.children_of(node_id)

        if not children:
            activity_scores = [
                self._score_activity(activity, node)
                for activity in self._activities_by_rule.get(node.id, [])
            ]
            raw = sum((item.base for item in activity_scores), ZERO)
            counted, overflow, remaining = self._apply_cap(raw, node.cap)
            return NodeScore(
                node_id=node.id,
                name=node.name,
                raw=raw,
                counted=counted,
                cap=node.cap,
                overflow=overflow,
                remaining=remaining,
                activity_scores=activity_scores,
            )

        child_scores = [self._score_node(child.id) for child in children]
        if node.aggregation == "sum":
            raw = sum((child.counted for child in child_scores), ZERO)
            activity_scores = [item for child in child_scores for item in child.activity_scores]
        elif node.aggregation in {"highest", "top_n"}:
            candidates = [item for child in child_scores for item in child.activity_scores]
            selected, activity_scores = self._select(node, candidates)
            raw = sum((item.base for item in selected), ZERO)
        else:  # pragma: no cover - 由 RuleSet 校验保证
            raise RuleError(f"未知聚合方式: {node.aggregation}")

        counted, overflow, remaining = self._apply_cap(raw, node.cap)
        return NodeScore(
            node_id=node.id,
            name=node.name,
            raw=raw,
            counted=counted,
            cap=node.cap,
            overflow=overflow,
            remaining=remaining,
            children=child_scores,
            activity_scores=activity_scores,
        )

    def _score_activity(self, activity: Activity, node) -> ActivityScore:
        if activity.override_points is not None:
            base = to_decimal(activity.override_points, "override_points")
            reason = "手动调整"
            if activity.override_reason:
                reason = f"{reason}: {activity.override_reason}"
            return ActivityScore(activity=activity, base=base, counted=base, reason=reason)
        assert node.calculator is not None
        base = calculate(node.calculator, node.params, activity.inputs)
        return ActivityScore(activity=activity, base=base, counted=base)

    def _apply_cap(
        self,
        raw: Decimal,
        cap: Decimal | None,
    ) -> tuple[Decimal, Decimal, Decimal | None]:
        if cap is None:
            return raw, ZERO, None
        counted = min(raw, cap)
        overflow = max(ZERO, raw - counted)
        remaining = max(ZERO, cap - counted)
        return counted, overflow, remaining

    def _select(
        self,
        node,
        candidates: list[ActivityScore],
    ) -> tuple[list[ActivityScore], list[ActivityScore]]:
        if not candidates:
            return [], []

        selected: list[ActivityScore] = []
        counted_map: dict[str, tuple[Decimal, str | None]] = {
            item.activity.uuid: (ZERO, "未计入") for item in candidates
        }

        if node.aggregation == "highest" or node.max_count == 1:
            ordered = sorted(candidates, key=lambda item: item.base, reverse=True)
            selected = ordered[:1]
            for item in ordered[1:]:
                counted_map[item.activity.uuid] = (ZERO, "同类取最高，未计入")
        else:
            dropped_by_dedupe: list[ActivityScore] = []
            if node.dedupe_by:
                best_by_key: dict[str, ActivityScore] = {}
                for item in candidates:
                    key = str(item.activity.inputs.get(node.dedupe_by) or item.activity.uuid)
                    previous = best_by_key.get(key)
                    if previous is None:
                        best_by_key[key] = item
                    elif item.base > previous.base:
                        dropped_by_dedupe.append(previous)
                        best_by_key[key] = item
                    else:
                        dropped_by_dedupe.append(item)
                pool = list(best_by_key.values())
            else:
                pool = list(candidates)

            ordered = sorted(pool, key=lambda item: item.base, reverse=True)
            limit = node.max_count or len(ordered)
            selected = ordered[:limit]
            for item in ordered[limit:]:
                counted_map[item.activity.uuid] = (ZERO, "超过限项，未计入")
            for item in dropped_by_dedupe:
                counted_map[item.activity.uuid] = (ZERO, "同一项目取最高，未计入")

        for item in selected:
            counted_map[item.activity.uuid] = (item.base, item.reason)

        activity_scores = [
            ActivityScore(
                activity=item.activity,
                base=item.base,
                counted=counted_map[item.activity.uuid][0],
                reason=counted_map[item.activity.uuid][1],
            )
            for item in candidates
        ]
        return selected, activity_scores
