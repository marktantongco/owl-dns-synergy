#!/usr/bin/env python3
"""
AutoClaw Ecosystem Synergy Research Deep-Dive
=============================================

Generates a comprehensive multi-section PDF report profiling 9 GitHub
repositories in the AutoClaw / GLM-proxy ecosystem, an architecture
comparison matrix, a Top-15 synergy integration matrix, a 3-phase
implementation roadmap, an anti-bot analysis, recommendations, and
a conclusion.

Output: /home/z/my-project/download/AutoClaw-Synergy-Research-Deep-Dive.pdf
"""

import os
import sys
import time
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable, NextPageTemplate
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ─── Font Registration ─────────────────────────────────────────────────────
# User requirement: Helvetica for body, Helvetica-Bold for headings.
# Helvetica is one of the 14 PDF "base-14" fonts and ships with every
# PDF reader; we therefore do NOT need to register it explicitly.
# We register Noto Sans SC as a graceful fallback for any CJK glyphs
# (the report is in English, but ZH error-message samples may appear).

FONT_DIR = '/usr/share/fonts'

# Track which fallback fonts actually registered (for graceful degradation)
FALLBACK_SANS = None
FALLBACK_SANS_BOLD = None

try:
    pdfmetrics.registerFont(TTFont('NotoSansSC',
        f'{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('NotoSansSC-Bold',
        f'{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Bold.ttf'))
    registerFontFamily('NotoSansSC',
        normal='NotoSansSC', bold='NotoSansSC-Bold')
    FALLBACK_SANS = 'NotoSansSC'
    FALLBACK_SANS_BOLD = 'NotoSansSC-Bold'
except Exception:
    try:
        pdfmetrics.registerFont(TTFont('NotoSansSC',
            f'{FONT_DIR}/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('NotoSansSC-Bold',
            f'{FONT_DIR}/truetype/dejavu/DejaVuSans-Bold.ttf'))
        registerFontFamily('NotoSansSC',
            normal='NotoSansSC', bold='NotoSansSC-Bold')
        FALLBACK_SANS = 'NotoSansSC'
        FALLBACK_SANS_BOLD = 'NotoSansSC-Bold'
    except Exception:
        # Last resort: rely on Helvetica (built-in) only
        FALLBACK_SANS = 'Helvetica'
        FALLBACK_SANS_BOLD = 'Helvetica-Bold'

# Use Helvetica (built-in base-14 font) as requested
BODY_FONT = 'Helvetica'
BODY_FONT_BOLD = 'Helvetica-Bold'
BODY_FONT_ITALIC = 'Helvetica-Oblique'
MONO_FONT = 'Courier'
MONO_FONT_BOLD = 'Courier-Bold'

# ─── Color Palette ─────────────────────────────────────────────────────────
COLOR_DARK_BLUE = colors.HexColor('#1a365d')   # primary heading
COLOR_ACCENT_BLUE = colors.HexColor('#2563eb')  # accents
COLOR_BLACK = colors.black
COLOR_GRAY_DARK = colors.HexColor('#2d3748')
COLOR_GRAY_MED = colors.HexColor('#4a5568')
COLOR_GRAY_LIGHT = colors.HexColor('#e2e8f0')
COLOR_ROW_ALT = colors.HexColor('#f7fafc')      # alternating row
COLOR_ROW_HEADER = colors.HexColor('#1a365d')   # table header bg
COLOR_TABLE_GRID = colors.HexColor('#cbd5e0')
COLOR_PRIORITY1 = colors.HexColor('#c6f6d5')    # green tint
COLOR_PRIORITY2 = colors.HexColor('#fefcbf')    # yellow tint
COLOR_PRIORITY3 = colors.HexColor('#fed7d7')    # red tint
COLOR_HIGH = colors.HexColor('#9b2c2c')
COLOR_MED = colors.HexColor('#b7791f')
COLOR_LOW = colors.HexColor('#2f855a')

# ─── Paragraph Styles ─────────────────────────────────────────────────────
styles = getSampleStyleSheet()

style_cover_title = ParagraphStyle(
    'CoverTitle', parent=styles['Title'],
    fontName=BODY_FONT_BOLD, fontSize=28, leading=34,
    textColor=COLOR_DARK_BLUE, alignment=TA_CENTER,
    spaceAfter=14
)
style_cover_subtitle = ParagraphStyle(
    'CoverSubtitle', parent=styles['Normal'],
    fontName=BODY_FONT, fontSize=14, leading=18,
    textColor=COLOR_GRAY_DARK, alignment=TA_CENTER,
    spaceAfter=10
)
style_cover_meta = ParagraphStyle(
    'CoverMeta', parent=styles['Normal'],
    fontName=BODY_FONT, fontSize=11, leading=15,
    textColor=COLOR_GRAY_MED, alignment=TA_CENTER,
    spaceAfter=6
)

style_h1 = ParagraphStyle(
    'H1', parent=styles['Heading1'],
    fontName=BODY_FONT_BOLD, fontSize=20, leading=24,
    textColor=COLOR_DARK_BLUE, spaceBefore=18, spaceAfter=12,
    keepWithNext=True
)
style_h2 = ParagraphStyle(
    'H2', parent=styles['Heading2'],
    fontName=BODY_FONT_BOLD, fontSize=15, leading=19,
    textColor=COLOR_DARK_BLUE, spaceBefore=14, spaceAfter=8,
    keepWithNext=True
)
style_h3 = ParagraphStyle(
    'H3', parent=styles['Heading3'],
    fontName=BODY_FONT_BOLD, fontSize=12, leading=16,
    textColor=COLOR_ACCENT_BLUE, spaceBefore=10, spaceAfter=6,
    keepWithNext=True
)

style_body = ParagraphStyle(
    'Body', parent=styles['Normal'],
    fontName=BODY_FONT, fontSize=10.5, leading=15,
    textColor=COLOR_BLACK, alignment=TA_JUSTIFY,
    spaceAfter=8
)
style_body_left = ParagraphStyle(
    'BodyLeft', parent=style_body,
    alignment=TA_LEFT
)
style_bullet = ParagraphStyle(
    'Bullet', parent=style_body,
    leftIndent=18, bulletIndent=6, spaceAfter=4,
    alignment=TA_LEFT
)
style_table_cell = ParagraphStyle(
    'TableCell', parent=styles['Normal'],
    fontName=BODY_FONT, fontSize=8.5, leading=11,
    textColor=COLOR_BLACK, alignment=TA_LEFT
)
style_table_cell_bold = ParagraphStyle(
    'TableCellBold', parent=style_table_cell,
    fontName=BODY_FONT_BOLD
)
style_table_header = ParagraphStyle(
    'TableHeader', parent=styles['Normal'],
    fontName=BODY_FONT_BOLD, fontSize=8.5, leading=11,
    textColor=colors.white, alignment=TA_LEFT
)
style_table_header_center = ParagraphStyle(
    'TableHeaderCenter', parent=style_table_header,
    alignment=TA_CENTER
)
style_table_cell_center = ParagraphStyle(
    'TableCellCenter', parent=style_table_cell,
    alignment=TA_CENTER
)
style_toc_entry_1 = ParagraphStyle(
    'TOCEntry1', parent=styles['Normal'],
    fontName=BODY_FONT_BOLD, fontSize=11, leading=16,
    textColor=COLOR_DARK_BLUE, leftIndent=0
)
style_toc_entry_2 = ParagraphStyle(
    'TOCEntry2', parent=styles['Normal'],
    fontName=BODY_FONT, fontSize=10, leading=14,
    textColor=COLOR_GRAY_DARK, leftIndent=18
)
style_callout = ParagraphStyle(
    'Callout', parent=style_body,
    fontName=BODY_FONT_ITALIC, fontSize=10, leading=14,
    textColor=COLOR_GRAY_DARK, leftIndent=12, rightIndent=12,
    spaceBefore=6, spaceAfter=8,
    backColor=COLOR_GRAY_LIGHT, borderPadding=8
)
style_code = ParagraphStyle(
    'Code', parent=styles['Code'],
    fontName=MONO_FONT, fontSize=9, leading=12,
    textColor=COLOR_DARK_BLUE,
    backColor=COLOR_GRAY_LIGHT, borderPadding=6,
    leftIndent=8, rightIndent=8, spaceAfter=8
)

# ─── Page Header / Footer ─────────────────────────────────────────────────
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 22 * mm
RIGHT_MARGIN = 22 * mm
TOP_MARGIN = 25 * mm
BOTTOM_MARGIN = 22 * mm

def _draw_header_footer(canvas, doc):
    """Draw running header (left) + page number (right) + bottom rule."""
    canvas.saveState()
    # Header
    canvas.setFont(BODY_FONT, 8)
    canvas.setFillColor(COLOR_GRAY_MED)
    canvas.drawString(LEFT_MARGIN, PAGE_HEIGHT - 14 * mm,
        'AutoClaw Ecosystem Synergy Research Deep-Dive')
    canvas.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 14 * mm,
        'Super Z AI  -  2026-09-19')
    canvas.setStrokeColor(COLOR_GRAY_LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT_MARGIN, PAGE_HEIGHT - 16 * mm,
               PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 16 * mm)
    # Footer
    canvas.setFont(BODY_FONT, 8)
    canvas.setFillColor(COLOR_GRAY_MED)
    page_label = 'Page %d' % doc.page
    canvas.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, 12 * mm, page_label)
    canvas.drawString(LEFT_MARGIN, 12 * mm,
        'AutoClaw Synergy Research - Confidential')
    canvas.line(LEFT_MARGIN, 15 * mm,
                PAGE_WIDTH - RIGHT_MARGIN, 15 * mm)
    canvas.restoreState()

