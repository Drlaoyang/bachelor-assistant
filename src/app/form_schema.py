from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REGION_LABELS = {
    "national": "国家级",
    "provincial": "省级",
    "city": "地市级",
    "school": "校级",
    "academy": "书院级",
    "college": "院级",
}
TRACK_LABELS = {"individual": "个人项目", "collective": "集体项目"}
AWARD_LEVEL_LABELS = {
    "first": "一等奖/第一名",
    "second": "二等奖/第二名",
    "third": "三等奖/第三名",
    "other": "其他名次",
    "special": "特等奖",
}
COMPETITION_AWARD_LABELS = {
    "national_first": "国家一等奖",
    "national_second": "国家二等奖",
    "national_third_or_provincial_first": "国家三等奖/省级一等奖",
    "provincial_second_or_school_first": "省级二等奖/校级一等奖",
    "school_second": "校级二等奖",
}
COMPETITION_CLASS_LABELS = {
    "A": "A 类",
    "A*": "A* 类",
    "A-": "A- 类",
    "A-*": "A-* 类",
    "B": "B 类",
    "B*": "B* 类",
    "C": "C 类",
    "D": "D 类",
    "E": "E 类",
}
TEAM_ROLE_LABELS = {
    "leader": "负责人",
    "second": "第二成员",
    "third": "第三成员",
    "fourth_plus": "第四及以后",
    "individual": "个人",
}
PROJECT_ROLE_LABELS = {"host": "主持人", "first3": "前三位成员", "other": "其他成员"}
PATENT_TYPE_LABELS = {"invention": "发明专利", "utility": "实用新型", "appearance": "外观专利"}
STAR_LABELS = {"five": "五星级", "four": "四星级", "three": "三星级", "participation": "参与未获评"}
PLATFORM_LABELS = {
    "national": "新华网/人民网等国家级平台（5分）",
    "campus": "山大视点/山大日记等校区级（3分）",
    "school": "青春山大/学生在线等校内（2分）",
}
FITNESS_LABELS = {
    "优秀": "优秀（9）",
    "良好": "良好（6）",
    "合格": "合格（3）",
    "不合格": "不合格（0）",
}

GENERIC_LABELS: dict[str, str] = {}
GENERIC_LABELS.update(REGION_LABELS)
GENERIC_LABELS.update(AWARD_LEVEL_LABELS)
GENERIC_LABELS.update(COMPETITION_AWARD_LABELS)
GENERIC_LABELS.update(COMPETITION_CLASS_LABELS)
GENERIC_LABELS.update(TEAM_ROLE_LABELS)
GENERIC_LABELS.update(PROJECT_ROLE_LABELS)
GENERIC_LABELS.update(PATENT_TYPE_LABELS)
GENERIC_LABELS.update(STAR_LABELS)
GENERIC_LABELS.update(FITNESS_LABELS)
GENERIC_LABELS.update(
    {
        "head": "宿舍长",
        "member": "成员",
        "main": "主要负责人",
        "yes": "是",
        "no": "否",
        "rank": "按名次",
        "prize": "按等级奖",
        "domestic": "境内",
        "overseas": "境外",
        "excellent": "赛道卓越奖",
        "winner": "赛道优胜奖",
        "core": "中文核心（或相同等级）",
        "co_first": "共同第一作者",
        "legal_rep": "法人",
        "shareholder": "股东",
        "collective": "集体项目",
        "individual": "个人",
    }
)

DIMENSION_NAMES = {
    "region": "级别",
    "track": "项目类型",
    "award": "奖项",
    "role": "角色/位次",
    "level": "级别",
    "star": "星级",
    "patent_type": "专利类型",
    "transfer": "成果是否转让",
    "steps": "干部递减档位",
    "award_type": "项目类型",
    "position": "位次",
}

DIMENSION_LABELS: dict[str, dict[str, str]] = {
    "region": REGION_LABELS,
    "level": REGION_LABELS,
    "track": TRACK_LABELS,
    "award": AWARD_LEVEL_LABELS,
    "role": {
        **TEAM_ROLE_LABELS,
        **PROJECT_ROLE_LABELS,
        "head": "宿舍长",
        "member": "成员",
        "main": "主要负责人",
    },
    "star": STAR_LABELS,
    "patent_type": PATENT_TYPE_LABELS,
    "transfer": {"yes": "是", "no": "否"},
    "award_type": {"collective": "集体项目", "individual": "个人项目"},
}


