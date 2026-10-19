from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 2

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rule_versions (
    id INTEGER PRIMARY KEY,
    version TEXT NOT NULL,
    name TEXT NOT NULL,
    academic_year TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL,
    source_files_json TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rule_nodes (
    id TEXT NOT NULL,
    version_id INTEGER NOT NULL REFERENCES rule_versions(id),
    parent_id TEXT,
    name TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT '',
    cap_1e4 INTEGER,
    aggregation TEXT NOT NULL DEFAULT 'sum',
    max_count INTEGER,
    dedupe_by TEXT,
    calculator TEXT,
    params_json TEXT NOT NULL DEFAULT '{}',
    source_ref TEXT,
    sort INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (version_id, id)
);
CREATE TABLE IF NOT EXISTS activities (
    uuid TEXT PRIMARY KEY,
    student_id TEXT NOT NULL DEFAULT '',
    academic_year TEXT NOT NULL DEFAULT '',
    rule_version INTEGER NOT NULL REFERENCES rule_versions(id),
    rule_node_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    activity_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    inputs_json TEXT NOT NULL DEFAULT '{}',
    computed_points_1e4 INTEGER NOT NULL DEFAULT 0,
    override_points_1e4 INTEGER,
    override_reason TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    device_id TEXT NOT NULL DEFAULT '',
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_activities_year ON activities(academic_year, deleted_at);
CREATE INDEX IF NOT EXISTS idx_activities_rule ON activities(rule_node_id);
CREATE TABLE IF NOT EXISTS evidence (
    uuid TEXT PRIMARY KEY,
    activity_uuid TEXT NOT NULL REFERENCES activities(uuid),
    sha256 TEXT NOT NULL,
    original_name TEXT NOT NULL,
    mime TEXT NOT NULL DEFAULT 'application/pdf',
    size INTEGER NOT NULL DEFAULT 0,
    relative_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_evidence_activity ON evidence(activity_uuid, deleted_at);
CREATE INDEX IF NOT EXISTS idx_evidence_sha ON evidence(sha256);
"""


def migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.executescript(SCHEMA_V1)
        version = 1
    if version < 2:
        conn.execute(
            "UPDATE activities SET status = 'confirmed'"
            " WHERE status IN ('pending', 'planned')"
        )
        version = 2
    conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()
