from __future__ import annotations

from core.points import D


def score(scorer, activities, include_statuses=("confirmed",)):
    return scorer.score(activities, include_statuses)


def counted(result, node_id):
    node = result.find(node_id)
    assert node is not None
    return node.counted


def test_empty_score(scorer):
    result = score(scorer, [])
    assert result.total == D("0")
    assert result.root.remaining == D("100")
    assert result.activity_count == 0


def test_physical_base_participation_and_fitness(scorer, make_activity):
    activities = [make_activity("physical_base_sports_rule") for _ in range(3)]
    result = score(scorer, activities)
    assert counted(result, "physical_base") == D("9")
    assert counted(result, "physical") == D("9")

    result = score(scorer, [*activities, make_activity("physical_base_sports_rule")])
    assert counted(result, "physical_base") == D("9")
    group = result.find("physical_base_sports")
    assert sum(item.counted for item in group.activity_scores) == D("9")
    assert any(
        item.counted == D("0") and "超过限项" in (item.reason or "")
        for item in group.activity_scores
    )

    result = score(scorer, [make_activity("physical_base_fitness", grade="优秀")])
    assert counted(result, "physical_base") == D("9")

    result = score(
        scorer,
        [
            make_activity("physical_base_fitness", grade="良好"),
            make_activity("physical_base_sports_rule"),
            make_activity("physical_base_sports_rule"),
        ],
    )
    assert counted(result, "physical_base") == D("9")
    assert result.find("physical_base").overflow == D("3")


def test_physical_achievement_takes_highest(scorer, make_activity):
    result = score(
        scorer,
        [
            make_activity(
                "physical_achievement_sports",
                region="national",
                track="individual",
                result_type="rank",
                result="first",
            ),
            make_activity(
                "physical_achievement_sports",
                region="provincial",
                track="collective",
                result_type="rank",
                result="first",
            ),
        ],
    )
    assert counted(result, "physical_achievement") == D("6")
    assert counted(result, "physical") == D("6")
    node = result.find("physical_achievement")
    assert node is not None
    assert [item.counted for item in node.activity_scores].count(D("6")) == 1
    assert [item.counted for item in node.activity_scores].count(D("0")) == 1


def test_arts_base_and_highest(scorer, make_activity):
    activities = [make_activity("arts_base_activities_rule") for _ in range(3)]
    result = score(scorer, activities)
    assert counted(result, "arts_base") == D("9")
    result = score(scorer, [*activities, make_activity("arts_base_activities_rule")])
    assert counted(result, "arts_base") == D("9")

    result = score(
        scorer,
        [
            make_activity(
                "arts_achievement_awards",
                region="national",
                track="individual",
                result_type="rank",
                result="first",
            ),
            make_activity(
                "arts_achievement_literature",
                platform="national",
                article_index=1,
                is_staff=False,
            ),
        ],
    )
    assert counted(result, "arts_achievement") == D("6")
    assert counted(result, "arts") == D("6")

    result = score(
        scorer,
        [
            make_activity(
                "arts_achievement_literature",
                platform="national",
                article_index=1,
                is_staff=False,
            )
        ],
    )
    assert counted(result, "arts_achievement") == D("5")


def test_labor_base_conditions_and_cap(scorer, make_activity):
    activities = [
        make_activity("labor_base_social_work", value=True),
        make_activity("labor_base_practice", value=True),
        make_activity("labor_base_volunteer", hours=25),
        make_activity("labor_base_dorm", value=True),
        make_activity("labor_base_education", hours=10),
        *[make_activity("labor_base_career_rule") for _ in range(5)],
    ]
    result = score(scorer, activities)
    assert counted(result, "labor_base") == D("15")
    assert result.find("labor_base").raw == D("30")
    assert result.find("labor_base").overflow == D("15")

    result = score(scorer, [make_activity("labor_base_volunteer", hours=20)])
    assert counted(result, "labor_base") == D("0")

    result = score(scorer, [make_activity("labor_base_military", value=True)])
    assert counted(result, "labor_base") == D("15")


