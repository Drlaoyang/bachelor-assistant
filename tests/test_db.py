from __future__ import annotations

from pathlib import Path

import pytest

from db.backup import export_backup, import_backup
from db.database import connect
from db.repository import Repository
from db.seed_rules import seed_rules_if_empty

ROOT = Path(__file__).resolve().parents[1]
RULES_JSON = ROOT / "rules" / "2026-2027.json"


@pytest.fixture
def repo(tmp_path):
    conn = connect(tmp_path / "ledger.sqlite3")
    assert seed_rules_if_empty(conn, RULES_JSON)
    yield Repository(conn), tmp_path
    conn.close()


def test_seed_rules(repo):
    repository, _ = repo
    version = repository.active_rule_version()
    assert version is not None
    assert version["version"] == "2026-2027"
    nodes = repository.rule_nodes(version["id"])
    assert len(nodes) == 70
    leaves = repository.rule_leaves(version["id"])
    assert all(row["calculator"] for row in leaves)
    assert not seed_rules_if_empty(repository.conn, RULES_JSON)


def test_settings_and_meta(repo):
    repository, _ = repo
    assert repository.get_setting("student_id") is None
    repository.set_setting("student_id", "20220001")
    assert repository.get_setting("student_id") == "20220001"
    first = repository.device_id()
    assert repository.device_id() == first


def test_activity_crud_and_filters(repo):
    repository, _ = repo
    activity_uuid = repository.create_activity(
        rule_node_id="physical_base_sports_rule",
        title="校运动会志愿服务",
        status="confirmed",
        inputs={},
        activity_date="2026-10-01",
        academic_year="2026-2027",
        student_id="20220001",
    )
    repository.add_evidence(
        activity_uuid=activity_uuid,
        sha256="a" * 64,
        original_name="证明.pdf",
        size=10,
        relative_path="a.pdf",
    )
    rows = repository.list_activities(academic_year="2026-2027")
    assert len(rows) == 1
    assert rows[0]["evidence_count"] == 1
    assert repository.list_activities(academic_year="2026-2027", has_evidence=True)
    assert not repository.list_activities(academic_year="2026-2027", has_evidence=False)
    assert repository.list_activities(keyword="运动会")
    assert repository.list_activities(academic_year="2025-2026") == []

    repository.update_activity(activity_uuid, status="rejected")
    assert repository.get_activity(activity_uuid)["status"] == "rejected"

    repository.soft_delete_activity(activity_uuid)
    assert repository.list_activities() == []
    assert repository.list_evidence(activity_uuid) == []

    core = repository.core_activities("2026-2027")
    assert core == []


def test_core_activity_conversion(repo):
    repository, _ = repo
    activity_uuid = repository.create_activity(
        rule_node_id="physical_base_fitness",
        title="体测",
        status="confirmed",
        inputs={"grade": "优秀"},
        academic_year="2026-2027",
        override_points="6",
        override_reason="学院认定良好",
    )
    rows = repository.list_activities()
    core = repository.to_core_activity(rows[0])
    assert core.uuid == activity_uuid
    assert core.inputs == {"grade": "优秀"}
    assert str(core.override_points) == "6"
    assert core.override_reason == "学院认定良好"


def test_backup_roundtrip(repo, tmp_path):
    repository, data_dir = repo
    evidence_dir = data_dir / "evidence"
    backups_dir = data_dir / "backups"
    evidence_dir.mkdir(exist_ok=True)
    backups_dir.mkdir(exist_ok=True)
    (evidence_dir / "blob1.pdf").write_bytes(b"pdf-content")
    repository.set_setting("student_id", "20220001")
    repository.create_activity(
        rule_node_id="physical_base_sports_rule",
        title="活动A",
        status="confirmed",
        inputs={},
        academic_year="2026-2027",
    )

    archive = data_dir / "backup.zip"
    export_backup(repository.conn, evidence_dir, archive)
    assert archive.exists()

    fresh_conn = connect(data_dir / "restored.sqlite3")
    backup_path = import_backup(fresh_conn, evidence_dir, archive, backups_dir)
    assert backup_path.exists()
    fresh = Repository(fresh_conn)
    assert fresh.get_setting("student_id") == "20220001"
    assert len(fresh.list_activities()) == 1
    assert fresh.list_activities()[0]["title"] == "活动A"
    fresh_conn.close()
