#!/usr/bin/env python3
"""
OWL-DNS Synergy Report — Comprehensive A/B Comparison Matrix, 
Implementation Plan, Unified Script, and Obsidian Integration
"""

import os, sys, time, json
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus.tableofcontents import TableOfContents

# ─── Font Registration ──────────────────────────────────────────
FONT_DIR = '/usr/share/fonts'

pdfmetrics.registerFont(TTFont('NotoSerifSC', f'{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Regular.ttf'))
pdfmetrics.registerFont(TTFont('NotoSerifSC-Bold', f'{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Bold.ttf'))
registerFontFamily('NotoSerifSC', normal='NotoSerifSC', bold='NotoSerifSC-Bold')

pdfmetrics.registerFont(TTFont('DejaVuSans', f'{FONT_DIR}/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', f'{FONT_DIR}/truetype/dejavu/DejaVuSans-Bold.ttf'))
registerFontFamily('DejaVuSans', normal='DejaVuSans', bold='DejaVuSans-Bold')

pdfmetrics.registerFont(TTFont('Carlito', f'{FONT_DIR}/truetype/english/Carlito-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Carlito-Bold', f'{FONT_DIR}/truetype/english/Carlito-Bold.ttf'))
pdfmetrics.registerFont(TTFont('Carlito-Italic', f'{FONT_DIR}/truetype/english/Carlito-Italic.ttf'))
registerFontFamily('Carlito', normal='Carlito', bold='Carlito-Bold', italic='Carlito-Italic')

# ─── Palette ────────────────────────────────────────────────────
PAGE_BG       = colors.HexColor('#f7f7f6')
SECTION_BG    = colors.HexColor('#f2f2f1')
CARD_BG       = colors.HexColor('#e8e7e4')
TABLE_STRIPE  = colors.HexColor('#eeedeb')
HEADER_FILL   = colors.HexColor('#5b5133')
COVER_BLOCK   = colors.HexColor('#6c6552')
BORDER        = colors.HexColor('#d5d1c4')
ICON          = colors.HexColor('#75673d')
ACCENT        = colors.HexColor('#8f7422')
ACCENT_2      = colors.HexColor('#6541cf')
TEXT_PRIMARY   = colors.HexColor('#1e1e1b')
TEXT_MUTED     = colors.HexColor('#79766f')
SEM_SUCCESS   = colors.HexColor('#457a56')
SEM_WARNING   = colors.HexColor('#9e834e')
SEM_ERROR     = colors.HexColor('#a54f47')
SEM_INFO      = colors.HexColor('#476a8d')

# ─── Page Setup ─────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
LEFT_MARGIN = 20*mm
RIGHT_MARGIN = 20*mm
TOP_MARGIN = 20*mm
BOTTOM_MARGIN = 20*mm
CONTENT_W = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN

OUTPUT_PATH = '/home/z/my-project/download/OWL-DNS-Synergy-Report.pdf'

# ─── Styles ─────────────────────────────────────────────────────
styles = getSampleStyleSheet()

style_title = ParagraphStyle(
    'DocTitle', parent=styles['Title'],
    fontName='DejaVuSans-Bold', fontSize=28, leading=34,
    textColor=TEXT_PRIMARY, alignment=TA_CENTER,
    spaceAfter=12
)

style_h1 = ParagraphStyle(
    'H1', parent=styles['Heading1'],
    fontName='DejaVuSans-Bold', fontSize=22, leading=26,
    textColor=HEADER_FILL, alignment=TA_LEFT,
    spaceBefore=18, spaceAfter=8,
    borderWidth=0, borderPadding=0
)

style_h2 = ParagraphStyle(
    'H2', parent=styles['Heading2'],
    fontName='DejaVuSans-Bold', fontSize=16, leading=20,
    textColor=COVER_BLOCK, alignment=TA_LEFT,
    spaceBefore=14, spaceAfter=6
)

style_h3 = ParagraphStyle(
    'H3', parent=styles['Heading3'],
    fontName='Carlito-Bold', fontSize=13, leading=17,
    textColor=ACCENT, alignment=TA_LEFT,
    spaceBefore=10, spaceAfter=4
)

style_body = ParagraphStyle(
    'Body', parent=styles['Normal'],
    fontName='Carlito', fontSize=10, leading=14,
    textColor=TEXT_PRIMARY, alignment=TA_JUSTIFY,
    spaceBefore=2, spaceAfter=4
)

style_body_bold = ParagraphStyle(
    'BodyBold', parent=style_body,
    fontName='Carlito-Bold', fontSize=10
)

style_bullet = ParagraphStyle(
    'Bullet', parent=style_body,
    fontName='Carlito', fontSize=10, leading=14,
    leftIndent=20, bulletIndent=10,
    spaceBefore=1, spaceAfter=2
)

style_caption = ParagraphStyle(
    'Caption', parent=style_body,
    fontName='Carlito-Italic', fontSize=9, leading=12,
    textColor=TEXT_MUTED, alignment=TA_CENTER,
    spaceBefore=4, spaceAfter=6
)

style_code = ParagraphStyle(
    'Code', parent=style_body,
    fontName='Carlito', fontSize=8, leading=11,
    textColor=TEXT_PRIMARY, alignment=TA_LEFT,
    leftIndent=10,
    backColor=CARD_BG,
    spaceBefore=4, spaceAfter=4
)

style_star = ParagraphStyle(
    'Star', parent=style_body,
    fontName='Carlito-Bold', fontSize=10, leading=14,
    textColor=ACCENT, alignment=TA_CENTER
)

# ─── Helper Functions ────────────────────────────────────────────
def heading1(text):
    return Paragraph(text, style_h1)

def heading2(text):
    return Paragraph(text, style_h2)

def heading3(text):
    return Paragraph(text, style_h3)

def body(text):
    return Paragraph(text, style_body)

def body_bold(text):
    return Paragraph(text, style_body_bold)

def bullet_item(text):
    return Paragraph(text, style_bullet, bulletText='\u2022')

def caption(text):
    return Paragraph(text, style_caption)

def code_block(text):
    return Paragraph(text, style_code)

def spacer(h=6):
    return Spacer(1, h)

def hr():
    return HRFlowable(width="100%", thickness=1, color=BORDER, spaceBefore=6, spaceAfter=6)

def star_rating(n, max_n=5):
    """Generate star rating display."""
    filled = '\u2605' * n
    empty = '\u2606' * (max_n - n)
    return Paragraph(f'{filled}{empty}', style_star)

def make_table(data, col_widths=None, header_rows=1):
    """Create a styled table with palette colors."""
    if col_widths is None:
        col_widths = [CONTENT_W / len(data[0])] * len(data[0])
    
    t = Table(data, colWidths=col_widths, repeatRows=header_rows)
    
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, header_rows-1), HEADER_FILL),
        ('TEXTCOLOR', (0, 0), (-1, header_rows-1), colors.white),
        ('FONTNAME', (0, 0), (-1, header_rows-1), 'Carlito-Bold'),
        ('FONTSIZE', (0, 0), (-1, header_rows-1), 9),
        ('FONTNAME', (0, header_rows), (-1, -1), 'Carlito'),
        ('FONTSIZE', (0, header_rows), (-1, -1), 9),
        ('LEADING', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]
    
    # Alternating row colors
    for i in range(header_rows, len(data)):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), TABLE_STRIPE))
        else:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), PAGE_BG))
    
    t.setStyle(TableStyle(style_cmds))
    return t

# ─── Document Builder ────────────────────────────────────────────
story = []

# ============================================================
# COVER PAGE
# ============================================================
story.append(Spacer(1, 80))
story.append(Paragraph('OWL-AGENT v4.2 + LLM-DNS-Proxy', style_title))
story.append(Spacer(1, 12))
story.append(Paragraph('Synergy Merger Analysis & Implementation Blueprint', ParagraphStyle(
    'Subtitle', parent=style_title, fontSize=16, leading=20,
    textColor=COVER_BLOCK, fontName='DejaVuSans-Bold'
)))
story.append(Spacer(1, 20))
story.append(hr())
story.append(Spacer(1, 8))
story.append(Paragraph('A/B Comparison Matrix | Unified Architecture | Obsidian Integration', ParagraphStyle(
    'CoverMeta', parent=style_body, fontSize=11, textColor=TEXT_MUTED, alignment=TA_CENTER
)))
story.append(Spacer(1, 10))
story.append(Paragraph('Operating Protocol: SMP-v5.1 (Silent Methodological Protocol)', ParagraphStyle(
    'CoverProto', parent=style_body, fontSize=10, textColor=ICON, alignment=TA_CENTER, fontName='Carlito-Italic'
)))
story.append(Spacer(1, 8))
story.append(Paragraph('Deep Research & Orchestration | Skills.sh Discovery | End-to-End Simulation', ParagraphStyle(
    'CoverDetail', parent=style_body, fontSize=9, textColor=TEXT_MUTED, alignment=TA_CENTER
)))
story.append(Spacer(1, 60))
story.append(Paragraph('Generated: 2026-07-28 | Z.ai Research Division', ParagraphStyle(
    'CoverFooter', parent=style_body, fontSize=8, textColor=TEXT_MUTED, alignment=TA_CENTER
)))
story.append(PageBreak())

# ============================================================
# TABLE OF CONTENTS
# ============================================================
story.append(heading1('Table of Contents'))
story.append(spacer(8))

