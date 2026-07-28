#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# OWL-DNS-SYNERGY Unified Installer v2.0.0
# Self-contained script that installs the merged OWL-AGENT v4.2 +
# LLM-DNS-Proxy system with OpenRouter key rotation, Prometheus
# metrics, DNS flood protection, and Obsidian integration.
#
# Usage:
#   chmod +x install.sh && ./install.sh
#   ./install.sh --skip-clone     # Skip git clone
#   ./install.sh --with-redis     # Install and configure Redis
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Parse Arguments ────────────────────────────────────────────────
SKIP_CLONE=0
WITH_REDIS=0
SKIP_NPM=0

for arg in "$@"; do
    case $arg in
        --skip-clone)  SKIP_CLONE=1 ;;
        --with-redis)  WITH_REDIS=1 ;;
        --skip-npm)    SKIP_NPM=1 ;;
        --help|-h)
            echo "Usage: $0 [--skip-clone] [--with-redis] [--skip-npm]"
            echo ""
            echo "  --skip-clone   Skip git clone operations"
            echo "  --with-redis   Install and configure Redis"
            echo "  --skip-npm     Skip npm/npx operations"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# ─── Configuration ──────────────────────────────────────────────────
SYNERGY_HOME="${HOME}/.owl-dns-synergy"
REPO_DIR="${HOME}/owl-dns-synergy"
VENV_DIR="${SYNERGY_HOME}/venv"
PYTHON_CMD="${VENV_DIR}/bin/python"
PIP_CMD="${VENV_DIR}/bin/pip"
LLM_DNS_PROXY_REPO="https://github.com/irdbl/llm-dns-proxy.git"
SYNERGY_PKG_DIR=""  # Will be set if local repo exists

# ─── Colors ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Logging helpers ──────────────────────────────────────────────────
log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}${BOLD}[STEP]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}${BOLD}[OK]${NC}    $1"; }
log_phase() { echo -e "${MAGENTA}${BOLD}[PHASE]${NC} $1"; }

# ─── Banner ──────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   OWL-DNS-SYNERGY Unified Installer v2.0.0                ║${NC}"
echo -e "${BOLD}${CYAN}║   HTTP Proxy Evasion + DNS Tunneling + Obsidian           ║${NC}"
echo -e "${BOLD}${CYAN}║   OpenRouter Key Rotation + Prometheus + Flood Protection  ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════════
# PHASE 1: System Requirements Check
# ═══════════════════════════════════════════════════════════════════
log_phase "1 — System Requirements Check"

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

if [[ $MISSING -eq 1 ]]; then
    log_error "Missing critical dependencies. Please install them first."
    exit 1
fi

log_ok "System requirements satisfied"

# ═══════════════════════════════════════════════════════════════════
# PHASE 2: Discover Scraper Skills (npx skills find scraper)
# ═══════════════════════════════════════════════════════════════════
log_phase "2 — Discovering scraper skills via npx skills find scraper"

if [[ $SKIP_NPM -eq 0 ]] && command -v npx &>/dev/null; then
    npx skills find scraper 2>&1 | head -30 || log_warn "skills.sh discovery failed (non-blocking)"
    log_ok "Skills.sh scraper discovery completed"
else
    log_warn "npx not available or --skip-npm — skip skills.sh discovery"
fi

# ═══════════════════════════════════════════════════════════════════
# PHASE 3: Clone Repositories
# ═══════════════════════════════════════════════════════════════════
log_phase "3 — Cloning Repositories"

LLM_DNS_DIR="${SYNERGY_HOME}/repos/llm-dns-proxy"

if [[ $SKIP_CLONE -eq 0 ]]; then
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
else
    log_info "Skipping git clone (--skip-clone)"
fi

# ═══════════════════════════════════════════════════════════════════
# PHASE 4: Create Project Directory Structure
# ═══════════════════════════════════════════════════════════════════
log_phase "4 — Creating OWL-DNS-Synergy home directory structure"

mkdir -p "$SYNERGY_HOME/cache/http"
mkdir -p "$SYNERGY_HOME/config"
mkdir -p "$SYNERGY_HOME/logs"
mkdir -p "$SYNERGY_HOME/repos"
mkdir -p "$SYNERGY_HOME/scripts"