def label_of(key: Any) -> str:
    text = str(key)
    return GENERIC_LABELS.get(text, text)


@dataclass
class FieldDef:
    key: str
    label: str
    kind: str  # text / number / select / bool
    options: list[tuple[str, str]] = field(default_factory=list)
    required: bool = True
    default: Any = None
    hint: str = ""


def _opts(keys, label_map: dict[str, str] | None = None) -> list[tuple[str, str]]:
    result = []
    for key in keys:
        text = str(key)
        if label_map and text in label_map:
            result.append((text, label_map[text]))
        else:
            result.append((text, label_of(text)))
    return result


def _matrix_level_options(table: dict, depth: int) -> list[str]:
    options: set[str] = set()

    def walk(node: Any, level: int) -> None:
        if not isinstance(node, dict):
            return
        if level == depth:
            options.update(str(k) for k in node)
            return
        for value in node.values():
            walk(value, level + 1)

    walk(table, 0)
    return sorted(options, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))


def _matrix_fields(params: dict) -> list[FieldDef]:
    dimensions = params.get("dimensions", [])
    table = params.get("table", {})
    fields = []
    for depth, dimension in enumerate(dimensions):
        key = str(dimension)
        fields.append(
            FieldDef(
                key=key,
                label=DIMENSION_NAMES.get(key, label_of(key)),
                kind="select",
                options=_opts(
                    _matrix_level_options(table, depth),
                    DIMENSION_LABELS.get(key),
                ),
            )
        )
    return fields