def _draw_cover_only(canvas, doc):
    """Cover page: only footer, no running header."""
    canvas.saveState()
    canvas.setFont(BODY_FONT, 8)
    canvas.setFillColor(COLOR_GRAY_MED)
    canvas.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, 12 * mm,
        'Page %d' % doc.page)
    canvas.drawString(LEFT_MARGIN, 12 * mm,
        'AutoClaw Synergy Research - Confidential')
    canvas.setStrokeColor(COLOR_GRAY_LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT_MARGIN, 15 * mm,
                PAGE_WIDTH - RIGHT_MARGIN, 15 * mm)
    canvas.restoreState()

# ─── Document Template with TOC support ──────────────────────────────────
class SynergyReportDoc(BaseDocTemplate):
    """Custom doc template that auto-populates TableOfContents."""

    def __init__(self, filename, **kw):
        BaseDocTemplate.__init__(self, filename, **kw)
        # Cover frame (full bleed-ish margins, no header)
        cover_frame = Frame(LEFT_MARGIN, BOTTOM_MARGIN,
            PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN,
            PAGE_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN,
            id='cover', showBoundary=0)
        # Body frame (with header reserved space)
        body_frame = Frame(LEFT_MARGIN, BOTTOM_MARGIN,
            PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN,
            PAGE_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN - 8 * mm,
            id='body', showBoundary=0)
        self.addPageTemplates([
            PageTemplate(id='Cover', frames=[cover_frame],
                         onPage=_draw_cover_only),
            PageTemplate(id='Body', frames=[body_frame],
                         onPage=_draw_header_footer),
        ])
        self._toc_seq = 0

    def afterFlowable(self, flowable):
        """Register H1/H2 paragraphs into the TOC and PDF outline."""
        if isinstance(flowable, Paragraph):
            sname = flowable.style.name
            text = flowable.getPlainText()
            if sname == 'H1':
                self._toc_seq += 1
                key = 'h1-%d' % self._toc_seq
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, 0, 0)
                # canonical 3-tuple form for reliable TOC convergence
                self.notify('TOCEntry', (0, text, self.page))
            elif sname == 'H2':
                self._toc_seq += 1
                key = 'h2-%d' % self._toc_seq
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, 1, 0)
                self.notify('TOCEntry', (1, text, self.page))


# ─── Helper: alternating-row styled table ─────────────────────────────────
def styled_table(data, col_widths=None, header_rows=1, repeat_header=True,
                 row_height=None, font_size=8.5):
    """Build a Table with header bg, alternating row colors, grid."""
    tbl = Table(data, colWidths=col_widths, rowHeights=row_height,
                repeatRows=header_rows if repeat_header else 0)
    cmds = [
        ('BACKGROUND', (0, 0), (-1, header_rows - 1), COLOR_ROW_HEADER),
        ('TEXTCOLOR', (0, 0), (-1, header_rows - 1), colors.white),
        ('FONTNAME', (0, 0), (-1, header_rows - 1), BODY_FONT_BOLD),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, header_rows - 1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.4, COLOR_TABLE_GRID),
        ('LINEBELOW', (0, header_rows - 1), (-1, header_rows - 1),
            1.2, COLOR_DARK_BLUE),
    ]
    # alternating rows
    for r in range(header_rows, len(data)):
        if (r - header_rows) % 2 == 1:
            cmds.append(('BACKGROUND', (0, r), (-1, r), COLOR_ROW_ALT))
    tbl.setStyle(TableStyle(cmds))
    return tbl


def p(text, style=style_table_cell):
    """Wrap text in a Paragraph for table cells (so it wraps)."""
    return Paragraph(text, style)


def impact_cell(label, color):
    """Coloured impact pill for table cells."""
    st = ParagraphStyle('pill', parent=style_table_cell_center,
                        fontName=BODY_FONT_BOLD,
                        textColor=color, fontSize=8.5)
    return Paragraph(label, st)


# ─── Build story sections ─────────────────────────────────────────────────
story = []

# ═══ 1. COVER PAGE ═════════════════════════════════════════════════════
story.append(NextPageTemplate('Body'))  # subsequent pages use Body template

# vertical spacer to center title visually
story.append(Spacer(1, 55 * mm))

# Top accent bar (table with dark blue fill)
top_bar = Table([['']], colWidths=[PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN],
                rowHeights=[3 * mm])
top_bar.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), COLOR_DARK_BLUE)]))
story.append(top_bar)
story.append(Spacer(1, 10 * mm))

story.append(Paragraph('AutoClaw Ecosystem', style_cover_title))
story.append(Paragraph('Synergy Research Deep-Dive', style_cover_title))
story.append(Spacer(1, 6 * mm))

# subtitle with accent rule
story.append(HRFlowable(width='40%', thickness=1.2,
                        color=COLOR_ACCENT_BLUE, spaceBefore=4, spaceAfter=10,
                        hAlign='CENTER'))
story.append(Paragraph(
    '9-Repo Investigation, Integration Matrix &amp; Enhancement Roadmap',
    style_cover_subtitle))
story.append(Spacer(1, 22 * mm))

# Meta block (centered card)
meta_data = [
    [p('Date', style_table_cell_bold), p('2026-09-19')],
    [p('Author', style_table_cell_bold), p('Super Z AI')],
    [p('Document Class', style_table_cell_bold), p('Research - Confidential')],
    [p('Scope', style_table_cell_bold),
     p('9 GitHub repositories; 7 active, 2 empty')],
    [p('Total Innovations Identified', style_table_cell_bold), p('35+ unique')],
    [p('Baseline Project', style_table_cell_bold),
     p('andreanocalvin/autoclaw-autologin (78/78 tests passing, 41 hardening fixes)')],
    [p('Synergies Selected', style_table_cell_bold), p('Top 15 (3 priority tiers)')],
]
meta_tbl = Table(meta_data, colWidths=[55 * mm, 95 * mm])
meta_tbl.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (0, -1), COLOR_GRAY_LIGHT),
    ('FONTNAME', (0, 0), (0, -1), BODY_FONT_BOLD),
    ('FONTSIZE', (0, 0), (-1, -1), 9.5),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('BOX', (0, 0), (-1, -1), 0.6, COLOR_DARK_BLUE),
    ('INNERGRID', (0, 0), (-1, -1), 0.3, COLOR_TABLE_GRID),
]))
story.append(meta_tbl)

story.append(Spacer(1, 30 * mm))
bottom_bar = Table([['']], colWidths=[PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN],
                   rowHeights=[2 * mm])
bottom_bar.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), COLOR_ACCENT_BLUE)]))
story.append(bottom_bar)

story.append(PageBreak())

# ═══ 2. TABLE OF CONTENTS ══════════════════════════════════════════════
story.append(Paragraph('Table of Contents', style_h1))
story.append(HRFlowable(width='100%', thickness=1.2,
                         color=COLOR_DARK_BLUE, spaceAfter=14))

toc = TableOfContents()
toc.levelStyles = [style_toc_entry_1, style_toc_entry_2]
story.append(toc)
story.append(PageBreak())

# ═══ 3. EXECUTIVE SUMMARY ══════════════════════════════════════════════
story.append(Paragraph('1. Executive Summary', style_h1))
story.append(HRFlowable(width='100%', thickness=1.0,
                         color=COLOR_DARK_BLUE, spaceAfter=10))

story.append(Paragraph(
    'This report documents a structured investigation of nine GitHub '
    'repositories in the AutoClaw and GLM-proxy ecosystem, conducted to '
    'identify complementary innovations that could be ported into our local '
    'baseline project (andreanocalvin/autoclaw-autologin). Seven of the nine '
    'repositories contained substantial production-quality code; the '
    'remaining two were empty placeholders with no source files at all. '
    'Across the seven active repos we catalogued more than thirty-five '
    'unique technical innovations spanning anti-bot evasion, '
    'wire-format translation, streaming protocol handling, tool-calling '
    'shims, session hygiene, and operator dashboards. The breadth of '
    'this catalogue demonstrates that the broader open-source community has '
    'collectively solved many of the operational problems our local project '
    'still faces.',
    style_body))

story.append(Paragraph(
    'Our local autoclaw-autologin baseline already possesses the strongest '
    'security and memory-hardening posture of any repo in the surveyed set. '
    'It has received forty-one targeted security and memory fixes and now '
    'passes seventy-eight out of seventy-eight tests, giving it a verifiable '
    'regression-safety net that none of the upstream community projects '
    'currently match. Two of the surveyed repos (ai-router-switch with 930 '
    'tests, and glm-free-api-admin-panel with integration tests) come close '
    'on coverage, but neither has the same focus on memory-safety and '
    'token-lifecycle correctness that our baseline enforces. This means we '
    'are well-positioned to absorb external innovations without '
    'compromising our existing security guarantees.',
    style_body))