def test_labor_achievement_groups_and_section_cap(scorer, make_activity):
    result = score(
        scorer,
        [
            make_activity("labor_ach_social_work_collective", region="national", steps=0),
            make_activity("labor_ach_social_work_personal", region="national"),
        ],
    )
    assert counted(result, "labor_ach_social_work") == D("10")
    assert counted(result, "labor_achievement") == D("10")

    result = score(
        scorer,
        [
            make_activity("labor_ach_social_work_base", value=True),
            make_activity("labor_ach_social_work_collective", region="school", steps=0),
        ],
    )
    assert counted(result, "labor_ach_social_work") == D("9.5")

    result = score(
        scorer,
        [
            make_activity("labor_ach_social_work_base", value=True),
            make_activity("labor_ach_social_work_collective", region="national", steps=0),
        ],
    )
    assert counted(result, "labor_ach_social_work") == D("10")
    assert result.find("labor_ach_social_work").overflow == D("4")

    result = score(
        scorer,
        [
            make_activity("labor_ach_practice_rule", region="national", role="leader"),
            make_activity(
                "labor_ach_volunteer_team",
                region="national",
                role="leader",
                hours=25,
            ),
        ],
    )
    assert counted(result, "labor_achievement") == D("10")

    result = score(
        scorer,
        [
            make_activity(
                "labor_ach_volunteer_team",
                region="national",
                role="leader",
                hours=10,
            )
        ],
    )
    assert counted(result, "labor_achievement") == D("0")

    result = score(
        scorer,
        [
            make_activity("labor_ach_career_team", region="national", award="first", position=3),
            make_activity("labor_ach_career_college", points=4),
        ],
    )
    assert counted(result, "labor_ach_career") == D("7")

    result = score(
        scorer,
        [
            make_activity("labor_ach_dorm_star_rule", star="five", role="head"),
            make_activity(
                "labor_ach_dorm_school_festival_rule",
                award_type="collective",
                award="first",
                role="main",
            ),
        ],
    )
    assert counted(result, "labor_ach_dorm") == D("8")

    result = score(
        scorer,
        [
            make_activity("labor_ach_open_source_rule", award="excellent", role="leader"),
        ],
    )
    assert counted(result, "labor_ach_open_source") == D("4")


def test_innovation_base_counts_and_cap(scorer, make_activity):
    result = score(
        scorer,
        [
            make_activity("innovation_base_projects_rule", level="national", role="host"),
            make_activity("innovation_base_papers_rule", journal_level="core", author_role="first"),
        ],
    )
    assert counted(result, "innovation_base") == D("5")
    assert result.find("innovation_base").raw == D("9")
    assert result.find("innovation_base").overflow == D("4")

    result = score(
        scorer,
        [
            make_activity(
                "innovation_base_papers_rule",
                journal_level="core",
                author_role="co_first",
                co_first_count=2,
            )
        ],
    )
    assert counted(result, "innovation_base") == D("2.5")

    result = score(
        scorer,
        [
            make_activity(
                "innovation_base_competition_rule",
                competition_class="A*",
                award="national_first",
                team_size=3,
                undergraduate_rank=1,
                project_key="p1",
            ),
            make_activity(
                "innovation_base_competition_rule",
                competition_class="A*",
                award="national_second",
                team_size=3,
                undergraduate_rank=1,
                project_key="p1",
            ),
            make_activity(
                "innovation_base_competition_rule",
                competition_class="A*",
                award="national_first",
                team_size=3,
                undergraduate_rank=1,
                project_key="p2",
            ),
        ],
    )
    assert counted(result, "innovation_base_competition") == D("5")
    assert result.find("innovation_base_competition").overflow == D("5")
    competition_scores = result.find("innovation_base_competition").activity_scores
    assert competition_scores[1].counted == D("0")
    assert "同一项目" in (competition_scores[1].reason or "")

    result = score(
        scorer,
        [
            make_activity(
                "innovation_base_entrepreneurship_rule",
                role="legal_rep",
                months=12,
                equity=30,
                profitable=True,
            ),
            make_activity(
                "innovation_base_overseas_rule",
                duration_days=120,
            ),
        ],
    )
    assert counted(result, "innovation_base") == D("5")


