# AutoClaw × OWL-AGENT Integration (Synergy 6)

**Shipped in:** `marktantongco/autoclaw-autologin` **v2.1.0** (2026-09-19)

The OWL-AGENT v5.3 proxy defense stack is now the upstream network-resilience
layer of AutoClaw: every upstream HTTP call (chat SSE, token refresh, profile,
wallet, ledger) is routed **proxy-first** with hedged parallel racing and an
always-available direct fallback.

## Architecture

```
Flask proxy.py (sync)                     auth.py (sync)
  chat_completions()                        refresh/profile/wallet/ledger
    └─ owl_bridge.owl_stream_request()      └─ owl_bridge.owl_request()
         │  (fallback: requests direct)          │  (fallback: requests direct)
─────────┼───────────────────────────────────────┼──────────
         │ run_coroutine_threadsafe (daemon loop thread)
owl_bridge: hybrid backend loader
  1. external  ~/.owl-agent/proxy_defense.py   ← wins if installed
  2. vendored  owl_proxy.py (this integration) ← always-works fallback
         │
ResilientClient (OWL-AGENT v5.3-autoclaw)
  ├─ ProxyPoolManager   seed(100) → dedup → validate → score → pool
  ├─ hedged race        HEDGE_FANOUT=3 × PROXY_TIMEOUT=6s (headers only)
  ├─ single-strike ban  idempotent, backoff 60s × fail_count (cap 10)
  ├─ AdaptiveRateLimiter per-domain buckets; 429 halves, success grows
  ├─ AsyncCircuitBreaker per-domain, NETWORK failures only
  ├─ HTTPCache + dedup   GET-only, header-aware keys
  └─ direct fallback     httpx/http2 or curl_cffi (TLS impersonation)
```

## Files in this directory

| File | Role |
|---|---|
| `owl_proxy.py` | Vendored OWL-AGENT v5.3 core (adapted: streaming, header-aware cache, env-tunable) |
| `owl_bridge.py` | Sync bridge: hybrid loader, background loop, fail-safe shims, SSE pump |
| `test_owl_integration.py` | 61 offline tests (core, bridge, Flask routes, Phase-1 regression) |

These are **synced copies** — the canonical versions live in
`marktantongco/autoclaw-autologin` (v2.1.0 tag).

## Integration adaptations vs upstream OWL-AGENT v5.3

1. **Streaming** — upstream v5.3 buffers whole responses; AutoClaw needs SSE
   passthrough. `stream_request()` races proxies for *connection
   establishment* (time-to-headers) and streams the body through the winner.
2. **Header-aware cache/dedup** — upstream keys omitted auth headers (two
   accounts would collide). Keys now hash the full header map; only GETs are
   cached/coalesced (token-refresh POSTs must never be merged).
3. **Circuit breakers count network failures only** — HTTP 4xx/5xx are
   application-level signals and never open the breaker.
4. **Env-tunable** — 12 `OWL_*` variables; no code edits to tune.
5. **Library-first** — importable module + standalone CLI retained.

## Ops quick reference

```bash
# Exact v2.0.0 behavior (OWL off)
OWL_PROXY_ENABLED=0 ./start-proxy.bat

# TLS impersonation (Phase-3 uTLS path)
pip install curl_cffi && OWL_TLS_IMPERSONATE=chrome110

# Health / stats
curl -s localhost:31000/health | jq .owl
python owl_proxy.py stats
python owl_proxy.py benchmark

# Every chat response tells you the network path:
#   X-Upstream-Via: direct | owl-proxy/vendored | owl-proxy/external
```

## Phase 2 (v2.2.0) — DSML shim + fingerprint + loop_breaker

Synced sources for AutoClaw v2.2.0's application-layer synergies
(sources: tt-52101/chat-z-ai-proxy-web2api-free #8 and
eroslifestyle/ai-router-switch #9):

- `dsml_shim.py` — synthesises OpenAI function-calling: DSML protocol
  injection on the request, buffered parse + `DSMLStreamSieve` streaming
  conversion of `<dsml:tool_call>` blocks into real `tool_calls` deltas
- `chat_fingerprint.py` — SHA-256 of the first user message (or
  `X-AutoClaw-Chat-Id` header) pinned on first use to the serving account;
  defeats conversation-merge, gives per-conversation account affinity
- `loop_breaker.py` — 4+ re-emits of the same turn at >=80% context fill
  return HTTP 400 `loop_breaker_triggered` (runaway-spend guard)
- `test_owl_integration.py` — 112-test offline suite (61 v2.1.0 + 51 Phase-2)

## Test evidence

```
61 passed, 0 failed (offline, mocked seams)
Live smoke: vendored backend booted, 100 proxies seeded from proxifly CDN,
validators running, /health owl block green (enabled, vendored, 100 total).
```

## Phase 3 (v2.3.0) — WS fallback × thermoptic × React dashboard

| File | Purpose |
|---|---|
| `metrics.py` | Thread-safe dashboard registry: totals, per-status/via/model counters, block + feature counters, latency p95 window, capped request log, SHA-256 masked-IP client list |
| `ws_fallback.py` | Synergy 13: cloud-to-local WebSocket transport (`autoclaw-ws-agent-v1`), local-agent discovery, network-only breaker; SSE reassembled requests-style so the DSML sieve works unchanged |
| `thermoptic_bridge.py` | Synergy 14 via [mandatoryprogrammer/thermoptic](https://github.com/mandatoryprogrammer/thermoptic): real-browser JA4+ camouflage egress tier with probe + transport-only breaker |
| `dashboard-src/` | Vite/React source of the operator dashboard (build → `ui/dashboard/`, served at `/dashboard`); WebSocket metrics stream + REST fallback + backend-switch control surface |
| `scripts/smoke_test_dsml_live.py` | Live smoke: boots the real proxy, probes real egress, sends the banner+DSML envelope over the live wire; full tool-call round-trips when tokens.json exists |
| `test_owl_integration.py` | 148 offline tests (Phase 1–3 regression + integration) |

Egress chain order is runtime-switchable from the dashboard control
surface: `owl-first` (default) | `thermoptic-first` | `direct-only`. The
WS local-agent engages only after network-level faults on every HTTP
tier; HTTP 4xx/5xx always pass through verbatim.
