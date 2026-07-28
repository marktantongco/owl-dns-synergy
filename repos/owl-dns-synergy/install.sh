#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# OWL-DNS-SYNERGY Unified Installer v1.0.0
# Self-contained script that installs the merged OWL-AGENT v4.2 +
# LLM-DNS-Proxy system with Prometheus metrics, DNS flood protection,
# and Obsidian integration.
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────────
SYNERGY_HOME="${HOME}/.owl-dns-synergy"
REPO_DIR="${HOME}/owl-dns-synergy"
VENV_DIR="${SYNERGY_HOME}/venv"
PYTHON_CMD="${VENV_DIR}/bin/python"
PIP_CMD="${VENV_DIR}/bin/pip"
LLM_DNS_PROXY_REPO="https://github.com/irdbl/llm-dns-proxy.git"
SYNERGY_REPO_DIR=""  # Will be set if local repo exists

# ─── Colors ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Logging helpers ──────────────────────────────────────────────────
log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}${BOLD}[STEP]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}${BOLD}[OK]${NC}    $1"; }

# ─── Banner ──────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   OWL-DNS-SYNERGY Unified Installer v1.0.0                ║${NC}"
echo -e "${BOLD}${CYAN}║   HTTP Proxy Evasion + DNS Tunneling + Obsidian           ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════════
# STEP 1: System Requirements Check
# ═══════════════════════════════════════════════════════════════════
log_step "1/10 — Checking system requirements..."

MISSING=0

if ! command -v python3 &>/dev/null; then
    log_error "Python3 is required but not installed."
    MISSING=1
else
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ "$(printf '%s\n' "3.10" "$PY_VER" | sort -V | head -n1)" != "3.10" ]]; then
        log_error "Python 3.10+ required (found $PY_VER)."
        MISSING=1
    else
        log_ok "Python $PY_VER detected"
    fi
fi

if ! command -v git &>/dev/null; then
    log_warn "git not found — cloning repos will be skipped"
fi

if ! command -v pip3 &>/dev/null && ! python3 -m pip --version &>/dev/null; then
    log_error "pip is required but not found."
    MISSING=1
fi

if ! command -v node &>/dev/null; then
    log_warn "Node.js not found — npx skills and agent-browser will be skipped"
fi

if ! command -v uv &>/dev/null; then
    log_warn "uv not found — llm-dns-proxy standalone install will use pip fallback"
fi

if [[ $MISSING -eq 1 ]]; then
    log_error "Missing critical dependencies. Please install them first."
    exit 1
fi

log_ok "System requirements satisfied"

# ═══════════════════════════════════════════════════════════════════
# STEP 2: npx skills find scraper — Discover additional skills
# ═══════════════════════════════════════════════════════════════════
log_step "2/10 — Discovering scraper skills via npx skills find scraper..."

if command -v npx &>/dev/null; then
    npx skills find scraper 2>&1 | head -30 || log_warn "skills.sh discovery failed (non-blocking)"
    log_ok "Skills.sh scraper discovery completed"
else
    log_warn "npx not available — skip skills.sh discovery"
fi

# ═══════════════════════════════════════════════════════════════════
# STEP 3: Clone LLM-DNS-Proxy repo
# ═══════════════════════════════════════════════════════════════════
log_step "3/10 — Cloning LLM-DNS-Proxy repository..."

LLM_DNS_DIR="${SYNERGY_HOME}/repos/llm-dns-proxy"

if [[ -d "$LLM_DNS_DIR" ]]; then
    log_info "llm-dns-proxy already cloned at $LLM_DNS_DIR"
    cd "$LLM_DNS_DIR" && git pull 2>/dev/null || log_warn "git pull failed (non-blocking)"
else
    if command -v git &>/dev/null; then
        mkdir -p "${SYNERGY_HOME}/repos"
        git clone "$LLM_DNS_PROXY_REPO" "$LLM_DNS_DIR" 2>/dev/null || {
            log_warn "git clone failed — you can manually clone: git clone $LLM_DNS_PROXY_REPO"
        }
        log_ok "llm-dns-proxy cloned to $LLM_DNS_DIR"
    else
        log_warn "git not available — manual clone required"
    fi
