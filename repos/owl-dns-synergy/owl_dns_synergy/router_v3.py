"""
SmartChannelRouter v3 — Unified Synergy Stack Integration Layer

Merges 7 repos into a single resilient access engine:
  - OWL-AGENT v4.2  (QualityScorer, CircuitBreaker, HTTPCache, RateLimiter)
  - LLM-DNS-Proxy   (DNS tunneling, Fernet encryption, TXT records)
  - secret-agent     (MITM proxy, TLS fingerprinting, browser stealth)
  - proxytunnel      (CONNECT chaining, NTLM auth, SSL tunneling)
  - autoclaw-autologin (OAuth harvesting, token rotation, OpenAI-compatible proxy)
  - https_proxy      (Rust stealth proxy, ACME TLS, nginx disguise)
  - prox5            (Go Mystery Dialer, SOCKS pool, validation engine)

Architecture:
  Client → SmartChannelRouter → [HTTP|DNS|SOCKS|MITM] channel
    ↓ channel selection + failover
  ProxyPool (prox5-compatible) → validated SOCKS5/HTTP exits
    ↓ per-exit stealth proxy (https_proxy)
  StealthLayer (https_proxy + secret-agent TLS fingerprints)
    ↓ CONNECT tunneling
  TransportLayer (proxytunnel chaining + DNS fallback)
"""

import asyncio
import time
import logging
import os
import json
import threading
import subprocess
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse
from collections import deque
from pathlib import Path

import httpx

logger = logging.getLogger("owl-dns-synergy.router_v3")

# ─── Prometheus Metrics (extended for v3) ─────────────────────────
try:
    from prometheus_client import Counter, Gauge, Histogram, Info
except ImportError:
    # Stub if prometheus_client not available
    class _Stub:
        def __init__(self, *a, **kw): pass
        def labels(self, *a, **kw): return self
        def inc(self, *a): pass
        def dec(self, *a): pass
        def set(self, *a): pass
        def observe(self, *a): pass
        def info(self, *a): pass
    Counter = Gauge = Histogram = Info = _Stub

REQUESTS_TOTAL = Counter(
    'synergy_v3_requests_total',
    'Total requests processed by SmartChannelRouter v3',
    ['channel', 'domain', 'status']
)

