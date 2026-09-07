import json
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
)


RESULT_PATH = Path("inspection_result.json")
DEFECT_PATH = Path("defect.json")
OUTPUT_PATH = Path("inspection_report.pdf")


def register_korean_font() -> str:
    """
    Windows의 맑은 고딕 폰트를 등록합니다.
    사용 가능한 폰트를 찾지 못하면 오류를 발생시킵니다.
    """
    font_candidates = [
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\NanumGothic.ttf",
        r"C:\Windows\Fonts\gulim.ttc",
    ]

    for font_path in font_candidates:
        if os.path.exists(font_path):
            font_name = "KoreanFont"
            pdfmetrics.registerFont(
                TTFont(font_name, font_path)
            )
            return font_name

    raise FileNotFoundError(
        "사용할 한글 폰트를 찾지 못했습니다. "
        "C:\\Windows\\Fonts\\malgun.ttf 경로를 확인하세요."
    )


def safe_text(value) -> str:
    """None 등의 값을 PDF에 안전하게 표시합니다."""
    if value is None:
        return "-"
    return str(value)


def add_page_number(canvas, doc):
    """각 페이지 아래에 페이지 번호를 표시합니다."""
    canvas.saveState()

    font_name = getattr(doc, "korean_font", "Helvetica")
    canvas.setFont(font_name, 9)

    page_number = canvas.getPageNumber()
    page_text = f"- {page_number} -"

    canvas.drawCentredString(
        A4[0] / 2,
        12 * mm,
        page_text,
    )

    canvas.restoreState()


def create_styles(font_name: str):
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        name="KoreanTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=20,
        leading=28,
        alignment=TA_CENTER,
        spaceAfter=14,
    )

    heading_style = ParagraphStyle(
        name="KoreanHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=13,
        leading=18,
        spaceBefore=10,
        spaceAfter=7,
        textColor=colors.HexColor("#1F3A5F"),
    )

    body_style = ParagraphStyle(
        name="KoreanBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10,
        leading=16,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )

    small_style = ParagraphStyle(
        name="KoreanSmall",
        parent=body_style,
        fontSize=8.5,
        leading=13,
    )

    warning_style = ParagraphStyle(
        name="KoreanWarning",
        parent=body_style,
        textColor=colors.HexColor("#9C2F2F"),
        backColor=colors.HexColor("#FFF3F3"),
        borderColor=colors.HexColor("#D99A9A"),
        borderWidth=0.5,
        borderPadding=7,
        spaceBefore=8,
        spaceAfter=8,
    )

    return {
        "title": title_style,
        "heading": heading_style,
        "body": body_style,
        "small": small_style,
        "warning": warning_style,
    }


def paragraph(value, style):
    """
    줄바꿈을 ReportLab Paragraph에서 표시할 수 있도록 변환합니다.
    """
    text = safe_text(value)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace("\n", "<br/>")
    return Paragraph(text, style)


