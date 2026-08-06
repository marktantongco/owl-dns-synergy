#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
# OWL-DNS-SYNERGY Unified Installer v4.0.0
#
# Self-contained installer for the merged OWL-AGENT v4.2 +
# LLM-DNS-Proxy system with AutoClaw proxy management, Prometheus
# metrics, DNS flood protection, Fernet encryption, and full
# production deployment support.
#
# Usage:
#   ./install.sh              # Full installation
#   ./install.sh --uninstall  # Remove all installed files
#
# ═════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────────────────
SYNERGY_HOME="${HOME}/.owl-dns-synergy"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SYNERGY_HOME}/venv"
PYTHON_CMD="${VENV_DIR}/bin/python"
PIP_CMD="${VENV_DIR}/bin/pip"
INSTALL_LOG="${SYNERGY_HOME}/logs/install.log"
LLM_DNS_PROXY_REPO="https://github.com/irdbl/llm-dns-proxy.git"
INSTALL_VERSION="4.0.0"
PRODUCT_VERSION="1.0.0"

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ─── Logging helpers ────────────────────────────────────────────────────────
log_info()    { echo -e "${GREEN}[INFO]${NC}    $1" | tee -a "$INSTALL_LOG" 2>/dev/null || echo -e "${GREEN}[INFO]${NC}    $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}    $1" | tee -a "$INSTALL_LOG" 2>/dev/null || echo -e "${YELLOW}[WARN]${NC}    $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC}   $1" | tee -a "$INSTALL_LOG" 2>/dev/null || echo -e "${RED}[ERROR]${NC}   $1"; }
log_step()    { echo -e "${CYAN}${BOLD}[STEP]${NC}    $1" | tee -a "$INSTALL_LOG" 2>/dev/null || echo -e "${CYAN}${BOLD}[STEP]${NC}    $1"; }
log_ok()      { echo -e "${GREEN}${BOLD}[OK]${NC}      $1" | tee -a "$INSTALL_LOG" 2>/dev/null || echo -e "${GREEN}${BOLD}[OK]${NC}      $1"; }
log_phase()   { echo ""; echo -e "${BOLD}${BLUE}[PHASE $1]${NC}  $2" | tee -a "$INSTALL_LOG" 2>/dev/null || echo -e "${BOLD}${BLUE}[PHASE $1]${NC}  $2"; echo ""; }
log_progress(){ echo -e "${DIM}        $1${NC}"; }

# ─── Error handler ──────────────────────────────────────────────────────────
cleanup_on_error() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo ""
        log_error "Installation failed with exit code $exit_code"
        log_error "Check the install log at: $INSTALL_LOG"
        log_info "Partial installation may exist at: $SYNERGY_HOME"
        log_info "To clean up and retry: $0 --uninstall && $0"
    fi
}
trap cleanup_on_error ERR

# ─── Helper: version comparison ─────────────────────────────────────────────
version_gte() {
    # Returns 0 if $1 >= $2 (semantic version, first 2 parts)
    local v1="$1" v2="$2"
    local v1_major v1_minor v2_major v2_minor
    IFS='.' read -r v1_major v1_minor _ <<< "$v1"
    IFS='.' read -r v2_major v2_minor _ <<< "$v2"
    if [[ $v1_major -gt $v2_major ]]; then return 0; fi
    if [[ $v1_major -eq $v2_major ]] && [[ $v1_minor -ge $v2_minor ]]; then return 0; fi
    return 1
}

# ─── Helper: check command exists ───────────────────────────────────────────
require_cmd() {
    local cmd="$1" label="${2:-$1}"
    if ! command -v "$cmd" &>/dev/null; then
        log_error "$label is required but not installed."
        return 1
    fi
    return 0
}

