#!/usr/bin/env python3
"""Probe non-overseasv1 OAuth variants + app-login field contract discovery."""
import sys, os, json, time, uuid, hashlib, itertools
import urllib3
urllib3.disable_warnings()

REPO = "/home/z/my-project/repos/autoclaw-autologin"
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ["OWL_PROXY_ENABLED"] = "0"

import requests
from config import APP_ID, APP_KEY, PRODUCT

BASE = "https://autoglm-api.autoglm.ai"
V = "1.44.0"

def sign_headers():
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    return {
        "X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sign,
        "X-Product": PRODUCT, "X-Version": V, "X-Tm": "win",
        "X-Trace-Id": str(uuid.uuid4()), "Content-Type": "application/json",
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       f"autoclaw/{V} Chrome/120.0.0.0 Electron/28.0.0 Safari/537.36"),
    }

def post(url, body):
    try:
        r = requests.post(url, headers=sign_headers(), json=body, timeout=12, verify=False)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"_raw": r.text[:100]}
    except Exception as e:
        return None, {"_error": str(e)[:100]}

def show(label, sc, d):
    slim = {k: d.get(k) for k in ("code", "msg") if k in d}
    if "_raw" in d: slim["_raw"] = d["_raw"]
    if "_error" in d: slim["_error"] = d["_error"]
    print(f"{label:<52} HTTP {sc} {json.dumps(slim, ensure_ascii=False)[:170]}")

def main():
    did = str(uuid.uuid4())
    nav = "http://localhost:18432/auth/callback-google"

    print("=== non-overseasv1 OAuth variants (route existence) ===")
    for path in ("/userapi/v1/google-oauth-url",
                 "/userapi/v1/google-oauth-login",
                 "/userapi/overseasv1/app-login",
                 "/userapi/overseasv1/oneclick-login",
                 "/userapi/v1/login", "/userapi/v1/email-login",
                 "/userapi/v1/password-login", "/userapi/v1/token-login",
                 "/userapi/overseasv1/email-login"):
        sc, d = post(BASE + path, {"device_id": did, "source_id": "autoclaw"})
        show(path, sc, d)
        time.sleep(0.8)

    print("=== app-login field contract discovery ===")
    field_sets = [
        {"email": "mymarky0@gmail.com"},
        {"email": "mymarky0@gmail.com", "password": "x"},
        {"username": "mymarky0@gmail.com", "password": "x"},
        {"auth_code": "x", "device_id": did},
        {"ticket": "x", "device_id": did},
        {"code": "x", "device_id": did},
        {"token": "x", "device_id": did},
        {"google_token": "x", "device_id": did, "source_id": "autoclaw"},
        {"id_token": "x", "device_id": did, "source_id": "autoclaw"},
        {"navigate_uri": nav, "device_id": did, "auth_type": "google"},
    ]
    for fs in field_sets:
        sc, d = post(BASE + "/userapi/v1/app-login", fs)
        show(f"app-login {sorted(fs.keys())}", sc, d)
        time.sleep(0.8)

    print("=== oneclick-login field contract discovery ===")
    for fs in [{"email": "mymarky0@gmail.com"}, {"device_id": did, "auth_code": "x"},
               {"token": "x"}, {"email": "mymarky0@gmail.com", "device_id": did}]:
        sc, d = post(BASE + "/userapi/v1/oneclick-login", fs)
        show(f"oneclick-login {sorted(fs.keys())}", sc, d)
        time.sleep(0.8)

if __name__ == "__main__":
    main()
