#!/usr/bin/env python3
"""Integration test for SmartChannelRouter v3 with all audit fixes applied.

Tests:
  1. Circuit breaker (3-state: CLOSED → OPEN → HALF_OPEN → CLOSED)
  2. DomainPreference EMA learning
  3. Cache with max size eviction
  4. DNS flood protector (reordered: per-client before global)
  5. AutoClaw adapter (channel label, error logging)
  6. CurlCffiClient (initialization)
  7. ChannelCircuitBreaker state transitions
  8. Full router status endpoint
"""

import asyncio
import os
import sys
import time

# Add repo to path
sys.path.insert(0, '/home/z/my-project/repos/owl-dns-synergy')
os.chdir('/home/z/my-project/repos/owl-dns-synergy')

# Load .env
from dotenv import load_dotenv
load_dotenv('/home/z/.owl-dns-synergy/.env')

from owl_dns_synergy.router_v3 import (
    SmartChannelRouterV3, ChannelCircuitBreaker, CircuitState,
    DomainPreference, DNSFloodProtector, AutoClawAdapter,
    CurlCffiClient, ChannelResult, Channel,
)

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} — {detail}")


async def run_tests():
    print("\n=== SmartChannelRouter v3 — Post-Audit Integration Tests ===\n")

    # Test 1: Circuit Breaker 3-state transitions
    print("[1] Circuit Breaker 3-state transitions")
    cb = ChannelCircuitBreaker("test_channel", failure_threshold=3, recovery_timeout=1.0, success_threshold=1)
    test("Initial state is CLOSED", cb.state == CircuitState.CLOSED, f"got {cb.state}")
    test("Allow request when CLOSED", await cb.allow_request())

    # Record 3 failures → OPEN
    for i in range(3):
        await cb.record_failure()
    test("State is OPEN after 3 failures", cb.state == CircuitState.OPEN, f"got {cb.state}")
    test("Reject request when OPEN", not await cb.allow_request())

    # Wait for recovery timeout → HALF_OPEN
    await asyncio.sleep(1.1)
    test("State is HALF_OPEN after timeout", cb.state == CircuitState.HALF_OPEN, f"got {cb.state}")
    test("Allow probe request when HALF_OPEN", await cb.allow_request())

    # Record success in HALF_OPEN → CLOSED
    await cb.record_success()
    test("State is CLOSED after probe success", cb.state == CircuitState.CLOSED, f"got {cb.state}")

    # Test HALF_OPEN failure → back to OPEN
    cb2 = ChannelCircuitBreaker("test2", failure_threshold=1, recovery_timeout=0.5, success_threshold=1)
    await cb2.record_failure()
    test("cb2 is OPEN", cb2.state == CircuitState.OPEN)
    await asyncio.sleep(0.6)
    test("cb2 is HALF_OPEN", cb2.state == CircuitState.HALF_OPEN)
    await cb2.record_failure()
    test("cb2 back to OPEN after probe fail", cb2.state == CircuitState.OPEN)

    # Test 2: DomainPreference EMA
    print("\n[2] DomainPreference EMA learning")
    pref = DomainPreference(domain="example.com")
    test("Initial preferred is http_proxy", pref.preferred_channel == "http_proxy")

    # Record 5 successes for dns_tunnel
    for _ in range(5):
        pref.record_channel_result("dns_tunnel", True)
    test("dns_tunnel EMA > 0.5 after 5 successes", pref.get_channel_score("dns_tunnel") > 0.5,
         f"score={pref.get_channel_score('dns_tunnel'):.3f}")
    test("Preferred channel updated to dns_tunnel", pref.preferred_channel == "dns_tunnel",
         f"got {pref.preferred_channel}")

    # Record 10 failures for dns_tunnel → should drop
    for _ in range(10):
        pref.record_channel_result("dns_tunnel", False)
    test("dns_tunnel EMA drops after failures", pref.get_channel_score("dns_tunnel") < 0.3,
         f"score={pref.get_channel_score('dns_tunnel'):.3f}")

    # Record successes for http_proxy → should become preferred
    for _ in range(8):
        pref.record_channel_result("http_proxy", True)
    test("Preferred switched to http_proxy", pref.preferred_channel == "http_proxy",
         f"got {pref.preferred_channel}")
    test("last_updated is recent", time.time() - pref.last_updated < 5)

    # Test 3: Cache with max size
    print("\n[3] Cache with max size eviction")
    router = SmartChannelRouterV3()
    test("Cache max is set", router._cache_max > 0, f"max={router._cache_max}")

    # Fill cache beyond max
    old_max = router._cache_max
    router._cache_max = 5
    for i in range(10):
        router._cache_set(f"key_{i}", f"value_{i}")
    test("Cache respects max size", len(router._cache) <= 5,
         f"size={len(router._cache)}")
    router._cache_max = old_max

    # Test 4: DNS Flood Protector (reordered)
    print("\n[4] DNS Flood Protector (per-client before global)")
    fp = DNSFloodProtector(max_qps=100, burst=100)
    test("Allow legitimate request", await fp.allow("192.168.1.1"))
    test("Allow second request", await fp.allow("192.168.1.2"))

    # Test 5: AutoClaw Adapter
    print("\n[5] AutoClaw Adapter")
    ac = AutoClawAdapter(base_url="http://localhost:31000")
    test("AutoClaw initialized", ac._base_url == "http://localhost:31000")
    # Token check will fail (server not running) but should log warning, not crash
    token = await ac.get_next_token()
    test("get_next_token returns None gracefully when server down", token is None)

    # Test 6: CurlCffiClient
    print("\n[6] CurlCffiClient")
    cfc = CurlCffiClient(chrome_version="chrome131")
    test("CurlCffiClient initialized", cfc._chrome_version == "chrome131")
    # Whether it's available depends on installation
    test("Available flag is boolean", isinstance(cfc._available, bool))

    # Test 7: Router circuit breakers
    print("\n[7] Router has per-channel circuit breakers")
    test("Circuit breakers dict is populated", len(router._circuit_breakers) > 0,
         f"count={len(router._circuit_breakers)}")
    test("http_proxy has circuit breaker", "http_proxy" in router._circuit_breakers)
    test("dns_tunnel has circuit breaker", "dns_tunnel" in router._circuit_breakers)

    # Test 8: Router status endpoint
    print("\n[8] Router status endpoint")
    status = router.get_status()
    test("Status has version", status.get("version") == "3.0.0")
    test("Status has circuit_breakers", "circuit_breakers" in status)
    test("Status has domain_preferences", "domain_preferences" in status)
    test("Status has cache max", "max" in status.get("cache", {}))
    test("Circuit breaker states are strings",
         all(isinstance(v["state"], str) for v in status["circuit_breakers"].values()))

    # Test 9: Channel selection with EMA preference
    print("\n[9] Channel selection respects EMA preference")
    router._prefs["preferred.example.com"] = DomainPreference(
        domain="preferred.example.com", preferred_channel="dns_tunnel"
    )
    # After recording successes for dns_tunnel
    for _ in range(5):
        router._prefs["preferred.example.com"].record_channel_result("dns_tunnel", True)
    selected = router._select_channel("preferred.example.com")
    test("Selected channel matches preference", selected == Channel.DNS_TUNNEL,
         f"got {selected}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed == 0:
        print("All tests PASSED!")
    else:
        print(f"{failed} test(s) FAILED")
    print(f"{'='*60}\n")

    return failed == 0


if __name__ == '__main__':
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
