from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class RuleNode:
    id: str
    parent_id: str | None
    name: str
    level: str
    cap: Decimal | None
    aggregation: str
    max_count: int | None
    dedupe_by: str | None
    calculator: str | None
    params: dict[str, Any]
    source_ref: str | None
    sort: int = 0


@dataclass
class Activity:
    uuid: str
    rule_node_id: str
    title: str
    status: str = "confirmed"
    inputs: dict[str, Any] = field(default_factory=dict)
    override_points: Decimal | None = None
    override_reason: str | None = None
    academic_year: str | None = None
    student_id: str | None = None
    activity_date: str | None = None
    notes: str | None = None


@dataclass
class ActivityScore:
    activity: Activity
    base: Decimal
    counted: Decimal
    reason: str | None = None


@dataclass
class NodeScore:
    node_id: str
    name: str
    raw: Decimal
    counted: Decimal
    cap: Decimal | None
    overflow: Decimal
    remaining: Decimal | None
    children: list[NodeScore] = field(default_factory=list)
    activity_scores: list[ActivityScore] = field(default_factory=list)

    def walk(self) -> Iterator[NodeScore]:
        yield self
        for child in self.children:
            yield from child.walk()

    def find(self, node_id: str) -> NodeScore | None:
        if self.node_id == node_id:
            return self
        for child in self.children:
            found = child.find(node_id)
            if found is not None:
                return found
        return None


@dataclass
class ScoreResult:
    root: NodeScore
    total: Decimal
    activity_count: int

    def find(self, node_id: str) -> NodeScore | None:
        return self.root.find(node_id)

    @property
    def remaining(self) -> Decimal | None:
        return self.root.remaining
