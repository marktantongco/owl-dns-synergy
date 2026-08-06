"""Prometheus Metrics for OWL-DNS-Synergy Stack

Exports memory budgets, session counts, cache stats, and process metrics
for Grafana dashboards and alerting.

Metrics exposed at /metrics endpoint:
  - owl_dns_sessions_pending: Current pending DNS chunk sessions
  - owl_dns_sessions_max: Maximum allowed sessions
  - owl_cache_entries: HTTP cache entry count
  - owl_cache_max_size: Cache maximum size
  - owl_decompress_budget_bytes: Current decompression budget usage
  - owl_decompress_budget_max: Maximum decompression budget
  - owl_domain_prefs_count: Number of tracked domain preferences
  - owl_flood_clients_count: Number of tracked client IPs
  - owl_quality_targets_count: Number of quality-scored targets
  - owl_router_http_client_active: Whether shared HTTP client is active
"""

import os
import logging

logger = logging.getLogger("owl-dns-synergy.metrics")

try:
    from prometheus_client import (
        Gauge, Counter, Histogram, Info,
        generate_latest, CONTENT_TYPE_LATEST,
        CollectorRegistry, ProcessCollector,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed — metrics disabled")

# ─── Custom Registry (avoid conflicts with default) ──────────────────
registry = CollectorRegistry() if PROMETHEUS_AVAILABLE else None

# ─── Process Metrics (CPU, memory, file descriptors) ────────────────
if PROMETHEUS_AVAILABLE:
    try:
        ProcessCollector(registry=registry)
    except Exception:
        pass

# ─── DNS Chunker Metrics ────────────────────────────────────────────
dns_sessions_pending = Gauge(
    'owl_dns_sessions_pending', 'Current pending DNS chunk sessions',
    registry=registry
) if PROMETHEUS_AVAILABLE else None

dns_sessions_max = Gauge(
    'owl_dns_sessions_max', 'Maximum allowed DNS sessions',
    registry=registry
) if PROMETHEUS_AVAILABLE else None

# ─── HTTP Cache Metrics ─────────────────────────────────────────────
cache_entries = Gauge(
    'owl_cache_entries', 'HTTP cache entry count',
    registry=registry
) if PROMETHEUS_AVAILABLE else None

cache_max_size = Gauge(
    'owl_cache_max_size', 'Cache maximum size limit',
    registry=registry
) if PROMETHEUS_AVAILABLE else None

# ─── Crypto Metrics ─────────────────────────────────────────────────
decompress_budget_bytes = Gauge(
    'owl_decompress_budget_bytes', 'Current decompression budget usage',
    registry=registry
) if PROMETHEUS_AVAILABLE else None

decompress_budget_max = Gauge(
    'owl_decompress_budget_max', 'Maximum decompression budget',
    registry=registry
) if PROMETHEUS_AVAILABLE else None

# ─── Router Metrics ─────────────────────────────────────────────────
domain_prefs_count = Gauge(
    'owl_domain_prefs_count', 'Number of tracked domain preferences',
    registry=registry
) if PROMETHEUS_AVAILABLE else None

flood_clients_count = Gauge(
    'owl_flood_clients_count', 'Number of tracked client IPs',
    registry=registry
) if PROMETHEUS_AVAILABLE else None

quality_targets_count = Gauge(
    'owl_quality_targets_count', 'Number of quality-scored targets',
    registry=registry
) if PROMETHEUS_AVAILABLE else None

channel_requests_total = Counter(
    'owl_channel_requests_total', 'Total requests per channel',
    ['channel'], registry=registry
) if PROMETHEUS_AVAILABLE else None

channel_latency_seconds = Histogram(
    'owl_channel_latency_seconds', 'Channel request latency',
    ['channel'], buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=registry
) if PROMETHEUS_AVAILABLE else None

# ─── AutoClaw Metrics ───────────────────────────────────────────────
autoclaw_accounts_total = Gauge(
    'owl_autoclaw_accounts_total', 'Total AutoClaw accounts',
    registry=registry
) if PROMETHEUS_AVAILABLE else None

autoclaw_token_refresh_total = Counter(
    'owl_autoclaw_token_refresh_total', 'Token refresh attempts',
    ['result'], registry=registry
) if PROMETHEUS_AVAILABLE else None

# ─── Stack Info ─────────────────────────────────────────────────────
stack_info = Info(
    'owl_dns_synergy', 'Stack version and configuration',
    registry=registry
) if PROMETHEUS_AVAILABLE else None


# ─── Helper: Update metrics from stack components ───────────────────
def update_dns_metrics(chunker):
    """Update DNS chunker gauges from a DNSChunker instance."""
    if not PROMETHEUS_AVAILABLE or dns_sessions_pending is None:
        return
    dns_sessions_pending.set(len(chunker.pending_messages))
    dns_sessions_max.set(chunker._max_pending_sessions)


def update_cache_metrics(cache):
    """Update HTTP cache gauges from an HTTPCache instance."""
    if not PROMETHEUS_AVAILABLE or cache_entries is None:
        return
    cache_entries.set(len(cache._memory))
    cache_max_size.set(cache._max_size)


def update_crypto_metrics():
    """Update crypto decompression budget gauges."""
    if not PROMETHEUS_AVAILABLE or decompress_budget_bytes is None:
        return
    try:
        from owl_dns_synergy.core import _current_decompress_bytes, _MAX_DECOMPRESS_BUDGET
        decompress_budget_bytes.set(_current_decompress_bytes)
        decompress_budget_max.set(_MAX_DECOMPRESS_BUDGET)
    except ImportError:
        pass


def update_router_metrics(router):
    """Update router gauges from a SmartChannelRouterV3 instance."""
    if not PROMETHEUS_AVAILABLE or domain_prefs_count is None:
        return
    domain_prefs_count.set(len(router._prefs))
    if hasattr(router, '_flood_protector') and router._flood_protector:
        flood_clients_count.set(len(router._flood_protector._client_queries))


def update_quality_metrics(scorer):
    """Update quality scorer gauges."""
    if not PROMETHEUS_AVAILABLE or quality_targets_count is None:
        return
    quality_targets_count.set(len(scorer._scores))


def update_autoclaw_metrics():
    """Update AutoClaw account count."""
    if not PROMETHEUS_AVAILABLE or autoclaw_accounts_total is None:
        return
    try:
        from auth import load_tokens
        data = load_tokens()
        autoclaw_accounts_total.set(len(data.get("accounts", [])))
    except Exception:
        pass


def get_metrics():
    """Generate Prometheus metrics output (bytes)."""
    if not PROMETHEUS_AVAILABLE:
        return b"# Prometheus metrics disabled (prometheus_client not installed)\n"
    return generate_latest(registry)


def get_content_type():
    """Get Prometheus content type."""
    return CONTENT_TYPE_LATEST if PROMETHEUS_AVAILABLE else "text/plain"