# ═════════════════════════════════════════════════════════════════════════════
# UNINSTALL
# ═════════════════════════════════════════════════════════════════════════════
if [[ "${1:-}" == "--uninstall" ]]; then
    echo ""
    echo -e "${BOLD}${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${RED}║   OWL-DNS-SYNERGY Uninstaller                              ║${NC}"
    echo -e "${BOLD}${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [[ ! -d "$SYNERGY_HOME" ]]; then
        log_warn "Installation directory $SYNERGY_HOME does not exist. Nothing to uninstall."
        exit 0
    fi

    log_info "Removing OWL-DNS-Synergy installation at: $SYNERGY_HOME"

    # Deactivate venv if active
    if [[ -n "${VIRTUAL_ENV:-}" ]] && [[ "$VIRTUAL_ENV" == "$VENV_DIR" ]]; then
        log_info "Deactivating virtual environment..."
        deactivate 2>/dev/null || true
    fi

    # Stop systemd services if running
    if systemctl is-active --quiet owl-dns-synergy 2>/dev/null; then
        log_info "Stopping owl-dns-synergy service..."
        sudo systemctl stop owl-dns-synergy 2>/dev/null || true
        sudo systemctl disable owl-dns-synergy 2>/dev/null || true
    fi
    if systemctl is-active --quiet autoclaw-proxy 2>/dev/null; then
        log_info "Stopping autoclaw-proxy service..."
        sudo systemctl stop autoclaw-proxy 2>/dev/null || true
        sudo systemctl disable autoclaw-proxy 2>/dev/null || true
    fi

    # Remove systemd unit files
    sudo rm -f /etc/systemd/system/owl-dns-synergy.service 2>/dev/null || true
    sudo rm -f /etc/systemd/system/autoclaw-proxy.service 2>/dev/null || true
    sudo systemctl daemon-reload 2>/dev/null || true

    # Remove installation directory
    log_info "Removing directory: $SYNERGY_HOME"
    rm -rf "$SYNERGY_HOME"

    # Remove system config directory if it exists
    if [[ -d "/etc/owl-dns-synergy" ]]; then
        log_info "Removing system config: /etc/owl-dns-synergy"
        sudo rm -rf /etc/owl-dns-synergy 2>/dev/null || true
    fi

    echo ""
    log_ok "OWL-DNS-Synergy has been completely uninstalled."
    log_info "You may also want to remove these manually:"
    log_info "  - PATH entry in ~/.bashrc (if added)"
    log_info "  - Nginx config in /etc/nginx/sites-available/ (if configured)"
    log_info "  - Prometheus/scrape configs (if configured)"
    echo ""
    exit 0
fi

# ═════════════════════════════════════════════════════════════════════════════
# BANNER
# ═════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                                                                      ║${NC}"
echo -e "${BOLD}${CYAN}║   OWL-DNS-SYNERGY v${PRODUCT_VERSION}  Installer v${INSTALL_VERSION}                         ║${NC}"
echo -e "${BOLD}${CYAN}║                                                                      ║${NC}"
echo -e "${BOLD}${CYAN}║   Unified Dual-Channel Resilient Access Engine                      ║${NC}"
echo -e "${BOLD}${CYAN}║   HTTP Proxy Evasion + DNS Tunneling + AutoClaw Management          ║${NC}"
echo -e "${BOLD}${CYAN}║                                                                      ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${DIM}Repository:  $REPO_DIR${NC}"
echo -e "  ${DIM}Target:      $SYNERGY_HOME${NC}"
echo -e "  ${DIM}Log:         $INSTALL_LOG${NC}"
echo ""

# Ensure log directory exists for logging
mkdir -p "$SYNERGY_HOME/logs" 2>/dev/null || true

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 1: Check Prerequisites
# ═════════════════════════════════════════════════════════════════════════════
log_phase "1/12" "Checking Prerequisites"

MISSING=0

# Python 3.10+
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_VER_FULL=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
    if version_gte "$PY_VER" "3.10"; then
        log_ok "Python $PY_VER_FULL detected"
    else
        log_error "Python 3.10+ required (found $PY_VER_FULL)"
        MISSING=1
    fi
else
    log_error "Python3 is not installed"
    MISSING=1
fi

# pip
if python3 -m pip --version &>/dev/null; then
    PIP_VER=$(python3 -m pip --version 2>/dev/null | awk '{print $2}')
    log_ok "pip $PIP_VER detected"
else
    log_error "pip is required but not found"
    MISSING=1
fi

# git
if command -v git &>/dev/null; then
    GIT_VER=$(git --version 2>/dev/null | awk '{print $3}')
    log_ok "git $GIT_VER detected"
else
    log_warn "git not found -- repository cloning will be skipped"
fi

