#!/usr/bin/env python3
"""Live probe: is the AutoClaw google-oauth-url route still 405-deprecated?

Runs directly against autoglm-api.autoglm.ai with proper app signing
(APP_ID/APP_KEY/timestamp MD5), the desktop Electron UA, and a fresh
device_id — exactly as auth.google_oauth_url() would, minus proxies/retries.
"""
import sys, os, json, time, uuid, hashlib
import urllib3
urllib3.disable_warnings()

REPO = "/home/z/my-project/repos/autoclaw-autologin"
sys.path.insert(0, REPO)
os.chdir(REPO)

# Clean direct probe: disable OWL free-pool racing for a deterministic verdict
os.environ["OWL_PROXY_ENABLED"] = "0"

import requests
from config import (
    APP_ID, APP_KEY, PRODUCT, VERSION, PLATFORM,
    GOOGLE_OAUTH_URL, UPSTREAM_UA,
)

def sign_headers():
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    return {
        "X-Auth-Appid": APP_ID,
        "X-Auth-TimeStamp": ts,
        "X-Auth-Sign": sign,
        "X-Product": PRODUCT,
        "X-Version": VERSION,
        "X-Tm": PLATFORM,
        "X-Trace-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
        "User-Agent": UPSTREAM_UA,
    }

def main():
    device_id = str(uuid.uuid4())
    body = {
        "source_id": "autoclaw",
        "device_id": device_id,
        "navigate_uri": "http://localhost:18432/auth/callback-google",
    }
    hdrs = sign_headers()
    print(f"[*] POST {GOOGLE_OAUTH_URL}")
    print(f"[*] UA: {UPSTREAM_UA[:70]}...")
    print(f"[*] device_id: {device_id}")
    try:
        r = requests.post(GOOGLE_OAUTH_URL, headers=hdrs, json=body, timeout=20, verify=False)
    except Exception as e:
        print(f"[!] transport error: {e}")
        return 2
    print(f"[*] HTTP {r.status_code}")
    ctype = r.headers.get("content-type", "")
    print(f"[*] content-type: {ctype}")
    text = r.text[:600]
    if "json" in ctype:
        try:
            data = r.json()
            print(f"[*] body: {json.dumps(data, ensure_ascii=False)[:600]}")
            code = data.get("code")
            if r.status_code == 200 and code == 0:
                oauth = data.get("data", {}).get("oauth_url", "")
                print(f"[+] OAUTH ROUTE LIVE — oauth_url: {oauth[:120]}")
                print(f"[+] state: {data.get('data', {}).get('state', '')[:40]}")
                return 0
            print(f"[-] ROUTE REJECTED: code={code} msg={data.get('msg','')}")
            return 1
        except Exception as e:
            print(f"[!] json parse error: {e}; raw={text}")
            return 1
    else:
        # HTML challenge page = WAF block
        print(f"[-] non-JSON (likely WAF challenge). first 300 chars:")
        print(text[:300].replace("\n", " "))
        return 1

if __name__ == "__main__":
    sys.exit(main())