story.append(Paragraph(
    'From the thirty-five-plus innovations we distilled a Top-15 synergy '
    'matrix ranked by a combined impact/effort heuristic. Five synergies '
    'fall into Priority-1 (must-have, easy), seven into Priority-2 '
    '(should-have, medium), and three into Priority-3 (nice-to-have, hard). '
    'Priority-1 items are predominantly defensive guards lifted directly '
    'from eequaled/GLM_proxy - output-cap clamping, system-banner '
    'injection, permanent-failure negative caching, Chinese-to-English '
    'error translation, and the in-chat !router command from '
    'ai-router-switch. Each of these is implementable in under a day and '
    'each closes a documented production failure mode that we have '
    'observed in our own logs.',
    style_body))

story.append(Paragraph(
    'Priority-2 items expand our API surface into the Anthropic ecosystem, '
    'which is the single largest remaining functional gap. Adding '
    '/v1/messages (from OmniClaw) unlocks native Claude Code support, '
    'Claude credit-tier routing (from GLM_proxy) lets us exploit the '
    'cheaper haiku and medium sonnet tiers automatically, per-chat '
    'fingerprint isolation (from ai-router-switch) defeats the '
    'conversation-merge attacks we see in production, and the DSML '
    'tool-calling shim plus reasoning_content phase separation (both '
    'from chat-z-ai-proxy) add OpenAI-compatible function calling and '
    'o1-style reasoning transparency for models that lack either '
    'natively. Throwaway chat sessions from glm-free-api-admin-panel '
    'finish the tier by closing a context-rot vulnerability.',
    style_body))

story.append(Paragraph(
    'Priority-3 items are advanced hardening measures that pay off in '
    'adversarial environments but carry non-trivial integration cost. The '
    'cloud-to-local WebSocket fallback from GLM_proxy provides resilience '
    'when the upstream API is unreachable but a local AutoClaw desktop '
    'agent is online. The uTLS Chrome-120 ClientHello from '
    'glm-free-api-admin-panel defeats JA3 fingerprinting entirely and is '
    'the most robust anti-bot measure we have surveyed - but it requires '
    'either a Go or Rust TLS bridge since Python\'s ssl module cannot '
    'forge ClientHellos. Finally, the local React dashboard from '
    'OmniClaw would give operators live metrics, request logs, and '
    'rate-limit visibility that our current HTML dashboard lacks.',
    style_body))

story.append(Paragraph(
    'The recommended path forward is to execute Phase-1 immediately '
    '(estimated one day of engineering effort), Phase-2 over two-to-three '
    'days, and to treat Phase-3 as a discretionary one-week investment '
    'triggered by demonstrated adversarial need. This sequencing preserves '
    'our security posture while systematically closing the gaps identified '
    'in the architecture comparison matrix. The remainder of this report '
    'provides the per-repo inventory, the comparison matrix, the full '
    'synergy table with difficulty and impact ratings, the phased '
    'roadmap, an anti-bot deep-dive, and concrete recommendations.',
    style_body))

story.append(PageBreak())

# ═══ 4. REPOSITORY INVENTORY ═══════════════════════════════════════════
story.append(Paragraph('2. Repository Inventory', style_h1))
story.append(HRFlowable(width='100%', thickness=1.0,
                         color=COLOR_DARK_BLUE, spaceAfter=10))

story.append(Paragraph(
    'The nine repositories below were investigated in full. For each, we '
    'record the canonical GitHub URL, primary language and framework, '
    'maturity indicators (commit count, star count where available, test '
    'suite status), licence status, the most salient innovation tags, and '
    'a qualitative integration-potential rating. Integration potential is '
    'rated HIGH when the repo contains multiple directly portable '
    'features, MEDIUM when portability requires non-trivial adaptation, '
    'LOW for limited-salvage repos, BASELINE for our own project, and '
    'N/A for empty repositories. The data below was verified by direct '
    'clone and inspection; no facts have been inferred or extrapolated.',
    style_body))

# ---- Repo 1: eequaled/GLM_proxy
story.append(Paragraph('2.1 eequaled/GLM_proxy', style_h2))
story.append(Paragraph(
    'Node.js MIT-licensed proxy that has become the de facto reference '
    'implementation for the GLM-to-OpenAI translation layer. Its dual '
    'wire-format support (OpenAI Chat Completions and Anthropic Messages) '
    'makes it directly usable from both the OpenAI Python SDK and Claude '
    'Code. The most production-relevant innovation is a cloud-to-local '
    'fallback path that transparently routes traffic through a local '
    'AutoClaw desktop agent over WebSocket when the upstream cloud '
    'endpoint fails, giving best-in-class resilience. It also introduces '
    'an output-cap clamping guard that prevents a silent substitution '
    'failure mode we have confirmed by probe: requesting more than '
    '131,072 output tokens causes the cloud to silently substitute '
    'DeepSeek and bill DeepSeek credits. Additional innovations include '
    'credit-tier routing for Claude models (opus to High, sonnet to '
    'Medium, haiku to Low), a sixty-second permanent-failure negative '
    'cache for quota-exhausted and unknown-model responses, a '
    'Chinese-to-English error translation map for stable client-side '
    'messaging, and --doctor / --test-models subcommands for self-service '
    'operational diagnostics. Integration potential: HIGH.',
    style_body))

# ---- Repo 2: guell11/OmniClaw-GLM-Proxy
story.append(Paragraph('2.2 guell11/OmniClaw-GLM-Proxy', style_h2))
story.append(Paragraph(
    'Node.js proxy with a nominal MIT licence declared in the README but '
    'no actual LICENSE file committed to the repository. Its standout '
    'feature is a tri-API surface that supports OpenAI Chat Completions, '
    'the newer OpenAI Responses API, and Anthropic Messages in a single '
    'binary. The repo ships a React dashboard with live metrics, a '
    'request log, a masked-IP client list, and rate-limit-block counters, '
    'which is the most complete operator surface we have surveyed. '
    'One-click integration setup writes configuration files into '
    '~/.claude, ~/.codex, and ~/.config/opencode so a new operator can '
    'go from clone to live in minutes. Internally it implements a local '
    'compaction envelope for long conversations, per-client '
    'previous_response_id tracking for the Responses API, and an '
    'agent-prompt synchronisation layer that keeps client-side system '
    'prompts in lock-step with server-side prompts. Integration '
    'potential: HIGH.',
    style_body))

# ---- Repo 3: andreanocalvin/autoclaw-autologin (BASELINE)
story.append(Paragraph('2.3 andreanocalvin/autoclaw-autologin (BASELINE)', style_h2))
story.append(Paragraph(
    'Python project, our base and currently the most operationally '
    'hardened repo in the surveyed set. There is no committed LICENSE '
    'file - an item we recommend addressing as part of the synergy work, '
    'since most downstream integrators will not adopt an unlicensed '
    'project regardless of technical merit. The repo harvests Google '
    'OAuth tokens via CloakBrowser (a patched C++ Chromium with '
    'fifty-eight patches targeting Cloudflare, reCAPTCHA, '
    'FingerprintJS, and BrowserScan detection), rotates them '
    'round-robin across requests, and monitors wallet/credit balances '
    'proactively. Our local fork has received forty-one targeted '
    'security and memory hardening fixes and currently passes '
    'seventy-eight out of seventy-eight tests, giving it the strongest '
    'regression-safety net of any repo surveyed. This is the project '
    'into which the Top-15 synergies will be integrated; it is rated '
    'BASELINE rather than HIGH/MED/LOW because it is the target, not a '
    'donor.',
    style_body))

# ---- Repo 4: sitimas9/autoclaw2api
story.append(Paragraph('2.4 sitimas9/autoclaw2api', style_h2))
story.append(Paragraph(
    'Python FastAPI rewrite with a nominal MIT licence declared in the '
    'README but no committed LICENSE file. It is a server-first redesign '
    'that deliberately drops CloakBrowser - there is no 535MB stealth '
    'Chromium bundled - and instead requires operators to manually import '
    'desktop-extracted bearer tokens. Authentication is a simple '
    'bearer-password scheme. The repo ships systemd unit files and an '
    'Nginx reverse-proxy config, integrates with the 9router multi-model '
    'router, and pins a minimal five-dependency requirements list. The '
    'architectural stance is interesting because it implies that '
    'production deployments should run on a server without a desktop '
    'environment, with token harvesting performed elsewhere. Integration '
    'potential: MEDIUM - the deployment artifacts are directly useful, '
    'but the absence of anti-bot measures means it cannot replace our '
    'CloakBrowser path.',
    style_body))

# ---- Repo 5: NiceBdsmer/glm-web-proxy-v2 (EMPTY)
story.append(Paragraph('2.5 NiceBdsmer/glm-web-proxy-v2 (EMPTY)', style_h2))
story.append(Paragraph(
    'Empty repository. No code, no README, no LICENSE, no commits beyond '
    'the initial creation. Possibly a placeholder for a planned successor '
    'to a v1 project, or a fork target that was never developed further. '
    'Integration potential: N/A. We record it here only because it '
    'appears in the upstream autoclaw-autologin documentation as a '
    'recommended companion project; readers should treat it as '
    'non-existent for integration purposes and revisit it only if its '
    'author commits code. No further analysis is possible without source.',
    style_body))

