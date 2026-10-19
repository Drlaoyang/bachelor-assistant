from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_evidence_blob(evidence_dir: Path, data: bytes, suffix: str = ".pdf") -> tuple[str, str]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(data)
    relative_path = f"{digest}{suffix}"
    target = evidence_dir / relative_path
    if not target.exists():
        target.write_bytes(data)
    return digest, relative_path