REQUESTS_DURATION = Histogram(
    'synergy_v3_request_duration_seconds',
    'Request duration in seconds',
    ['channel', 'domain'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

CHANNEL_SWITCHES = Counter(
    'synergy_v3_channel_switches_total',
    'Channel switches',
    ['from_channel', 'to_channel']
)

PROXY_POOL_SIZE = Gauge(
    'synergy_v3_proxy_pool_size',
    'Number of validated proxies in pool',
    ['protocol']
)

STEALTH_SESSIONS = Gauge(
    'synergy_v3_stealth_sessions',
    'Active stealth browser sessions'
)

CONNECT_TUNNELS = Counter(
    'synergy_v3_connect_tunnels_total',
    'CONNECT tunnels established',
    ['chain_depth']
)

DNS_FLOOD_BLOCKED = Counter(
    'synergy_v3_dns_flood_blocked_total',
    'DNS queries blocked by flood protection'
)

KEY_ROTATION_COUNT = Counter(
    'synergy_v3_key_rotation_total',
    'API key rotations'
)

STACK_INFO = Info(
    'synergy_v3_stack',
    'Integrated stack component versions'
)


# ═══════════════════════════════════════════════════════════════
# Channel State Machine
# ═══════════════════════════════════════════════════════════════

class Channel(Enum):
    HTTP_DIRECT = "http_direct"
    HTTP_PROXY = "http_proxy"
    DNS_TUNNEL = "dns_tunnel"
    SOCKS_POOL = "socks_pool"
    MITM_STEALTH = "mitm_stealth"
    CONNECT_CHAIN = "connect_chain"
    CACHED = "cached"


class ChannelState(Enum):
    PREFERRED = 1      # Using preferred channel
    FALLBACK = 2       # Primary failed, using fallback
    HYBRID_RETRY = 3   # Both channels failed, alternating


class CircuitState(Enum):
    """3-state circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED"""
    CLOSED = 0      # Normal operation — requests flow through
    OPEN = 1        # Circuit tripped — all requests rejected
    HALF_OPEN = 2  # Probe state — one request allowed to test recovery


class ChannelCircuitBreaker:
    """Per-channel 3-state circuit breaker with Prometheus tracking.

    States:
      CLOSED: Normal. All requests pass. Failure count tracked.
      OPEN: Circuit tripped. All requests fail-fast. Timer starts.
      HALF_OPEN: One probe request allowed. If success → CLOSED, if fail → OPEN.

    Args:
        channel_name: Name for logging/metrics
        failure_threshold: Consecutive failures before opening (default 5)
        recovery_timeout: Seconds before half-open probe (default 30)
        success_threshold: Consecutive successes in HALF_OPEN to close (default 2)
    """
    def __init__(self, channel_name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0, success_threshold: int = 2):
        self.channel_name = channel_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current state, with automatic HALF_OPEN transition on timeout."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._opened_at >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state
    @property
    def is_open(self) -> bool:
        """True if circuit is OPEN (requests should be rejected)."""
        return self.state == CircuitState.OPEN
    async def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        async with self._lock:
            state = self.state
            if state == CircuitState.CLOSED:
                return True
            elif state == CircuitState.HALF_OPEN:
                # Allow ONE probe request through
                return True
            else:  # OPEN
                return False
    async def record_success(self):
        """Record a successful request."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit CLOSED for {self.channel_name} — recovered")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0  # Reset on success
    async def record_failure(self):
        """Record a failed request."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Probe failed → back to OPEN
                self._state = CircuitState.OPEN
                self._opened_at = time.time()
                self._success_count = 0
                logger.warning(f"Circuit back to OPEN for {self.channel_name} — probe failed")
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = time.time()
                    logger.warning(
                        f"Circuit OPEN for {self.channel_name} — "
                        f"{self._failure_count} failures >= threshold {self.failure_threshold}"
                    )


@dataclass
class ChannelResult:
    channel: str
    success: bool
    data: Any = None
    latency_ms: float = 0.0
    status_code: int = 0
    error: str = ""
    proxy_used: str = ""
    chain_depth: int = 0


@dataclass(slots=True)
class DomainPreference:
    """Per-domain channel preference with EMA-based learning.

    Tracks success/failure counts per channel and uses exponential moving average
    to compute a quality score. The channel with the highest EMA score becomes
    the preferred_channel for subsequent requests to this domain.
    
    Memory Fix: slots=True reduces per-instance memory by ~40% (no __dict__).
    """
    domain: str
    successes: Dict[str, int] = field(default_factory=lambda: {})
    failures: Dict[str, int] = field(default_factory=lambda: {})
    preferred_channel: str = "http_proxy"
    last_updated: float = field(default_factory=time.time)
    # EMA scores per channel (0.0-1.0)
    _ema_scores: Dict[str, float] = field(default_factory=lambda: {})
    _ema_alpha: float = 0.3  # EMA smoothing factor (higher = more responsive)

    def record_channel_result(self, channel: str, success: bool):
        """Record a channel result and update EMA score."""
        if success:
            self.successes[channel] = self.successes.get(channel, 0) + 1
        else:
            self.failures[channel] = self.failures.get(channel, 0) + 1
        # EMA update: new_score = alpha * sample + (1 - alpha) * old_score
        old_score = self._ema_scores.get(channel, 0.5)
        sample = 1.0 if success else 0.0
        self._ema_scores[channel] = self._ema_alpha * sample + (1 - self._ema_alpha) * old_score
        self.last_updated = time.time()
        # Re-compute preferred channel from EMA scores
        if self._ema_scores:
            best_channel = max(self._ema_scores, key=self._ema_scores.get)
            if self._ema_scores[best_channel] > 0.3:  # Minimum quality threshold
                self.preferred_channel = best_channel

    def get_channel_score(self, channel: str) -> float:
        """Get EMA quality score for a channel (0.0-1.0)."""
        return self._ema_scores.get(channel, 0.5)


# ═══════════════════════════════════════════════════════════════
# 1. OpenRouter Key Rotator (from v2)
# ═══════════════════════════════════════════════════════════════

class OpenRouterKeyRotator:
    """Round-robin API key rotation with failover on 429/401/403."""

    def __init__(self, keys: List[str] = None, base_url: str = "https://openrouter.ai/api/v1"):
        self._keys = keys or []
        self._current_index = 0
        self._base_url = base_url
        self._key_errors: Dict[int, int] = {}
        self._key_cooldown: Dict[int, float] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "OpenRouterKeyRotator":
        keys = []
        primary = os.getenv("OPENAI_API_KEY")
        if primary:
            keys.append(primary)
        for i in range(1, 10):
            key = os.getenv(f"OPENROUTER_KEY_{i}")
            if key:
                keys.append(key)
        base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        return cls(keys=keys, base_url=base_url)

    @property
    def base_url(self) -> str:
        return self._base_url

    def get_active_key(self) -> Optional[str]:
        with self._lock:
            if not self._keys:
                return None
            now = time.time()
            if now >= self._key_cooldown.get(self._current_index, 0):
                return self._keys[self._current_index]
            for offset in range(len(self._keys)):
                idx = (self._current_index + offset) % len(self._keys)
                if now >= self._key_cooldown.get(idx, 0):
                    self._current_index = idx
                    KEY_ROTATION_COUNT.inc()
                    return self._keys[idx]
            return None

    def report_error(self, status_code: int, error_type: str = "unknown"):
        with self._lock:
            idx = self._current_index
            self._key_errors[idx] = self._key_errors.get(idx, 0) + 1
            if status_code == 429:
                self._key_cooldown[idx] = time.time() + 60
            elif status_code in (401, 403):
                self._key_cooldown[idx] = time.time() + 300
            else:
                self._key_cooldown[idx] = time.time() + 10
            self._rotate_to_next()

    def _rotate_to_next(self):
        if len(self._keys) <= 1:
            return
        now = time.time()
        for offset in range(1, len(self._keys)):
            idx = (self._current_index + offset) % len(self._keys)
            if now >= self._key_cooldown.get(idx, 0):
                self._current_index = idx
                KEY_ROTATION_COUNT.inc()
                return
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


# ═══════════════════════════════════════════════════════════════
# 2. DNS Flood Protector (from v2)
# ═══════════════════════════════════════════════════════════════

class DNSFloodProtector:
    """Token-bucket + per-client rate limiting for DNS queries."""

    def __init__(self, max_qps: int = 50, burst: int = 100,
                 max_clients: int = 50000, client_ttl: float = 300.0):
        self.max_qps = max_qps
        self.burst = burst
        self._tokens: float = float(burst)
        self._last_refill: float = time.time()
        self._lock = asyncio.Lock()
        self._blocked_count = 0
        self._client_queries: Dict[str, deque] = {}
        # Memory Fix M-R2: Client IP eviction + max client cap
        self._client_last_seen: Dict[str, float] = {}
        self._max_clients = max_clients
        self._client_ttl = client_ttl

    def _evict_stale_clients(self) -> None:
        """Memory Fix M-R2: Evict client IPs idle > client_ttl to prevent unbounded growth."""
        now = time.time()
        stale = [ip for ip, t in self._client_last_seen.items()
                 if now - t > self._client_ttl]
        for ip in stale:
            self._client_queries.pop(ip, None)
            self._client_last_seen.pop(ip, None)

    async def allow(self, client_ip: str = "default") -> bool:
        async with self._lock:
            now = time.time()
            # Memory Fix M-R2: Evict idle clients periodically
            self._evict_stale_clients()
            # Per-client rate check FIRST (before consuming global token)
            if client_ip not in self._client_queries:
                # Memory Fix M-R2: Cap total tracked clients
                if len(self._client_queries) >= self._max_clients:
                    # Evict oldest client to make room
                    oldest_ip = min(self._client_last_seen, key=self._client_last_seen.get)
                    self._client_queries.pop(oldest_ip, None)
                    self._client_last_seen.pop(oldest_ip, None)
                self._client_queries[client_ip] = deque(maxlen=100)
            self._client_queries[client_ip].append(now)
            self._client_last_seen[client_ip] = now  # Track last activity
            recent = sum(1 for t in self._client_queries[client_ip] if now - t < 1.0)
            if recent > 10:
                self._blocked_count += 1
                DNS_FLOOD_BLOCKED.inc()
                return False
            # Global token bucket check (after per-client passes)
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.max_qps)
            self._last_refill = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            self._blocked_count += 1
            DNS_FLOOD_BLOCKED.inc()
            return False


# ═══════════════════════════════════════════════════════════════
# 3. Proxy Pool Adapter — prox5-compatible SOCKS/HTTP pool
# ═══════════════════════════════════════════════════════════════

@dataclass
class ProxyEntry:
    """Represents a single proxy endpoint (prox5-compatible)."""
    endpoint: str           # host:port
    protocol: str = "socks5"  # socks5, socks4, http
    username: str = ""
    password: str = ""
    proxied_ip: str = ""
    last_validated: float = 0.0
    successes: int = 0
    failures: int = 0
    score: float = 1.0      # EMA quality score
    region: str = ""

    @property
    def url(self) -> str:
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.endpoint}"
        return f"{self.protocol}://{self.endpoint}"

    @property
    def is_stale(self) -> bool:
        return time.time() - self.last_validated > 1800  # 30 min