# Go 1.21+ (optional, for some auxiliary tools)
if command -v go &>/dev/null; then
    GO_VER=$(go version 2>/dev/null | awk '{print $3}' | sed 's/go//')
    if version_gte "$GO_VER" "1.21"; then
        log_ok "Go $GO_VER detected"
    else
        log_warn "Go 1.21+ recommended (found $GO_VER)"
    fi
else
    log_warn "Go not found -- optional for auxiliary tooling"
fi

# Node.js 18+ (optional, for agent-browser and skills)
if command -v node &>/dev/null; then
    NODE_VER=$(node --version 2>/dev/null | sed 's/v//')
    if version_gte "$NODE_VER" "18"; then
        log_ok "Node.js $NODE_VER detected"
    else
        log_warn "Node.js 18+ recommended (found $NODE_VER)"
    fi
else
    log_warn "Node.js not found -- agent-browser and npx skills will be skipped"
fi

# Rust / cargo (optional)
if command -v cargo &>/dev/null; then
    CARGO_VER=$(cargo --version 2>/dev/null | awk '{print $2}')
    log_ok "cargo $CARGO_VER detected (Rust toolchain available)"
else
    log_warn "Rust/cargo not found -- optional for agent-browser native build"
fi

if [[ $MISSING -eq 1 ]]; then
    log_error "Critical prerequisites missing. Please install them before continuing."
    echo ""
    log_info "Install hints:"
    log_info "  Python 3.10+:  https://www.python.org/downloads/"
    log_info "  pip:           python3 -m ensurepip --upgrade"
    log_info "  git:           apt install git / brew install git"
    log_info "  Go 1.21+:      https://go.dev/dl/"
    log_info "  Node.js 18+:   https://nodejs.org/ or nvm install 18"
    log_info "  Rust/cargo:    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

log_ok "All critical prerequisites satisfied"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 2: Create Directory Structure
# ═════════════════════════════════════════════════════════════════════════════
log_phase "2/12" "Creating Directory Structure"

mkdir -p "$SYNERGY_HOME/config"
mkdir -p "$SYNERGY_HOME/cache/http"
mkdir -p "$SYNERGY_HOME/cache/dns"
mkdir -p "$SYNERGY_HOME/logs"
mkdir -p "$SYNERGY_HOME/venv"
mkdir -p "$SYNERGY_HOME/repos"
mkdir -p "$SYNERGY_HOME/deploy"

log_progress "config/      -- configuration files (config.json, .env, tokens)"
log_progress "cache/       -- HTTP and DNS response caches"
log_progress "logs/        -- application and install logs"
log_progress "venv/        -- Python virtual environment"
log_progress "repos/       -- cloned auxiliary repositories"
log_progress "deploy/      -- systemd unit files and deployment artifacts"

log_ok "Directory structure created at $SYNERGY_HOME"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 3: Create Python Virtual Environment & Install Core Dependencies
# ═════════════════════════════════════════════════════════════════════════════
log_phase "3/12" "Creating Python Virtual Environment & Installing Core Dependencies"

if [[ ! -d "$VENV_DIR/bin" ]]; then
    log_info "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    log_ok "Virtual environment created"
else
    log_info "Virtual environment already exists at $VENV_DIR"
    log_info "Upgrading pip and build tools..."
fi

$PIP_CMD install --upgrade pip wheel setuptools 2>&1 | tail -1 | xargs -I{} log_progress "pip upgrade: {}"

# Install owl-dns-synergy package (editable, from local repo)
SYNERGY_PKG_DIR=""
if [[ -f "$REPO_DIR/pyproject.toml" ]]; then
    SYNERGY_PKG_DIR="$REPO_DIR"
    log_info "Installing owl-dns-synergy from local repo: $SYNERGY_PKG_DIR"
    cd "$SYNERGY_PKG_DIR"
    $PIP_CMD install -e . 2>&1 | tail -3 | while read -r line; do log_progress "$line"; done
    log_ok "owl-dns-synergy package installed (editable)"
else
    log_warn "pyproject.toml not found at $REPO_DIR"
    log_info "Falling back to pip install owl-dns-synergy..."
    $PIP_CMD install owl-dns-synergy 2>/dev/null || {
        log_warn "Package not available on PyPI -- manual install required"
        log_info "Install manually: cd /path/to/owl-dns-synergy && pip install -e ."
    }
fi

# Install all core dependencies explicitly (ensures completeness)
log_info "Installing core dependencies..."

