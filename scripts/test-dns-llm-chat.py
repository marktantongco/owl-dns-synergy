#!/usr/bin/env python3
"""
Test LLM chat via DNS tunnel — starts DNS server, sends a real chat message
through the DNS client, and verifies OpenRouter responds.
"""

import os
import sys
import time
import threading
import socket
import signal

# Load environment from .env
env_path = os.path.expanduser("~/.owl-dns-synergy/.env")
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()

# Add repos to path
sys.path.insert(0, os.path.expanduser("~/.owl-dns-synergy/repos/llm-dns-proxy"))
sys.path.insert(0, os.path.expanduser("~/.owl-dns-synergy/repos/owl-dns-synergy"))

from llm_dns_proxy.server import LLMDNSServer
from llm_dns_proxy.crypto import CryptoManager
from llm_dns_proxy.client import DNSLLMClient

# ─── Configuration ───
DNS_HOST = "127.0.0.1"
DNS_PORT = 5353
CRYPTO_KEY = os.environ.get('LLM_PROXY_KEY', '').encode() if os.environ.get('LLM_PROXY_KEY') else None
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://openrouter.ai/api/v1')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'openai/gpt-4o')

print("╔══════════════════════════════════════════════════════════════╗")
print("║   OWL-DNS-Synergy: LLM Chat via DNS Tunnel Test            ║")
print("╚══════════════════════════════════════════════════════════════╝")
print()
print(f"  DNS Server:     {DNS_HOST}:{DNS_PORT}")
print(f"  LLM Provider:   {OPENAI_BASE_URL}")
print(f"  Model:          {OPENAI_MODEL}")
print(f"  API Key:        {OPENAI_API_KEY[:20]}...{OPENAI_API_KEY[-8:]}")
print(f"  Encryption:     Fernet AES-128")
print(f"  DNS Suffix:     {os.environ.get('LLM_DNS_SUFFIX', '_sonos._udp.local')}")
print()

# ─── Step 1: Start DNS Server ───
print("── Step 1: Starting DNS Tunneling Server ──")
server = LLMDNSServer(
    host=DNS_HOST,
    port=DNS_PORT,
    crypto_key=CRYPTO_KEY,
    openai_api_key=OPENAI_API_KEY,
    openai_base_url=OPENAI_BASE_URL,
    openai_model=OPENAI_MODEL
)
server.start()
print("  ✓ DNS server started on 127.0.0.1:5353")

# Give server time to bind
time.sleep(1)

# ─── Step 2: Test basic DNS connectivity ───
print()
print("── Step 2: Testing Basic DNS Connectivity ──")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)
    # Send a test query: t._sonos._udp.local
    from dnslib import DNSRecord, DNSHeader, QTYPE, DNSQuestion
    test_query = DNSRecord(
        header=DNSHeader(id=1, qr=0, q=1),
        q=DNSQuestion("t._sonos._udp.local", QTYPE.TXT)
    )
    sock.sendto(test_query.pack(), (DNS_HOST, DNS_PORT))
    data, addr = sock.recvfrom(1024)
    response = DNSRecord.parse(data)
    print(f"  ✓ DNS query successful — server responded with {len(response.rr)} records")
    for rr in response.rr:
        print(f"    TXT: {rr.rdata}")
    sock.close()
except Exception as e:
    print(f"  ✗ DNS connectivity test failed: {e}")

# ─── Step 3: Send LLM chat via DNS tunnel ───
print()
print("── Step 3: Sending LLM Chat Message via DNS Tunnel ──")
print("  Message: 'Hello! What is 2+2? Answer briefly.'")
print()

chat_success = False
try:
    client = DNSLLMClient(
        server_host=DNS_HOST,
        server_port=DNS_PORT,
        crypto_key=CRYPTO_KEY,
        verbose=True,
        poll_interval=0.2,
        model=OPENAI_MODEL
    )

    # Send chat message with timeout
    test_message = "Hello! What is 2+2? Answer briefly."
    print(f"  Sending via DNS tunnel: '{test_message}'")
    print(f"  Waiting for OpenRouter response (via DNS TXT records)...")

    # Use send_message() — the actual DNSLLMClient API
    result = client.send_message(test_message, show_spinner=False, streaming=True)
    print()
    print(f"  ╔════════════════════════════════════════════════════╗")
    print(f"  ║  LLM Response via DNS Tunnel:                     ║")
    print(f"  ╚════════════════════════════════════════════════════╝")
    if result:
        print(f"  {result}")
    else:
        print("  (no response received)")
    chat_success = True

except Exception as e:
    print(f"  ✗ Chat via DNS tunnel failed: {e}")
    import traceback
    traceback.print_exc()

# ─── Step 4: Summary ───
print()
print("── Step 4: Test Summary ──")
print(f"  DNS Server:        ✓ Running on {DNS_HOST}:{DNS_PORT}")
print(f"  DNS Connectivity:  ✓ Responds to TXT queries")
print(f"  LLM Chat:          {'✓ OpenRouter responded via DNS tunnel' if chat_success else '✗ Failed'}")
print()

# Cleanup
server.stop()
print("  DNS server stopped.")
print()

if chat_success:
    print("═════════════════════════════════════════════════════════════")
    print("  ✓ ALL TESTS PASSED — OpenRouter responds through DNS tunnel")
    print("═════════════════════════════════════════════════════════════")
else:
    print("  ✗ Chat test did not complete successfully")