toc_items = [
    ('1', 'Executive Summary & SMP-v5.1 Adoption'),
    ('2', 'Skills Discovery & Capability Composition'),
    ('3', 'Project A: OWL-AGENT v4.2 Architecture Deep Dive'),
    ('4', 'Project B: LLM-DNS-Proxy Architecture Deep Dive'),
    ('5', 'A/B Comparison Matrix (Pros, Cons, Layers, Tools, Components, Star Ratings)'),
    ('6', 'Unified Architecture & Synergy Analysis'),
    ('7', 'Implementation Plan (Phased Roadmap)'),
    ('8', 'Unified Synergies Script'),
    ('9', 'Obsidian Integration via kepano/obsidian-skills'),
    ('10', 'Appendix: Skills.sh Trending & Scraper Ecosystem'),
]

for num, title in toc_items:
    story.append(Paragraph(f'<b>{num}.</b>  {title}', ParagraphStyle(
        f'TOC_{num}', parent=style_body, fontSize=10, leading=14,
        textColor=TEXT_PRIMARY, fontName='Carlito'
    )))
story.append(PageBreak())

# ============================================================
# CHAPTER 1: EXECUTIVE SUMMARY & SMP-v5.1 ADOPTION
# ============================================================
story.append(heading1('1. Executive Summary & SMP-v5.1 Adoption'))

story.append(body(
    'This document presents a comprehensive merger analysis of two powerful network-utility projects: '
    '<b>OWL-AGENT v4.2</b> (a self-optimizing scraping engine with 50+ proxy sources, quality scoring, '
    'adaptive rate limiting, and Chrome fingerprinting) and <b>LLM-DNS-Proxy</b> (a DNS tunneling system '
    'that enables encrypted LLM conversations through captive portals and restricted networks). The analysis '
    'follows the <b>SMP-v5.1 Silent Methodological Protocol</b> as the governing operating instructions, '
    'which mandates zero-fluff execution, alignment over speed, quality-gated reasoning, and depth before velocity.'
))
story.append(spacer(6))

story.append(body(
    'The SMP-v5.1 protocol establishes a state-machine workflow with hard gates at every stage: Discovery, '
    'Brainstorming, Research, Planning, Execution, Validation, Review, and Completion. Each stage must be '
    'satisfied before proceeding. The protocol also routes cognitive effort through seven distinct modes: '
    'Rabbit (speed), Ant (systematic), Beaver (builder), Owl (depth), Eagle (strategy), Dolphin (creative), '
    'and Elephant (memory). For this merger analysis, we primarily employ Owl (depth analysis of hidden factors) '
    'and Beaver (practical system design), with Ant for incremental task decomposition and Eagle for strategic '
    'pattern recognition across both projects.'
))
story.append(spacer(6))

story.append(body(
    'The core insight driving this merger is that OWL-AGENT and LLM-DNS-Proxy occupy complementary positions '
    'in the network-access stack. OWL-AGENT excels at <b>getting through</b> (bypassing anti-bot systems, '
    'rotating proxies, fingerprinting browsers) while LLM-DNS-Proxy excels at <b>getting under</b> (tunneling '
    'through DNS when HTTP is blocked entirely). Combined, they create a dual-channel resilient system: when '
    'HTTP proxies fail, DNS tunneling activates; when DNS is monitored, HTTP proxy rotation takes over. This '
    'creates a self-healing, multi-protocol access layer that no single project can achieve alone.'
))
story.append(spacer(6))

story.append(heading2('1.1 Key Findings'))
story.append(bullet_item('<b>Complementary Access Channels:</b> OWL-AGENT provides HTTP/HTTPS proxy evasion; LLM-DNS-Proxy provides DNS tunnel evasion. Together they cover the two primary network bypass vectors.'))
story.append(bullet_item('<b>Shared Intelligence Layer:</b> Both projects implement quality scoring, adaptive rate limiting, and retry logic. A unified scorer can combine DNS-latency metrics with HTTP-success-rate metrics.'))
story.append(bullet_item('<b>Session Persistence:</b> OWL-AGENT uses Redis for state sharing; LLM-DNS-Proxy uses session persistence for conversation context. A merged RedisStore can serve both purposes.'))
story.append(bullet_item('<b>Obsidian Integration:</b> Both projects can output scraped/tunneled data as Markdown, making them natural fits for Obsidian vaults via kepano/obsidian-skills.'))
story.append(bullet_item('<b>Star Rating Preview:</b> OWL-AGENT scores 4.5/5 on proxy management but 2/5 on restricted-network bypass; LLM-DNS-Proxy scores 5/5 on DNS evasion but 2/5 on HTTP resilience. Merged system targets 4.5/5 across all dimensions.'))

story.append(PageBreak())

# ============================================================
# CHAPTER 2: SKILLS DISCOVERY & CAPABILITY COMPOSITION
# ============================================================
story.append(heading1('2. Skills Discovery & Capability Composition'))

story.append(body(
    'Following SMP-v5.1 Stage 1 (Discovery & Capability Composition), we browsed skills.sh/trending to '
    'identify available agent skills, then composed the bespoke toolset needed for this specific task. The '
    'skills.sh marketplace hosts skills for Claude Code, Cursor, Windsurf, OpenCode, and other AI agents, '
    'with trending categories including browser automation, web scraping, data processing, and Obsidian integration. '
    'The find-skills command on skills.sh enables version-locked discovery and installation of relevant capabilities.'
))
story.append(spacer(6))

story.append(heading2('2.1 Skills.sh Trending Landscape'))
story.append(body(
    'The skills.sh trending page reveals the fastest-growing AI agent skills each week, categorized by agent '
    'compatibility. The marketplace includes skills for browser automation (agent-browser by vercel-labs), '
    'Obsidian integration (obsidian-skills by kepano), web research (parallel-deep-research), code generation, '
    'and DevOps automation. For this merger task, we identified the following version-locked toolset:'
))
story.append(spacer(4))

skills_data = [
    ['Skill / Tool', 'Version', 'Role in Merger', 'Source'],
    ['find-skills (skills.sh)', 'latest', 'Discover and install scraper/research skills', 'npx skills find scraper'],
    ['agent-browser (vercel-labs)', 'v2.x', 'Headless browser for OWL-AGENT JS rendering', 'npm / npx skills add'],
    ['obsidian-skills (kepano)', 'v1.x', 'Obsidian CLI + Markdown/Canvas/Bases integration', 'npx skills add kepano/obsidian-skills'],
    ['parallel-deep-research', 'v1.x', 'Multi-source deep research for proxy pool analysis', 'skills.sh/trending'],
    ['web-reader (z-ai)', 'v1.x', 'Content extraction from web pages', 'z-ai-web-dev-sdk'],
    ['page_reader', 'v1.x', 'Raw page content extraction (GitHub READMEs)', 'z-ai function'],
]

story.append(make_table(skills_data, col_widths=[67.2*mm, 19.8*mm, 51.4*mm, 31.6*mm]))
story.append(caption('Table 2.1: Version-locked toolset assembled for this merger task'))

story.append(spacer(8))

story.append(heading2('2.2 Scraper Skills Discovery'))
story.append(body(
    'Running <b>npx skills find scraper</b> on skills.sh yields a catalog of scraping-related skills. The most '
    'relevant ones for this merger include skills for proxy pool management, DNS-based data retrieval, browser '
    'automation with fingerprint evasion, and Markdown conversion for Obsidian ingestion. The scraper ecosystem '
    'on skills.sh spans three categories: (1) HTTP-based scrapers that use proxy rotation and TLS fingerprinting '
    '(where OWL-AGENT belongs), (2) protocol-level scrapers that tunnel through DNS or ICMP (where LLM-DNS-Proxy '
    'belongs), and (3) hybrid scrapers that combine both approaches (the target of our merged system).'
))
story.append(spacer(6))

story.append(body(
    'The key discovery from skills.sh is that no existing skill combines HTTP proxy evasion with DNS tunneling '
    'in a single unified interface. This gap is precisely what the OWL-AGENT + LLM-DNS-Proxy merger fills. '
    'The merged skill would be installable via <b>npx skills add owl-dns-synergy</b> and would expose both '
    'access channels through a single ResilientClient API, automatically selecting the optimal channel based '
    'on network conditions and target accessibility.'
))

story.append(PageBreak())

# ============================================================
# CHAPTER 3: PROJECT A - OWL-AGENT v4.2
# ============================================================
story.append(heading1('3. Project A: OWL-AGENT v4.2 Architecture Deep Dive'))

story.append(body(
    'OWL-AGENT v4.2 is a production-grade, self-healing HTTP client that combines over 50 proxy sources, '
    'quality scoring, adaptive rate limiting, Redis state sharing, curl_cffi Chrome fingerprinting, Retry-After '
    'parsing, circuit breaker protection, and agent-browser automation into a single memory-efficient Python '
    'script. It is designed for high-volume SEO scraping, API integration, and dynamic content retrieval, with '
    'seamless integration into modern AI-coding ecosystems including OpenCode, Cline, Cursor, Warp, Codebuff, '
    'Claude Code, Codex, Antigravity, Kiro-CLI, Hermes-Agent, and Obsidian Skills.'
))
story.append(spacer(6))

story.append(heading2('3.1 Layer Architecture'))

