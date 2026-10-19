from __future__ import annotations

from collections.abc import Callable
from typing import Any

import flet as ft

from app import form_schema as schema


class DynamicForm(ft.Column):
    def __init__(self, on_change: Callable | None = None):
        super().__init__(spacing=10, tight=True)
        self.on_change = on_change
        self._controls: dict[str, ft.Control] = {}
        self._fields: list[schema.FieldDef] = []

    def build_for(self, calculator: str, params: dict) -> None:
        self._fields = schema.fields_for(calculator, params)
        self._controls.clear()
        self.controls = [self._build_control(field) for field in self._fields]

    def _changed(self, _):
        if self.on_change:
            self.on_change(self.collect())

    def _build_control(self, field: schema.FieldDef) -> ft.Control:
        if field.kind == "select":
            control = ft.Dropdown(
                label=field.label,
                options=[ft.DropdownOption(key=key, text=label) for key, label in field.options],
                value=str(field.default) if field.default is not None else None,
                on_select=self._changed,
                enable_filter=True,
            )
        elif field.kind == "bool":
            control = ft.Checkbox(
                label=field.label,
                value=bool(field.default) if field.default is not None else False,
                on_change=self._changed,
            )
        elif field.kind == "number":
            control = ft.TextField(
                label=field.label,
                hint_text=field.hint,
                value=str(field.default) if field.default is not None else "",
                on_change=self._changed,
                keyboard_type=ft.KeyboardType.NUMBER,
            )
        else:
            control = ft.TextField(
                label=field.label,
                hint_text=field.hint,
                value=str(field.default) if field.default is not None else "",
                on_change=self._changed,
            )
        self._controls[field.key] = control
        return control

    def collect(self) -> dict[str, Any]:
        inputs: dict[str, Any] = {}
        for field in self._fields:
            control = self._controls.get(field.key)
            if control is None:
                continue
            if field.kind == "bool":
                inputs[field.key] = bool(control.value)
            elif field.kind == "select":
                if control.value in (None, ""):
                    if field.required:
                        inputs[field.key] = None
                    continue
                inputs[field.key] = control.value
            else:
                raw = (control.value or "").strip()
                if raw == "":
                    if field.required:
                        inputs[field.key] = None
                    continue
                if field.kind == "number":
                    try:
                        number = float(raw)
                        inputs[field.key] = int(number) if number.is_integer() else number
                    except ValueError:
                        inputs[field.key] = None
                else:
                    inputs[field.key] = raw
        return inputs

    def set_values(self, inputs: dict[str, Any]) -> None:
        for field in self._fields:
            control = self._controls.get(field.key)
            if control is None or field.key not in inputs:
                continue
            value = inputs[field.key]
            if value is None:
                continue
            control.value = value if field.kind == "bool" else str(value)