fi

# ═══════════════════════════════════════════════════════════════════
# STEP 4: Create project directories
# ═══════════════════════════════════════════════════════════════════
log_step "4/10 — Creating OWL-DNS-Synergy home directory structure..."

mkdir -p "$SYNERGY_HOME/cache/http"
mkdir -p "$SYNERGY_HOME/config"
mkdir -p "$SYNERGY_HOME/logs"
mkdir -p "$SYNERGY_HOME/repos"

log_ok "Directory structure created at $SYNERGY_HOME"

# ═══════════════════════════════════════════════════════════════════
# STEP 5: Create Python virtual environment
# ═══════════════════════════════════════════════════════════════════
log_step "5/10 — Creating Python virtual environment..."

if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
    log_ok "Virtual environment created"
else
    log_info "Virtual environment already exists"
fi

# ═══════════════════════════════════════════════════════════════════
# STEP 6: Install Python dependencies (merged requirements)
# ═══════════════════════════════════════════════════════════════════
log_step "6/10 — Installing merged Python dependencies..."
log_info "This may take a few minutes..."

$PIP_CMD install --upgrade pip wheel setuptools 2>/dev/null

# OWL-AGENT dependencies
$PIP_CMD install \
    httpx[socks] \
    aiohttp \
    aiofiles \
    proxybroker2 \
    circuitbreaker \
    beautifulsoup4 \
    markdownify \
    prometheus-client \
    2>/dev/null || log_warn "Some OWL-AGENT dependencies failed"

# LLM-DNS-Proxy dependencies
$PIP_CMD install \
    dnslib \
    openai \
    cryptography \
    click \
    2>/dev/null || log_warn "Some LLM-DNS-Proxy dependencies failed"

# Optional: Redis support
$PIP_CMD install redis 2>/dev/null || log_warn "Redis package skipped (optional)"

# Optional: curl_cffi for Chrome fingerprinting
$PIP_CMD install curl_cffi 2>/dev/null || log_warn "curl_cffi skipped (optional — requires compilation)"

# Optional: resilient-httpx for advanced retry logic
$PIP_CMD install resilient-httpx 2>/dev/null || log_warn "resilient-httpx skipped (optional)"

log_ok "Core dependencies installed"

# ═══════════════════════════════════════════════════════════════════
# STEP 7: Install owl-dns-synergy package (if repo available)
# ═══════════════════════════════════════════════════════════════════
log_step "7/10 — Installing OWL-DNS-Synergy package..."

# Check if the unified repo is available locally
SYNERGY_PKG_DIR=""
if [[ -d "/home/z/my-project/repos/owl-dns-synergy" ]]; then
    SYNERGY_PKG_DIR="/home/z/my-project/repos/owl-dns-synergy"
elif [[ -d "$REPO_DIR" ]]; then
    SYNERGY_PKG_DIR="$REPO_DIR"
fi

if [[ -n "$SYNERGY_PKG_DIR" ]]; then
    cd "$SYNERGY_PKG_DIR"
    $PIP_CMD install -e . 2>/dev/null || {
        log_warn "pip install -e failed — package may need manual setup"
        log_info "You can install manually: cd $SYNERGY_PKG_DIR && $PIP_CMD install -e ."
    }
    log_ok "OWL-DNS-Synergy package installed"
else
    log_warn "OWL-DNS-Synergy repo not found locally"
    log_info "To install: clone or copy the repo to $REPO_DIR, then run: $PIP_CMD install -e ."
fi

# ═══════════════════════════════════════════════════════════════════
# STEP 8: Install LLM-DNS-Proxy standalone (via uv or pip)
# ═══════════════════════════════════════════════════════════════════
log_step "8/10 — Installing LLM-DNS-Proxy standalone..."