owl_layers = [
    ['Layer', 'Components', 'Function', 'Why It Matters'],
    ['User Layer', 'OpenCode, Cline, Cursor, Warp, Claude Code, Codex, Antigravity, Kiro-CLI, Hermes-Agent', 
     'Natural-language interfaces to invoke OWL-AGENT', 'Developers stay in preferred environment'],
    ['API Interface', 'CLI (run.sh), Python class, OpenCode skill, Cursor command', 
     'Exposes OWL-AGENT as a reusable tool', 'Both human and agentic usage'],
    ['Core Engine', 'ResilientClient orchestrator', 
     'Caching, dedup, rate limiting, scoring, pacing, circuit breaking, proxy selection', 
     'Central nervous system'],
    ['Proxy Management', 'ProxyPoolManager + ProxyBroker2', 
     '50+ proxy sources, country filtering, validation', 'Self-healing proxy supply'],
    ['Intelligence', 'QualityScorer, AdaptiveRateLimiter, CircuitBreaker', 
     'Proxy quality scoring, request pacing, failure threshold', 'Reduces bans, improves success'],
    ['Persistence', 'RedisStore (optional)', 
     'Shares proxy pool, scores, circuit state across restarts', 'Horizontal scaling'],
    ['Fingerprint Evasion', 'curl_cffi (Chrome 110 impersonation)', 
     'Mimics real browser TLS handshake', 'Bypasses anti-bot detection'],
    ['Headless Browser', 'agent-browser', 
     'JavaScript-heavy page rendering', 'Handles SPAs, captchas'],
    ['Obsidian Integration', 'obsidian-skills (kepano)', 
     'Read/write Obsidian notes, bases, markdown', 'Knowledge base as data source'],
]

story.append(make_table(owl_layers, col_widths=[26.2*mm, 47.9*mm, 56.7*mm, 39.2*mm]))
story.append(caption('Table 3.1: OWL-AGENT v4.2 layer architecture'))

story.append(spacer(8))

story.append(heading2('3.2 Core Components Deep Dive'))

story.append(heading3('3.2.1 HTTPCache (LRU + Disk)'))
story.append(body(
    'The HTTPCache implements a two-tier caching system: an in-memory LRU dictionary for fast lookups and a '
    'disk-based JSON store at ~/.owl-agent/cache/http/ for persistence across restarts. Each cached response '
    'includes status code, content bytes, headers, timestamp, TTL, and protocol. A background cleanup loop '
    'runs every 60 seconds, evicting expired entries and trimming oversized caches to the configured maximum '
    '(default 1000 entries). Cache keys are SHA-256 hashes of method + URL + parameters + protocol, ensuring '
    'deterministic deduplication even across different HTTP/2 vs HTTP/1.1 sessions.'
))

story.append(heading3('3.2.2 RequestDeduplicator'))
story.append(body(
    'The RequestDeduplicator prevents redundant concurrent requests by tracking in-flight futures keyed by '
    'the same SHA-256 hash used by the cache. When two requests arrive simultaneously for the same resource, '
    'the second request awaits the first request\'s future rather than issuing a duplicate network call. This '
    'is critical for high-concurrency scraping scenarios where multiple threads or agents may target the same '
    'URL simultaneously. The deduplicator uses asyncio.Lock for thread-safe registration and cleanup of futures, '
    'with proper exception propagation to all waiting consumers.'
))

story.append(heading3('3.2.3 QualityScorer'))
story.append(body(
    'The QualityScorer implements an exponential moving average (EMA) with configurable decay factor (default '
    '0.9) to track proxy quality over time. Each proxy receives a score between 0.0 (completely unreliable) '
    'and 1.0 (perfect reliability), updated on every request outcome. The EMA formula is: new_score = '
    'old_score * decay + (success ? 1.0 : 0.0) * (1 - decay). This ensures recent failures weigh heavily '
    'while historical performance provides stability. The scorer also maintains a latency history (last 100 '
    'measurements per proxy) for latency-aware proxy selection. The get_best_proxy() method selects the proxy '
    'with the highest combined score from a candidate pool.'
))

story.append(heading3('3.2.4 AdaptiveRateLimiter'))
story.append(body(
    'The AdaptiveRateLimiter dynamically adjusts per-domain request rates based on server response codes. On '
    'success (200-299), the rate increases by 10% toward a configurable maximum (default 5.0 req/s). On '
    'rate-limit responses (429, 503), the rate decreases by 50% toward a configurable minimum (default 0.1 '
    'req/s). Other error codes maintain the current rate. This creates a natural throttling behavior that '
    'automatically backs off when servers indicate overload, and gradually ramps up when servers are responsive. '
    'Each domain maintains its own independent rate, preventing a single slow domain from bottlenecking others.'
))

story.append(heading3('3.2.5 CircuitBreaker'))
story.append(body(
    'The CircuitBreaker follows the standard three-state pattern (Closed, Open, Half-Open) with configurable '
    'failure threshold (default 5 consecutive failures) and recovery timeout (default 30 seconds). When a '
    'domain exceeds the failure threshold, the circuit opens and all subsequent requests to that domain are '
    'immediately rejected without network calls, saving resources and preventing cascading failures. After '
    'the recovery timeout, the circuit enters half-open state and allows a single probe request. If the probe '
    'succeeds, the circuit closes and normal traffic resumes. This pattern is essential for scraping scenarios '
    'where target sites may temporarily go down or deploy aggressive anti-bot measures.'
))

story.append(heading3('3.2.6 ProxyPoolManager'))
story.append(body(
    'The ProxyPoolManager continuously discovers proxies from 50+ sources via ProxyBroker2, filters them by '
    'country (default: US, GB, DE, FR, CA), validates connectivity, and maintains a rotating pool. Proxies '
    'are tracked as ProxyEntry objects with health status, failure counts, and ban timers. Failed proxies are '
    'automatically banned for 60 seconds and retried later. The manager supports LitProxy for rotation and '
    'integrates with curl_cffi for Chrome 110 TLS impersonation. When RedisStore is enabled, the proxy pool '
    'state is shared across multiple OWL-AGENT instances, enabling distributed scraping with zero proxy wastage.'
))

story.append(PageBreak())

# ============================================================
# CHAPTER 4: PROJECT B - LLM-DNS-PROXY
# ============================================================
story.append(heading1('4. Project B: LLM-DNS-Proxy Architecture Deep Dive'))

story.append(body(
    'LLM-DNS-Proxy is a DNS tunneling system that enables encrypted LLM (Large Language Model) conversations '
    'through captive portals, corporate firewalls, and network filters. It exploits a fundamental oversight in '
    'network restrictions: while most traffic (HTTP, HTTPS) gets blocked until authentication, DNS queries '
    'almost always work because captive portals themselves need DNS to function. The project masks encrypted '
    'chat messages as mundane DNS lookups (e.g., mDNS device discovery traffic), chunking and encrypting data '
    'across multiple DNS TXT record queries that pass through unrestricted.'
))
story.append(spacer(6))

story.append(heading2('4.1 Protocol Architecture'))

story.append(body(
    'The DNS tunneling protocol operates in seven distinct phases: (1) Message Encryption using Fernet '
    '(AES-128) symmetric encryption with configurable keys; (2) Chunking where encrypted data is base36-encoded '
    'and split into DNS-compatible segments; (3) DNS Encoding where each chunk becomes a subdomain query with '
    'a configurable camouflage suffix (e.g., _sonos._udp.local, _airplay._tcp.local); (4) Server Processing '
    'where the DNS server receives queries, reassembles chunks, decrypts, and sends to the LLM; (5) Response '
    'Encoding where the AI response is encrypted, chunked, and stored as DNS TXT records; (6) Response Retrieval '
    'where the client fetches response chunks via DNS TXT queries; and (7) Decryption where the client reassembles '
    'chunks and decrypts the final response. To external observers, this appears as standard DNS resolution or '
    'mDNS device discovery activity.'
))
story.append(spacer(6))

dns_layers = [
    ['Layer', 'Components', 'Function', 'Why It Matters'],
    ['Client Layer', 'CLI (python -m llm_dns_proxy.cli)', 
     'Interactive chat, single message, connection testing', 'User-facing interface'],
    ['Protocol Layer', 'Fernet encryption, base36 encoding, DNS chunking', 
     'Encrypt, split, and encode messages as DNS queries', 'Core tunneling mechanism'],
    ['DNS Encoding', 'Camouflage suffixes (_sonos._udp.local, _airplay._tcp.local)', 
     'Make queries appear as legitimate mDNS traffic', 'Steganographic evasion'],
    ['Server Layer', 'DNS server (UDP 53/5353), TXT record responses', 
     'Receive queries, reassemble, decrypt, send to LLM, encode response', 'Server-side processing'],
    ['LLM Integration', 'OpenAI, Ollama, vLLM, OpenRouter, LocalAI', 
     'Multiple provider support via OpenAI-compatible API', 'Flexibility in LLM choice'],
    ['Web Search', 'Perplexity AI integration (function calling)', 
     'Real-time information via web_search tool', 'Live data access through DNS'],
    ['Session Persistence', 'Conversation context across requests', 
     'Maintains multi-turn dialogue state', 'Continuous conversations'],
    ['Production Deploy', 'Systemd service, domain delegation, firewall config', 
     'Production-grade DNS infrastructure setup', 'Real-world deployment'],
]

story.append(make_table(dns_layers, col_widths=[26.2*mm, 47.9*mm, 56.7*mm, 39.2*mm]))
story.append(caption('Table 4.1: LLM-DNS-Proxy layer architecture'))

story.append(spacer(8))

story.append(heading2('4.2 Security Model'))

story.append(body(
    'The security model operates on three levels. First, <b>encryption</b>: all messages use Fernet (AES-128 '
    'CBC with HMAC authentication), ensuring both confidentiality and integrity. Keys are either user-provided '
    'or auto-generated using cryptography.fernet.Fernet.generate_key(). Second, <b>steganography</b>: DNS '
    'suffixes are configurable to mimic legitimate network traffic patterns. Default suffix _sonos._udp.local '
    'makes queries appear as Sonos device discovery; alternatives include _airplay._tcp.local (Apple AirPlay), '
    '_spotify._tcp.local (Spotify Connect), _http._tcp.local (generic HTTP), or custom corporate domains. Third, '
    '<b>acknowledged limitations</b>: DNS queries are visible to network infrastructure (though encrypted payload '
    'is unreadable), and sophisticated IDS/IPS systems may flag unusual DNS patterns. The project explicitly '
    'notes this as a proof-of-concept for educational purposes.'
))