# ---- Repo 6: tt-52101/chat-z-ai-proxy-web2api-free
story.append(Paragraph('2.6 tt-52101/chat-z-ai-proxy-web2api-free', style_h2))
story.append(Paragraph(
    'Python FastAPI browser-delegation proxy with no committed licence. '
    'Its central design choice is to delegate all browser-flavoured work '
    'to a real system Chrome instance (channel="chrome") rather than '
    'embedding a stealth browser, letting the real page solve the Aliyun '
    'TRACELESS captcha in-band. Notable innovations include a DSML '
    'tool-calling shim that synthesises OpenAI function-calling responses '
    'for upstream models that lack a native tool API, and a StreamSieve '
    'state machine that performs reasoning_content phase separation - '
    'parsing the upstream SSE "phase" field to split thinking content '
    'from answering content for o1-style transparency. The repo also '
    'includes a generic HAR (HTTP Archive) analyser for reverse-'
    'engineering upstream wire formats, an x-signature HMAC generator '
    'for Aliyun-flavoured request signing, and an Aliyun TRACELESS '
    'captcha harvester. Integration potential: HIGH.',
    style_body))

# ---- Repo 7: eroslifestyle/ai-router-switch
story.append(Paragraph('2.7 eroslifestyle/ai-router-switch', style_h2))
story.append(Paragraph(
    'Python aiohttp router, MIT-licensed, and by a wide margin the most '
    'mature project in the surveyed set: nine hundred and thirty tests '
    'across six hundred and seventy-nine commits. It implements fourteen '
    'routing modes with THINK/ACT role-splitting, per-chat fingerprint '
    'isolation (a SHA-256 hash of the first user message, pinned on '
    'first use to defeat conversation-merge attacks), and a multi-port '
    'architecture that lets different model backends listen on different '
    'local ports. OAuth subscription rotation is built in. Operators can '
    'switch backends mid-conversation via an in-chat !router command '
    'that synthesises an SSE event stream from the router into the '
    'client. A loop_breaker detects stuck conversations (defined as four '
    'or more re-emits at eighty percent or more of context) and returns '
    'HTTP 400 to force a clean restart. Context-aware rerouting, '
    '/debug/* echo routes, and a self-fixer that patches its own '
    'configuration at runtime round out the feature set. Integration '
    'potential: HIGH.',
    style_body))

# ---- Repo 8: Dhau143/z-ai-glm-5.1 (EMPTY)
story.append(Paragraph('2.8 Dhau143/z-ai-glm-5.1 (EMPTY)', style_h2))
story.append(Paragraph(
    'Empty repository. No code, no README, no LICENSE, no commits beyond '
    'the initial creation. The name suggests an intent to expose the '
    'GLM-5.1 model (or a renamed upstream variant) through a proxy, but '
    'no implementation exists to evaluate. Integration potential: N/A. '
    'Like the other empty repo, we record it for completeness because it '
    'appears in cross-references from related projects, but no '
    'integration analysis is possible. If the author commits code in the '
    'future we will revisit.',
    style_body))

# ---- Repo 9: sabyaghosh/glm-free-api-admin-panel
story.append(Paragraph('2.9 sabyaghosh/glm-free-api-admin-panel', style_h2))
story.append(Paragraph(
    'Go-plus-Next.js project, MIT-licensed, and the most technically '
    'comprehensive anti-bot implementation in the surveyed set. It '
    'uses the Go uTLS library to forge a Chrome 120 ClientHello '
    '(HelloChrome_120) with HTTP/1.1-only NextProtos, defeating JA3 '
    'fingerprinting without needing a real browser. The Aliyun Captcha '
    'v3 defeating routine uses RC4-like cipher primitives to break the '
    'captcha token exchange. A device-token pool is maintained with a '
    '--topup patch for hot-reload of new tokens. Throwaway chat sessions '
    'create a fresh chat_id per request and delete it after the '
    'response, defeating context-rot. An async session pool amortises '
    'WebSocket setup costs. Agent-mode tolerant marker parsing and '
    'stream-truncation hardening with a one-hundred-and-eighty-second '
    'drain window round out the resilience work. The Next.js admin '
    'panel provides the operator UI. Integration potential: HIGH.',
    style_body))

story.append(PageBreak())

# ═══ 5. ARCHITECTURE COMPARISON MATRIX ══════════════════════════════════
story.append(Paragraph('3. Architecture Comparison Matrix', style_h1))
story.append(HRFlowable(width='100%', thickness=1.0,
                         color=COLOR_DARK_BLUE, spaceAfter=10))

story.append(Paragraph(
    'The matrix below compares the seven active repositories across eight '
    'architectural dimensions. Two repos (NiceBdsmer/glm-web-proxy-v2 and '
    'Dhau143/z-ai-glm-5.1) are excluded because they are empty and have no '
    'architecture to compare. The dimensions chosen - wire formats, auth '
    'strategy, anti-bot approach, local fallback, dashboard, streaming, '
    'tool calling, and tests - are the ones that most directly determine '
    'integration difficulty and operational risk. Reading the matrix '
    'top-to-bottom reveals that no single repo is uniformly strongest; '
    'each leads on at most two dimensions, which is why the synergy '
    'matrix in the next section is so valuable.',
    style_body))

# Build comparison table
matrix_header = [
    p('Dimension', style_table_header),
    p('eequaled/GLM_proxy', style_table_header_center),
    p('OmniClaw', style_table_header_center),
    p('autoclaw-autologin', style_table_header_center),
    p('autoclaw2api', style_table_header_center),
    p('chat-z-ai-proxy', style_table_header_center),
    p('ai-router-switch', style_table_header_center),
    p('glm-free-api-admin-panel', style_table_header_center),
]

matrix_rows = [
    ['Wire formats',
     'OpenAI + Anthropic',
     'OpenAI + Responses + Anthropic',
     'OpenAI only',
     'OpenAI only',
     'OpenAI only',
     'Anthropic only',
     'OpenAI + Anthropic'],
    ['Auth strategy',
     'Token file watch',
     'Token file watch',
     'OAuth + round-robin',
     'Manual import',
     'Browser localStorage',
     'OAuth + API keys',
     'Token pool + captcha'],
    ['Anti-bot',
     'Client fingerprint mimicry',
     'Client fingerprint mimicry',
     'CloakBrowser stealth',
     'None',
     'Real browser + system Chrome',
     'None',
     'uTLS Chrome 120 + Aliyun captcha v3'],
    ['Local fallback',
     'WS to desktop agent',
     'None',
     'None',
     'None',
     'None',
     'Multi-provider failover',
     'None'],
    ['Dashboard',
     'None',
     'React dashboard',
     'HTML dashboard',
     'None',
     'None',
     'None',
     'Next.js admin panel'],
    ['Streaming',
     'SSE passthrough + assembly',
     'SSE passthrough',
     'SSE passthrough',
     'SSE + accumulation',
     'SSE + phase separation',
     'Byte passthrough',
     'SSE + holdback'],
    ['Tool calling',
     'Native',
     'Native',
     'Native',
     'Native',
     'DSML shim',
     'Native',
     'Agent-mode shim'],
    ['Tests',
     'Some pen-tests',
     'None (aspirational)',
     '78/78 (our local)',
     'None',
     'None',
     '930',
     'Some integration tests'],
]

matrix_data = [matrix_header]
for r in matrix_rows:
    matrix_data.append([p(r[0], style_table_cell_bold)] +
                       [p(c, style_table_cell_center) for c in r[1:]])

# Column widths: dimension column wider, rest equal
avail = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
dim_w = 26 * mm
rest_w = (avail - dim_w) / 7.0
matrix_tbl = styled_table(matrix_data,
                          col_widths=[dim_w] + [rest_w] * 7,
                          font_size=7.5)
story.append(matrix_tbl)

story.append(Spacer(1, 6 * mm))

story.append(Paragraph(
    'Three observations stand out from the matrix. First, only two repos '
    '(GLM_proxy and glm-free-api-admin-panel) support both OpenAI and '
    'Anthropic wire formats; OmniClaw uniquely adds the OpenAI Responses '
    'API on top. Second, the anti-bot column shows the largest spread - '
    'no two repos use the same approach, and three repos (autoclaw2api, '
    'chat-z-ai-proxy for the captcha solver only, and ai-router-switch) '
    'effectively punt on the problem. Third, the tests column shows that '
    'ai-router-switch is the only community project with a serious test '
    'culture; our local baseline is the only other repo with a '
    'comprehensive passing suite. This confirms the synergy thesis: '
    'each repo contributes a non-overlapping set of strengths.',
    style_body))

story.append(PageBreak())

# ═══ 6. SYNERGY MATRIX - TOP 15 INTEGRATIONS ═════════════════════════════
story.append(Paragraph('4. Synergy Matrix - Top 15 Integrations', style_h1))
story.append(HRFlowable(width='100%', thickness=1.0,
                         color=COLOR_DARK_BLUE, spaceAfter=10))

