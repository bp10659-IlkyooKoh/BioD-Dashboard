"""Readable reports from calculated results; no external AI calls."""
import io
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import pandas as pd


def summarize_results(ranking, retention, comparisons, settings, labels):
    target, organ = settings["target"], settings["comparator"]
    scope = (f"{len(settings['selected_profiles'])}개 물질을 {settings['start_h']:g}–{settings['end_h']:g}h 구간에서 비교했습니다. "
             f"표적 장기는 {target}, 비교 장기는 {organ}이며 Reference는 {settings['reference_name']}입니다. "
             f"AUC 계산: {settings['auc_method']}.")
    if ranking.empty:
        finding = "선택한 구간에서 두 장기의 AUC가 모두 있는 물질이 없어 후보 순위를 산출하지 못했습니다."
    else:
        leaders = ranking[ranking["rank"] == ranking["rank"].min()]
        names = ", ".join(labels[p] for p in leaders.profile.head(6))
        if len(leaders) > 6:
            names += f" 외 {len(leaders) - 6}개 물질"
        finding = f"표적 AUC와 비교 장기 AUC를 1:1로 반영한 참고 순위의 1위는 {names}입니다. "
        first = leaders.iloc[0]
        finding += (f"{labels[first.profile]}의 {target} AUC는 {first.tumor_auc:.4g}, "
                    f"{organ} AUC는 {first.normal_auc:.4g} %ID/g·h입니다. ")
        if pd.notna(first.auc_ratio):
            finding += f"두 장기의 AUC 비율은 {first.auc_ratio:.4g}입니다."
        else:
            finding += "비교 장기 AUC가 0이어서 AUC 비율은 산출하지 않았습니다."
        if len(leaders) > 1:
            finding += " 공동 순위이므로 단일 우위 후보로 해석하지 않습니다."
    valid = retention.dropna(subset=["retention_pct"])
    if valid.empty:
        retention_text = "선택한 장기와 초기·후기 시점의 유효한 쌍이 없어 유지율을 산출하지 못했습니다."
    else:
        entries = [f"{labels[r.profile]} {r.retention_pct:.1f}%" for _, r in valid.head(6).iterrows()]
        retention_text = (f"{settings['retention_organ']}의 {settings['early_h']:g}h 대비 {settings['late_h']:g}h 유지율은 "
                          + ", ".join(entries) + "입니다. 감소율은 100에서 유지율을 뺀 값이며, 음수는 분포 증가를 뜻합니다.")
        if len(valid) > 6:
            retention_text += f" 나머지 {len(valid) - 6}개 물질의 수치는 상세표에 포함됩니다."
    tested = comparisons.q_bh.notna()
    reasons = ", ".join(sorted(set(comparisons.loc[~tested, "test_status"])))
    stats = (f"{settings['reference_view_organ']} {settings['reference_view_time_h']:g}h의 Reference 비교 "
             f"{len(comparisons)}건 중 {int(tested.sum())}건에서 검정을 수행했습니다. "
             "방법은 양측 독립 Student t-test(등분산 가정)이며, 선택한 전체 물질·장기·시간의 유효 p값에 BH FDR 보정을 적용합니다. ")
    if tested.any():
        stats += f"보정 p값 q<0.05인 비교는 {int((comparisons.q_bh < 0.05).sum())}건입니다."
    if reasons:
        stats += f" 미산출 사유: {reasons}."
    return [("분석 범위", scope), ("주요 관찰", finding), ("유지율·감소율", retention_text),
            ("Reference 비교 및 통계", stats),
            ("해석 범위", "이 요약은 계산 결과를 문장으로 정리한 것이며 AI 해석은 포함하지 않습니다. "
                         "참고 순위와 분포 지표만으로 효능·독성·작용기전을 판정하지 않습니다.")]


