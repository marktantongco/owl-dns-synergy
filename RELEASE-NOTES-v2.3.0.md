# owl-dns-synergy v2.3.0 — Phase 3: WS fallback × thermoptic × React dashboard

`autoclaw-autologin` **v2.3.0** lands Phase 3 — the Priority-3 tier of the
AutoClaw Ecosystem Synergy Research Deep-Dive — on top of the v2.2.0 API
surface expansion. With this release **every actionable synergy in the
Top-15 matrix is shipped** (only the deferred no-CloakBrowser mode, #7,
remains, by operator choice).

## What arrived in this phase

| # | Source repo | Synergy | Status |
|---|---|---|---|
| 13 | eequaled/GLM_proxy | **Cloud-to-local WebSocket fallback** — when the cloud API is network-unreachable, chat transparently re-routes through a local AutoClaw desktop agent (`autoclaw-ws-agent-v1`), SSE reassembled through the same DSML sieve | ✅ v2.3.0 |
| 14 | sabyaghosh/glm-free-api-admin-panel → **superseded by mandatoryprogrammer/thermoptic** | **Browser-grade traffic camouflaging** — real-Chrome JA3/JA4/JA4H egress via the thermoptic MITM proxy, a strictly stronger mechanism than forging a uTLS Chrome-120 ClientHello (no Go/Rust bridge needed, defeats the full JA4+ family, not just JA3) | ✅ v2.3.0 |
| 15 | guell11/OmniClaw-GLM-Proxy | **Local React dashboard** — live metrics, request log, masked-IP client list, block counters, backend-switch control surface, long-running WebSocket metrics stream | ✅ v2.3.0 |

## Full synergy ledger

| # | Source | Synergy | Status |
|---|--------|---------|--------|
| 1–4 | eequaled/GLM_proxy | Output caps / banner / negative cache / i18n | ✅ v2.0.0 |
| 5 | eroslifestyle/ai-router-switch | `!router` command | ✅ v2.0.0 |
| 6 | OWL-AGENT v5.3 | proxy-first defense layer | ✅ v2.1.0 |
| 7 | sitimas9/autoclaw2api | Server-first no-CloakBrowser mode | deferred |
| 8 | tt-52101/chat-z-ai-proxy | DSML tool-calling shim | ✅ v2.2.0 |
| 9 | eroslifestyle/ai-router-switch | Per-chat fingerprint + loop_breaker | ✅ v2.2.0 |
| 10 | sabyaghosh/glm-free-api-admin-panel | uTLS Chrome 120 | ✅ **v2.3.0** (superseded: real-browser thermoptic egress) |
| 11 | eequaled/GLM_proxy | Local WS fallback | ✅ **v2.3.0** |
| 12 | guell11/OmniClaw | React dashboard | ✅ **v2.3.0** |

*(matrix rows renumbered against the research PDF's canonical #13/#14/#15;
the v2.2.0 notes used the provisional 10/11/12 numbering)*

## Tiered egress chain (the Phase-3 architecture)

```
client → AutoClaw proxy
           ├─ OWL free-pool racing (Synergy 6)        ┐ order switchable
           ├─ thermoptic browser camouflage (new)     │ live, no restart
           ├─ direct                                  ┘
           └─ WS local-agent fallback (network faults ONLY, last resort)
```

Every HTTP error status passes through verbatim; only network-level
faults (refused / DNS / connect timeout) advance the chain. Network-only
breakers on both new transports mirror the OWL contract.

## New modules synced to `integrations/autoclaw-owl/`

- `metrics.py` — thread-safe dashboard registry (masked-IP clients,
  capped request log, block/feature counters, latency p95 window)
- `ws_fallback.py` — cloud-to-local WS transport + breaker + discovery
- `thermoptic_bridge.py` — probe/breaker/proxy-auth for the thermoptic tier
- `scripts/smoke_test_dsml_live.py` — live DSML shim smoke (12 stages)
- `test_owl_integration.py` — the full 148-test suite

## Validation

- **148/148 offline tests** (112 → 148; +36 for metrics, WS protocol,
  thermoptic bridge, dashboard routes, egress-chain integration)
- **Live smoke 12/12** — real proxy boot, real upstream egress (direct +
  OWL-raced), banner+DSML envelope over the live wire, dashboard API/UI
  serving, metrics registry populated (`scripts/smoke_test_dsml_live.py`)
- Two real defects caught by the new tests before release:
  `/health` deadlock (non-reentrant lock re-entry) and WS late-error
  envelopes being dropped from the proxy error path
