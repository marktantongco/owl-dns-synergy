"""
Merged core module: OWL-AGENT resilience classes + LLM-DNS-Proxy crypto.
Contains HTTPCache, RequestDeduplicator, QualityScorer, AdaptiveRateLimiter,
CircuitBreaker, CryptoManager, and DNSChunker.
"""

import asyncio
import hashlib
import json
import time
import logging
import math
import uuid
import zlib
import os
import base64
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, Awaitable, List, Tuple
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import aiofiles
import httpx
from circuitbreaker import CircuitBreaker

# Optional imports
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

from .config import SynergyConfig, CACHE_DIR, CONFIG_DIR, PROXY_CACHE_FILE

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("owl-dns-synergy.core")

# ─── Constants ──────────────────────────────────────────────────
DEFAULT_TTL = 300
DEFAULT_RATE = 1.0
MAX_RETRIES = 3
MAX_CACHED_RESPONSES = 1000
MAX_PROXY_CACHE = 100
QUALITY_DECAY = 0.9
ADAPTIVE_MIN_RATE = 0.1
ADAPTIVE_MAX_RATE = 5.0
CB_FAILURE_THRESHOLD = 5
CB_RECOVERY_TIMEOUT = 30


# ═══════════════════════════════════════════════════════════════════
# OWL-AGENT Classes (proxy_defense.py v4.2)
# ═══════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class CachedResponse:
    status: int
    content: bytes
    headers: Dict[str, str]
    timestamp: float
    ttl: int
    protocol: str = "http/1.1"

    def is_fresh(self) -> bool:
        return time.time() - self.timestamp < self.ttl


@dataclass(slots=True)
class TokenBucket:
    rate: float
    capacity: float
    tokens: float = 0.0
    last_update: float = field(default_factory=time.time)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def _replenish(self):
        now = time.time()
        elapsed = now - self.last_update
        async with self.lock:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

    async def acquire(self, tokens: float = 1.0) -> bool:
        """Acquire tokens from the bucket. Uses loop instead of recursion to prevent stack overflow."""
        while True:
            await self._replenish()
            async with self.lock:
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                deficit = tokens - self.tokens
            await asyncio.sleep(deficit / self.rate)


@dataclass(slots=True)
class ProxyEntry:
    url: str
    healthy: bool = True
    last_check: float = 0.0
    fail_count: int = 0
    ban_until: float = 0.0

    def is_banned(self) -> bool:
        return time.time() < self.ban_until

    def mark_failed(self):
        self.fail_count += 1
        self.ban_until = time.time() + 60
        self.healthy = False
        logger.warning(f"Proxy banned (60s): {self.url}")

    def mark_success(self):
        self.fail_count = 0
        self.healthy = True
        self.last_check = time.time()