story.append(heading2('4.3 Production Deployment'))
story.append(body(
    'For production deployment, the system requires: (1) A domain under user control with NS delegation '
    '(*.llm.yourdomain.com NS llm.yourdomain.com); (2) A DNS server running on port 53 with root/sudo '
    'permissions; (3) Proper firewall configuration (UFW or firewalld allowing 53/UDP and 53/TCP); (4) A '
    'systemd service for automatic startup with environment variables for API keys and encryption keys; '
    '(5) DNS resolution testing via dig commands before running the proxy. The deployment guide includes '
    'complete systemd unit file templates, iptables port forwarding rules, and monitoring commands using '
    'tcpdump and journalctl. This level of deployment documentation is unusual for a proof-of-concept project '
    'and indicates serious production intent.'
))

story.append(PageBreak())

# ============================================================
# CHAPTER 5: A/B COMPARISON MATRIX
# ============================================================
story.append(heading1('5. A/B Comparison Matrix'))

story.append(body(
    'The following comprehensive A/B comparison matrix evaluates OWL-AGENT v4.2 and LLM-DNS-Proxy across '
    'ten critical dimensions: architecture layers, proxy/access management, encryption and evasion, rate '
    'limiting and resilience, session and state management, LLM integration, deployment maturity, Obsidian '
    'compatibility, ecosystem integration, and overall robustness. Each dimension includes pros, cons, and '
    'a star rating (1-5 scale) to enable quick visual comparison.'
))
story.append(spacer(8))

# ─── Dimension 1: Architecture ───────────────────────────────────
story.append(heading2('5.1 Architecture Layers'))

arch_comparison = [
    ['Dimension', 'OWL-AGENT v4.2 (A)', 'LLM-DNS-Proxy (B)'],
    ['Primary Protocol', 'HTTP/HTTPS with proxy rotation', 'DNS tunneling (UDP TXT records)'],
    ['Layer Count', '9 layers (User, API, Core, Proxy, Intelligence, Persistence, Fingerprint, Browser, Obsidian)', 
     '8 layers (Client, Protocol, DNS Encoding, Server, LLM, Web Search, Session, Production)'],
    ['Core Orchestrator', 'ResilientClient class (async Python)', 'CLI + server binary (async Python)'],
    ['Design Philosophy', 'Self-optimizing: learns from failures, adapts rates, rotates proxies', 
     'Steganographic: hides in legitimate traffic patterns'],
    ['Extensibility', 'OpenCode skill, Cursor command, Python class, CLI', 'CLI only; provider-agnostic OpenAI API'],
    ['Language', 'Python 3.8+ (asyncio)', 'Python (uv-managed, asyncio)'],
    ['Star Rating (A)', '\u2605\u2605\u2605\u2605\u2606 (4/5)', '\u2605\u2605\u2605\u2605\u2606 (4/5)'],
]

story.append(make_table(arch_comparison, col_widths=[30.5*mm, 69.7*mm, 69.7*mm]))
story.append(caption('Table 5.1: Architecture layer comparison'))

story.append(spacer(8))

# ─── Dimension 2: Proxy & Access Management ──────────────────────
story.append(heading2('5.2 Proxy & Access Channel Management'))

access_comparison = [
    ['Dimension', 'OWL-AGENT v4.2 (A)', 'LLM-DNS-Proxy (B)'],
    ['Access Channel', 'HTTP/HTTPS proxies (SOCKS5, HTTP, HTTPS)', 'DNS queries (UDP port 53)'],
    ['Source Pool', '50+ proxy sources via ProxyBroker2 + LitProxy', 'Single DNS server (user-deployed)'],
    ['Country Filtering', 'Yes: configurable country list (US, GB, DE, FR, CA)', 'No (DNS is location-independent)'],
    ['Rotation Strategy', 'Quality-score-based selection with EMA decay', 'No rotation (single server endpoint)'],
    ['Fallback Path', 'Direct connection when all proxies fail', 'No fallback (DNS is the only channel)'],
    ['Anti-Bot Evasion', 'curl_cffi Chrome 110 TLS impersonation', 'Steganographic DNS suffix camouflage'],
    ['Pros (A)', 'Massive proxy pool, geographic control, quality learning', 'Works when HTTP is completely blocked'],
    ['Cons (A)', 'Fails when HTTP is blocked at network level', 'Single server, no geographic diversity'],
    ['Star Rating (A)', '\u2605\u2605\u2605\u2605\u2605 (5/5)', '\u2605\u2605\u2606\u2606\u2606 (2/5)'],
    ['Star Rating (B)', '\u2605\u2605\u2606\u2606\u2606 (2/5)', '\u2605\u2605\u2605\u2605\u2605 (5/5)'],
]

story.append(make_table(access_comparison, col_widths=[30.5*mm, 69.7*mm, 69.7*mm]))
story.append(caption('Table 5.2: Proxy & access channel management comparison'))

story.append(spacer(8))

# ─── Dimension 3: Encryption & Evasion ────────────────────────────
story.append(heading2('5.3 Encryption & Evasion Capabilities'))

enc_comparison = [
    ['Dimension', 'OWL-AGENT v4.2 (A)', 'LLM-DNS-Proxy (B)'],
    ['Encryption', 'None (relies on HTTPS/TLS of target)', 'Fernet AES-128 CBC + HMAC (end-to-end)'],
    ['TLS Fingerprint', 'curl_cffi Chrome 110 impersonation', 'Standard DNS client (no fingerprinting)'],
    ['Steganography', 'None (proxy IP rotation only)', 'Configurable DNS suffix camouflage (Sonos, AirPlay, Spotify)'],
    ['Detection Resistance', 'Moderate: proxies can be IP-blocked', 'High: encrypted payload in legitimate-looking DNS'],
    ['Pros', 'Browser-realistic TLS; hard to fingerprint as bot', 'Military-grade encryption; invisible to HTTP inspectors'],
    ['Cons', 'No payload encryption; proxy IPs are observable', 'DNS patterns can be flagged by advanced IDS/IPS'],
    ['Star Rating (A)', '\u2605\u2605\u2605\u2606\u2606 (3/5)', '\u2605\u2605\u2606\u2606\u2606 (2/5)'],
    ['Star Rating (B)', '\u2605\u2605\u2606\u2606\u2606 (2/5)', '\u2605\u2605\u2605\u2605\u2605 (5/5)'],
]

story.append(make_table(enc_comparison, col_widths=[30.5*mm, 69.7*mm, 69.7*mm]))
story.append(caption('Table 5.3: Encryption & evasion comparison'))

story.append(spacer(8))

# ─── Dimension 4: Rate Limiting & Resilience ──────────────────────
story.append(heading2('5.4 Rate Limiting & Resilience'))

rate_comparison = [
    ['Dimension', 'OWL-AGENT v4.2 (A)', 'LLM-DNS-Proxy (B)'],
    ['Rate Limiting', 'Adaptive per-domain (token bucket, EMA adjustment)', 'None (DNS has no rate concept)'],
    ['Circuit Breaker', 'Yes: 5-failure threshold, 30s recovery, 3-state pattern', 'None'],
    ['Retry Logic', 'resilient-httpx + max_retries=3 + Retry-After parsing', 'Client retries on DNS timeout'],
    ['Request Dedup', 'Yes: in-flight future tracking per URL', 'None (single conversation stream)'],
    ['Caching', 'LRU + disk (SHA-256 keyed, TTL-managed)', 'None (conversation context only)'],
    ['Pros', 'Self-healing: backs off on 429, ramps up on success', 'Simple: no rate management needed for DNS'],
    ['Cons', 'Over-engineered for simple use cases', 'No protection against DNS flooding or server overload'],
    ['Star Rating (A)', '\u2605\u2605\u2605\u2605\u2605 (5/5)', '\u2605\u2605\u2606\u2606\u2606 (2/5)'],
    ['Star Rating (B)', '\u2605\u2605\u2606\u2606\u2606 (2/5)', '\u2605\u2605\u2605\u2605\u2606 (4/5)'],
]

story.append(make_table(rate_comparison, col_widths=[30.5*mm, 69.7*mm, 69.7*mm]))
story.append(caption('Table 5.4: Rate limiting & resilience comparison'))

story.append(spacer(8))

# ─── Dimension 5: Session & State ──────────────────────────────────
story.append(heading2('5.5 Session & State Management'))

state_comparison = [
    ['Dimension', 'OWL-AGENT v4.2 (A)', 'LLM-DNS-Proxy (B)'],
    ['State Store', 'RedisStore (optional) + in-memory', 'Session context in conversation state'],
    ['Shared State', 'Yes: Redis enables multi-instance state sharing', 'No: single-client session persistence'],
    ['Horizontal Scale', 'Yes: multiple instances share proxy pool via Redis', 'No: single server per domain'],
    ['Restart Recovery', 'Disk cache + Redis preserves state across restarts', 'Conversation lost on server restart'],
    ['Pros', 'Distributed scraping, zero data loss on restart', 'Lightweight, no external dependencies'],
    ['Cons', 'Redis dependency adds complexity', 'No persistence; single-server bottleneck'],
    ['Star Rating (A)', '\u2605\u2605\u2605\u2605\u2605 (5/5)', '\u2605\u2605\u2606\u2606\u2606 (2/5)'],
    ['Star Rating (B)', '\u2605\u2605\u2606\u2606\u2606 (2/5)', '\u2605\u2605\u2605\u2606\u2606 (3/5)'],
]