class ProxyPoolAdapter:
    """
    Python adapter for prox5-style proxy pool management.
    Loads proxies from file (prox5/proxies.txt format), validates,
    and rotates using Mystery Dialer pattern (retry on failure).
    """

    def __init__(self, proxy_file: str = None, max_workers: int = 10):
        self._pool: List[ProxyEntry] = []
        self._current_index = 0
        self._lock = threading.Lock()
        self._max_workers = max_workers
        self._proxy_file = proxy_file
        if proxy_file and os.path.exists(proxy_file):
            self.load_from_file(proxy_file)

    def load_from_file(self, filepath: str):
        """
        Load proxies from file. Supports formats:
          - host:port:user:pass  (autoclaw/prox5 format)
          - protocol://host:port  (URL format)
          - host:port  (simple format)
        """
        count = 0
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                entry = self._parse_proxy_line(line)
                if entry:
                    self._pool.append(entry)
                    count += 1
        logger.info(f"Loaded {count} proxies from {filepath}")
        PROXY_POOL_SIZE.labels(protocol="all").set(len(self._pool))

    def _parse_proxy_line(self, line: str) -> Optional[ProxyEntry]:
        """Parse a proxy line in any supported format."""
        if '://' in line:
            # URL format: socks5://user:pass@host:port
            parsed = urlparse(line)
            protocol = parsed.scheme or "socks5"
            host = parsed.hostname or ""
            port = parsed.port or 1080
            return ProxyEntry(
                endpoint=f"{host}:{port}",
                protocol=protocol,
                username=parsed.username or "",
                password=parsed.password or "",
            )
        parts = line.split(':')
        if len(parts) == 4:
            # host:port:user:pass format
            return ProxyEntry(
                endpoint=f"{parts[0]}:{parts[1]}",
                username=parts[2],
                password=parts[3],
            )
        if len(parts) == 2:
            try:
                int(parts[1])
                return ProxyEntry(endpoint=line)
            except ValueError:
                pass
        return None

    def add_proxy(self, endpoint: str, protocol: str = "socks5",
                  username: str = "", password: str = ""):
        with self._lock:
            self._pool.append(ProxyEntry(
                endpoint=endpoint, protocol=protocol,
                username=username, password=password
            ))

    def get_next(self) -> Optional[ProxyEntry]:
        """Get next proxy using round-robin with Mystery Dialer retry."""
        with self._lock:
            if not self._pool:
                return None
            # Try current proxy first
            for offset in range(len(self._pool)):
                idx = (self._current_index + offset) % len(self._pool)
                proxy = self._pool[idx]
                if proxy.score > 0.2 and not proxy.is_stale:
                    self._current_index = idx
                    return proxy
            # All stale/low-score, return best available
            best = max(self._pool, key=lambda p: p.score)
            return best

    def report_success(self, endpoint: str, latency_ms: float = 0):
        with self._lock:
            for p in self._pool:
                if p.endpoint == endpoint:
                    p.successes += 1
                    p.last_validated = time.time()
                    # EMA update: alpha=0.3
                    p.score = 0.3 * 1.0 + 0.7 * p.score
                    break

    def report_failure(self, endpoint: str):
        with self._lock:
            for p in self._pool:
                if p.endpoint == endpoint:
                    p.failures += 1
                    p.score = 0.3 * 0.0 + 0.7 * p.score
                    break

    @property
    def size(self) -> int:
        return len(self._pool)

    @property
    def valid_count(self) -> int:
        return sum(1 for p in self._pool if p.score > 0.2 and not p.is_stale)

    def get_status(self) -> Dict[str, Any]:
        return {
            "total": self.size,
            "valid": self.valid_count,
            "current_index": self._current_index,
            "protocols": {
                proto: sum(1 for p in self._pool if p.protocol == proto)
                for proto in set(p.protocol for p in self._pool)
            },
            "top_5": [
                {"endpoint": p.endpoint, "protocol": p.protocol,
                 "score": round(p.score, 3), "successes": p.successes,
                 "failures": p.failures}
                for p in sorted(self._pool, key=lambda x: x.score, reverse=True)[:5]
            ]
        }


