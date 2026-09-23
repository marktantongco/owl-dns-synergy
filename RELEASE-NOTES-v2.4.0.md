# owl-dns-synergy v2.4.0 — Phase 3.1: Synergy #7 import mode × DSML real-world metrics × dashboard tuning

The **deferred synergy ships last**: #7 (sitimas9/autoclaw2api's server-first
no-CloakBrowser mode) was promoted after a live probe confirmed the upstream
OAuth URL route returns **HTTP 405 for properly-signed requests** — the
browser harvest path is dead upstream for all forks, making token import the
supply lifeline. Differential evidence: a bad signature yields `400002
Middleware sign error` (middleware runs before routing); a good signature
passes middleware and hits a removed route (405).

## Synergy ledger — final state

| # | Source | Synergy | Status |
|---|--------|---------|--------|
| 7 | sitimas9/autoclaw2api | **Server-first no-CloakBrowser mode** — `token_import.py`, import API, watch-dir, `ACLAW_OAUTH_MODE` gating | ✅ **v2.4.0** (promoted from deferred) |
| 13 | eequaled/GLM_proxy | Cloud-to-local WebSocket fallback | ✅ v2.3.0 |
| 14 | mandatoryprogrammer/thermoptic | Browser-grade JA4+ camouflaging egress | ✅ v2.3.0 |
| 15 | guell11/OmniClaw-GLM-Proxy | Local React dashboard | ✅ v2.3.0 |
| 1–6, 8–9 | — | caps / banner / negative cache / i18n / `!router` / OWL / DSML / fingerprint+loop_breaker | ✅ v2.0.0–v2.2.0 |

**Every actionable synergy in the Top-15 matrix is now shipped** (#7 was the
last; harvesting stays browser-based by design — Google SSO cannot be
HTTP-ized, so #7 imports desktop-extracted tokens instead).

## New in this repo

- `integrations/autoclaw-owl/token_import.py` — import module (3 formats,
  JWT jti-email, device_id preservation, dedupe, fail-safe per-record)
- DSML real-world metrics: grain-correct counters, markup-leak taxonomy,
  overhead ring, honest rates (`/health` superset + dashboard DSML panel)
- Metrics persistence (versioned JSON, atomic, rollups 72 h) + telemetry
  hygiene (streaming latency = true duration; `/health` unrecorded; WS
  keepalive + client cap; clients LRU cap)
- Dashboard: DSML panel, hourly history, reconnect backoff, formatting
- 180-test offline suite (149 → 180), 0 regressions

## Live-verified in sandbox

- Blank-page `/dashboard` bug found by headless-browser verification and
  fixed (308 → `/dashboard/`)
- Persistence proven: restart restored `requests` + request log exactly
- `features.dsml_shim` now ticks on real traffic (was dead documentation)