class HTTPCache:
    """LRU + disk cache with periodic cleanup."""

    def __init__(self, ttl: int = DEFAULT_TTL, max_size: int = MAX_CACHED_RESPONSES,
                 max_entry_bytes: int = 50 * 1024):
        self.ttl = ttl
        self._max_size = max_size
        # Memory Fix M-O1: Use OrderedDict for O(1) LRU eviction
        self._memory: OrderedDict[str, CachedResponse] = OrderedDict()
        # Memory Fix M-O5: Reject entries larger than max_entry_bytes
        self._max_entry_bytes = max_entry_bytes
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleaner(self):
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(60)
            now = time.time()
            async with self._lock:
                expired = [k for k, v in self._memory.items() if not v.is_fresh()]
                for k in expired:
                    del self._memory[k]
                if len(self._memory) > self._max_size:
                    sorted_items = sorted(self._memory.items(), key=lambda x: x[1].timestamp)
                    for k, _ in sorted_items[:len(self._memory) - self._max_size]:
                        del self._memory[k]

    def _key(self, method, url, params=None, protocol="http/1.1") -> str:
        return hashlib.sha256(
            f"{method}:{url}:{json.dumps(params or {}, sort_keys=True)}:{protocol}".encode()
        ).hexdigest()

    async def get(self, method, url, params=None, protocol="http/1.1") -> Optional[CachedResponse]:
        key = self._key(method, url, params, protocol)
        async with self._lock:
            if key in self._memory and self._memory[key].is_fresh():
                return self._memory[key]
        path = CACHE_DIR / f"{key}.json"
        if path.exists():
            try:
                async with aiofiles.open(path, 'r') as f:
                    data = json.loads(await f.read())
                # Decode base64 content (Audit Fix: was decode utf-8 with replace, corrupting binary)
                import base64 as _b64
                content_bytes = _b64.b64decode(data["content_b64"])
                cached = CachedResponse(
                    status=data["status"],
                    content=content_bytes,
                    headers=data["headers"],
                    timestamp=data["timestamp"],
                    ttl=data["ttl"],
                    protocol=data.get("protocol", "http/1.1"),
                )
                if cached.is_fresh():
                    async with self._lock:
                        self._memory[key] = cached
                    return cached
                else:
                    path.unlink()
            except Exception:
                pass
        return None

    async def set(self, method, url, response: CachedResponse, params=None):
        key = self._key(method, url, params, response.protocol)
        # Memory Fix M-O5: Reject oversized entries to prevent memory bloat
        if len(response.content) > self._max_entry_bytes:
            logger.debug(f"Cache skip: {len(response.content)}B > {self._max_entry_bytes}B limit")
            return
        async with self._lock:
            # Memory Fix M-O1: LRU eviction on set() — evict oldest when at capacity
            if key in self._memory:
                self._memory.move_to_end(key)  # Promote to most-recent
            elif len(self._memory) >= self._max_size:
                self._memory.popitem(last=False)  # Evict oldest (LRU)
            self._memory[key] = response
        # Atomic disk write (Audit Fix: was non-atomic, crash could corrupt)
        import base64 as _b64
        path = CACHE_DIR / f"{key}.json"
        tmp_path = CACHE_DIR / f"{key}.json.tmp"
        data = {
            "status": response.status,
            "content_b64": _b64.b64encode(response.content).decode('ascii'),  # base64 for binary safety
            "headers": response.headers,
            "timestamp": response.timestamp,
            "ttl": response.ttl,
            "protocol": response.protocol,
        }
        async with aiofiles.open(tmp_path, 'w') as f:
            await f.write(json.dumps(data))
        # Atomic rename (os.replace is atomic on POSIX)
        import os as _os
        _os.replace(str(tmp_path), str(path))


class RequestDeduplicator:
    """Prevents duplicate concurrent requests."""

    def __init__(self):
        self._in_flight: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    def _key(self, method, url, params=None, protocol="http/1.1") -> str:
        return hashlib.sha256(
            f"{method}:{url}:{json.dumps(params or {}, sort_keys=True)}:{protocol}".encode()
        ).hexdigest()

    async def execute(self, method, url, params, protocol, factory: Callable[[], Awaitable[CachedResponse]]) -> CachedResponse:
        key = self._key(method, url, params, protocol)
        async with self._lock:
            if key in self._in_flight:
                future = self._in_flight[key]
                # Release lock BEFORE awaiting future to prevent deadlock
            else:
                future = asyncio.Future()
                self._in_flight[key] = future
        # If we're joining an in-flight request, await outside the lock
        if key in self._in_flight and future is not self._in_flight.get(key, None):
            return await future
        if key in self._in_flight and future is self._in_flight.get(key):
            # We created this future — run the factory
            pass
        try:
            result = await factory()
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            async with self._lock:
                self._in_flight.pop(key, None)


class QualityScorer:
    """Weighted scoring for proxies and DNS servers based on success rate and latency."""

    MAX_TARGETS = 5000  # Memory Fix: cap tracked targets to prevent unbounded growth

    def __init__(self, decay_factor: float = QUALITY_DECAY):
        self._scores: Dict[str, float] = {}
        self._history: Dict[str, List[float]] = {}
        self._decay = decay_factor

    def update(self, target_id: str, success: bool, latency_ms: float = 9999.0):
        # Memory Fix: Evict oldest target when at capacity
        if target_id not in self._scores and len(self._scores) >= self.MAX_TARGETS:
            oldest = min(self._scores, key=self._scores.get)
            del self._scores[oldest]
            self._history.pop(oldest, None)
        old_score = self._scores.get(target_id, 0.5)
        new_score = old_score * self._decay + (1.0 if success else 0.0) * (1 - self._decay)
        self._scores[target_id] = new_score
        if target_id not in self._history:
            self._history[target_id] = []
        self._history[target_id].append(latency_ms)
        if len(self._history[target_id]) > 100:
            self._history[target_id] = self._history[target_id][-100:]

    def get_score(self, target_id: str) -> float:
        return self._scores.get(target_id, 0.5)

    def get_best(self, candidates: List[str]) -> Optional[str]:
        if not candidates:
            return None
        return max(candidates, key=lambda p: self.get_score(p))

    def get_all_scores(self) -> Dict[str, float]:
        return self._scores.copy()