log_ok "Directory structure created at $SYNERGY_HOME"

# ═══════════════════════════════════════════════════════════════════
# PHASE 5: Create Python Virtual Environment
# ═══════════════════════════════════════════════════════════════════
log_phase "5 — Creating Python virtual environment"

if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
    log_ok "Virtual environment created"
else
    log_info "Virtual environment already exists"
fi

# ═══════════════════════════════════════════════════════════════════
# PHASE 6: Install Python Dependencies (merged requirements)
# ═══════════════════════════════════════════════════════════════════
log_phase "6 — Installing merged Python dependencies"
log_info "This may take a few minutes..."

$PIP_CMD install --upgrade pip wheel setuptools 2>/dev/null

# OWL-AGENT core dependencies
log_info "Installing OWL-AGENT dependencies..."
$PIP_CMD install \
    httpx[socks] \
    aiohttp \
    aiofiles \
    proxybroker2 \
    circuitbreaker \
    beautifulsoup4 \
    markdownify \
    prometheus-client \
    structlog \
    2>/dev/null || log_warn "Some OWL-AGENT dependencies failed"

# LLM-DNS-Proxy dependencies
log_info "Installing LLM-DNS-Proxy dependencies..."
$PIP_CMD install \
    dnslib \
    openai \
    cryptography \
    click \
    2>/dev/null || log_warn "Some LLM-DNS-Proxy dependencies failed"

# Optional: Redis support
if [[ $WITH_REDIS -eq 1 ]]; then
    log_info "Installing Redis support..."
    $PIP_CMD install redis 2>/dev/null || log_warn "Redis package skipped"
else
    $PIP_CMD install redis 2>/dev/null || true
fi

# Optional: curl_cffi for Chrome fingerprinting
$PIP_CMD install curl_cffi 2>/dev/null || log_warn "curl_cffi skipped (optional — requires compilation)"

# Optional: resilient-httpx for advanced retry logic
$PIP_CMD install resilient-httpx 2>/dev/null || log_warn "resilient-httpx skipped (optional)"

log_ok "Core dependencies installed"

# ═══════════════════════════════════════════════════════════════════
# PHASE 7: Install owl-dns-synergy package
# ═══════════════════════════════════════════════════════════════════
log_phase "7 — Installing OWL-DNS-Synergy package"

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
# PHASE 8: Install LLM-DNS-Proxy standalone
# ═══════════════════════════════════════════════════════════════════
log_phase "8 — Installing LLM-DNS-Proxy standalone"

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
# PHASE 9: Install Obsidian skills + agent-browser
# ═══════════════════════════════════════════════════════════════════
log_phase "9 — Installing Obsidian skills and agent-browser"

if [[ $SKIP_NPM -eq 0 ]] && command -v npx &>/dev/null; then
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
    log_warn "Node.js/npx not available or --skip-npm — skip skills and agent-browser"
fi

# ═══════════════════════════════════════════════════════════════════
# PHASE 10: Create Configuration Files
# ═══════════════════════════════════════════════════════════════════
log_phase "10 — Creating configuration files"

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
    "openai_model": "openai/gpt-4o",
    "openai_base_url": "https://openrouter.ai/api/v1",
    "prometheus_port": 9090,
    "dns_flood_max_qps": 50,
    "dns_flood_burst": 100
}
CONFEOF
log_ok "Default config written to $SYNERGY_HOME/config/config.json"

# Write .env file (only if not already present)
if [[ ! -f "$SYNERGY_HOME/.env" ]]; then
    cat > "$SYNERGY_HOME/.env" <<'ENVEOF'
# ─── OWL-DNS-Synergy Environment Variables ──────────────────────
# OpenRouter API Configuration (OpenAI-compatible endpoint)
OPENAI_API_KEY=your-openrouter-api-key-here
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=openai/gpt-4o

# Backup OpenRouter Keys (for key rotation / failover)
# OPENROUTER_KEY_1=sk-or-v1-backup-key-1
# OPENROUTER_KEY_2=sk-or-v1-backup-key-2

# DNS Proxy Encryption Key (Fernet AES-128)
# Generate with: python -m owl_dns_synergy.cli generate-key
LLM_PROXY_KEY=your-fernet-encryption-key-here

# DNS Suffix for Traffic Camouflage
LLM_DNS_SUFFIX=_sonos._udp.local

