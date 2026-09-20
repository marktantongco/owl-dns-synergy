# owl-dns-synergy v2.5.0 — Dashboard Auth Surface (SPEC-8b7)

Mirror release of [autoclaw-autologin v2.5.0](https://github.com/marktantongco/autoclaw-autologin/releases/tag/v2.5.0).

**Scope:** the top remaining 8-b backlog item — the dashboard/telemetry
authentication surface, per `SPEC-8b7` (research-graded, evidence-based).

## Highlights

- **Fail-closed posture (D2):** with `AUTOCLAW_PROXY_API_KEY` configured,
  `/api/dashboard/state`, `/api/dashboard/control` and the WS stream require
  Bearer or a session cookie; WITHOUT a key, control is **503
  `auth_unconfigured` (never open)** and reads are loopback-only — fixing
  8-b findings #1/#2/#3 (unauthenticated state/control/WS surfaces).
- **Stateless session bootstrap (D1):** `POST /api/dashboard/auth` exchanges
  the Bearer key once for an `HttpOnly; SameSite=Strict` cookie (8h,
  HMAC-signed with an API-key-derived key — multi-worker-safe, rotation
  invalidates all sessions, constant-time verify). `DELETE` signs out.
- **CSRF defense (D1a):** Origin/Host check on cookie-authenticated mutations.
- **WS one-time tickets (D3):** 60s single-use tickets via
  `GET /api/dashboard/ticket` + `?ticket=` handshake; unauthenticated →
  error frame + close 4001; tickets redacted from access logs (D5).
- **Backoff + audit (D5):** 5 fails/60s/source → 429; failed dashboard auth
  recorded as `blocks.auth_failed` in the metrics registry.
- **UI (D4):** login card (key never stored), 401-aware fetches with
  `credentials: same-origin`, sign-out, fail-closed control banner,
  `ACLAW_DASHBOARD_PUBLIC=1` warning banner.
- **Carries:** `ACLAW_OAUTH_MODE=import` deploy enforcement (upstream OAuth
  route live-probe-confirmed 405-deprecated 2026-09-19).

## Verification

- Offline suite **198/198** (17 new auth tests: posture matrix, session
  crypto, CSRF, ticket lifecycle, WS handshake matrix, redaction, backoff).
- `integrations/autoclaw-owl/` code mirror synced from autoclaw-autologin
  (proxy.py byte-identical).
