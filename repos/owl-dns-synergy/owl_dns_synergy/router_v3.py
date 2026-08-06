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


@dataclass
class DomainPreference:
    domain: str
    successes: Dict[str, int] = field(default_factory=lambda: {})
    failures: Dict[str, int] = field(default_factory=lambda: {})
    preferred_channel: str = "http_proxy"
    last_updated: float = field(default_factory=time.time)


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

    def __init__(self, max_qps: int = 50, burst: int = 100):
        self.max_qps = max_qps
        self.burst = burst
        self._tokens: float = float(burst)
        self._last_refill: float = time.time()
        self._lock = asyncio.Lock()
        self._blocked_count = 0
        self._client_queries: Dict[str, deque] = {}

    async def allow(self, client_ip: str = "default") -> bool:
        async with self._lock:
            now = time.time()
            # Per-client rate check FIRST (before consuming global token)
            if client_ip not in self._client_queries:
                self._client_queries[client_ip] = deque(maxlen=100)
            self._client_queries[client_ip].append(now)
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

    async def get_next_token(self) -> Optional[Dict]:
        """Get next available token via autoclaw API."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/v1/models",
                    timeout=10.0,
                )
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
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions",
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

        # DNS flood protection
        self.flood_protector = DNSFloodProtector(
            max_qps=int(os.getenv("DNS_FLOOD_MAX_QPS", "50")),
            burst=int(os.getenv("DNS_FLOOD_BURST", "100")),
        )

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

        # Channel preferences per domain
        self._prefs: Dict[str, DomainPreference] = {}
        self._states: Dict[str, ChannelState] = {}

        # Cache (simple TTL cache)
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl = int(os.getenv("SYNERGY_CACHE_TTL", "300"))

        # Stack info
        STACK_INFO.info({
            "version": "3.0.0",
            "repos": "owl-agent+llm-dns-proxy+secret-agent+proxytunnel+autoclaw+https_proxy+prox5",
            "channels": "cached,http_proxy,socks_pool,dns_tunnel,mitm_stealth,connect_chain,http_direct",
        })

    # ─── Cache ────────────────────────────────────────────────

    def _cache_get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            data, ts = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
            del self._cache[key]
        return None

    def _cache_set(self, key: str, data: Any):
        self._cache[key] = (data, time.time())

    # ─── Channel Selection ────────────────────────────────────

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
        import httpx
        start = time.time()
        proxy = self.proxy_pool.get_next()

        if not proxy:
            return ChannelResult("http_proxy", False, error="No proxies available")

        try:
            api_key = self.key_rotator.get_active_key()
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(
                proxy=proxy.url, timeout=30.0
            ) as client:
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
        import httpx
        start = time.time()
        proxy = self.proxy_pool.get_next()

        if not proxy or proxy.protocol not in ("socks5", "socks4"):
            return ChannelResult("socks_pool", False, error="No SOCKS proxies available")

        try:
            async with httpx.AsyncClient(proxy=proxy.url, timeout=30.0) as client:
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
        import httpx
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
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

        Channel selection priority:
          cached → http_proxy → socks_pool → dns_tunnel → mitm_stealth → connect_chain → http_direct
        """
        domain = self._extract_domain(url)

        # Check cache
        cached = self._cache_get(url)
        if cached and not force_channel:
            return ChannelResult("cached", True, data=cached)

        # Select channel
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

        # Try preferred channel
        if channel in channel_map:
            result = await channel_map[channel](url, domain, **kwargs)
            if result.success:
                REQUESTS_TOTAL.labels(channel=result.channel, domain=domain, status="success").inc()
                REQUESTS_DURATION.labels(channel=result.channel, domain=domain).observe(result.latency_ms / 1000)
                return result

        # Fallback: try all channels in priority order
        # NOTE: CONNECT_CHAIN was missing — added between MITM and HTTP_DIRECT
        fallback_order = [
            Channel.HTTP_PROXY, Channel.SOCKS_POOL, Channel.DNS_TUNNEL,
            Channel.MITM_STEALTH, Channel.CONNECT_CHAIN, Channel.HTTP_DIRECT,
        ]
        for ch in fallback_order:
            if ch == channel:
                continue  # Already tried
            if ch in channel_map:
                result = await channel_map[ch](url, domain, **kwargs)
                if result.success:
                    CHANNEL_SWITCHES.labels(
                        from_channel=channel.value, to_channel=ch.value
                    ).inc()
                    REQUESTS_TOTAL.labels(channel=result.channel, domain=domain, status="success").inc()
                    return result

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
            "key_rotator": self.key_rotator.get_status(),
            "proxy_pool": self.proxy_pool.get_status(),
            "flood_protection": {
                "blocked": self.flood_protector._blocked_count,
            },
            "cache": {
                "entries": len(self._cache),
                "ttl": self._cache_ttl,
            },
        }