# Core (always required)
$PIP_CMD install \
    httpx[socks]>=0.24 \
    aiohttp>=3.8 \
    aiofiles>=23.1 \
    circuitbreaker>=2.0 \
    beautifulsoup4>=4.12 \
    markdownify>=0.11 \
    dnslib>=0.9.24 \
    openai>=1.0.0 \
    click>=8.0.0 \
    2>&1 | tail -1 | xargs -I{} log_progress "core: {}" || log_warn "Some core dependencies failed"

# Optional: prometheus-client (metrics export)
$PIP_CMD install "prometheus-client>=0.17" 2>/dev/null && log_ok "prometheus-client installed" || log_warn "prometheus-client skipped (optional)"

# Optional: cryptography (Fernet encryption, token encryption)
$PIP_CMD install "cryptography>=41.0.0" 2>/dev/null && log_ok "cryptography installed" || log_warn "cryptography skipped (optional)"

# Optional: redis (distributed caching)
$PIP_CMD install "redis>=5.0" 2>/dev/null && log_ok "redis installed" || log_warn "redis skipped (optional)"

# Optional: curl_cffi (Chrome TLS fingerprinting)
$PIP_CMD install "curl_cffi>=0.5" 2>/dev/null && log_ok "curl_cffi installed" || log_warn "curl_cffi skipped (optional -- requires compilation)"

log_ok "Core Python dependencies installed"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 4: Install AutoClaw Dependencies
# ═════════════════════════════════════════════════════════════════════════════
log_phase "4/12" "Installing AutoClaw Proxy Manager Dependencies"

log_info "Installing AutoClaw runtime dependencies..."

$PIP_CMD install \
    flask>=3.0 \
    gunicorn>=21.2 \
    eventlet>=0.33 \
    cryptography>=41.0.0 \
    requests>=2.31 \
    aiohttp>=3.8 \
    2>&1 | tail -1 | xargs -I{} log_progress "autoclaw: {}" || log_warn "Some AutoClaw dependencies failed"

log_ok "AutoClaw dependencies installed"
log_info "AutoClaw components: Flask web server, Gunicorn WSGI, eventlet async workers"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 5: Generate Fernet Encryption Key (LLM_PROXY_KEY)
# ═════════════════════════════════════════════════════════════════════════════
log_phase "5/12" "Generating Fernet Encryption Key for DNS Tunneling (LLM_PROXY_KEY)"

