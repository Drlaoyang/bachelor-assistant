from __future__ import annotations

import flet as ft

from core.points import format_points, points_from_1e4


def build_activities(page: ft.Page, state, app) -> ft.Control:
    evidence_filter = ft.Dropdown(
        label="证明",
        options=[
            ft.DropdownOption(key="", text="全部"),
            ft.DropdownOption(key="yes", text="有证明"),
            ft.DropdownOption(key="no", text="缺证明"),
        ],
        value="",
        width=140,
    )
    category_filter = ft.Dropdown(label="分类", options=[], value="", width=160)
    category_filter.options = [ft.DropdownOption(key="", text="全部")] + [
        ft.DropdownOption(key=c.id, text=c.name)
        for c in state.rules.children_of(state.rules.root_id)
    ]
    keyword = ft.TextField(label="搜索标题", width=200)

    list_view = ft.Column([], spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    def reload():
        has_ev = None
        if evidence_filter.value == "yes":
            has_ev = True
        elif evidence_filter.value == "no":
            has_ev = False
        rows = state.repo.list_activities(
            academic_year=state.academic_year,
            statuses=None,
            keyword=(keyword.value or "").strip() or None,
            has_evidence=has_ev,
            category=category_filter.value or None,
        )
        rule_names = {
            row["id"]: row["name"]
            for row in state.repo.rule_nodes(state.repo.active_rule_version()["id"])
        }
        cards = []
        for row in rows:
            points = format_points(points_from_1e4(row["computed_points_1e4"]))
            evidence_note = (
                f"证明 {row['evidence_count']} 个" if row["evidence_count"] else "缺证明"
            )
            cards.append(
                ft.Card(
                    ft.Container(
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            row["title"] or rule_names.get(row["rule_node_id"], ""),
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(
                                            (
                                                f"{rule_names.get(row['rule_node_id'], '')}"
                                                f" · {row['activity_date'] or '未填日期'}"
                                            ),
                                            size=12,
                                            color=ft.Colors.GREY_700,
                                        ),
                                        ft.Text(evidence_note, size=12),
                                    ],
                                    tight=True,
                                    expand=True,
                                    spacing=4,
                                ),
                                ft.Text(f"{points} 分", size=18, weight=ft.FontWeight.BOLD),
                                ft.IconButton(
                                    ft.Icons.EDIT,
                                    on_click=lambda _, u=row["uuid"]: app.open_activity_form(u),
                                ),
                                ft.IconButton(
                                    ft.Icons.DELETE_OUTLINE,
                                    on_click=lambda _, u=row["uuid"]: _confirm_delete(
                                        page, state, app, u
                                    ),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        padding=12,
                    )
                )
            )
        list_view.controls = cards or [ft.Text("暂无活动，点击右上角新增。")]
        page.update()

    for control in (evidence_filter, category_filter):
        control.on_select = lambda _: reload()
    keyword.on_submit = lambda _: reload()

    reload()

    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text("活动", size=24, weight=ft.FontWeight.BOLD),
                    ft.FilledButton(
                        "新增活动",
                        icon=ft.Icons.ADD,
                        on_click=lambda _: app.open_activity_form(None),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Row(
                [evidence_filter, category_filter, keyword], wrap=True, spacing=8
            ),
            list_view,
        ],
        expand=True,
        spacing=10,
    )


def _confirm_delete(page, state, app, activity_uuid):
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("删除活动"),
        content=ft.Text("删除后可在备份中找回。确定删除这条活动吗？"),
        actions=[
            ft.TextButton("取消", on_click=lambda _: page.pop_dialog()),
            ft.FilledButton(
                "删除",
                on_click=lambda _: _do_delete(page, state, app, activity_uuid),
            ),
        ],
    )
    page.show_dialog(dialog)


def _do_delete(page, state, app, activity_uuid):
    state.repo.soft_delete_activity(activity_uuid)
    page.pop_dialog()
    app.refresh()
    app.notify("已删除")
