#!/usr/bin/env python3
"""Generate the body PDF (TOC + 8 chapters) for the 20-Repo Tooling Recon report.

Route: Report (ReportLab). Cover is rendered separately (Template 07) and merged.
"""
import os
import sys
import hashlib

SKILL_SCRIPTS = "/home/z/my-project/skills/pdf/scripts"
sys.path.insert(0, SKILL_SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                                Table, TableStyle, Image, KeepTogether, CondPageBreak,
                                HRFlowable)
from reportlab.platypus.tableofcontents import TableOfContents
from PIL import Image as PILImage

# ---------------- fonts ----------------
FONT_DIR = "/usr/share/fonts"
pdfmetrics.registerFont(TTFont("NotoSerifSC", f"{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Regular.ttf"))
pdfmetrics.registerFont(TTFont("NotoSerifSC-Bold", f"{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Noto Sans SC", f"{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Noto Sans SC Bold", f"{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Bold.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif", f"{FONT_DIR}/truetype/freefont/FreeSerif.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif-Bold", f"{FONT_DIR}/truetype/freefont/FreeSerifBold.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif-Italic", f"{FONT_DIR}/truetype/freefont/FreeSerifItalic.ttf"))
pdfmetrics.registerFont(TTFont("FreeSerif-BoldItalic", f"{FONT_DIR}/truetype/freefont/FreeSerifBoldItalic.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuSans", f"{FONT_DIR}/truetype/dejavu/DejaVuSansMono.ttf"))
registerFontFamily("NotoSerifSC", normal="NotoSerifSC", bold="NotoSerifSC-Bold")
registerFontFamily("Noto Sans SC", normal="Noto Sans SC", bold="Noto Sans SC Bold")
registerFontFamily("FreeSerif", normal="FreeSerif", bold="FreeSerif-Bold",
                   italic="FreeSerif-Italic", boldItalic="FreeSerif-BoldItalic")
registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans")

from pdf import install_font_fallback  # noqa: E402
install_font_fallback()

# ---------------- palette: Template 07 Crystal Blue (fixed body palette) ----------------
PAGE_BG      = colors.HexColor("#f5f8fc")   # XL
SECTION_BG   = colors.HexColor("#edf2f9")   # XL
CARD_BG      = colors.HexColor("#e4ecf5")   # L
TABLE_STRIPE = colors.HexColor("#eef3fa")   # L
HEADER_FILL  = colors.HexColor("#1a4a7a")   # M
BORDER       = colors.HexColor("#c0d0e2")   # S
ACCENT       = colors.HexColor("#2d7ab3")   # XS
TEXT_PRIMARY = colors.HexColor("#142840")
TEXT_MUTED   = colors.HexColor("#5a7a96")

TABLE_HEADER_COLOR = HEADER_FILL
TABLE_ROW_EVEN = colors.white
TABLE_ROW_ODD = TABLE_STRIPE

# ---------------- layout constants ----------------
MARGIN = 0.9 * inch
PAGE_W, PAGE_H = A4
AVAIL_W = PAGE_W - 2 * MARGIN
AVAIL_H = PAGE_H - 2 * MARGIN
H1_THRESHOLD = AVAIL_H * 0.25
MAX_KEEP = PAGE_H * 0.4

OUT = "/home/z/my-project/scripts/recon_report/body.pdf"
DOC_TITLE = "20-Repo Tooling Recon and Orchestration Blueprint"

# ---------------- styles ----------------
body_style = ParagraphStyle("Body", fontName="FreeSerif", fontSize=10.5, leading=17,
                            alignment=TA_JUSTIFY, textColor=TEXT_PRIMARY,
                            spaceBefore=0, spaceAfter=10)
bullet_style = ParagraphStyle("Bullet", fontName="FreeSerif", fontSize=10.5, leading=16,
                              alignment=TA_LEFT, textColor=TEXT_PRIMARY,
                              leftIndent=18, firstLineIndent=-12, spaceAfter=7)
h1_style = ParagraphStyle("H1", fontName="FreeSerif", fontSize=22, leading=27,
                          alignment=TA_LEFT, textColor=TEXT_PRIMARY,
                          spaceBefore=0, spaceAfter=4)
h2_style = ParagraphStyle("H2", fontName="FreeSerif", fontSize=15, leading=20,
                          alignment=TA_LEFT, textColor=HEADER_FILL,
                          spaceBefore=16, spaceAfter=8)
caption_style = ParagraphStyle("Caption", fontName="FreeSerif", fontSize=8.5, leading=12,
                               alignment=TA_CENTER, textColor=TEXT_MUTED,
                               spaceBefore=3, spaceAfter=6)