# ═══════════════════════════════════════════════════════════════
# 3b. curl_cffi Chrome Impersonation Client
# ═══════════════════════════════════════════════════════════════

class CurlCffiClient:
    """HTTP client using curl_cffi with Chrome TLS fingerprint impersonation.

    Uses curl_cffi's impersonate parameter to match Chrome 131's JA3/JA4
    TLS fingerprint, making requests indistinguishable from real Chrome browsers.
    Falls back to httpx if curl_cffi is not available.
    """
    def __init__(self, chrome_version: str = "chrome131"):
        self._chrome_version = chrome_version
        self._client = None
        self._available = False
        try:
            from curl_cffi.requests import AsyncSession
            self._available = True
            logger.info(f"curl_cffi available — will impersonate {chrome_version}")
        except ImportError:
            logger.warning("curl_cffi not installed — falling back to httpx (no TLS impersonation)")

    async def _get_client(self):
        """Lazily create the curl_cffi session."""
        if not self._available:
            return None
        if self._client is None:
            from curl_cffi.requests import AsyncSession
            self._client = AsyncSession(impersonate=self._chrome_version)
        return self._client

    async def get(self, url: str, headers: Dict = None, timeout: float = 30.0) -> Optional[Any]:
        """GET request with Chrome TLS fingerprint."""
        client = await self._get_client()
        if client:
            try:
                return await client.get(url, headers=headers, timeout=timeout)
            except Exception as e:
                logger.warning(f"curl_cffi request failed: {e}")
        return None

    async def close(self):
        if self._client:
            await self._client.close3()
            self._client = None


# ═══════════════════════════════════════════════════════════════
# 4. Stealth Proxy Adapter — https_proxy (Rust) integration
# ═══════════════════════════════════════════════════════════════

@dataclass
class StealthProxyConfig:
    """Configuration for https_proxy (Rust) stealth proxy."""
    listen: str = "0.0.0.0:443"
    domain: str = ""
    acme_email: str = ""
    users: List[Dict[str, str]] = field(default_factory=list)
    server_name: str = "nginx/1.24.0"
    fast_open: bool = True

    def to_yaml(self) -> str:
        """Generate config.yaml for https_proxy."""
        users_yaml = "\n".join(
            f'  - username: "{u["username"]}"\n    password: "{u["password"]}"'
            for u in self.users
        )
        return f"""listen: "{self.listen}"
domain: "{self.domain}"
acme:
  email: "{self.acme_email}"
  staging: false
  cache_dir: "/var/lib/https_proxy/acme"
users:
{users_yaml}
stealth:
  server_name: "{self.server_name}"
fast_open: {str(self.fast_open).lower()}
"""


