from __future__ import annotations

from app.components.form_fields import DynamicForm


def _threshold_form() -> DynamicForm:
    form = DynamicForm()
    form.build_for("threshold", {"field": "hours"})
    return form


def test_required_number_validation():
    form = _threshold_form()
    assert form.validate() == ["时长（小时）"]
    form._controls["hours"].value = "20"
    assert form.validate() == []
    form._controls["hours"].value = "abc"
    assert form.validate() == ["时长（小时）"]


def test_clear_errors():
    form = _threshold_form()
    form.validate()
    assert form._controls["hours"].error == "必填"
    form.clear_errors()
    assert form._controls["hours"].error is None