def create_report(
    defect: dict,
    result: dict,
    output_path: Path,
) -> None:
    font_name = register_korean_font()
    styles = create_styles(font_name)

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="터널 시설물 안전점검 보고서",
        author="시설물 점검 RAG 시스템",
    )

    document.korean_font = font_name
    story = []

    # 제목
    story.append(
        Paragraph(
            "터널 시설물 안전점검 보고서",
            styles["title"],
        )
    )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    story.append(
        Paragraph(
            f"보고서 생성일시: {generated_at}",
            styles["small"],
        )
    )
    story.append(Spacer(1, 8 * mm))

    # 1. 기본 정보
    story.append(
        Paragraph("1. 점검 기본정보", styles["heading"])
    )

    basic_data = [
        [
            paragraph("항목", styles["body"]),
            paragraph("내용", styles["body"]),
        ],
        [
            paragraph("시설물", styles["body"]),
            paragraph(defect.get("facility"), styles["body"]),
        ],
        [
            paragraph("점검 부재", styles["body"]),
            paragraph(defect.get("component"), styles["body"]),
        ],
        [
            paragraph("점검 위치", styles["body"]),
            paragraph(defect.get("location"), styles["body"]),
        ],
        [
            paragraph("결함 종류", styles["body"]),
            paragraph(defect.get("defect"), styles["body"]),
        ],
        [
            paragraph("결함 길이", styles["body"]),
            paragraph(
                f"{safe_text(defect.get('length_mm'))} mm",
                styles["body"],
            ),
        ],
        [
            paragraph("최대 균열폭", styles["body"]),
            paragraph(
                f"{safe_text(defect.get('max_width_mm'))} mm",
                styles["body"],
            ),
        ],
        [
            paragraph("AI 검출 신뢰도", styles["body"]),
            paragraph(
                safe_text(defect.get("confidence")),
                styles["body"],
            ),
        ],
        [
            paragraph("원본 이미지", styles["body"]),
            paragraph(
                defect.get("image_path"),
                styles["body"],
            ),
        ],
    ]

    basic_table = Table(
        basic_data,
        colWidths=[38 * mm, 130 * mm],
        repeatRows=1,
    )

    basic_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#DCE6F1")),
            ("TEXTCOLOR", (0, 0), (-1, 0),
             colors.HexColor("#1F1F1F")),
            ("GRID", (0, 0), (-1, -1), 0.5,
             colors.HexColor("#909090")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )

    story.append(basic_table)
    story.append(Spacer(1, 6 * mm))

    # 이미지가 실제로 존재하면 보고서에 삽입
    image_path = defect.get("image_path")

    if image_path and Path(image_path).exists():
        story.append(
            Paragraph("2. 점검 이미지", styles["heading"])
        )

        try:
            report_image = Image(image_path)
            report_image._restrictSize(165 * mm, 95 * mm)
            story.append(report_image)
            story.append(Spacer(1, 5 * mm))
        except Exception as error:
            story.append(
                paragraph(
                    f"이미지를 삽입하지 못했습니다: {error}",
                    styles["warning"],
                )
            )

    # 결과
    story.append(
        Paragraph("3. 점검결과", styles["heading"])
    )
    story.append(
        paragraph(
            result.get("inspection_summary"),
            styles["body"],
        )
    )
    story.append(Spacer(1, 4 * mm))

    story.append(
        Paragraph("4. 결함 평가", styles["heading"])
    )
    story.append(
        paragraph(
            result.get("defect_assessment"),
            styles["body"],
        )
    )
    story.append(Spacer(1, 4 * mm))

    story.append(
        Paragraph("5. 권장 조치사항", styles["heading"])
    )
    story.append(
        paragraph(
            result.get("recommended_action"),
            styles["body"],
        )
    )
    story.append(Spacer(1, 4 * mm))

    # 긴급도
    story.append(
        Paragraph("6. 조치 우선순위", styles["heading"])
    )

    urgency = safe_text(result.get("urgency"))

    urgency_table = Table(
        [[
            paragraph("판정", styles["body"]),
            paragraph(urgency, styles["body"]),
        ]],
        colWidths=[38 * mm, 130 * mm],
    )

    urgency_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("BACKGROUND", (0, 0), (0, 0),
             colors.HexColor("#DCE6F1")),
            ("GRID", (0, 0), (-1, -1), 0.5,
             colors.HexColor("#909090")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )

    story.append(urgency_table)
    story.append(Spacer(1, 4 * mm))

    # 추가 점검 항목
    story.append(
        Paragraph("7. 추가 점검 필요사항", styles["heading"])
    )

    additional_items = result.get("additional_inspection", [])

    if additional_items:
        for index, item in enumerate(additional_items, start=1):
            story.append(
                paragraph(
                    f"{index}. {item}",
                    styles["body"],
                )
            )
            story.append(Spacer(1, 1.5 * mm))
    else:
        story.append(
            paragraph("추가 점검 항목 없음", styles["body"])
        )

    story.append(Spacer(1, 4 * mm))

    # 근거 문서
    story.append(
        Paragraph("8. 적용 근거", styles["heading"])
    )

    source_rows = [[
        paragraph("문서", styles["small"]),
        paragraph("페이지", styles["small"]),
        paragraph("적용 사유", styles["small"]),
    ]]

    for source in result.get("sources", []):
        source_rows.append([
            paragraph(source.get("document"), styles["small"]),
            paragraph(source.get("page"), styles["small"]),
            paragraph(source.get("reason"), styles["small"]),
        ])

    source_table = Table(
        source_rows,
        colWidths=[45 * mm, 20 * mm, 103 * mm],
        repeatRows=1,
    )

    source_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#DCE6F1")),
            ("GRID", (0, 0), (-1, -1), 0.5,
             colors.HexColor("#909090")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )

    story.append(source_table)
    story.append(Spacer(1, 8 * mm))

    # 검토 안내
    story.append(
        paragraph(
            "본 보고서는 AI 기반 검색 및 문서작성 시스템이 생성한 "
            "점검 초안입니다. AI 검출 신뢰도는 구조적 안전도를 의미하지 "
            "않으며, 최종 판정과 조치 결정은 관련 자격을 갖춘 점검자가 "
            "원본 기준서와 현장 상태를 확인한 후 수행해야 합니다.",
            styles["warning"],
        )
    )

    # 검토 서명란
    story.append(Spacer(1, 7 * mm))

    review_table = Table(
        [
            [
                paragraph("점검자", styles["body"]),
                "",
                paragraph("검토자", styles["body"]),
                "",
            ],
            [
                paragraph("검토일", styles["body"]),
                "",
                paragraph("승인", styles["body"]),
                "",
            ],
        ],
        colWidths=[25 * mm, 59 * mm, 25 * mm, 59 * mm],
        rowHeights=[15 * mm, 15 * mm],
    )

    review_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("BACKGROUND", (0, 0), (0, -1),
             colors.HexColor("#EEEEEE")),
            ("BACKGROUND", (2, 0), (2, -1),
             colors.HexColor("#EEEEEE")),
            ("GRID", (0, 0), (-1, -1), 0.5,
             colors.HexColor("#808080")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ])
    )

    story.append(review_table)

    document.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    print(f"PDF 보고서 저장 완료: {output_path.resolve()}")