story.append(Paragraph(
    'The table below ranks the fifteen highest-value integrations by '
    'priority tier (P1 must-have easy, P2 should-have medium, P3 '
    'nice-to-have hard). For each synergy we record the source repo, '
    'the feature name, a substantive description, the integration '
    'difficulty (EASY/MEDIUM/HARD), the impact rating (HIGH/MED/LOW), '
    'and a derived priority. Difficulty is an engineering-effort '
    'estimate; impact is the severity of the failure mode that the '
    'synergy closes. The combination of the two yields the priority '
    'ranking. Each synergy is cross-referenced to its donor repo in the '
    'Repository Inventory above.',
    style_body))

# ── Priority 1 ──
story.append(Paragraph('Priority 1 - Must-have, Easy', style_h2))
story.append(Paragraph(
    'These five synergies are the quickest wins. Each can be implemented '
    'in well under a day, each closes a documented production failure '
    'mode, and none carries architectural risk. They form the entirety '
    'of Phase 1 in the implementation roadmap.',
    style_body))

p1_header = [
    p('#', style_table_header_center),
    p('Source Repo', style_table_header),
    p('Feature', style_table_header),
    p('Description', style_table_header),
    p('Difficulty', style_table_header_center),
    p('Impact', style_table_header_center),
    p('Priority', style_table_header_center),
]
p1_rows = [
    ['1', 'eequaled/GLM_proxy', 'Output-Cap Clamping',
     'Probe-verified: requesting >131072 output tokens makes the cloud '
     'silently substitute DeepSeek and bill DeepSeek credits. Add an '
     'OUTPUT_CAPS table and a clampMaxOutput() guard that caps the '
     'requested max_tokens to the documented per-model ceiling before '
     'forwarding upstream.',
     'EASY', 'HIGH', 'P1'],
    ['2', 'eequaled/GLM_proxy', 'System-Banner Injection',
     'Required gate; without it the upstream returns HTTP 400. Introduce '
     'an AUTOCLAW_SYSTEM_BANNER environment variable whose value is '
     'prepended to every system prompt on the way upstream. Defaults to '
     'a minimal compliant banner so the proxy boots out-of-the-box.',
     'EASY', 'HIGH', 'P1'],
    ['3', 'eequaled/GLM_proxy', 'Permanent-Failure Negative Cache',
     'A sixty-second TTL cache of quota-exhausted and unknown-model '
     'failure responses. Prevents re-issuing the same failing request '
     'rapidly when an account is throttled or a model is misnamed, '
     'which would otherwise burn rate-limit budget and trip circuit '
     'breakers downstream.',
     'EASY', 'HIGH', 'P1'],
    ['4', 'eequaled/GLM_proxy', 'Chinese-to-English Error Translation',
     'A ZH_ERROR_MAP table that converts upstream Chinese-language '
     'error strings into stable, English-language equivalents. '
     'Critical for client libraries (notably the OpenAI Python SDK) '
     'that pattern-match on error substrings and would otherwise fail '
     'to classify Chinese-language failures.',
     'EASY', 'MED', 'P1'],
    ['5', 'eroslifestyle/ai-router-switch', 'In-chat !router Command',
     'Allows the operator to switch backends from inside an ongoing '
     'conversation via a synthetic SSE event injected into the stream. '
     'Removes the need to restart the conversation when a backend '
     'fails or when a cheaper model becomes appropriate mid-chat.',
     'EASY', 'MED', 'P1'],
]
p1_data = [p1_header]
for r in p1_rows:
    p1_data.append([
        p(r[0], style_table_cell_center),
        p(r[1], style_table_cell_bold),
        p(r[2], style_table_cell_bold),
        p(r[3], style_table_cell),
        impact_cell(r[4], COLOR_LOW),
        impact_cell(r[5], COLOR_HIGH if r[5] == 'HIGH' else COLOR_MED),
        impact_cell(r[6], COLOR_DARK_BLUE),
    ])
p1_tbl = styled_table(p1_data,
    col_widths=[8*mm, 32*mm, 28*mm, 56*mm, 16*mm, 14*mm, 14*mm],
    font_size=8)
story.append(p1_tbl)
story.append(Spacer(1, 5 * mm))

# ── Priority 2 ──
story.append(Paragraph('Priority 2 - Should-have, Medium', style_h2))
story.append(Paragraph(
    'These seven synergies form the bulk of Phase 2. They take between '
    'a few hours and one engineering day each, and they significantly '
    'expand the API surface and the resilience of the proxy. The '
    'Anthropic Messages endpoint is the highest-value item in this tier '
    'because it unlocks native Claude Code support without any '
    'workarounds.',
    style_body))

p2_rows = [
    ['6', 'guell11/OmniClaw-GLM-Proxy', 'Anthropic Messages Endpoint',
     'Add /v1/messages to expose the Anthropic Messages API natively. '
     'Unlocks native Claude Code support without a translation shim. '
     'Implementation reuses the existing SSE passthrough path and '
     'adds an Anthropic-format request/response envelope around it.',
     'MEDIUM', 'HIGH', 'P2'],
    ['7', 'eequaled/GLM_proxy', 'Claude Credit-Tier Routing',
     'Route opus requests to the High credit tier, sonnet to Medium, '
     'haiku to Low, sourced from a remote model-config endpoint. Lets '
     'operators exploit the cheaper haiku tier automatically for '
     'low-latency classification workloads while reserving expensive '
     'opus capacity for tasks that genuinely need it.',
     'MEDIUM', 'MED', 'P2'],
    ['8', 'eroslifestyle/ai-router-switch', 'Per-Chat Fingerprint Isolation',
     'Compute SHA-256 of the first user message, pin-on-first-use to '
     'a single upstream chat_id. Defeats conversation-merge attacks '
     'where two unrelated client sessions are concatenated server-side '
     'and leak context across users. The fingerprint is the unit of '
     'isolation, not the bearer token.',
     'MEDIUM', 'HIGH', 'P2'],
    ['9', 'eroslifestyle/ai-router-switch', 'loop_breaker',
     'Detect stuck conversations defined as four or more re-emits at '
     'eighty percent or more of context window. Returns HTTP 400 to '
     'force the client to start a fresh conversation rather than '
     'spinning on a context-rotted one. Prevents runaway token spend.',
     'MEDIUM', 'MED', 'P2'],
    ['10', 'tt-52101/chat-z-ai-proxy-web2api-free', 'DSML Tool-Calling Shim',
     'Synthesises OpenAI function-calling responses for upstream '
     'models that lack a native tool API. Wraps the model\'s natural-'
     'language tool-use intent into a structured tool_calls field that '
     'the OpenAI Python SDK can dispatch on. Adds tool-using capability '
     'to models that would otherwise be excluded.',
     'MEDIUM', 'MED', 'P2'],
    ['11', 'tt-52101/chat-z-ai-proxy-web2api-free',
     'reasoning_content Phase Separation',
     'Parse the upstream SSE "phase" field to separate thinking '
     'content from answering content. Emits OpenAI-style '
     'reasoning_content for o1-style transparency. Lets clients '
     'display reasoning steps separately from the final answer.',
     'MEDIUM', 'MED', 'P2'],
    ['12', 'sabyaghosh/glm-free-api-admin-panel', 'Throwaway Chat Sessions',
     'Create a fresh upstream chat_id per request and delete it after '
     'the response completes. Closes a context-rot vulnerability where '
     'long-lived chat_ids accumulate noise that eventually confuses '
     'the upstream model into emitting stale responses.',
     'MEDIUM', 'HIGH', 'P2'],
]
p2_data = [p1_header]
for r in p2_rows:
    p2_data.append([
        p(r[0], style_table_cell_center),
        p(r[1], style_table_cell_bold),
        p(r[2], style_table_cell_bold),
        p(r[3], style_table_cell),
        impact_cell(r[4], COLOR_MED),
        impact_cell(r[5], COLOR_HIGH if r[5] == 'HIGH' else COLOR_MED),
        impact_cell(r[6], COLOR_DARK_BLUE),
    ])
p2_tbl = styled_table(p2_data,
    col_widths=[8*mm, 32*mm, 28*mm, 56*mm, 16*mm, 14*mm, 14*mm],
    font_size=8)
story.append(p2_tbl)
story.append(PageBreak())

# ── Priority 3 ──
story.append(Paragraph('Priority 3 - Nice-to-have, Hard', style_h2))
story.append(Paragraph(
    'These three synergies form Phase 3 and are the most technically '
    'demanding items in the matrix. Each requires either a non-Python '
    'dependency, a substantial UI build-out, or both. They are '
    'discretionary: the proxy remains fully functional without them, '
    'and we recommend triggering them only when a specific operational '
    'need is demonstrated.',
    style_body))

