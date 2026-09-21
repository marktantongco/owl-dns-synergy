#!/usr/bin/env python3
"""Extended version sweep for the 631002 gate on google-oauth-url.

Hypothesis: desktop versioning is 1.x (token_import.py: "desktop v1.17.6+"),
so sweep 1.14.0..1.22.x + a few oddballs. Also probe candidate update-check
endpoints that might reveal the true latest version string.
"""
import sys, os, json, time, uuid, hashlib
import urllib3
urllib3.disable_warnings()

REPO = "/home/z/my-project/repos/autoclaw-autologin"
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ["OWL_PROXY_ENABLED"] = "0"

import requests
from config import APP_ID, APP_KEY, PRODUCT, GOOGLE_OAUTH_URL

BASE = "https://autoglm-api.autoglm.ai"

CANDIDATES = [
    "1.14.0", "1.15.0", "1.16.0", "1.16.5", "1.17.0", "1.17.5", "1.17.6",
    "1.17.7", "1.17.8", "1.18.0", "1.18.1", "1.18.2", "1.19.0", "1.19.5",
    "1.20.0", "1.21.0", "1.22.0", "1.25.0", "1.30.0",
    "2.0.0", "2.10.0", "2.25.0", "2.50.0",
    "0.0.0", "99.99.99",
]

UPDATE_ENDPOINTS = [
    "/userapi/v1/version", "/userapi/v1/app-version", "/userapi/v1/versions",
    "/userapi/v1/update", "/userapi/v1/latest-version",
    "/userapi/overseasv1/version", "/userapi/v1/config",
]

def sign_headers(version):
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    return {
        "X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sign,
        "X-Product": PRODUCT, "X-Version": version, "X-Tm": "win",
        "X-Trace-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       f"autoclaw/{version} Chrome/120.0.0.0 Electron/28.0.0 "
                       "Safari/537.36"),
    }

def oauth_probe(version):
    body = {"source_id": "autoclaw", "device_id": str(uuid.uuid4()),
            "navigate_uri": "http://localhost:18432/auth/callback-google"}
    try:
        r = requests.post(GOOGLE_OAUTH_URL, headers=sign_headers(version),
                          json=body, timeout=15, verify=False)
        d = r.json()
        return d.get("code"), (d.get("msg") or "")[:60], d
    except Exception as e:
        return None, str(e)[:60], None

def main():
    print("=== oauth-url version sweep (1.x hypothesis) ===")
    for v in CANDIDATES:
        code, msg, data = oauth_probe(v)
        tag = ""
        if code == 0:
            tag = "  <<<< LIVE!"
        elif code not in (631002,):
            tag = "  <- PAST THE GATE"
        print(f"  {v:>8}: code={code} {msg}{tag}")
        if code == 0:
            print(json.dumps(data, ensure_ascii=False)[:500])
            return 0
        time.sleep(1.2)

    print("=== update/version endpoint discovery ===")
    for ep in UPDATE_ENDPOINTS:
        try:
            r = requests.post(BASE + ep, headers=sign_headers("1.17.6"),
                              json={"source_id": "autoclaw"}, timeout=10, verify=False)
            try:
                d = r.json()
                slim = {k: d.get(k) for k in ("code", "msg", "data")}
                print(f"  POST {ep:<36} HTTP {r.status_code} {json.dumps(slim, ensure_ascii=False)[:180]}")
            except Exception:
                print(f"  POST {ep:<36} HTTP {r.status_code} (non-JSON)")
        except Exception as e:
            print(f"  POST {ep:<36} ERR {str(e)[:80]}")
    return 1

if __name__ == "__main__":
    sys.exit(main())
