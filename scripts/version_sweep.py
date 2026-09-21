#!/usr/bin/env python3
"""Version sweep: find an X-Version that passes the 631002 version gate.

Sends the signed google-oauth-url request with candidate version strings
(both X-Version header and the autoclaw/x.y.z token inside the UA must match).
A DIFFERENT business code (400005 rate limit, 400001, etc.) means the version
gate PASSED and we're through to the real API logic.
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

BASE_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) autoclaw/{v} Chrome/120.0.0.0 Electron/28.0.0 "
           "Safari/537.36")

CANDIDATES = [
    "2.5.0", "2.5.1", "2.5.2", "2.6.0", "2.6.1", "2.6.2",
    "2.7.0", "2.7.1", "2.8.0", "2.9.0",
    "3.0.0", "3.0.1", "3.1.0", "3.2.0", "4.0.0",
]

def probe(version):
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    ua = BASE_UA.format(v=version)
    hdrs = {
        "X-Auth-Appid": APP_ID,
        "X-Auth-TimeStamp": ts,
        "X-Auth-Sign": sign,
        "X-Product": PRODUCT,
        "X-Version": version,
        "X-Tm": "win",
        "X-Trace-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
        "User-Agent": ua,
    }
    body = {
        "source_id": "autoclaw",
        "device_id": str(uuid.uuid4()),
        "navigate_uri": "http://localhost:18432/auth/callback-google",
    }
    try:
        r = requests.post(GOOGLE_OAUTH_URL, headers=hdrs, json=body,
                          timeout=15, verify=False)
        data = r.json()
        return r.status_code, data.get("code"), (data.get("msg") or "")[:80], data
    except Exception as e:
        return None, None, str(e)[:80], None

def main():
    for v in CANDIDATES:
        sc, code, msg, data = probe(v)
        flag = ""
        if code == 631002:
            flag = "  <- version gate"
        elif code == 0:
            flag = "  <<<< LIVE! oauth_url obtained"
        elif code == 400005:
            flag = "  <- rate limit (version ACCEPTED, shared quota)"
        else:
            flag = "  <- non-version error (version ACCEPTED)"
        print(f"X-Version {v:>6}: HTTP {sc} code={code}  {msg}{flag}")
        if code == 0:
            print(json.dumps(data, ensure_ascii=False)[:400])
            return 0
        time.sleep(1.5)
    return 1

if __name__ == "__main__":
    sys.exit(main())
