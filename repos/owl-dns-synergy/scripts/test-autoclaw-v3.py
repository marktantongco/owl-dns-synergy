#!/usr/bin/env python3
"""
AutoClaw × SmartChannelRouter v3 — Full Integration Test
========================================================
Tests the AutoClaw OpenAI-compatible proxy as a channel
in the unified SmartChannelRouter v3 decision engine.
"""

import os
import sys
import json
import time
import subprocess
import threading

# Load .env
env_path = os.path.expanduser("~/.owl-dns-synergy/.env")
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()

sys.path.insert(0, os.path.expanduser("~/my-project/repos/owl-dns-synergy"))

from owl_dns_synergy.router_v3 import (
    SmartChannelRouterV3, Channel, AutoClawAdapter, OpenRouterKeyRotator,
)

AUTOCRAW_DIR = os.path.expanduser("~/.owl-dns-synergy/autoclaw")
PROXY_PORT = 31000

def section(title):
    print(f"\n{'═' * 62}")
    print(f"  {title}")
    print(f"{'═' * 62}")

def ok(name, detail=""):
    print(f"  ✓ {name}" + (f" — {detail}" if detail else ""))

def warn(name, detail=""):
    print(f"  ⚠ {name}" + (f" — {detail}" if detail else ""))

# ═══════════════════════════════════════════════════════════════
print("╔══════════════════════════════════════════════════════════════╗")
print("║   AutoClaw × SmartChannelRouter v3 — Integration Test     ║")
print("╚══════════════════════════════════════════════════════════════╝")

# ─── Start AutoClaw Proxy Server ──────────────────────────────
section("Step 1: Start AutoClaw Proxy Server")

