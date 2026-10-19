from __future__ import annotations

import json
import sqlite3
from datetime import UTC
from pathlib import Path

from core.points import points_to_1e4


def seed_rules_if_empty(conn: sqlite3.Connection, rules_path: Path | str) -> bool:
    existing = conn.execute("SELECT COUNT(*) FROM rule_versions").fetchone()[0]
    if existing:
        return False
    data = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    from datetime import datetime

    now = datetime.now(UTC).isoformat()
    sources = json.dumps(data.get("sources", []), ensure_ascii=False)
    cur = conn.execute(
        "INSERT INTO rule_versions(version, name, academic_year, raw_json,"
        " source_files_json, is_active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
        (
            data["version"],
            data["name"],
            data["version"],
            json.dumps(data, ensure_ascii=False),
            sources,
            now,
        ),
    )
    version_id = cur.lastrowid
    rows = []
    for node in data.get("nodes", []):
        cap = node.get("cap")
        rows.append(
            (
                node["id"],
                version_id,
                node.get("parent"),
                node["name"],
                node.get("level", ""),
                points_to_1e4(cap) if cap is not None else None,
                node.get("aggregation", "sum"),
                node.get("max_count"),
                node.get("dedupe_by"),
                node.get("calculator"),
                json.dumps(node.get("params") or {}, ensure_ascii=False),
                node.get("source_ref"),
                int(node.get("sort", 0)),
            )
        )
    conn.executemany(
        "INSERT INTO rule_nodes(id, version_id, parent_id, name, level, cap_1e4,"
        " aggregation, max_count, dedupe_by, calculator, params_json, source_ref, sort)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return True