def create_combined_report(
    report_items: list[dict],
    output_path: Path,
) -> None:
    font_name = register_korean_font()
    styles = create_styles(font_name)

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="터널 시설물 종합 안전점검 보고서",
        author="시설물 점검 RAG 시스템",
    )

    document.korean_font = font_name
    story = []

    # 표지
    story.append(
        Paragraph(
            "터널 시설물 종합 안전점검 보고서",
            styles["title"],
        )
    )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    story.append(
        Paragraph(
            f"보고서 생성일시: {generated_at}",
            styles["body"],
        )
    )

    story.append(Spacer(1, 5 * mm))

    story.append(
        Paragraph(
            f"총 점검 결함 수: {len(report_items)}건",
            styles["body"],
        )
    )

    story.append(Spacer(1, 10 * mm))

    # 결함 목록 요약
    summary_rows = [[
        paragraph("번호", styles["small"]),
        paragraph("부재", styles["small"]),
        paragraph("위치", styles["small"]),
        paragraph("결함", styles["small"]),
        paragraph("조치 우선순위", styles["small"]),
    ]]

    for index, item in enumerate(report_items, start=1):
        defect = item["defect_data"]
        result = item["inspection_result"]

        summary_rows.append([
            paragraph(index, styles["small"]),
            paragraph(defect.get("component", "-"), styles["small"]),
            paragraph(defect.get("location", "-"), styles["small"]),
            paragraph(defect.get("defect", "-"), styles["small"]),
            paragraph(result.get("urgency", "-"), styles["small"]),
        ])

    summary_table = Table(
        summary_rows,
        colWidths=[
            12 * mm,
            30 * mm,
            68 * mm,
            28 * mm,
            30 * mm,
        ],
        repeatRows=1,
    )

    summary_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#DCE6F1")),
            ("GRID", (0, 0), (-1, -1), 0.5,
             colors.HexColor("#808080")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )

    story.append(summary_table)

    # 결함별 상세 보고서
    for index, item in enumerate(report_items, start=1):
        defect = item["defect_data"]
        result = item["inspection_result"]

        story.append(PageBreak())

        story.append(
            Paragraph(
                f"결함 {index}. {safe_text(defect.get('defect'))}",
                styles["title"],
            )
        )

        # 기본 정보는 존재하는 필드만 자동 출력
        excluded_fields = {"image_path"}

        field_name_map = {
            "facility": "시설물",
            "component": "점검 부재",
            "location": "점검 위치",
            "defect": "결함 종류",
            "length_mm": "결함 길이(mm)",
            "max_width_mm": "최대 폭(mm)",
            "area_mm2": "결함 면적(mm²)",
            "confidence": "AI 검출 신뢰도",
            "measurement_basis": "치수 산출 근거",
            "measurement_limit_mm": "측정 한계(mm)",
            "measurement_note": "측정 비고",
            "detector_grade": "탐지기 예비 등급",
            "width_change_status": "폭 변화 상태",
            "observed_at": "관측 일시",
            "damage_no": "손상 번호",
        }

        basic_rows = [[
            paragraph("항목", styles["body"]),
            paragraph("내용", styles["body"]),
        ]]

        for key, value in defect.items():
            if key in excluded_fields:
                continue

            field_name = field_name_map.get(key, key)

            basic_rows.append([
                paragraph(field_name, styles["body"]),
                paragraph(value, styles["body"]),
            ])

        basic_table = Table(
            basic_rows,
            colWidths=[45 * mm, 123 * mm],
            repeatRows=1,
        )

        basic_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("BACKGROUND", (0, 0), (-1, 0),
                 colors.HexColor("#DCE6F1")),
                ("GRID", (0, 0), (-1, -1), 0.5,
                 colors.HexColor("#808080")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )

        story.append(
            Paragraph("1. 점검 기본정보", styles["heading"])
        )
        story.append(basic_table)
        story.append(Spacer(1, 5 * mm))

        # 이미지
        image_path = defect.get("image_path")

        if image_path and Path(image_path).exists():
            story.append(
                Paragraph("2. 점검 이미지", styles["heading"])
            )

            try:
                report_image = Image(image_path)
                report_image._restrictSize(165 * mm, 90 * mm)
                story.append(report_image)
                story.append(Spacer(1, 4 * mm))
            except Exception as error:
                story.append(
                    paragraph(
                        f"이미지 삽입 실패: {error}",
                        styles["warning"],
                    )
                )

        # 점검 결과
        story.append(
            Paragraph("3. 점검결과", styles["heading"])
        )
        story.append(
            paragraph(
                result.get("inspection_summary", "-"),
                styles["body"],
            )
        )

        story.append(
            Paragraph("4. 결함 평가", styles["heading"])
        )
        story.append(
            paragraph(
                result.get("defect_assessment", "-"),
                styles["body"],
            )
        )

        story.append(
            Paragraph("5. 권장 조치사항", styles["heading"])
        )
        story.append(
            paragraph(
                result.get("recommended_action", "-"),
                styles["body"],
            )
        )

        story.append(
            Paragraph("6. 조치 우선순위", styles["heading"])
        )

        urgency_table = Table(
            [[
                paragraph("판정", styles["body"]),
                paragraph(
                    result.get("urgency", "판단보류"),
                    styles["body"],
                ),
            ]],
            colWidths=[45 * mm, 123 * mm],
        )

        urgency_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("BACKGROUND", (0, 0), (0, 0),
                 colors.HexColor("#DCE6F1")),
                ("GRID", (0, 0), (-1, -1), 0.5,
                 colors.HexColor("#808080")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )

        story.append(urgency_table)

        # 추가 점검 사항
        story.append(
            Paragraph("7. 추가 점검 필요사항", styles["heading"])
        )

        additional_items = result.get(
            "additional_inspection",
            [],
        )

        if additional_items:
            for item_number, additional_item in enumerate(
                additional_items,
                start=1,
            ):
                story.append(
                    paragraph(
                        f"{item_number}. {additional_item}",
                        styles["body"],
                    )
                )
        else:
            story.append(
                paragraph("추가 점검 항목 없음", styles["body"])
            )

        # 적용 근거
        story.append(
            Paragraph("8. 적용 근거", styles["heading"])
        )

        source_rows = [[
            paragraph("문서", styles["small"]),
            paragraph("페이지", styles["small"]),
            paragraph("적용 사유", styles["small"]),
        ]]

        for source in result.get("sources", []):
            source_rows.append([
                paragraph(
                    source.get("document", "-"),
                    styles["small"],
                ),
                paragraph(
                    source.get("page", "-"),
                    styles["small"],
                ),
                paragraph(
                    source.get("reason", "-"),
                    styles["small"],
                ),
            ])

        source_table = Table(
            source_rows,
            colWidths=[
                45 * mm,
                20 * mm,
                103 * mm,
            ],
            repeatRows=1,
        )

        source_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("BACKGROUND", (0, 0), (-1, 0),
                 colors.HexColor("#DCE6F1")),
                ("GRID", (0, 0), (-1, -1), 0.5,
                 colors.HexColor("#808080")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])
        )

        story.append(source_table)
        story.append(Spacer(1, 6 * mm))

        story.append(
            paragraph(
                "본 결과는 AI 기반 검색 및 문서작성 시스템이 "
                "생성한 초안이며, 최종 판정은 점검자가 원본 "
                "기준서와 현장 상태를 확인한 후 수행해야 합니다.",
                styles["warning"],
            )
        )

    document.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    if not output_path.exists():
        raise RuntimeError(
            f"종합 PDF 생성 실패: {output_path.resolve()}"
        )

    print(
        f"종합 PDF 생성 완료: {output_path.resolve()}"
    )



def main():
    if not DEFECT_PATH.exists():
        raise FileNotFoundError(
            f"결함 데이터 파일이 없습니다: {DEFECT_PATH}"
        )

    if not RESULT_PATH.exists():
        raise FileNotFoundError(
            f"점검 결과 파일이 없습니다: {RESULT_PATH}"
        )

    with DEFECT_PATH.open("r", encoding="utf-8-sig") as file:
        defect = json.load(file)

    with RESULT_PATH.open("r", encoding="utf-8-sig") as file:
        result = json.load(file)

    create_report(
        defect=defect,
        result=result,
        output_path=OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()