class AdaptiveRateLimiter:
    """Dynamically adjusts per-domain request rate based on response codes."""

    def __init__(self, base_rate=DEFAULT_RATE, min_rate=ADAPTIVE_MIN_RATE, max_rate=ADAPTIVE_MAX_RATE):
        self.base_rate = base_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self._rates: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def adjust(self, domain: str, status: int):
        async with self._lock:
            current = self._rates.get(domain, self.base_rate)
            if status in (429, 503):
                new_rate = max(self.min_rate, current * 0.5)
            elif 200 <= status < 300:
                new_rate = min(self.max_rate, current * 1.1)
            else:
                new_rate = current
            self._rates[domain] = new_rate
            logger.debug(f"Rate for {domain}: {new_rate:.2f} req/s")

    async def get_rate(self, domain: str) -> float:
        return self._rates.get(domain, self.base_rate)


class RedisStore:
    """Persistent state storage using Redis (optional)."""

    def __init__(self, url: str = "redis://localhost:6379", prefix: str = "synergy:"):
        self.url = url
        self.prefix = prefix
        self._redis = None
        self._enabled = False

    async def connect(self):
        if not REDIS_AVAILABLE:
            logger.warning("Redis not installed - falling back to memory")
            return
        try:
            self._redis = aioredis.from_url(self.url, decode_responses=True)
            await self._redis.ping()
            self._enabled = True
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis unavailable: {e} - falling back to memory")
            self._enabled = False

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        if self._enabled:
            await self._redis.set(self.prefix + key, json.dumps(value), ex=ttl)

    async def get(self, key: str) -> Optional[Any]:
        if not self._enabled:
            return None
        data = await self._redis.get(self.prefix + key)
        if data:
            return json.loads(data)
        return None

    async def delete(self, key: str):
        if self._enabled:
            await self._redis.delete(self.prefix + key)

    async def keys(self, pattern: str) -> List[str]:
        if not self._enabled:
            return []
        return await self._redis.keys(self.prefix + pattern)


# ═══════════════════════════════════════════════════════════════════
# LLM-DNS-Proxy Classes (crypto.py + chunking.py)
# ═══════════════════════════════════════════════════════════════════

# ─── Memory Fix M-C1: Global decompression budget (100MB concurrent) ───
_MAX_DECOMPRESS_BUDGET = 100 * 1024 * 1024  # 100 MB total concurrent decompressed output
_current_decompress_bytes = 0
_decompress_lock = asyncio.Lock()  # asyncio lock for async context