toc_title_style = ParagraphStyle("TocTitle", fontName="FreeSerif", fontSize=20, leading=25,
                                 textColor=TEXT_PRIMARY, spaceAfter=14)
th_style = ParagraphStyle("TH", fontName="FreeSerif", fontSize=9.5, leading=12.5,
                          textColor=colors.white, alignment=TA_CENTER)
td_left = ParagraphStyle("TDL", fontName="FreeSerif", fontSize=9.5, leading=13,
                         textColor=TEXT_PRIMARY, alignment=TA_LEFT)
td_center = ParagraphStyle("TDC", fontName="FreeSerif", fontSize=9.5, leading=13,
                           textColor=TEXT_PRIMARY, alignment=TA_CENTER)
th_style_s = ParagraphStyle("THS", fontName="FreeSerif", fontSize=8.5, leading=11,
                            textColor=colors.white, alignment=TA_CENTER)
td_left_s = ParagraphStyle("TDLS", fontName="FreeSerif", fontSize=8.5, leading=11.5,
                           textColor=TEXT_PRIMARY, alignment=TA_LEFT)
td_center_s = ParagraphStyle("TDCS", fontName="FreeSerif", fontSize=8.5, leading=11.5,
                             textColor=TEXT_PRIMARY, alignment=TA_CENTER)


# ---------------- doc template with TOC support ----------------
class TocDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if hasattr(flowable, "bookmark_name"):
            level = getattr(flowable, "bookmark_level", 0)
            text = getattr(flowable, "bookmark_text", "")
            key = getattr(flowable, "bookmark_key", "")
            # displayed body page number = physical page - 1 (page 1 is the TOC, shown as roman i)
            self.notify("TOCEntry", (level, text, self.page - 1, key))


def deco(canvas, doc):
    """Header + footer for every body page. English-only text -> FreeSerif is safe."""
    canvas.saveState()
    # header
    canvas.setFont("FreeSerif", 7.5)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(MARGIN, PAGE_H - 42, DOC_TITLE.upper())
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(1.2)
    canvas.line(MARGIN, PAGE_H - 48, PAGE_W - MARGIN, PAGE_H - 48)
    # footer
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 44, PAGE_W - MARGIN, 44)
    canvas.setFont("FreeSerif", 7.5)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(MARGIN, 32, "OWL-DNS-Synergy Engineering · Super Z")
    page_label = "i" if doc.page == 1 else str(doc.page - 1)
    canvas.drawRightString(PAGE_W - MARGIN, 32, page_label)
    canvas.restoreState()


# ---------------- helpers ----------------
def add_heading(text, style, level=0):
    key = "h_%s" % hashlib.md5(text.encode()).hexdigest()[:8]
    p = Paragraph('<a name="%s"/><b>%s</b>' % (key, text), style)
    p.bookmark_name = key
    p.bookmark_level = level
    p.bookmark_text = text
    p.bookmark_key = key
    return p


def safe_keep_together(elements):
    total_h = 0
    for el in elements:
        w, h = el.wrap(AVAIL_W, PAGE_H)
        total_h += h
    if total_h <= MAX_KEEP:
        return [KeepTogether(elements)]
    elif len(elements) >= 2:
        return [KeepTogether(elements[:2])] + list(elements[2:])
    return list(elements)


def embed_image(path, max_width, max_height=PAGE_H * 0.35):
    pil = PILImage.open(path)
    ow, oh = pil.size
    ratio = min(max_width / ow if ow > max_width else 1.0,
                max_height / oh if oh > max_height else 1.0)
    return Image(path, width=ow * ratio, height=oh * ratio)


def build_table(spec):
    small = spec.get("small", False)
    th = th_style_s if small else th_style
    tdl = td_left_s if small else td_left
    tdc = td_center_s if small else td_center
    aligns = spec.get("align", ["left"] * len(spec["header"]))
    ratios = spec["ratios"]
    total = sum(ratios)
    col_w = [r / total * AVAIL_W for r in ratios]
    assert sum(col_w) <= AVAIL_W + 0.5

    def cell(text, col):
        st = tdc if aligns[col] == "center" else tdl
        return Paragraph(str(text), st)

    data = [[Paragraph("<b>%s</b>" % h, th) for h in spec["header"]]]
    for row in spec["rows"]:
        data.append([cell(c, i) for i, c in enumerate(row)])

    t = Table(data, colWidths=col_w, repeatRows=1, hAlign="CENTER")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        style.append(("BACKGROUND", (0, i), (-1, i),
                      TABLE_ROW_ODD if i % 2 == 1 else TABLE_ROW_EVEN))
    t.setStyle(TableStyle(style))
    return t


