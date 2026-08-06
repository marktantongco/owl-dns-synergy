#!/usr/bin/env python3
"""
AutoClaw Integration for OWL-DNS-Synergy v3
============================================
Sets up the AutoClaw OpenAI-compatible reverse proxy and integrates
it as a channel in the SmartChannelRouter v3 decision engine.

Features:
  - Google OAuth auto-login via CloakBrowser (58 C++ patches)
  - Round-robin token rotation across accounts
  - Proxy rotation per account (bypasses 630014 IP rate limit)
  - OpenAI-compatible /v1/chat/completions endpoint
  - Free GLM-5.2, GLM-5 Turbo, DeepSeek models
  - Dashboard at http://localhost:31000
"""

import os
import sys
import json
import time
import signal
import threading
import subprocess

# ─── Configuration ─────────────────────────────────────────────
AUTOCRAW_DIR = os.path.expanduser("~/.owl-dns-synergy/autoclaw")
SYNERGY_HOME = os.path.expanduser("~/.owl-dns-synergy")
PROXY_PORT = 31000
CALLBACK_PORT = 18432

# Load .env
env_path = os.path.join(SYNERGY_HOME, ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()


def print_banner():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   AutoClaw × OWL-DNS-Synergy Integration                  ║")
    print("║   Free GLM-5.2 / GLM-5 Turbo / DeepSeek via Google SSO    ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def check_prerequisites():
    """Check all dependencies are available."""
    print("── Prerequisites Check ──")
    all_ok = True

    # Python deps
    for mod in ["flask", "requests", "aiohttp", "cloakbrowser"]:
        try:
            __import__(mod)
            print(f"  ✓ {mod}")
        except ImportError:
            print(f"  ✗ {mod} — install with: pip3 install {mod}")
            all_ok = False

    # Autoclaw files
    for f in ["config.py", "auth.py", "proxy.py", "login.py", "autoclaw_autologin.py"]:
        path = os.path.join(AUTOCRAW_DIR, f)
        if os.path.exists(path):
            print(f"  ✓ {f}")
        else:
            print(f"  ✗ {f} missing")
            all_ok = False

    # tokens.json
    tokens_path = os.path.join(AUTOCRAW_DIR, "tokens.json")
    if os.path.exists(tokens_path):
        with open(tokens_path) as tf:
            data = json.load(tf)
            count = len(data.get("accounts", []))
            print(f"  ✓ tokens.json ({count} accounts)")
    else:
        print(f"  ⚠ tokens.json not found — will be created on first login")

    # accounts.txt
    acc_path = os.path.join(AUTOCRAW_DIR, "accounts.txt")
    if os.path.exists(acc_path):
        with open(acc_path) as af:
            lines = [l.strip() for l in af if l.strip() and not l.startswith('#')]
            print(f"  ✓ accounts.txt ({len(lines)} accounts)")
    else:
        print(f"  ⚠ accounts.txt not found — create with email:password entries")

    # proxies.txt
    proxy_path = os.path.join(AUTOCRAW_DIR, "proxies.txt")
    if os.path.exists(proxy_path):
        with open(proxy_path) as pf:
            lines = [l.strip() for l in pf if l.strip() and not l.startswith('#')]
            print(f"  ✓ proxies.txt ({len(lines)} proxies)")
    else:
        print(f"  ⚠ proxies.txt not found — proxy rotation disabled")

    return all_ok


def start_proxy_server():
    """Start the AutoClaw Flask proxy server on port 31000."""
    print()
    print("── Starting AutoClaw Proxy Server ──")
    print(f"  OpenAI-compatible API: http://localhost:{PROXY_PORT}/v1/chat/completions")
    print(f"  Dashboard:             http://localhost:{PROXY_PORT}/")
    print(f"  OAuth callback:        http://localhost:{CALLBACK_PORT}/auth/callback-google")
    print()

    # Start proxy.py as a subprocess
    proxy_script = os.path.join(AUTOCRAW_DIR, "proxy.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = AUTOCRAW_DIR

    proc = subprocess.Popen(
        [sys.executable, proxy_script],
        cwd=AUTOCRAW_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Wait a bit and check if it started
    time.sleep(2)
    if proc.poll() is not None:
        print(f"  ✗ Proxy server failed to start (exit code {proc.returncode})")
        output = proc.stdout.read().decode()[:2000]
        print(f"  Output: {output}")
        return None

    print(f"  ✓ Proxy server started (PID {proc.pid})")
    return proc


def test_proxy_endpoint():
    """Test the OpenAI-compatible endpoint."""
    import requests

    print()
    print("── Testing OpenAI-Compatible Endpoint ──")

    # Test /health
    try:
        resp = requests.get(f"http://localhost:{PROXY_PORT}/health", timeout=5)
        print(f"  ✓ /health: {resp.status_code} — {resp.json()}")
    except Exception as e:
        print(f"  ✗ /health: {e}")

    # Test /v1/models
    try:
        resp = requests.get(f"http://localhost:{PROXY_PORT}/v1/models", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
            print(f"  ✓ /v1/models: {len(models)} models — {models[:5]}")
        else:
            print(f"  /v1/models: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ✗ /v1/models: {e}")

    # Test /accounts
    try:
        resp = requests.get(f"http://localhost:{PROXY_PORT}/accounts", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            count = len(data.get("accounts", []))
            print(f"  ✓ /accounts: {count} accounts")
        else:
            print(f"  /accounts: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ✗ /accounts: {e}")

    # Test chat completions (only if accounts exist)
    try:
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
            print(f"  ✓ /v1/chat/completions: \"{content[:50]}\"")
            return True
        elif resp.status_code == 401:
            print(f"  ⚠ /v1/chat/completions: 401 — No accounts/tokens yet")
            print(f"     Run: python login.py or python autoclaw_autologin.py --batch accounts.txt")
        else:
            err = resp.json().get("error", {}).get("message", "")[:100]
            print(f"  ✗ /v1/chat/completions: HTTP {resp.status_code} — {err}")
    except Exception as e:
        print(f"  ✗ /v1/chat/completions: {e}")

    return False


def show_integration_guide():
    """Show how to integrate with SmartChannelRouter v3."""
    print()
    print("── Integration with SmartChannelRouter v3 ──")
    print()
    print("  The AutoClaw proxy is now accessible as an OpenAI-compatible")
    print("  LLM backend. Add it to your SmartChannelRouter v3 config:")
    print()
    print("  # In .env or config:")
    print(f"  AUTOCLAW_BASE_URL=http://localhost:{PROXY_PORT}")
    print("  OPENAI_BASE_URL=http://localhost:31000/v1   # Drop-in for any OpenAI client")
    print()
    print("  # Using with OpenAI SDK:")
    print("  from openai import OpenAI")
    print(f"  client = OpenAI(base_url='http://localhost:{PROXY_PORT}/v1', api_key='unused')")
    print("  resp = client.chat.completions.create(")
    print("      model='glm-5-turbo',  # or glm-5.2, cheap, auto, deepseek")
    print("      messages=[{'role':'user','content':'Hello!'}]")
    print("  )")
    print()
    print("  # Model aliases:")
    print("    glm-5.2     → Best quality (GLM-5.2 via OpenRouter)")
    print("    glm-5-turbo → Cheapest (always available)")
    print("    cheap       → Alias for glm-5-turbo")
    print("    auto        → Auto-select (may use DeepSeek, ~7x cost)")
    print("    deepseek    → Explicit DeepSeek-V4-Pro")
    print()
    print("  # Google OAuth Login:")
    print("    cd ~/.owl-dns-synergy/autoclaw")
    print("    python login.py              # Interactive browser login")
    print("    python login.py --manual     # Manual callback URL paste")
    print("    python autoclaw_autologin.py --batch accounts.txt  # Auto-login")
    print()
    print("  # Add Google accounts to accounts.txt:")
    print("    email1@gmail.com:password1")
    print("    email2@gmail.com:password2")
    print()
    print("  # Add proxies to proxies.txt (one per account):")
    print("    host:port:username:password")


def main():
    print_banner()

    if not check_prerequisites():
        print("\n  ⚠ Some prerequisites missing — proxy may not work fully")

    proc = start_proxy_server()
    if proc:
        chat_ok = test_proxy_endpoint()
        show_integration_guide()

        print()
        print("── Proxy Server Running ──")
        print(f"  PID: {proc.pid}")
        print(f"  URL: http://localhost:{PROXY_PORT}")
        print("  Press Ctrl+C to stop")
        print()

        try:
            while proc.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n  Stopping proxy server...")
            proc.terminate()
            proc.wait(timeout=5)
            print("  Stopped.")
    else:
        show_integration_guide()


if __name__ == "__main__":
    main()