def fields_for(calculator: str, params: dict) -> list[FieldDef]:
    if calculator == "per_occurrence":
        return []
    if calculator == "boolean":
        return [FieldDef(key="value", label="是否满足条件", kind="bool", default=False)]
    if calculator == "lookup":
        field_name = str(params.get("field", "value"))
        if field_name == "grade":
            label_map = FITNESS_LABELS
        elif field_name == "region":
            label_map = REGION_LABELS
        else:
            label_map = None
        return [
            FieldDef(
                key=field_name,
                label=label_of(field_name),
                kind="select",
                options=_opts(params.get("table", {}).keys(), label_map),
            )
        ]
    if calculator == "threshold":
        field_name = str(params.get("field", "value"))
        threshold_labels = {"hours": "时长（小时）", "months": "月数"}
        return [
            FieldDef(
                key=field_name,
                label=threshold_labels.get(field_name, label_of(field_name)),
                kind="number",
                hint="小时/数量",
            )
        ]
    if calculator == "matrix":
        return _matrix_fields(params)
    if calculator == "gated_matrix":
        gate = FieldDef(
            key=str(params.get("gate_field", "hours")),
            label="服务/参与时长（小时）",
            kind="number",
            hint=f"需 {params.get('gate_op', 'gte')} {params.get('gate_value', '')}",
        )
        return [gate, *_matrix_fields(params)]
    if calculator == "tiered_award":
        return [
            FieldDef(
                key="region",
                label="级别",
                kind="select",
                options=_opts(params.get("table", {}).keys(), REGION_LABELS),
            ),
            FieldDef(
                key="track",
                label="项目类型",
                kind="select",
                options=_opts(TRACK_LABELS.keys(), TRACK_LABELS),
            ),
            FieldDef(
                key="result_type",
                label="获奖形式",
                kind="select",
                options=[("rank", "按名次"), ("prize", "按等级奖")],
                default="rank",
            ),
            FieldDef(
                key="result",
                label="名次/等级",
                kind="select",
                options=[
                    ("first", "第一名/一等奖"),
                    ("second", "第二名/二等奖"),
                    ("third", "第三名/三等奖"),
                    ("other", "其他名次"),
                ],
            ),
            FieldDef(
                key="rank_number",
                label="具体名次（其他名次时填写，前8名有效）",
                kind="number",
                required=False,
            ),
            FieldDef(
                key="fun", label="趣味类比赛（减半）", kind="bool", required=False, default=False
            ),
        ]
    if calculator == "competition":
        return [
            FieldDef(
                key="competition_class",
                label="竞赛类别",
                kind="select",
                options=_opts(params.get("class_divisors", {}).keys(), COMPETITION_CLASS_LABELS),
            ),
            FieldDef(
                key="award",
                label="获奖等级",
                kind="select",
                options=_opts(params.get("base_table", {}).keys(), COMPETITION_AWARD_LABELS),
            ),
            FieldDef(key="project_key", label="项目名称（同一项目只取最高奖）", kind="text"),
            FieldDef(
                key="team_size",
                label="团队本科生人数",
                kind="number",
                default=1,
                hint="个人项目填 1",
            ),
            FieldDef(
                key="undergraduate_rank",
                label="本人本科生位次",
                kind="number",
                default=1,
                hint="团队人数超过 3 人时必填；研究生混队填剔除研究生后的位次",
            ),
        ]
    if calculator == "breakthrough_competition":
        return [
            FieldDef(
                key="competition_class",
                label="竞赛类别",
                kind="select",
                options=_opts(params.get("awards", {}).keys(), COMPETITION_CLASS_LABELS),
            ),
            FieldDef(
                key="award",
                label="获奖等级",
                kind="select",
                options=[
                    ("national_first", "国家一等奖"),
                    ("national_second", "国家二等奖"),
                    ("national_third", "国家三等奖"),
                ],
            ),
            FieldDef(
                key="is_main_member", label="是否主力队员（前三名）", kind="bool", default=False
            ),
        ]
    if calculator == "research_defense":
        return [
            FieldDef(key="score", label="答辩分数（0-40）", kind="number"),
            FieldDef(key="co_first_count", label="共同第一作者人数", kind="number", default=1),
        ]
    if calculator == "internship":
        return [
            FieldDef(
                key="region",
                label="实习地区",
                kind="select",
                options=[("domestic", "境内"), ("overseas", "境外")],
            ),
            FieldDef(
                key="months",
                label="实习月数",
                kind="number",
                hint="境内3个月24/6个月32；境外3个月40",
            ),
            FieldDef(key="online", label="是否线上实习（减8分）", kind="bool", default=False),
        ]
    if calculator == "literature":
        return [
            FieldDef(
                key="platform",
                label="发布平台",
                kind="select",
                options=_opts(params.get("platform_points", {}).keys(), PLATFORM_LABELS),
            ),
            FieldDef(
                key="article_index",
                label="本篇是第几篇（供职平台/院学通社从第6篇起计分）",
                kind="number",
                default=1,
            ),
            FieldDef(
                key="is_staff",
                label="是否为供职平台投稿者/院学通社记者",
                kind="bool",
                default=False,
            ),
        ]
    if calculator == "team_award":
        return [
            FieldDef(
                key="region",
                label="级别",
                kind="select",
                options=_opts(params.get("base_table", {}).keys(), REGION_LABELS),
            ),
            FieldDef(
                key="award",
                label="奖项",
                kind="select",
                options=[
                    ("first", "一等奖"),
                    ("second", "二等奖"),
                    ("third", "三等奖"),
                ],
            ),
            FieldDef(
                key="position", label="本人位次（1=负责人，逐位递减1.5）", kind="number", default=1
            ),
        ]
    if calculator == "paper":
        return [
            FieldDef(
                key="journal_level",
                label="期刊等级",
                kind="select",
                options=[("core", "中文核心（或相同等级）"), ("other", "其他等级（手动填分）")],
            ),
            FieldDef(
                key="author_role",
                label="作者角色",
                kind="select",
                options=[
                    ("first", "第一作者"),
                    ("co_first", "共同第一作者"),
                    ("other", "其他作者"),
                ],
            ),
            FieldDef(key="co_first_count", label="共同第一作者人数", kind="number", default=1),
            FieldDef(
                key="manual_points",
                label="其他等级期刊分值（0-5）",
                kind="number",
                required=False,
                hint="仅期刊等级选“其他等级”时填写",
            ),
        ]
    if calculator == "entrepreneurship":
        return [
            FieldDef(
                key="role",
                label="角色",
                kind="select",
                options=[("legal_rep", "法人"), ("shareholder", "主要股东")],
            ),
            FieldDef(key="months", label="经营月数", kind="number"),
            FieldDef(key="equity", label="个人占股（%）", kind="number"),
            FieldDef(key="profitable", label="是否盈利", kind="bool", default=False),
        ]
    if calculator == "overseas":
        return [
            FieldDef(
                key="duration_days", label="交流天数（>90天最高5分，否则最高3分）", kind="number"
            ),
            FieldDef(key="points", label="实际赋分（可留空取上限）", kind="number", required=False),
        ]
    if calculator == "manual":
        return [FieldDef(key="points", label="分值", kind="number", hint="院级/其他由学院自定")]
    return [FieldDef(key="points", label="分值", kind="number", required=False)]
