from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from core.image_tools import detect_evidence_type, prepare_image_for_ocr
from core.rules import RuleSet

MAX_OCR_PAGES = 5


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
            "运动会": 4,
            "秋日运动会": 5,
            "乐享运动": 4,
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
        {"社会实践": 4, "实践考核": 4, "寒暑假社会实践": 4, "三下乡": 4},
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
            "大赛": 2,
            "技能大赛": 6,
            "网络安全大赛": 6,
            "学科竞赛": 4,
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
        r"(?:活动名称|项目名称|竞赛名称|比赛名称)[:：]?\s*([^\n，。；,.;:]{2,60})"
    ),
    re.compile(
        r"(?:参加|参与|参加了|参与了)(?!证明)([^，。；,.;:\n]{4,60}?)(?=[，。；,.;:]|并|荣获|获得|取得|$)"
    ),
    re.compile(r"在([^。；\n]{4,80}?)(?:中|上)(?=[，。；,.;:]|荣获|获得|取得|表现)"),
    re.compile(
        r"([^，。；,.;:\n]{4,60}?)(?:竞赛|比赛|活动|项目)(?:中|上)?(?:荣获|获得|取得)"
    ),
)

TITLE_PREFIX_RE = re.compile(r"^(?:山东大学网络空间安全学院|山东大学|网络空间安全学院)+")

DATE_RE = re.compile(r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})")
MONTH_RE = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月")
DATE_MD_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日")
TITLE_STRIP_RE = re.compile(r"(获奖|荣誉|参赛|活动|实践)?(证书|证明书|证明)$")


def extract_pdf_text(pdf_bytes: bytes, page_indexes: list[int] | None = None) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_indexes is None:
            pages = list(doc)
        else:
            pages = [doc[index] for index in page_indexes if 0 <= index < len(doc)]
        return "\n".join(page.get_text("text") for page in pages)
    finally:
        doc.close()


_ocr_engines: dict[int, object] = {}


def _get_ocr_engine(max_side: int = 1024):
    engine = _ocr_engines.get(max_side)
    if engine is None:
        from rapidocr import RapidOCR

        engine = RapidOCR(
            params={
                "Global.max_side_len": max_side,
                "Global.log_level": "error",
            }
        )
        _ocr_engines[max_side] = engine
    return engine


def _render_png(page, dpi: int) -> bytes:
    import pymupdf

    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    return pix.tobytes("png")


def _ocr_png(engine, png: bytes, *, use_cls: bool) -> str:
    result = engine(png, use_cls=use_cls)
    lines = []
    for text in getattr(result, "txts", None) or ():
        if text and text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


def _text_score(text: str) -> int:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    bonus = 5 * sum(
        1
        for word in (
            "参加",
            "参与",
            "竞赛",
            "比赛",
            "活动",
            "志愿",
            "实践",
            "证书",
            "证明",
            "荣获",
            "获得",
        )
        if word in text
    )
    return cjk + bonus


def _needs_quality(text: str) -> bool:
    return _text_score(text) < 20 or not any(
        word in text
        for word in (
            "参加",
            "参与",
            "竞赛",
            "比赛",
            "活动",
            "志愿",
            "实践",
            "证书",
            "证明",
            "荣获",
            "获得",
        )
    )


def _rotate_png(png: bytes, angle: int) -> bytes:
    from io import BytesIO

    from PIL import Image

    image = Image.open(BytesIO(png))
    image = image.rotate(angle, expand=True)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _ocr_page(page, dpi: int, *, fast_only: bool = False) -> str:
    fast_engine = _get_ocr_engine(1024)
    png = _render_png(page, dpi)
    text = _ocr_png(fast_engine, png, use_cls=fast_only)
    if fast_only or not _needs_quality(text):
        return text

    quality_engine = _get_ocr_engine(1600)
    best_text = text
    best_score = _text_score(text)
    quality_png = _render_png(page, 200)
    for angle in (0, 90, 180, 270):
        candidate_png = quality_png if angle == 0 else _rotate_png(quality_png, angle)
        candidate = _ocr_png(quality_engine, candidate_png, use_cls=True)
        score = _text_score(candidate)
        if score > best_score:
            best_text = candidate
            best_score = score
    return best_text


def ocr_image_text(png_bytes: bytes) -> str:
    """OCR one already-upright image. Direction is corrected manually by the user."""
    fast_engine = _get_ocr_engine(1024)
    text = _ocr_png(fast_engine, png_bytes, use_cls=False)
    if not _needs_quality(text):
        return text
    quality_engine = _get_ocr_engine(1600)
    candidate = _ocr_png(quality_engine, png_bytes, use_cls=True)
    if _text_score(candidate) >= _text_score(text):
        return candidate
    return text


def ocr_pdf_text(
    pdf_bytes: bytes,
    *,
    dpi: int = 120,
    max_pages: int = 1,
    page_indexes: list[int] | None = None,
    fast_only: bool = False,
) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if len(doc) == 0:
            return ""
        if page_indexes is not None:
            indexes = page_indexes[:MAX_OCR_PAGES]
        else:
            indexes = list(range(min(max_pages, len(doc), MAX_OCR_PAGES)))
        return "\n".join(
            _ocr_page(doc[index], dpi, fast_only=fast_only)
            for index in indexes
            if 0 <= index < len(doc)
        )
    finally:
        doc.close()


def _pdf_page_count(pdf_bytes: bytes) -> int:
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return len(doc)
    finally:
        doc.close()


