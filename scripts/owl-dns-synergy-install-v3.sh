#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# OWL-DNS-Synergy Merged Stack Installer v3.0.0
# Integrates 7 repos into a unified resilient access engine
# ═══════════════════════════════════════════════════════════════
#
# Repos:
#   1. OWL-AGENT v4.2 (QualityScorer, CircuitBreaker, HTTPCache)
#   2. LLM-DNS-Proxy (DNS tunneling, Fernet, TXT records)
#   3. secret-agent (MITM proxy, TLS fingerprinting, stealth browser)
#   4. proxytunnel (CONNECT chaining, NTLM, SSL tunneling)
#   5. autoclaw-autologin (OAuth harvesting, token rotation)
#   6. https_proxy (Rust stealth proxy, ACME TLS, nginx disguise)
#   7. prox5 (Go Mystery Dialer, SOCKS pool, validation)
#
# Usage: bash install-v3.sh [--skip-clone] [--skip-build] [--skip-go] [--skip-rust]
#
set -euo pipefail

VERSION="3.0.0"
SYNERGY_HOME="${OWL_DNS_SYNERGY_HOME:-$HOME/.owl-dns-synergy}"
REPOS_DIR="$SYNERGY_HOME/repos"
CONFIG_DIR="$SYNERGY_HOME/config"
BIN_DIR="$SYNERGY_HOME/bin"
LOG_DIR="$SYNERGY_HOME/logs"
CACHE_DIR="$SYNERGY_HOME/cache/http"

SKIP_CLONE=false
SKIP_BUILD=false
SKIP_GO=false
SKIP_RUST=false

for arg in "$@"; do
    case "$arg" in
        --skip-clone) SKIP_CLONE=true ;;
        --skip-build) SKIP_BUILD=true ;;
        --skip-go)    SKIP_GO=true ;;
        --skip-rust)  SKIP_RUST=true ;;
    esac
done

# ─── Phase Banner ─────────────────────────────────────────────
phase() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  Phase $1: $2"
    echo "╚══════════════════════════════════════════════════════════════╝"
}

ok()   { echo "  ✓ $1"; }
warn() { echo "  ⚠ $1"; }
fail() { echo "  ✗ $1"; }

# ─── Header ───────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   OWL-DNS-Synergy Merged Stack Installer v${VERSION}         ║"
echo "║   7-Repo Unified Resilient Access Engine                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  SYNERGY_HOME: $SYNERGY_HOME"
echo "  Skip clone:   $SKIP_CLONE"
echo "  Skip build:   $SKIP_BUILD"
echo "  Skip Go:      $SKIP_GO"
echo "  Skip Rust:    $SKIP_RUST"

# ─── Phase 1: Directory Structure ─────────────────────────────
phase 1 "Directory Structure"
mkdir -p "$SYNERGY_HOME" "$REPOS_DIR" "$CONFIG_DIR" "$BIN_DIR" "$LOG_DIR" "$CACHE_DIR"
ok "Created directory structure at $SYNERGY_HOME"

# ─── Phase 2: Git Clone ───────────────────────────────────────
phase 2 "Clone Repositories"

REPOS=(
    "owl-agent|https://github.com/nicholasgriffintn/OWL-AGENT"
    "llm-dns-proxy|https://github.com/nicholasgriffintn/llm-dns-proxy"
    "secret-agent|https://github.com/ulixee/secret-agent"
    "proxytunnel|https://github.com/proxytunnel/proxytunnel"
    "autoclaw-autologin|https://github.com/andreanocalvin/autoclaw-autologin"
    "https_proxy|https://github.com/madeye/https_proxy"
    "prox5|https://github.com/yunginnanet/prox5"
)

if [ "$SKIP_CLONE" = false ]; then
    for repo_spec in "${REPOS[@]}"; do
        IFS='|' read -r name url <<< "$repo_spec"
        if [ -d "$REPOS_DIR/$name" ]; then
            ok "$name already cloned — skipping"
        else
            echo "  Cloning $name..."
            if git clone --depth 1 "$url" "$REPOS_DIR/$name" 2>/dev/null; then
                ok "$name cloned"
            else
                warn "Failed to clone $name — will continue without it"
            fi
        fi
    done
else
    ok "Clone skipped (--skip-clone)"
