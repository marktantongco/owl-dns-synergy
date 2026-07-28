"""
OWL-DNS-Synergy CLI v2 — Unified command-line interface.
Enhanced with DNS server serve command, key rotation status, and Prometheus metrics.
"""

import asyncio
import os
import sys
import click
import logging
import signal

from .config import SynergyConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("owl-dns-synergy.cli")


@click.group()
def main():
    """OWL-DNS-Synergy: Unified dual-channel resilient access engine."""
    pass


@main.command()
@click.argument('url')
@click.option('--channel', default='auto', help='Channel: auto, http, dns')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def fetch(url, channel, verbose):
    """Fetch a URL through the optimal access channel."""
    from .router import SmartChannelRouter
    config = SynergyConfig()
    router = SmartChannelRouter(config=config)

    async def _fetch():
        await router.initialize()
        result = await router.fetch(url)
        if result.success:
            if isinstance(result.data, bytes):
                print(result.data.decode('utf-8', errors='replace'))
            else:
                print(result.data)
            if verbose:
                print(f"\n--- Stats: channel={result.channel}, latency={result.latency_ms:.0f}ms ---")
        else:
            print(f"Error: {result.error}")
            if verbose:
                print(f"Channel: {result.channel}")

    asyncio.run(_fetch())


@main.command()
@click.argument('message')
@click.option('--server', default='127.0.0.1', help='DNS server host')
@click.option('--port', default=5353, type=int, help='DNS server port')
def chat(message, server, port):
    """Send a message via DNS tunnel to LLM."""
    print(f"Chat via DNS tunnel to {server}:{port}: {message}")
    print("(DNS client integration pending — use llm-dns-proxy standalone for now)")


@main.command()
def stats():
    """Show current channel statistics."""
    from .router import SmartChannelRouter
    config = SynergyConfig()
    router = SmartChannelRouter(config=config)

    async def _stats():
        await router.initialize()
        stats = router.get_channel_stats()
        import json
        print(json.dumps(stats, indent=2))

    asyncio.run(_stats())


@main.command()
def generate_key():
    """Generate a Fernet encryption key for DNS tunneling."""
    from .core import CryptoManager
    key = CryptoManager.generate_key()
    print(f"LLM_PROXY_KEY={key.decode()}")
    print("Save this key in your environment or config file.")


@main.command()
def test_connection():
    """Test both HTTP and DNS channel connectivity."""
    from .router import SmartChannelRouter
    config = SynergyConfig()
    router = SmartChannelRouter(config=config)

    async def _test():
        await router.initialize()
        # Test HTTP
        print("Testing HTTP channel...")
        http_result = await router._try_http("https://httpbin.org/get", "httpbin.org")
        print(f"HTTP: {http_result.success} ({http_result.latency_ms:.0f}ms)")

        # Test DNS
        print("Testing DNS channel...")
        dns_result = await router._try_dns("https://httpbin.org/get", "httpbin.org")
        print(f"DNS: {dns_result.success} ({dns_result.latency_ms:.0f}ms)")

        print(f"\nChannel stats: {router.get_channel_stats()}")

    asyncio.run(_test())


@main.command()
@click.option('--host', default='127.0.0.1', help='DNS server host')
@click.option('--port', default=5353, type=int, help='DNS server port')
@click.option('--prometheus-port', default=9090, type=int, help='Prometheus metrics port')
def serve(host, port, prometheus_port):
    """Start the OWL-DNS-Synergy DNS tunneling server with Prometheus metrics."""
    # Load environment from .env file
    env_path = os.path.expanduser("~/.owl-dns-synergy/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    # Import DNS server components
    sys.path.insert(0, os.path.expanduser("~/.owl-dns-synergy/repos/llm-dns-proxy"))
    from llm_dns_proxy.server import LLMDNSServer
    from llm_dns_proxy.crypto import CryptoManager as DNSCryptoManager

    # Initialize key rotator
    from .router import OpenRouterKeyRotator
    key_rotator = OpenRouterKeyRotator.from_env()

    crypto_key = os.environ.get('LLM_PROXY_KEY', '').encode() if os.environ.get('LLM_PROXY_KEY') else None
    openai_api_key = key_rotator.get_active_key() or os.environ.get('OPENAI_API_KEY')
    openai_base_url = key_rotator.base_url
    openai_model = os.environ.get('OPENAI_MODEL', 'gpt-4o')

    print(f"╔══════════════════════════════════════════════════════════════╗")
    print(f"║   OWL-DNS-SYNERGY DNS Tunneling Server v2.0               ║")
    print(f"║   HTTP Proxy Evasion + DNS Tunneling + Obsidian           ║")
    print(f"╚══════════════════════════════════════════════════════════════╝")
    print(f"")
    print(f"  Host:              {host}:{port}")
    print(f"  LLM Provider:      {openai_base_url}")
    print(f"  Model:             {openai_model}")
    print(f"  API Keys:          {key_rotator.total_keys} ({key_rotator.available_keys} available)")
    print(f"  Prometheus:        http://localhost:{prometheus_port}/metrics")
    print(f"  DNS Suffix:        {os.environ.get('LLM_DNS_SUFFIX', '_sonos._udp.local')}")
    print(f"  Encryption:        Fernet AES-128 (active)")
    print(f"")

    server = LLMDNSServer(
        host=host,
        port=port,
        crypto_key=crypto_key,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        openai_model=openai_model
    )

    # Start Prometheus metrics
    try:
        from prometheus_client import start_http_server
        start_http_server(prometheus_port)
        print(f"  Prometheus metrics server started on port {prometheus_port}")
    except OSError:
        print(f"  Warning: Prometheus port {prometheus_port} already in use")

    server.start()
    print(f"\n  DNS server started — waiting for queries...")
    print(f"  Press Ctrl+C to stop\n")

    running = True
    def signal_handler(sig, frame):
        nonlocal running
        print(f"\n  Shutting down...")
        running = False

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        while running:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    server.stop()
    print("  Server stopped.")


@main.command()
def key_status():
    """Show OpenRouter API key rotation status."""
    from .router import OpenRouterKeyRotator
    import json

    rotator = OpenRouterKeyRotator.from_env()
    status = rotator.get_status()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   OpenRouter API Key Rotation Status                       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Total keys:    {status['total_keys']}")
    print(f"  Available:     {status['available_keys']}")
    print(f"  Current index: {status['current_index']}")
    print(f"  Base URL:      {rotator.base_url}")
    print()

    if status['key_errors']:
        print("  Key Errors:")
        for idx, count in status['key_errors'].items():
            print(f"    Key {idx}: {count} errors")

    if status['cooldowns']:
        print("  Cooldowns:")
        for idx, remaining in status['cooldowns'].items():
            if remaining > 0:
                print(f"    Key {idx}: {remaining:.0f}s remaining")


if __name__ == '__main__':
    main()