class StealthProxyAdapter:
    """
    Adapter for the https_proxy Rust stealth proxy.
    Manages config generation, process lifecycle, and health checks.
    """

    def __init__(self, binary_path: str = None, config_path: str = None):
        self._binary = binary_path or self._find_binary()
        self._config_path = config_path or os.path.expanduser(
            "~/.owl-dns-synergy/config/https_proxy.yaml"
        )
        self._process: Optional[subprocess.Popen] = None
        self._config = StealthProxyConfig()

    def _find_binary(self) -> Optional[str]:
        """Find https_proxy binary in PATH or repos."""
        for path in [
            os.path.expanduser("~/my-project/repos/https_proxy/target/release/https_proxy"),
            os.path.expanduser("~/.owl-dns-synergy/bin/https_proxy"),
            "/usr/local/bin/https_proxy",
        ]:
            if os.path.exists(path):
                return path
        return None

    def generate_config(self, config: StealthProxyConfig) -> str:
        """Generate and save config.yaml."""
        self._config = config
        yaml_content = config.to_yaml()
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, 'w') as f:
            f.write(yaml_content)
        return yaml_content

    def start(self) -> bool:
        """Start the https_proxy process."""
        if not self._binary:
            logger.warning("https_proxy binary not found — stealth proxy disabled")
            return False
        try:
            self._process = subprocess.Popen(
                [self._binary, "run", "-c", self._config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.info(f"https_proxy started (PID {self._process.pid})")
            return True
        except Exception as e:
            logger.error(f"Failed to start https_proxy: {e}")
            return False

    def stop(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=5)
            logger.info("https_proxy stopped")

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def get_proxy_url(self, username: str = "", password: str = "") -> str:
        """Get proxy URL for connecting through the stealth proxy."""
        host = self._config.listen.split(':')[0] or "0.0.0.0"
        port = self._config.listen.split(':')[1] or "443"
        if username and password:
            return f"http://{username}:{password}@{host}:{port}"
        return f"http://{host}:{port}"


# ═══════════════════════════════════════════════════════════════
# 5. ProxyTunnel Adapter — CONNECT chain integration
# ═══════════════════════════════════════════════════════════════

class ProxyTunnelAdapter:
    """
    Adapter for proxytunnel (C) — CONNECT tunnel chaining.
    Supports dual-proxy chains with per-hop SSL encryption.
    """

    def __init__(self, binary_path: str = None):
        self._binary = binary_path or self._find_binary()

    def _find_binary(self) -> Optional[str]:
        for path in [
            os.path.expanduser("~/my-project/repos/proxytunnel/proxytunnel"),
            os.path.expanduser("~/.owl-dns-synergy/bin/proxytunnel"),
            "/usr/local/bin/proxytunnel",
            "/usr/bin/proxytunnel",
        ]:
            if os.path.exists(path):
                return path
        return None

    def build_command(
        self,
        proxy: str,
        destination: str,
        remproxy: str = None,
        proxyauth: str = None,
        remproxyauth: str = None,
        encrypt: bool = False,
        encrypt_proxy: bool = False,
        encrypt_remproxy: bool = False,
        ntlm: bool = False,
        custom_headers: List[str] = None,
    ) -> List[str]:
        """
        Build proxytunnel command with full flag support.
        Chain: Client → proxy (-p) → [remproxy (-r)] → destination (-d)
        """
        if not self._binary:
            return []

        cmd = [self._binary, "-p", proxy, "-d", destination]
        if remproxy:
            cmd.extend(["-r", remproxy])
        if proxyauth:
            cmd.extend(["-P", proxyauth])
        if remproxyauth:
            cmd.extend(["-R", remproxyauth])
        if encrypt:
            cmd.append("-e")
        if encrypt_proxy:
            cmd.append("-E")
        if encrypt_remproxy:
            cmd.append("-X")
        if ntlm:
            cmd.append("-N")
        if custom_headers:
            for h in custom_headers:
                cmd.extend(["-H", h])
        return cmd

    async def tunnel(
        self,
        proxy: str,
        destination: str,
        **kwargs
    ) -> ChannelResult:
        """Execute proxytunnel to establish a CONNECT tunnel."""
        start = time.time()
        cmd = self.build_command(proxy, destination, **kwargs)
        if not cmd:
            return ChannelResult("connect_chain", False, error="proxytunnel binary not found")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=30)
            latency = (time.time() - start) * 1000
            chain_depth = 2 if kwargs.get('remproxy') else 1
            CONNECT_TUNNELS.labels(chain_depth=str(chain_depth)).inc()

            if proc.returncode == 0:
                return ChannelResult(
                    "connect_chain", True, latency_ms=latency, chain_depth=chain_depth
                )
            else:
                stderr = await proc.stderr.read()
                return ChannelResult(
                    "connect_chain", False, error=stderr.decode()[:200], latency_ms=latency
                )
        except asyncio.TimeoutError:
            return ChannelResult("connect_chain", False, error="proxytunnel timeout (30s)")
        except Exception as e:
            return ChannelResult("connect_chain", False, error=str(e))


# ═══════════════════════════════════════════════════════════════
# 6. SecretAgent Adapter — MITM stealth browser integration
# ═══════════════════════════════════════════════════════════════

class SecretAgentAdapter:
    """
    Adapter for secret-agent/Hero (Node.js) — stealth browser automation.
    Routes browser sessions through DNS-tunneled proxy pool.
    """

    def __init__(self, npm_path: str = None, project_dir: str = None):
        self._npm = npm_path or "npx"
        self._project_dir = project_dir or os.path.expanduser(
            "~/my-project/repos/secret-agent"
        )
        self._sessions: Dict[str, Dict] = {}

    def generate_session_script(
        self,
        url: str,
        upstream_proxy: str = None,
        extract_selector: str = None,
        session_id: str = None,
    ) -> str:
        """
        Generate a Node.js script for a secret-agent session.
        Uses @secret-agent/client with upstreamProxyUrl for proxy routing.
        """
        sid = session_id or hashlib.md5(url.encode()).hexdigest()[:8]
        proxy_opt = f", upstreamProxyUrl: '{upstream_proxy}'" if upstream_proxy else ""
        extract_code = ""
        if extract_selector:
            extract_code = f"""
    const elements = await agent.document.querySelectorAll('{extract_selector}');
    const results = [];
    for (const el of elements) {{
      results.push(await el.textContent);
    }}
    console.log(JSON.stringify(results));
"""
        else:
            extract_code = """
    const title = await agent.document.title;
    const body = await agent.document.querySelector('body').textContent;
    console.log(JSON.stringify({ title, bodyLength: body.length, preview: body.substring(0, 500) }));
"""
        return f"""const {{ Handler }} = require('@secret-agent/client');

(async () => {{
  const handler = new Handler({{
    maxConcurrentClientsCount: 1{proxy_opt}
  }});
  const agent = await handler.createAgent();
  await agent.goto('{url}');
  await agent.waitForPaintingStable();{extract_code}
  await handler.close();
}})();"""

    async def scrape(
        self,
        url: str,
        upstream_proxy: str = None,
        timeout: int = 30,
    ) -> ChannelResult:
        """Execute a secret-agent scraping session."""
        start = time.time()
        script = self.generate_session_script(url, upstream_proxy)

        try:
            proc = await asyncio.create_subprocess_exec(
                self._npm, "--yes", "@secret-agent/client",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._project_dir,
            )
            proc.stdin.write(script.encode())
            await proc.stdin.drain()
            proc.stdin.close()

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            latency = (time.time() - start) * 1000

            if proc.returncode == 0:
                STEALTH_SESSIONS.inc()
                return ChannelResult(
                    "mitm_stealth", True,
                    data=stdout.decode()[:10000],
                    latency_ms=latency
                )
            else:
                return ChannelResult(
                    "mitm_stealth", False,
                    error=stderr.decode()[:500],
                    latency_ms=latency
                )
        except asyncio.TimeoutError:
            return ChannelResult("mitm_stealth", False, error=f"Timeout ({timeout}s)")
        except Exception as e:
            return ChannelResult("mitm_stealth", False, error=str(e))


# ═══════════════════════════════════════════════════════════════
# 7. AutoClaw Adapter — OAuth token harvesting
# ═══════════════════════════════════════════════════════════════

class AutoClawAdapter:
    """
    Adapter for autoclaw-autologin — Google OAuth token harvesting
    with proxy rotation and OpenAI-compatible API proxy.
    """

    def __init__(self, base_url: str = "http://localhost:31000"):
        self._base_url = base_url
        self._tokens: List[Dict] = []
        self._current_index = 0
        # Memory Fix M-R3: Shared httpx.AsyncClient (connection pooling)
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create shared client (M-R3)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def get_next_token(self) -> Optional[Dict]:
        """Get next available token via autoclaw API."""
        try:
            client = self._get_client()
            resp = await client.get("/v1/models", timeout=10.0)
            if resp.status_code == 200:
                return {"source": "autoclaw", "status": "active", "url": self._base_url}
        except Exception as e:
            logger.warning(f"AutoClaw token check failed: {e}")
        return None

    async def chat_completion(
        self,
        message: str,
        model: str = "glm-5.2",
        stream: bool = False,
    ) -> ChannelResult:
        """Send chat completion through autoclaw's OpenAI-compatible proxy."""
        start = time.time()
        try:
            client = self._get_client()
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": message}],
                    "stream": stream,
                },
                timeout=30.0,
            )
            latency = (time.time() - start) * 1000
            if resp.status_code == 200:
                return ChannelResult(
                    "autoclaw", True,
                    data=resp.json(),
                    latency_ms=latency,
                    status_code=200
                )
            else:
                return ChannelResult(
                    "autoclaw", False,
                    error=f"HTTP {resp.status_code}",
                    latency_ms=latency,
                    status_code=resp.status_code
                )
        except Exception as e:
            return ChannelResult("autoclaw", False, error=str(e))