fi

# ─── Phase 3: Python Dependencies ─────────────────────────────
phase 3 "Python Dependencies"

PYTHON_DEPS=(
    "openai"
    "dnslib"
    "cryptography"
    "prometheus_client"
    "httpx"
    "click"
    "redis"
)

for dep in "${PYTHON_DEPS[@]}"; do
    if python3 -c "import ${dep//-/_}" 2>/dev/null; then
        ok "$dep already installed"
    else
        echo "  Installing $dep..."
        pip3 install "$dep" 2>/dev/null && ok "$dep installed" || warn "Failed to install $dep"
    fi
done

# ─── Phase 4: Build proxytunnel (C) ───────────────────────────
phase 4 "Build proxytunnel (C)"

if [ -f "$REPOS_DIR/proxytunnel/Makefile" ] && [ "$SKIP_BUILD" = false ]; then
    if command -v make &>/dev/null && command -v gcc &>/dev/null; then
        echo "  Compiling proxytunnel..."
        if (cd "$REPOS_DIR/proxytunnel" && make -j$(nproc 2>/dev/null || echo 2) 2>/dev/null); then
            cp "$REPOS_DIR/proxytunnel/proxytunnel" "$BIN_DIR/" 2>/dev/null && ok "proxytunnel built and installed to $BIN_DIR" || warn "Build succeeded but copy failed"
        else
            warn "proxytunnel build failed — C compiler or deps may be missing"
        fi
    else
        warn "make/gcc not found — skipping proxytunnel build"
    fi
else
    ok "proxytunnel build skipped"
fi

# ─── Phase 5: Build https_proxy (Rust) ────────────────────────
phase 5 "Build https_proxy (Rust)"

if [ -d "$REPOS_DIR/https_proxy" ] && [ "$SKIP_RUST" = false ] && [ "$SKIP_BUILD" = false ]; then
    if command -v cargo &>/dev/null; then
        echo "  Compiling https_proxy (release)..."
        if (cd "$REPOS_DIR/https_proxy" && cargo build --release 2>/dev/null); then
            cp "$REPOS_DIR/https_proxy/target/release/https_proxy" "$BIN_DIR/" 2>/dev/null && ok "https_proxy built and installed" || warn "Build succeeded but copy failed"
        else
            warn "https_proxy build failed"
        fi
    else
        warn "cargo not found — skipping https_proxy build (install Rust: https://rustup.rs)"
    fi
else
    ok "https_proxy build skipped"
fi

# ─── Phase 6: Build prox5 (Go) ────────────────────────────────
phase 6 "Build prox5 (Go)"

if [ -d "$REPOS_DIR/prox5" ] && [ "$SKIP_GO" = false ] && [ "$SKIP_BUILD" = false ]; then
    if command -v go &>/dev/null; then
        echo "  Compiling prox5..."
        if (cd "$REPOS_DIR/prox5" && go build -o prox5 . 2>/dev/null); then
            cp "$REPOS_DIR/prox5/prox5" "$BIN_DIR/" 2>/dev/null && ok "prox5 built and installed" || warn "Build succeeded but copy failed"
        else
            warn "prox5 build failed (may need go mod tidy)"
        fi
    else
        warn "go not found — skipping prox5 build"
    fi
else
    ok "prox5 build skipped"
fi

# ─── Phase 7: Install secret-agent (Node.js) ──────────────────
phase 7 "Install secret-agent (Node.js)"

if [ -d "$REPOS_DIR/secret-agent" ] && [ "$SKIP_BUILD" = false ]; then
    if command -v npm &>/dev/null; then
        echo "  Installing Node.js dependencies..."
        (cd "$REPOS_DIR/secret-agent" && npm install --production 2>/dev/null) && ok "secret-agent deps installed" || warn "secret-agent npm install failed"
    else
        warn "npm not found — secret-agent requires Node.js"
    fi
else
    ok "secret-agent install skipped"
fi

# ─── Phase 8: Configuration Files ─────────────────────────────
phase 8 "Configuration Files"

# .env template
if [ ! -f "$SYNERGY_HOME/.env" ]; then
    cat > "$SYNERGY_HOME/.env" << 'ENVEOF'