if [[ -d "$LLM_DNS_DIR" ]]; then
    cd "$LLM_DNS_DIR"
    if command -v uv &>/dev/null; then
        uv sync 2>/dev/null || log_warn "uv sync failed for llm-dns-proxy"
        log_ok "llm-dns-proxy installed via uv"
    else
        $PIP_CMD install -e . 2>/dev/null || log_warn "pip install failed for llm-dns-proxy"
        log_ok "llm-dns-proxy installed via pip (fallback)"
    fi
else
    log_warn "llm-dns-proxy repo not cloned — standalone DNS server unavailable"
fi

# ═══════════════════════════════════════════════════════════════════
# STEP 9: Install Obsidian skills + agent-browser
# ═══════════════════════════════════════════════════════════════════
log_step "9/10 — Installing Obsidian skills and agent-browser..."

if command -v npx &>/dev/null; then
    # Install kepano/obsidian-skills
    npx skills add https://github.com/kepano/obsidian-skills 2>/dev/null || {
        log_warn "npx skills add obsidian-skills failed — you can install manually"
        log_info "Manual: git clone https://github.com/kepano/obsidian-skills ~/.opencode/skills/obsidian-skills"
    }
    log_ok "obsidian-skills installation attempted"

    # Install OWL-DNS-Synergy skill (if available)
    if [[ -n "$SYNERGY_PKG_DIR" ]] && [[ -d "$SYNERGY_PKG_DIR/skills/owl-dns-synergy" ]]; then
        mkdir -p "${HOME}/.opencode/skills/owl-dns-synergy"
        cp "$SYNERGY_PKG_DIR/skills/owl-dns-synergy/SKILL.md" "${HOME}/.opencode/skills/owl-dns-synergy/" 2>/dev/null || true
        log_ok "OWL-DNS-Synergy skill installed to ~/.opencode/skills/"
    fi

    # Install agent-browser (headless browser for OWL-AGENT)
    npm install -g agent-browser 2>/dev/null || {
        log_warn "agent-browser npm install failed (non-blocking)"
        log_info "You can install manually: npm install -g agent-browser"
    }
else
    log_warn "Node.js/npx not available — skip skills and agent-browser"
fi

# ═══════════════════════════════════════════════════════════════════
# STEP 10: Create default configuration + systemd template
# ═══════════════════════════════════════════════════════════════════
log_step "10/10 — Creating default configuration and service templates..."

# Write default config.json
cat > "$SYNERGY_HOME/config/config.json" <<'CONFEOF'
{
    "cache_ttl": 300,
    "rate_limit": 1.0,
    "max_retries": 3,
    "countries": ["US", "GB", "DE", "FR", "CA"],
    "use_curl_cffi": true,
    "use_redis": false,
    "redis_url": "redis://localhost:6379",
    "dns_suffix": "_sonos._udp.local",
    "dns_port": 5353,
    "dns_host": "127.0.0.1",
    "openai_model": "gpt-4o",
    "openai_base_url": "https://api.openai.com/v1",
    "prometheus_port": 9090,
    "dns_flood_max_qps": 50,
    "dns_flood_burst": 100
}
CONFEOF
log_ok "Default config written to $SYNERGY_HOME/config/config.json"

# Write systemd service template
cat > "$SYNERGY_HOME/config/owl-dns-synergy.service" <<'SVCEOF'
[Unit]
Description=OWL-DNS-Synergy Dual-Channel Resilient Access Engine
After=network.target

[Service]
Type=simple
User=%i
WorkingDirectory=%h/.owl-dns-synergy
Environment=OWL_DNS_SYNERGY_HOME=%h/.owl-dns-synergy
Environment=OPENAI_API_KEY=your-api-key-here
Environment=LLM_PROXY_KEY=your-encryption-key-here
ExecStart=%h/.owl-dns-synergy/venv/bin/owl-dns-synergy serve
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SVCEOF
log_ok "Systemd service template created at $SYNERGY_HOME/config/owl-dns-synergy.service"

# Write .env.example
cat > "$SYNERGY_HOME/config/.env.example" <<'ENVEOF'
# ─── OWL-DNS-Synergy Environment Variables ──────────────────────
# Required for DNS tunneling:
OPENAI_API_KEY=your-openai-api-key
LLM_PROXY_KEY=your-fernet-encryption-key

