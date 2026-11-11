from __future__ import annotations

from io import BytesIO

import pymupdf
from PIL import Image

from core.image_tools import (
    JPEG_MIME,
    PDF_MIME,
    detect_evidence_type,
    prepare_image_for_ocr,
    prepare_image_for_storage,
    render_preview,
)


def _png(text: str = "证明") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=900, height=400)
    page.insert_text((60, 180), text, fontname="china-s", fontsize=34)
    data = page.get_pixmap(dpi=150, colorspace=pymupdf.csRGB, alpha=False).tobytes("png")
    doc.close()
    return data


def test_detect_evidence_type_for_pdf_and_images():
    pdf = pymupdf.open()
    pdf.new_page()
    pdf_bytes = pdf.tobytes()
    pdf.close()
    assert detect_evidence_type(pdf_bytes, "proof.pdf").mime == PDF_MIME

    png = _png()
    detected = detect_evidence_type(png, "proof.png")
    assert detected.kind == "image"
    assert detected.mime == "image/png"
    assert detected.suffix == ".png"

    image = Image.open(BytesIO(png)).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    detected = detect_evidence_type(buffer.getvalue(), "photo.jpg")
    assert detected.mime == JPEG_MIME
    assert detected.suffix == ".jpg"


def test_png_is_stored_as_jpeg():
    data, mime, suffix = prepare_image_for_storage(_png(), quality=92)
    assert mime == JPEG_MIME
    assert suffix == ".jpg"
    assert data.startswith(b"\xff\xd8")
    with Image.open(BytesIO(data)) as image:
        assert image.format == "JPEG"


def test_storage_applies_clockwise_rotation():
    png = _png()
    with Image.open(BytesIO(png)) as original:
        width, height = original.size
    stored, _, _ = prepare_image_for_storage(png, rotation=90)
    with Image.open(BytesIO(stored)) as image:
        assert image.size == (height, width)


def test_storage_downscales_and_flattens_transparency():
    image = Image.new("RGBA", (4000, 2000), (0, 0, 0, 0))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    stored, _, _ = prepare_image_for_storage(
        buffer.getvalue(), max_side=1000, quality=90
    )
    with Image.open(BytesIO(stored)) as result:
        assert result.mode == "RGB"
        assert max(result.size) == 1000
        assert result.getpixel((0, 0)) == (255, 255, 255)


def test_preview_and_ocr_helpers_return_png_jpeg():
    png = _png()
    preview = render_preview(png, rotation=90, max_side=120)
    assert preview.startswith(b"\xff\xd8")
    with Image.open(BytesIO(preview)) as image:
        assert max(image.size) <= 120

    ocr = prepare_image_for_ocr(png, rotation=90, max_side=800)
    assert ocr.startswith(b"\x89PNG")
    with Image.open(BytesIO(ocr)) as image:
        assert max(image.size) <= 800
