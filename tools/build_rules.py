#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.rules import load_rules  # noqa: E402


def main() -> int:
    source = ROOT / "rules" / "2026-2027.yaml"
    payload = json.dumps(load_rules(source).raw, ensure_ascii=False, indent=2) + "\n"
    for target in (
        source.with_suffix(".json"),
        ROOT / "src" / "assets" / "rules" / source.with_suffix(".json").name,
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
        print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
