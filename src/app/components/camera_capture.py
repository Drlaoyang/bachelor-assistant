from __future__ import annotations

import asyncio
import base64

import flet as ft

from core.image_tools import render_preview

_BLANK_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
)


def camera_supported(page: ft.Page) -> bool:
    platform = page.platform
    if platform is None:
        return False
    return platform in {ft.PagePlatform.ANDROID, ft.PagePlatform.IOS}


async def capture_photo(
    page: ft.Page,
    permission_handler,
    notify,
) -> tuple[bytes, int] | None:
    """Open an in-app camera, let the user rotate the photo and return it."""
    if not camera_supported(page):
        notify("当前平台不支持应用内拍照，请使用“添加文件”")
        return None

    try:
        import flet_camera as fc
        import flet_permission_handler as fph
    except ImportError:
        notify("相机组件未安装，请重新安装或更新应用")
        return None

    try:
        if permission_handler is not None:
            status = await permission_handler.request(fph.Permission.CAMERA)
            allowed = {
                fph.PermissionStatus.GRANTED,
                fph.PermissionStatus.LIMITED,
                fph.PermissionStatus.PROVISIONAL,
            }
            if status not in allowed:
                if status == fph.PermissionStatus.PERMANENTLY_DENIED:
                    notify("相机权限已被永久拒绝，请在系统设置中授权")
                else:
                    notify("未授予相机权限，无法拍照")
                return None
    except Exception as exc:  # noqa: BLE001 - 权限服务异常不应让页面崩溃
        notify(f"请求相机权限失败：{exc}")
        return None

    loop = asyncio.get_running_loop()
    result: asyncio.Future = loop.create_future()
    rotation = 0
    captured: bytes | None = None

    camera = fc.Camera(
        expand=True,
        preview_enabled=True,
        content=ft.Container(
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(color=ft.Colors.WHITE),
        ),
    )
    preview = ft.Image(
        src=_BLANK_IMAGE,
        visible=False,
        fit=ft.BoxFit.CONTAIN,
        expand=True,
        border_radius=8,
    )
    status_text = ft.Text("正在启动相机…", size=12)
    shutter = ft.FilledIconButton(
        icon=ft.Icons.PHOTO_CAMERA,
        tooltip="拍照",
        disabled=True,
    )
    rotate_left = ft.IconButton(
        ft.Icons.ROTATE_LEFT,
        tooltip="向左旋转",
        visible=False,
    )
    rotate_right = ft.IconButton(
        ft.Icons.ROTATE_RIGHT,
        tooltip="向右旋转",
        visible=False,
    )
    retake = ft.TextButton("重拍", visible=False)
    use_photo = ft.FilledButton("使用这张", visible=False)

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("拍照添加证明"),
        content=ft.Column(
            [
                ft.Container(
                    height=340,
                    bgcolor=ft.Colors.BLACK,
                    border_radius=8,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Stack([camera, preview], expand=True),
                ),
                status_text,
                ft.Row(
                    [rotate_left, shutter, rotate_right],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    [retake, use_photo],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            tight=True,
            spacing=10,
            width=360,
        ),
    )

    def finish(value: tuple[bytes, int] | None) -> None:
        if not result.done():
            result.set_result(value)

    def close(value: tuple[bytes, int] | None) -> None:
        try:
            camera.preview_enabled = False
            camera.visible = False
        except Exception:
            pass
        finish(value)
        page.pop_dialog()

    def on_dismiss(_):
        finish(None)

    dialog.on_dismiss = on_dismiss

    def show_camera() -> None:
        nonlocal captured
        captured = None
        preview.visible = False
        camera.visible = True
        shutter.visible = True
        shutter.disabled = False
        retake.visible = False
        use_photo.visible = False
        rotate_left.visible = False
        rotate_right.visible = False
        status_text.value = "将证明放入画面，点击快门"
        page.update()

    def show_captured(data: bytes) -> None:
        nonlocal captured, rotation
        captured = data
        rotation = 0
        camera.visible = False
        preview.src = render_preview(data, 0)
        preview.visible = True
        shutter.visible = False
        retake.visible = True
        use_photo.visible = True
        rotate_left.visible = True
        rotate_right.visible = True
        status_text.value = "请确认方向，必要时旋转图片"
        page.update()

    async def take_picture(_):
        shutter.disabled = True
        status_text.value = "正在拍照…"
        page.update()
        try:
            data = await camera.take_picture()
        except Exception as exc:  # noqa: BLE001
            status_text.value = f"拍照失败：{exc}"
            shutter.disabled = False
            page.update()
            return
        if data:
            show_captured(data)
        else:
            status_text.value = "没有获取到照片，请重试"
            shutter.disabled = False
            page.update()

    def rotate(delta: int):
        nonlocal rotation
        if captured is None:
            return
        rotation = (rotation + delta) % 360
        preview.src = render_preview(captured, rotation)
        page.update()

    async def start_camera() -> None:
        if result.done():
            return
        try:
            cameras = await camera.get_available_cameras()
        except Exception as exc:  # noqa: BLE001
            status_text.value = f"无法读取摄像头：{exc}"
            page.update()
            return
        if result.done():
            return
        if not cameras:
            status_text.value = "没有检测到可用摄像头"
            page.update()
            return
        selected = next(
            (item for item in cameras if item.lens_direction == fc.CameraLensDirection.BACK),
            cameras[0],
        )
        try:
            await camera.initialize(
                description=selected,
                resolution_preset=fc.ResolutionPreset.HIGH,
                enable_audio=False,
                image_format_group=fc.ImageFormatGroup.JPEG,
            )
        except Exception as exc:  # noqa: BLE001
            status_text.value = f"启动相机失败：{exc}"
            page.update()
            return
        if result.done():
            camera.preview_enabled = False
            camera.visible = False
            return
        camera.content = None
        status_text.value = "将证明放入画面，点击快门"
        shutter.disabled = False
        page.update()

    def cancel(_):
        close(None)

    def confirm(_):
        if captured is None:
            return
        close((captured, rotation))

    shutter.on_click = take_picture
    rotate_left.on_click = lambda _: rotate(-90)
    rotate_right.on_click = lambda _: rotate(90)
    retake.on_click = lambda _: show_camera()
    use_photo.on_click = confirm
    dialog.actions = [
        ft.TextButton("取消", on_click=cancel),
    ]

    page.show_dialog(dialog)
    page.update()
    await start_camera()
    try:
        return await result
    finally:
        try:
            camera.preview_enabled = False
            camera.visible = False
        except Exception:
            pass


async def choose_image_rotation(
    page: ft.Page,
    data: bytes,
    filename: str,
    notify,
) -> int | None:
    """Let the user rotate an imported image before it is stored."""
    loop = asyncio.get_running_loop()
    result: asyncio.Future = loop.create_future()
    rotation = 0

    try:
        first_preview = render_preview(data, 0)
    except Exception as exc:  # noqa: BLE001
        notify(f"无法预览图片：{exc}")
        return None

    preview = ft.Image(
        src=first_preview,
        fit=ft.BoxFit.CONTAIN,
        height=340,
        border_radius=8,
    )
    status_text = ft.Text("请确认图片方向，必要时旋转", size=12)

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("校正图片方向"),
        content=ft.Column(
            [
                preview,
                ft.Text(filename, size=12, color=ft.Colors.GREY_700),
                status_text,
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.ROTATE_LEFT,
                            tooltip="向左旋转",
                            on_click=lambda _: rotate(-90),
                        ),
                        ft.IconButton(
                            ft.Icons.ROTATE_RIGHT,
                            tooltip="向右旋转",
                            on_click=lambda _: rotate(90),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            tight=True,
            spacing=10,
            width=360,
        ),
        actions=[
            ft.TextButton("取消", on_click=lambda _: finish(None)),
            ft.FilledButton("使用这张", on_click=lambda _: finish(rotation)),
        ],
    )

    def finish(value: int | None) -> None:
        if result.done():
            return
        result.set_result(value)
        page.pop_dialog()

    def rotate(delta: int) -> None:
        nonlocal rotation
        rotation = (rotation + delta) % 360
        try:
            preview.src = render_preview(data, rotation)
        except Exception as exc:  # noqa: BLE001
            status_text.value = f"无法预览图片：{exc}"
        page.update()

    dialog.on_dismiss = lambda _: finish(None)
    page.show_dialog(dialog)
    page.update()
    return await result
