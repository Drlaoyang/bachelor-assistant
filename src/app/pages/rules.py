from __future__ import annotations

import flet as ft

from core.points import format_points


def build_rules_page(page: ft.Page, state, app) -> ft.Control:
    rules = state.rules

    def node_tile(node_id: str) -> ft.Control:
        node = rules.get(node_id)
        children = rules.children_of(node_id)
        if not children:
            return ft.ListTile(title=ft.Text(node.name), dense=True)

        subtitle = None
        if node.cap is not None:
            subtitle = ft.Text(
                f"上限 {format_points(node.cap)} 分",
                size=12,
                color=ft.Colors.GREY_700,
            )
        return ft.ExpansionTile(
            title=ft.Text(
                node.name,
                weight=ft.FontWeight.BOLD
                if node.level in {"category", "section"}
                else None,
            ),
            subtitle=subtitle,
            controls=[node_tile(child.id) for child in children],
        )

    return ft.Column(
        [
            ft.Text("规则", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(
                f"{rules.version} · 仅展示分类与上限",
                size=12,
                color=ft.Colors.GREY_700,
            ),
            ft.Column(
                [node_tile(child.id) for child in rules.children_of(rules.root_id)],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        ],
        expand=True,
        spacing=10,
    )
