from __future__ import annotations

from pathlib import Path

import flet as ft

from db.backup import export_backup, import_backup
from device.open_file import share_file
from device.paths import data_paths


def build_backup(page: ft.Page, state, app) -> ft.Control:
    paths = data_paths()
    status = ft.Text("")
    is_mobile = page.platform.is_mobile() if page.platform else False

    async def do_export(_):
        target = paths["exports"] / "backup.zip"
        export_backup(state.repo.conn, paths["evidence"], target)
        if is_mobile:
            await share_file(target, "综合测评账本备份")
            status.value = "已通过系统分享导出备份。"
        else:
            chosen = await ft.FilePicker().save_file(
                file_name="backup.zip",
                src_bytes=target.read_bytes(),
            )
            status.value = f"已导出：{chosen or target}"
        page.update()

    async def do_import(_):
        files = await ft.FilePicker().pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["zip"],
            with_data=True,
        )
        if not files:
            return
        data = files[0].bytes
        if data is None and files[0].path:
            data = Path(files[0].path).read_bytes()
        if data is None:
            app.notify("无法读取所选文件内容")
            return
        source = paths["exports"] / "import.zip"
        source.write_bytes(data)
        try:
            backup_path = import_backup(
                state.repo.conn, paths["evidence"], source, paths["backups"]
            )
        except Exception as exc:
            app.notify(f"导入失败：{exc}")
            return
        state.rules = state.repo.load_active_ruleset()
        status.value = f"导入完成；导入前已自动备份到 {backup_path.name}"
        app.refresh()
        page.update()

    return ft.Column(
        [
            ft.Text("备份与恢复", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(
                "导出内容包含数据库、全部证明 PDF、规则版本与 CSV 汇总。"
                "导入会整体替换当前数据，导入前会自动备份。",
                size=13,
                color=ft.Colors.GREY_700,
            ),
            ft.FilledButton("导出备份 zip", icon=ft.Icons.UPLOAD, on_click=do_export),
            ft.OutlinedButton("导入备份 zip", icon=ft.Icons.DOWNLOAD, on_click=do_import),
            status,
        ],
        spacing=14,
        tight=True,
    )
