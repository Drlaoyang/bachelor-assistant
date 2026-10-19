from __future__ import annotations

from pathlib import Path

from core.points import D
from core.rules import load_rules

ROOT = Path(__file__).resolve().parents[1]


def test_rule_tree_caps(rules):
    assert rules.version == "2026-2027"
    assert rules.root_id == "quality"
    assert rules.get("quality").cap == D("100")
    assert rules.get("physical").cap == D("15")
    assert rules.get("arts").cap == D("15")
    assert rules.get("labor").cap == D("25")
    assert rules.get("innovation").cap == D("45")
    assert len(rules.nodes) == 70


def test_all_nodes_reachable_and_leaves_have_calculators(rules):
    assert rules.is_leaf("physical_base_sports_rule")
    assert not rules.is_leaf("physical_base_sports")
    for node in rules.nodes.values():
        if rules.is_leaf(node.id):
            assert node.calculator
            assert node.cap is None
        else:
            assert node.calculator is None


def test_json_version_matches_yaml(rules):
    json_rules = load_rules(ROOT / "rules" / "2026-2027.json")
    assert json_rules.version == rules.version
    assert set(json_rules.nodes) == set(rules.nodes)


def test_category_section_caps_sum_to_category(rules):
    for category_id in ("physical", "arts", "labor", "innovation"):
        category = rules.get(category_id)
        child_total = sum((child.cap or D("0")) for child in rules.children_of(category_id))
        assert child_total == category.cap
