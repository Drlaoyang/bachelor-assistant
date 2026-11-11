from __future__ import annotations

from dataclasses import dataclass

from core.image_tools import render_preview


@dataclass
class StagedEvidence:
    name: str
    data: bytes
    mime: str
    suffix: str
    rotation: int = 0

    @property
    def is_image(self) -> bool:
        return self.mime.startswith("image/")

    def rotate(self, delta: int) -> None:
        self.rotation = (self.rotation + int(delta)) % 360

    def preview(self, max_side: int = 96) -> bytes | None:
        if not self.is_image:
            return None
        return render_preview(self.data, self.rotation, max_side=max_side)