# OWL-DNS-Synergy v3.0.0 — Merged Stack Configuration
# ═════════════════════════════════════════════════════════════

# OpenRouter API Keys
OPENAI_API_KEY=sk-or-v1-YOUR_KEY_HERE
OPENROUTER_KEY_1=sk-or-v1-BACKUP_KEY_1
OPENROUTER_KEY_2=sk-or-v1-BACKUP_KEY_2

# OpenRouter endpoint (OpenAI-compatible)
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=meta-llama/llama-3.1-8b-instruct:free

# DNS tunneling encryption key (Fernet AES-128)
LLM_PROXY_KEY=GENERATE_WITH:_python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# DNS server
DNS_SERVER_HOST=127.0.0.1
DNS_SERVER_PORT=5353
LLM_DNS_SUFFIX=_sonos._udp.local

# Prometheus metrics
OWL_DNS_SYNERGY_PROMETHEUS_PORT=9090

# DNS flood protection
DNS_FLOOD_MAX_QPS=50
DNS_FLOOD_BURST=100

# Proxy pool file (prox5/autoclaw format: host:port:user:pass)
SYNERGY_PROXY_FILE=

# Stealth proxy (https_proxy Rust)
STEALTH_PROXY_LISTEN=0.0.0.0:443
STEALTH_PROXY_DOMAIN=
STEALTH_PROXY_ACME_EMAIL=

# AutoClaw reverse proxy
AUTOCLAW_BASE_URL=http://localhost:31000

# Redis (optional)
REDIS_URL=redis://localhost:6379

# Cache TTL (seconds)
SYNERGY_CACHE_TTL=300
ENVEOF
    ok "Created .env template at $SYNERGY_HOME/.env"
else
    ok ".env already exists — preserving"
fi

# https_proxy config template
cat > "$CONFIG_DIR/https_proxy.yaml" << 'YAMLEOF'
listen: "0.0.0.0:443"
domain: "proxy.example.com"
acme:
  email: "admin@example.com"
  staging: false
  cache_dir: "/var/lib/https_proxy/acme"
users:
  - username: "synergy"
    password: "changeme"
stealth:
  server_name: "nginx/1.24.0"
fast_open: true
YAMLEOF
ok "Created https_proxy.yaml config"

# Proxy list template
cat > "$CONFIG_DIR/proxies.txt" << 'PROXYEOF'
# Proxy pool — one per line
# Format: host:port:user:pass  or  socks5://host:port
# Examples:
# 192.168.1.100:1080:user1:pass1
# socks5://10.0.0.1:9050
PROXYEOF
ok "Created proxies.txt template"

# Prometheus config
cat > "$CONFIG_DIR/prometheus.yml" << 'PROMEOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'owl-dns-synergy'
    static_configs:
      - targets: ['localhost:9090']
PROMEOF
ok "Created prometheus.yml"

# ─── Phase 9: Systemd Service ─────────────────────────────────
phase 9 "Systemd Service Templates"

# Main synergy service
cat > "$CONFIG_DIR/owl-dns-synergy.service" << 'SVCEOF'
[Unit]
Description=OWL-DNS-Synergy v3 Dual-Channel Resilient Access Engine
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

NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=%h/.owl-dns-synergy
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SVCEOF
ok "Created owl-dns-synergy.service"

# https_proxy service
cat > "$CONFIG_DIR/https-proxy.service" << 'SVCEOF2'
[Unit]
Description=OWL-DNS-Synergy Stealth HTTPS Proxy
After=network.target

[Service]
Type=simple
ExecStart=%h/.owl-dns-synergy/bin/https_proxy run -c %h/.owl-dns-synergy/config/https_proxy.yaml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF2
ok "Created https-proxy.service"

# ─── Phase 10: Runner Scripts ─────────────────────────────────
phase 10 "Runner Scripts"

# Unified runner
cat > "$SYNERGY_HOME/run.sh" << 'RUNEOF'
#!/usr/bin/env bash
# OWL-DNS-Synergy v3 Unified Runner
set -euo pipefail
SYNERGY_HOME="${OWL_DNS_SYNERGY_HOME:-$HOME/.owl-dns-synergy}"
source "$SYNERGY_HOME/.env" 2>/dev/null || true
export PYTHONPATH="$SYNERGY_HOME/repos/llm-dns-proxy:$SYNERGY_HOME/repos/owl-dns-synergy:$PYTHONPATH"
python3 -m owl_dns_synergy.cli "$@"
RUNEOF
chmod +x "$SYNERGY_HOME/run.sh"
ok "Created run.sh"