# Optional:
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
LLM_DNS_SUFFIX=_sonos._udp.local
PERPLEXITY_API_KEY=your-perplexity-api-key
REDIS_URL=redis://localhost:6379
OWL_DNS_SYNERGY_PROMETHEUS_PORT=9090
ENVEOF
log_ok ".env.example created"

# ─── Create wrapper run.sh ────────────────────────────────────────
cat > "$SYNERGY_HOME/run.sh" <<'RUNEOF'
#!/usr/bin/env bash
# OWL-DNS-Synergy wrapper
set -e
SYNERGY_HOME="${HOME}/.owl-dns-synergy"
VENV_PYTHON="${SYNERGY_HOME}/venv/bin/python"
SYNERGY_CMD="${SYNERGY_HOME}/venv/bin/owl-dns-synergy"

# If owl-dns-synergy is installed as a package, use it directly
if command -v owl-dns-synergy &>/dev/null; then
    exec owl-dns-synergy "$@"
fi

# Otherwise, try running from the repo
REPO_DIR="${HOME}/owl-dns-synergy"
if [[ -d "$REPO_DIR" ]]; then
    cd "$REPO_DIR"
    exec "$VENV_PYTHON" -m owl_dns_synergy.cli "$@"
fi

echo "Error: OWL-DNS-Synergy not installed. Run install.sh first."
exit 1
RUNEOF
chmod +x "$SYNERGY_HOME/run.sh"
log_ok "Wrapper script created at $SYNERGY_HOME/run.sh"

# ═══════════════════════════════════════════════════════════════════
# Final Summary
# ═══════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   OWL-DNS-SYNERGY Installation Complete                    ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Installation Summary:${NC}"
echo -e "  Home directory:    ${GREEN}$SYNERGY_HOME${NC}"
echo -e "  Virtual env:       ${GREEN}$VENV_DIR${NC}"
echo -e "  Config file:       ${GREEN}$SYNERGY_HOME/config/config.json${NC}"
echo -e "  Service template:  ${GREEN}$SYNERGY_HOME/config/owl-dns-synergy.service${NC}"
echo -e "  .env example:      ${GREEN}$SYNERGY_HOME/config/.env.example${NC}"
echo -e "  Run wrapper:       ${GREEN}$SYNERGY_HOME/run.sh${NC}"
echo -e "  llm-dns-proxy:     ${GREEN}$LLM_DNS_DIR${NC}"
echo ""
echo -e "${BOLD}Quick Start:${NC}"
echo -e "  ${YELLOW}1.${NC} Set environment:   ${CYAN}cp $SYNERGY_HOME/config/.env.example $SYNERGY_HOME/.env && edit${NC}"
echo -e "  ${YELLOW}2.${NC} Generate key:       ${CYAN}$SYNERGY_HOME/run.sh generate-key${NC}"
echo -e "  ${YELLOW}3.${NC} Test connectivity:   ${CYAN}$SYNERGY_HOME/run.sh test-connection${NC}"
echo -e "  ${YELLOW}4.${NC} Fetch a URL:         ${CYAN}$SYNERGY_HOME/run.sh fetch https://example.com${NC}"
echo -e "  ${YELLOW}5.${NC} View stats:          ${CYAN}$SYNERGY_HOME/run.sh stats${NC}"
echo -e "  ${YELLOW}6.${NC} Start DNS server:    ${CYAN}cd $LLM_DNS_DIR && python -m llm_dns_proxy.cli server${NC}"
echo ""
echo -e "${BOLD}Add to PATH:${NC}  ${CYAN}echo 'export PATH=\"\$PATH:$SYNERGY_HOME\"' >> ~/.bashrc${NC}"
echo ""
echo -e "${BOLD}Prometheus Metrics:${NC}  ${CYAN}http://localhost:9090/metrics${NC}"
echo -e "${BOLD}Systemd Deploy:${NC}      ${CYAN}sudo cp $SYNERGY_HOME/config/owl-dns-synergy.service /etc/systemd/system/${NC}"
echo ""
