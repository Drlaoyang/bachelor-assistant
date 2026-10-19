from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .calculators import CALCULATORS
from .errors import RuleError
from .models import RuleNode
from .points import to_decimal

ALLOWED_AGGREGATIONS = {"sum", "highest", "top_n"}


def _optional_decimal(value: Any, field: str) -> Any:
    if value is None:
        return None
    try:
        return to_decimal(value, field)
    except ValueError as exc:
        raise RuleError(str(exc)) from exc


class RuleSet:
    def __init__(self, data: dict[str, Any]):
        self.raw = data
        self.version = str(data.get("version", ""))
        self.name = str(data.get("name", ""))
        self.total_cap = _optional_decimal(data.get("total_cap"), "total_cap")
        self.nodes: dict[str, RuleNode] = {}
        self.children: dict[str, list[str]] = defaultdict(list)
        self.root_id: str | None = None

        for raw_node in data.get("nodes", []):
            try:
                node_id = str(raw_node["id"])
                name = str(raw_node["name"])
            except KeyError as exc:
                raise RuleError(f"规则节点缺少字段: {exc}") from exc
            if node_id in self.nodes:
                raise RuleError(f"规则节点 ID 重复: {node_id}")
            max_count = raw_node.get("max_count")
            if max_count is not None:
                try:
                    max_count = int(max_count)
                except (TypeError, ValueError) as exc:
                    raise RuleError(f"节点 {node_id} 的 max_count 不是整数") from exc
            node = RuleNode(
                id=node_id,
                parent_id=raw_node.get("parent"),
                name=name,
                level=str(raw_node.get("level", "")),
                cap=_optional_decimal(raw_node.get("cap"), f"{node_id}.cap"),
                aggregation=str(raw_node.get("aggregation", "sum")),
                max_count=max_count,
                dedupe_by=raw_node.get("dedupe_by"),
                calculator=raw_node.get("calculator"),
                params=raw_node.get("params") or {},
                source_ref=raw_node.get("source_ref"),
                sort=int(raw_node.get("sort", 0)),
            )
            self.nodes[node.id] = node

        for node in self.nodes.values():
            if node.parent_id is None:
                if self.root_id is not None:
                    raise RuleError("规则树存在多个根节点")
                self.root_id = node.id
            else:
                if node.parent_id not in self.nodes:
                    raise RuleError(f"节点 {node.id} 的父节点不存在: {node.parent_id}")
                self.children[node.parent_id].append(node.id)

        if self.root_id is None:
            raise RuleError("规则树没有根节点")
        for parent_id in self.children:
            self.children[parent_id].sort(key=lambda node_id: self.nodes[node_id].sort)

        self._validate()

    def get(self, node_id: str) -> RuleNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise RuleError(f"未知规则节点: {node_id}") from exc

    def children_of(self, node_id: str) -> list[RuleNode]:
        return [self.nodes[child_id] for child_id in self.children.get(node_id, [])]

    def is_leaf(self, node_id: str) -> bool:
        return not self.children.get(node_id)

    def _validate(self) -> None:
        assert self.root_id is not None
        root = self.get(self.root_id)
        if root.parent_id is not None:
            raise RuleError("根节点不能有父节点")
        if self.total_cap is not None and root.cap is not None and root.cap != self.total_cap:
            raise RuleError(f"根节点上限 {root.cap} 与 total_cap {self.total_cap} 不一致")

        visited: set[str] = set()

        def visit(node_id: str, path: set[str]) -> None:
            if node_id in path:
                raise RuleError(f"规则树存在环: {node_id}")
            if node_id in visited:
                return
            path.add(node_id)
            node = self.get(node_id)
            children = self.children.get(node_id, [])
            if children:
                if node.calculator:
                    raise RuleError(f"内部节点 {node.id} 不能同时定义 calculator")
                aggregation = node.aggregation
                if aggregation not in ALLOWED_AGGREGATIONS:
                    raise RuleError(f"节点 {node.id} 的 aggregation 非法: {aggregation}")
                if aggregation == "top_n":
                    if node.max_count is None or node.max_count < 1:
                        raise RuleError(f"节点 {node.id} 使用 top_n 时必须设置 max_count >= 1")
                    if node.dedupe_by is not None and not node.dedupe_by:
                        raise RuleError(f"节点 {node.id} 的 dedupe_by 不能为空")
                elif aggregation == "highest":
                    if node.max_count not in (None, 1):
                        raise RuleError(f"节点 {node.id} 使用 highest 时 max_count 只能为空或 1")
                    if node.dedupe_by:
                        raise RuleError(f"节点 {node.id} 不能对 highest 使用 dedupe_by")
                else:
                    if node.max_count is not None:
                        raise RuleError(f"节点 {node.id} 使用 sum 时不能设置 max_count")
                    if node.dedupe_by:
                        raise RuleError(f"节点 {node.id} 使用 sum 时不能设置 dedupe_by")
                if aggregation in {"highest", "top_n"}:
                    non_leaf_children = [child for child in children if not self.is_leaf(child)]
                    if non_leaf_children:
                        raise RuleError(
                            f"节点 {node.id} 使用 {aggregation} 时子节点必须都是叶子: "
                            f"{', '.join(non_leaf_children)}"
                        )
            else:
                if not node.calculator:
                    raise RuleError(f"叶子节点 {node.id} 缺少 calculator")
                if node.calculator not in CALCULATORS:
                    raise RuleError(f"节点 {node.id} 使用未知计算器: {node.calculator}")
                if node.cap is not None:
                    raise RuleError(f"叶子节点 {node.id} 不直接设置 cap，请放到父节点")
                if node.aggregation != "sum":
                    raise RuleError(f"叶子节点 {node.id} 的 aggregation 必须为 sum")

            if node.cap is not None and node.cap < 0:
                raise RuleError(f"节点 {node.id} 的 cap 不能为负数")

            for child in children:
                visit(child, path)
            path.remove(node_id)
            visited.add(node_id)

        visit(self.root_id, set())
        if len(visited) != len(self.nodes):
            unreachable = sorted(set(self.nodes) - visited)
            raise RuleError(f"存在从根节点不可达的规则节点: {', '.join(unreachable)}")

    def summary(self) -> list[dict[str, Any]]:
        rows = []
        for node in self.nodes.values():
            if node.level in {"root", "category", "section"}:
                rows.append(
                    {
                        "id": node.id,
                        "name": node.name,
                        "level": node.level,
                        "cap": node.cap,
                        "aggregation": node.aggregation,
                    }
                )
        return rows


def load_rules(path: str | Path) -> RuleSet:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - 仅在缺少开发依赖时触发
            raise RuleError("读取 YAML 需要安装 PyYAML；运行时请使用生成的 JSON") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise RuleError("规则文件顶层必须是对象")
    return RuleSet(data)