p3_rows = [
    ['13', 'eequaled/GLM_proxy', 'Cloud-to-Local WebSocket Fallback',
     'When the upstream cloud API is unreachable, transparently route '
     'the request through a local AutoClaw desktop agent over '
     'WebSocket. Provides best-in-class resilience for operators who '
     'run a desktop agent alongside the proxy. HARD because it '
     'requires a new transport layer and a local-agent discovery '
     'mechanism.',
     'HARD', 'HIGH', 'P3'],
    ['14', 'sabyaghosh/glm-free-api-admin-panel',
     'uTLS Chrome 120 ClientHello',
     'Forge a Chrome 120 ClientHello via the uTLS library, with '
     'HTTP/1.1-only NextProtos to avoid HTTP/2 fingerprinting. Defeats '
     'JA3 fingerprinting without a real browser. HARD because Python\'s '
     'ssl module cannot forge ClientHellos - requires a Go or Rust TLS '
     'bridge (we recommend the Rust tls-client crate).',
     'HARD', 'HIGH', 'P3'],
    ['15', 'guell11/OmniClaw-GLM-Proxy', 'Local React Dashboard',
     'Live metrics, request log, masked-IP client list, rate-limit '
     'block counters, and a backend-switch control surface. Replaces '
     'the current HTML dashboard with a reactive UI. HARD because it '
     'introduces a JavaScript build pipeline and a long-running '
     'WebSocket metrics endpoint.',
     'HARD', 'MED', 'P3'],
]
p3_data = [p1_header]
for r in p3_rows:
    p3_data.append([
        p(r[0], style_table_cell_center),
        p(r[1], style_table_cell_bold),
        p(r[2], style_table_cell_bold),
        p(r[3], style_table_cell),
        impact_cell(r[4], COLOR_HIGH),
        impact_cell(r[5], COLOR_HIGH if r[5] == 'HIGH' else COLOR_MED),
        impact_cell(r[6], COLOR_DARK_BLUE),
    ])
p3_tbl = styled_table(p3_data,
    col_widths=[8*mm, 32*mm, 28*mm, 56*mm, 16*mm, 14*mm, 14*mm],
    font_size=8)
story.append(p3_tbl)

story.append(Spacer(1, 5 * mm))
story.append(Paragraph(
    'The total integration burden across all three priorities is '
    'approximately one week of focused engineering effort. Phase 1 '
    'alone (one day) closes three HIGH-impact defensive failure modes '
    'and is the recommended starting point. Phase 2 (two-to-three '
    'days) is where the API surface expansion happens. Phase 3 (one '
    'week) is reserved for adversarial-environment hardening and may '
    'be deferred indefinitely if the operational pressure that '
    'motivates it never materialises.',
    style_body))

story.append(PageBreak())

# ═══ 7. IMPLEMENTATION ROADMAP ═════════════════════════════════════════
story.append(Paragraph('5. Implementation Roadmap', style_h1))
story.append(HRFlowable(width='100%', thickness=1.0,
                         color=COLOR_DARK_BLUE, spaceAfter=10))

story.append(Paragraph(
    'The roadmap below sequences the fifteen synergies into three '
    'phases. The phases are ordered by descending ease and ascending '
    'risk: Phase 1 delivers immediate defensive value with no '
    'architectural change; Phase 2 expands the API surface and '
    'introduces the Anthropic endpoint; Phase 3 introduces new '
    'transports and UI surfaces that demand additional dependencies. '
    'Each phase lists its component synergies, an estimated effort, '
    'and the dependencies that must be satisfied before the phase '
    'begins.',
    style_body))

# Phase 1
story.append(Paragraph('Phase 1 - Quick Wins (estimated: 1 day)', style_h2))
story.append(Paragraph(
    'All five Priority-1 items ship in Phase 1. None requires a new '
    'dependency and none requires a public API change - they are all '
    'internal guards and translations on the existing request path. '
    'The cumulative effect is to close the three most-seen production '
    'failure modes in our logs (silent DeepSeek substitution, missing '
    'system banner, quota-burn cascades) plus two quality-of-life '
    'improvements (stable English error messages, mid-chat backend '
    'switching). No prerequisite work is needed before Phase 1 begins.',
    style_body))

phase1_header = [
    p('Item', style_table_header_center),
    p('Synergy', style_table_header),
    p('Source', style_table_header),
    p('Effort', style_table_header_center),
    p('Dependencies', style_table_header),
]
phase1_rows = [
    ['1.1', 'Output-cap clamping', 'eequaled/GLM_proxy',
     '~2h', 'OUTPUT_CAPS table per model'],
    ['1.2', 'System-banner injection', 'eequaled/GLM_proxy',
     '~1h', 'AUTOCLAW_SYSTEM_BANNER env var'],
    ['1.3', 'Permanent-failure negative cache', 'eequaled/GLM_proxy',
     '~3h', 'In-process TTL cache (no external dep)'],
    ['1.4', 'Chinese-to-English error translation', 'eequaled/GLM_proxy',
     '~1h', 'ZH_ERROR_MAP table'],
    ['1.5', 'In-chat !router command', 'ai-router-switch',
     '~3h', 'Synthetic SSE emitter'],
]
phase1_data = [phase1_header]
for r in phase1_rows:
    phase1_data.append([
        p(r[0], style_table_cell_center),
        p(r[1], style_table_cell_bold),
        p(r[2], style_table_cell),
        p(r[3], style_table_cell_center),
        p(r[4], style_table_cell),
    ])
story.append(styled_table(phase1_data,
    col_widths=[12*mm, 50*mm, 38*mm, 18*mm, 52*mm], font_size=8.5))

# Phase 2
story.append(Paragraph('Phase 2 - API Surface Expansion (estimated: 2-3 days)',
                       style_h2))
story.append(Paragraph(
    'Phase 2 expands the API surface to include the Anthropic Messages '
    'endpoint, adds the credit-tier and fingerprint guards that make '
    'multi-backend operation safe, and lifts two upstream innovations '
    '(DSML tool-calling shim and reasoning_content phase separation) '
    'from chat-z-ai-proxy. The throwaway-chat-sessions guard closes the '
    'last open context-rot vulnerability. Prerequisite: Phase 1 must be '
    'complete because Phase 2 reuses the negative cache for the new '
    'Anthropic endpoint, and the system-banner injection for the new '
    'Anthropic envelope.',
    style_body))

phase2_rows = [
    ['2.1', 'Anthropic /v1/messages endpoint', 'OmniClaw',
     '~6h', 'Phase 1.2 system banner'],
    ['2.2', 'Claude credit-tier routing', 'eequaled/GLM_proxy',
     '~3h', 'Phase 2.1 Anthropic endpoint'],
    ['2.3', 'Per-chat fingerprint isolation', 'ai-router-switch',
     '~4h', 'None (orthogonal)'],
    ['2.4', 'loop_breaker', 'ai-router-switch',
     '~3h', 'Phase 2.3 fingerprint'],
    ['2.5', 'DSML tool-calling shim', 'chat-z-ai-proxy',
     '~6h', 'Function-calling spec'],
    ['2.6', 'reasoning_content phase separation', 'chat-z-ai-proxy',
     '~4h', 'SSE phase-field parser'],
    ['2.7', 'Throwaway chat sessions', 'glm-free-api-admin-panel',
     '~3h', 'Per-request chat_id lifecycle'],
]
phase2_data = [phase1_header]
for r in phase2_rows:
    phase2_data.append([
        p(r[0], style_table_cell_center),
        p(r[1], style_table_cell_bold),
        p(r[2], style_table_cell),
        p(r[3], style_table_cell_center),
        p(r[4], style_table_cell),
    ])
story.append(styled_table(phase2_data,
    col_widths=[12*mm, 50*mm, 38*mm, 18*mm, 52*mm], font_size=8.5))

story.append(PageBreak())

# Phase 3
story.append(Paragraph('Phase 3 - Advanced Hardening (estimated: 1 week)',
                       style_h2))
story.append(Paragraph(
    'Phase 3 introduces new transports (the cloud-to-local WebSocket '
    'fallback), new language ecosystems (the Rust tls-client crate for '
    'the uTLS ClientHello), and a new UI surface (the React dashboard). '
    'Each item is independently shippable; we recommend tackling them '
    'in the order shown. Prerequisite: Phase 2.7 (throwaway chat '
    'sessions) must be complete before Phase 3.1 (cloud-to-local '
    'fallback), because the fallback path inherits the per-request '
    'chat_id lifecycle from the throwaway-session guard.',
    style_body))

phase3_rows = [
    ['3.1', 'Cloud-to-local WebSocket fallback', 'eequaled/GLM_proxy',
     '~2d', 'Phase 2.7 throwaway sessions; local agent discovery'],
    ['3.2', 'uTLS Chrome 120 ClientHello', 'glm-free-api-admin-panel',
     '~3d', 'Rust tls-client crate (or Go uTLS bridge)'],
    ['3.3', 'Local React dashboard', 'OmniClaw',
     '~2d', 'JavaScript build pipeline; metrics WS endpoint'],
]
phase3_data = [phase1_header]
for r in phase3_rows:
    phase3_data.append([
        p(r[0], style_table_cell_center),
        p(r[1], style_table_cell_bold),
        p(r[2], style_table_cell),
        p(r[3], style_table_cell_center),
        p(r[4], style_table_cell),
    ])
story.append(styled_table(phase3_data,
    col_widths=[12*mm, 50*mm, 38*mm, 18*mm, 52*mm], font_size=8.5))

story.append(Spacer(1, 6 * mm))