def test_innovation_breakthrough_modules(scorer, make_activity):
    result = score(
        scorer,
        [
            make_activity("innovation_bt_research_rule", score=40, co_first_count=2),
            make_activity(
                "innovation_bt_competition_rule",
                competition_class="A",
                award="national_first",
                is_main_member=True,
            ),
        ],
    )
    assert counted(result, "innovation_bt_research") == D("20")
    assert counted(result, "innovation_bt_competition") == D("40")
    assert counted(result, "innovation_breakthrough") == D("40")
    assert counted(result, "innovation") == D("40")

    result = score(
        scorer,
        [
            make_activity("innovation_base_papers_rule", journal_level="core", author_role="first"),
            make_activity("innovation_bt_research_rule", score=40),
        ],
    )
    assert counted(result, "innovation") == D("45")

    result = score(
        scorer,
        [
            make_activity(
                "innovation_bt_competition_rule",
                competition_class="A-",
                award="national_second",
                is_main_member=True,
            )
        ],
    )
    assert counted(result, "innovation_bt_competition") == D("10")

    result = score(
        scorer,
        [
            make_activity(
                "innovation_bt_competition_rule",
                competition_class="A",
                award="national_first",
                is_main_member=False,
            )
        ],
    )
    assert counted(result, "innovation_bt_competition") == D("0")

    result = score(
        scorer,
        [
            make_activity(
                "innovation_bt_internship_rule",
                region="overseas",
                months=4,
                online=True,
            )
        ],
    )
    assert counted(result, "innovation_bt_internship") == D("32")


def test_total_cap_100(scorer, make_activity):
    activities = [
        make_activity("physical_base_fitness", grade="优秀"),
        make_activity(
            "physical_achievement_sports",
            region="national",
            track="individual",
            result_type="rank",
            result="first",
        ),
        *[make_activity("arts_base_activities_rule") for _ in range(3)],
        make_activity(
            "arts_achievement_awards",
            region="national",
            track="individual",
            result_type="rank",
            result="first",
        ),
        make_activity("labor_base_military", value=True),
        make_activity("labor_ach_social_work_collective", region="national", steps=0),
        make_activity("innovation_base_papers_rule", journal_level="core", author_role="first"),
        make_activity("innovation_bt_research_rule", score=40),
    ]
    result = score(scorer, activities)
    assert counted(result, "physical") == D("15")
    assert counted(result, "arts") == D("15")
    assert counted(result, "labor") == D("25")
    assert counted(result, "innovation") == D("45")
    assert result.total == D("100")
    assert result.root.overflow == D("0")

    result = score(scorer, [*activities, make_activity("arts_base_activities_rule")])
    assert result.total == D("100")


def test_status_filtering_and_marginal_gain(scorer, make_activity):
    planned = make_activity("arts_base_activities_rule", status="planned")
    assert score(scorer, [planned]).total == D("0")
    assert score(scorer, [planned], include_statuses=("confirmed", "planned")).total == D("3")

    current = [make_activity("arts_base_activities_rule") for _ in range(3)]
    result = score(scorer, current)
    assert result.total == D("9")
    new = make_activity("arts_base_activities_rule")
    assert scorer.marginal_gain(new, current) == D("0")

    current = [
        make_activity(
            "arts_achievement_awards",
            region="provincial",
            track="individual",
            result_type="rank",
            result="first",
        )
    ]
    assert score(scorer, current).total == D("4.5")
    better = make_activity(
        "arts_achievement_awards",
        region="national",
        track="individual",
        result_type="rank",
        result="first",
    )
    assert scorer.marginal_gain(better, current) == D("1.5")
    worse = make_activity(
        "arts_achievement_awards",
        region="school",
        track="individual",
        result_type="rank",
        result="first",
    )
    assert scorer.marginal_gain(worse, current) == D("0")


def test_manual_override(scorer, make_activity):
    activity = make_activity(
        "physical_achievement_sports",
        region="national",
        track="individual",
        result_type="rank",
        result="first",
    )
    activity.override_points = D("4")
    activity.override_reason = "学院认定"
    result = score(scorer, [activity])
    assert counted(result, "physical_achievement") == D("4")
    assert result.find("physical_achievement").activity_scores[0].reason == "手动调整: 学院认定"
