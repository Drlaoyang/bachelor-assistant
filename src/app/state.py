from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from core.rules import RuleSet
from core.scoring import Scorer
from db.database import connect
from db.repository import Repository
from db.seed_rules import sync_rules
from device.paths import data_paths

DEFAULT_YEAR = "2026-2027"


def default_rules_path() -> str:
    from pathlib import Path

    src_dir = Path(__file__).resolve().parents[1]
    candidates = [
        src_dir / "assets" / "rules" / "2026-2027.json",
        src_dir.parent / "rules" / "2026-2027.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("找不到 rules/2026-2027.json")


class AppState:
    def __init__(self):
        self.paths = data_paths()
        self.conn = connect(self.paths["db"])
        sync_rules(self.conn, self._rules_path())
        self.repo = Repository(self.conn)
        self.rules: RuleSet = self.repo.load_active_ruleset()
        self.academic_year = self.repo.get_setting("academic_year", DEFAULT_YEAR) or DEFAULT_YEAR

    def _rules_path(self) -> str:
        import os

        return os.environ.get("LEDGER_RULES_JSON", default_rules_path())

    @property
    def statuses(self) -> tuple[str, ...]:
        return ("confirmed",)

    def compute(self):
        activities = self.repo.core_activities(self.academic_year)
        result = Scorer(self.rules).score(activities, self.statuses)
        counted: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for item in result.root.activity_scores:
            activity_uuid = item.activity.uuid
            if activity_uuid.endswith("::extra"):
                activity_uuid = activity_uuid[: -len("::extra")]
            counted[activity_uuid] += item.counted
        self.repo.set_computed(dict(counted))
        return result

    def core_activities(self):
        return self.repo.core_activities(self.academic_year)

    def set_year(self, year: str) -> None:
        self.academic_year = year
        self.repo.set_setting("academic_year", year)