# DNS server launcher
cat > "$SYNERGY_HOME/start-dns-server.sh" << 'DNSEOF'
#!/usr/bin/env bash
set -euo pipefail
SYNERGY_HOME="${OWL_DNS_SYNERGY_HOME:-$HOME/.owl-dns-synergy}"
source "$SYNERGY_HOME/.env" 2>/dev/null || true
export PYTHONPATH="$SYNERGY_HOME/repos/llm-dns-proxy:$PYTHONPATH"
exec python3 -m llm_dns_proxy.cli server --host ${DNS_SERVER_HOST:-127.0.0.1} --port ${DNS_SERVER_PORT:-5353}
DNSEOF
chmod +x "$SYNERGY_HOME/start-dns-server.sh"
ok "Created start-dns-server.sh"

# Stealth proxy launcher
cat > "$SYNERGY_HOME/start-stealth-proxy.sh" << 'STEALTH'
#!/usr/bin/env bash
set -euo pipefail
SYNERGY_HOME="${OWL_DNS_SYNERGY_HOME:-$HOME/.owl-dns-synergy}"
exec "$SYNERGY_HOME/bin/https_proxy" run -c "$SYNERGY_HOME/config/https_proxy.yaml" "$@"
STEALTH
chmod +x "$SYNERGY_HOME/start-stealth-proxy.sh"
ok "Created start-stealth-proxy.sh"

# ─── Phase 11: Verification ───────────────────────────────────
phase 11 "Stack Verification"

echo "  Installed components:"
echo "  ┌─────────────────────────┬──────────┬──────────────┐"
echo "  │ Component               │ Status   │ Language     │"
echo "  ├─────────────────────────┼──────────┼──────────────┤"

check_repo() {
    if [ -d "$REPOS_DIR/$1" ]; then
        printf "  │ %-23s │ %-8s │ %-12s │\n" "$1" "✓ Cloned" "$2"
    else
        printf "  │ %-23s │ %-8s │ %-12s │\n" "$1" "✗ Missing" "$2"
    fi
}

check_repo "owl-agent" "Python"
check_repo "llm-dns-proxy" "Python"
check_repo "secret-agent" "TypeScript"
check_repo "proxytunnel" "C"
check_repo "autoclaw-autologin" "Python"
check_repo "https_proxy" "Rust"
check_repo "prox5" "Go"

echo "  └─────────────────────────┴──────────┴──────────────┘"

echo ""
echo "  Built binaries:"
for bin in proxytunnel https_proxy prox5; do
    if [ -f "$BIN_DIR/$bin" ]; then
        ok "$bin → $BIN_DIR/$bin"
    else
        warn "$bin not built"
    fi
done

echo ""
echo "  Configuration files:"
for cfg in .env config/https_proxy.yaml config/proxies.txt config/prometheus.yml; do
    if [ -f "$SYNERGY_HOME/$cfg" ]; then
        ok "$cfg"
    else
        warn "$cfg missing"
    fi
done

# ─── Summary ──────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   OWL-DNS-Synergy v${VERSION} Installation Complete         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Next steps:"
echo "    1. Edit $SYNERGY_HOME/.env with your API keys"
echo "    2. Add proxies to $SYNERGY_HOME/config/proxies.txt"
echo "    3. Start DNS server:    $SYNERGY_HOME/start-dns-server.sh"
echo "    4. Start stealth proxy: $SYNERGY_HOME/start-stealth-proxy.sh"
echo "    5. Run unified:         $SYNERGY_HOME/run.sh serve"
echo "    6. Deploy systemd:      sudo cp $CONFIG_DIR/owl-dns-synergy.service /etc/systemd/system/"
echo "                            sudo systemctl daemon-reload"
echo "                            sudo systemctl enable --now owl-dns-synergy@\$(whoami)"
echo ""
echo "  Stack channels (priority order):"
echo "    cached → http_proxy → socks_pool → dns_tunnel → mitm_stealth → connect_chain → http_direct"