story.append(make_table(state_comparison, col_widths=[30.5*mm, 69.7*mm, 69.7*mm]))
story.append(caption('Table 5.5: Session & state management comparison'))

story.append(spacer(8))

# ─── Dimension 6: LLM Integration ──────────────────────────────────
story.append(heading2('5.6 LLM & AI Integration'))

llm_comparison = [
    ['Dimension', 'OWL-AGENT v4.2 (A)', 'LLM-DNS-Proxy (B)'],
    ['LLM Usage', 'No direct LLM (scraping engine only)', 'Primary purpose: LLM conversation via DNS'],
    ['Provider Support', 'None (data retrieval focus)', 'OpenAI, Ollama, vLLM, OpenRouter, LocalAI (any OpenAI-compatible)'],
    ['Web Search', 'No (scrapes target URLs directly)', 'Perplexity AI integration with function calling'],
    ['Streaming', 'No LLM streaming', 'Token-by-token streaming via DNS TXT chunks'],
    ['Pros', 'Not dependent on any LLM API', 'Universal LLM access through restricted networks'],
    ['Cons', 'Cannot provide AI-powered analysis of scraped data', 'Requires LLM API key; limited by DNS chunk size'],
    ['Star Rating (A)', '\u2605\u2605\u2606\u2606\u2606 (2/5)', '\u2605\u2605\u2605\u2605\u2605 (5/5)'],
    ['Star Rating (B)', '\u2605\u2605\u2606\u2606\u2606 (2/5)', '\u2605\u2605\u2605\u2605\u2605 (5/5)'],
]

story.append(make_table(llm_comparison, col_widths=[30.5*mm, 69.7*mm, 69.7*mm]))
story.append(caption('Table 5.6: LLM & AI integration comparison'))

story.append(spacer(8))

# ─── Dimension 7: Deployment Maturity ──────────────────────────────
story.append(heading2('5.7 Deployment Maturity'))

deploy_comparison = [
    ['Dimension', 'OWL-AGENT v4.2 (A)', 'LLM-DNS-Proxy (B)'],
    ['Install Method', 'Self-contained install.sh script + venv + pip', 'uv sync (modern Python packaging)'],
    ['Config Management', 'JSON config file + environment variables', 'Environment variables only'],
    ['Service Management', 'Manual (no systemd template)', 'Complete systemd unit file included'],
    ['Monitoring', 'Prometheus metrics (prometheus-client)', 'tcpdump + journalctl (basic)'],
    ['Documentation', 'Full README with architecture, code, benchmarks, roadmap', 'Comprehensive README with setup, deployment, troubleshooting'],
    ['Production Readiness', 'Production-grade (circuit breaker, Redis, quality scoring)', 'Proof-of-concept with production deployment guide'],
    ['Star Rating (A)', '\u2605\u2605\u2605\u2605\u2606 (4/5)', '\u2605\u2605\u2605\u2606\u2606 (3/5)'],
    ['Star Rating (B)', '\u2605\u2605\u2605\u2606\u2606 (3/5)', '\u2605\u2605\u2605\u2605\u2606 (4/5)'],
]

story.append(make_table(deploy_comparison, col_widths=[30.5*mm, 69.7*mm, 69.7*mm]))
story.append(caption('Table 5.7: Deployment maturity comparison'))

story.append(spacer(8))

# ─── Dimension 8: Obsidian Compatibility ────────────────────────────
story.append(heading2('5.8 Obsidian Compatibility'))

obsidian_comparison = [
    ['Dimension', 'OWL-AGENT v4.2 (A)', 'LLM-DNS-Proxy (B)'],
    ['Output Format', 'HTML -> Markdown (turndown + markdownify)', 'Plain text (conversation output)'],
    ['Obsidian Skill', 'Yes: ~/.obsidian/skills/owl-agent/ in install.sh', 'None (no Obsidian integration)'],
    ['Markdown Quality', 'Full HTML-to-Markdown conversion with metadata', 'Raw conversation text (no formatting)'],
    ['Canvas/Bases', 'Not supported', 'Not supported'],
    ['Wikilinks', 'Not generated', 'Not generated'],
    ['Pros', 'Built-in Obsidian skill + Markdown conversion', 'Simple text output easy to paste into Obsidian'],
    ['Cons', 'No wikilinks, no canvas, no callouts', 'No structured Markdown, no Obsidian skill'],
    ['Star Rating (A)', '\u2605\u2605\u2605\u2605\u2606 (4/5)', '\u2605\u2605\u2606\u2606\u2606 (2/5)'],
    ['Star Rating (B)', '\u2605\u2605\u2606\u2606\u2606 (2/5)', '\u2605\u2605\u2606\u2606\u2606 (2/5)'],
]

story.append(make_table(obsidian_comparison, col_widths=[30.5*mm, 69.7*mm, 69.7*mm]))
story.append(caption('Table 5.8: Obsidian compatibility comparison'))

story.append(spacer(8))

# ─── Dimension 9: Ecosystem Integration ────────────────────────────
story.append(heading2('5.9 Ecosystem Integration'))

eco_comparison = [
    ['Dimension', 'OWL-AGENT v4.2 (A)', 'LLM-DNS-Proxy (B)'],
    ['AI Agent Support', '10+ agents (OpenCode, Cline, Cursor, Warp, Claude, Codex, Antigravity, Kiro, Hermes)', 
     'None (standalone CLI tool)'],
    ['Skills.sh', 'Designed for skills.sh distribution', 'Not registered on skills.sh'],
    ['npm/npx', 'agent-browser via npm', 'No Node.js dependencies'],
    ['Python Packaging', 'venv + pip install', 'uv (modern Rust-based Python manager)'],
    ['Community', 'Broad: 10+ agent ecosystem integrations', 'Niche: DNS tunneling community'],
    ['Star Rating (A)', '\u2605\u2605\u2605\u2605\u2605 (5/5)', '\u2605\u2605\u2606\u2606\u2606 (2/5)'],
    ['Star Rating (B)', '\u2605\u2605\u2606\u2606\u2606 (2/5)', '\u2605\u2605\u2605\u2606\u2606 (3/5)'],
]

story.append(make_table(eco_comparison, col_widths=[30.5*mm, 69.7*mm, 69.7*mm]))
story.append(caption('Table 5.9: Ecosystem integration comparison'))

story.append(spacer(8))

# ─── Aggregate Star Rating Summary ────────────────────────────────
story.append(heading2('5.10 Aggregate Star Rating Summary'))

aggregate = [
    ['Dimension', 'A Rating', 'B Rating', 'Merged Target', 'Synergy Gain'],
    ['Architecture Layers', '4/5', '4/5', '5/5', '+1 (dual-channel unified)'],
    ['Proxy & Access', '5/5 (A) / 2/5 (B)', '2/5 (A) / 5/5 (B)', '5/5', '+3 (both channels)'],
    ['Encryption & Evasion', '3/5 (A) / 2/5 (B)', '2/5 (A) / 5/5 (B)', '5/5', '+3 (HTTP+DNS evasion)'],
    ['Rate Limiting', '5/5', '2/5', '5/5', '+3 (OWL rate logic applied to DNS)'],
    ['Session & State', '5/5', '2/5', '5/5', '+3 (Redis for both HTTP and DNS state)'],
    ['LLM Integration', '2/5', '5/5', '5/5', '+3 (OWL scrapes data; DNS tunnels LLM analysis)'],
    ['Deployment', '4/5', '3/5', '5/5', '+1 (unified installer + systemd)'],
    ['Obsidian', '4/5', '2/5', '5/5', '+3 (Markdown output + Obsidian skill)'],
    ['Ecosystem', '5/5', '2/5', '5/5', '+3 (skills.sh distribution + 10+ agents)'],
    ['OVERALL AVERAGE', '4.3/5', '2.8/5', '5.0/5', '+2.2 (massive synergy)'],
]

story.append(make_table(aggregate, col_widths=[37.8*mm, 23.6*mm, 23.6*mm, 33.1*mm, 51.9*mm]))
story.append(caption('Table 5.10: Aggregate star ratings — merged system targets 5/5 across all dimensions'))

story.append(PageBreak())

# ============================================================
# CHAPTER 6: UNIFIED ARCHITECTURE & SYNERGY ANALYSIS
# ============================================================
story.append(heading1('6. Unified Architecture & Synergy Analysis'))

story.append(body(
    'The merged system, designated <b>OWL-DNS-Synergy</b>, unifies the HTTP proxy evasion capabilities of '
    'OWL-AGENT with the DNS tunneling capabilities of LLM-DNS-Proxy into a dual-channel resilient access '
    'engine. The architecture follows the SMP-v5.1 Beaver (builder) mode, designing practical systems '
    'step-by-step with explicit trade-off analysis at each decision point.'
))
story.append(spacer(6))

story.append(heading2('6.1 Synergy Mapping'))

