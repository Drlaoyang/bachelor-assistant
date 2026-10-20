from __future__ import annotations

import asyncio

import flet as ft

from app.components.form_fields import DynamicForm
from app.components.rule_picker import RulePicker
from core.calculators import calculate
from core.models import Activity as CoreActivity
from core.points import format_points, to_decimal
from core.proof_analyzer import ProofSuggestion, analyze_pdf
from core.scoring import Scorer
from device.files import save_evidence_blob
from device.paths import data_paths


class ActivityForm:
    def __init__(self, page: ft.Page, state, app, activity_uuid: str | None):
        self.page = page
        self.state = state
        self.app = app
        self.activity_uuid = activity_uuid
        self.staged_files: list[tuple[str, bytes]] = []
        self.file_picker = ft.FilePicker()
        self._picker_attached = False
        self.form = DynamicForm(on_change=lambda _: self.preview())
        self.rule_picker = RulePicker(self.state.rules, self._on_rule_selected)
        self.title_field = ft.TextField(label="标题", on_change=lambda _: self.preview())
        self.date_field = ft.TextField(
            label="日期", hint_text="YYYY-MM-DD", on_change=lambda _: self.preview()
        )
        self.notes_field = ft.TextField(label="备注", multiline=True, min_lines=1, max_lines=3)
        self.override_check = ft.Checkbox(label="手动调整分值", on_change=self._on_override_toggle)
        self.override_points = ft.TextField(
            label="手动分值", visible=False, on_change=lambda _: self.preview()
        )
        self.override_reason = ft.TextField(label="调整理由", visible=False)
        self.preview_text = ft.Text("选择规则后实时显示计分预览。", size=13)
        self.evidence_column = ft.Column([], spacing=6)
        self.existing_evidence: list = []
        if activity_uuid:
            self._load(activity_uuid)

    # ------------------------------------------------------------------
    def _load(self, activity_uuid: str) -> None:
        import json

        from core.points import points_from_1e4

        row = self.state.repo.get_activity(activity_uuid)
        if row is None:
            return
        self.rule_picker.set_leaf(row["rule_node_id"])
        self.form.set_values(json.loads(row["inputs_json"] or "{}"))
        self.title_field.value = row["title"]
        self.date_field.value = row["activity_date"]
        self.notes_field.value = row["notes"]
        if row["override_points_1e4"] is not None:
            self.override_check.value = True
            self.override_points.visible = True
            self.override_reason.visible = True
            self.override_points.value = format_points(points_from_1e4(row["override_points_1e4"]))
            self.override_reason.value = row["override_reason"] or ""
        self.existing_evidence = self.state.repo.list_evidence(activity_uuid)
        self.preview()

    # ------------------------------------------------------------------
    def _on_rule_selected(self, leaf_id: str | None):
        if leaf_id:
            node = self.state.rules.get(leaf_id)
            self.form.build_for(node.calculator, node.params)
        else:
            self.form.controls = []
        self.preview()
        self.page.update()

    def _on_override_toggle(self, _):
        self.override_points.visible = bool(self.override_check.value)
        self.override_reason.visible = bool(self.override_check.value)
        self.preview()
        self.page.update()

    def _candidate(self) -> CoreActivity | None:
        node_id = self.rule_picker.leaf_id
        if not node_id:
            return None
        override = None
        if self.override_check.value and (self.override_points.value or "").strip():
            try:
                override = to_decimal(self.override_points.value, "override")
            except Exception:
                override = None
        return CoreActivity(
            uuid="__preview__",
            rule_node_id=node_id,
            title=self.title_field.value or "预览",
            status="confirmed",
            inputs=self.form.collect(),
            override_points=override,
            override_reason=self.override_reason.value or None,
        )

    def preview(self) -> None:
        candidate = self._candidate()
        if candidate is None:
            self.preview_text.value = "选择规则后实时显示计分预览。"
            self.page.update()
            return
        node = self.state.rules.get(candidate.rule_node_id)
        try:
            if candidate.override_points is not None:
                base = candidate.override_points
            else:
                base = calculate(node.calculator, node.params, candidate.inputs)
        except Exception as exc:
            self.preview_text.value = f"计分失败：{exc}"
            self.page.update()
            return
        scorer = Scorer(self.state.rules)
        existing = [
            activity
            for activity in self.state.core_activities()
            if activity.uuid != (self.activity_uuid or "")
        ]
        statuses = tuple(sorted(set(self.state.statuses) | {candidate.status}))
        current_total = scorer.score(existing, self.state.statuses).total
        simulated = scorer.score([*existing, candidate], statuses)
        counted = next(
            (
                item.counted
                for item in simulated.root.activity_scores
                if item.activity.uuid == "__preview__"
            ),
            base,
        )
        gain = simulated.total - current_total
        self.preview_text.value = (
            f"应得 {format_points(base)} ｜ 计入 {format_points(counted)} ｜ "
            f"边际加分 {format_points(gain)} ｜ 试算总分 {format_points(simulated.total)}"
        )
        self.page.update()

    # ------------------------------------------------------------------
    async def pick_evidence(self, _):
        try:
            files = await self.file_picker.pick_files(
                allow_multiple=True,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf"],
                with_data=True,
            )
        except Exception as exc:
            self.app.notify(f"打开文件选择器失败：{exc}")
            return
        if not files:
            return
        for f in files:
            data = f.bytes
            if data is None and f.path:
                data = open(f.path, "rb").read()
            if data is not None:
                self.staged_files.append((f.name, data))
        self._render_staged()
        self.page.update()
        if self.staged_files:
            self.app.notify(f"已选择 {len(self.staged_files)} 个 PDF，正在识别…")
            first_data = self.staged_files[0][1]
            try:
                suggestion = await asyncio.to_thread(
                    analyze_pdf,
                    first_data,
                    self.state.rules,
                    self.state.academic_year,
                )
            except Exception as exc:
                self.app.notify(f"已选择 {len(self.staged_files)} 个 PDF；分析失败：{exc}")
            else:
                self._apply_suggestion(suggestion, len(self.staged_files))
        self.page.update()

    def _apply_suggestion(self, suggestion: ProofSuggestion, count: int) -> None:
        filled = []
        if suggestion.title and not (self.title_field.value or "").strip():
            self.title_field.value = suggestion.title
            filled.append(f"名称「{suggestion.title}」")
        if suggestion.activity_date and not (self.date_field.value or "").strip():
            self.date_field.value = suggestion.activity_date
            filled.append(f"日期「{suggestion.activity_date}」")
        if suggestion.rule_id and not self.rule_picker.leaf_id:
            self.rule_picker.set_leaf(suggestion.rule_id)
            filled.append(f"类型「{self.state.rules.get(suggestion.rule_id).name}」")
        self.preview()

        recognized = []
        if suggestion.title:
            recognized.append(f"名称「{suggestion.title}」")
        if suggestion.rule_id:
            recognized.append(f"类型「{self.state.rules.get(suggestion.rule_id).name}」")
        if suggestion.activity_date:
            recognized.append(f"日期「{suggestion.activity_date}」")
        if recognized:
            suffix = "已自动填入" if filled else "已有内容未覆盖"
            self.app.notify(
                f"已选择 {count} 个 PDF；识别到 " + "、".join(recognized) + f"；{suffix}"
            )
        else:
            notes = "；".join(suggestion.notes) or "未识别到可自动填充的信息"
            self.app.notify(f"已选择 {count} 个 PDF；{notes}")
        self.page.update()

    def _render_staged(self):
        self.evidence_column.controls = [
            ft.Row(
                [
                    ft.Icon(ft.Icons.PICTURE_AS_PDF),
                    ft.Text(name, expand=True),
                    ft.IconButton(ft.Icons.CLOSE, on_click=lambda _, i=i: self._remove_staged(i)),
                ]
            )
            for i, (name, _data) in enumerate(self.staged_files)
        ]

    def _remove_staged(self, index: int):
        del self.staged_files[index]
        self._render_staged()
        self.page.update()

    def _attach_staged(self, activity_uuid: str):
        paths = data_paths()
        for name, data in self.staged_files:
            digest, relative = save_evidence_blob(paths["evidence"], data, ".pdf")
            self.state.repo.add_evidence(
                activity_uuid=activity_uuid,
                sha256=digest,
                original_name=name,
                size=len(data),
                relative_path=relative,
            )
        self.staged_files.clear()

    def _delete_existing_evidence(self, evidence_uuid: str):
        self.state.repo.soft_delete_evidence(evidence_uuid)
        self.existing_evidence = self.state.repo.list_evidence(self.activity_uuid)
        self._render_existing_evidence()
        self.page.update()

    def _render_existing_evidence(self):
        controls = []
        for row in self.existing_evidence:
            controls.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.PICTURE_AS_PDF),
                        ft.Text(row["original_name"], expand=True),
                        ft.IconButton(
                            ft.Icons.DELETE_OUTLINE,
                            on_click=lambda _, u=row["uuid"]: self._delete_existing_evidence(u),
                        ),
                    ]
                )
            )
        return controls

    # ------------------------------------------------------------------
    def save(self, _):
        candidate = self._candidate()
        if candidate is None:
            self.app.notify("请先选择规则")
            return
        if not (self.title_field.value or "").strip():
            self.app.notify("请填写标题")
            return
        try:
            if candidate.override_points is not None:
                pass
            else:
                calculate(
                    self.state.rules.get(candidate.rule_node_id).calculator,
                    self.state.rules.get(candidate.rule_node_id).params,
                    candidate.inputs,
                )
        except Exception as exc:
            self.app.notify(f"条件不完整：{exc}")
            return

        fields = dict(
            rule_node_id=candidate.rule_node_id,
            title=(self.title_field.value or "").strip(),
            activity_date=(self.date_field.value or "").strip(),
            status=candidate.status,
            inputs=candidate.inputs,
            notes=self.notes_field.value or "",
            override_points=candidate.override_points,
            override_reason=candidate.override_reason,
        )
        if self.activity_uuid:
            self.state.repo.update_activity(self.activity_uuid, **fields)
            self._attach_staged(self.activity_uuid)
            self.app.notify("已保存")
        else:
            new_uuid = self.state.repo.create_activity(
                **fields,
                academic_year=self.state.academic_year,
                student_id=self.state.repo.get_setting("student_id", "") or "",
            )
            self._attach_staged(new_uuid)
            self.app.notify("已新增")
        self.state.compute()
        self.app.show_page(1)

    def view(self) -> ft.Control:
        services = getattr(self.page, "services", None)
        if services is not None and not self._picker_attached:
            services.append(self.file_picker)
            self._picker_attached = True
        evidence_section = ft.Column(
            [
                ft.Text("证明材料（PDF）", weight=ft.FontWeight.BOLD),
                ft.OutlinedButton(
                    "选择 PDF", icon=ft.Icons.UPLOAD_FILE, on_click=self.pick_evidence
                ),
                self.evidence_column,
                *self._render_existing_evidence(),
            ],
            spacing=8,
        )
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.ARROW_BACK, on_click=lambda _: self.app.show_page(1)
                        ),
                        ft.Text(
                            "编辑活动" if self.activity_uuid else "新增活动",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ]
                ),
                self.rule_picker,
                self.title_field,
                self.date_field,
                self.form,
                self.notes_field,
                self.override_check,
                self.override_points,
                self.override_reason,
                ft.Container(
                    self.preview_text,
                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLUE),
                    padding=10,
                    border_radius=8,
                ),
                evidence_section,
                ft.Row(
                    [
                        ft.FilledButton("保存", icon=ft.Icons.SAVE, on_click=self.save),
                        ft.TextButton("取消", on_click=lambda _: self.app.show_page(1)),
                    ]
                ),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
