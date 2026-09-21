#!/usr/bin/env python3
"""Deep route probe: map the live upstream auth surface.

1. /userapi/v1/app-login + /userapi/v1/oneclick-login  (unsigned + signed)
   - unsigned 400002 => route exists (middleware before routing)
   - signed 400001   => route exists AND tells required fields via msg
2. /userapi/v1/refresh with signed bogus token
   - non-631002 error => version gate is ROUTE-SPECIFIC (overseasv1 only)
3. /userapi/overseasv1/google-oauth-login (signed, bogus code)
   - tells whether the EXCHANGE route shares the version gate
"""
import sys, os, json, time, uuid, hashlib
import urllib3
urllib3.disable_warnings()

REPO = "/home/z/my-project/repos/autoclaw-autologin"
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ["OWL_PROXY_ENABLED"] = "0"

import requests
from config import APP_ID, APP_KEY, PRODUCT, VERSION, REFRESH_URL

BASE = "https://autoglm-api.autoglm.ai"

def sign_headers(version=None, ua=None):
    v = version or VERSION
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    return {
        "X-Auth-Appid": APP_ID,
        "X-Auth-TimeStamp": ts,
        "X-Auth-Sign": sign,
        "X-Product": PRODUCT,
        "X-Version": v,
        "X-Tm": "win",
        "X-Trace-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
        "User-Agent": ua or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) autoclaw/{v} Chrome/120.0.0.0 Electron/28.0.0 "
            "Safari/537.36"),
    }

def post(url, hdrs, body):
    try:
        r = requests.post(url, headers=hdrs, json=body, timeout=15, verify=False)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"_raw": r.text[:150]}
    except Exception as e:
        return None, {"_error": str(e)[:120]}

def show(label, sc, data):
    slim = {k: v for k, v in data.items() if k in
            ("code", "msg", "error", "data", "_error", "_raw")}
    print(f"{label:<58} HTTP {sc}  {json.dumps(slim, ensure_ascii=False)[:200]}")

def main():
    did = str(uuid.uuid4())

    # 1a. app-login unsigned (route existence)
    sc, d = post(f"{BASE}/userapi/v1/app-login", {"Content-Type": "application/json"}, {})
    show("[1a] app-login UNSIGNED {}", sc, d)

    # 1b. app-login signed empty body
    sc, d = post(f"{BASE}/userapi/v1/app-login", sign_headers(), {})
    show("[1b] app-login SIGNED {}", sc, d)

    # 1c. app-login signed with plausible fields
    body = {"device_id": did, "source_id": "autoclaw",
            "navigate_uri": "http://localhost:18432/auth/callback-google"}
    sc, d = post(f"{BASE}/userapi/v1/app-login", sign_headers(), body)
    show("[1c] app-login SIGNED {device_id,source_id,navigate_uri}", sc, d)

    # 2a. oneclick-login unsigned
    sc, d = post(f"{BASE}/userapi/v1/oneclick-login", {"Content-Type": "application/json"}, {})
    show("[2a] oneclick-login UNSIGNED {}", sc, d)

    # 2b. oneclick-login signed
    sc, d = post(f"{BASE}/userapi/v1/oneclick-login", sign_headers(), {"device_id": did})
    show("[2b] oneclick-login SIGNED {device_id}", sc, d)

    # 3. refresh with signed bogus token (route-specific gate check)
    body = {"source_id": "autoclaw", "device_id": did,
            "refresh_token": "bogus-refresh-token-probe-0123456789abcdef"}
    sc, d = post(REFRESH_URL, sign_headers(), body)
    show("[3 ] v1/refresh SIGNED bogus refresh_token", sc, d)

    # 4. overseasv1 google-oauth-login signed bogus code
    body = {"code": "bogus-oauth-code", "state": "bogus-state",
            "navigate_uri": "http://localhost:18432/auth/callback-google",
            "device_id": did, "source_id": "autoclaw"}
    sc, d = post(f"{BASE}/userapi/overseasv1/google-oauth-login", sign_headers(), body)
    show("[4 ] overseasv1/google-oauth-login SIGNED bogus", sc, d)

if __name__ == "__main__":
    main()
