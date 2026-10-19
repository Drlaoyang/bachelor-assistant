from __future__ import annotations

import re
from pathlib import Path


def safe_stem(name: str) -> str:
    stem = Path(name).stem
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", stem).strip("._")
    return cleaned[:60] or "proof"


def pdf_page_count(pdf_path: Path) -> int:
    import pymupdf

    doc = pymupdf.open(str(pdf_path))
    try:
        return len(doc)
    finally:
        doc.close()


def pdf_to_jpgs(
    pdf_bytes: bytes,
    *,
    dpi: int = 120,
    quality: int = 82,
    pages: list[int] | None = None,
) -> list[tuple[int, bytes]]:
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        indexes = pages if pages is not None else list(range(len(doc)))
        images = []
        for index in indexes:
            if index < 0 or index >= len(doc):
                continue
            page = doc[index]
            pix = page.get_pixmap(
                dpi=dpi,
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            images.append((index + 1, pix.tobytes("jpeg", jpg_quality=quality)))
        return images
    finally:
        doc.close()


def export_jpgs(
    pdf_path: Path,
    out_dir: Path,
    *,
    dpi: int = 120,
    quality: int = 82,
    pages: list[int] | None = None,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    images = pdf_to_jpgs(
        pdf_path.read_bytes(),
        dpi=dpi,
        quality=quality,
        pages=pages,
    )
    stem = safe_stem(pdf_path.stem)
    paths = []
    for page_number, data in images:
        target = out_dir / f"{stem}_p{page_number}.jpg"
        target.write_bytes(data)
        paths.append(target)
    return paths
