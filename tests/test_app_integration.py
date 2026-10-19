from __future__ import annotations

import flet as ft
import pytest

from app.app import LedgerApp
from app.state import AppState
from core.proof_analyzer import ProofSuggestion


class FakeWindow:
    width = 900


class FakePage:
    def __init__(self):
        self.title = ""
        self.theme_mode = None
        self.navigation_bar = None
        self.on_resize = None
        self.width = 900
        self.window = FakeWindow()
        self.platform = ft.PagePlatform.LINUX
        self.controls = []
        self.dialogs = []

    def add(self, control):
        self.controls.append(control)

    def clean(self):
        self.controls = []

    def update(self):
        pass

    def show_dialog(self, dialog):
        self.dialogs.append(dialog)

    def pop_dialog(self):
        if self.dialogs:
            self.dialogs.pop()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path))
    state = AppState()
    fake = FakePage()
    ledger = LedgerApp(fake)
    return ledger, state, fake


def test_onboarding_then_shell(app):
    ledger, state, fake = app
    assert fake.controls  # onboarding 渲染
    repo = state.repo
    repo.set_setting("student_id", "20220001")
    repo.set_setting("onboarded", "1")
    ledger.render()
    assert fake.navigation_bar is None  # 900 宽度使用侧边导航
    assert fake.controls


def test_dashboard_with_activities(app):
    ledger, state, fake = app
    repo = state.repo
    repo.set_setting("onboarded", "1")
    for _ in range(3):
        repo.create_activity(
            rule_node_id="physical_base_sports_rule",
            title="运动会服务",
            status="confirmed",
            inputs={},
            academic_year=state.academic_year,
        )
    ledger.render()
    result = state.compute()
    assert str(result.find("physical").counted) == "9"
    assert str(result.total) == "9"


def test_activity_form_preview_and_save(app):
    ledger, state, fake = app
    repo = state.repo
    repo.set_setting("onboarded", "1")
    ledger.render()
    ledger.open_activity_form(None)
    form = ledger._activity_form
    assert form is not None
    form.rule_picker.set_leaf("physical_base_fitness")
    form.form.set_values({"grade": "优秀"})
    form.title_field.value = "体测"
    form.date_field.value = "2026-10-01"
    form.preview()
    assert "9" in form.preview_text.value
    form.save(None)
    rows = repo.list_activities(academic_year=state.academic_year)
    assert len(rows) == 1
    assert rows[0]["status"] == "confirmed"
    assert ledger.current_index == 1
    assert ledger._activity_form is None


def test_rule_picker_cascading(app):
    ledger, state, fake = app
    state.repo.set_setting("onboarded", "1")
    ledger.open_activity_form(None)
    picker = ledger._activity_form.rule_picker

    first = picker.controls[1]
    labels = [option.text for option in first.options]
    assert "素质能力" not in labels
    assert {"身心素养", "文艺素养", "劳动素养", "创新素养"}.issubset(set(labels))

    first.value = "physical"
    picker._on_select(0)
    assert len(picker._levels) == 2
    second = picker.controls[2]
    assert "基础性评价" in [option.text for option in second.options]

    second.value = "physical_base"
    picker._on_select(1)
    third = picker.controls[3]
    assert "体育/心理类活动参与" in [option.text for option in third.options]

    third.value = "physical_base_sports"
    picker._on_select(2)
    assert picker.leaf_id == "physical_base_sports_rule"


def test_rule_picker_callback_sees_new_level(app):
    ledger, state, fake = app
    state.repo.set_setting("onboarded", "1")
    ledger.open_activity_form(None)
    picker = ledger._activity_form.rule_picker
    seen: dict[str, int] = {}
    picker.on_leaf = lambda _leaf: seen.setdefault("control_count", len(picker.controls))

    first = picker.controls[1]
    first.value = "physical"
    picker._on_select(0)
    assert seen["control_count"] == 3
    assert len(picker._levels) == 2


def test_rule_picker_set_leaf_nested(app):
    ledger, state, fake = app
    state.repo.set_setting("onboarded", "1")
    ledger.open_activity_form(None)
    picker = ledger._activity_form.rule_picker
    picker.set_leaf("labor_ach_social_work_collective")
    assert picker.leaf_id == "labor_ach_social_work_collective"
    assert len(picker._levels) >= 4
    assert "工作成效荣誉" in [option.text for option in picker.controls[-2].options]
    assert "集体荣誉" in [option.text for option in picker.controls[-1].options]


def test_apply_suggestion(app):
    ledger, state, fake = app
    state.repo.set_setting("onboarded", "1")
    ledger.render()
    ledger.open_activity_form(None)
    form = ledger._activity_form
    assert form is not None
    form._apply_suggestion(
        ProofSuggestion(
            title="体测证明",
            rule_id="physical_base_fitness",
            activity_date="2025-10-01",
        ),
        1,
    )
    assert form.title_field.value == "体测证明"
    assert form.date_field.value == "2025-10-01"
    assert form.rule_picker.leaf_id == "physical_base_fitness"
    assert form.form.controls


def test_rules_page_tree(app):
    ledger, state, fake = app
    state.repo.set_setting("onboarded", "1")
    ledger.show_page(3)
    content = fake.controls[-1]
    assert content is not None


def test_all_pages_render(app):
    ledger, state, fake = app
    state.repo.set_setting("onboarded", "1")
    for index in range(6):
        ledger.show_page(index)
        assert fake.controls, f"page {index} 未渲染"


def test_what_if_dialog(app):
    ledger, state, fake = app
    state.repo.set_setting("onboarded", "1")
    ledger.show_page(0)
    from app.pages.dashboard import _what_if

    _what_if(fake, state, ledger)
    assert fake.dialogs, "what-if 对话框未弹出"


def test_backup_export(app, tmp_path):
    ledger, state, fake = app
    state.repo.set_setting("onboarded", "1")
    state.repo.create_activity(
        rule_node_id="physical_base_sports_rule",
        title="活动",
        status="confirmed",
        inputs={},
        academic_year=state.academic_year,
    )
    from db.backup import export_backup

    target = tmp_path / "out.zip"
    export_backup(state.repo.conn, state.paths["evidence"], target)
    assert target.exists()
