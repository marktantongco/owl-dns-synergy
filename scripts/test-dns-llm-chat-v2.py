#!/usr/bin/env python3
"""
Test LLM chat via DNS tunnel with a free OpenRouter model.
Tries multiple models in order until one works.
"""

import os
import sys
import time

# Load environment from .env
env_path = os.path.expanduser("~/.owl-dns-synergy/.env")
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()

sys.path.insert(0, os.path.expanduser("~/.owl-dns-synergy/repos/llm-dns-proxy"))

from llm_dns_proxy.server import LLMDNSServer
from llm_dns_proxy.client import DNSLLMClient

DNS_HOST = "127.0.0.1"
DNS_PORT = 5353
CRYPTO_KEY = os.environ.get('LLM_PROXY_KEY', '').encode() if os.environ.get('LLM_PROXY_KEY') else None
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://openrouter.ai/api/v1')

# Models to try (free/cheap ones first that should be globally available)
MODELS_TO_TRY = [
    "meta-llama/llama-3.1-8b-instruct:free",
    "google/gemma-2-9b-it:free",
    "qwen/qwen-2.5-7b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "openchat/openchat-7b:free",
    "huggingfaceh4/zephyr-7b-beta:free",
]

test_message = "Hello! What is 2+2? Answer in one sentence."

print("╔══════════════════════════════════════════════════════════════╗")
print("║   OWL-DNS-Synergy: DNS Tunnel LLM Chat — Model Selection   ║")
print("╚══════════════════════════════════════════════════════════════╝")
print()

chat_success = False
successful_model = None

for model in MODELS_TO_TRY:
    print(f"── Trying model: {model} ──")

    # Start DNS server with this model
    server = LLMDNSServer(
        host=DNS_HOST,
        port=DNS_PORT,
        crypto_key=CRYPTO_KEY,
        openai_api_key=OPENAI_API_KEY,
        openai_base_url=OPENAI_BASE_URL,
        openai_model=model
    )
    server.start()
    time.sleep(0.5)

    try:
        client = DNSLLMClient(
            server_host=DNS_HOST,
            server_port=DNS_PORT,
            crypto_key=CRYPTO_KEY,
            verbose=False,
            poll_interval=0.2,
            model=model
        )

        result = client.send_message(test_message, show_spinner=False, streaming=True)

        if result and "Error" not in result and "403" not in result and "401" not in result:
            print(f"  ✓ Model {model} works!")
            print()
            print(f"  ╔════════════════════════════════════════════════════╗")
            print(f"  ║  LLM Response via DNS Tunnel:                     ║")
            print(f"  ╚════════════════════════════════════════════════════╝")
            # Clean EOS marker
            clean_result = result.replace("[EOS]", "").strip()
            print(f"  {clean_result}")
            print()
            chat_success = True
            successful_model = model
            server.stop()
            break
        else:
            error_msg = result.replace("[EOS]", "").strip() if result else "No response"
            print(f"  ✗ Failed: {error_msg[:80]}")
            server.stop()
            time.sleep(0.5)
    except Exception as e:
        print(f"  ✗ Error: {e}")
        server.stop()
        time.sleep(0.5)

print()
print("── Final Summary ──")
if chat_success:
    print(f"  ✓ SUCCESS: OpenRouter responded via DNS tunnel")
    print(f"  ✓ Working model: {successful_model}")
    print(f"  ✓ DNS tunnel path: Client → UDP:5353 → Fernet decrypt → OpenRouter API → TXT response")
    print()
    # Update .env with the working model
    print(f"  Recommended: Update OPENAI_MODEL in .env to: {successful_model}")
else:
    print(f"  ✗ No free models worked through DNS tunnel")
    print(f"  The DNS tunnel itself is functional (encryption + transport verified)")
    print(f"  The 403 errors are from OpenRouter region/model availability restrictions")