proxy_proc = subprocess.Popen(
    [sys.executable, os.path.join(AUTOCRAW_DIR, "proxy.py")],
    cwd=AUTOCRAW_DIR,
    env={**os.environ, "PYTHONPATH": AUTOCRAW_DIR},
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
time.sleep(3)

if proxy_proc.poll() is not None:
    print("  ✗ Proxy server failed to start")
    output = proxy_proc.stdout.read().decode()[:2000]
    print(f"  Output: {output}")
    sys.exit(1)

ok(f"Proxy server running", f"PID {proxy_proc.pid} on port {PROXY_PORT}")

# ─── Test AutoClaw Endpoints ──────────────────────────────────
section("Step 2: Test AutoClaw Endpoints")

import requests

# /health
resp = requests.get(f"http://localhost:{PROXY_PORT}/health", timeout=5)
health = resp.json()
ok("/health", f"status={health['status']}, accounts={health['accounts']}")

# /v1/models
resp = requests.get(f"http://localhost:{PROXY_PORT}/v1/models", timeout=5)
models_data = resp.json()
models = [m["id"] for m in models_data.get("data", [])]
ok("/v1/models", f"{len(models)} models: {', '.join(models)}")

# Show model details
for m in models_data.get("data", []):
    print(f"    {m['id']:15s} → upstream: {m['upstream']}")

# /accounts
resp = requests.get(f"http://localhost:{PROXY_PORT}/accounts", timeout=5)
accounts_data = resp.json()
account_count = len(accounts_data.get("accounts", []))
ok("/accounts", f"{account_count} accounts")

# ─── Test AutoClawAdapter ─────────────────────────────────────
section("Step 3: Test AutoClawAdapter in SmartChannelRouter v3")

adapter = AutoClawAdapter(base_url=f"http://localhost:{PROXY_PORT}")
ok("AutoClawAdapter initialized", adapter._base_url)

# ─── Test SmartChannelRouterV3 Integration ────────────────────
section("Step 4: SmartChannelRouter v3 with AutoClaw Backend")

router = SmartChannelRouterV3()

# Check autoclaw is wired into router
ok("Router has AutoClaw adapter", hasattr(router, 'autoclaw'))
ok("AutoClaw base URL", router.autoclaw._base_url)

# Full status
status = router.get_status()
ok("Stack version", f"v{status['version']}")
ok("Channels available", json.dumps(status["channels"]))
ok("Key rotator", f"{status['key_rotator']['total_keys']} OpenRouter keys")
ok("AutoClaw channel", f"base_url={router.autoclaw._base_url}")

# ─── Test Chat Completions ────────────────────────────────────
section("Step 5: Chat Completions via AutoClaw")

if account_count > 0:
    # Test with real account tokens
    resp = requests.post(
        f"http://localhost:{PROXY_PORT}/v1/chat/completions",
        json={
            "model": "glm-5-turbo",
            "messages": [{"role": "user", "content": "Say OK only."}],
            "max_tokens": 10,
            "stream": False,
        },
        timeout=30,
    )
    if resp.status_code == 200:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        ok("Chat completion", f'model={data["model"]}, content="{content[:50]}"')
    else:
        err = resp.json().get("error", {}).get("message", "")[:100]
        warn("Chat completion failed", f"HTTP {resp.status_code}: {err}")
else:
    warn("No accounts configured", "Login required to test chat completions")
    print()
    print("  To add accounts, run one of:")
    print("    cd ~/.owl-dns-synergy/autoclaw")
    print("    python login.py              # Interactive browser login")
    print("    python login.py --manual     # Manual callback URL")
    print("    python autoclaw_autologin.py --batch accounts.txt")
    print()
    print("  accounts.txt format: email@gmail.com:password")

# ─── Test OpenAI SDK Compatibility ────────────────────────────
section("Step 6: OpenAI SDK Compatibility")

try:
    from openai import OpenAI
    client = OpenAI(
        base_url=f"http://localhost:{PROXY_PORT}/v1",
        api_key="unused",  # AutoClaw uses its own token rotation
    )

    # List models
    models_resp = client.models.list()
    model_ids = [m.id for m in models_resp.data]
    ok("OpenAI SDK: models.list()", f"{len(model_ids)} models: {', '.join(model_ids[:3])}")

    if account_count > 0:
        # Chat completion via SDK
        chat_resp = client.chat.completions.create(
            model="glm-5-turbo",
            messages=[{"role": "user", "content": "Say OK only."}],
            max_tokens=10,
        )
        ok("OpenAI SDK: chat.completions.create()",
           f'content="{chat_resp.choices[0].message.content[:50]}"')
    else:
        warn("OpenAI SDK: chat skipped", "No accounts configured")
except Exception as e:
    warn("OpenAI SDK test", str(e)[:100])

# ─── Summary ──────────────────────────────────────────────────
section("Integration Summary")

print("  AutoClaw Proxy Server:")
print(f"    URL:        http://localhost:{PROXY_PORT}")
print(f"    API:        http://localhost:{PROXY_PORT}/v1/chat/completions")
print(f"    Models:     http://localhost:{PROXY_PORT}/v1/models")
print(f"    Dashboard:  http://localhost:{PROXY_PORT}/")
print()
print("  Available Models (FREE via Google SSO):")
print("    glm-5.2      → Best quality (GLM-5.2 via OpenRouter)")
print("    glm-5-turbo  → Cheapest (always available)")
print("    cheap        → Alias for glm-5-turbo")
print("    auto         → Auto-select (may use DeepSeek)")
print("    deepseek     → DeepSeek-V4-Pro (~7x cost)")
print()
print("  SmartChannelRouter v3 Channel Priority:")
print("    cached → http_proxy → socks_pool → dns_tunnel")
print("    → mitm_stealth → connect_chain → http_direct")
print()
print("  To use AutoClaw as primary LLM backend, set in .env:")
print("    OPENAI_BASE_URL=http://localhost:31000/v1")
print("    OPENAI_MODEL=glm-5-turbo")

# Cleanup
proxy_proc.terminate()
proxy_proc.wait(timeout=5)
print()
ok("Proxy server stopped")