# Server Configuration
DNS_SERVER_HOST=127.0.0.1
DNS_SERVER_PORT=5353

# Redis (for SmartChannelRouter domain preference learning)
REDIS_URL=redis://localhost:6379

# Prometheus Metrics
OWL_DNS_SYNERGY_PROMETHEUS_PORT=9090

# DNS Flood Protection
DNS_FLOOD_MAX_QPS=50
DNS_FLOOD_BURST=100
ENVEOF
    log_ok ".env file created at $SYNERGY_HOME/.env"
    log_warn "IMPORTANT: Edit $SYNERGY_HOME/.env with your actual API keys!"
else
    log_info ".env file already exists — preserving existing configuration"
fi

# Write systemd service template
cat > "$SYNERGY_HOME/config/owl-dns-synergy.service" <<'SVCEOF'
[Unit]
Description=OWL-DNS-Synergy Dual-Channel Resilient Access Engine
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=%i
WorkingDirectory=%h/.owl-dns-synergy
Environment=OWL_DNS_SYNERGY_HOME=%h/.owl-dns-synergy
EnvironmentFile=%h/.owl-dns-synergy/.env
ExecStart=%h/.owl-dns-synergy/venv/bin/owl-dns-synergy serve
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=%h/.owl-dns-synergy
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SVCEOF
log_ok "Systemd service template created at $SYNERGY_HOME/config/owl-dns-synergy.service"

# ─── Create DNS Server Launch Script ────────────────────────────────
cat > "$SYNERGY_HOME/start-dns-server.sh" <<'RUNEOF'
#!/usr/bin/env bash
# OWL-DNS-Synergy DNS Server Launcher
# Loads environment and starts the DNS tunneling server

set -e

SYNERGY_HOME="${HOME}/.owl-dns-synergy"
ENV_FILE="${SYNERGY_HOME}/.env"

# Load environment
if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "Error: $ENV_FILE not found. Run install.sh first."
    exit 1
fi

# Start DNS server
cd "${SYNERGY_HOME}/repos/llm-dns-proxy"
exec "${SYNERGY_HOME}/venv/bin/python" -m llm_dns_proxy.cli server \
    --host "${DNS_SERVER_HOST:-127.0.0.1}" \
    --port "${DNS_SERVER_PORT:-5353}"
RUNEOF
chmod +x "$SYNERGY_HOME/start-dns-server.sh"
log_ok "DNS server launcher created at $SYNERGY_HOME/start-dns-server.sh"

# ─── Create Unified Serve Script ────────────────────────────────────
cat > "$SYNERGY_HOME/run.sh" <<'RUNEOF'
#!/usr/bin/env bash
# OWL-DNS-Synergy Unified Runner
set -e

SYNERGY_HOME="${HOME}/.owl-dns-synergy"
VENV_PYTHON="${SYNERGY_HOME}/venv/bin/python"
SYNERGY_CMD="${SYNERGY_HOME}/venv/bin/owl-dns-synergy"

# Load environment
if [[ -f "${SYNERGY_HOME}/.env" ]]; then
    set -a
    source "${SYNERGY_HOME}/.env"
    set +a
fi

# If owl-dns-synergy is installed as a package, use it directly
if [[ -x "$SYNERGY_CMD" ]]; then
    exec "$SYNERGY_CMD" "$@"
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
log_ok "Unified runner created at $SYNERGY_HOME/run.sh"

# ─── Create Prometheus Config ────────────────────────────────────────
mkdir -p "$SYNERGY_HOME/config/prometheus"
cat > "$SYNERGY_HOME/config/prometheus/prometheus.yml" <<'PROMEOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'owl-dns-synergy'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: /metrics
    scrape_interval: 10s
PROMEOF
log_ok "Prometheus config created at $SYNERGY_HOME/config/prometheus/prometheus.yml"

