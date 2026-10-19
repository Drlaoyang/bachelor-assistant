from __future__ import annotations

import pymupdf

from core.proof_analyzer import analyze_pdf, suggest_from_text
from device.pdf_tools import export_jpgs, pdf_page_count, pdf_to_jpgs, safe_stem


def _make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontname="china-s", fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def test_suggest_competition(rules):
    suggestion = suggest_from_text(
        "全国大学生数学建模竞赛获奖证书\n2025年9月", rules
    )
    assert suggestion.rule_id == "innovation_base_competition_rule"
    assert suggestion.title == "全国大学生数学建模竞赛"
    assert suggestion.activity_date == "2025-09-01"


def test_suggest_volunteer_and_skip_proof_sentence(rules):
    suggestion = suggest_from_text(
        "兹证明张三同学在2024-2025学年志愿服务时长累计30小时。\n"
        "山东大学网络空间安全学院\n2025年6月30日",
        rules,
    )
    assert suggestion.rule_id == "labor_base_volunteer"
    assert suggestion.title is None
    assert suggestion.activity_date == "2025-06-30"


def test_suggest_social_work_honor(rules):
    suggestion = suggest_from_text(
        "山东大学2024-2025学年优秀学生干部证书\n2025年10月", rules
    )
    assert suggestion.rule_id == "labor_ach_social_work_personal"
    assert suggestion.title == "山东大学2024-2025学年优秀学生干部"


def test_suggest_fitness(rules):
    suggestion = suggest_from_text(
        "国家学生体质健康标准测试成绩：优秀", rules
    )
    assert suggestion.rule_id == "physical_base_fitness"


def test_empty_text(rules):
    suggestion = suggest_from_text("", rules)
    assert suggestion.rule_id is None
    assert suggestion.title is None
    assert suggestion.notes


def test_analyze_pdf(rules):
    data = _make_pdf("全国大学生数学建模竞赛获奖证书 2025年9月")
    suggestion = analyze_pdf(data, rules)
    assert suggestion.rule_id == "innovation_base_competition_rule"
    assert suggestion.activity_date == "2025-09-01"
    assert "数学建模" in suggestion.text


def test_pdf_to_jpgs_and_export(tmp_path):
    doc = pymupdf.open()
    for index in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {index + 1}", fontsize=14)
    data = doc.tobytes()
    doc.close()

    images = pdf_to_jpgs(data)
    assert len(images) == 2
    assert all(image.startswith(b"\xff\xd8") for _, image in images)

    pdf_path = tmp_path / "测试 证明.pdf"
    pdf_path.write_bytes(data)
    assert pdf_page_count(pdf_path) == 2
    out_dir = tmp_path / "jpg"
    files = export_jpgs(pdf_path, out_dir, pages=[0])
    assert len(files) == 1
    assert files[0].name == f"{safe_stem('测试 证明')}_p1.jpg"
    assert files[0].exists()


def _make_scanned_pdf(text: str) -> bytes:
    source = pymupdf.open()
    source_page = source.new_page(width=900, height=400)
    source_page.insert_text(
        (60, 150), text, fontname="china-s", fontsize=40
    )
    pix = source_page.get_pixmap(dpi=200, colorspace=pymupdf.csRGB, alpha=False)
    png = pix.tobytes("png")
    source.close()

    doc = pymupdf.open()
    page = doc.new_page(width=900, height=400)
    page.insert_image(page.rect, stream=png)
    data = doc.tobytes()
    doc.close()
    return data


def test_analyze_scanned_pdf_with_ocr(rules):
    data = _make_scanned_pdf("全国大学生数学建模竞赛 2025年9月")
    assert not suggest_from_text("", rules).rule_id
    suggestion = analyze_pdf(data, rules)
    assert suggestion.rule_id == "innovation_base_competition_rule"
    assert "数学建模" in suggestion.text
    assert suggestion.activity_date == "2025-09-01"
    assert any("OCR" in note for note in suggestion.notes)


def test_full_width_digits_normalized(rules):
    suggestion = suggest_from_text("2025年９月全国大学生数学建模竞赛", rules)
    assert suggestion.activity_date == "2025-09-01"


def test_title_from_body_when_heading_is_generic(rules):
    suggestion = suggest_from_text(
        "参与证明\n"
        "兹证明张三同学参加2025年全国大学生数学建模竞赛，荣获国家二等奖。\n"
        "2025年9月",
        rules,
    )
    assert suggestion.title == "2025年全国大学生数学建模竞赛"
    assert suggestion.rule_id == "innovation_base_competition_rule"


def test_title_from_body_with_in_pattern(rules):
    suggestion = suggest_from_text(
        "参与证明\n张三同学在2025年校运动会中获得男子100米第一名。",
        rules,
    )
    assert suggestion.title == "2025年校运动会"
    assert suggestion.rule_id == "physical_achievement_sports"


def test_generic_title_not_used(rules):
    suggestion = suggest_from_text("参与证明\n2025年9月", rules)
    assert suggestion.title is None
