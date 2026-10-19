from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from core.rules import RuleSet


@dataclass
class ProofSuggestion:
    title: str | None = None
    rule_id: str | None = None
    activity_date: str | None = None
    text: str = ""
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _RuleKeywords:
    rule_id: str
    keywords: dict[str, int]


KEYWORDS: tuple[_RuleKeywords, ...] = (
    _RuleKeywords(
        "physical_base_fitness",
        {"体质健康": 5, "体测": 5, "体质测试": 5, "学生体质": 5},
    ),
    _RuleKeywords(
        "physical_base_sports_rule",
        {
            "体育": 2,
            "心理": 2,
            "运动会": 2,
            "篮球": 3,
            "足球": 3,
            "排球": 3,
            "羽毛球": 3,
            "乒乓球": 3,
            "拔河": 3,
            "跳绳": 3,
            "趣味运动": 3,
        },
    ),
    _RuleKeywords(
        "physical_achievement_sports",
        {
            "第一名": 4,
            "第二名": 4,
            "第三名": 4,
            "冠军": 4,
            "亚军": 4,
            "季军": 4,
            "一等奖": 1,
            "二等奖": 1,
            "三等奖": 1,
        },
    ),
    _RuleKeywords(
        "arts_base_activities_rule",
        {"美育": 5, "艺术": 3, "文艺": 3, "合唱": 3, "书画": 3, "摄影": 3, "舞蹈": 3},
    ),
    _RuleKeywords(
        "arts_achievement_awards",
        {
            "艺术展演": 5,
            "合唱比赛": 5,
            "器乐": 5,
            "舞蹈比赛": 5,
            "征文": 4,
            "演讲": 4,
            "辩论": 4,
            "摄影比赛": 4,
            "一等奖": 1,
            "二等奖": 1,
            "三等奖": 1,
        },
    ),
    _RuleKeywords(
        "arts_achievement_literature",
        {"新闻稿": 5, "文学作品": 5, "山大视点": 5, "山大日记": 5, "稿件": 4, "发表": 3},
    ),
    _RuleKeywords(
        "labor_base_social_work",
        {
            "班长": 4,
            "团支书": 4,
            "学生会": 4,
            "社团负责人": 4,
            "学生干部": 4,
            "宿舍长": 4,
            "任职": 3,
        },
    ),
    _RuleKeywords(
        "labor_base_practice",
        {"社会实践": 4, "实践考核": 4, "寒暑假社会实践": 4},
    ),
    _RuleKeywords(
        "labor_base_volunteer",
        {"志愿服务": 4, "志愿者": 3, "志愿时长": 5, "志愿活动": 3},
    ),
    _RuleKeywords(
        "labor_base_career_rule",
        {
            "生涯发展": 4,
            "就业": 3,
            "职业规划": 3,
            "简历": 3,
            "面试": 3,
            "讲座": 1,
            "培训": 1,
        },
    ),
    _RuleKeywords(
        "labor_base_dorm",
        {"宿舍卫生": 5, "文明宿舍": 4, "宿舍评比": 4},
    ),
    _RuleKeywords(
        "labor_base_education",
        {"劳动教育": 5, "劳动实践": 4, "劳动时长": 5},
    ),
    _RuleKeywords("labor_base_military", {"参军": 6, "入伍": 6}),
    _RuleKeywords(
        "labor_ach_social_work_collective",
        {"优秀班集体": 6, "先进班集体": 6, "优秀团支部": 6, "先进集体": 5},
    ),
    _RuleKeywords(
        "labor_ach_social_work_personal",
        {"优秀学生干部": 6, "优秀共青团员": 6, "先进个人": 5, "个人荣誉": 4},
    ),
    _RuleKeywords(
        "labor_ach_practice_rule",
        {"社会实践优秀": 6, "优秀实践": 5, "社会实践先进": 6, "优秀团队": 4},
    ),
    _RuleKeywords(
        "labor_ach_volunteer_team",
        {"优秀志愿者": 6, "志愿服务先进": 6, "志愿项目": 4},
    ),
    _RuleKeywords(
        "labor_ach_volunteer_competition",
        {"志愿项目大赛": 7, "志愿服务比赛": 7},
    ),
    _RuleKeywords(
        "labor_ach_dorm_star_rule",
        {"星级宿舍": 6, "五星级宿舍": 7, "四星级宿舍": 7, "三星级宿舍": 7},
    ),
    _RuleKeywords(
        "labor_ach_dorm_school_festival_rule",
        {"宿舍文化节": 6},
    ),
    _RuleKeywords(
        "labor_ach_career_team",
        {"职业规划大赛": 7, "简历大赛": 7, "面试大赛": 7, "生涯规划大赛": 7},
    ),
    _RuleKeywords(
        "labor_ach_open_source_rule",
        {"开源": 6, "开源安全": 7, "赛道卓越": 7, "赛道优胜": 7},
    ),
    _RuleKeywords("labor_ach_veteran", {"退役复学": 7, "退伍": 6}),
    _RuleKeywords(
        "innovation_base_projects_rule",
        {
            "创新创业训练计划": 7,
            "大创": 6,
            "国创": 6,
            "省创": 6,
            "校创": 6,
            "立项": 4,
            "结题": 4,
        },
    ),
    _RuleKeywords(
        "innovation_base_papers_rule",
        {
            "论文": 4,
            "期刊": 5,
            "CSSCI": 7,
            "SCI": 6,
            "SSCI": 7,
            "EI": 5,
            "第一作者": 5,
        },
    ),
    _RuleKeywords(
        "innovation_base_patents_rule",
        {"专利": 5, "发明专利": 7, "实用新型": 7, "外观专利": 7},
    ),
    _RuleKeywords(
        "innovation_base_competition_rule",
        {
            "互联网+": 7,
            "挑战杯": 7,
            "数学建模": 7,
            "竞赛": 3,
            "创新创业大赛": 6,
            "CTF": 6,
            "网络安全竞赛": 6,
            "一等奖": 1,
            "二等奖": 1,
            "三等奖": 1,
        },
    ),
    _RuleKeywords(
        "innovation_base_entrepreneurship_rule",
        {"创业": 4, "公司": 3, "法人": 5, "股东": 5, "营业执照": 6},
    ),
    _RuleKeywords(
        "innovation_base_overseas_rule",
        {"境外": 3, "访学": 5, "交流": 2, "国际": 2},
    ),
    _RuleKeywords(
        "innovation_bt_research_rule",
        {"答辩": 5, "科研成果": 6, "论文答辩": 7},
    ),
    _RuleKeywords(
        "innovation_bt_competition_rule",
        {
            "国家一等奖": 6,
            "国家二等奖": 6,
            "国家三等奖": 6,
            "主力队员": 6,
            "A类": 5,
            "A*": 5,
            "A-": 4,
        },
    ),
    _RuleKeywords(
        "innovation_bt_internship_rule",
        {"国际组织": 7, "实习": 2},
    ),
)

