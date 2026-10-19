from __future__ import annotations

import json
import sqlite3
import uuid as uuidlib
from datetime import UTC, datetime
from typing import Any

from core.models import Activity as CoreActivity
from core.points import points_from_1e4, points_to_1e4
from core.rules import RuleSet


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # --------------------------------------------------------------
    # settings / meta
    # --------------------------------------------------------------
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def device_id(self) -> str:
        value = self.get_meta("device_id")
        if not value:
            value = str(uuidlib.uuid4())
            self.set_meta("device_id", value)
        return value

    # --------------------------------------------------------------
    # rules
    # --------------------------------------------------------------
    def active_rule_version(self) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM rule_versions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()

    def load_active_ruleset(self) -> RuleSet:
        row = self.active_rule_version()
        if row is None:
            raise RuntimeError("数据库中没有规则版本，请先导入规则")
        return RuleSet(json.loads(row["raw_json"]))

    def list_rule_versions(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT id, version, name, academic_year, is_active, created_at"
            " FROM rule_versions ORDER BY id"
        ).fetchall()

    def rule_nodes(self, version_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM rule_nodes WHERE version_id = ? ORDER BY sort, id", (version_id,)
        ).fetchall()

    def rule_leaves(self, version_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT r.* FROM rule_nodes r WHERE r.version_id = ? AND r.calculator IS NOT NULL"
            " AND NOT EXISTS (SELECT 1 FROM rule_nodes c WHERE c.version_id = r.version_id"
            " AND c.parent_id = r.id) ORDER BY r.sort, r.id",
            (version_id,),
        ).fetchall()

    # --------------------------------------------------------------
    # activities
    # --------------------------------------------------------------
    def create_activity(
        self,
        *,
        rule_node_id: str,
        title: str,
        status: str,
        inputs: dict[str, Any],
        activity_date: str = "",
        notes: str = "",
        override_points: Any = None,
        override_reason: str | None = None,
        academic_year: str = "",
        student_id: str = "",
    ) -> str:
        version = self.active_rule_version()
        if version is None:
            raise RuntimeError("没有可用规则版本")
        new_uuid = str(uuidlib.uuid4())
        now = _now()
        self.conn.execute(
            "INSERT INTO activities(uuid, student_id, academic_year, rule_version,"
            " rule_node_id, title, activity_date, status, inputs_json,"
            " override_points_1e4, override_reason, notes, created_at, updated_at, device_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                new_uuid,
                student_id,
                academic_year,
                version["id"],
                rule_node_id,
                title,
                activity_date,
                status,
                json.dumps(inputs, ensure_ascii=False),
                points_to_1e4(override_points) if override_points is not None else None,
                override_reason,
                notes,
                now,
                now,
                self.device_id(),
            ),
        )
        self.conn.commit()
        return new_uuid

    def update_activity(self, activity_uuid: str, **fields: Any) -> None:
        if "inputs" in fields:
            fields["inputs_json"] = json.dumps(fields.pop("inputs"), ensure_ascii=False)
        if "override_points" in fields:
            value = fields.pop("override_points")
            fields["override_points_1e4"] = points_to_1e4(value) if value is not None else None
        fields["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = [*fields.values(), activity_uuid]
        self.conn.execute(f"UPDATE activities SET {assignments} WHERE uuid = ?", values)
        self.conn.commit()

    def soft_delete_activity(self, activity_uuid: str) -> None:
        now = _now()
        self.conn.execute(
            "UPDATE activities SET deleted_at = ?, updated_at = ? WHERE uuid = ?",
            (now, now, activity_uuid),
        )
        self.conn.execute(
            "UPDATE evidence SET deleted_at = ? WHERE activity_uuid = ? AND deleted_at IS NULL",
            (now, activity_uuid),
        )
        self.conn.commit()

    def get_activity(self, activity_uuid: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM activities WHERE uuid = ?", (activity_uuid,)
        ).fetchone()

    def list_activities(
        self,
        academic_year: str | None = None,
        statuses: tuple[str, ...] | None = None,
        keyword: str | None = None,
        has_evidence: bool | None = None,
        category: str | None = None,
    ) -> list[sqlite3.Row]:
        clauses = ["a.deleted_at IS NULL"]
        params: list[Any] = []
        if academic_year:
            clauses.append("a.academic_year = ?")
            params.append(academic_year)
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            clauses.append(f"a.status IN ({placeholders})")
            params.extend(statuses)
        if keyword:
            clauses.append("a.title LIKE ?")
            params.append(f"%{keyword}%")
        if has_evidence is True:
            clauses.append(
                "EXISTS (SELECT 1 FROM evidence e WHERE e.activity_uuid = a.uuid"
                " AND e.deleted_at IS NULL)"
            )
        elif has_evidence is False:
            clauses.append(
                "NOT EXISTS (SELECT 1 FROM evidence e WHERE e.activity_uuid = a.uuid"
                " AND e.deleted_at IS NULL)"
            )
        if category:
            version = self.active_rule_version()
            if version is not None:
                ruleset = self.load_active_ruleset()
                leaf_ids = []
                for cat in ruleset.children_of(ruleset.root_id):
                    if cat.id == category:
                        leaf_ids = self._leaf_ids(ruleset, cat.id)
                        break
                if leaf_ids:
                    placeholders = ",".join("?" for _ in leaf_ids)
                    clauses.append(f"a.rule_node_id IN ({placeholders})")
                    params.extend(leaf_ids)
        sql = (
            "SELECT a.*, (SELECT COUNT(*) FROM evidence e WHERE e.activity_uuid = a.uuid"
            " AND e.deleted_at IS NULL) AS evidence_count"
            " FROM activities a WHERE "
            + " AND ".join(clauses)
            + " ORDER BY a.activity_date DESC, a.created_at DESC"
        )
        return self.conn.execute(sql, params).fetchall()

    def _leaf_ids(self, ruleset: RuleSet, node_id: str) -> list[str]:
        result = []
        for child in ruleset.children_of(node_id):
            if ruleset.is_leaf(child.id):
                result.append(child.id)
            else:
                result.extend(self._leaf_ids(ruleset, child.id))
        return result

    def set_computed(self, computed: dict[str, Any]) -> None:
        now = _now()
        self.conn.executemany(
            "UPDATE activities SET computed_points_1e4 = ?, updated_at = ? WHERE uuid = ?",
            [(points_to_1e4(points), now, uuid) for uuid, points in computed.items()],
        )
        self.conn.commit()

    # --------------------------------------------------------------
    # evidence
    # --------------------------------------------------------------
    def add_evidence(
        self,
        *,
        activity_uuid: str,
        sha256: str,
        original_name: str,
        size: int,
        relative_path: str,
    ) -> str:
        new_uuid = str(uuidlib.uuid4())
        self.conn.execute(
            "INSERT INTO evidence(uuid, activity_uuid, sha256, original_name, mime,"
            " size, relative_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                new_uuid,
                activity_uuid,
                sha256,
                original_name,
                "application/pdf",
                size,
                relative_path,
                _now(),
            ),
        )
        self.conn.commit()
        return new_uuid

    def list_evidence(self, activity_uuid: str | None = None) -> list[sqlite3.Row]:
        if activity_uuid is None:
            return self.conn.execute(
                "SELECT e.*, a.title AS activity_title FROM evidence e"
                " JOIN activities a ON a.uuid = e.activity_uuid"
                " WHERE e.deleted_at IS NULL AND a.deleted_at IS NULL"
                " ORDER BY e.created_at DESC"
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM evidence WHERE activity_uuid = ? AND deleted_at IS NULL"
            " ORDER BY created_at",
            (activity_uuid,),
        ).fetchall()

    def soft_delete_evidence(self, evidence_uuid: str) -> None:
        self.conn.execute(
            "UPDATE evidence SET deleted_at = ? WHERE uuid = ?", (_now(), evidence_uuid)
        )
        self.conn.commit()

    # --------------------------------------------------------------
    # conversions
    # --------------------------------------------------------------
    def to_core_activity(self, row: sqlite3.Row) -> CoreActivity:
        override = row["override_points_1e4"]
        return CoreActivity(
            uuid=row["uuid"],
            rule_node_id=row["rule_node_id"],
            title=row["title"],
            status=row["status"],
            inputs=json.loads(row["inputs_json"] or "{}"),
            override_points=points_from_1e4(override) if override is not None else None,
            override_reason=row["override_reason"],
            academic_year=row["academic_year"],
            student_id=row["student_id"],
            activity_date=row["activity_date"],
            notes=row["notes"],
        )

    def core_activities(
        self, academic_year: str, statuses: tuple[str, ...] | None = None
    ) -> list[CoreActivity]:
        rows = self.list_activities(academic_year=academic_year, statuses=statuses)
        return [self.to_core_activity(row) for row in rows]
