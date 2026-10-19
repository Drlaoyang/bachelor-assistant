from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import flet as ft

from core.rules import RuleSet

LEVEL_HINT = "请选择分类 → 评价类型 → 项目"


@dataclass
class _Level:
    parent_id: str
    dropdown: ft.Dropdown
    targets: dict[str, str | None]
    next_parents: dict[str, str]
    labels: dict[str, str]


class RulePicker(ft.Column):
    """Cascading rule picker: category -> section -> project -> leaf."""

    def __init__(
        self,
        rules: RuleSet,
        on_leaf: Callable[[str | None], None],
    ):
        super().__init__(spacing=8, tight=True)
        self.rules = rules
        self.on_leaf = on_leaf
        self._leaf_id: str | None = None
        self._levels: list[_Level] = []
        self.breadcrumb = ft.Text(LEVEL_HINT, size=12, color=ft.Colors.GREY_700)
        self._levels.append(self._make_level(self.rules.root_id, 0))
        self._sync()

    @property
    def leaf_id(self) -> str | None:
        return self._leaf_id

    def _display(self, node_id: str):
        node = self.rules.get(node_id)
        if self.rules.is_leaf(node.id):
            return node
        children = self.rules.children_of(node.id)
        if len(children) == 1 and self.rules.is_leaf(children[0].id):
            return children[0]
        return node

    def _level_label(self, index: int, all_complete: bool) -> str:
        if index == 0:
            return "分类"
        if all_complete:
            return "具体项目"
        if index == 1:
            return "评价类型"
        if index == 2:
            return "项目"
        return "具体项目"

    def _make_level(self, parent_id: str, index: int) -> _Level:
        children = self.rules.children_of(parent_id)
        options = [ft.DropdownOption(key="", text="请选择…")]
        targets: dict[str, str | None] = {"": None}
        next_parents: dict[str, str] = {}
        labels = {"": "请选择…"}
        all_complete = True
        for child in children:
            display = self._display(child.id)
            target = display.id if self.rules.is_leaf(display.id) else None
            if target is None:
                all_complete = False
            options.append(ft.DropdownOption(key=child.id, text=child.name))
            targets[child.id] = target
            next_parents[child.id] = display.id
            labels[child.id] = child.name

        dropdown = ft.Dropdown(
            label=self._level_label(index, all_complete),
            options=options,
            value="",
            on_select=lambda _, i=index: self._on_select(i),
            menu_height=360,
        )
        return _Level(
            parent_id=parent_id,
            dropdown=dropdown,
            targets=targets,
            next_parents=next_parents,
            labels=labels,
        )

    def _on_select(self, index: int) -> None:
        level = self._levels[index]
        key = level.dropdown.value or ""
        self._levels = self._levels[: index + 1]
        leaf_id: str | None = None
        if key:
            target = level.targets.get(key)
            if target is not None:
                leaf_id = target
            else:
                parent = level.next_parents.get(key)
                if parent:
                    self._levels.append(self._make_level(parent, index + 1))
        self._leaf_id = leaf_id
        self._sync()
        self.on_leaf(leaf_id)

    def _sync(self) -> None:
        names = []
        for level in self._levels:
            key = level.dropdown.value or ""
            if key:
                names.append(level.labels.get(key, key))
        self.breadcrumb.value = " / ".join(names) if names else LEVEL_HINT
        self.controls = [self.breadcrumb, *[level.dropdown for level in self._levels]]

    def set_leaf(self, leaf_id: str) -> None:
        chain = []
        node = self.rules.get(leaf_id)
        while node.parent_id and node.parent_id != self.rules.root_id:
            chain.append(node)
            node = self.rules.get(node.parent_id)
        if node.parent_id == self.rules.root_id:
            chain.append(node)
        chain.reverse()

        self._levels = []
        parent = self.rules.root_id
        found = None
        for node in chain:
            level = self._make_level(parent, len(self._levels))
            self._levels.append(level)
            if node.id not in level.targets:
                break
            level.dropdown.value = node.id
            target = level.targets[node.id]
            if target is not None:
                found = target
                break
            parent = level.next_parents[node.id]

        self._leaf_id = found or leaf_id
        self._sync()
        self.on_leaf(self._leaf_id)