if $PYTHON_CMD -c "from cryptography.fernet import Fernet" 2>/dev/null; then
    LLM_PROXY_KEY=$($PYTHON_CMD -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    log_ok "LLM_PROXY_KEY generated (Fernet 256-bit)"
    log_progress "Key length: ${#LLM_PROXY_KEY} characters (url-safe base64)"
else
    log_warn "cryptography package not available -- generating key via openssl fallback"
    LLM_PROXY_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
    log_ok "LLM_PROXY_KEY generated via openssl fallback"
fi

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 6: Generate Token Encryption Key (AUTOCLAW_TOKEN_KEY)
# ═════════════════════════════════════════════════════════════════════════════
log_phase "6/12" "Generating Token Encryption Key (AUTOCLAW_TOKEN_KEY)"

if $PYTHON_CMD -c "from cryptography.fernet import Fernet" 2>/dev/null; then
    AUTOCLAW_TOKEN_KEY=$($PYTHON_CMD -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    log_ok "AUTOCLAW_TOKEN_KEY generated (Fernet 256-bit)"
    log_progress "Key length: ${#AUTOCLAW_TOKEN_KEY} characters (url-safe base64)"
else
    log_warn "cryptography package not available -- generating key via openssl fallback"
    AUTOCLAW_TOKEN_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
    log_ok "AUTOCLAW_TOKEN_KEY generated via openssl fallback"
fi

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 7: Create config.json with Defaults
# ═════════════════════════════════════════════════════════════════════════════
log_phase "7/12" "Creating Default Configuration (config.json)"

CONFIG_FILE="$SYNERGY_HOME/config/config.json"

if [[ -f "$CONFIG_FILE" ]]; then
    log_warn "config.json already exists -- backing up to config.json.bak"
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak"
fi

cat > "$CONFIG_FILE" <<'CONFEOF'
{
    "cache_ttl": 300,
    "cache_max": 1000,
    "rate_limit": 1.0,
    "max_retries": 3,
    "countries": ["US", "GB", "DE", "FR", "CA"],
    "use_curl_cffi": true,
    "use_redis": false,
    "redis_url": "redis://localhost:6379",
    "dns_suffix": "_sonos._udp.local",
    "dns_port": 5353,
    "dns_host": "127.0.0.1",
    "dns_flood_max_qps": 50,
    "dns_flood_burst": 100,
    "openai_model": "gpt-4o",
    "openai_base_url": "https://api.openai.com/v1",
    "prometheus_port": 9090,
    "circuit_breaker_failure_threshold": 5,
    "circuit_breaker_recovery_timeout": 30,
    "autoclaw": {
        "port": 31000,
        "host": "127.0.0.1",
        "workers": 3,
        "worker_class": "eventlet",
        "max_requests": 1000,
        "max_requests_jitter": 50,
        "graceful_timeout": 30,
        "token_refresh_interval": 3600,
        "enable_encryption": true
    }
}
CONFEOF

log_ok "config.json written to $CONFIG_FILE"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 8: Create .env File with All Environment Variables
# ═════════════════════════════════════════════════════════════════════════════
log_phase "8/12" "Creating .env File with Environment Variables"

ENV_FILE="$SYNERGY_HOME/config/.env"

if [[ -f "$ENV_FILE" ]]; then
    log_warn ".env already exists -- backing up to .env.bak"
    cp "$ENV_FILE" "$ENV_FILE.bak"
fi

cat > "$ENV_FILE" <<ENVEOF
# ═════════════════════════════════════════════════════════════════════════════
# OWL-DNS-SYNERGY + AutoClaw Environment Variables
# Generated by install.sh v${INSTALL_VERSION} on $(date -Iseconds)
# ═════════════════════════════════════════════════════════════════════════════

# ─── OWL-DNS-Synergy: Crypto ────────────────────────────────────────────────
LLM_PROXY_KEY=${LLM_PROXY_KEY}

# ─── OWL-DNS-Synergy: Router ───────────────────────────────────────────────
SYNERGY_LOG_LEVEL=info
SYNERGY_CACHE_TTL=300
SYNERGY_CACHE_MAX=1000

# ─── OWL-DNS-Synergy: Prometheus ───────────────────────────────────────────
SYNERGY_METRICS_PORT=9090

# ─── OWL-DNS-Synergy: Redis (optional) ─────────────────────────────────────
SYNERGY_REDIS_URL=redis://localhost:6379

# ─── OWL-DNS-Synergy: OpenAI / LLM ─────────────────────────────────────────
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# ─── OWL-DNS-Synergy: DNS Tunneling ────────────────────────────────────────
LLM_DNS_SUFFIX=_sonos._udp.local
LLM_DNS_HOST=127.0.0.1
LLM_DNS_PORT=5353
LLM_DNS_FLOOD_MAX_QPS=50
LLM_DNS_FLOOD_BURST=100

# ─── OWL-DNS-Synergy: Circuit Breaker ──────────────────────────────────────
SYNERGY_CB_FAILURE_THRESHOLD=5
SYNERGY_CB_RECOVERY_TIMEOUT=30

# ─── AutoClaw: Token Encryption ────────────────────────────────────────────
AUTOCLAW_TOKEN_KEY=${AUTOCLAW_TOKEN_KEY}

# ─── AutoClaw: Server ──────────────────────────────────────────────────────
AUTOCLAW_HOST=127.0.0.1
AUTOCLAW_PORT=31000
AUTOCLAW_WORKERS=3
AUTOCLAW_WORKER_CLASS=eventlet
AUTOCLAW_MAX_REQUESTS=1000
AUTOCLAW_GRACEFUL_TIMEOUT=30

# ─── AutoClaw: Token Management ────────────────────────────────────────────
AUTOCLAW_TOKEN_REFRESH_INTERVAL=3600
AUTOCLAW_ENABLE_ENCRYPTION=true
AUTOCLAW_PROXY_FILE=\${HOME}/.owl-dns-synergy/config/proxies.txt
AUTOCLAW_ACCOUNTS_FILE=\${HOME}/.owl-dns-synergy/config/accounts.txt
ENVEOF

chmod 600 "$ENV_FILE"
log_ok ".env written to $ENV_FILE (mode 600)"
log_warn "REMEMBER: Set OPENAI_API_KEY in .env before starting services"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 9: Create Example Token Files
# ═════════════════════════════════════════════════════════════════════════════
log_phase "9/12" "Creating Example Token Files"

PROXIES_EXAMPLE="$SYNERGY_HOME/config/proxies.txt.example"
ACCOUNTS_EXAMPLE="$SYNERGY_HOME/config/accounts.txt.example"

cat > "$PROXIES_EXAMPLE" <<'PROXIESEOF'
# ═════════════════════════════════════════════════════════════════════════════
# OWL-DNS-Synergy Proxy List
# Format:  protocol://host:port  or  protocol://user:pass@host:port
# One proxy per line. Lines starting with # are comments.
# ═════════════════════════════════════════════════════════════════════════════
#
# Examples:
# http://proxy1.example.com:8080
# socks5://user:password@proxy2.example.com:1080
# https://proxy3.example.com:443
#
# Copy this file to proxies.txt and add your proxies:
# cp proxies.txt.example proxies.txt
# chmod 600 proxies.txt
PROXIESEOF

chmod 600 "$PROXIES_EXAMPLE"
log_ok "proxies.txt.example created (mode 600)"

cat > "$ACCOUNTS_EXAMPLE" <<'ACCOUNTSEOF'
# ═════════════════════════════════════════════════════════════════════════════
# AutoClaw Account Credentials
# Format:  provider|account_id|refresh_token|access_token|expires_at
# Tokens will be encrypted with AUTOCLAW_TOKEN_KEY if encryption is enabled.
# ═════════════════════════════════════════════════════════════════════════════
#
# Examples:
# openai|acct_12345|rtok_xxxxxxxx|atok_xxxxxxxx|1700000000
# anthropic|acct_67890|rtok_yyyyyyyy|atok_yyyyyyyy|1700000000
#
# Copy this file to accounts.txt and add your accounts:
# cp accounts.txt.example accounts.txt
# chmod 600 accounts.txt
ACCOUNTSEOF

chmod 600 "$ACCOUNTS_EXAMPLE"
log_ok "accounts.txt.example created (mode 600)"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 10: Create Systemd Unit Files
# ═════════════════════════════════════════════════════════════════════════════
log_phase "10/12" "Creating Systemd Unit Files"

DEPLOY_DIR="$SYNERGY_HOME/deploy"

# owl-dns-synergy.service
cat > "$DEPLOY_DIR/owl-dns-synergy.service" <<'SVCEOF'
[Unit]
Description=OWL-DNS-Synergy Smart Channel Router v3
Documentation=https://github.com/owl-dns-synergy
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
User=owl-dns
Group=owl-dns
WorkingDirectory=/opt/owl-dns-synergy
ExecStart=/opt/owl-dns-synergy/venv/bin/python -m owl_dns_synergy.server
EnvironmentFile=-/etc/owl-dns-synergy/env
Environment=PYTHONUNBUFFERED=1
Environment=SYNERGY_LOG_LEVEL=info

# Resource Limits
MemoryMax=1G
MemoryHigh=768M
CPUQuota=200%
LimitNOFILE=65536

# Restart Policy
Restart=on-failure
RestartSec=5
WatchdogSec=120

# Security Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/log/owl-dns-synergy /var/cache/owl-dns-synergy
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE

StandardOutput=journal
StandardError=journal
SyslogIdentifier=owl-dns-synergy

[Install]
WantedBy=multi-user.target
SVCEOF

log_ok "owl-dns-synergy.service created"

# autoclaw-proxy.service
cat > "$DEPLOY_DIR/autoclaw-proxy.service" <<'AUTOSVCEOF'
[Unit]
Description=AutoClaw Proxy Manager (Gunicorn + eventlet)
Documentation=https://github.com/owl-dns-synergy
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
User=owl-dns
Group=owl-dns
WorkingDirectory=/opt/owl-dns-synergy
ExecStart=/opt/owl-dns-synergy/venv/bin/gunicorn \
    --bind 127.0.0.1:31000 \
    --workers 3 \
    --worker-class eventlet \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --graceful-timeout 30 \
    --timeout 120 \
    --access-logfile /var/log/owl-dns-synergy/autoclaw-access.log \
    --error-logfile /var/log/owl-dns-synergy/autoclaw-error.log \
    autoclaw.app:create_app()
EnvironmentFile=-/etc/owl-dns-synergy/env
Environment=PYTHONUNBUFFERED=1

# Resource Limits
MemoryMax=512M
MemoryHigh=384M
CPUQuota=100%
LimitNOFILE=32768

# Restart Policy
Restart=on-failure
RestartSec=5
WatchdogSec=90

# Security Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/log/owl-dns-synergy
CapabilityBoundingSet=

StandardOutput=journal
StandardError=journal
SyslogIdentifier=autoclaw-proxy

[Install]
WantedBy=multi-user.target
AUTOSVCEOF

log_ok "autoclaw-proxy.service created"

# Copy from repo deploy/ if available
if [[ -d "$REPO_DIR/deploy" ]]; then
    log_info "Copying deploy/ templates from repository..."
    cp "$REPO_DIR/deploy/"* "$DEPLOY_DIR/" 2>/dev/null || true
    log_ok "Repository deploy/ templates copied"
fi

log_info "To install systemd services:"
log_info "  sudo cp $DEPLOY_DIR/owl-dns-synergy.service /etc/systemd/system/"
log_info "  sudo cp $DEPLOY_DIR/autoclaw-proxy.service /etc/systemd/system/"
log_info "  sudo systemctl daemon-reload"
log_info "  sudo systemctl enable --now owl-dns-synergy"
log_info "  sudo systemctl enable --now autoclaw-proxy"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 11: Quick Verification
# ═════════════════════════════════════════════════════════════════════════════
log_phase "11/12" "Running Quick Verification"

VERIFY_PASS=0
VERIFY_FAIL=0

# Check virtual environment
if [[ -f "$PYTHON_CMD" ]]; then
    log_ok "Virtual environment Python: $($PYTHON_CMD --version 2>&1)"
    ((VERIFY_PASS++))
else
    log_error "Virtual environment Python not found at $PYTHON_CMD"
    ((VERIFY_FAIL++))
fi

# Check critical imports
declare -a CRITICAL_IMPORTS=(
    "httpx:HTTPX (SOCKS proxy support)"
    "aiohttp:AioHTTP (async HTTP client)"
    "circuitbreaker:Circuit Breaker"
    "dnslib:DNSLib (DNS protocol)"
    "openai:OpenAI SDK"
    "cryptography:Cryptography (Fernet encryption)"
    "click:Click CLI framework"
    "flask:Flask (AutoClaw web server)"
    "gunicorn:Gunicorn (WSGI server)"
    "eventlet:Eventlet (async workers)"
)

for item in "${CRITICAL_IMPORTS[@]}"; do
    IFS=':' read -r module label <<< "$item"
    if $PYTHON_CMD -c "import $module" 2>/dev/null; then
        log_ok "$label importable"
        ((VERIFY_PASS++))
    else
        log_warn "$label NOT importable (may need manual install)"
        ((VERIFY_FAIL++))
    fi
done

# Check optional imports
declare -a OPTIONAL_IMPORTS=(
    "prometheus_client:Prometheus Client (metrics)"
    "redis:Redis (distributed cache)"
    "curl_cffi:curl_cffi (Chrome fingerprinting)"
)

for item in "${OPTIONAL_IMPORTS[@]}"; do
    IFS=':' read -r module label <<< "$item"
    if $PYTHON_CMD -c "import $module" 2>/dev/null; then
        log_ok "$label importable (optional)"
        ((VERIFY_PASS++))
    else
        log_warn "$label NOT importable (optional -- not blocking)"
    fi
done

# Check owl-dns-synergy CLI
if $PYTHON_CMD -c "import owl_dns_synergy" 2>/dev/null; then
    log_ok "owl_dns_synergy package importable"
    ((VERIFY_PASS++))
else
    log_warn "owl_dns_synergy package not importable -- may need: pip install -e ."
    ((VERIFY_FAIL++))
fi

# Check config files
for f in config.json .env; do
    if [[ -f "$SYNERGY_HOME/config/$f" ]]; then
        log_ok "config/$f exists"
        ((VERIFY_PASS++))
    else
        log_error "config/$f missing"
        ((VERIFY_FAIL++))
    fi
done

# Check systemd unit files
for f in owl-dns-synergy.service autoclaw-proxy.service; do
    if [[ -f "$DEPLOY_DIR/$f" ]]; then
        log_ok "deploy/$f exists"
        ((VERIFY_PASS++))
    else
        log_error "deploy/$f missing"
        ((VERIFY_FAIL++))
    fi
done

log_info "Verification: $VERIFY_PASS passed, $VERIFY_FAIL failed"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 12: Next Steps
# ═════════════════════════════════════════════════════════════════════════════
log_phase "12/12" "Installation Complete"

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                                                                      ║${NC}"
echo -e "${BOLD}${CYAN}║   OWL-DNS-SYNERGY v${PRODUCT_VERSION} Installation Complete                     ║${NC}"
echo -e "${BOLD}${CYAN}║                                                                      ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BOLD}Installation Summary:${NC}"
echo -e "  Home directory:      ${GREEN}$SYNERGY_HOME${NC}"
echo -e "  Virtual environment:  ${GREEN}$VENV_DIR${NC}"
echo -e "  Python:              ${GREEN}$($PYTHON_CMD --version 2>&1)${NC}"
echo -e "  Config file:         ${GREEN}$SYNERGY_HOME/config/config.json${NC}"
echo -e "  Environment file:    ${GREEN}$SYNERGY_HOME/config/.env${NC}  ${RED}(mode 600)${NC}"
echo -e "  Systemd units:       ${GREEN}$DEPLOY_DIR/${NC}"
echo -e "  Install log:         ${GREEN}$INSTALL_LOG${NC}"
echo -e "  Verification:        ${GREEN}$VERIFY_PASS passed${NC}, ${RED}$VERIFY_FAIL failed${NC}"
echo ""

echo -e "${BOLD}${YELLOW}Next Steps:${NC}"
echo ""
echo -e "  ${BOLD}1. Set your API key:${NC}"
echo -e "     ${CYAN}vi $SYNERGY_HOME/config/.env${NC}"
echo -e "     ${DIM}# Set OPENAI_API_KEY=sk-...${NC}"
echo ""
echo -e "  ${BOLD}2. Create token files (if using AutoClaw):${NC}"
echo -e "     ${CYAN}cp $SYNERGY_HOME/config/proxies.txt.example $SYNERGY_HOME/config/proxies.txt${NC}"
echo -e "     ${CYAN}cp $SYNERGY_HOME/config/accounts.txt.example $SYNERGY_HOME/config/accounts.txt${NC}"
echo -e "     ${CYAN}chmod 600 $SYNERGY_HOME/config/proxies.txt $SYNERGY_HOME/config/accounts.txt${NC}"
echo ""
echo -e "  ${BOLD}3. Test the installation:${NC}"
echo -e "     ${CYAN}source $VENV_DIR/bin/activate${NC}"
echo -e "     ${CYAN}owl-dns-synergy --help${NC}"
echo ""
echo -e "  ${BOLD}4. Start services (development):${NC}"
echo -e "     ${CYAN}owl-dns-synergy serve${NC}             ${DIM}# DNS + HTTP router${NC}"
echo -e "     ${CYAN}gunicorn -b 127.0.0.1:31000 autoclaw.app:create_app()${NC}  ${DIM}# AutoClaw${NC}"
echo ""
echo -e "  ${BOLD}5. Deploy as systemd services (production):${NC}"
echo -e "     ${CYAN}sudo cp $DEPLOY_DIR/*.service /etc/systemd/system/${NC}"
echo -e "     ${CYAN}sudo systemctl daemon-reload${NC}"
echo -e "     ${CYAN}sudo systemctl enable --now owl-dns-synergy autoclaw-proxy${NC}"
echo ""
echo -e "  ${BOLD}6. Verify services:${NC}"
echo -e "     ${CYAN}sudo systemctl status owl-dns-synergy autoclaw-proxy${NC}"
echo -e "     ${CYAN}curl http://localhost:9090/metrics${NC}  ${DIM}# Prometheus metrics${NC}"
echo ""
echo -e "  ${BOLD}7. View logs:${NC}"
echo -e "     ${CYAN}journalctl -u owl-dns-synergy -f${NC}"
echo -e "     ${CYAN}journalctl -u autoclaw-proxy -f${NC}"
echo ""
echo -e "  ${BOLD}To uninstall:${NC}  ${CYAN}$0 --uninstall${NC}"
echo ""