# Dependency graph summary
story.append(Paragraph('Dependency Graph Summary', style_h2))
story.append(Paragraph(
    'The dependency graph across the three phases is shallow. Phase 1 '
    'has no internal dependencies and can ship as a single PR. Within '
    'Phase 2, only two ordered pairs exist: 2.1 -> 2.2 (the '
    'credit-tier routing needs the Anthropic endpoint to route into) '
    'and 2.3 -> 2.4 (the loop_breaker needs the fingerprint to track '
    're-emits). Within Phase 3, the prerequisite is 2.7 -> 3.1 as '
    'noted above. All other synergies can ship in any order or in '
    'parallel, which simplifies staffing: a single engineer can drive '
    'the entire roadmap end-to-end in approximately one calendar week.',
    style_body))

story.append(PageBreak())

# ═══ 8. ANTI-BOT & ANTI-FINGERPRINT ANALYSIS ═══════════════════════════
story.append(Paragraph('6. Anti-Bot and Anti-Fingerprint Analysis', style_h1))
story.append(HRFlowable(width='100%', thickness=1.0,
                         color=COLOR_DARK_BLUE, spaceAfter=10))

story.append(Paragraph(
    'The anti-bot dimension is the most heterogeneous column in the '
    'architecture matrix. No two repos use the same strategy, and the '
    'strategies range from "no anti-bot at all" through client-side '
    'header mimicry to full uTLS ClientHello forgery. The deep-dive '
    'below examines the five distinct approaches and rates each for '
    'effectiveness, operational cost, and portability into our '
    'baseline. The approaches are presented in roughly ascending order '
    'of effectiveness against modern fingerprinting.',
    style_body))

# Strategy 1: CloakBrowser
story.append(Paragraph('6.1 CloakBrowser (autoclaw-autologin baseline)', style_h2))
story.append(Paragraph(
    'CloakBrowser is a C++ patched Chromium with fifty-eight patches '
    'targeting Cloudflare, reCAPTCHA, FingerprintJS, and BrowserScan '
    'detection vectors. It is the heaviest anti-bot measure in the '
    'surveyed set: a 535MB stealth Chromium that must be bundled or '
    'downloaded at deploy time. The advantage is that it defeats the '
    'broadest range of detection vectors because it modifies the '
    'browser itself rather than its network profile. The disadvantage '
    'is that the bundling cost makes server-only deployments impractical '
    '(which is precisely what motivated sitimas9/autoclaw2api to drop '
    'CloakBrowser entirely). CloakBrowser remains our baseline approach '
    'for OAuth token harvesting because no other surveyed strategy '
    'solves the Google OAuth login flow end-to-end.',
    style_body))

# Strategy 2: Real browser delegation
story.append(Paragraph('6.2 Real Browser Delegation (chat-z-ai-proxy)', style_h2))
story.append(Paragraph(
    'chat-z-ai-proxy delegates all browser-flavoured work to a real '
    'system Chrome instance via channel="chrome". It uses init-script '
    'overrides to inject custom behaviour into the real page and lets '
    'the real page solve the Aliyun TRACELESS captcha in-band. The '
    'advantage is that there is no bundled stealth browser to maintain '
    '- the operator installs Chrome once and the proxy reuses it. The '
    'disadvantage is that a real Chrome instance is harder to sandbox '
    'and harder to run in a headless server environment, and the '
    'captured HAR must be re-analysed whenever the upstream page '
    'changes. This approach is attractive for operator workstations '
    'but is a poor fit for the server-first deployment mode that '
    'autoclaw2api targets.',
    style_body))

# Strategy 3: uTLS Chrome 120
story.append(Paragraph('6.3 uTLS Chrome 120 ClientHello (glm-free-api-admin-panel)',
                       style_h2))
story.append(Paragraph(
    'glm-free-api-admin-panel uses the Go uTLS library to forge a '
    'Chrome 120 ClientHello (HelloChrome_120) with HTTP/1.1-only '
    'NextProtos to avoid HTTP/2 fingerprinting. This is the most '
    'technically sophisticated anti-bot measure in the surveyed set '
    'because it defeats JA3 fingerprinting at the TLS layer without '
    'running any browser at all. The Aliyun Captcha v3 defeating '
    'routine uses RC4-like cipher primitives to break the captcha '
    'token exchange, completing a fully browserless anti-bot stack. '
    'The disadvantage is the language gap: Python\'s ssl module '
    'cannot forge ClientHellos, so porting this approach requires '
    'either a Go dependency or a Rust bridge via the tls-client crate. '
    'We recommend the Rust bridge to keep the dependency footprint '
    'manageable.',
    style_body))

# Strategy 4: Client fingerprint mimicry
story.append(Paragraph('6.4 Client Fingerprint Mimicry (GLM_proxy / OmniClaw)',
                       style_h2))
story.append(Paragraph(
    'Both eequaled/GLM_proxy and guell11/OmniClaw reproduce the upstream '
    'client envelope header set (X-Client-Type, X-Tm, X-Version, '
    'X-Product, X-Channel, X-Lang) rather than forging a TLS '
    'fingerprint. This is the lightest anti-bot measure in the surveyed '
    'set and is sufficient for upstreams that gate on application-layer '
    'headers rather than TLS fingerprints. The advantage is that it '
    'requires no special runtime support - it is plain HTTP. The '
    'disadvantage is that it is fully defeated by any upstream that '
    'upgrades to JA3 or JA4 fingerprinting, which several Aliyun-'
    'flavoured upstreams have already done. We recommend adopting the '
    'header envelope (it is cheap and effective against non-TLS '
    'fingerprinting upstreams) but not relying on it as the sole '
    'anti-bot measure.',
    style_body))

# Strategy 5: None
story.append(Paragraph('6.5 None (autoclaw2api)', style_h2))
story.append(Paragraph(
    'sitimas9/autoclaw2api deliberately drops all stealth measures. '
    'The architectural stance is that production deployments should '
    'run on a server without a desktop environment, with token '
    'harvesting performed elsewhere (by a separate CloakBrowser '
    'instance, or by manual desktop extraction). The advantage is the '
    'minimal dependency list (five Python packages) and the clean '
    'server-first deployment story. The disadvantage is that the '
    'deployed proxy depends on an external token harvester and cannot '
    'self-serve when tokens run out. This is a reasonable trade for '
    'operators who already run a CloakBrowser harvester in parallel, '
    'but it is not a viable primary anti-bot strategy.',
    style_body))

# Comparison summary table
story.append(Spacer(1, 4 * mm))
story.append(Paragraph('6.6 Anti-Bot Strategy Comparison', style_h2))

ab_header = [
    p('Strategy', style_table_header),
    p('Repos Using', style_table_header),
    p('Effectiveness', style_table_header_center),
    p('Operational Cost', style_table_header_center),
    p('Portability', style_table_header_center),
]
ab_rows = [
    ['CloakBrowser (C++ patched Chromium)',
     'autoclaw-autologin',
     'Highest (58 patches)',
     'High (535MB bundle)',
     'Already in baseline'],
    ['Real browser delegation (system Chrome)',
     'chat-z-ai-proxy',
     'High (real page)',
     'Medium (needs Chrome)',
     'MEDIUM - workstations only'],
    ['uTLS Chrome 120 ClientHello',
     'glm-free-api-admin-panel',
     'High (defeats JA3)',
     'Low (no browser)',
     'HARD - needs Rust/Go bridge'],
    ['Client fingerprint mimicry (headers)',
     'GLM_proxy, OmniClaw',
     'Medium (no TLS)',
     'Low (plain HTTP)',
     'EASY - pure Python'],
    ['None (drop all stealth)',
     'autoclaw2api',
     'None',
     'None',
     'N/A - orthogonal stance'],
]
ab_data = [ab_header]
for r in ab_rows:
    ab_data.append([
        p(r[0], style_table_cell_bold),
        p(r[1], style_table_cell),
        p(r[2], style_table_cell_center),
        p(r[3], style_table_cell_center),
        p(r[4], style_table_cell_center),
    ])
story.append(styled_table(ab_data,
    col_widths=[45*mm, 32*mm, 30*mm, 30*mm, 33*mm], font_size=8.5))

story.append(PageBreak())

# ═══ 9. RECOMMENDATIONS ═════════════════════════════════════════════════
story.append(Paragraph('7. Recommendations', style_h1))
story.append(HRFlowable(width='100%', thickness=1.0,
                         color=COLOR_DARK_BLUE, spaceAfter=10))

story.append(Paragraph(
    'The recommendations below distil the analysis into actionable '
    'guidance for the engineering team that will integrate the Top-15 '
    'synergies. They are ordered by urgency and grouped by theme. '
    'Each recommendation is concrete enough to translate directly into '
    'a ticket or a pull-request scope; the implementation roadmap in '
    'Section 5 provides the sequencing.',
    style_body))