def ocr_last_page_text(pdf_bytes: bytes, *, dpi: int = 120) -> str:
    from io import BytesIO

    import pymupdf
    from PIL import Image

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if len(doc) == 0:
            return ""
        page = doc[-1]
        png = _render_png(page, dpi)
        image = Image.open(BytesIO(png))
        width, height = image.size
        bottom = image.crop((0, int(height * 0.75), width, height))
        buffer = BytesIO()
        bottom.save(buffer, format="PNG")
        engine = _get_ocr_engine(1024)
        text = _ocr_png(engine, buffer.getvalue(), use_cls=True)
        if DATE_RE.search(text) or MONTH_RE.search(text) or DATE_MD_RE.search(text):
            return text
        return _ocr_page(page, dpi, fast_only=True)
    finally:
        doc.close()


def _extract_date(text: str, academic_year: str | None = None) -> str | None:
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
    match = DATE_MD_RE.search(text)
    if match and academic_year:
        month, day = (int(part) for part in match.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            start_year = int(academic_year.split("-")[0])
            year = start_year if month >= 9 else start_year + 1
            return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _clean_title(value: str) -> str | None:
    title = re.sub(r"\s+", " ", value).strip()
    title = re.sub(r"^(兹证明|特此证明)[:：]?", "", title).strip()
    title = TITLE_PREFIX_RE.sub("", title).strip()
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
    compact = re.sub(r"\s+", "", text)

    label_pattern = BODY_PATTERNS[0]
    for line in lines:
        match = label_pattern.search(line)
        if match:
            title = _clean_title(match.group(1))
            if title:
                return title

    for pattern in BODY_PATTERNS[1:]:
        for candidate_text in (compact, *lines):
            match = pattern.search(candidate_text)
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


def suggest_from_text(
    text: str,
    rules: RuleSet,
    academic_year: str | None = None,
) -> ProofSuggestion:
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
    activity_date = _extract_date(compact, academic_year)
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


def _first_last_indexes(count: int) -> list[int]:
    if count <= 1:
        return [0] if count == 1 else []
    return [0, count - 1]


def _ocr_pdf_first_last(pdf_bytes: bytes, count: int) -> str:
    texts: list[str] = []
    try:
        first_text = ocr_pdf_text(pdf_bytes, max_pages=1)
    except Exception:
        first_text = ""
    if first_text.strip():
        texts.append(first_text)
    if count > 1:
        try:
            last_text = ocr_last_page_text(pdf_bytes)
        except Exception:
            last_text = ""
        if last_text.strip():
            texts.append(last_text)
    return "\n".join(texts)


def analyze_pdf(
    pdf_bytes: bytes,
    rules: RuleSet,
    academic_year: str | None = None,
) -> ProofSuggestion:
    try:
        count = _pdf_page_count(pdf_bytes)
        indexes = _first_last_indexes(count)
        text = extract_pdf_text(pdf_bytes, indexes)
    except Exception as exc:
        return ProofSuggestion(notes=[f"无法解析 PDF：{exc}"])

    used_ocr = False
    if len(text.strip()) < 10:
        try:
            text = _ocr_pdf_first_last(pdf_bytes, count)
            used_ocr = bool(text.strip())
        except Exception as exc:
            return ProofSuggestion(notes=[f"PDF 无文字，OCR 失败：{exc}"])
        if not used_ocr:
            return ProofSuggestion(notes=["PDF 无文字，OCR 未识别到内容，请手动填写"])

    suggestion = suggest_from_text(text, rules, academic_year)

    # 文字层可能只有标题，日期常常在最后一页。只在缺少日期时补 OCR 最后一页。
    if not used_ocr and count > 1 and suggestion.activity_date is None:
        try:
            last_text = ocr_last_page_text(pdf_bytes)
        except Exception:
            last_text = ""
        if last_text.strip():
            used_ocr = True
            text = f"{text}\n{last_text}"
            suggestion = suggest_from_text(text, rules, academic_year)

    if used_ocr:
        suggestion.notes.append("已使用本地 OCR 识别证明首尾页，请核对识别结果")
    return suggestion


def analyze_image(
    image_bytes: bytes,
    rules: RuleSet,
    academic_year: str | None = None,
    rotation: int = 0,
) -> ProofSuggestion:
    try:
        png = prepare_image_for_ocr(image_bytes, rotation=rotation)
        text = ocr_image_text(png)
    except Exception as exc:
        return ProofSuggestion(notes=[f"无法识别图片：{exc}"])

    suggestion = suggest_from_text(text, rules, academic_year)
    if text.strip():
        suggestion.notes.append("已使用本地 OCR 识别图片，请核对识别结果")
    return suggestion


def merge_suggestions(
    primary: ProofSuggestion | None,
    secondary: ProofSuggestion | None,
) -> ProofSuggestion:
    if primary is None:
        return secondary or ProofSuggestion()
    if secondary is None:
        return primary
    notes = list(primary.notes)
    for note in secondary.notes:
        if note not in notes:
            notes.append(note)
    return ProofSuggestion(
        title=primary.title or secondary.title,
        rule_id=primary.rule_id or secondary.rule_id,
        activity_date=primary.activity_date or secondary.activity_date,
        text="\n".join(part for part in (primary.text, secondary.text) if part),
        confidence=max(primary.confidence, secondary.confidence),
        notes=notes,
    )


def analyze_proof(
    data: bytes,
    filename: str | None,
    rules: RuleSet,
    academic_year: str | None = None,
    rotation: int = 0,
) -> ProofSuggestion:
    """Analyze one PDF or image proof file."""
    try:
        evidence_type = detect_evidence_type(data, filename)
    except ValueError as exc:
        return ProofSuggestion(notes=[str(exc)])
    if evidence_type.kind == "pdf":
        return analyze_pdf(data, rules, academic_year)
    return analyze_image(data, rules, academic_year, rotation=rotation)
