from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps

PDF_MIME = "application/pdf"
PDF_SUFFIX = ".pdf"

IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}

JPEG_MIME = "image/jpeg"
JPEG_SUFFIX = ".jpg"


@dataclass(frozen=True)
class EvidenceType:
    mime: str
    suffix: str
    kind: str  # "pdf" or "image"


def detect_evidence_type(data: bytes, filename: str | None = None) -> EvidenceType:
    """Detect the real evidence format from its bytes, not its extension."""
    if data.startswith(b"%PDF-"):
        return EvidenceType(mime=PDF_MIME, suffix=PDF_SUFFIX, kind="pdf")

    try:
        with Image.open(BytesIO(data)) as image:
            fmt = (image.format or "").upper()
    except Exception as exc:  # noqa: BLE001 - 统一转成可读错误
        name = f"：{filename}" if filename else ""
        raise ValueError(f"不支持的证明文件格式{name}") from exc

    try:
        mime, suffix = IMAGE_FORMATS[fmt]
    except KeyError as exc:
        name = f"：{filename}" if filename else ""
        raise ValueError(f"不支持的图片格式 {fmt or '未知'}{name}") from exc
    return EvidenceType(mime=mime, suffix=suffix, kind="image")


def _open_upright(data: bytes) -> Image.Image:
    image = Image.open(BytesIO(data))
    image.load()
    return ImageOps.exif_transpose(image)


def _rotate(image: Image.Image, rotation: int) -> Image.Image:
    angle = int(rotation) % 360
    if angle == 0:
        return image
    # Positive rotation means clockwise in the UI; Pillow uses counter-clockwise.
    return image.rotate(-angle, expand=True)


def _resize(image: Image.Image, max_side: int) -> Image.Image:
    if max_side <= 0:
        return image
    if max(image.size) <= max_side:
        return image
    resized = image.copy()
    resized.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return resized


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")
    if image.mode in {"RGBA", "LA"}:
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def prepare_image_for_ocr(
    data: bytes,
    rotation: int = 0,
    max_side: int = 2400,
) -> bytes:
    """Return an upright PNG suitable for OCR."""
    image = _resize(_rotate(_open_upright(data), rotation), max_side)
    image = _flatten_to_rgb(image)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def render_preview(data: bytes, rotation: int = 0, max_side: int = 480) -> bytes:
    """Return a small JPEG preview for the UI."""
    image = _resize(_rotate(_open_upright(data), rotation), max_side)
    image = _flatten_to_rgb(image)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=82, optimize=True)
    return buffer.getvalue()


def prepare_image_for_storage(
    data: bytes,
    rotation: int = 0,
    max_side: int = 2400,
    quality: int = 92,
) -> tuple[bytes, str, str]:
    """Rotate, downscale and encode an image once for durable storage."""
    image = _resize(_rotate(_open_upright(data), rotation), max_side)
    image = _flatten_to_rgb(image)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue(), JPEG_MIME, JPEG_SUFFIX
