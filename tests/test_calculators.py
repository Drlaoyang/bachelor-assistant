from __future__ import annotations

import pytest

from core.calculators import calculate
from core.errors import CalculationError
from core.points import D


def params(rules, node_id):
    return rules.get(node_id).params


def test_competition_matrix(rules):
    p = params(rules, "innovation_base_competition_rule")
    assert calculate(
        "competition",
        p,
        {
            "competition_class": "A*",
            "award": "national_first",
            "team_size": 3,
            "undergraduate_rank": 1,
        },
    ) == D("5")
    assert calculate(
        "competition",
        p,
        {
            "competition_class": "A*",
            "award": "national_first",
            "team_size": 5,
            "undergraduate_rank": 4,
        },
    ) == D("4")
    assert calculate(
        "competition",
        p,
        {
            "competition_class": "A-",
            "award": "national_first",
            "team_size": 5,
            "undergraduate_rank": 4,
        },
    ) == D("2")
    assert calculate(
        "competition",
        p,
        {
            "competition_class": "B",
            "award": "national_second",
            "team_size": 4,
            "undergraduate_rank": 3,
        },
    ) == D("4") / D("3")
    assert calculate(
        "competition",
        p,
        {
            "competition_class": "C",
            "award": "national_first",
            "team_size": 6,
            "undergraduate_rank": 5,
        },
    ) == D("1")
    assert calculate(
        "competition",
        p,
        {
            "competition_class": "D",
            "award": "national_first",
            "team_size": 4,
            "undergraduate_rank": 4,
        },
    ) == D("0")
    assert calculate(
        "competition",
        p,
        {
            "competition_class": "E",
            "award": "national_first",
            "team_size": 4,
            "undergraduate_rank": 1,
        },
    ) == D("5") / D("16")
    assert calculate(
        "competition",
        p,
        {
            "competition_class": "E",
            "award": "national_first",
            "team_size": 4,
            "undergraduate_rank": 2,
        },
    ) == D("0")
    with pytest.raises(CalculationError):
        calculate(
            "competition",
            p,
            {
                "competition_class": "A*",
                "award": "national_first",
                "team_size": 5,
            },
        )


def test_tiered_award_sports_mapping(rules):
    p = params(rules, "physical_achievement_sports")
    base = {"region": "national", "track": "individual", "result_type": "rank"}
    assert calculate("tiered_award", p, {**base, "result": "first"}) == D("6")
    assert calculate(
        "tiered_award",
        p,
        {"region": "provincial", "track": "collective", "result_type": "rank", "result": "first"},
    ) == D("5.25")
    assert calculate(
        "tiered_award",
        p,
        {"region": "college", "track": "individual", "result_type": "rank", "result": "first"},
    ) == D("2.0")
    assert calculate(
        "tiered_award",
        p,
        {
            "region": "national",
            "track": "individual",
            "result_type": "rank",
            "result": "first",
            "fun": True,
        },
    ) == D("3")
    assert calculate(
        "tiered_award",
        p,
        {"region": "national", "track": "individual", "result_type": "prize", "result": "second"},
    ) == D("4.5")
    assert calculate(
        "tiered_award",
        p,
        {
            "region": "national",
            "track": "individual",
            "result_type": "rank",
            "result": "other",
            "rank_number": 9,
        },
    ) == D("0")


def test_tiered_award_arts_mapping(rules):
    p = params(rules, "arts_achievement_awards")

    def value(result, rank_number=None, result_type="rank"):
        inputs = {
            "region": "national",
            "track": "individual",
            "result_type": result_type,
            "result": result,
        }
        if rank_number is not None:
            inputs["rank_number"] = rank_number
        return calculate("tiered_award", p, inputs)

    assert value("first", 1) == D("6")
    assert value("second", 2) == D("5.25")
    assert value("third", 4) == D("3.75")
    assert value("other", 7) == D("3")
    assert value("other", 9) == D("0")
    assert value("special", result_type="prize") == D("6")