class CryptoManager:
    """Fernet (AES-128) encryption with compression for DNS tunneling."""

    def __init__(self, key: bytes = None, config: SynergyConfig = None):
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography package required for DNS tunneling")
        if key is None:
            key_str = (config.llm_proxy_key if config else None) or os.getenv('LLM_PROXY_KEY')
            if key_str:
                key = key_str.encode()
            else:
                key = Fernet.generate_key()
        if isinstance(key, str):
            key = key.encode()
        self.fernet = Fernet(key)

    @classmethod
    def generate_key(cls) -> bytes:
        return Fernet.generate_key()

    def encrypt(self, message: str) -> bytes:
        compressed = zlib.compress(message.encode(), level=9)
        return self.fernet.encrypt(compressed)

    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt with global decompression budget (M-C1) to prevent OOM."""
        global _current_decompress_bytes
        decrypted = self.fernet.decrypt(encrypted_data)
        estimated_size = len(decrypted) * 12  # zlib worst-case ratio
        # Check budget (best-effort for sync callers; async callers should use decrypt_async)
        if _current_decompress_bytes + estimated_size > _MAX_DECOMPRESS_BUDGET:
            raise MemoryError(
                f"Decompression budget exceeded: "
                f"{_current_decompress_bytes}/{_MAX_DECOMPRESS_BUDGET} bytes"
            )
        _current_decompress_bytes += estimated_size
        try:
            return zlib.decompress(decrypted).decode()
        finally:
            _current_decompress_bytes -= estimated_size

    def encrypt_chunk(self, text_chunk: str, sequence: int = 0) -> bytes:
        return self.fernet.encrypt(text_chunk.encode('utf-8'))

    def decrypt_chunk(self, encrypted_chunk: bytes) -> str:
        return self.fernet.decrypt(encrypted_chunk).decode('utf-8')


def base36encode(number: int) -> str:
    if number == 0:
        return '0'
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    result = ''
    while number:
        number, remainder = divmod(number, 36)
        result = alphabet[remainder] + result
    return result


def base36decode(string: str) -> int:
    return int(string, 36)


def bytes_to_base36(data: bytes) -> str:
    number = int.from_bytes(data, byteorder='big')
    encoded = base36encode(number)
    length_prefix = base36encode(len(data))
    # Use '_' as separator instead of 'z' — 'z' is a valid base36 digit
    return f"{length_prefix}_{encoded}"


def base36_to_bytes(string: str) -> bytes:
    parts = string.split('_', 1)
    if len(parts) != 2:
        raise ValueError("Invalid base36 format")
    length_str, data_str = parts
    original_length = base36decode(length_str)
    number = base36decode(data_str)
    if number == 0:
        return b'\x00' * original_length
    byte_length = (number.bit_length() + 7) // 8
    result = number.to_bytes(byte_length, byteorder='big')
    if len(result) < original_length:
        result = b'\x00' * (original_length - len(result)) + result
    return result


class DNSChunker:
    """DNS message chunking and reassembly for tunneling."""

    MAX_DNS_LABEL_LENGTH = 63
    MAX_DNS_RECORD_LENGTH = 255
    MAX_DNS_QNAME_LENGTH = 253
    MAX_DATA_LABEL_LENGTH = 50

    def __init__(self, config: SynergyConfig = None,
                 max_pending_sessions: int = 10000, session_ttl: float = 60.0):
        self.config = config or SynergyConfig()
        self.pending_messages: Dict[str, Dict[int, str]] = {}
        self.total_chunks: Dict[str, int] = {}
        # Memory Fix M-D1/M-D3: TTL-based session eviction + max session cap
        self._session_time: Dict[str, float] = {}
        self._max_pending_sessions = max_pending_sessions
        self._session_ttl = session_ttl

    def _split_data_into_labels(self, data: str, max_per_label: int) -> List[str]:
        labels = []
        for i in range(0, len(data), max_per_label):
            labels.append(data[i:i + max_per_label])
        return labels

    def create_chunks(self, encrypted_data: bytes, session_id: str = None) -> List[str]:
        if session_id is None:
            # 8-hex-digit session ID (4B values, avoids birthday collision)
            session_id = uuid.uuid4().hex[:8]

        data_b36 = bytes_to_base36(encrypted_data)
        dns_suffix = self.config.dns_suffix
        base_overhead = len(f"m.999.999.999.{dns_suffix}") + 5
        max_data_per_chunk = self.MAX_DNS_QNAME_LENGTH - base_overhead
        total_chunks = math.ceil(len(data_b36) / max_data_per_chunk)

        chunks = []
        for i in range(total_chunks):
            start = i * max_data_per_chunk
            end = min(start + max_data_per_chunk, len(data_b36))
            chunk_data = data_b36[start:end]
            data_labels = self._split_data_into_labels(chunk_data, self.MAX_DATA_LABEL_LENGTH)
            data_part = '.'.join(data_labels)
            query = self.config.format_dns_query("m", session_id, i, total_chunks, data_part)

            if len(query) > self.MAX_DNS_QNAME_LENGTH:
                reduced_data_len = self.MAX_DNS_QNAME_LENGTH - len(query) + len(data_part)
                if reduced_data_len > 0:
                    chunk_data = chunk_data[:reduced_data_len]
                    data_labels = self._split_data_into_labels(chunk_data, self.MAX_DATA_LABEL_LENGTH)
                    data_part = '.'.join(data_labels)
                    query = self.config.format_dns_query("m", session_id, i, total_chunks, data_part)
                else:
                    raise ValueError(f"Cannot fit data into DNS qname constraints for chunk {i}")

            chunks.append(query)
        return chunks

    def _evict_stale_sessions(self) -> None:
        """Memory Fix M-D1: Evict sessions older than session_ttl to prevent unbounded growth."""
        now = time.time()
        stale = [sid for sid, t in self._session_time.items()
                 if now - t > self._session_ttl]
        for sid in stale:
            self.pending_messages.pop(sid, None)
            self.total_chunks.pop(sid, None)
            self._session_time.pop(sid, None)

    def process_chunk_query(self, query: str) -> Tuple[Optional[str], Optional[bytes]]:
        parts = query.split('.')
        if len(parts) < 6 or parts[0] != 'm' or not self.config.validate_dns_suffix_in_query(parts):
            return None, None
        try:
            session_id = parts[1]
            chunk_index = int(parts[2])
            total_chunks = int(parts[3])

            # Memory Fix M-D1: Evict stale sessions on each query
            self._evict_stale_sessions()

            suffix_parts = self.config.get_dns_suffix_parts()
            data_labels = parts[4:-len(suffix_parts)]
            chunk_data = ''.join(data_labels)

            if session_id not in self.pending_messages:
                # Memory Fix M-D3: Reject new sessions when at capacity
                if len(self.pending_messages) >= self._max_pending_sessions:
                    return None, None  # Too many pending sessions — reject
                self.pending_messages[session_id] = {}
                self.total_chunks[session_id] = total_chunks
                self._session_time[session_id] = time.time()
            elif self.total_chunks[session_id] != total_chunks:
                return None, None  # total_chunks mismatch — reject

            self.pending_messages[session_id][chunk_index] = chunk_data
            self._session_time[session_id] = time.time()  # Refresh TTL

            # Verify ALL expected indices present (not just count)
            if set(self.pending_messages[session_id].keys()) == set(range(self.total_chunks[session_id])):
                # Memory Fix M-D4: Use list+join instead of string concat
                parts_list = [self.pending_messages[session_id][i]
                              for i in range(self.total_chunks[session_id])]
                complete_data = ''.join(parts_list)
                del self.pending_messages[session_id]
                del self.total_chunks[session_id]
                self._session_time.pop(session_id, None)
                return session_id, base36_to_bytes(complete_data)

            return session_id, None
        except (ValueError, IndexError):
            return None, None

    def create_response_chunks(self, encrypted_data: bytes, session_id: str) -> Dict[int, str]:
        data_b64 = encrypted_data.decode('ascii')
        max_prefix_size = 10
        max_chunk_size = self.MAX_DNS_RECORD_LENGTH - max_prefix_size
        total_chunks = math.ceil(len(data_b64) / max_chunk_size)
        chunks = {}
        for i in range(total_chunks):
            start = i * max_chunk_size
            end = min(start + max_chunk_size, len(data_b64))
            chunk_data = data_b64[start:end]
            txt_record = f"{i}:{total_chunks}:{chunk_data}"
            if len(txt_record) > self.MAX_DNS_RECORD_LENGTH:
                max_data_len = self.MAX_DNS_RECORD_LENGTH - len(f"{i}:{total_chunks}:")
                if max_data_len > 0:
                    chunk_data = chunk_data[:max_data_len]
                    txt_record = f"{i}:{total_chunks}:{chunk_data}"
            chunks[i] = txt_record
        return chunks

    def reassemble_response(self, chunks: Dict[int, str]) -> bytes:
        if not chunks:
            return b''
        total_chunks = None
        for chunk_data in chunks.values():
            parts = chunk_data.split(':', 2)
            if len(parts) == 3:
                try:
                    chunk_total = int(parts[1])
                    if total_chunks is None or chunk_total > total_chunks:
                        total_chunks = chunk_total
                except ValueError:
                    continue
        if total_chunks is None:
            return b''
        expected = set(range(total_chunks))
        available = set(chunks.keys())
        if expected != available:
            return b''
        sorted_chunks = sorted(chunks.items())
        # Memory Fix M-D4: Use list+join instead of string concat
        parts_list = []
        for _, chunk in sorted_chunks:
            parts = chunk.split(':', 2)
            if len(parts) == 3:
                parts_list.append(parts[2])
        return ''.join(parts_list).encode('ascii')