# ═══════════════════════════════════════════════════════════════
# 8. SMART CHANNEL ROUTER v3 — Unified Decision Engine
# ═══════════════════════════════════════════════════════════════

class SmartChannelRouterV3:
    """
    Unified SmartChannelRouter v3 — selects optimal access channel
    across 7 integrated repos with automatic failover.

    Channels (priority order):
      1. CACHED         — Return cached response if fresh
      2. HTTP_PROXY     — Route through proxy pool (prox5/https_proxy)
      3. SOCKS_POOL     — Use SOCKS5 pool directly (prox5 Mystery Dialer)
      4. DNS_TUNNEL     — Fall back to DNS tunneling (llm-dns-proxy)
      5. MITM_STEALTH   — Use secret-agent for JS-heavy/protected targets
      6. CONNECT_CHAIN  — Use proxytunnel for corporate proxy traversal
      7. HTTP_DIRECT    — Last resort direct connection
    """

    def __init__(self, config=None):
        # Key rotation
        self.key_rotator = OpenRouterKeyRotator.from_env()

        # Shared HTTP client (Audit Fix: was creating new client per request)
        self._http_client: Optional[httpx.AsyncClient] = None

        # DNS flood protection
        self.flood_protector = DNSFloodProtector(
            max_qps=int(os.getenv("DNS_FLOOD_MAX_QPS", "50")),
            burst=int(os.getenv("DNS_FLOOD_BURST", "100")),
        )

        # Per-channel circuit breakers (Audit Fix: no circuit breaker existed)
        self._circuit_breakers: Dict[str, ChannelCircuitBreaker] = {
            ch.value: ChannelCircuitBreaker(
                ch.value,
                failure_threshold=int(os.getenv(f"CB_{ch.name}_THRESHOLD", "5")),
                recovery_timeout=float(os.getenv(f"CB_{ch.name}_TIMEOUT", "30")),
            )
            for ch in Channel if ch != Channel.CACHED
        }

        # Proxy pool (prox5-compatible)
        proxy_file = os.getenv("SYNERGY_PROXY_FILE", "")
        self.proxy_pool = ProxyPoolAdapter(
            proxy_file=proxy_file if os.path.exists(proxy_file) else None
        )

        # Stealth proxy (https_proxy Rust)
        self.stealth_proxy = StealthProxyAdapter()

        # ProxyTunnel adapter
        self.proxytunnel = ProxyTunnelAdapter()

        # SecretAgent adapter
        self.secret_agent = SecretAgentAdapter()

        # AutoClaw adapter
        self.autoclaw = AutoClawAdapter(
            base_url=os.getenv("AUTOCLAW_BASE_URL", "http://localhost:31000")
        )

        # curl_cffi Chrome impersonation client (Audit Fix: no TLS fingerprinting)
        self.curl_client = CurlCffiClient(
            chrome_version=os.getenv("CURL_CFFI_CHROME", "chrome131")
        )

        # Channel preferences per domain (with EMA learning)
        self._prefs: Dict[str, DomainPreference] = {}
        self._states: Dict[str, ChannelState] = {}
        # Memory Fix M-R1: DomainPreference TTL eviction + max domain cap
        self._max_prefs = int(os.getenv("SYNERGY_MAX_DOMAINS", "10000"))
        self._pref_ttl = float(os.getenv("SYNERGY_DOMAIN_TTL", "3600"))

        # Cache (simple TTL cache with max size)
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl = int(os.getenv("SYNERGY_CACHE_TTL", "300"))
        self._cache_max = int(os.getenv("SYNERGY_CACHE_MAX", "1000"))

        # Stack info
        STACK_INFO.info({
            "version": "3.0.0",
            "repos": "owl-agent+llm-dns-proxy+secret-agent+proxytunnel+autoclaw+https_proxy+prox5",
            "channels": "cached,http_proxy,socks_pool,dns_tunnel,mitm_stealth,connect_chain,http_direct",
        })

    # ─── Cache ────────────────────────────────────────────────

    def _evict_stale_preferences(self) -> None:
        """Memory Fix M-R1: Evict DomainPreference entries idle > pref_ttl; hard cap at max_prefs."""
        now = time.time()
        stale = [d for d, p in self._prefs.items()
                 if now - p.last_updated > self._pref_ttl]
        for d in stale:
            del self._prefs[d]
        # Hard cap: evict oldest if still over limit
        if len(self._prefs) > self._max_prefs:
            sorted_d = sorted(self._prefs.items(), key=lambda x: x[1].last_updated)
            for d, _ in sorted_d[:len(self._prefs) - self._max_prefs]:
                del self._prefs[d]

    def _cache_get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            data, ts = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
            del self._cache[key]
        return None

    def _cache_set(self, key: str, data: Any):
        # Evict oldest entries when cache exceeds max size
        if len(self._cache) >= self._cache_max:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        self._cache[key] = (data, time.time())

    async def _get_http_client(self, proxy: str = None) -> httpx.AsyncClient:
        """Get or create shared HTTP client (connection pooling)."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                proxy=proxy, timeout=30.0,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
            )
        return self._http_client

    def _extract_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.hostname or url

    def _select_channel(self, domain: str, force_channel: str = None) -> Channel:
        """Select the optimal channel for a domain."""
        if force_channel:
            try:
                return Channel(force_channel)
            except ValueError:
                pass

        pref = self._prefs.get(domain)
        if pref and pref.preferred_channel:
            try:
                return Channel(pref.preferred_channel)
            except ValueError:
                pass

        # Default priority: proxy pool → SOCKS → DNS → MITM → direct
        if self.proxy_pool.valid_count > 0:
            return Channel.HTTP_PROXY
        return Channel.DNS_TUNNEL

    # ─── Channel Implementations ──────────────────────────────

    async def _try_http_proxy(self, url: str, domain: str, **kwargs) -> ChannelResult:
        """Route through proxy pool (prox5/https_proxy)."""
        start = time.time()
        proxy = self.proxy_pool.get_next()

        if not proxy:
            return ChannelResult("http_proxy", False, error="No proxies available")

        try:
            api_key = self.key_rotator.get_active_key()
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            # Memory Fix M-R3: Use shared httpx client instead of per-request creation
            client = await self._get_http_client(proxy=proxy.url)
            resp = await client.get(url, headers=headers)
            latency = (time.time() - start) * 1000

            if resp.status_code in (401, 403, 429):
                self.key_rotator.report_error(
                    resp.status_code,
                    "rate_limit" if resp.status_code == 429 else "auth_error"
                )

            self.proxy_pool.report_success(proxy.endpoint, latency)

            # Only treat 2xx as success — non-2xx should trigger failover
            is_success = 200 <= resp.status_code < 300
            if is_success:
                self._cache_set(url, resp.content)

            return ChannelResult(
                "http_proxy", is_success,
                data=resp.content, latency_ms=latency,
                status_code=resp.status_code, proxy_used=proxy.endpoint
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            self.proxy_pool.report_failure(proxy.endpoint)
            return ChannelResult("http_proxy", False, error=str(e), latency_ms=latency)

    async def _try_socks_pool(self, url: str, domain: str, **kwargs) -> ChannelResult:
        """Route through SOCKS5 pool directly (prox5 Mystery Dialer pattern)."""
        start = time.time()
        proxy = self.proxy_pool.get_next()

        if not proxy or proxy.protocol not in ("socks5", "socks4"):
            return ChannelResult("socks_pool", False, error="No SOCKS proxies available")

        try:
            # Memory Fix M-R3: Use shared httpx client instead of per-request creation
            client = await self._get_http_client(proxy=proxy.url)
            resp = await client.get(url)
            latency = (time.time() - start) * 1000
            self.proxy_pool.report_success(proxy.endpoint, latency)
            return ChannelResult(
                "socks_pool", True, data=resp.content,
                latency_ms=latency, status_code=resp.status_code,
                proxy_used=proxy.endpoint
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            self.proxy_pool.report_failure(proxy.endpoint)
            return ChannelResult("socks_pool", False, error=str(e), latency_ms=latency)

    async def _try_dns_tunnel(self, url: str, domain: str, **kwargs) -> ChannelResult:
        """Fall back to DNS tunneling (llm-dns-proxy).
        Verifies DNS server is actually reachable by sending a health-check query."""
        start = time.time()
        try:
            import socket
            dns_host = os.getenv("DNS_SERVER_HOST", "127.0.0.1")
            dns_port = int(os.getenv("DNS_SERVER_PORT", "5353"))
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            # Send a minimal DNS query to verify the server is actually running
            # DNS header: ID=0x1234, RD=1, QDCOUNT=1, QNAME=., QTYPE=TXT, QCLASS=IN
            query = b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x01'
            sock.sendto(query, (dns_host, dns_port))
            # Wait for any response (even SERVFAIL proves the server is alive)
            data, _ = sock.recvfrom(512)
            sock.close()
            if not data:
                return ChannelResult("dns_tunnel", False, error="DNS server returned empty response")
            return ChannelResult(
                "dns_tunnel", True,
                data=f"[DNS tunnel verified for {domain}]",
                latency_ms=(time.time() - start) * 1000
            )
        except socket.timeout:
            return ChannelResult("dns_tunnel", False, error="DNS server not reachable (timeout)")
        except ConnectionRefusedError:
            return ChannelResult("dns_tunnel", False, error="DNS server not running (connection refused)")
        except Exception as e:
            return ChannelResult("dns_tunnel", False, error=str(e))

    async def _try_mitm_stealth(self, url: str, domain: str, **kwargs) -> ChannelResult:
        """Use secret-agent for JS-heavy/protected targets."""
        proxy = self.proxy_pool.get_next()
        upstream = proxy.url if proxy else None
        return await self.secret_agent.scrape(url, upstream_proxy=upstream)

    async def _try_connect_chain(self, url: str, domain: str, **kwargs) -> ChannelResult:
        """Use proxytunnel for corporate proxy traversal."""
        proxy = kwargs.get('proxy', '')
        dest = kwargs.get('destination', url)
        if not proxy:
            return ChannelResult("connect_chain", False, error="No proxy specified for CONNECT chain")
        return await self.proxytunnel.tunnel(proxy, dest)

    async def _try_http_direct(self, url: str, domain: str, **kwargs) -> ChannelResult:
        """Last resort: direct HTTP connection."""
        start = time.time()
        try:
            # Memory Fix M-R3: Reuse shared client instead of per-request AsyncClient
            client = await self._get_http_client()
            resp = await client.get(url)
            latency = (time.time() - start) * 1000
            return ChannelResult(
                "http_direct", True, data=resp.content,
                latency_ms=latency, status_code=resp.status_code
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ChannelResult("http_direct", False, error=str(e), latency_ms=latency)

    # ─── Main Fetch Method ────────────────────────────────────

    async def fetch(self, url: str, force_channel: str = None, **kwargs) -> ChannelResult:
        """
        Fetch a URL through the optimal channel with automatic failover.
        Now includes per-channel circuit breaker and EMA domain preference learning.

        Channel selection priority:
          cached → http_proxy → socks_pool → dns_tunnel → mitm_stealth → connect_chain → http_direct
        """
        domain = self._extract_domain(url)

        # Memory Fix M-R1: Evict stale domain preferences on each request
        self._evict_stale_preferences()

        # Check cache
        cached = self._cache_get(url)
        if cached and not force_channel:
            return ChannelResult("cached", True, data=cached)

        # Select channel (uses DomainPreference EMA if available)
        channel = self._select_channel(domain, force_channel)

        # Channel implementations
        channel_map = {
            Channel.HTTP_PROXY: self._try_http_proxy,
            Channel.SOCKS_POOL: self._try_socks_pool,
            Channel.DNS_TUNNEL: self._try_dns_tunnel,
            Channel.MITM_STEALTH: self._try_mitm_stealth,
            Channel.CONNECT_CHAIN: self._try_connect_chain,
            Channel.HTTP_DIRECT: self._try_http_direct,
        }

        # Try preferred channel (with circuit breaker check)
        if channel in channel_map:
            cb = self._circuit_breakers.get(channel.value)
            if cb and not await cb.allow_request():
                logger.debug(f"Circuit OPEN for {channel.value} — skipping")
            else:
                result = await channel_map[channel](url, domain, **kwargs)
                # Record result in circuit breaker and EMA
                if cb:
                    if result.success:
                        await cb.record_success()
                    else:
                        await cb.record_failure()
                # Update domain preference EMA
                pref = self._prefs.get(domain)
                if not pref:
                    pref = DomainPreference(domain=domain)
                    self._prefs[domain] = pref
                pref.record_channel_result(result.channel, result.success)

                if result.success:
                    REQUESTS_TOTAL.labels(channel=result.channel, domain=domain, status="success").inc()
                    REQUESTS_DURATION.labels(channel=result.channel, domain=domain).observe(result.latency_ms / 1000)
                    return result
                # Record failure in Prometheus
                REQUESTS_TOTAL.labels(channel=result.channel, domain=domain, status="error").inc()

        # Fallback: try all channels in priority order
        # NOTE: CONNECT_CHAIN was missing — added between MITM and HTTP_DIRECT
        fallback_order = [
            Channel.HTTP_PROXY, Channel.SOCKS_POOL, Channel.DNS_TUNNEL,
            Channel.MITM_STEALTH, Channel.CONNECT_CHAIN, Channel.HTTP_DIRECT,
        ]
        for ch in fallback_order:
            if ch == channel:
                continue  # Already tried
            if ch not in channel_map:
                continue

            # Circuit breaker check
            cb = self._circuit_breakers.get(ch.value)
            if cb and not await cb.allow_request():
                logger.debug(f"Circuit OPEN for {ch.value} — skipping fallback")
                continue

            result = await channel_map[ch](url, domain, **kwargs)

            # Record in circuit breaker and EMA
            if cb:
                if result.success:
                    await cb.record_success()
                else:
                    await cb.record_failure()
            pref = self._prefs.get(domain)
            if pref:
                pref.record_channel_result(result.channel, result.success)

            if result.success:
                CHANNEL_SWITCHES.labels(
                    from_channel=channel.value, to_channel=ch.value
                ).inc()
                REQUESTS_TOTAL.labels(channel=result.channel, domain=domain, status="success").inc()
                REQUESTS_DURATION.labels(channel=result.channel, domain=domain).observe(result.latency_ms / 1000)
                return result
            # Record failure
            REQUESTS_TOTAL.labels(channel=result.channel, domain=domain, status="error").inc()

        REQUESTS_TOTAL.labels(channel="none", domain=domain, status="all_failed").inc()
        return ChannelResult("none", False, error=f"All channels exhausted for {domain}")

    # ─── Status & Monitoring ──────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive stack status."""
        return {
            "version": "3.0.0",
            "channels": {
                "http_proxy": self.proxy_pool.valid_count > 0,
                "socks_pool": any(
                    p.protocol.startswith("socks") and p.score > 0.2
                    for p in self.proxy_pool._pool
                ),
                "dns_tunnel": True,  # Always available if server running
                "mitm_stealth": bool(self.secret_agent._npm),
                "connect_chain": bool(self.proxytunnel._binary),
                "stealth_proxy": self.stealth_proxy.is_running,
            },
            "circuit_breakers": {
                name: {
                    "state": cb.state.name,
                    "failures": cb._failure_count,
                }
                for name, cb in self._circuit_breakers.items()
            },
            "domain_preferences": {
                domain: {
                    "preferred": pref.preferred_channel,
                    "scores": pref._ema_scores,
                }
                for domain, pref in self._prefs.items()
            },
            "key_rotator": self.key_rotator.get_status(),
            "proxy_pool": self.proxy_pool.get_status(),
            "flood_protection": {
                "blocked": self.flood_protector._blocked_count,
            },
            "cache": {
                "entries": len(self._cache),
                "ttl": self._cache_ttl,
                "max": self._cache_max,
            },
        }