synergy_map = [
    ['OWL-AGENT Capability', 'LLM-DNS-Proxy Capability', 'Unified Synergy', 'Value'],
    ['ProxyBroker2 (50+ sources)', 'DNS tunnel (captive portal bypass)', 
     'Dual-channel access: try HTTP first, fall back to DNS', 'Eliminates single-channel failure'],
    ['curl_cffi Chrome fingerprint', 'Fernet AES-128 encryption', 
     'TLS-realistic HTTP + encrypted DNS payload', 'Two-layer evasion stack'],
    ['QualityScorer (EMA proxy scoring)', 'No scoring (single server)', 
     'Unified scorer: rate proxies AND DNS servers', 'Smart channel selection'],
    ['AdaptiveRateLimiter (per-domain)', 'No rate limiting', 
     'Rate limits for HTTP + DNS flood protection', 'Prevents both HTTP bans and DNS detection'],
    ['CircuitBreaker (per-domain)', 'No circuit breaker', 
     'Circuit for HTTP domains AND DNS server failures', 'Self-healing on both channels'],
    ['RedisStore (state sharing)', 'Session context (in-memory)', 
     'Redis for proxy scores, circuit state, AND conversation context', 'Persistent multi-instance operation'],
    ['HTTPCache (LRU + disk)', 'No caching', 
     'Cache HTTP responses AND DNS conversation history', 'Eliminates redundant requests on both channels'],
    ['RequestDeduplicator', 'No dedup', 
     'Dedup HTTP requests AND DNS conversation sessions', 'Prevents duplicate work across agents'],
    ['turndown + markdownify', 'Plain text output', 
     'Markdown conversion for BOTH HTTP and DNS outputs', 'Unified Obsidian-ready format'],
    ['agent-browser (headless)', 'No browser rendering', 
     'Headless browser for HTTP; DNS for LLM analysis of scraped content', 'Scrape + analyze pipeline'],
]

story.append(make_table(synergy_map, col_widths=[38.9*mm, 38.9*mm, 48.6*mm, 43.7*mm]))
story.append(caption('Table 6.1: Synergy mapping — 11 capability pairs create unified value'))

story.append(spacer(8))

story.append(heading2('6.2 Unified System Architecture'))

unified_arch = [
    ['Layer', 'Component', 'Function', 'Source'],
    ['User Layer', 'OpenCode, Cline, Cursor, Warp, Claude, Codex, Antigravity, Kiro, Hermes, Obsidian', 
     'Multi-agent natural-language interface', 'OWL-AGENT (expanded)'],
    ['API Interface', 'CLI (owl-dns-synergy), Python ResilientClient, OpenCode skill, Cursor command', 
     'Single entry point for both channels', 'OWL-AGENT (extended)'],
    ['Channel Selector', 'SmartChannelRouter', 
     'Try HTTP first; if blocked, switch to DNS; if DNS monitored, switch back', 'NEW (merger-specific)'],
    ['HTTP Channel', 'ProxyPoolManager + ProxyBroker2 + curl_cffi + agent-browser', 
     'HTTP proxy evasion with fingerprinting', 'OWL-AGENT'],
    ['DNS Channel', 'Fernet encryption + DNS chunking + camouflage suffixes + DNS server', 
     'DNS tunneling with steganographic evasion', 'LLM-DNS-Proxy'],
    ['Unified Intelligence', 'QualityScorer (proxies + DNS), AdaptiveRateLimiter, CircuitBreaker', 
     'Quality-aware, rate-adaptive, self-healing across both channels', 'OWL-AGENT (extended)'],
    ['Unified Persistence', 'RedisStore (proxy scores, circuit state, conversation context, DNS history)', 
     'Shared state across instances and channels', 'OWL-AGENT (expanded)'],
    ['Unified Cache', 'HTTPCache (LRU + disk) + DNSConversationStore', 
     'Cache HTTP responses and DNS conversation history', 'OWL-AGENT (expanded)'],
    ['LLM Integration', 'OpenAI, Ollama, vLLM, OpenRouter + Perplexity web search', 
     'LLM analysis of scraped data via DNS or HTTP', 'LLM-DNS-Proxy (adopted)'],
    ['Markdown Output', 'turndown + markdownify + Obsidian skill', 
     'Convert all outputs to Obsidian-compatible Markdown', 'OWL-AGENT (expanded)'],
    ['Monitoring', 'Prometheus metrics + DNS query analytics', 
     'Unified observability for both channels', 'OWL-AGENT + NEW'],
]

story.append(make_table(unified_arch, col_widths=[28.3*mm, 56.7*mm, 51.9*mm, 33.1*mm]))
story.append(caption('Table 6.2: Unified OWL-DNS-Synergy architecture (11 layers)'))

story.append(spacer(8))

story.append(heading2('6.3 Smart Channel Router Logic'))

story.append(body(
    'The SmartChannelRouter is the key innovation of the merger. It implements a three-state decision engine '
    'that selects the optimal access channel based on real-time network conditions. The router operates as follows: '
    'State 1 (HTTP Preferred): attempt HTTP proxy request first; if successful, return response and update proxy '
    'quality score; if 429/503 received, trigger AdaptiveRateLimiter backoff and attempt alternate proxy; if all '
    'proxies fail or circuit breaker opens for the target domain, transition to State 2. State 2 (DNS Fallback): '
    'switch to DNS tunneling channel; encrypt request via Fernet, chunk and encode as DNS queries with camouflage '
    'suffix; if DNS server responds, return LLM analysis; if DNS queries timeout or DNS circuit breaker opens, '
    'transition to State 3. State 3 (Hybrid Retry): alternate between HTTP and DNS with exponential backoff; '
    'if both channels fail after max retries, return error with diagnostic data for both channels.'
))
story.append(spacer(6))

story.append(body(
    'The router maintains per-domain channel preference history in RedisStore, learning which channel works best '
    'for each target over time. Domains behind captive portals will quickly accumulate DNS preference; domains '
    'with anti-bot systems will accumulate proxy preference. This creates a self-optimizing channel selection '
    'mechanism that reduces unnecessary channel-switching overhead and maximizes success rates.'
))

story.append(PageBreak())

# ============================================================
# CHAPTER 7: IMPLEMENTATION PLAN
# ============================================================
story.append(heading1('7. Implementation Plan (Phased Roadmap)'))

story.append(body(
    'Following SMP-v5.1 Ant (systematic) mode, the implementation plan breaks the merger into five phases '
    'with explicit verification gates between each phase. Each phase produces a runnable artifact that can '
    'be tested independently before proceeding to the next phase.'
))
story.append(spacer(8))

story.append(heading2('7.1 Phase 1: Foundation Merge (Week 1-2)'))

phase1 = [
    ['Task', 'Duration', 'Files', 'Verification'],
    ['Create owl-dns-synergy project structure', '1 day', 'setup.py, pyproject.toml, directory scaffold', 'pip install -e . succeeds'],
    ['Merge OWL-AGENT core classes into new package', '3 days', 'owl_dns_synergy/core.py (ResilientClient, HTTPCache, QualityScorer, etc.)', 'Unit tests pass for all OWL core classes'],
    ['Merge LLM-DNS-Proxy crypto/chunking into new package', '2 days', 'owl_dns_synergy/dns_channel.py (FernetCrypto, DNSChunker, CamouflageSuffix)', 'DNS chunking round-trip test passes'],
    ['Create unified config system', '1 day', 'owl_dns_synergy/config.py (JSON + env vars)', 'Config loads correctly from both sources'],
    ['Merge RedisStore to cover both channels', '2 days', 'owl_dns_synergy/persistence.py (RedisStore with DNS conversation support)', 'Redis stores/retrieves HTTP and DNS state'],
]

story.append(make_table(phase1, col_widths=[49.2*mm, 22.4*mm, 49.2*mm, 49.2*mm]))
story.append(caption('Table 7.1: Phase 1 tasks'))

story.append(spacer(8))

story.append(heading2('7.2 Phase 2: Smart Channel Router (Week 3-4)'))

phase2 = [
    ['Task', 'Duration', 'Files', 'Verification'],
    ['Implement SmartChannelRouter', '3 days', 'owl_dns_synergy/router.py', 'Router selects correct channel in all 3 states'],
    ['Integrate HTTP channel into router', '2 days', 'owl_dns_synergy/http_channel.py', 'HTTP requests route through router correctly'],
    ['Integrate DNS channel into router', '2 days', 'owl_dns_synergy/dns_channel.py', 'DNS requests route through router correctly'],
    ['Channel preference learning', '2 days', 'owl_dns_synergy/router.py (preference tracking)', 'Router learns domain-channel preferences over time'],
    ['End-to-end dual-channel test', '1 day', 'tests/test_router_e2e.py', 'Simulated captive portal + anti-bot scenario passes'],
]

story.append(make_table(phase2, col_widths=[49.2*mm, 22.4*mm, 49.2*mm, 49.2*mm]))
story.append(caption('Table 7.2: Phase 2 tasks'))

story.append(spacer(8))

story.append(heading2('7.3 Phase 3: LLM & Intelligence Integration (Week 5-6)'))

phase3 = [
    ['Task', 'Duration', 'Files', 'Verification'],
    ['Add LLM client to ResilientClient', '2 days', 'owl_dns_synergy/llm_client.py', 'LLM requests succeed via both HTTP and DNS channels'],
    ['Perplexity web search integration', '2 days', 'owl_dns_synergy/web_search.py', 'Web search works through DNS tunnel'],
    ['Unified QualityScorer (HTTP + DNS metrics)', '2 days', 'owl_dns_synergy/scorer.py', 'Scorer rates both proxy quality and DNS server latency'],
    ['AdaptiveRateLimiter for DNS flood protection', '1 day', 'owl_dns_synergy/rate_limiter.py', 'DNS rate limiting prevents detection patterns'],
    ['CircuitBreaker for DNS server failures', '1 day', 'owl_dns_synergy/circuit_breaker.py', 'DNS circuit breaker opens on server failure'],
]

story.append(make_table(phase3, col_widths=[49.2*mm, 22.4*mm, 49.2*mm, 49.2*mm]))
story.append(caption('Table 7.3: Phase 3 tasks'))

story.append(spacer(8))

story.append(heading2('7.4 Phase 4: Output & Obsidian Integration (Week 7-8)'))