def test_internship(rules):
    p = params(rules, "innovation_bt_internship_rule")
    assert calculate("internship", p, {"region": "domestic", "months": 4}) == D("24")
    assert calculate("internship", p, {"region": "domestic", "months": 8}) == D("32")
    assert calculate("internship", p, {"region": "overseas", "months": 4}) == D("40")
    assert calculate("internship", p, {"region": "overseas", "months": 4, "online": True}) == D(
        "32"
    )
    assert calculate("internship", p, {"region": "domestic", "months": 2}) == D("0")


def test_research_defense(rules):
    p = params(rules, "innovation_bt_research_rule")
    assert calculate("research_defense", p, {"score": 40, "co_first_count": 2}) == D("20")
    assert calculate("research_defense", p, {"score": 30}) == D("30")
    with pytest.raises(CalculationError):
        calculate("research_defense", p, {"score": 41})


def test_entrepreneurship(rules):
    p = params(rules, "innovation_base_entrepreneurship_rule")
    assert calculate(
        "entrepreneurship",
        p,
        {"role": "legal_rep", "months": 12, "equity": 30, "profitable": True},
    ) == D("4")
    assert calculate(
        "entrepreneurship",
        p,
        {"role": "legal_rep", "months": 6, "equity": 30, "profitable": False},
    ) == D("2")
    assert calculate(
        "entrepreneurship",
        p,
        {"role": "legal_rep", "months": 12, "equity": 30, "profitable": False},
    ) == D("0")
    assert calculate(
        "entrepreneurship",
        p,
        {"role": "shareholder", "months": 12, "equity": 10, "profitable": True},
    ) == D("1")
    assert calculate(
        "entrepreneurship",
        p,
        {"role": "shareholder", "months": 12, "equity": 5, "profitable": True},
    ) == D("0")


def test_paper(rules):
    p = params(rules, "innovation_base_papers_rule")
    assert calculate("paper", p, {"journal_level": "core", "author_role": "first"}) == D("5")
    assert calculate(
        "paper",
        p,
        {"journal_level": "core", "author_role": "co_first", "co_first_count": 2},
    ) == D("2.5")
    assert calculate(
        "paper",
        p,
        {"journal_level": "other", "author_role": "first", "manual_points": 3},
    ) == D("3")
    assert calculate(
        "paper",
        p,
        {"journal_level": "core", "author_role": "other"},
    ) == D("0")


def test_thresholds(rules):
    volunteer = params(rules, "labor_base_volunteer")
    assert calculate("threshold", volunteer, {"hours": 21}) == D("5")
    assert calculate("threshold", volunteer, {"hours": 20}) == D("0")
    education = params(rules, "labor_base_education")
    assert calculate("threshold", education, {"hours": 9}) == D("5")
    assert calculate("threshold", education, {"hours": 8}) == D("0")


def test_literature(rules):
    p = params(rules, "arts_achievement_literature")
    assert calculate(
        "literature", p, {"platform": "national", "article_index": 5, "is_staff": True}
    ) == D("0")
    assert calculate(
        "literature", p, {"platform": "national", "article_index": 6, "is_staff": True}
    ) == D("5")
    assert calculate(
        "literature", p, {"platform": "campus", "article_index": 1, "is_staff": False}
    ) == D("3")


def test_overseas_long_and_short_boundary(rules):
    p = params(rules, "innovation_base_overseas_rule")
    assert calculate("overseas", p, {"duration_days": 90}) == D("3")
    assert calculate("overseas", p, {"duration_days": 91}) == D("5")


def test_team_award(rules):
    p = params(rules, "labor_ach_career_team")
    assert calculate("team_award", p, {"region": "national", "award": "first", "position": 1}) == D(
        "10"
    )
    assert calculate("team_award", p, {"region": "national", "award": "first", "position": 3}) == D(
        "7"
    )
    assert calculate(
        "team_award", p, {"region": "provincial", "award": "first", "position": 2}
    ) == D("7")
    assert calculate("team_award", p, {"region": "school", "award": "third", "position": 5}) == D(
        "0"
    )
