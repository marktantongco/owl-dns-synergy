# Release Notes — owl-dns-synergy v2.1.0

**Date:** 2026-09-19 · **Theme:** Synergy 6 — OWL-AGENT × AutoClaw network layer

## What landed

`marktantongco/autoclaw-autologin` **v2.1.0** integrates the OWL-AGENT v5.3
proxy defense stack as AutoClaw's upstream network-resilience layer:

- **Proxy-first routing** for ALL upstream calls (chat SSE, token refresh,
  profile, wallet, ledger) with hedged 3-way parallel racing (6 s cap) and
  always-available direct fallback
- **Hybrid backend** — external `~/.owl-agent` install wins over the vendored
  module (GLM_proxy cloud→local pattern)
- **Full defense stack** — single-strike bans, adaptive per-domain rate
  limiting, network-failure circuit breakers, header-aware GET-only cache +
  dedup, SOCKS4/5, optional curl_cffi chrome110 TLS impersonation
- **Observability** — `X-Upstream-Via` response header, `/health` owl block,
  standalone `owl_proxy.py` CLI
- **61 committed offline tests** (first committed suite for the repo; includes
  Phase-1 synergy regression: output caps, banner injection, negative cache,
  CN→EN translation, !router)
- **Fixed:** duplicate SSE `[DONE]` terminator that could confuse strict
  OpenAI clients

## New in this repo

- `integrations/autoclaw-owl/` — synced integration sources + README with
  architecture map and ops quick reference
- `download/autoclaw-autologin-v2.1.0.tar.gz` — release source tarball
- `owl-dns-synergy-v2.1.0.tar.gz` — this repo snapshot

## Synergy ledger (cumulative)

| # | Source | Synergy | Status |
|---|--------|---------|--------|
| 1 | eequaled/GLM_proxy | Output-cap clamping | ✅ v2.0.0 |
| 2 | eequaled/GLM_proxy | System-banner injection | ✅ v2.0.0 |
| 3 | eequaled/GLM_proxy | Permanent-failure negative cache | ✅ v2.0.0 |
| 4 | eequaled/GLM_proxy | CN→EN error translation | ✅ v2.0.0 |
| 5 | eroslifestyle/ai-router-switch | In-chat `!router` command | ✅ v2.0.0 |
| 6 | **OWL-AGENT v5.3** | **Proxy-first defense layer (hybrid, streaming)** | ✅ **v2.1.0** |
| 7 | sitimas9/autoclaw2api | Server-first no-CloakBrowser mode | Phase 2 |
| 8 | tt-52101/chat-z-ai-proxy | DSML tool-calling shim | Phase 2 |
| 9 | eroslifestyle/ai-router-switch | Per-chat fingerprint, loop_breaker | Phase 2 |
| 10 | sabyaghosh/glm-free-api-admin-panel | uTLS Chrome 120 | Partial (curl_cffi flag) |
| 11 | eequaled/GLM_proxy | Local WS fallback | Phase 3 |
| 12 | guell11/OmniClaw | React dashboard | Phase 3 |