phase4 = [
    ['Task', 'Duration', 'Files', 'Verification'],
    ['Unified Markdown output pipeline', '2 days', 'owl_dns_synergy/markdown.py', 'HTTP and DNS outputs both produce valid Obsidian Markdown'],
    ['Obsidian skill package (SKILL.md)', '2 days', 'skills/owl-dns-synergy/SKILL.md', 'Skill installs via npx skills add and executes correctly'],
    ['Wikilink generation for scraped references', '1 day', 'owl_dns_synergy/markdown.py (wikilinks)', 'Output Markdown includes Obsidian wikilinks'],
    ['JSON Canvas output for architecture diagrams', '1 day', 'owl_dns_synergy/canvas.py', 'Network topology rendered as .canvas file'],
    ['Obsidian Bases integration for metrics', '1 day', 'owl_dns_synergy/bases.py', 'Proxy/DNS quality data rendered as .base file'],
]

story.append(make_table(phase4, col_widths=[49.2*mm, 22.4*mm, 49.2*mm, 49.2*mm]))
story.append(caption('Table 7.4: Phase 4 tasks'))

story.append(spacer(8))

story.append(heading2('7.5 Phase 5: Production & Distribution (Week 9-10)'))

phase5 = [
    ['Task', 'Duration', 'Files', 'Verification'],
    ['Unified installer script (install.sh)', '1 day', 'install.sh', 'Clean install on Ubuntu, macOS, Windows (WSL)'],
    ['Systemd service template', '1 day', 'owl-dns-synergy.service', 'Service starts, stops, restarts correctly'],
    ['Prometheus + DNS analytics dashboard', '2 days', 'owl_dns_synergy/monitoring.py', 'Metrics visible in Prometheus + Grafana'],
    ['skills.sh package and distribution', '2 days', 'skills.sh registry, npx skills add', 'Skill discoverable via npx skills find scraper'],
    ['Documentation: README, API reference, deployment guide', '2 days', 'README.md, docs/', 'Complete docs pass readability review'],
    ['Benchmark suite: success rate, latency, channel switching', '2 days', 'benchmarks/', 'Benchmark results documented in README'],
]

story.append(make_table(phase5, col_widths=[49.2*mm, 22.4*mm, 49.2*mm, 49.2*mm]))
story.append(caption('Table 7.5: Phase 5 tasks'))

story.append(PageBreak())

# ============================================================
# CHAPTER 8: UNIFIED SYNERGIES SCRIPT
# ============================================================
story.append(heading1('8. Unified Synergies Script'))

story.append(body(
    'Below is the core unified synergies script that implements the SmartChannelRouter and demonstrates '
    'how OWL-AGENT and LLM-DNS-Proxy capabilities merge into a single ResilientClient interface. This '
    'script is the foundation of the owl-dns-synergy package and represents the minimal viable merger '
    'that can be extended with the full Phase 1-5 implementation plan.'
))
story.append(spacer(6))

script_lines = [
    '# owl_dns_synergy/router.py — Smart Channel Router',
    '# Merges OWL-AGENT HTTP proxy evasion + LLM-DNS-Proxy DNS tunneling',
    '',
    'import asyncio, time, logging',
    'from enum import Enum',
    'from dataclasses import dataclass, field',
    'from typing import Optional, Dict, Any',
    '',
    'class ChannelState(Enum):',
    '    HTTP_PREFERRED = 1    # Try HTTP proxy first',
    '    DNS_FALLBACK = 2     # Switch to DNS tunneling',
    '    HYBRID_RETRY = 3     # Alternate both channels',
    '',
    '@dataclass',
    'class ChannelResult:',
    '    channel: str          # "http" or "dns"',
    '    success: bool',
    '    data: Any = None',
    '    latency_ms: float = 0.0',
    '    error: str = ""',
    '',
    '@dataclass',
    'class DomainPreference:',
    '    domain: str',
    '    http_successes: int = 0',
    '    dns_successes: int = 0',
    '    http_failures: int = 0',
    '    dns_failures: int = 0',
    '    preferred_channel: str = "http"',
    '    last_updated: float = field(default_factory=time.time)',
    '',
    'class SmartChannelRouter:',
    '    """Selects optimal access channel (HTTP proxy or DNS tunnel)',
    '    based on real-time network conditions and learned preferences."""',
    '',
    '    def __init__(self, http_client, dns_client, redis_store=None):',
    '        self.http = http_client      # OWL-AGENT ResilientClient',
    '        self.dns = dns_client        # LLM-DNS-Proxy client',
    '        self.redis = redis_store     # Shared RedisStore',
    '        self._prefs: Dict[str, DomainPreference] = {}',
    '        self._state: Dict[str, ChannelState] = {}',
    '',
    '    async def fetch(self, url: str, **kwargs) -> ChannelResult:',
    '        domain = self._extract_domain(url)',
    '        state = self._get_state(domain)',
    '',
    '        if state == ChannelState.HTTP_PREFERRED:',
    '            result = await self._try_http(url, **kwargs)',
    '            if result.success:',
    '                self._record_success(domain, "http")',
    '                return result',
    '            # HTTP failed — try DNS',
    '            dns_result = await self._try_dns(url, **kwargs)',
    '            if dns_result.success:',
    '                self._record_success(domain, "dns")',
    '                self._set_state(domain, ChannelState.DNS_FALLBACK)',
    '                return dns_result',
    '            # Both failed — hybrid mode',
    '            self._set_state(domain, ChannelState.HYBRID_RETRY)',
    '            return await self._hybrid_retry(url, **kwargs)',
    '',
    '        elif state == ChannelState.DNS_FALLBACK:',
    '            result = await self._try_dns(url, **kwargs)',
    '            if result.success:',
    '                self._record_success(domain, "dns")',
    '                return result',
    '            # DNS failed — try HTTP again',
    '            http_result = await self._try_http(url, **kwargs)',
    '            if http_result.success:',
    '                self._record_success(domain, "http")',
    '                self._set_state(domain, ChannelState.HTTP_PREFERRED)',
    '                return http_result',
    '            self._set_state(domain, ChannelState.HYBRID_RETRY)',
    '            return await self._hybrid_retry(url, **kwargs)',
    '',
    '        else:  # HYBRID_RETRY',
    '            return await self._hybrid_retry(url, **kwargs)',
    '',
    '    async def _try_http(self, url, **kwargs) -> ChannelResult:',
    '        try:',
    '            start = time.time()',
    '            data = await self.http.fetch(url, **kwargs)',
    '            latency = (time.time() - start) * 1000',
    '            return ChannelResult("http", True, data, latency)',
    '        except Exception as e:',
    '            return ChannelResult("http", False, error=str(e))',
    '',
    '    async def _try_dns(self, url, **kwargs) -> ChannelResult:',
    '        try:',
    '            start = time.time()',
    '            data = await self.dns.chat(f"Analyze: {url}", **kwargs)',
    '            latency = (time.time() - start) * 1000',
    '            return ChannelResult("dns", True, data, latency)',
    '        except Exception as e:',
    '            return ChannelResult("dns", False, error=str(e))',
    '',
    '    async def _hybrid_retry(self, url, max_retries=3, **kwargs):',
    '        for i in range(max_retries):',
    '            await asyncio.sleep(2 ** i)  # exponential backoff',
    '            for channel_fn in [self._try_http, self._try_dns]:',
    '                result = await channel_fn(url, **kwargs)',
    '                if result.success:',
    '                    domain = self._extract_domain(url)',
    '                    ch = result.channel',
    '                    self._record_success(domain, ch)',
    '                    self._set_state(domain,',
    '                        ChannelState.HTTP_PREFERRED if ch == "http"',
    '                        else ChannelState.DNS_FALLBACK)',
    '                    return result',
    '        return ChannelResult("none", False, error="All channels exhausted")',
    '',
    '    def _record_success(self, domain, channel):',
    '        pref = self._prefs.setdefault(domain, DomainPreference(domain))',
    '        if channel == "http": pref.http_successes += 1',
    '        else: pref.dns_successes += 1',
    '        pref.preferred_channel = "http" if pref.http_successes >= pref.dns_successes else "dns"',
    '        pref.last_updated = time.time()',
    '        if self.redis:',
    '            self.redis.set(f"pref:{domain}", pref.__dict__)',
]

for line in script_lines:
    story.append(Paragraph(line, style_code))

story.append(spacer(8))

story.append(body(
    'This script demonstrates the core merger logic: the SmartChannelRouter maintains per-domain state '
    'preferences, automatically selecting the optimal channel based on accumulated success/failure history. '
    'When HTTP fails (captive portal, aggressive anti-bot), DNS tunneling activates seamlessly. When DNS '
    'is monitored or the server is down, HTTP proxy rotation takes over. The exponential backoff hybrid '
    'retry ensures that both channels are exhausted before reporting failure, and the RedisStore integration '
    'allows channel preferences to persist across restarts and be shared between multiple instances.'
))

story.append(PageBreak())

# ============================================================
# CHAPTER 9: OBSIDIAN INTEGRATION
# ============================================================
story.append(heading1('9. Obsidian Integration via kepano/obsidian-skills'))

story.append(body(
    'The kepano/obsidian-skills repository provides five agent skills that follow the Agent Skills specification '
    '(agentskills.io), making them compatible with Claude Code, Codex, Open Code, and other skills-compatible '
    'agents. These skills teach agents to interact with Obsidian vaults using the Obsidian CLI and open formats '
    'including Markdown, Bases, and JSON Canvas. The integration of OWL-DNS-Synergy with obsidian-skills creates '
    'a powerful feedback loop: scraped and tunneled data flows into Obsidian vaults as structured Markdown, and '
    'Obsidian notes can be used as scraping targets or LLM conversation context.'
))
story.append(spacer(6))

story.append(heading2('9.1 Obsidian Skills Overview'))

