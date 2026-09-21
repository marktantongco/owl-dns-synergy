# AutoClaw Token Harvest & Import — Operator Guide

Goal: obtain ONE real AutoClaw JWT and feed the OWL-DNS-Synergy proxy so
`scripts/smoke_test_messages_live.py --token-file <file>` completes the
14/14 success path (real upstream 200 on `/v1/messages`).

## Why the Google credentials alone are not enough

Live-probed 2026-09-21 (autoglm-api.autoglm.ai):

| route | verdict |
|---|---|
| `POST /userapi/overseasv1/google-oauth-url` | **631002** "version no longer supported" (X-Tm: win); other X-Tm values rejected 400001 |
| `POST /userapi/overseasv1/google-oauth-login` | alive (631001 with garbage code/state) but needs a valid server-side state from step 1 |
| `POST /userapi/v1/app-login`, `/oneclick-login` | schema unknown — 16+ body shapes rejected (400001) |
| guest/visitor/device routes | 404 |
| chat.z.ai JWT vs autoglm-api | **410000 Invalid access token** (separate auth realms) |

Conclusion: email+password cannot be converted into an AutoClaw token by any
scripted path. The JWT must be lifted from a logged-in AutoClaw desktop app
(or an autoclaw2api-style export).

## Option A — harvest from the desktop app (recommended, ~2 min)

1. Open the AutoClaw desktop app and log in with the Google account.
2. Run the bundled harvester **on that machine**:

       python harvest_token.py

   It auto-finds `%LOCALAPPDATA%\AutoClaw\Local Storage\leveldb` (plus
   macOS/Linux equivalents), regex-scans the leveldb blobs for account JWTs,
   decodes `exp`/`jti` (the login email), and writes `autoclaw_token.json`:

       {
         "email": "mymarky0@gmail.com",
         "access_token": "eyJhbGciOi...",
         "refresh_token": "",
         "user_id": "...",
         "device_id": "",
         "source_id": "desktop-ls"
       }

   If the app's storage lives elsewhere, pass the path:

       python harvest_token.py "%LOCALAPPDATA%\AutoClaw\Local Storage\leveldb"

3. Verify the token upstream (optional):

       curl -s -X POST https://autoglm-api.autoglm.ai/userapi/v1/user-profile \
         -H "X-Auth-Appid: 100003" \
         -H "X-Authorization: Bearer <access_token>" \
         -H "Content-Type: application/json" -d "{}"

   `code: 0` = valid. `410000` = invalid/expired.

## Option B — autoclaw2api-style export

If you already run an autoclaw2api-style exporter, its token record is
imported as-is:

    {
      "email": "...", "access_token": "...", "refresh_token": "...",
      "user_id": "...", "device_id": "...", "source_id": "autoclaw2api"
    }

## Import into the proxy (either way)

1. **Watch-dir**: copy the JSON file into the directory named by
   `ACLAW_IMPORT_DIR` (default `<repo>/.autoclaw_imports`). It is ingested at
   boot or via the import API; duplicate emails update in place
   (dedupe key configurable via `ACLAW_IMPORT_DEDUPE`).
2. **API**:

       curl -X POST http://127.0.0.1:31000/api/tokens/import \
            -H "Content-Type: application/json" \
            -d @autoclaw_token.json

   Response is per-record: `{results:[{ok, email, action, warnings}], summary}`.
   `device_id` is minted when absent (desktop refresh_tokens may be
   device-bound — check `/health` → `token_import` counters).

## Final acceptance run

    python3 scripts/smoke_test_messages_live.py \
        --token-file autoclaw_token.json

Expected: 14/14 stages, upstream verdict switches from the probe's
`401 {"error":"Invalid token"}` to a real `200` completion on
`/v1/messages` (Anthropic wire), with credit-tier routing, negative-cache
replay, SSE stream, `!router status`, and telemetry all green.

## Multi-account note

All four provided accounts can be harvested the same way; the importer
accepts an `{"accounts": [...]}` fragment (merge key = email). The proxy
rotates accounts via `get_valid_token()`; per-chat fingerprint isolation is
already enforced by the v2.6.1 routing layer.
