# owl-dns-synergy v2.2.0 — Phase 2: DSML shim × fingerprint × loop_breaker

`autoclaw-autologin` **v2.2.0** lands Phase 2 of the synergy roadmap
(items 2.3 / 2.4 / 2.5 from the AutoClaw Ecosystem Synergy Research
Deep-Dive), on top of the v2.1.0 OWL-AGENT network layer.

## What arrived in this phase

| # | Source repo | Synergy | Status |
|---|---|---|---|
| 8 | tt-52101/chat-z-ai-proxy | **DSML tool-calling shim** — synthesised OpenAI function-calling (buffered + streaming via StreamSieve) | ✅ v2.2.0 |
| 9 | eroslifestyle/ai-router-switch | **Per-chat fingerprint isolation** — SHA-256 first-user-message, pin-on-first-use account affinity, repin-on-drift | ✅ v2.2.0 |
| 9 | eroslifestyle/ai-router-switch | **loop_breaker** — 4+ same-turn re-emits at ≥80% context fill → HTTP 400 forced restart | ✅ v2.2.0 |

## Full synergy ledger

| # | Source | Synergy | Status |
|---|--------|---------|--------|
| 1–4 | eequaled/GLM_proxy | Output caps / banner / negative cache / i18n | ✅ v2.0.0 |
| 5 | eroslifestyle/ai-router-switch | `!router` command | ✅ v2.0.0 |
| 6 | OWL-AGENT v5.3 | proxy-first defense layer | ✅ v2.1.0 |
| 7 | sitimas9/autoclaw2api | Server-first no-CloakBrowser mode | Phase 2 (deferred) |
| 8 | tt-52101/chat-z-ai-proxy | **DSML tool-calling shim** | ✅ **v2.2.0** |
| 9 | eroslifestyle/ai-router-switch | **Per-chat fingerprint + loop_breaker** | ✅ **v2.2.0** |
| 10 | sabyaghosh/glm-free-api-admin-panel | uTLS Chrome 120 | Partial (curl_cffi flag) |
| 11 | eequaled/GLM_proxy | Local WS fallback | Phase 3 |
| 12 | guell11/OmniClaw | React dashboard | Phase 3 |

## New in this repo

- `integrations/autoclaw-owl/` — synced Phase-2 sources:
  `dsml_shim.py`, `chat_fingerprint.py`, `loop_breaker.py`
- 112-test offline suite (61 v2.1.0 + 51 Phase-2), 0 regressions

## Assets

- `owl-dns-synergy-v2.2.0.tar.gz` — this repo @ v2.2.0
- `autoclaw-autologin-v2.2.0.tar.gz` — integrated release source
