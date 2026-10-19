from __future__ import annotations

import flet as ft

from app.components.form_fields import DynamicForm
from app.components.rule_picker import RulePicker
from core.calculators import calculate
from core.points import format_points


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
    subtitle = (
        f"{format_points(node.counted)} / {format_points(cap)}"
        if cap
        else format_points(node.counted)
    )
    if node.overflow and node.overflow > 0:
        subtitle += f"（溢出 {format_points(node.overflow)}）"
    if node.remaining is not None:
        subtitle += f"，剩余 {format_points(node.remaining)}"
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
    roomy = []
    for node in root.walk():
        if node.cap is None or node.node_id == root.node_id:
            continue
        if node.remaining is not None and node.remaining == 0 and node.cap > 0:
            alerts.append(f"{node.name} 已封顶")
        elif (
            node.remaining is not None
            and node.cap
            and node.cap > 0
            and 0 < node.counted / node.cap >= 0.9
        ):
            alerts.append(f"{node.name} 已接近上限（剩余 {format_points(node.remaining)}）")
        elif node.remaining is not None and node.remaining > 0 and node.node_id != root.node_id:
            roomy.append((node.name, node.remaining))

    category_cards = []
    for category in root.children:
        color = _status_color(category.counted, category.cap)
        ratio = float(category.counted / category.cap) if category.cap else 0.0
        card = ft.Card(
            ft.Container(
                ft.Column(
                    [
                        ft.Text(category.name, size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            f"{format_points(category.counted)} / {format_points(category.cap)}",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=color,
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
    if not alert_controls:
        alert_controls = [
            ft.Container(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_700),
                        ft.Text(
                            "暂无封顶提醒，继续合理规划。",
                            color=ft.Colors.GREEN_700,
                        ),
                    ]
                ),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN),
                padding=10,
                border_radius=8,
            )
        ]

    roomy_controls = [
        ft.ListTile(
            leading=ft.Icon(ft.Icons.TRENDING_UP),
            title=ft.Text(name),
            subtitle=ft.Text(f"剩余 {format_points(remaining)} 分空间"),
            dense=True,
        )
        for name, remaining in roomy[:12]
    ]

    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text("总览", size=26, weight=ft.FontWeight.BOLD),
                    ft.FilledButton(
                        "What-if 试算",
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
                                    ft.Text(
                                        f"{format_points(root.counted)} /"
                                        f" {format_points(root.cap or 100)}",
                                        size=34,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ],
                                tight=True,
                            ),
                            ft.Column(
                                [
                                    ft.Text("折算综合测评贡献（×10%）", size=14),
                                    ft.Text(format_points(root.counted / 10), size=24),
                                    ft.Text(
                                        f"剩余 {format_points(root.remaining)}",
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
            ft.Column(alert_controls, spacing=6),
            ft.Text("分类进度", size=18, weight=ft.FontWeight.BOLD),
            ft.Column(category_cards, spacing=10),
            ft.Text("还有空间的分类", size=18, weight=ft.FontWeight.BOLD),
            ft.Column(roomy_controls or [ft.Text("全部分类均已封顶。")], spacing=0),
        ],
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


def _what_if(page: ft.Page, state, app) -> None:
    rules = state.rules
    form = DynamicForm()
    result_text = ft.Text("选择规则并填写条件后，点击计算。")
    dialog = ft.AlertDialog(modal=True, title=ft.Text("What-if 试算"), scrollable=True)

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
            except Exception as exc:
                result_text.value = f"计算失败：{exc}"
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
            current = scorer.score(state.core_activities(), state.statuses).total
            simulated = scorer.score(
                [*state.core_activities(), candidate],
                tuple(sorted(set(state.statuses) | {"confirmed"})),
            )
            gain = simulated.total - current
            counted = next(
                (
                    item.counted
                    for item in simulated.root.activity_scores
                    if item.activity.uuid == "__what_if__"
                ),
                base,
            )
            result_text.value = (
                f"应得 {format_points(base)}，计入 {format_points(counted)}，"
                f"边际加分 {format_points(gain)}，试算总分 {format_points(simulated.total)}"
            )
        page.update()

    dialog.content = ft.Column([picker, form, result_text], tight=True, spacing=10, width=420)
    dialog.actions = [
        ft.TextButton("计算", on_click=compute_gain),
        ft.TextButton("关闭", on_click=lambda _: page.pop_dialog()),
    ]
    page.show_dialog(dialog)