story.append(Paragraph('7.1 Immediate Actions', style_h2))
story.append(Paragraph(
    'Adopt the five Phase-1 synergies immediately. They are low-risk, '
    'high-value, and each closes a failure mode we have observed in '
    'production. Output-cap clamping alone prevents the silent '
    'DeepSeek substitution that has billed real credits against our '
    'account. The system-banner injection is a hard prerequisite - '
    'without it the upstream returns HTTP 400 and nothing else matters. '
    'The permanent-failure negative cache and the Chinese-to-English '
    'error translation are quality-of-life improvements that pay back '
    'their one-day implementation cost within the first week of '
    'operation. The in-chat !router command is the only Phase-1 item '
    'that touches the public API surface; ship it last in the phase so '
    'we can roll it back independently if operators find it intrusive.',
    style_body))

story.append(Paragraph('7.2 API Surface Expansion', style_h2))
story.append(Paragraph(
    'Phase 2 is where the API surface expands into the Anthropic '
    'ecosystem, which is the single largest remaining functional gap. '
    'Adding /v1/messages unlocks native Claude Code support, which is '
    'the most-requested feature from our downstream integrators. '
    'Claude credit-tier routing is the natural follow-up because it '
    'makes the new endpoint economically viable: routing opus requests '
    'to the High credit tier, sonnet to Medium, and haiku to Low '
    'reduces average cost per request without sacrificing latency for '
    'classification workloads. Per-chat fingerprint isolation and '
    'loop_breaker together close the conversation-merge and '
    'context-rot failure modes that have produced the most confusing '
    'bug reports from operators.',
    style_body))

story.append(Paragraph('7.3 Optional Hardening', style_h2))
story.append(Paragraph(
    'Phase 3 hardening is optional but provides resilience in '
    'adversarial environments. The cloud-to-local WebSocket fallback '
    'is the most-valuable item in this tier because it gives the proxy '
    'a working degraded mode when the upstream cloud is unreachable. '
    'The uTLS Chrome 120 ClientHello is the most technically demanding '
    'item; we recommend implementing it via the Rust tls-client crate '
    'rather than introducing a Go dependency, because Rust integrates '
    'more cleanly with our Python deployment story (PyO3 bindings, '
    'single wheel artifact). The local React dashboard is the lowest-'
    'impact item in Phase 3 and should be deferred until operators '
    'explicitly request richer observability than the existing HTML '
    'dashboard provides.',
    style_body))

story.append(Paragraph('7.4 Process and Documentation', style_h2))
story.append(Paragraph(
    'Document the integration matrix in the repository README so that '
    'downstream integrators can see at a glance which community '
    'innovations we have adopted and from which donor repo. Create one '
    'synergetic integration test per adopted feature - a regression '
    'test that exercises the new feature end-to-end through the proxy. '
    'This grows our suite from its current seventy-eight tests toward '
    'the ninety-three-test target that an adoption of all fifteen '
    'synergies implies. Commit the ZH_ERROR_MAP, OUTPUT_CAPS, and '
    'model-config tables as data files rather than inline constants so '
    'they can be patched without a code change when upstream changes '
    'its caps or adds new error strings.',
    style_body))

story.append(PageBreak())

# ═══ 10. CONCLUSION ════════════════════════════════════════════════════
story.append(Paragraph('8. Conclusion', style_h1))
story.append(HRFlowable(width='100%', thickness=1.0,
                         color=COLOR_DARK_BLUE, spaceAfter=10))

story.append(Paragraph(
    'The AutoClaw ecosystem is rich with complementary innovations. '
    'Across the nine repositories surveyed we catalogued more than '
    'thirty-five unique technical contributions, of which no single '
    'repo provides more than a handful. The seven active repos each '
    'lead on at most two of the eight architectural dimensions '
    'compared in Section 3 - a pattern that confirms the synergy '
    'thesis: there is no "best" repo, only best-of-breed components '
    'that compose well together.',
    style_body))

story.append(Paragraph(
    'Our local autoclaw-autologin baseline has the strongest security '
    'and memory-hardening posture of any repo in the surveyed set. '
    'Forty-one targeted fixes and seventy-eight out of seventy-eight '
    'passing tests give it a regression-safety net that no community '
    'project currently matches. Only ai-router-switch (930 tests, 679 '
    'commits) approaches our coverage, and even it does not focus on '
    'memory safety or token-lifecycle correctness. This means we are '
    'well-positioned to absorb external innovations without '
    'compromising the guarantees that our baseline already enforces.',
    style_body))

story.append(Paragraph(
    'Adopting the Phase-1 and Phase-2 synergies - twelve features in '
    'total - would significantly expand the API surface and resilience '
    'of the proxy without compromising our security posture. Phase 1 '
    'closes three HIGH-impact defensive failure modes in a single day '
    'of engineering effort. Phase 2 adds the Anthropic Messages '
    'endpoint (the most-requested feature from downstream integrators) '
    'and the credit-tier, fingerprint, and throwaway-session guards '
    'that make multi-backend operation safe. The combined '
    'approximately three-to-four-day investment is the single highest '
    'leverage engineering work available to the project right now.',
    style_body))

story.append(Paragraph(
    'Phase 3 provides advanced hardening for adversarial environments '
    'and may be deferred indefinitely if the operational pressure that '
    'motivates it never materialises. The cloud-to-local WebSocket '
    'fallback is the most-valuable item in this tier for general '
    'resilience; the uTLS Chrome 120 ClientHello is the most-valuable '
    'item for environments where JA3 fingerprinting is observed in the '
    'wild; the React dashboard is the most-valuable item for operators '
    'who need richer observability than the current HTML dashboard '
    'provides. Each is independently shippable and each is '
    'discretionary.',
    style_body))

story.append(Paragraph(
    'In summary: the ecosystem survey validates that our local baseline '
    'is the right anchor for integration, that the community has '
    'collectively solved many of the problems we still face, and that '
    'a focused one-week engineering effort will close the highest-'
    'value gaps without compromising our hard-won security posture. '
    'The Top-15 synergy matrix, the architecture comparison matrix, '
    'and the phased roadmap together provide a concrete, sequenced, '
    'and effort-bounded plan for the next phase of project evolution. '
    'Engineering should begin with Phase 1 immediately.',
    style_body))

# Closing rule
story.append(Spacer(1, 8 * mm))
story.append(HRFlowable(width='100%', thickness=1.5, color=COLOR_DARK_BLUE))
story.append(Spacer(1, 4 * mm))
story.append(Paragraph(
    'End of report. Prepared by Super Z AI on 2026-09-19. '
    'This document is classified Research - Confidential.',
    style_callout))

# ─── Build the PDF ───────────────────────────────────────────────────────
def build():
    out_path = '/home/z/my-project/download/AutoClaw-Synergy-Research-Deep-Dive.pdf'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc = SynergyReportDoc(
        out_path,
        pagesize=A4,
        leftMargin=LEFT_MARGIN, rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN, bottomMargin=BOTTOM_MARGIN,
        title='AutoClaw Ecosystem Synergy Research Deep-Dive',
        author='Super Z AI',
        subject='9-Repo Investigation, Integration Matrix & Enhancement Roadmap',
        creator='Super Z AI - generate-synergy-research.py',
    )
    # First page is Cover, subsequent pages are Body
    doc.multiBuild([
        NextPageTemplate('Body'),  # after cover, switch to body
    ] + story[1:])  # skip the NextPageTemplate we added at start (it's already there)
    # Actually we need to keep story[0] which is NextPageTemplate('Body') -
    # so just rebuild with full story
    return out_path

if __name__ == '__main__':
    # Re-do build cleanly - the multiBuild above had a slicing bug; fix inline
    out_path = '/home/z/my-project/download/AutoClaw-Synergy-Research-Deep-Dive.pdf'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # We want page 1 = Cover template, then switch to Body template.
    # The story's first element is NextPageTemplate('Body') which sets the
    # template for the page break that follows. We need the FIRST page to
    # actually use Cover - so we set Cover as the document default and let
    # NextPageTemplate('Body') switch on the page-break.
    doc = SynergyReportDoc(
        out_path,
        pagesize=A4,
        leftMargin=LEFT_MARGIN, rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN, bottomMargin=BOTTOM_MARGIN,
        title='AutoClaw Ecosystem Synergy Research Deep-Dive',
        author='Super Z AI',
        subject='9-Repo Investigation, Integration Matrix & Enhancement Roadmap',
        creator='Super Z AI - generate-synergy-research.py',
    )

    # Story[0] is NextPageTemplate('Body'); we need to ensure page 1 uses
    # Cover. Simplest fix: prepend a NextPageTemplate('Cover') so the
    # document opens on Cover, then NextPageTemplate('Body') takes over.
    full_story = [NextPageTemplate('Cover')] + story

    # The story already starts with NextPageTemplate('Body') as item 0,
    # which means after Cover renders and a page break occurs, Body is used.
    # To make page 1 = Cover we add NextPageTemplate('Cover') at the very
    # start, but reportlab's NextPageTemplate applies to the NEXT page
    # break, not the current page. The BaseDocTemplate.__init__ sets the
    # first PageTemplate in the list as the default - we registered Cover
    # first, so page 1 will be Cover. Good. We can drop the prepend.
    full_story = story

    doc.multiBuild(full_story, maxPasses=20)
    size = os.path.getsize(out_path)
    print(f'OK: PDF generated at {out_path}')
    print(f'    Size: {size:,} bytes ({size/1024:.1f} KB)')