SKIP_LINE_WORDS = (
    "山东大学",
    "网络空间安全学院",
    "教务处",
    "团委",
    "学生工作部",
    "身份证号",
    "学号",
    "姓名",
    "盖章",
)

GENERIC_TITLES = {
    "参与证明",
    "活动证明",
    "参与证书",
    "参赛证明",
    "实践证明",
    "志愿服务证明",
    "社会实践证明",
    "实习证明",
    "工作证明",
    "证明",
    "证书",
    "荣誉证书",
    "获奖证书",
    "兹证明",
    "特此证明",
}

BODY_PATTERNS = (
    re.compile(
        r"(?:参加|参与|参加了|参与了)([^，。；,.;:\n]{4,60}?)(?=[，。；,.;:]|并|荣获|获得|取得|$)"
    ),
    re.compile(r"在([^，。；,.;:\n]{4,60}?)(?:中|上)(?=[，。；,.;:]|荣获|获得|取得|表现)"),
    re.compile(
        r"([^，。；,.;:\n]{4,60}?)(?:竞赛|比赛|活动|项目)(?:中|上)?(?:荣获|获得|取得)"
    ),
)

DATE_RE = re.compile(r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})")
MONTH_RE = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月")
TITLE_STRIP_RE = re.compile(r"(获奖|荣誉|参赛|活动|实践)?(证书|证明书|证明)$")