# ---------------- donut chart ----------------
def make_donut(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    labels = ["ADOPT - 7", "REFERENCE - 9", "REJECT - 4"]
    sizes = [7, 9, 4]
    cols = ["#2d7ab3", "#1a4a7a", "#c0d0e2"]

    fig, ax = plt.subplots(figsize=(5.6, 2.9), constrained_layout=True)
    ax.pie(sizes, colors=cols, startangle=90, counterclock=False,
           wedgeprops=dict(width=0.35, edgecolor="white", linewidth=1.5))
    ax.text(0, 0, "20\nrepos", ha="center", va="center",
            fontsize=15, color="#142840", linespacing=1.3)
    ax.legend(labels, loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, fontsize=10.5, handlelength=1.0, handleheight=1.0)
    ax.set_aspect("equal")
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


# ---------------- build story ----------------
from content_data import BLOCKS  # noqa: E402


def main():
    donut = "/home/z/my-project/scripts/recon_report/verdict_donut.png"
    make_donut(donut)

    story = []
    # TOC page (front matter, roman i)
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("TOC0", fontName="FreeSerif", fontSize=12, leading=20,
                       leftIndent=6, textColor=TEXT_PRIMARY),
        ParagraphStyle("TOC1", fontName="FreeSerif", fontSize=10.5, leading=16,
                       leftIndent=24, textColor=TEXT_MUTED),
    ]
    story.append(Paragraph("<b>Table of Contents</b>", toc_title_style))
    story.append(HRFlowable(width="100%", color=ACCENT, thickness=1.2,
                            spaceBefore=0, spaceAfter=10))
    story.append(toc)
    story.append(PageBreak())

    chapter = 0
    pending_h = [None]  # boxed so nested helpers can rebind

    def flush_with(first_body):
        """Attach pending heading group to first body element (anti-orphan)."""
        if pending_h[0] is not None:
            group = pending_h[0] + [first_body]
            pending_h[0] = None
            return safe_keep_together(group)
        return [first_body]

    def flush_with_keep(flowable, cap):
        """Heading + (flowable + caption) kept together, flat list, no nesting."""
        if pending_h[0] is not None:
            group = pending_h[0] + [flowable, cap]
            pending_h[0] = None
            return safe_keep_together(group)
        return safe_keep_together([flowable, cap])

    for kind, payload in BLOCKS:
        if kind == "h1":
            chapter += 1
            story.append(CondPageBreak(H1_THRESHOLD))
            h = add_heading("%d.  %s" % (chapter, payload), h1_style, level=0)
            rule = HRFlowable(width="100%", color=ACCENT, thickness=1.2,
                              spaceBefore=2, spaceAfter=12)
            pending_h[0] = [h, rule]
        elif kind == "h2":
            story.append(CondPageBreak(H1_THRESHOLD * 0.6))
            h = add_heading(payload, h2_style, level=1)
            pending_h[0] = [h]
        elif kind == "p":
            for fl in flush_with(Paragraph(payload, body_style)):
                story.append(fl)
        elif kind == "bullet":
            first = Paragraph("\u2022\u00a0\u00a0" + payload[0], bullet_style)
            for fl in flush_with(first):
                story.append(fl)
            for item in payload[1:]:
                story.append(Paragraph("\u2022\u00a0\u00a0" + item, bullet_style))
            story.append(Spacer(1, 4))
        elif kind == "table":
            t = build_table(payload)
            cap = Paragraph(payload["caption"], caption_style)
            story.append(Spacer(1, 8))
            if len(payload["rows"]) <= 8:
                for fl in flush_with_keep(t, cap):
                    story.append(fl)
            else:
                for fl in flush_with(t):
                    story.append(fl)
                story.append(Spacer(1, 6))
                story.append(cap)
            story.append(Spacer(1, 12))
        elif kind == "img":
            img = embed_image(payload["path"], max_width=payload.get("max_w", 452))
            cap = Paragraph(payload["caption"], caption_style)
            for fl in flush_with_keep(img, cap):
                story.append(fl)
            story.append(Spacer(1, 10))

    doc = TocDocTemplate(
        OUT, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
        title=DOC_TITLE, author="Z.ai", creator="Z.ai",
        subject="External dependency triage for OWL-DNS-Synergy Phase-2/3",
    )
    doc.multiBuild(story, onFirstPage=deco, onLaterPages=deco)
    print("body.pdf written")


if __name__ == "__main__":
    main()
