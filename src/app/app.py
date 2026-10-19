from __future__ import annotations

import flet as ft

from app.pages import activities as activities_page
from app.pages import backup as backup_page
from app.pages import dashboard as dashboard_page
from app.pages import evidence as evidence_page
from app.pages import onboarding as onboarding_page
from app.pages import rules as rules_page
from app.pages import settings as settings_page
from app.pages.activity_form import ActivityForm
from app.state import AppState

DESTINATIONS = [
    ("总览", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD),
    ("活动", ft.Icons.LIST_ALT, ft.Icons.LIST_ALT),
    ("证明", ft.Icons.FOLDER_OUTLINED, ft.Icons.FOLDER),
    ("规则", ft.Icons.ACCOUNT_TREE_OUTLINED, ft.Icons.ACCOUNT_TREE),
    ("备份", ft.Icons.BACKUP_OUTLINED, ft.Icons.BACKUP),
    ("设置", ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS),
]


class LedgerApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.state = AppState()
        self.current_index = 0
        self._activity_form: ActivityForm | None = None
        page.title = "综合测评账本"
        self.apply_theme()
        page.on_resize = lambda _: self.render()
        if not self.state.repo.get_setting("onboarded"):
            self.show_onboarding()
        else:
            self.render()

    # --------------------------------------------------------------
    def apply_theme(self):
        mode = self.state.repo.get_setting("theme", "system") or "system"
        self.page.theme_mode = {
            "light": ft.ThemeMode.LIGHT,
            "dark": ft.ThemeMode.DARK,
        }.get(mode, ft.ThemeMode.SYSTEM)
        self.page.update()

    def notify(self, message: str):
        self.page.show_dialog(ft.SnackBar(ft.Text(message)))

    def show_onboarding(self):
        self.page.clean()
        self.page.navigation_bar = None
        self.page.add(
            onboarding_page.build_onboarding(self.page, self.state, self._finish_onboarding)
        )
        self.page.update()

    def _finish_onboarding(self):
        self.render()

    # --------------------------------------------------------------
    def _page_content(self) -> ft.Control:
        page, state = self.page, self.state
        if self._activity_form is not None:
            return self._activity_form.view()
        builders = [
            dashboard_page.build_dashboard,
            activities_page.build_activities,
            evidence_page.build_evidence,
            rules_page.build_rules_page,
            backup_page.build_backup,
            settings_page.build_settings,
        ]
        return builders[self.current_index](page, state, self)

    def open_activity_form(self, activity_uuid: str | None):
        self._activity_form = ActivityForm(self.page, self.state, self, activity_uuid)
        self.render()

    def show_page(self, index: int):
        self._activity_form = None
        self.current_index = index
        self.render()

    def refresh(self):
        self.render()

    # --------------------------------------------------------------
    def render(self):
        page = self.page
        is_mobile = bool(page.platform and page.platform.is_mobile())
        width = page.width or page.window.width or 800
        narrow = is_mobile or width < 600
        content = self._page_content()

        def on_nav(e):
            if e.control.selected_index is not None:
                self.show_page(e.control.selected_index)

        if self._activity_form is not None:
            page.navigation_bar = None
            page.clean()
            page.add(ft.SafeArea(content=content, expand=True))
            page.update()
            return

        if narrow:
            page.navigation_bar = ft.NavigationBar(
                selected_index=self.current_index,
                on_change=on_nav,
                destinations=[
                    ft.NavigationBarDestination(icon=icon, selected_icon=selected, label=label)
                    for label, icon, selected in DESTINATIONS
                ],
            )
            page.clean()
            page.add(ft.SafeArea(content=content, expand=True))
        else:
            page.navigation_bar = None
            rail = ft.NavigationRail(
                selected_index=self.current_index,
                on_change=on_nav,
                label_type=ft.NavigationRailLabelType.ALL,
                min_width=90,
                destinations=[
                    ft.NavigationRailDestination(icon=icon, selected_icon=selected, label=label)
                    for label, icon, selected in DESTINATIONS
                ],
            )
            page.clean()
            page.add(
                ft.SafeArea(
                    expand=True,
                    content=ft.Row(
                        [
                            rail,
                            ft.VerticalDivider(width=1),
                            ft.Container(content=content, expand=True, padding=16),
                        ],
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                )
            )
        page.update()
