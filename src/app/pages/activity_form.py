from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path

import flet as ft

from app.components.camera_capture import (
    camera_supported,
    capture_photo,
    choose_image_rotation,
)
from app.components.form_fields import DynamicForm
from app.components.rule_picker import RulePicker
from app.score_text import describe_gain
from app.staged_evidence import StagedEvidence
from core.calculators import calculate
from core.image_tools import detect_evidence_type, prepare_image_for_storage
from core.models import Activity as CoreActivity
from core.points import format_points, to_decimal
from core.proof_analyzer import ProofSuggestion, analyze_proof, merge_suggestions
from core.scoring import Scorer
from device.files import save_evidence_blob
from device.paths import data_paths

EXTRA_BASE_RULES = {
    "physical_achievement_sports": "physical_base_sports_rule",
    "arts_achievement_awards": "arts_base_activities_rule",
}

IMAGE_MAX_SIDE = 2400
JPEG_QUALITY = 92


class ActivityForm:
    def __init__(self, page: ft.Page, state, app, activity_uuid: str | None):
        self.page = page
        self.state = state
        self.app = app
        self.activity_uuid = activity_uuid
        self.staged_files: list[StagedEvidence] = []
        self.file_picker = ft.FilePicker()
        self._picker_attached = False
        self.permission_handler = None
        self._analysis_seq = 0
        self.form = DynamicForm(on_change=lambda _: self.preview())
        self.rule_picker = RulePicker(self.state.rules, self._on_rule_selected)
        self.extra_base_check = ft.Checkbox(
            label="同一活动同时计入基础参与分（3分）",
            value=False,
            visible=False,
            on_change=lambda _: self.preview(),
        )
        self.title_field = ft.TextField(label="标题", on_change=lambda _: self.preview())
        self._date_is_default = False
        self.date_field = ft.TextField(
            label="日期", hint_text="YYYY-MM-DD", on_change=self._on_date_change
        )
        self.notes_field = ft.TextField(label="备注", multiline=True, min_lines=1, max_lines=3)
        self.override_check = ft.Checkbox(label="手动调整分值", on_change=self._on_override_toggle)
        self.override_points = ft.TextField(
            label="手动分值", visible=False, on_change=lambda _: self.preview()
        )
        self.override_reason = ft.TextField(label="调整理由", visible=False)
        self.preview_text = ft.Text("选择规则后实时显示计分预览。", size=13)
        self.ocr_status = ft.Text("", size=12, color=ft.Colors.GREY_700)
        self.reanalyze_button = ft.TextButton(
            "重新识别",
            icon=ft.Icons.REFRESH,
            visible=False,
            on_click=self._reanalyze_staged,
        )
        self.ocr_text = ft.Text("", size=12, selectable=True)
        self.ocr_panel = ft.ExpansionTile(
            title=ft.Text("识别原文", size=13),
            controls=[self.ocr_text],
            visible=False,
        )
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
        self.extra_base_check.visible = row["rule_node_id"] in EXTRA_BASE_RULES
        self.extra_base_check.value = bool(row["extra_rule_node_id"])
        self.form.set_values(json.loads(row["inputs_json"] or "{}"))
        self.title_field.value = row["title"]
        self.date_field.value = row["activity_date"]
        self._date_is_default = False
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
        was_visible = self.extra_base_check.visible
        extra_rule = EXTRA_BASE_RULES.get(leaf_id) if leaf_id else None
        self.extra_base_check.visible = extra_rule is not None
        if extra_rule is None:
            self.extra_base_check.value = False
        elif not was_visible:
            self.extra_base_check.value = True
        if leaf_id:
            node = self.state.rules.get(leaf_id)
            self.form.build_for(node.calculator, node.params)
        else:
            self.form.controls = []
        self.preview()
        self.page.update()

    def _on_date_change(self, _):
        self._date_is_default = False
        self.preview()

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
        extra_rule = None
        if self.extra_base_check.visible and self.extra_base_check.value:
            extra_rule = EXTRA_BASE_RULES.get(node_id)
        return CoreActivity(
            uuid="__preview__",
            rule_node_id=node_id,
            title=self.title_field.value or "预览",
            status="confirmed",
            inputs=self.form.collect(),
            extra_rule_node_id=extra_rule,
            override_points=override,
            override_reason=self.override_reason.value or None,
        )

    def preview(self) -> None:
        candidate = self._candidate()
        if candidate is None:
            self.preview_text.value = "选择规则并填写条件后，这里显示实际加分。"
            self.page.update()
            return
        node = self.state.rules.get(candidate.rule_node_id)
        try:
            if candidate.override_points is not None:
                base = candidate.override_points
            else:
                base = calculate(node.calculator, node.params, candidate.inputs)
        except Exception:
            self.preview_text.value = "请先填写完整条件。"
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
        self.preview_text.value = describe_gain(
            self.state.rules,
            simulated,
            "__preview__",
            candidate.rule_node_id,
            base,
            current_total,
        )
        self.page.update()

    # ------------------------------------------------------------------
    def _permission_handler(self):
        if self.permission_handler is None:
            try:
                import flet_permission_handler as fph
            except ImportError:
                return None
            self.permission_handler = fph.PermissionHandler()
            services = getattr(self.page, "services", None)
            if services is not None:
                try:
                    services.append(self.permission_handler)
                except Exception:
                    pass
        return self.permission_handler

    async def pick_evidence(self, _):
        try:
            files = await self.file_picker.pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf", "jpg", "jpeg", "png", "webp"],
                with_data=True,
            )
        except Exception as exc:
            self.app.notify(f"打开文件选择器失败：{exc}")
            return
        if not files:
            return
        f = files[0]
        data = f.bytes
        if data is None and f.path:
            data = Path(f.path).read_bytes()
        if data is None:
            self.app.notify("无法读取所选文件内容")
            return

        try:
            evidence_type = detect_evidence_type(data, f.name)
        except ValueError as exc:
            self.app.notify(str(exc))
            return

        rotation = 0
        if evidence_type.kind == "image":
            try:
                chosen = await choose_image_rotation(
                    self.page, data, f.name, self.app.notify
                )
            except Exception as exc:
                self.app.notify(f"无法打开图片校正：{exc}")
                return
            if chosen is None:
                return
            rotation = chosen

        self.staged_files.append(
            StagedEvidence(
                name=f.name,
                data=data,
                mime=evidence_type.mime,
                suffix=evidence_type.suffix,
                rotation=rotation,
            )
        )
        self._render_staged()
        self.page.update()
        await self._analyze_staged()

    async def capture_evidence(self, _):
        try:
            photo = await capture_photo(
                self.page,
                self._permission_handler(),
                self.app.notify,
            )
        except Exception as exc:
            self.app.notify(f"拍照失败：{exc}")
            return
        if photo is None:
            return
        data, rotation = photo
        try:
            evidence_type = detect_evidence_type(data, "photo.jpg")
        except ValueError as exc:
            self.app.notify(str(exc))
            return
        self.staged_files.append(
            StagedEvidence(
                name=f"photo_{datetime.now():%Y%m%d_%H%M%S}.jpg",
                data=data,
                mime=evidence_type.mime,
                suffix=evidence_type.suffix,
                rotation=rotation,
            )
        )
        self._render_staged()
        self.page.update()
        await self._analyze_staged()

    async def _reanalyze_staged(self, _):
        await self._analyze_staged()

    async def _analyze_staged(self) -> None:
        self.reanalyze_button.visible = bool(self.staged_files)
        if not self.staged_files:
            self._ensure_default_date()
            self.ocr_status.value = ""
            self.ocr_panel.visible = False
            self.ocr_text.value = ""
            self.page.update()
            return

        self._analysis_seq += 1
        seq = self._analysis_seq
        self.ocr_status.value = "正在识别证明…"
        self.page.update()

        first = self.staged_files[0]
        last = self.staged_files[-1]
        items = [first] if len(self.staged_files) == 1 else [first, last]
        try:
            results = []
            for item in items:
                results.append(
                    await asyncio.to_thread(
                        analyze_proof,
                        item.data,
                        item.name,
                        self.state.rules,
                        self.state.academic_year,
                        item.rotation,
                    )
                )
        except Exception as exc:
            if seq != self._analysis_seq:
                return
            self.ocr_status.value = f"识别失败：{exc}"
            self._ensure_default_date()
            self.page.update()
            return

        if seq != self._analysis_seq:
            return

        suggestion = merge_suggestions(
            results[0] if results else None,
            results[1] if len(results) > 1 else None,
        )
        self.ocr_status.value = ""
        self.ocr_text.value = suggestion.text
        self.ocr_panel.visible = bool(suggestion.text.strip())
        self._apply_suggestion(suggestion, len(self.staged_files))

    def _ensure_default_date(self) -> None:
        if not (self.date_field.value or "").strip():
            self.date_field.value = date.today().isoformat()
            self._date_is_default = True

    def _apply_suggestion(self, suggestion: ProofSuggestion, count: int) -> None:
        filled = []
        if suggestion.title and not (self.title_field.value or "").strip():
            self.title_field.value = suggestion.title
            filled.append(f"名称「{suggestion.title}」")
        if suggestion.rule_id and not self.rule_picker.leaf_id:
            self.rule_picker.set_leaf(suggestion.rule_id)
            filled.append(f"类型「{self.state.rules.get(suggestion.rule_id).name}」")

        recognized = []
        if suggestion.title:
            recognized.append(f"名称「{suggestion.title}」")
        if suggestion.rule_id:
            recognized.append(f"类型「{self.state.rules.get(suggestion.rule_id).name}」")
        if suggestion.activity_date:
            recognized.append(f"日期「{suggestion.activity_date}」")

        current_date = (self.date_field.value or "").strip()
        if suggestion.activity_date and (not current_date or self._date_is_default):
            self.date_field.value = suggestion.activity_date
            self._date_is_default = False
            filled.append(f"日期「{suggestion.activity_date}」")
        elif not current_date:
            self.date_field.value = date.today().isoformat()
            self._date_is_default = True

        self.preview()

        if recognized:
            suffix = "已自动填入" if filled else "已有内容未覆盖"
            self.app.notify(
                f"已选择 {count} 个证明文件；识别到 "
                + "、".join(recognized)
                + f"；{suffix}"
            )
        else:
            notes = "；".join(suggestion.notes) or "未识别到可自动填充的信息"
            self.app.notify(f"已选择 {count} 个证明文件；{notes}")
        self.page.update()

    def _render_staged(self):
        controls = []
        for i, item in enumerate(self.staged_files):
            if item.is_image:
                preview = ft.Image(
                    src=item.preview(),
                    width=56,
                    height=56,
                    fit=ft.BoxFit.COVER,
                    border_radius=4,
                )

                async def rotate_left_handler(_, i=i):
                    await self._rotate_staged(i, -90)

                async def rotate_right_handler(_, i=i):
                    await self._rotate_staged(i, 90)

                rotate_controls = [
                    ft.IconButton(
                        ft.Icons.ROTATE_LEFT,
                        tooltip="向左旋转",
                        on_click=rotate_left_handler,
                    ),
                    ft.IconButton(
                        ft.Icons.ROTATE_RIGHT,
                        tooltip="向右旋转",
                        on_click=rotate_right_handler,
                    ),
                ]
            else:
                preview = ft.Icon(ft.Icons.PICTURE_AS_PDF, color=ft.Colors.RED)
                rotate_controls = []

            async def remove_handler(_, i=i):
                await self._remove_staged(i)

            controls.append(
                ft.Row(
                    [
                        preview,
                        ft.Text(item.name, expand=True),
                        *rotate_controls,
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            tooltip="移除",
                            on_click=remove_handler,
                        ),
                    ]
                )
            )
        self.evidence_column.controls = controls

    async def _rotate_staged(self, index: int, delta: int) -> None:
        if index < 0 or index >= len(self.staged_files):
            return
        self.staged_files[index].rotate(delta)
        self._render_staged()
        self.page.update()
        await self._analyze_staged()

    async def _remove_staged(self, index: int):
        if index < 0 or index >= len(self.staged_files):
            return
        del self.staged_files[index]
        self._render_staged()
        self.page.update()
        await self._analyze_staged()

    def _attach_staged(self, activity_uuid: str):
        paths = data_paths()
        for item in self.staged_files:
            if item.is_image:
                data, mime, suffix = prepare_image_for_storage(
                    item.data,
                    rotation=item.rotation,
                    max_side=IMAGE_MAX_SIDE,
                    quality=JPEG_QUALITY,
                )
            else:
                data, mime, suffix = item.data, item.mime, item.suffix
            name = f"{Path(item.name).stem}.jpg" if item.is_image else item.name
            digest, relative = save_evidence_blob(paths["evidence"], data, suffix)
            self.state.repo.add_evidence(
                activity_uuid=activity_uuid,
                sha256=digest,
                original_name=name,
                size=len(data),
                relative_path=relative,
                mime=mime,
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
            is_image = str(row["mime"] or "").startswith("image/")
            controls.append(
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.IMAGE if is_image else ft.Icons.PICTURE_AS_PDF,
                            color=ft.Colors.BLUE if is_image else ft.Colors.RED,
                        ),
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
        if candidate.override_points is None:
            errors = self.form.validate()
            if errors:
                self.page.update()
                self.app.notify("请填写：" + "、".join(errors[:3]))
                return
        else:
            self.form.clear_errors()
        date_text = (self.date_field.value or "").strip() or date.today().isoformat()
        self.date_field.error = None
        if date_text:
            try:
                date_text = datetime.strptime(date_text, "%Y-%m-%d").date().isoformat()
            except ValueError:
                self.date_field.error = "格式应为 YYYY-MM-DD"
                self.page.update()
                self.app.notify("日期格式应为 YYYY-MM-DD")
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
            activity_date=date_text,
            status=candidate.status,
            inputs=candidate.inputs,
            notes=self.notes_field.value or "",
            override_points=candidate.override_points,
            override_reason=candidate.override_reason,
            extra_rule_node_id=candidate.extra_rule_node_id,
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
        evidence_buttons = [
            ft.OutlinedButton(
                "添加文件", icon=ft.Icons.UPLOAD_FILE, on_click=self.pick_evidence
            )
        ]
        if camera_supported(self.page):
            evidence_buttons.append(
                ft.OutlinedButton(
                    "拍照", icon=ft.Icons.PHOTO_CAMERA, on_click=self.capture_evidence
                )
            )
        evidence_section = ft.Column(
            [
                ft.Text("证明材料（PDF / 图片）", weight=ft.FontWeight.BOLD),
                ft.Text(
                    "一个活动添加一个证明文件；PDF 只识别第 1 页和最后一页，"
                    "图片可手动旋转校正。",
                    size=12,
                    color=ft.Colors.GREY_700,
                ),
                ft.Row(evidence_buttons, wrap=True, spacing=8),
                self.evidence_column,
                ft.Row([self.ocr_status, self.reanalyze_button], spacing=8),
                self.ocr_panel,
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
                self.extra_base_check,
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
