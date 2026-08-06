# OWL-DNS-Synergy Deployment Guide

Production deployment guide for OWL-DNS-Synergy v1.0.0 -- the unified
dual-channel resilient access engine combining HTTP proxy evasion (OWL-AGENT v4.2)
and DNS tunneling (LLM-DNS-Proxy) with AutoClaw proxy management.

---

## Table of Contents

1. [Production Deployment](#production-deployment)
2. [Systemd Services](#systemd-services)
3. [Gunicorn Configuration](#gunicorn-configuration)
4. [Nginx Reverse Proxy](#nginx-reverse-proxy)
5. [Prometheus + Grafana](#prometheus--grafana)
6. [Token Encryption](#token-encryption)
7. [Security Hardening](#security-hardening)
8. [Docker Deployment](#docker-deployment)
9. [Troubleshooting](#troubleshooting)

---

## Production Deployment

### System Requirements

| Component       | Minimum          | Recommended       |
|-----------------|------------------|-------------------|
| OS              | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| RAM             | 2 GB             | 4 GB              |
| CPU Cores       | 2                | 4+                |
| Disk            | 10 GB            | 50 GB (SSD)       |
| Python          | 3.10             | 3.12              |
| Network         | 100 Mbps         | 1 Gbps            |

### Initial Server Setup

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install essential dependencies
sudo apt install -y \
    python3 python3-pip python3-venv \
    git curl wget \
    build-essential python3-dev \
    libssl-dev libffi-dev \
    nginx \
    prometheus prometheus-node-exporter \
    ufw

# Install Go 1.21+ (optional, for auxiliary tooling)
wget -q https://go.dev/dl/go1.22.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin

# Install Node.js 18+ (optional, for agent-browser)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Create dedicated service user
sudo useradd --system --shell /usr/sbin/nologin --home /opt/owl-dns-synergy owl-dns
sudo mkdir -p /opt/owl-dns-synergy
sudo chown owl-dns:owl-dns /opt/owl-dns-synergy
```

### OS-Level Tuning

#### Sysctl Parameters

Create `/etc/sysctl.d/99-owl-dns-synergy.conf`:

```ini
# Increase file descriptor limits for DNS and HTTP connections
fs.file-max = 1048576

# TCP connection tuning for high-throughput proxy routing
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15

# TCP keepalive for long-lived connections
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 6

# TCP window scaling for better throughput
net.ipv4.tcp_window_scaling = 1
net.ipv4.tcp_syncookies = 1

# Allow binding to privileged ports (DNS port 53) without root
net.ipv4.ip_unprivileged_port_start = 53

# Increase socket buffer sizes
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
```

Apply with:

```bash
sudo sysctl --system
```

#### Ulimit Configuration

Create `/etc/security/limits.d/owl-dns-synergy.conf`:

```
owl-dns  soft  nofile  65536
owl-dns  hard  nofile  1048576
owl-dns  soft  nproc   4096
owl-dns  hard  nproc   8192
```

#### Run the Installer

```bash
# Clone the repository (or use the local copy)
cd /opt/owl-dns-synergy
git clone https://github.com/user/owl-dns-synergy.git .

# Run the installer as the service user
sudo -u owl-dns bash install.sh
```

---

## Systemd Services

### Installing Service Files

The installer generates two systemd unit files in `~/.owl-dns-synergy/deploy/`:

```bash
# Copy service files to system location
sudo cp ~/.owl-dns-synergy/deploy/owl-dns-synergy.service /etc/systemd/system/
sudo cp ~/.owl-dns-synergy/deploy/autoclaw-proxy.service /etc/systemd/system/

# Reload systemd manager configuration
sudo systemctl daemon-reload

# Enable and start both services
sudo systemctl enable --now owl-dns-synergy
sudo systemctl enable --now autoclaw-proxy

# Verify both are running
sudo systemctl status owl-dns-synergy autoclaw-proxy
```

### owl-dns-synergy.service

This service runs the core DNS tunneling and HTTP proxy routing engine:

```ini
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
```

**Key directives explained:**

| Directive              | Value        | Purpose                                      |
|------------------------|--------------|----------------------------------------------|
| `MemoryMax`            | 1G           | Hard memory limit; OOM kill if exceeded      |
| `MemoryHigh`           | 768M         | Throttle memory above this threshold         |
| `CPUQuota`             | 200%         | Allow up to 2 CPU cores                      |
| `LimitNOFILE`          | 65536        | Maximum open file descriptors                |
| `Restart`              | on-failure   | Auto-restart on non-zero exit                |
| `WatchdogSec`          | 120          | Service must report healthy within 120s      |
| `ProtectSystem`        | strict       | Read-only root filesystem                    |
| `NoNewPrivileges`      | true         | Prevent privilege escalation                 |
| `CapabilityBoundingSet`| CAP_NET_BIND | Only allow binding to privileged ports        |

### autoclaw-proxy.service

This service runs the AutoClaw proxy management API via Gunicorn with
eventlet async workers:

```ini
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
```

### Viewing Logs with journalctl

```bash
# Follow logs for each service
journalctl -u owl-dns-synergy -f
journalctl -u autoclaw-proxy -f

# View recent logs (last 100 lines)
journalctl -u owl-dns-synergy -n 100
journalctl -u autoclaw-proxy -n 100

# Filter by priority
journalctl -u owl-dns-synergy -p err       # Errors only
journalctl -u owl-dns-synergy -p warning   # Warnings and above

# Time-range queries
journalctl -u owl-dns-synergy --since "2024-01-01" --until "2024-01-02"
journalctl -u owl-dns-synergy --since "1 hour ago"

# Search for specific patterns
journalctl -u owl-dns-synergy | grep -i "circuit breaker"
journalctl -u autoclaw-proxy | grep -i "token refresh"

# Export logs for analysis
journalctl -u owl-dns-synergy --since "24 hours ago" > /tmp/synergy-logs.txt
```

### Creating the System Environment File

```bash
# Create system-level environment file
sudo mkdir -p /etc/owl-dns-synergy
sudo cp ~/.owl-dns-synergy/config/.env /etc/owl-dns-synergy/env
sudo chmod 600 /etc/owl-dns-synergy/env
sudo chown owl-dns:owl-dns /etc/owl-dns-synergy/env
```

---

## Gunicorn Configuration

### Worker Count Formula

The optimal number of Gunicorn workers follows the standard formula:

```
workers = (2 x CPU_cores) + 1
```

| CPU Cores | Workers |
|-----------|---------|
| 1         | 3       |
| 2         | 5       |
| 4         | 9       |
| 8         | 17      |

For memory-constrained environments, reduce workers to minimize RSS:

```
workers = min((2 x CPU_cores) + 1, available_RAM_MB / 100)
```

### Worker Class: eventlet

AutoClaw uses `eventlet` as the worker class for async I/O support.
This is required because AutoClaw makes concurrent outbound HTTP requests
for token refresh and proxy validation.

```bash
# eventlet provides:
# - Cooperative multitasking (green threads / coroutines)
# - Non-blocking I/O for HTTP requests
# - Patched stdlib modules (socket, time, etc.)
# - Compatible with Flask and most Python web frameworks
```

**Alternative worker classes (not recommended for AutoClaw):**

| Worker Class | Use Case                           | Notes                        |
|--------------|------------------------------------|------------------------------|
| `sync`       | CPU-bound, no I/O                  | Default; blocks on I/O       |
| `eventlet`   | I/O-bound with async needs         | Recommended for AutoClaw     |
| `gevent`     | Similar to eventlet                | Alternative async library    |
| `uvicorn`    | ASGI apps (FastAPI, Starlette)     | Not compatible with Flask    |

### max_requests Recycling

To prevent memory leaks in long-running worker processes, Gunicorn
recycles workers after they have handled a configurable number of requests:

```bash
--max-requests 1000             # Recycle after 1000 requests
--max-requests-jitter 50        # Add random jitter (0-50) to prevent all workers recycling at once
```

Without jitter, all workers would restart simultaneously, causing a
brief spike in latency. Jitter spreads the restarts across a wider
time window.

### Graceful Timeout for Zero-Downtime Restarts

```bash
--graceful-timeout 30           # Workers have 30s to finish in-flight requests before being killed
--timeout 120                   # Workers are killed if they don't respond within 120s
```

When a worker receives a restart signal (e.g., during `systemctl restart`):

1. The worker stops accepting new requests
2. In-flight requests are given `graceful_timeout` seconds to complete
3. If the worker is still alive after `graceful_timeout`, it is force-killed
4. A new worker is spawned to replace it

### Complete Gunicorn Configuration File

Create `/opt/owl-dns-synergy/gunicorn.conf.py`:

```python
import multiprocessing
import os

# Server socket
bind = os.environ.get("AUTOCLAW_BIND", "127.0.0.1:31000")
backlog = 2048

# Worker processes
workers = int(os.environ.get("AUTOCLAW_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "eventlet"
worker_connections = 1000       # Max concurrent connections per eventlet worker
threads = 1                     # eventlet does not use threads

# Max requests before recycling (prevents memory leaks)
max_requests = int(os.environ.get("AUTOCLAW_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("AUTOCLAW_MAX_REQUESTS_JITTER", "50"))

# Timeouts
graceful_timeout = int(os.environ.get("AUTOCLAW_GRACEFUL_TIMEOUT", "30"))
timeout = int(os.environ.get("AUTOCLAW_TIMEOUT", "120"))
keepalive = 5

# Logging
accesslog = os.environ.get("AUTOCLAW_ACCESS_LOG", "/var/log/owl-dns-synergy/autoclaw-access.log")
errorlog = os.environ.get("AUTOCLAW_ERROR_LOG", "/var/log/owl-dns-synergy/autoclaw-error.log")
loglevel = os.environ.get("AUTOCLAW_LOG_LEVEL", "info")

# Security
limit_request_line = 8190       # Max size of HTTP request line
limit_request_fields = 100      # Max number of header fields
limit_request_field_size = 8190 # Max size of each header field

# Server mechanics
preload_app = True              # Load app code before forking workers (saves memory)
daemon = False                  # Do not daemonize (systemd manages the process)
pidfile = None
tmp_upload_dir = None

# Hooks
def on_starting(server):
    """Called before the server starts."""
    pass

def post_worker_init(worker):
    """Called after a worker has been initialized."""
    worker.log.info("AutoClaw worker initialized [pid=%d]", worker.pid)

def pre_exec(server):
    """Called before a new master process is started (during upgrade)."""
    server.log.info("AutoClaw server pre-exec hook")

def when_ready(server):
    """Called when the server is ready to accept connections."""
    server.log.info("AutoClaw server ready on %s", bind)
```

---

## Nginx Reverse Proxy

### Sample Configuration

Create `/etc/nginx/sites-available/owl-dns-synergy`:

```nginx
# ─── Upstream Definitions ────────────────────────────────────────────────────

upstream autoclaw_backend {
    server 127.0.0.1:31000;
    keepalive 32;
}

upstream dns_metrics_backend {
    server 127.0.0.1:9090;
    keepalive 16;
}

# ─── Rate Limiting Zones ─────────────────────────────────────────────────────

# General request rate limiting: 10 requests/second per IP
limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;

# API rate limiting: 5 requests/second per IP
limit_req_zone $binary_remote_addr zone=api:10m rate=5r/s;

# DNS tunnel rate limiting: 30 requests/second per IP
limit_req_zone $binary_remote_addr zone=dns_tunnel:10m rate=30r/s;

# ─── Shared TLS Configuration ────────────────────────────────────────────────

map $upstream_status $upstream_response_time {
    default $upstream_response_time;
}

# ─── HTTP to HTTPS Redirect ──────────────────────────────────────────────────

server {
    listen 80;
    listen [::]:80;
    server_name owl-dns.example.com;

    # Allow ACME challenges for Let's Encrypt
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# ─── Main HTTPS Server ───────────────────────────────────────────────────────

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name owl-dns.example.com;

    # ── TLS 1.3 Configuration ──────────────────────────────────────────────
    ssl_certificate     /etc/letsencrypt/live/owl-dns.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/owl-dns.example.com/privkey.pem;
    ssl_protocols       TLSv1.3 TLSv1.2;
    ssl_ciphers         ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    ssl_stapling        on;
    ssl_stapling_verify on;

    # ── Security Headers ───────────────────────────────────────────────────
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Request-ID $request_id always;

    # ── AutoClaw Proxy API ─────────────────────────────────────────────────
    location /api/ {
        limit_req zone=api burst=10 nodelay;

        proxy_pass http://autoclaw_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;

        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        # WebSocket support (for real-time token status)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # ── DNS Tunneling Endpoint ─────────────────────────────────────────────
    location /dns/ {
        limit_req zone=dns_tunnel burst=50 nodelay;

        proxy_pass http://autoclaw_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # ── Prometheus Metrics (restrict to internal networks) ─────────────────
    location /metrics {
        allow 10.0.0.0/8;
        allow 172.16.0.0/12;
        allow 192.168.0.0/16;
        allow 127.0.0.1;
        deny all;

        proxy_pass http://dns_metrics_backend/metrics;
        proxy_set_header Host $host;
    }

    # ── Health Check Endpoint ──────────────────────────────────────────────
    location /health {
        proxy_pass http://autoclaw_backend/health;
        access_log off;
    }

    # ── Default ────────────────────────────────────────────────────────────
    location / {
        return 404;
    }
}
```

### Enable the Configuration

```bash
# Create symbolic link
sudo ln -sf /etc/nginx/sites-available/owl-dns-synergy /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### Obtain TLS Certificate (Let's Encrypt)

```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d owl-dns.example.com

# Auto-renewal is configured by certbot timer
sudo systemctl status certbot.timer
```

---

## Prometheus + Grafana

### Prometheus Scrape Configuration

Add to `/etc/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  # ─── OWL-DNS-Synergy Core Metrics ────────────────────────────────
  - job_name: 'owl-dns-synergy'
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['localhost:9090']
        labels:
          service: 'owl-dns-synergy'
          component: 'dns-router'

  # ─── AutoClaw Proxy Manager Metrics ──────────────────────────────
  - job_name: 'autoclaw-proxy'
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['localhost:31000']
        labels:
          service: 'autoclaw-proxy'
          component: 'proxy-manager'

  # ─── Node Exporter (System Metrics) ──────────────────────────────
  - job_name: 'node'
    scrape_interval: 30s
    static_configs:
      - targets: ['localhost:9100']
        labels:
          service: 'owl-dns-synergy'
          component: 'system'
```

### Key Metrics Exported

| Metric Name                              | Type    | Description                              |
|------------------------------------------|---------|------------------------------------------|
| `synergy_requests_total`                 | Counter | Total requests processed                  |
| `synergy_requests_duration_seconds`      | Histogram | Request latency distribution            |
| `synergy_channel_requests_total`         | Counter | Requests per channel (dns/http/fallback)  |
| `synergy_circuit_breaker_state`          | Gauge   | Circuit breaker state (0=closed, 1=open)  |
| `synergy_dns_queries_total`              | Counter | Total DNS queries received                |
| `synergy_dns_flood_events_total`         | Counter | DNS flood protection events               |
| `synergy_cache_hits_total`               | Counter | Cache hit count                           |
| `synergy_cache_misses_total`             | Counter | Cache miss count                          |
| `autoclaw_token_refresh_total`           | Counter | Token refresh attempts                    |
| `autoclaw_token_refresh_failures_total`  | Counter | Token refresh failures                    |
| `autoclaw_active_proxies`                | Gauge   | Number of active proxies                  |

### Grafana Dashboard

Import the dashboard JSON template. The dashboard includes panels for:

1. **Request Rate** -- Requests/second by channel (DNS, HTTP, fallback)
2. **Latency Percentiles** -- P50, P95, P99 request duration
3. **Circuit Breaker State** -- Open/closed transitions over time
4. **DNS Flood Protection** -- Flood events per minute
5. **Cache Hit Ratio** -- Percentage of cache hits vs misses
6. **Memory Usage** -- RSS memory per process
7. **Active Proxies** -- Count of working proxies over time
8. **Token Refresh** -- Success/failure rate over time

To import:

```bash
# From the Grafana UI:
# 1. Navigate to Dashboards > Import
# 2. Upload the JSON file from deploy/grafana-dashboard.json
# 3. Select the Prometheus data source
```

### Prometheus Alert Rules

Create `/etc/prometheus/rules/owl-dns-synergy.yml`:

```yaml
groups:
  - name: owl-dns-synergy
    rules:
      # ─── Memory Alerts ─────────────────────────────────────────────
      - alert: SynergyMemoryHigh
        expr: process_resident_memory_bytes{service="owl-dns-synergy"} > 838860800  # 800MB
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "OWL-DNS-Synergy memory usage above 800MB"
          description: "Memory usage is {{ $value | humanize }}B (threshold: 800MB). Consider restarting the service."

      - alert: SynergyMemoryCritical
        expr: process_resident_memory_bytes{service="owl-dns-synergy"} > 943718400  # 900MB
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "OWL-DNS-Synergy memory usage critical (>900MB)"
          description: "Memory usage is {{ $value | humanize }}B. OOM kill imminent."

      # ─── Circuit Breaker Alerts ────────────────────────────────────
      - alert: CircuitBreakerOpen
        expr: synergy_circuit_breaker_state == 1
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker is open on {{ $labels.instance }}"
          description: "The circuit breaker has been open for more than 1 minute. All requests are being rejected."

      - alert: CircuitBreakerStuckOpen
        expr: synergy_circuit_breaker_state == 1
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker stuck open for 10 minutes on {{ $labels.instance }}"
          description: "The circuit breaker has been open for 10+ minutes. Manual intervention may be required."

      # ─── DNS Flood Alerts ──────────────────────────────────────────
      - alert: DNSFloodDetected
        expr: rate(synergy_dns_flood_events_total[5m]) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "DNS flood detected on {{ $labels.instance }}"
          description: "DNS flood protection is triggering at {{ $value }} events/s."

      # ─── Token Refresh Alerts ──────────────────────────────────────
      - alert: TokenRefreshFailures
        expr: rate(autoclaw_token_refresh_failures_total[5m]) / rate(autoclaw_token_refresh_total[5m]) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Token refresh failure rate above 50%"
          description: "{{ $value | humanizePercentage }} of token refresh attempts are failing."

      # ─── Service Availability ──────────────────────────────────────
      - alert: SynergyServiceDown
        expr: up{service="owl-dns-synergy"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "OWL-DNS-Synergy service is down"
          description: "Prometheus cannot reach the metrics endpoint on {{ $labels.instance }}."

      - alert: AutoClawServiceDown
        expr: up{service="autoclaw-proxy"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "AutoClaw proxy service is down"
          description: "Prometheus cannot reach the AutoClaw metrics endpoint on {{ $labels.instance }}."
```

---

## Token Encryption

### Overview

AutoClaw stores proxy credentials and API tokens that must be protected
at rest. When token encryption is enabled, all tokens are encrypted using
Fernet (AES-128-CBC with HMAC-SHA256) before being written to disk.

### Generating the Encryption Key

```bash
# Using the installer (auto-generated during Phase 6)
# The key is stored in ~/.owl-dns-synergy/config/.env as AUTOCLAW_TOKEN_KEY

# Manual generation:
source ~/.owl-dns-synergy/venv/bin/activate
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Setting AUTOCLAW_TOKEN_KEY

```bash
# Set in .env file
vi ~/.owl-dns-synergy/config/.env

# Find the AUTOCLAW_TOKEN_KEY line and paste the generated key:
# AUTOCLAW_TOKEN_KEY=your-generated-fernet-key-here

# Ensure proper file permissions
chmod 600 ~/.owl-dns-synergy/config/.env

# For systemd deployments, also update the system environment file
sudo vi /etc/owl-dns-synergy/env
sudo chmod 600 /etc/owl-dns-synergy/env

# Restart services to pick up the new key
sudo systemctl restart autoclaw-proxy
```

### Migration from Plaintext to Encrypted Tokens

If you have existing plaintext tokens in `accounts.txt`, migrate them
to encrypted storage:

```bash
source ~/.owl-dns-synergy/venv/bin/activate

# Step 1: Enable encryption in config
python -c "
import json
with open('$HOME/.owl-dns-synergy/config/config.json') as f:
    config = json.load(f)
config['autoclaw']['enable_encryption'] = True
with open('$HOME/.owl-dns-synergy/config/config.json', 'w') as f:
    json.dump(config, f, indent=4)
"

# Step 2: Back up plaintext tokens
cp ~/.owl-dns-synergy/config/accounts.txt ~/.owl-dns-synergy/config/accounts.txt.plaintext.bak
chmod 600 ~/.owl-dns-synergy/config/accounts.txt.plaintext.bak

# Step 3: Run the migration script
python -m autoclaw.migrate encrypt \
    --input ~/.owl-dns-synergy/config/accounts.txt \
    --output ~/.owl-dns-synergy/config/accounts.txt.enc \
    --key-env AUTOCLAW_TOKEN_KEY

# Step 4: Replace plaintext with encrypted
mv ~/.owl-dns-synergy/config/accounts.txt.enc ~/.owl-dns-synergy/config/accounts.txt
chmod 600 ~/.owl-dns-synergy/config/accounts.txt

# Step 5: Restart AutoClaw
sudo systemctl restart autoclaw-proxy

# Step 6: Verify tokens are working
curl -s http://localhost:31000/health | python -m json.tool
```

### Verifying Encryption is Active

```bash
# Check the health endpoint
curl -s http://localhost:31000/health | python -m json.tool

# Expected output includes:
# {
#   "encryption_enabled": true,
#   "token_count": 5,
#   "encrypted_token_count": 5
# }
```

---

## Security Hardening

### Firewall Rules (UFW)

```bash
# Reset to defaults
sudo ufw reset

# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (adjust port if non-standard)
sudo ufw allow 22/tcp comment 'SSH access'

# Allow HTTPS (Nginx reverse proxy)
sudo ufw allow 443/tcp comment 'HTTPS (Nginx -> AutoClaw)'

# Allow HTTP (redirect to HTTPS + ACME challenges)
sudo ufw allow 80/tcp comment 'HTTP (redirect + Let''s Encrypt)'

# Allow DNS (if running authoritative DNS on port 53)
sudo ufw allow 53/udp comment 'DNS (UDP)'
sudo ufw allow 53/tcp comment 'DNS (TCP)'

# Internal ports -- DO NOT expose these publicly
# 31000  - AutoClaw (accessed via Nginx only)
# 5353   - DNS server (accessed via Nginx only)
# 9090   - Prometheus metrics (internal only)

# Enable firewall
sudo ufw enable

# Verify
sudo ufw status verbose
```

### File Permissions

```bash
# Configuration and token files must be readable only by the service user
chmod 600 ~/.owl-dns-synergy/config/.env
chmod 600 ~/.owl-dns-synergy/config/proxies.txt
chmod 600 ~/.owl-dns-synergy/config/accounts.txt
chmod 600 ~/.owl-dns-synergy/config/config.json

# Set ownership
chown owl-dns:owl-dns ~/.owl-dns-synergy/config/.env
chown owl-dns:owl-dns ~/.owl-dns-synergy/config/proxies.txt
chown owl-dns:owl-dns ~/.owl-dns-synergy/config/accounts.txt

# Log directory: writable by service, readable by admin
chmod 750 ~/.owl-dns-synergy/logs
chown owl-dns:owl-dns ~/.owl-dns-synergy/logs

# System environment file
sudo chmod 600 /etc/owl-dns-synergy/env
sudo chown owl-dns:owl-dns /etc/owl-dns-synergy/env

# Virtual environment: owned by service user
chown -R owl-dns:owl-dns ~/.owl-dns-synergy/venv

# Verify permissions
ls -la ~/.owl-dns-synergy/config/
```

### Systemd Security Directives Explained

| Directive              | Value              | Security Impact                                  |
|------------------------|--------------------|--------------------------------------------------|
| `NoNewPrivileges`      | `true`             | Blocks setuid/setgid; prevents privilege escalation |
| `ProtectSystem`        | `strict`           | Mounts /usr, /boot, /etc as read-only            |
| `ProtectHome`          | `true`             | Mounts /home, /root, /run/user as empty          |
| `PrivateTmp`           | `true`             | Isolates /tmp and /var/tmp from other processes  |
| `ReadWritePaths`       | (specific paths)   | Only listed paths are writable                   |
| `CapabilityBoundingSet`| `CAP_NET_BIND_SERVICE` | Drops all capabilities except port binding    |
| `AmbientCapabilities` | `CAP_NET_BIND_SERVICE` | Allows non-root process to bind ports <1024  |
| `MemoryMax`            | `1G`               | OOM kill if process exceeds 1GB RAM              |
| `CPUQuota`             | `200%`             | Limits CPU usage to 2 cores max                  |
| `LimitNOFILE`          | `65536`            | Sets explicit file descriptor limit              |
| `WatchdogSec`          | `120`              | Kills unresponsive service after 120s            |

Additional hardening directives to consider:

```ini
# Network isolation (if DNS server doesn't need full network access)
# PrivateNetwork=true  # WARNING: This breaks DNS and HTTP proxy functionality

# Device access restriction
PrivateDevices=true

# IPC namespace isolation
PrivateIPC=true

# User namespace isolation
PrivateUsers=true

# Restrict address families (only IPv4/IPv6)
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX

# Lock additional directories
InaccessiblePaths=/var/secret /root

# Set secure default umask
UMask=0077
```

### SELinux / AppArmor Considerations

#### AppArmor (Ubuntu default)

If AppArmor is active, the owl-dns service may be blocked from accessing
its data directories. Create an AppArmor profile:

```bash
# Check AppArmor status
sudo aa-status

# Create profile: /etc/apparmor.d/owl-dns-synergy
sudo tee /etc/apparmor.d/owl-dns-synergy <<'AAPROFILE'
#include <tunables/global>

profile owl-dns-synergy /opt/owl-dns-synergy/venv/bin/python {
  #include <abstractions/base>
  #include <abstractions/python>
  #include <abstractions/nameservice>

  # Allow reading the application directory
  /opt/owl-dns-synergy/ r,
  /opt/owl-dns-synergy/** r,

  # Allow writing to specific paths
  /var/log/owl-dns-synergy/** rw,
  /var/cache/owl-dns-synergy/** rw,
  /opt/owl-dns-synergy/logs/** rw,
  /opt/owl-dns-synergy/cache/** rw,

  # Allow reading config and tokens
  /etc/owl-dns-synergy/env r,
  /opt/owl-dns-synergy/config/** r,

  # Network access (DNS + HTTP)
  network inet stream,
  network inet dgram,
  network inet6 stream,
  network inet6 dgram,
}
AAPROFILE

# Load the profile
sudo apparmor_parser -r /etc/apparmor.d/owl-dns-synergy
```

#### SELinux (RHEL/CentOS)

```bash
# Check SELinux mode
getenforce

# If enforcing, create a custom policy module
# This is a simplified example -- adjust for your environment
sudo tee owl_dns_synergy.te <<'SEMODULE'
policy_module(owl_dns_synergy, 1.0)

require {
    type httpd_t;
    type var_log_t;
    class file { read write append open getattr };
}

# Allow the service to write logs
allow httpd_t var_log_t:file { read write append open getattr };
SEMODULE

# Compile and install
checkmodule -M -m -o owl_dns_synergy.mod owl_dns_synergy.te
semodule_package -o owl_dns_synergy.pp -m owl_dns_synergy.mod
sudo semodule -i owl_dns_synergy.pp
```

---

## Docker Deployment

### Multi-Stage Dockerfile

Create `Dockerfile` in the project root:

```dockerfile
# ─── Stage 1: Build ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY owl_dns_synergy/ owl_dns_synergy/

# Install into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -e ".[full]"

# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Labels
LABEL maintainer="owl-dns-synergy"
LABEL version="1.0.0"
LABEL description="OWL-DNS-Synergy: Unified Dual-Channel Resilient Access Engine"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r owl-dns && \
    useradd -r -g owl-dns -d /opt/owl-dns-synergy -s /sbin/nologin owl-dns

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Create application directories
RUN mkdir -p /opt/owl-dns-synergy/config \
    /opt/owl-dns-synergy/cache \
    /opt/owl-dns-synergy/logs && \
    chown -R owl-dns:owl-dns /opt/owl-dns-synergy

WORKDIR /opt/owl-dns-synergy

# Copy application code
COPY --chown=owl-dns:owl-dns owl_dns_synergy/ owl_dns_synergy/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:9090/metrics || exit 1

# Expose ports
# 5353  - DNS server
# 31000 - AutoClaw proxy API
# 9090  - Prometheus metrics
EXPOSE 5353 31000 9090

# Run as non-root user
USER owl-dns

# Default command: run the DNS server
CMD ["python", "-m", "owl_dns_synergy.server"]
```

### docker-compose.yml

```yaml
version: "3.9"

services:
  # ─── OWL-DNS-Synergy Core ───────────────────────────────────────────
  owl-dns-synergy:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: owl-dns-synergy
    restart: unless-stopped
    ports:
      - "5353:5353/udp"
      - "5353:5353/tcp"
      - "9090:9090"
    volumes:
      - ./config:/opt/owl-dns-synergy/config:ro
      - ./cache:/opt/owl-dns-synergy/cache
      - ./logs:/opt/owl-dns-synergy/logs
    env_file:
      - config/.env
    environment:
      - SYNERGY_LOG_LEVEL=info
      - SYNERGY_METRICS_PORT=9090
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9090/metrics"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "2.0"
        reservations:
          memory: 512M
          cpus: "1.0"
    networks:
      - synergy-net
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"

  # ─── AutoClaw Proxy Manager ─────────────────────────────────────────
  autoclaw-proxy:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: autoclaw-proxy
    restart: unless-stopped
    command: >
      gunicorn
      --bind 0.0.0.0:31000
      --workers 3
      --worker-class eventlet
      --max-requests 1000
      --max-requests-jitter 50
      --graceful-timeout 30
      --timeout 120
      autoclaw.app:create_app()
    ports:
      - "31000:31000"
    volumes:
      - ./config:/opt/owl-dns-synergy/config:ro
      - ./logs:/opt/owl-dns-synergy/logs
    env_file:
      - config/.env
    environment:
      - AUTOCLAW_HOST=0.0.0.0
      - AUTOCLAW_PORT=31000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:31000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    depends_on:
      owl-dns-synergy:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
        reservations:
          memory: 256M
          cpus: "0.5"
    networks:
      - synergy-net
    logging:
      driver: json-file
      options:
        max-size: "25m"
        max-file: "5"

  # ─── Redis (Optional: distributed caching) ──────────────────────────
  redis:
    image: redis:7-alpine
    container_name: synergy-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    deploy:
      resources:
        limits:
          memory: 300M
    networks:
      - synergy-net

  # ─── Prometheus ─────────────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:v2.50.0
    container_name: synergy-prometheus
    restart: unless-stopped
    ports:
      - "9091:9090"
    volumes:
      - ./deploy/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    networks:
      - synergy-net

  # ─── Grafana ────────────────────────────────────────────────────────
  grafana:
    image: grafana/grafana:10.4.0
    container_name: synergy-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_AUTH_ANONYMOUS_ENABLED=false
    depends_on:
      - prometheus
    networks:
      - synergy-net

volumes:
  redis-data:
  prometheus-data:
  grafana-data:

networks:
  synergy-net:
    driver: bridge
```

### Docker Deployment Commands

```bash
# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f owl-dns-synergy
docker compose logs -f autoclaw-proxy

# Scale AutoClaw workers (if needed)
docker compose up -d --scale autoclaw-proxy=2

# Restart a single service
docker compose restart owl-dns-synergy

# Stop and remove all containers
docker compose down

# Stop and remove including volumes (WARNING: deletes data)
docker compose down -v
```

---

## Troubleshooting

### DNS Server Not Responding

**Symptoms:** DNS queries to port 5353 time out or return SERVFAIL.

**Diagnosis:**

```bash
# Check if the service is running
sudo systemctl status owl-dns-synergy

# Check if the port is bound
sudo ss -tlnp | grep 5353
sudo ss -ulnp | grep 5353

# Test DNS resolution directly
dig @127.0.0.1 -p 5353 test._sonos._udp.local

# Check for DNS flood protection
journalctl -u owl-dns-synergy | grep -i "flood"

# Check OpenAI connectivity (required for DNS tunneling)
curl -s https://api.openai.com/v1/models \
    -H "Authorization: Bearer $OPENAI_API_KEY" | head -20
```

**Common causes and fixes:**

| Cause                            | Fix                                              |
|----------------------------------|--------------------------------------------------|
| OPENAI_API_KEY not set           | Set in .env file and restart service              |
| OpenAI API unreachable           | Check network/proxy; verify API key is valid      |
| Port already in use              | `sudo lsof -i :5353` to find conflicting process  |
| DNS flood protection triggered   | Increase `dns_flood_max_qps` in config.json       |
| Python venv not activated        | Ensure systemd ExecStart uses venv python         |
| Firewall blocking UDP/5353       | `sudo ufw allow 5353/udp`                        |

### Token Refresh Failures

**Symptoms:** AutoClaw token refresh fails, proxy credentials become stale.

**Diagnosis:**

```bash
# Check AutoClaw health
curl -s http://localhost:31000/health | python -m json.tool

# Check for encryption errors
journalctl -u autoclaw-proxy | grep -i "decrypt\|fernet\|token"

# Verify AUTOCLAW_TOKEN_KEY is set
grep AUTOCLAW_TOKEN_KEY ~/.owl-dns-synergy/config/.env

# Test encryption manually
source ~/.owl-dns-synergy/venv/bin/activate
python -c "
import os
from cryptography.fernet import Fernet
key = os.environ.get('AUTOCLAW_TOKEN_KEY', '')
if not key:
    print('ERROR: AUTOCLAW_TOKEN_KEY not set')
    exit(1)
f = Fernet(key.encode())
encrypted = f.encrypt(b'test-token')
decrypted = f.decrypt(encrypted)
print(f'Encryption OK: {decrypted.decode()}')
"

# Check token refresh rate in Prometheus
curl -s http://localhost:31000/metrics | grep autoclaw_token_refresh
```

**Common causes and fixes:**

| Cause                                | Fix                                              |
|--------------------------------------|--------------------------------------------------|
| AUTOCLAW_TOKEN_KEY mismatch          | Ensure same key in .env and /etc/owl-dns-synergy/env |
| Fernet key corrupted (wrong length)  | Regenerate key; re-encrypt all tokens             |
| Token expired upstream               | Manually refresh tokens or increase refresh interval |
| Network timeout during refresh       | Increase timeout in config; check proxy connectivity |
| accounts.txt permissions too open    | `chmod 600 accounts.txt`                          |

### Memory Exceeded (OOM Killer)

**Symptoms:** Service killed by OOM killer, seen in dmesg or journalctl.

**Diagnosis:**

```bash
# Check for OOM kills
dmesg | grep -i "oom-kill"
journalctl -k | grep -i "oom"

# Check current memory usage
ps aux | grep owl-dns
smem -t | grep owl-dns

# Check systemd memory accounting
systemctl show owl-dns-synergy | grep Memory

# Check Prometheus memory metrics
curl -s http://localhost:9090/metrics | grep process_resident_memory
```

**Common causes and fixes:**

| Cause                                | Fix                                              |
|--------------------------------------|--------------------------------------------------|
| Memory leak in long-running process  | Lower `max_requests` in Gunicorn config (more frequent worker recycling) |
| Large DNS cache                       | Reduce `cache_max` in config.json                 |
| Too many Gunicorn workers             | Reduce worker count; formula: (2 x CPU) + 1       |
| eventlet connection leak             | Ensure all HTTP responses are consumed/closed      |
| curl_cffi native memory not freed    | Upgrade curl_cffi; disable if not needed           |
| systemd MemoryMax too low            | Increase MemoryMax in service unit file            |

**Emergency memory reduction:**

```bash
# Restart the service to reclaim leaked memory
sudo systemctl restart owl-dns-synergy

# If persistent, increase memory limits temporarily
sudo systemctl set-property owl-dns-synergy MemoryMax=2G

# Reduce cache size
python -c "
import json
with open('$HOME/.owl-dns-synergy/config/config.json') as f:
    config = json.load(f)
config['cache_max'] = 500
config['cache_ttl'] = 60
with open('$HOME/.owl-dns-synergy/config/config.json', 'w') as f:
    json.dump(config, f, indent=4)
"
sudo systemctl restart owl-dns-synergy
```

### Circuit Breaker Stuck Open

**Symptoms:** All requests return errors; circuit breaker never recovers.

**Diagnosis:**

```bash
# Check circuit breaker state
curl -s http://localhost:9090/metrics | grep circuit_breaker

# Check recent failures
journalctl -u owl-dns-synergy | grep -i "circuit breaker"

# Check upstream service health
curl -s https://api.openai.com/v1/models \
    -H "Authorization: Bearer $OPENAI_API_KEY" | python -m json.tool
```

**Common causes and fixes:**

| Cause                                | Fix                                              |
|--------------------------------------|--------------------------------------------------|
| Upstream API permanently down        | Fix upstream connectivity; wait for recovery timeout |
| Recovery timeout too short           | Increase `circuit_breaker_recovery_timeout` in config |
| Failure threshold too low            | Increase `circuit_breaker_failure_threshold` (default: 5) |
| All proxy channels exhausted         | Add more proxies; check proxy health              |
| DNS channel also failing             | Check OpenAI API key and DNS configuration        |

**Force circuit breaker reset:**

```bash
# Option 1: Restart the service (resets circuit breaker)
sudo systemctl restart owl-dns-synergy

# Option 2: Reset via API (if available)
curl -X POST http://localhost:31000/api/circuit-breaker/reset

# Option 3: Increase recovery timeout for automatic recovery
python -c "
import json
with open('$HOME/.owl-dns-synergy/config/config.json') as f:
    config = json.load(f)
config['circuit_breaker_recovery_timeout'] = 120
config['circuit_breaker_failure_threshold'] = 10
with open('$HOME/.owl-dns-synergy/config/config.json', 'w') as f:
    json.dump(config, f, indent=4)
"
sudo systemctl restart owl-dns-synergy
```

### Additional Diagnostic Commands

```bash
# Full system health check
echo "=== Services ==="
sudo systemctl status owl-dns-synergy autoclaw-proxy --no-pager

echo "=== Ports ==="
sudo ss -tlnp | grep -E '5353|31000|9090'

echo "=== Memory ==="
ps aux --sort=-%mem | head -20

echo "=== Disk ==="
df -h /opt/owl-dns-synergy

echo "=== Network Connectivity ==="
curl -s -o /dev/null -w "%{http_code}" https://api.openai.com/v1/models

echo "=== Config Validation ==="
source ~/.owl-dns-synergy/venv/bin/activate
python -c "import json; json.load(open('$HOME/.owl-dns-synergy/config/config.json')); print('config.json: OK')"

echo "=== Encryption Keys ==="
grep -c "LLM_PROXY_KEY=.\+" ~/.owl-dns-synergy/config/.env && echo "LLM_PROXY_KEY: set" || echo "LLM_PROXY_KEY: MISSING"
grep -c "AUTOCLAW_TOKEN_KEY=.\+" ~/.owl-dns-synergy/config/.env && echo "AUTOCLAW_TOKEN_KEY: set" || echo "AUTOCLAW_TOKEN_KEY: MISSING"
```
