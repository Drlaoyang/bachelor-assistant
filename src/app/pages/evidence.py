from __future__ import annotations

import asyncio

import flet as ft

from device.open_file import open_file_desktop, open_or_share, share_files
from device.paths import data_paths
from device.pdf_tools import export_jpgs, pdf_page_count, safe_stem


def build_evidence(page: ft.Page, state, app) -> ft.Control:
    rows = state.repo.list_evidence()
    paths = data_paths()
    is_mobile = page.platform.is_mobile() if page.platform else False

    controls = []
    for row in rows:
        full_path = paths["evidence"] / row["relative_path"]

        async def open_handler(_, p=full_path, n=row["original_name"]):
            await open_or_share(p, is_mobile, n, display_name=n)

        async def do_convert(
            pages,
            p=full_path,
            n=row["original_name"],
            digest=row["sha256"],
        ):
            out_dir = paths["exports"] / "jpg" / f"{safe_stem(n)}_{digest[:8]}"
            try:
                files = await asyncio.to_thread(
                    export_jpgs, p, out_dir, pages=pages
                )
            except Exception as exc:
                app.notify(f"转 JPG 失败：{exc}")
                return
            if not files:
                app.notify("PDF 没有可转换的页面")
                return
            try:
                await share_files(files, f"{n} 转 JPG")
            except Exception:
                if is_mobile:
                    app.notify("分享面板不可用，JPG 已保存到导出目录")
                else:
                    open_file_desktop(out_dir)
            app.notify(f"已生成 {len(files)} 张 JPG")

        async def convert_handler(_, p=full_path):
            try:
                count = await asyncio.to_thread(pdf_page_count, p)
            except Exception as exc:
                app.notify(f"读取 PDF 页数失败：{exc}")
                return
            if count <= 1:
                await do_convert(None)
                return

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("转换为 JPG"),
                content=ft.Text(
                    f"该 PDF 共 {count} 页。默认只转第 1 页；"
                    "全部转换会更慢。"
                ),
            )

            async def convert_first(_):
                page.pop_dialog()
                await do_convert([0])

            async def convert_all(_):
                page.pop_dialog()
                await do_convert(None)

            dialog.actions = [
                ft.TextButton("仅第 1 页", on_click=convert_first),
                ft.TextButton(f"全部 {count} 页", on_click=convert_all),
                ft.TextButton("取消", on_click=lambda _: page.pop_dialog()),
            ]
            page.show_dialog(dialog)

        controls.append(
            ft.Card(
                ft.Container(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.PICTURE_AS_PDF, color=ft.Colors.RED),
                            ft.Column(
                                [
                                    ft.Text(row["original_name"], weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        f"{row['activity_title'] or '（已删除活动）'} ·"
                                        f" {row['size']} 字节",
                                        size=12,
                                        color=ft.Colors.GREY_700,
                                    ),
                                ],
                                tight=True,
                                expand=True,
                                spacing=2,
                            ),
                            ft.IconButton(
                                ft.Icons.IMAGE,
                                tooltip="转 JPG（默认第 1 页）",
                                on_click=convert_handler,
                            ),
                            ft.IconButton(ft.Icons.OPEN_IN_NEW, on_click=open_handler),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                on_click=lambda _, u=row["uuid"]: _delete(
                                    page, state, app, u
                                ),
                            ),
                        ]
                    ),
                    padding=12,
                )
            )
        )
    return ft.Column(
        [
            ft.Text("证明材料", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(
                "图片按钮转 JPG：默认只转第 1 页，多页 PDF 可选全部；转换后直接分享。",
                size=12,
                color=ft.Colors.GREY_700,
            ),
            ft.Column(
                controls or [ft.Text("暂无证明材料。")],
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        ],
        expand=True,
        spacing=10,
    )


def _delete(page, state, app, evidence_uuid):
    state.repo.soft_delete_evidence(evidence_uuid)
    app.refresh()
    app.notify("已删除证明")
