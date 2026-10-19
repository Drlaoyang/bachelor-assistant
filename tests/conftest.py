from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.models import Activity  # noqa: E402
from core.rules import RuleSet, load_rules  # noqa: E402
from core.scoring import Scorer  # noqa: E402


@pytest.fixture(scope="session")
def rules() -> RuleSet:
    return load_rules(ROOT / "rules" / "2026-2027.yaml")


@pytest.fixture
def make_activity():
    def _make(rule_node_id: str, status: str = "confirmed", **inputs) -> Activity:
        return Activity(
            uuid=str(uuid.uuid4()),
            rule_node_id=rule_node_id,
            title=rule_node_id,
            status=status,
            inputs=inputs,
        )

    return _make


@pytest.fixture
def scorer(rules: RuleSet) -> Scorer:
    return Scorer(rules)
