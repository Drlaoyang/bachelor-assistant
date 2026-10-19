from __future__ import annotations

import flet as ft

from app.state import DEFAULT_YEAR


def build_onboarding(page: ft.Page, state, on_done) -> ft.Control:
    student_id = ft.TextField(label="学号", autofocus=True)
    name = ft.TextField(label="姓名")
    year = ft.TextField(label="学年", value=DEFAULT_YEAR)
    window_start = ft.TextField(label="活动开始日期", value=f"{DEFAULT_YEAR.split('-')[0]}-09-01")
    window_end = ft.TextField(label="活动结束日期", value=f"{DEFAULT_YEAR.split('-')[1]}-08-31")

    def save(_):
        repo = state.repo
        repo.set_setting("student_id", (student_id.value or "").strip())
        repo.set_setting("student_name", (name.value or "").strip())
        repo.set_setting("academic_year", (year.value or DEFAULT_YEAR).strip())
        repo.set_setting("window_start", (window_start.value or "").strip())
        repo.set_setting("window_end", (window_end.value or "").strip())
        repo.set_setting("onboarded", "1")
        state.academic_year = (year.value or DEFAULT_YEAR).strip()
        on_done()

    return ft.SafeArea(
        ft.Column(
            [
                ft.Text("欢迎使用综合测评账本", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("首次使用，请填写基本信息。之后可在“设置”中修改。"),
                student_id,
                name,
                year,
                window_start,
                window_end,
                ft.FilledButton("开始使用", icon=ft.Icons.CHECK, on_click=save),
            ],
            spacing=14,
            tight=True,
        )
    )
