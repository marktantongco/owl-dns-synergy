"""
SmartChannelRouter v2 — Enhanced with OpenRouter key rotation, Prometheus metrics,
DNS flood protection, and per-client rate limiting.
"""

import asyncio
import time
import logging
import os
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from collections import deque

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger("owl-dns-synergy.router")


# ─── Prometheus Metrics ──────────────────────────────────────────
REQUESTS_TOTAL = Counter(
    'synergy_requests_total',
    'Total requests processed',
    ['channel', 'domain', 'status']
)

REQUESTS_DURATION = Histogram(
    'synergy_request_duration_seconds',
    'Request duration in seconds',
    ['channel', 'domain'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

CHANNEL_SWITCHES = Counter(
    'synergy_channel_switches_total',
    'Number of channel switches',
    ['from_channel', 'to_channel']
)

ACTIVE_CONNECTIONS = Gauge(
    'synergy_active_connections',
    'Currently active connections',
    ['channel']
)

PROXY_QUALITY_SCORE = Gauge(
    'synergy_proxy_quality_score',
    'Quality score for proxies',
    ['proxy_url']
)

DNS_SERVER_QUALITY_SCORE = Gauge(
    'synergy_dns_server_quality_score',
    'Quality score for DNS servers',
    ['dns_server']
)

DNS_FLOOD_BLOCKED = Counter(
    'synergy_dns_flood_blocked_total',
    'DNS queries blocked by flood protection'
)

CIRCUIT_BREAKER_STATE = Gauge(
    'synergy_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['channel', 'domain']
)

KEY_ROTATION_COUNT = Counter(
    'synergy_key_rotation_total',
    'Number of API key rotations performed'
)

API_KEY_ERRORS = Counter(
    'synergy_api_key_errors_total',
    'API key errors (rate limit, auth failure)',
    ['key_index', 'error_type']
)


class ChannelState(Enum):
    HTTP_PREFERRED = 1
    DNS_FALLBACK = 2
    HYBRID_RETRY = 3


@dataclass
class ChannelResult:
    channel: str
    success: bool
    data: Any = None
    latency_ms: float = 0.0
    status_code: int = 0
    error: str = ""


@dataclass
class DomainPreference:
    domain: str
    http_successes: int = 0
    dns_successes: int = 0
    http_failures: int = 0
    dns_failures: int = 0
    preferred_channel: str = "http"
    last_updated: float = field(default_factory=time.time)


class OpenRouterKeyRotator:
    """
    Manages multiple OpenRouter API keys with automatic rotation on
    rate limits (429) or authentication errors (401/403).
    Uses round-robin with failover to ensure continuous availability.
    """

    def __init__(self, keys: List[str] = None, base_url: str = "https://openrouter.ai/api/v1"):
        self._keys: List[str] = keys or []
        self._current_index: int = 0
        self._base_url = base_url
        self._key_errors: Dict[int, int] = {}  # index -> error count
        self._key_cooldown: Dict[int, float] = {}  # index -> cooldown_until timestamp
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "OpenRouterKeyRotator":
        """Load keys from environment variables (OPENAI_API_KEY + OPENROUTER_KEY_N)."""
        keys = []
        primary = os.getenv("OPENAI_API_KEY")
        if primary:
            keys.append(primary)

        # Collect backup keys
        for i in range(1, 10):
            key = os.getenv(f"OPENROUTER_KEY_{i}")
            if key:
                keys.append(key)

        base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        return cls(keys=keys, base_url=base_url)

    @property
    def current_key(self) -> Optional[str]:
        """Get the current active API key."""
        with self._lock:
            return self._keys[self._current_index] if self._keys else None

    @property
    def base_url(self) -> str:
        return self._base_url

    def get_active_key(self) -> Optional[str]:
        """
        Get the best available key, skipping those in cooldown.
        Returns None if all keys are exhausted.
        """
        with self._lock:
            if not self._keys:
                return None

            now = time.time()
            # Try current key first
            if now >= self._key_cooldown.get(self._current_index, 0):
                return self._keys[self._current_index]

            # Current key is in cooldown, find next available
            for offset in range(len(self._keys)):
                idx = (self._current_index + offset) % len(self._keys)
                if now >= self._key_cooldown.get(idx, 0):
                    self._current_index = idx
                    KEY_ROTATION_COUNT.inc()
                    logger.info(f"Rotated to API key index {idx}")
                    return self._keys[idx]

            logger.warning("All API keys in cooldown")
            return None

    def report_error(self, status_code: int, error_type: str = "unknown"):
        """
        Report an API error for the current key.
        Triggers cooldown or rotation based on error type.
        """
        with self._lock:
            idx = self._current_index
            self._key_errors[idx] = self._key_errors.get(idx, 0) + 1
            API_KEY_ERRORS.labels(key_index=str(idx), error_type=error_type).inc()

            if status_code == 429:
                # Rate limited — cooldown for 60 seconds
                self._key_cooldown[idx] = time.time() + 60
                logger.warning(f"API key {idx} rate limited, cooldown 60s")
                self._rotate_to_next()
            elif status_code in (401, 403):
                # Auth failure — cooldown for 300 seconds
                self._key_cooldown[idx] = time.time() + 300
                logger.error(f"API key {idx} auth failed, cooldown 300s")
                self._rotate_to_next()
            else:
                # Other error — short cooldown
                self._key_cooldown[idx] = time.time() + 10
                self._rotate_to_next()

    def _rotate_to_next(self):
        """Rotate to the next available key."""
        if len(self._keys) <= 1:
            return
        now = time.time()
        for offset in range(1, len(self._keys)):
            idx = (self._current_index + offset) % len(self._keys)
            if now >= self._key_cooldown.get(idx, 0):
                self._current_index = idx
                KEY_ROTATION_COUNT.inc()
                logger.info(f"Rotated to API key index {idx}")
                return
        # All keys in cooldown, just rotate anyway
        self._current_index = (self._current_index + 1) % len(self._keys)
        KEY_ROTATION_COUNT.inc()

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    @property
    def available_keys(self) -> int:
        now = time.time()
        return sum(1 for i in range(len(self._keys))
                   if now >= self._key_cooldown.get(i, 0))

    def get_status(self) -> Dict[str, Any]:
        now = time.time()
        return {
            "total_keys": self.total_keys,
            "available_keys": self.available_keys,
            "current_index": self._current_index,
            "key_errors": dict(self._key_errors),
            "cooldowns": {
                i: max(0, self._key_cooldown.get(i, 0) - now)
                for i in range(len(self._keys))
            }
        }


class DNSFloodProtector:
    """Protects against DNS query flooding with configurable rate limits."""

    def __init__(self, max_qps: int = 50, burst: int = 100):
        self.max_qps = max_qps
        self.burst = burst
        self._tokens: float = float(burst)
        self._last_refill: float = time.time()
        self._lock = asyncio.Lock()
        self._blocked_count: int = 0
        # Per-client tracking
        self._client_queries: Dict[str, deque] = {}

    async def allow(self, client_ip: str = "default") -> bool:
        """Check if a DNS query is allowed under flood protection."""
        async with self._lock:
            now = time.time()

            # Global token bucket
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.max_qps)
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
            else:
                self._blocked_count += 1
                DNS_FLOOD_BLOCKED.inc()
                logger.warning(f"DNS flood protection: global query blocked (tokens={self._tokens:.1f})")
                return False

            # Per-client rate check (max 10 queries per second per client)
            if client_ip not in self._client_queries:
                self._client_queries[client_ip] = deque(maxlen=100)
            self._client_queries[client_ip].append(now)

            # Count queries in last second
            recent = sum(1 for t in self._client_queries[client_ip] if now - t < 1.0)
            if recent > 10:
                self._blocked_count += 1
                DNS_FLOOD_BLOCKED.inc()
                logger.warning(f"DNS flood protection: client {client_ip} rate exceeded ({recent} qps)")
                return False

            return True


class SmartChannelRouter:
    """
    Selects optimal access channel (HTTP proxy or DNS tunnel) based on
    real-time network conditions and learned preferences.

    v2 enhancements:
    - OpenRouter key rotation with automatic failover
    - Per-client DNS rate limiting
    - Enhanced Prometheus metrics
    - Configurable via environment variables
    """

    def __init__(self, config=None, http_client=None, dns_client=None):
        # Import here to avoid circular dependencies
        if config is None:
            from .config import SynergyConfig
            config = SynergyConfig()
        self.config = config

        # OWL-AGENT components
        from .core import (
            QualityScorer, AdaptiveRateLimiter, CircuitBreaker,
            HTTPCache, RequestDeduplicator, RedisStore,
            CB_FAILURE_THRESHOLD, CB_RECOVERY_TIMEOUT, DEFAULT_TTL,
        )
        self.scorer = QualityScorer()
        self.rate_limiter = AdaptiveRateLimiter()
        self.http_circuit = CircuitBreaker(
            failure_threshold=CB_FAILURE_THRESHOLD,
            recovery_timeout=CB_RECOVERY_TIMEOUT
        )
        self.dns_circuit = CircuitBreaker(
            failure_threshold=CB_FAILURE_THRESHOLD,
            recovery_timeout=CB_RECOVERY_TIMEOUT
        )
        self.cache = HTTPCache(ttl=self.config.cache_ttl)
        self.dedup = RequestDeduplicator()
        self.redis = RedisStore(url=self.config.redis_url) if self.config.use_redis else None

        # LLM-DNS-Proxy components
        from .core import CryptoManager, DNSChunker
        self.crypto = CryptoManager(config=self.config)
        self.chunker = DNSChunker(config=self.config)

        # OpenRouter key rotation
        self.key_rotator = OpenRouterKeyRotator.from_env()
        logger.info(f"API key rotator initialized with {self.key_rotator.total_keys} keys")

        # DNS flood protection
        self.flood_protector = DNSFloodProtector(
            max_qps=self.config.dns_flood_max_qps,
            burst=self.config.dns_flood_burst,
        )

        # Channel preference state
        self._prefs: Dict[str, DomainPreference] = {}
        self._state: Dict[str, ChannelState] = {}

        # External client references
        self.http_client = http_client
        self.dns_client = dns_client

    async def initialize(self):
        """Start background services: cache cleaner, Redis, Prometheus."""
        await self.cache.start_cleaner()
        if self.redis:
            await self.redis.connect()
        # Start Prometheus metrics server
        try:
            start_http_server(self.config.prometheus_port)
            logger.info(f"Prometheus metrics on port {self.config.prometheus_port}")
        except OSError:
            logger.warning(f"Prometheus port {self.config.prometheus_port} already in use")

    def _extract_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.hostname or url

    def _get_state(self, domain: str) -> ChannelState:
        return self._state.get(domain, ChannelState.HTTP_PREFERRED)

    def _set_state(self, domain: str, state: ChannelState):
        old = self._state.get(domain)
        self._state[domain] = state
        if old and old != state:
            old_ch = "http" if old == ChannelState.HTTP_PREFERRED else "dns"
            new_ch = "http" if state == ChannelState.HTTP_PREFERRED else "dns"
            CHANNEL_SWITCHES.labels(from_channel=old_ch, to_channel=new_ch).inc()

    def _record_success(self, domain: str, channel: str, latency_ms: float = 0.0):
        pref = self._prefs.setdefault(domain, DomainPreference(domain))
        if channel == "http":
            pref.http_successes += 1
            self.scorer.update(f"http:{domain}", True, latency_ms)
            PROXY_QUALITY_SCORE.labels(proxy_url=domain).set(self.scorer.get_score(f"http:{domain}"))
        else:
            pref.dns_successes += 1
            self.scorer.update(f"dns:{domain}", True, latency_ms)
            DNS_SERVER_QUALITY_SCORE.labels(dns_server=domain).set(
                self.scorer.get_score(f"dns:{domain}"))
        pref.preferred_channel = "http" if pref.http_successes >= pref.dns_successes else "dns"
        pref.last_updated = time.time()
        if self.redis:
            self.redis.set(f"pref:{domain}", pref.__dict__)

    def _record_failure(self, domain: str, channel: str):
        pref = self._prefs.setdefault(domain, DomainPreference(domain))
        if channel == "http":
            pref.http_failures += 1
            self.scorer.update(f"http:{domain}", False)
        else:
            pref.dns_failures += 1
            self.scorer.update(f"dns:{domain}", False)

    async def fetch(self, url: str, **kwargs) -> ChannelResult:
        """Fetch a URL through the optimal channel with automatic fallback."""
        domain = self._extract_domain(url)
        state = self._get_state(domain)

        # Check cache first
        cached = await self.cache.get("GET", url)
        if cached and cached.is_fresh():
            REQUESTS_TOTAL.labels(channel="cache", domain=domain, status="cached").inc()
            return ChannelResult("cache", True, data=cached.content, status_code=cached.status)

        if state == ChannelState.HTTP_PREFERRED:
            result = await self._try_http(url, domain, **kwargs)
            if result.success:
                self._record_success(domain, "http", result.latency_ms)
                return result
            # HTTP failed — try DNS
            dns_result = await self._try_dns(url, domain, **kwargs)
            if dns_result.success:
                self._record_success(domain, "dns", dns_result.latency_ms)
                self._set_state(domain, ChannelState.DNS_FALLBACK)
                return dns_result
            # Both failed — hybrid
            self._set_state(domain, ChannelState.HYBRID_RETRY)
            return await self._hybrid_retry(url, domain, **kwargs)

        elif state == ChannelState.DNS_FALLBACK:
            result = await self._try_dns(url, domain, **kwargs)
            if result.success:
                self._record_success(domain, "dns", result.latency_ms)
                return result
            http_result = await self._try_http(url, domain, **kwargs)
            if http_result.success:
                self._record_success(domain, "http", http_result.latency_ms)
                self._set_state(domain, ChannelState.HTTP_PREFERRED)
                return http_result
            self._set_state(domain, ChannelState.HYBRID_RETRY)
            return await self._hybrid_retry(url, domain, **kwargs)

        else:  # HYBRID_RETRY
            return await self._hybrid_retry(url, domain, **kwargs)

    async def _try_http(self, url: str, domain: str, **kwargs) -> ChannelResult:
        """Attempt HTTP proxy channel with key rotation support."""
        import httpx
        start_time = time.time()
        ACTIVE_CONNECTIONS.labels(channel="http").inc()
        try:
            # Use rotated API key if available
            api_key = self.key_rotator.get_active_key()
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=30.0, headers=headers)
                data = resp.content

                # Handle API key errors
                if resp.status_code in (401, 403, 429):
                    self.key_rotator.report_error(
                        resp.status_code,
                        "rate_limit" if resp.status_code == 429 else "auth_error"
                    )

            latency = (time.time() - start_time) * 1000
            status = resp.status_code
            REQUESTS_TOTAL.labels(channel="http", domain=domain, status="success").inc()
            REQUESTS_DURATION.labels(channel="http", domain=domain).observe(time.time() - start_time)
            CIRCUIT_BREAKER_STATE.labels(channel="http", domain=domain).set(0)

            # Cache successful response
            from .core import CachedResponse
            cached = CachedResponse(
                status=status,
                content=data if isinstance(data, bytes) else data.encode(),
                headers=dict(resp.headers),
                timestamp=time.time(),
                ttl=self.config.cache_ttl,
            )
            await self.cache.set("GET", url, cached)

            return ChannelResult("http", True, data=data, latency_ms=latency, status_code=status)

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self._record_failure(domain, "http")
            REQUESTS_TOTAL.labels(channel="http", domain=domain, status="failure").inc()
            CIRCUIT_BREAKER_STATE.labels(channel="http", domain=domain).set(1)
            await self.rate_limiter.adjust(domain, 429)
            return ChannelResult("http", False, error=str(e), latency_ms=latency)

        finally:
            ACTIVE_CONNECTIONS.labels(channel="http").dec()

    async def _try_dns(self, url: str, domain: str, client_ip: str = "default", **kwargs) -> ChannelResult:
        """Attempt DNS tunnel channel with flood protection."""
        # DNS flood protection check
        if not await self.flood_protector.allow(client_ip):
            return ChannelResult("dns", False, error="DNS flood protection: query rate exceeded")

        start_time = time.time()
        ACTIVE_CONNECTIONS.labels(channel="dns").inc()
        try:
            if self.dns_client:
                data = await self.dns_client.chat(f"Fetch and summarize: {url}", **kwargs)
            else:
                # Placeholder: DNS client would tunnel LLM request
                data = f"[DNS tunneled response for {url}]"

            latency = (time.time() - start_time) * 1000
            REQUESTS_TOTAL.labels(channel="dns", domain=domain, status="success").inc()
            REQUESTS_DURATION.labels(channel="dns", domain=domain).observe(time.time() - start_time)
            CIRCUIT_BREAKER_STATE.labels(channel="dns", domain=domain).set(0)

            return ChannelResult("dns", True, data=data, latency_ms=latency, status_code=200)

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self._record_failure(domain, "dns")
            REQUESTS_TOTAL.labels(channel="dns", domain=domain, status="failure").inc()
            CIRCUIT_BREAKER_STATE.labels(channel="dns", domain=domain).set(1)
            return ChannelResult("dns", False, error=str(e), latency_ms=latency)

        finally:
            ACTIVE_CONNECTIONS.labels(channel="dns").dec()

    async def _hybrid_retry(self, url: str, domain: str, max_retries: int = 3, **kwargs) -> ChannelResult:
        """Alternate between HTTP and DNS with exponential backoff."""
        for i in range(max_retries):
            await asyncio.sleep(2 ** i)
            for channel_fn in [self._try_http, self._try_dns]:
                result = await channel_fn(url, domain, **kwargs)
                if result.success:
                    ch = result.channel
                    self._record_success(domain, ch, result.latency_ms)
                    new_state = ChannelState.HTTP_PREFERRED if ch == "http" else ChannelState.DNS_FALLBACK
                    self._set_state(domain, new_state)
                    return result

        REQUESTS_TOTAL.labels(channel="none", domain=domain, status="all_failed").inc()
        return ChannelResult("none", False, error=f"All channels exhausted for {domain}")

    def get_channel_stats(self) -> Dict[str, Any]:
        """Get current channel statistics for monitoring."""
        return {
            "preferences": {d: {"http_succ": p.http_successes, "dns_succ": p.dns_successes,
                                "http_fail": p.http_failures, "dns_fail": p.dns_failures,
                                "preferred": p.preferred_channel}
                           for d, p in self._prefs.items()},
            "states": {d: s.name for d, s in self._state.items()},
            "quality_scores": self.scorer.get_all_scores(),
            "flood_blocked": self.flood_protector._blocked_count,
            "key_rotator": self.key_rotator.get_status(),
        }