# ═══════════════════════════════════════════════════════════════════
# PHASE 11: Redis Setup (optional)
# ═══════════════════════════════════════════════════════════════════
if [[ $WITH_REDIS -eq 1 ]]; then
    log_phase "11 — Setting up Redis"

    if command -v redis-server &>/dev/null; then
        log_ok "Redis server already installed"
    else
        log_info "Installing Redis..."
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -qq && sudo apt-get install -y -qq redis-server 2>/dev/null || \
                log_warn "Redis installation failed via apt-get"
        elif command -v yum &>/dev/null; then
            sudo yum install -y redis 2>/dev/null || log_warn "Redis installation failed via yum"
        else
            log_warn "Cannot auto-install Redis — please install manually"
        fi
    fi

    # Start Redis if not running
    if command -v redis-cli &>/dev/null; then
        if redis-cli ping &>/dev/null; then
            log_ok "Redis server is running"
        else
            redis-server --daemonize yes 2>/dev/null || \
                log_warn "Could not start Redis — start manually: redis-server"
        fi
    fi

    # Update config to use Redis
    if command -v python3 &>/dev/null; then
        python3 -c "
import json
config_file = '$SYNERGY_HOME/config/config.json'
with open(config_file) as f:
    config = json.load(f)
config['use_redis'] = True
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)
print('Config updated: use_redis=True')
"
    fi
else
    log_info "Skipping Redis setup (use --with-redis to enable)"
fi

# ═══════════════════════════════════════════════════════════════════
# Final Summary
# ═══════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   OWL-DNS-SYNERGY Installation Complete (v2.0.0)          ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Installation Summary:${NC}"
echo -e "  Home directory:    ${GREEN}$SYNERGY_HOME${NC}"
echo -e "  Virtual env:       ${GREEN}$VENV_DIR${NC}"
echo -e "  Config file:       ${GREEN}$SYNERGY_HOME/config/config.json${NC}"
echo -e "  Environment:       ${GREEN}$SYNERGY_HOME/.env${NC}"
echo -e "  Service template:  ${GREEN}$SYNERGY_HOME/config/owl-dns-synergy.service${NC}"
echo -e "  Prometheus config: ${GREEN}$SYNERGY_HOME/config/prometheus/prometheus.yml${NC}"
echo -e "  DNS launcher:      ${GREEN}$SYNERGY_HOME/start-dns-server.sh${NC}"
echo -e "  Unified runner:    ${GREEN}$SYNERGY_HOME/run.sh${NC}"
echo -e "  llm-dns-proxy:     ${GREEN}$LLM_DNS_DIR${NC}"
echo ""
echo -e "${BOLD}${YELLOW}Required Next Steps:${NC}"
echo -e "  ${YELLOW}1.${NC} Edit API keys:     ${CYAN}nano $SYNERGY_HOME/.env${NC}"
echo -e "  ${YELLOW}2.${NC} Generate key:       ${CYAN}$SYNERGY_HOME/run.sh generate-key${NC}"
echo -e "  ${YELLOW}3.${NC} Test connectivity:   ${CYAN}$SYNERGY_HOME/run.sh test-connection${NC}"
echo ""
echo -e "${BOLD}Running the System:${NC}"
echo -e "  ${YELLOW}• Start DNS server:${NC}    ${CYAN}$SYNERGY_HOME/start-dns-server.sh${NC}"
echo -e "  ${YELLOW}• Start unified server:${NC} ${CYAN}$SYNERGY_HOME/run.sh serve${NC}"
echo -e "  ${YELLOW}• Fetch a URL:${NC}          ${CYAN}$SYNERGY_HOME/run.sh fetch https://example.com${NC}"
echo -e "  ${YELLOW}• View stats:${NC}           ${CYAN}$SYNERGY_HOME/run.sh stats${NC}"
echo -e "  ${YELLOW}• Key rotation status:${NC}  ${CYAN}$SYNERGY_HOME/run.sh key-status${NC}"
echo ""
echo -e "${BOLD}Production Deployment:${NC}"
echo -e "  ${CYAN}sudo cp $SYNERGY_HOME/config/owl-dns-synergy.service /etc/systemd/system/${NC}"
echo -e "  ${CYAN}sudo systemctl daemon-reload${NC}"
echo -e "  ${CYAN}sudo systemctl enable --now owl-dns-synergy@$(whoami)${NC}"
echo ""
echo -e "${BOLD}Prometheus Metrics:${NC}  ${CYAN}http://localhost:9090/metrics${NC}"
echo -e "${BOLD}DNS Tunnel Port:${NC}     ${CYAN}127.0.0.1:5353 (UDP)${NC}"
echo ""
