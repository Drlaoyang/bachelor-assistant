from __future__ import annotations

import os
from pathlib import Path

APP_ID = "sdu-ce-ledger"


def get_data_dir() -> Path:
    env = os.environ.get("FLET_APP_STORAGE_DATA")
    if env:
        return Path(env)
    import platformdirs

    return Path(platformdirs.user_data_dir(APP_ID, APP_ID))


def data_paths(base: Path | None = None) -> dict[str, Path]:
    base = base or get_data_dir()
    paths = {
        "base": base,
        "db": base / "ledger.sqlite3",
        "evidence": base / "evidence",
        "backups": base / "backups",
        "exports": base / "exports",
    }
    for key in ("evidence", "backups", "exports"):
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths
