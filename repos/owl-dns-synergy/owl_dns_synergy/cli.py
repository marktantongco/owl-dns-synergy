"""
OWL-DNS-Synergy CLI — Unified command-line interface.
"""

import asyncio
import click
import logging

from .config import SynergyConfig
from .router import SmartChannelRouter

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
                print(f"Channel: {result.channel}, Domain: {channel}")

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
    config = SynergyConfig()
    router = SmartChannelRouter(config=config)

    async def _test():
        await router.initialize()
        # Test HTTP
        print("Testing HTTP channel...")
        http_result = await router._try_http("https://httpbin.org/get", "httpbin.org")
        print(f"HTTP: {http_result.success} ({http_result.latency_ms:.0f}ms)")

        # Test DNS (placeholder)
        print("Testing DNS channel...")
        dns_result = await router._try_dns("https://httpbin.org/get", "httpbin.org")
        print(f"DNS: {dns_result.success} ({dns_result.latency_ms:.0f}ms)")

        print(f"\nChannel stats: {router.get_channel_stats()}")

    asyncio.run(_test())


if __name__ == '__main__':
    main()