@lru_cache(maxsize=1)
def _fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    root = Path(__file__).resolve().parent / "fonts"
    normal, bold = root / "NanumGothic-Regular.ttf", root / "NanumGothic-Bold.ttf"
    if not normal.is_file() or not bold.is_file():
        raise RuntimeError("PDF용 한글 글꼴이 누락되었습니다. 앱과 함께 fonts 폴더의 "
                           "NanumGothic-Regular.ttf, NanumGothic-Bold.ttf를 업로드해 주세요.")
    pdfmetrics.registerFont(TTFont("BioDText", str(normal)))
    pdfmetrics.registerFont(TTFont("BioDBold", str(bold)))
    pdfmetrics.registerFontFamily("BioDText", normal="BioDText", bold="BioDBold",
                                 italic="BioDText", boldItalic="BioDBold")
    return "BioDText", "BioDBold"


def report_pdf(sections, result_tables, reviewer_note=""):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable

    regular, bold = _fonts()
    out = io.BytesIO()
    width = A4[0] - 84
    body = ParagraphStyle("Body", fontName=regular, fontSize=10, leading=17, wordWrap="CJK", spaceAfter=10)
    heading = ParagraphStyle("Section", parent=body, fontName=bold, fontSize=12, leading=18, spaceBefore=13, spaceAfter=7, keepWithNext=True)
    title = ParagraphStyle("Title", parent=heading, fontSize=23, leading=32, spaceAfter=6)
    small = ParagraphStyle("Small", parent=body, fontSize=8, leading=12, textColor=colors.HexColor("#637083"))
    cell = ParagraphStyle("Cell", parent=body, fontSize=8, leading=12, spaceAfter=0, alignment=TA_LEFT)
    header_cell = ParagraphStyle("HeaderCell", parent=cell, fontName=bold, textColor=colors.white)
    story = [Paragraph("BioD 결과 보고서", title),
             Paragraph(datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST") + " · 계산 결과 기반 요약", small),
             HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3563B9")), Spacer(1, 10)]
    for number, (name, content) in enumerate(sections, start=1):
        story += [Paragraph(f"{number}. {escape(name)}", heading), Paragraph(escape(content).replace("\n", "<br/>"), body)]
    if reviewer_note.strip():
        story += [Paragraph("검토자 의견", heading), Paragraph(escape(reviewer_note).replace("\n", "<br/>"), body)]
    story += [PageBreak(), Paragraph("주요 결과표", title), Paragraph("전체 시간점과 상세 데이터는 Excel 보고서에서 확인할 수 있습니다.", small)]
    for name, frame in result_tables.items():
        story.append(Paragraph(escape(name), heading))
        if frame.empty:
            story.append(Paragraph("선택 조건에서 산출된 결과가 없습니다.", body))
            continue
        shown = frame.head(12)
        rows = [[Paragraph(escape(str(c)), header_cell) for c in shown.columns]]
        for row in shown.itertuples(index=False, name=None):
            texts = ["—" if pd.isna(v) else f"{v:.4g}" if isinstance(v, (int, float)) else str(v) for v in row]
            rows.append([Paragraph(escape(v), cell) for v in texts])
        weights = [0.4 if str(c) == "순위" else 2.2 if str(c) == "물질" else 1 for c in frame.columns]
        table = Table(rows, colWidths=[width * w / sum(weights) for w in weights], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243A59")),
                                   ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5FA")]),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                                   ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        story.append(table)
        if len(frame) > len(shown):
            story.append(Paragraph(f"전체 {len(frame)}행 중 앞 12행을 표시했습니다. 전체 결과는 Excel에 포함됩니다.", small))
        story.append(Spacer(1, 8))

    def footer(canvas, doc):
        canvas.setFont(regular, 8)
        canvas.setFillColor(colors.HexColor("#637083"))
        canvas.drawString(42, 24, "BioD Report")
        canvas.drawRightString(A4[0] - 42, 24, str(doc.page))

    SimpleDocTemplate(out, pagesize=A4, leftMargin=42, rightMargin=42, topMargin=34, bottomMargin=42,
                      title="BioD 결과 보고서", author="BioD Dashboard").build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
