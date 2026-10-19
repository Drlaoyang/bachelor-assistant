from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def is_android() -> bool:
    return sys.platform.startswith("android") or os.environ.get("FLET_PLATFORM") == "android"


def open_file_desktop(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])


async def share_file(
    path: Path,
    title: str = "证明文件",
    display_name: str | None = None,
) -> None:
    import flet as ft

    share = ft.Share()
    name = display_name or path.name
    if path.suffix.lower() == ".pdf":
        file = ft.ShareFile.from_bytes(
            path.read_bytes(),
            mime_type="application/pdf",
            name=name,
        )
    else:
        file = ft.ShareFile.from_path(str(path), name=name)
    await share.share_files([file], text=title)


async def share_files(paths: list[Path], title: str = "文件") -> None:
    import flet as ft

    share = ft.Share()
    files = [ft.ShareFile.from_path(str(path), name=path.name) for path in paths]
    await share.share_files(files, text=title)


async def open_or_share(
    path: Path,
    is_mobile: bool,
    title: str = "证明文件",
    display_name: str | None = None,
) -> None:
    if is_mobile or is_android():
        await share_file(path, title, display_name)
    else:
        open_file_desktop(path)
