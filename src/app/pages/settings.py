from __future__ import annotations

import flet as ft

from device.paths import data_paths

THEME_OPTIONS = [("system", "跟随系统"), ("light", "浅色"), ("dark", "深色")]


def build_settings(page: ft.Page, state, app) -> ft.Control:
    repo = state.repo
    student_id = ft.TextField(label="学号", value=repo.get_setting("student_id", "") or "")
    name = ft.TextField(label="姓名", value=repo.get_setting("student_name", "") or "")
    year = ft.TextField(label="学年", value=state.academic_year)
    window_start = ft.TextField(
        label="活动开始日期", value=repo.get_setting("window_start", "") or ""
    )
    window_end = ft.TextField(label="活动结束日期", value=repo.get_setting("window_end", "") or "")
    theme = ft.Dropdown(
        label="主题",
        options=[ft.DropdownOption(key=k, text=v) for k, v in THEME_OPTIONS],
        value=repo.get_setting("theme", "system") or "system",
    )

    def save(_):
        repo.set_setting("student_id", (student_id.value or "").strip())
        repo.set_setting("student_name", (name.value or "").strip())
        repo.set_setting("academic_year", (year.value or "").strip())
        repo.set_setting("window_start", (window_start.value or "").strip())
        repo.set_setting("window_end", (window_end.value or "").strip())
        repo.set_setting("theme", theme.value or "system")
        state.set_year((year.value or "").strip() or state.academic_year)
        app.apply_theme()
        app.refresh()
        app.notify("设置已保存")

    paths = data_paths()
    return ft.Column(
        [
            ft.Text("设置", size=24, weight=ft.FontWeight.BOLD),
            student_id,
            name,
            year,
            window_start,
            window_end,
            theme,
            ft.Text(f"数据目录：{paths['base']}", size=12, selectable=True),
            ft.FilledButton("保存", icon=ft.Icons.SAVE, on_click=save),
        ],
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
