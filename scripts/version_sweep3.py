#!/usr/bin/env python3
"""Targeted retry with the REAL current version (1.44.0 from autoglm.ai)."""
import sys, os, json, time, uuid, hashlib
import urllib3
urllib3.disable_warnings()

REPO = "/home/z/my-project/repos/autoclaw-autologin"
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ["OWL_PROXY_ENABLED"] = "0"

import requests
from config import APP_ID, APP_KEY, PRODUCT, GOOGLE_OAUTH_URL

CANDIDATES = ["1.44.0", "1.44.1", "1.43.0", "1.42.0", "1.45.0", "1.40.0", "1.35.0"]

def try_version(v):
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    hdrs = {
        "X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sign,
        "X-Product": PRODUCT, "X-Version": v, "X-Tm": "win",
        "X-Trace-Id": str(uuid.uuid4()), "Content-Type": "application/json",
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       f"autoclaw/{v} Chrome/120.0.0.0 Electron/28.0.0 Safari/537.36"),
    }
    body = {"source_id": "autoclaw", "device_id": str(uuid.uuid4()),
            "navigate_uri": "http://localhost:18432/auth/callback-google"}
    r = requests.post(GOOGLE_OAUTH_URL, headers=hdrs, json=body, timeout=15, verify=False)
    try:
        d = r.json()
    except Exception:
        return v, r.status_code, {"_raw": r.text[:120]}
    return v, r.status_code, d

def main():
    for v in CANDIDATES:
        v, sc, d = try_version(v)
        code = d.get("code")
        msg = (d.get("msg") or "")[:60]
        tag = "  <<<< LIVE!" if code == 0 else ("" if code == 631002 else "  <- PAST GATE")
        print(f"X-Version {v:>7}: HTTP {sc} code={code} {msg}{tag}")
        if code == 0:
            print(json.dumps(d, ensure_ascii=False)[:600])
            return 0
        time.sleep(1.2)
    return 1

if __name__ == "__main__":
    sys.exit(main())
