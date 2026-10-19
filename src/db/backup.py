from __future__ import annotations

import csv
import io
import json
import sqlite3
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .migrations import SCHEMA_VERSION

TABLES = ("rule_versions", "rule_nodes", "activities", "evidence", "settings", "meta")


def _dump_table(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(row) for row in rows]


def _activities_csv(conn: sqlite3.Connection) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["学号", "学年", "标题", "规则", "日期", "状态", "计入分值(万分)", "证明数", "备注"]
    )
    rows = conn.execute(
        "SELECT a.*, (SELECT COUNT(*) FROM evidence e WHERE e.activity_uuid = a.uuid"
        " AND e.deleted_at IS NULL) AS evidence_count FROM activities a"
        " WHERE a.deleted_at IS NULL ORDER BY a.activity_date, a.created_at"
    ).fetchall()
    for row in rows:
        writer.writerow(
            [
                row["student_id"],
                row["academic_year"],
                row["title"],
                row["rule_node_id"],
                row["activity_date"],
                row["status"],
                row["computed_points_1e4"],
                row["evidence_count"],
                row["notes"],
            ]
        )
    return buffer.getvalue()


def export_backup(conn: sqlite3.Connection, evidence_dir: Path, target: Path) -> None:
    now = datetime.now(UTC).isoformat()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": now,
        "format": "full-snapshot-v1",
    }
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for table in TABLES:
            zf.writestr(
                f"data/{table}.json",
                json.dumps(_dump_table(conn, table), ensure_ascii=False, indent=2),
            )
        zf.writestr("activities.csv", _activities_csv(conn))
        for file in evidence_dir.iterdir():
            if file.is_file():
                zf.write(file, f"blobs/{file.name}")


def _auto_backup(conn: sqlite3.Connection, evidence_dir: Path, backups_dir: Path) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backups_dir / f"backup_before_restore_{stamp}.zip"
    export_backup(conn, evidence_dir, target)
    return target


def import_backup(
    conn: sqlite3.Connection, evidence_dir: Path, source: Path, backups_dir: Path
) -> Path:
    with zipfile.ZipFile(source) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        if manifest.get("schema_version", 0) > SCHEMA_VERSION:
            raise ValueError("备份来自更新版本，无法导入")
        tables_data = {
            name.split("/")[1][:-5]: json.loads(zf.read(name))
            for name in zf.namelist()
            if name.startswith("data/") and name.endswith(".json")
        }
        blob_names = [name for name in zf.namelist() if name.startswith("blobs/")]
        evidence_dir.mkdir(parents=True, exist_ok=True)
        for name in blob_names:
            target = evidence_dir / Path(name).name
            target.write_bytes(zf.read(name))

    backup_path = _auto_backup(conn, evidence_dir, backups_dir)
    with conn:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
        for table, rows in tables_data.items():
            if table not in TABLES:
                continue
            for row in rows:
                columns = ", ".join(row.keys())
                placeholders = ", ".join("?" for _ in row)
                conn.execute(
                    f"INSERT INTO {table}({columns}) VALUES ({placeholders})",
                    list(row.values()),
                )
    return backup_path
