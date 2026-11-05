from __future__ import annotations

import flet as ft

from app.components.form_fields import DynamicForm
from app.components.rule_picker import RulePicker
from app.score_text import describe_gain
from core.calculators import calculate
from core.points import format_percent, format_points, format_score


def _status_color(counted, cap) -> str:
    if not cap:
        return ft.Colors.GREEN
    if counted >= cap:
        return ft.Colors.RED
    if cap > 0 and counted / cap >= 0.9:
        return ft.Colors.AMBER
    return ft.Colors.GREEN


def _node_progress(node) -> ft.Control:
    cap = node.cap
    ratio = float(node.counted / cap) if cap else 0.0
    color = _status_color(node.counted, cap)
    if cap:
        subtitle = (
            f"{format_score(node.counted)} / {format_points(cap)}"
            f"（{format_percent(node.counted, cap)}）"
        )
    else:
        subtitle = format_score(node.counted)
    if node.overflow and node.overflow > 0:
        subtitle += f"；超出上限 {format_score(node.overflow)}，不计入"
    if node.remaining is not None:
        subtitle += f"；还可加 {format_score(node.remaining)} 分"
    return ft.Column(
        [
            ft.Row([ft.Text(node.name, weight=ft.FontWeight.BOLD), ft.Text(subtitle, size=12)]),
            ft.ProgressBar(value=min(ratio, 1.0), color=color, bar_height=8),
        ],
        spacing=4,
        tight=True,
    )


def build_dashboard(page: ft.Page, state, app) -> ft.Control:
    result = state.compute()
    root = result.root

    alerts = []
    categories = list(root.children)
    for category in categories:
        if (
            category.cap
            and category.remaining is not None
            and category.remaining == 0
        ):
            other_rooms = [
                child.name
                for child in categories
                if child.node_id != category.node_id
                and child.remaining is not None
                and child.remaining > 0
            ]
            suffix = "其他分类仍可加分" if other_rooms else "所有分类都已加满"
            alerts.append(f"{category.name}已加满；{suffix}")
            continue
        for section in category.children:
            if section.cap is None or section.cap <= 0:
                continue
            if section.remaining is not None and section.remaining == 0:
                room = [
                    child
                    for child in category.children
                    if child.node_id != section.node_id
                    and child.remaining is not None
                    and child.remaining > 0
                ]
                if room:
                    extras = "；".join(
                        f"{child.name}还可加 {format_score(child.remaining)} 分"
                        for child in room[:2]
                    )
                    alerts.append(f"{section.name}已加满；{extras}")
                else:
                    alerts.append(f"{section.name}已加满；该二级项目不再加分")
            elif (
                section.remaining is not None
                and 0 < section.counted / section.cap >= 0.9
            ):
                alerts.append(
                    f"{section.name}快满了，还可加 {format_score(section.remaining)} 分"
                )

    category_cards = []
    for category in root.children:
        color = _status_color(category.counted, category.cap)
        ratio = float(category.counted / category.cap) if category.cap else 0.0
        card = ft.Card(
            ft.Container(
                ft.Column(
                    [
                        ft.Text(category.name, size=16, weight=ft.FontWeight.BOLD),
                        ft.Row(
                            [
                                ft.Text(
                                    f"{format_score(category.counted)} /"
                                    f" {format_points(category.cap)}",
                                    size=22,
                                    weight=ft.FontWeight.BOLD,
                                    color=color,
                                ),
                                ft.Text(
                                    format_percent(category.counted, category.cap),
                                    size=14,
                                    color=color,
                                ),
                            ],
                            spacing=8,
                        ),
                        ft.ProgressBar(value=min(ratio, 1.0), color=color, bar_height=10),
                        ft.Column(
                            [_node_progress(child) for child in category.children],
                            spacing=8,
                        ),
                    ],
                    spacing=10,
                ),
                padding=14,
            )
        )
        category_cards.append(card)

    alert_controls = [
        ft.Container(
            ft.Row(
                [
                    ft.Icon(ft.Icons.ERROR, color=ft.Colors.RED_700),
                    ft.Text(text, color=ft.Colors.RED_700),
                ]
            ),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED),
            padding=10,
            border_radius=8,
        )
        for text in alerts
    ]

    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text("总览", size=26, weight=ft.FontWeight.BOLD),
                    ft.FilledButton(
                        "试算加分",
                        icon=ft.Icons.CALCULATE,
                        on_click=lambda _: _what_if(page, state, app),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Card(
                ft.Container(
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("素质能力得分", size=14),
                                    ft.Row(
                                        [
                                            ft.Text(
                                                f"{format_score(root.counted)} /"
                                                f" {format_points(root.cap or 100)}",
                                                size=34,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                format_percent(root.counted, root.cap or 100),
                                                size=16,
                                                color=ft.Colors.GREY_700,
                                            ),
                                        ],
                                        spacing=8,
                                    ),
                                ],
                                tight=True,
                            ),
                            ft.Column(
                                [
                                    ft.Text("折算综合测评贡献（×10%）", size=14),
                                    ft.Text(format_score(root.counted / 10), size=24),
                                    ft.Text(
                                        f"还可加 {format_score(root.remaining)} 分",
                                        size=14,
                                        color=ft.Colors.GREY_700,
                                    ),
                                ],
                                tight=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                    ),
                    padding=16,
                )
            ),
            *( [ft.Column(alert_controls, spacing=6)] if alert_controls else [] ),
            ft.Text("分类进度", size=18, weight=ft.FontWeight.BOLD),
            ft.Column(category_cards, spacing=10),
        ],
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


def _what_if(page: ft.Page, state, app) -> None:
    rules = state.rules
    form = DynamicForm()
    result_text = ft.Text("选择规则并填写条件后，点击计算。")
    dialog = ft.AlertDialog(modal=True, title=ft.Text("试算加分"), scrollable=True)

    def on_leaf(leaf_id: str | None):
        if leaf_id:
            node = rules.get(leaf_id)
            form.build_for(node.calculator, node.params)
        else:
            form.controls = []
        page.update()

    picker = RulePicker(rules, on_leaf)

    def compute_gain(_):
        node_id = picker.leaf_id
        if not node_id:
            result_text.value = "请先选择规则。"
        else:
            node = rules.get(node_id)
            inputs = form.collect()
            try:
                base = calculate(node.calculator, node.params, inputs)
            except Exception:
                result_text.value = "请先填写完整条件。"
                page.update()
                return
            from core.models import Activity as CoreActivity

            candidate = CoreActivity(
                uuid="__what_if__",
                rule_node_id=node_id,
                title="试算",
                status="confirmed",
                inputs=inputs,
            )
            from core.scoring import Scorer

            scorer = Scorer(rules)
            current_total = scorer.score(
                state.core_activities(), state.statuses
            ).total
            simulated = scorer.score(
                [*state.core_activities(), candidate],
                tuple(sorted(set(state.statuses) | {"confirmed"})),
            )
            result_text.value = describe_gain(
                rules,
                simulated,
                "__what_if__",
                node_id,
                base,
                current_total,
            )
        page.update()

    dialog.content = ft.Column([picker, form, result_text], tight=True, spacing=10, width=420)
    dialog.actions = [
        ft.TextButton("计算", on_click=compute_gain),
        ft.TextButton("关闭", on_click=lambda _: page.pop_dialog()),
    ]
    page.show_dialog(dialog)