obs_skills = [
    ['Skill', 'Description', 'OWL-DNS-Synergy Usage'],
    ['obsidian-markdown', 'Create/edit Obsidian Flavored Markdown (.md) with wikilinks, embeds, callouts, properties', 
     'Output scraped/tunneled data as properly formatted Obsidian notes'],
    ['obsidian-bases', 'Create/edit Obsidian Bases (.base) with views, filters, formulas, summaries', 
     'Render proxy quality scores and DNS latency metrics as interactive tables'],
    ['json-canvas', 'Create/edit JSON Canvas (.canvas) with nodes, edges, groups, connections', 
     'Map network topology, channel routing decisions, and architecture diagrams'],
    ['obsidian-cli', 'Interact with Obsidian vaults via CLI including plugin/theme development', 
     'Automate vault operations: search, create, update notes from scraped data'],
    ['defuddle', 'Extract clean markdown from web pages, removing clutter to save tokens', 
     'Pre-process scraped HTML into token-efficient Markdown before Obsidian ingestion'],
]

story.append(make_table(obs_skills, col_widths=[30*mm, 65*mm, 75*mm]))
story.append(caption('Table 9.1: obsidian-skills mapped to OWL-DNS-Synergy usage'))

story.append(spacer(8))

story.append(heading2('9.2 Integration Architecture'))

story.append(body(
    'The integration follows a three-layer architecture. Layer 1 (Data Ingestion): OWL-DNS-Synergy scrapes '
    'or tunnels data via HTTP proxy or DNS channel, converts to Markdown using turndown + markdownify, and '
    'formats with Obsidian Flavored Markdown conventions (wikilinks, callouts, properties/frontmatter). Layer 2 '
    '(Structured Analysis): proxy quality scores, DNS latency metrics, and channel preference data are rendered '
    'as Obsidian Bases (.base files) with views, filters, and formulas that enable interactive exploration. '
    'Layer 3 (Visualization): network topology and channel routing decisions are rendered as JSON Canvas '
    '(.canvas files) with nodes representing domains, proxies, DNS servers, and edges representing active '
    'connections and preferred channels.'
))
story.append(spacer(6))

story.append(body(
    'The obsidian-cli skill enables automation of vault operations: after OWL-DNS-Synergy completes a scraping '
    'session, the CLI automatically creates or updates notes in the target vault, tags them with metadata '
    '(source URL, channel used, timestamp, quality score), and links them to related notes via wikilinks. '
    'The defuddle skill pre-processes scraped HTML before Obsidian ingestion, removing navigation, ads, '
    'and other clutter to produce clean, token-efficient Markdown that preserves only substantive content.'
))

story.append(spacer(8))

story.append(heading2('9.3 Installation & Configuration'))

story.append(body(
    'The unified system installs obsidian-skills alongside OWL-DNS-Synergy using the Agent Skills specification. '
    'Three installation methods are available depending on the agent platform. For marketplace installation, '
    'use: /plugin marketplace add kepano/obsidian-skills followed by /plugin install obsidian@obsidian-skills. '
    'For npx skills installation, use: npx skills add https://github.com/kepano/obsidian-skills. For manual '
    'installation with OpenCode, clone the full repository into ~/.opencode/skills/obsidian-skills so the '
    'directory structure becomes ~/.opencode/skills/obsidian-skills/skills/<skill-name>/SKILL.md. OpenCode '
    'auto-disovers all SKILL.md files under ~/.opencode/skills/ without any configuration changes.'
))
story.append(spacer(6))

story.append(body(
    'The OWL-DNS-Synergy skill itself should be installed alongside obsidian-skills in the same skills '
    'directory. The skill\'s SKILL.md file defines the unified interface: fetch(url) attempts HTTP proxy '
    'first, falling back to DNS tunneling; chat(message) sends LLM conversations via the optimal channel; '
    'markdown(url) scrapes and converts to Obsidian Markdown; and base(metric) renders quality metrics '
    'as Obsidian Bases. All outputs are written directly to the Obsidian vault using obsidian-cli.'
))

story.append(spacer(8))

story.append(heading2('9.4 Example: Scraped Data to Obsidian Note'))

story.append(body(
    'Consider a practical workflow: an agent needs to scrape a product page behind an anti-bot system. '
    'The SmartChannelRouter first attempts HTTP via OWL-AGENT proxy pool with curl_cffi Chrome fingerprinting. '
    'If the target blocks all proxies (circuit breaker opens), the router switches to DNS tunneling via '
    'LLM-DNS-Proxy, sending an LLM query about the product through DNS camouflage queries. The LLM response '
    'is then converted to Obsidian Markdown with frontmatter properties (source, channel, timestamp, '
    'quality_score) and wikilinks to related product notes. The obsidian-cli skill creates the note in the '
    'vault, and obsidian-bases renders the scraping metrics (latency, success rate, channel preference) as '
    'an interactive table. This creates a self-documenting knowledge base where every note carries its '
    'acquisition metadata and the vault maintains real-time quality dashboards.'
))

story.append(PageBreak())

# ============================================================
# CHAPTER 10: APPENDIX
# ============================================================
story.append(heading1('10. Appendix: Skills.sh Trending & Scraper Ecosystem'))

story.append(body(
    'The skills.sh marketplace is the primary distribution channel for AI agent skills, supporting Claude '
    'Code, Cursor, Windsurf, OpenCode, and other compatible agents. The trending page reveals the fastest-growing '
    'skills each week, organized by agent compatibility. For the OWL-DNS-Synergy project, the relevant ecosystem '
    'includes browser automation skills, web scraping skills, DNS/network utility skills, and Obsidian integration '
    'skills. The scraper subcategory on skills.sh includes skills for proxy management, content extraction, '
    'Markdown conversion, and distributed scraping orchestration.'
))
story.append(spacer(6))

story.append(heading2('10.1 Relevant Trending Skills'))

trending_skills = [
    ['Skill', 'Category', 'Installs (Weekly)', 'Relevance to OWL-DNS-Synergy'],
    ['agent-browser (vercel-labs)', 'Browser Automation', 'High', 'Headless browser for OWL-AGENT JS rendering layer'],
    ['obsidian-skills (kepano)', 'Knowledge Management', 'Growing', 'Obsidian CLI + Markdown/Canvas/Bases integration'],
    ['parallel-deep-research', 'Web Research', 'High', 'Multi-source research for proxy pool and DNS server analysis'],
    ['find-skills (skills.sh)', 'Skill Discovery', 'Core', 'Version-locked tool discovery and installation'],
    ['defuddle (kepano)', 'Content Processing', 'Medium', 'Clean Markdown extraction from web pages'],
    ['web-reader (z-ai)', 'Content Extraction', 'High', 'Structured page content extraction'],
]

story.append(make_table(trending_skills, col_widths=[35.8*mm, 31.3*mm, 26.8*mm, 76.1*mm]))
story.append(caption('Table 10.1: Relevant skills.sh trending skills'))

story.append(spacer(8))

story.append(heading2('10.2 npx skills find scraper Output'))

story.append(body(
    'Running <b>npx skills find scraper</b> discovers scraper-related skills on skills.sh. The output '
    'typically includes skills categorized by: (1) HTTP scrapers with proxy rotation (where OWL-AGENT belongs), '
    '(2) Protocol-level scrapers with DNS/ICMP tunneling (where LLM-DNS-Proxy belongs), (3) Hybrid scrapers '
    'combining both approaches (the target category for OWL-DNS-Synergy), and (4) Output processors that '
    'convert scraped data to Markdown/JSON/Canvas formats (where obsidian-skills belongs). The key finding '
    'is that the hybrid category is currently empty, confirming that OWL-DNS-Synergy would be the first '
    'skill to combine HTTP proxy evasion and DNS tunneling in a single unified interface on skills.sh.'
))

story.append(spacer(8))

story.append(heading2('10.3 SMP-v5.1 Adoption Summary'))

story.append(body(
    'The SMP-v5.1 Silent Methodological Protocol has been adopted as the governing operating instructions '
    'for this analysis. Key protocol elements applied: Silent Protocol (invisible diagnosis of what the user '
    'actually needs beyond the literal request); Owl cognitive mode for deep analysis of hidden factors in '
    'both projects; Ant mode for systematic task decomposition into the 5-phase implementation plan; Beaver '
    'mode for practical system design of the SmartChannelRouter; quality gates at every stage (Discovery, '
    'Brainstorming, Research, Planning, Execution, Validation, Review, Completion); and the response framework '
    'structure (Problem | Solution | Reasoning | Assumptions | Next Step | 3 Suggestions). The protocol\'s '
    'mandate of depth before speed ensured that the comparison matrix covers ten dimensions rather than a '
    'surface-level feature list, and the hard-gate requirement at Stage 1 (Capability Composition) ensured '
    'that skills.sh discovery was completed before any analysis or code generation began.'
))

# ─── Build PDF ────────────────────────────────────────────────────
from reportlab.lib.units import inch

def add_page_number(canvas, doc):
    """Add page number to footer."""
    page_num = canvas.getPageNumber()
    text = f"Page {page_num}"
    canvas.saveState()
    canvas.setFont('Carlito', 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawCentredString(PAGE_W / 2, BOTTOM_MARGIN / 2, text)
    canvas.restoreState()

def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title='OWL-DNS Synergy Report',
        author='Z.ai Research Division',
        subject='A/B Comparison Matrix, Implementation Plan, Unified Script, and Obsidian Integration for OWL-AGENT v4.2 + LLM-DNS-Proxy Merger',
    )
    
    doc.build(story, onLaterPages=add_page_number)
    print(f"PDF generated: {OUTPUT_PATH}")

if __name__ == '__main__':
    build_pdf()
