from __future__ import annotations

import html
import io
import json
import re
import textwrap
import zipfile
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Image as ReportLabImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .ebook_validation import MIN_ILLUSTRATIONS, MIN_PAGES


def _safe_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return value[:80] or "ebook"


def _font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _content_data(content: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"introduction": str(content), "chapters": [], "conclusion": "", "illustrations": []}


def _paragraphs(value: Any) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", str(value or "")) if part.strip()]


def _wrap_pixels(draw: ImageDraw.ImageDraw, value: str, font, max_width: int) -> list[str]:
    words = str(value or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def build_cover(title: str, subtitle: str) -> bytes:
    width, height = 1600, 2560
    image = Image.new("RGB", (width, height), "#101827")
    draw = ImageDraw.Draw(image)
    accent = "#f2a65a"
    draw.rounded_rectangle((90, 90, width - 90, height - 90), radius=50, outline=accent, width=5)
    draw.text((140, 180), "HERMES PRO", fill="#e5e7eb", font=_font(56))
    draw.text((140, 330), "GUIA DIGITAL ILUSTRADO", fill=accent, font=_font(42))

    y = 760
    title_font = _font(104)
    for line in textwrap.wrap(title, width=24):
        draw.text((140, y), line, fill="#ffffff", font=title_font)
        y += 130
    y += 80
    subtitle_font = _font(48)
    for line in textwrap.wrap(subtitle, width=38):
        draw.text((140, y), line, fill="#cbd5e1", font=subtitle_font)
        y += 68

    # A topic-neutral geometric motif keeps the cover readable without inventing facts.
    draw.ellipse((width - 560, height - 760, width - 180, height - 380), outline=accent, width=18)
    draw.ellipse((width - 460, height - 660, width - 280, height - 480), fill=accent)
    draw.line((180, height - 300, width - 180, height - 300), fill="#475569", width=4)

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def build_illustration(brief: dict[str, Any], index: int) -> bytes:
    """Render a topic-specific editorial infographic from the approved illustration brief."""
    width, height = 1600, 900
    image = Image.new("RGB", (width, height), "#f4f1e9")
    draw = ImageDraw.Draw(image)
    navy, accent, ink, muted = "#14213d", "#e07a3f", "#1f2937", "#64748b"
    draw.rectangle((0, 0, width, 205), fill=navy)
    draw.text((85, 42), f"ILUSTRAÇÃO {index + 1:02d}  |  HERMES PRO", fill="#f7c59f", font=_font(28))
    title = str(brief.get("title") or f"Conceito {index + 1}")
    for line_no, line in enumerate(_wrap_pixels(draw, title, _font(54), 1420)[:2]):
        draw.text((85, 92 + line_no * 62), line, fill="#ffffff", font=_font(54))

    description = str(brief.get("description") or brief.get("caption") or "")
    for line_no, line in enumerate(_wrap_pixels(draw, description, _font(25), 1400)[:2]):
        draw.text((90, 238 + line_no * 34), line, fill=muted, font=_font(25))

    raw_steps = brief.get("steps")
    if isinstance(raw_steps, list):
        steps = [str(step).strip() for step in raw_steps if str(step).strip()]
    else:
        steps = [part.strip() for part in re.split(r"(?<=[.!?])\s+", description) if part.strip()]
    defaults = [
        "Entenda o cenário e o objetivo",
        "Organize os recursos necessários",
        "Execute as etapas com método",
        "Revise os resultados e ajuste",
    ]
    steps = (steps + defaults)[:4]

    card_width, card_height = 330, 385
    start_x, gap, y = 80, 55, 385
    for step_index, step in enumerate(steps):
        x = start_x + step_index * (card_width + gap)
        draw.rounded_rectangle((x, y, x + card_width, y + card_height), radius=28, fill="#ffffff", outline="#d8d4ca", width=3)
        draw.ellipse((x + 28, y + 28, x + 100, y + 100), fill=accent if step_index % 2 == 0 else navy)
        number = str(step_index + 1)
        draw.text((x + 52, y + 39), number, fill="#ffffff", font=_font(42))
        lines = _wrap_pixels(draw, step, _font(29), card_width - 58)
        text_y = y + 135
        for line in lines[:6]:
            draw.text((x + 28, text_y), line, fill=ink, font=_font(29))
            text_y += 42
        if step_index < 3:
            center_y = y + card_height // 2
            arrow_x = x + card_width + 8
            draw.line((arrow_x, center_y, arrow_x + gap - 16, center_y), fill=accent, width=8)
            draw.polygon(
                [(arrow_x + gap - 25, center_y - 15), (arrow_x + gap - 5, center_y), (arrow_x + gap - 25, center_y + 15)],
                fill=accent,
            )

    caption = str(brief.get("caption") or title)
    draw.text((85, 825), "APLICAÇÃO PRÁTICA", fill=navy, font=_font(23))
    for line_no, line in enumerate(_wrap_pixels(draw, caption, _font(23), 1180)[:1]):
        draw.text((360, 825), line, fill=muted, font=_font(23))

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def build_docx(
    title: str,
    subtitle: str,
    content: str,
    *,
    cover_bytes: bytes | None = None,
    illustration_bytes: list[bytes] | None = None,
    illustration_briefs: list[dict[str, Any]] | None = None,
) -> bytes:
    data = _content_data(content)
    illustrations = illustration_bytes or []
    briefs = illustration_briefs or []
    doc = Document()
    if cover_bytes:
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run().add_picture(io.BytesIO(cover_bytes), width=Inches(6.0))
        doc.add_page_break()

    doc.add_heading(title, 0)
    if subtitle:
        doc.add_paragraph(subtitle)
    if data.get("introduction"):
        doc.add_heading("Introdução", level=1)
        for paragraph in _paragraphs(data["introduction"]):
            doc.add_paragraph(paragraph)

    for index, chapter in enumerate(data.get("chapters", [])):
        if not isinstance(chapter, dict):
            continue
        doc.add_page_break()
        doc.add_heading(str(chapter.get("title") or f"Capítulo {index + 1}"), level=1)
        for paragraph in _paragraphs(chapter.get("content")):
            doc.add_paragraph(paragraph)
        if index < len(illustrations):
            image_paragraph = doc.add_paragraph()
            image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            image_paragraph.add_run().add_picture(io.BytesIO(illustrations[index]), width=Inches(5.8))
            caption = str(briefs[index].get("caption") or briefs[index].get("title") or "")
            if caption:
                caption_paragraph = doc.add_paragraph(caption)
                caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if data.get("conclusion"):
        doc.add_heading("Conclusão", level=1)
        for paragraph in _paragraphs(data["conclusion"]):
            doc.add_paragraph(paragraph)

    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


def build_pdf(
    title: str,
    subtitle: str,
    content: str,
    *,
    cover_bytes: bytes | None = None,
    illustration_bytes: list[bytes] | None = None,
    illustration_briefs: list[dict[str, Any]] | None = None,
) -> bytes:
    data = _content_data(content)
    illustrations = illustration_bytes or []
    briefs = illustration_briefs or []
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=48,
        bottomMargin=48,
        title=title,
        author="Hermes Pro",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("HermesTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=29, alignment=TA_CENTER, spaceAfter=16)
    subtitle_style = ParagraphStyle("HermesSubtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=11, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#475569"), spaceAfter=22)
    body_style = ParagraphStyle("HermesBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=9)
    heading_style = ParagraphStyle("HermesHeading", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=23, spaceBefore=6, spaceAfter=14)

    story = []
    if cover_bytes:
        story.append(ReportLabImage(io.BytesIO(cover_bytes), width=doc.width - 12, height=doc.height - 12, kind="proportional"))
        story.append(PageBreak())

    story.append(Paragraph(html.escape(title), title_style))
    if subtitle:
        story.append(Paragraph(html.escape(subtitle), subtitle_style))
    if data.get("introduction"):
        story.append(Paragraph("Introdução", heading_style))
        for paragraph in _paragraphs(data["introduction"]):
            story.append(Paragraph(html.escape(paragraph).replace("\n", "<br/>"), body_style))

    for index, chapter in enumerate(data.get("chapters", [])):
        if not isinstance(chapter, dict):
            continue
        story.append(PageBreak())
        story.append(Paragraph(html.escape(str(chapter.get("title") or f"Capítulo {index + 1}")), heading_style))
        for paragraph in _paragraphs(chapter.get("content")):
            story.append(Paragraph(html.escape(paragraph).replace("\n", "<br/>"), body_style))
        if index < len(illustrations):
            story.append(Spacer(1, 8))
            story.append(ReportLabImage(io.BytesIO(illustrations[index]), width=doc.width - 12, height=(doc.width - 12) * 0.49, kind="proportional"))
            caption = str(briefs[index].get("caption") or briefs[index].get("title") or "")
            if caption:
                story.append(Paragraph(html.escape(caption), subtitle_style))

    if data.get("conclusion"):
        story.append(Spacer(1, 14))
        story.append(Paragraph("Conclusão", heading_style))
        for paragraph in _paragraphs(data["conclusion"]):
            story.append(Paragraph(html.escape(paragraph).replace("\n", "<br/>"), body_style))

    doc.build(story)
    return output.getvalue()


def build_artifacts(title: str, subtitle: str, content: str) -> dict[str, tuple[str, bytes, str]]:
    data = _content_data(content)
    raw_briefs = data.get("illustrations")
    briefs = [
        item for item in raw_briefs
        if isinstance(item, dict)
        and all(isinstance(item.get(key), str) and item[key].strip() for key in ("title", "description", "caption", "alt_text"))
    ] if isinstance(raw_briefs, list) else []
    if len(briefs) < MIN_ILLUSTRATIONS:
        raise ValueError(f"ebook requires {MIN_ILLUSTRATIONS} valid internal illustration briefs before artifact generation")

    slug = _safe_name(title)
    cover = build_cover(title, subtitle)
    selected_briefs = briefs[:MIN_ILLUSTRATIONS]
    illustration_bytes = [build_illustration(brief, index) for index, brief in enumerate(selected_briefs)]
    content_json = json.dumps(data, ensure_ascii=False)
    docx = build_docx(
        title, subtitle, content_json,
        cover_bytes=cover,
        illustration_bytes=illustration_bytes,
        illustration_briefs=selected_briefs,
    )
    pdf = build_pdf(
        title, subtitle, content_json,
        cover_bytes=cover,
        illustration_bytes=illustration_bytes,
        illustration_briefs=selected_briefs,
    )
    return {
        "cover": (f"{slug}/cover.png", cover, "image/png"),
        "docx": (f"{slug}/ebook.docx", docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "pdf": (f"{slug}/ebook.pdf", pdf, "application/pdf"),
    }


def validate_artifacts(artifacts: dict[str, tuple[str, bytes, str]]) -> dict[str, Any]:
    """Validate file signatures, embedded images and the ten-page commercial minimum."""
    required = {"cover", "docx", "pdf"}
    if set(artifacts) != required:
        return {
            "approved": False,
            "findings": ["Conjunto de arquivos incompleto; são obrigatórios capa, DOCX e PDF."],
            "page_count": 0,
            "illustration_count": 0,
        }

    cover_bytes = artifacts["cover"][1]
    docx_bytes = artifacts["docx"][1]
    pdf_bytes = artifacts["pdf"][1]
    if not cover_bytes.startswith(bytes.fromhex("89504e470d0a1a0a")):
        raise ValueError("cover is not a valid PNG")
    if not docx_bytes.startswith(bytes.fromhex("504b0304")):
        raise ValueError("DOCX is not a valid ZIP-based Office document")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("PDF signature is invalid")

    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        docx_image_count = len([
            name for name in archive.namelist()
            if name.startswith("word/media/") and not name.endswith("/")
        ])
    pdf_image_count = len(re.findall(rb"/Subtype\s*/Image\b", pdf_bytes))
    page_count = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
    illustration_count = min(max(0, docx_image_count - 1), max(0, pdf_image_count - 1))
    findings: list[str] = []
    if page_count < MIN_PAGES:
        findings.append(f"PDF curto: {page_count} páginas; mínimo {MIN_PAGES}.")
    if docx_image_count < MIN_ILLUSTRATIONS + 1:
        findings.append(f"DOCX sem as ilustrações internas obrigatórias: {docx_image_count - 1} de {MIN_ILLUSTRATIONS}.")
    if pdf_image_count < MIN_ILLUSTRATIONS + 1:
        findings.append(f"PDF sem as ilustrações internas obrigatórias: {pdf_image_count - 1} de {MIN_ILLUSTRATIONS}.")

    return {
        "approved": not findings,
        "page_count": page_count,
        "illustration_count": illustration_count,
        "pdf_image_count": pdf_image_count,
        "docx_image_count": docx_image_count,
        "minimums": {"pages": MIN_PAGES, "illustrations": MIN_ILLUSTRATIONS},
        "findings": findings,
    }
