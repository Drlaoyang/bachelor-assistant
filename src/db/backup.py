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


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _parse_manifest(zf: zipfile.ZipFile) -> dict[str, Any]:
    try:
        manifest = json.loads(zf.read("manifest.json"))
    except KeyError as exc:
        raise ValueError("备份缺少 manifest.json") from exc
    if not isinstance(manifest, dict):
        raise ValueError("备份 manifest 格式错误")
    try:
        version = int(manifest.get("schema_version", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("备份版本号格式错误") from exc
    if version > SCHEMA_VERSION:
        raise ValueError("备份来自更新版本，无法导入")
    manifest["schema_version"] = version
    return manifest


def _parse_tables(
    zf: zipfile.ZipFile, conn: sqlite3.Connection
) -> dict[str, list[dict[str, Any]]]:
    allowed_columns = {table: _table_columns(conn, table) for table in TABLES}
    tables_data: dict[str, list[dict[str, Any]]] = {}
    for name in zf.namelist():
        if not (name.startswith("data/") and name.endswith(".json")):
            continue
        table = Path(name).stem
        if table not in TABLES:
            raise ValueError(f"备份包含未知数据表: {table}")
        try:
            rows = json.loads(zf.read(name))
        except json.JSONDecodeError as exc:
            raise ValueError(f"备份表 {table} 不是有效 JSON") from exc
        if not isinstance(rows, list):
            raise ValueError(f"备份表 {table} 格式错误")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"备份表 {table} 含无效行")
            unknown = set(row) - allowed_columns[table]
            if unknown:
                raise ValueError(
                    f"备份表 {table} 含未知字段: {', '.join(sorted(unknown))}"
                )
        tables_data[table] = rows
    return tables_data


def import_backup(
    conn: sqlite3.Connection, evidence_dir: Path, source: Path, backups_dir: Path
) -> Path:
    with zipfile.ZipFile(source) as zf:
        _parse_manifest(zf)
        tables_data = _parse_tables(zf, conn)
        blob_names = [name for name in zf.namelist() if name.startswith("blobs/")]

    evidence_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _auto_backup(conn, evidence_dir, backups_dir)
    with zipfile.ZipFile(source) as zf:
        for name in blob_names:
            target = evidence_dir / Path(name).name
            target.write_bytes(zf.read(name))

    with conn:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
        for table, rows in tables_data.items():
            for row in rows:
                columns = ", ".join(row.keys())
                placeholders = ", ".join("?" for _ in row)
                conn.execute(
                    f"INSERT INTO {table}({columns}) VALUES ({placeholders})",
                    list(row.values()),
                )
    return backup_path