def extract_pdf_text(pdf_bytes: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


_ocr_engine = None


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr import RapidOCR

        _ocr_engine = RapidOCR(
            params={
                "Global.max_side_len": 1024,
                "Global.log_level": "error",
            }
        )
    return _ocr_engine


def ocr_pdf_text(
    pdf_bytes: bytes,
    *,
    dpi: int = 120,
    max_pages: int = 1,
) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if len(doc) == 0:
            return ""
        engine = _get_ocr_engine()
        lines: list[str] = []
        for page in doc[:max_pages]:
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
            result = engine(pix.tobytes("png"), use_cls=False)
            for text in getattr(result, "txts", None) or ():
                if text and text.strip():
                    lines.append(text.strip())
        return "\n".join(lines)
    finally:
        doc.close()


def _extract_date(text: str) -> str | None:
    match = DATE_RE.search(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    match = MONTH_RE.search(text)
    if match:
        year, month = (int(part) for part in match.groups())
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}-01"
    return None


def _clean_title(value: str) -> str | None:
    title = re.sub(r"\s+", " ", value).strip()
    title = re.sub(r"^(兹证明|特此证明)[:：]?", "", title).strip()
    title = title.strip("，。；：:、,.; ")
    if title.startswith("了"):
        title = title[1:].strip()
    if title.endswith(("中", "上")):
        title = title[:-1].strip()
    cleaned = TITLE_STRIP_RE.sub("", title).strip()
    if len(cleaned) >= 4:
        title = cleaned
    if len(title) < 4 or title in GENERIC_TITLES:
        return None
    return title


def _extract_title(text: str, rule_name: str | None) -> str | None:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]

    for pattern in BODY_PATTERNS:
        for line in lines:
            if line.startswith(("兹证明", "特此证明")):
                line = re.sub(r"^(兹证明|特此证明)[:：]?", "", line).strip()
            match = pattern.search(line)
            if match:
                title = _clean_title(match.group(1))
                if title:
                    return title

    best: tuple[int, int, str] | None = None
    for line in lines:
        if not line or len(line) < 4 or len(line) > 80:
            continue
        if line.startswith(("兹证明", "特此证明")):
            continue
        compact = re.sub(r"\s+", "", line)
        if compact in GENERIC_TITLES:
            continue
        if any(word in line for word in SKIP_LINE_WORDS) and not any(
            word in line
            for word in (
                "证书",
                "证明",
                "荣誉",
                "聘书",
                "获奖",
                "称号",
                "竞赛",
                "比赛",
                "活动",
                "项目",
            )
        ):
            continue
        score = 0
        if any(word in line for word in ("参加", "参与", "荣获", "获得", "取得")):
            score += 4
        if any(word in line for word in ("竞赛", "比赛")):
            score += 3
        if any(
            word in line
            for word in (
                "活动",
                "项目",
                "大会",
                "论坛",
                "培训",
                "实践",
                "志愿",
                "奖学金",
            )
        ):
            score += 2
        if any(word in line for word in ("证书", "证明", "荣誉", "聘书", "获奖", "称号")):
            score += 1
        if rule_name and len(rule_name) >= 3 and rule_name in line:
            score += 2
        if score >= 1:
            candidate = (score, len(line), line)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    if best is None:
        return None
    return _clean_title(best[2])


def suggest_from_text(text: str, rules: RuleSet) -> ProofSuggestion:
    normalized = unicodedata.normalize("NFKC", text).replace("\u3000", " ").strip()
    compact = re.sub(r"\s+", "", normalized)
    if len(compact) < 10:
        return ProofSuggestion(
            text=normalized,
            notes=["PDF 未包含可提取文字，可能是扫描件，请手动填写活动信息"],
        )

    scores: list[tuple[int, str]] = []
    for entry in KEYWORDS:
        if entry.rule_id not in rules.nodes:
            continue
        score = sum(weight for keyword, weight in entry.keywords.items() if keyword in compact)
        if score:
            scores.append((score, entry.rule_id))
    scores.sort(key=lambda item: (-item[0], item[1]))
    best_score, best_rule = scores[0] if scores else (0, None)

    rule_id = best_rule if best_score >= 3 else None
    rule_name = rules.get(rule_id).name if rule_id else None
    notes = []
    if rule_id is None:
        notes.append("未能自动识别活动类型，请手动选择")
    title = _extract_title(normalized, rule_name)
    if title is None:
        notes.append("未能自动识别活动名称，请手动填写")
    activity_date = _extract_date(compact)
    if activity_date is None:
        notes.append("未能自动识别活动日期，请手动填写")

    confidence = 0.0
    if best_score >= 6:
        confidence = 0.9
    elif best_score >= 3:
        confidence = 0.6
    return ProofSuggestion(
        title=title,
        rule_id=rule_id,
        activity_date=activity_date,
        text=normalized,
        confidence=confidence,
        notes=notes,
    )


def analyze_pdf(pdf_bytes: bytes, rules: RuleSet) -> ProofSuggestion:
    try:
        text = extract_pdf_text(pdf_bytes)
    except Exception as exc:
        return ProofSuggestion(notes=[f"无法解析 PDF：{exc}"])

    used_ocr = False
    if len(text.strip()) < 10:
        try:
            text = ocr_pdf_text(pdf_bytes)
            used_ocr = bool(text.strip())
        except Exception as exc:
            return ProofSuggestion(notes=[f"PDF 无文字，OCR 失败：{exc}"])

    suggestion = suggest_from_text(text, rules)
    if used_ocr:
        suggestion.notes.append("已使用本地 OCR 识别扫描件首页，请核对识别结果")
    return suggestion
