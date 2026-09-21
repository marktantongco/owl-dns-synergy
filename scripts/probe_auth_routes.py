#!/usr/bin/env python3
"""Probe every plausible upstream auth route for token acquisition.

Verdicts wanted:
  R1  POST /userapi/overseasv1/google-oauth-url   (signed)  — live | 405
  R2  POST /userapi/v1/app-login                  (signed)  — reachable?
  R3  POST /userapi/v1/app-login                  + email/password — accepted?
  R4  POST /userapi/v1/oneclick-login             (signed)  — reachable?
  R5  POST /userapi/v1/login (guess)              + email/password — exists?
  R6  WAF UA check: python-requests UA vs desktop UA control

Never prints passwords; only route verdicts + upstream codes.
"""
import hashlib
import json
import sys
import time
import uuid
import warnings

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, "/home/z/my-project/repos/autoclaw-autologin")
from config import (APP_ID, APP_KEY, PRODUCT, VERSION, PLATFORM,
                    USER_API_BASE, GOOGLE_OAUTH_URL)

BASE = USER_API_BASE
CANDIDATE_ACCOUNT = ("mymarky0@gmail.com", "Tanky1986!")  # first account only


def sign_headers(ua=None):
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
        "User-Agent": ua or ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) "
                             "autoclaw/2.5.0 Chrome/120.0.0.0 Electron/28.0.0 "
                             "Safari/537.36"),
    }


def post(path, body, ua=None, label=""):
    url = BASE + path
    try:
        r = requests.post(url, headers=sign_headers(ua), json=body,
                          timeout=12, verify=False)
        is_html = "text/html" in r.headers.get("Content-Type", "")
        try:
            data = r.json()
            code = data.get("code")
            msg = str(data.get("msg", ""))[:80]
        except Exception:
            data, code, msg = None, f"HTTP {r.status_code} (non-JSON)", ""
        print(f"[{label}] {path} -> HTTP {r.status_code} "
              f"{'HTML-WAF' if is_html else 'JSON'} code={code} msg={msg}")
        return r.status_code, data
    except Exception as exc:
        print(f"[{label}] {path} -> ERROR {str(exc)[:100]}")
        return None, None


def main():
    print("=" * 78)
    print(f"Auth-route probe @ {time.strftime('%Y-%m-%d %H:%M:%S')} base={BASE}")
    print("=" * 78)

    # R6 control: WAF UA discrimination (2 quick requests)
    print("\n--- R6: WAF UA discrimination control ---")
    post("/userapi/v1/refresh", {}, ua="python-requests/2.32.5",
         label="R6a requests-UA")
    post("/userapi/v1/refresh", {}, label="R6b desktop-UA")

    # R1: OAuth URL route — the deprecation verdict from 2026-09-19
    print("\n--- R1: google-oauth-url (signed, desktop UA) ---")
    body = {"source_id": "autoclaw",
            "device_id": str(uuid.uuid4()),
            "navigate_uri": "http://localhost:18432/auth/callback-google"}
    sc, data = post("/userapi/overseasv1/google-oauth-url", body, label="R1")
    if isinstance(data, dict) and data.get("code") == 0:
        print("    *** OAUTH URL ROUTE IS LIVE ***")
        ou = data.get("data", {}).get("oauth_url", "")
        print(f"    oauth_url prefix: {ou[:110]}")
        with open("/home/z/my-project/scripts/.oauth_url_live.json", "w") as f:
            json.dump(data["data"], f)
    elif sc == 405:
        print("    -> still 405-deprecated (matches 2026-09-19 verdict)")

    # R2/R3: app-login — empty (reachability) then with credentials
    print("\n--- R2: app-login empty (reachability probe) ---")
    post("/userapi/v1/app-login", {}, label="R2")

    print("\n--- R3: app-login with email+password ---")
    email, pwd = CANDIDATE_ACCOUNT
    post("/userapi/v1/app-login",
         {"email": email, "password": pwd, "source_id": "autoclaw",
          "device_id": str(uuid.uuid4())}, label="R3a email+password")
    post("/userapi/v1/app-login",
         {"account": email, "password": pwd, "source_id": "autoclaw",
          "device_id": str(uuid.uuid4())}, label="R3b account+password")

    # R4: oneclick-login — empty
    print("\n--- R4: oneclick-login empty (reachability probe) ---")
    post("/userapi/v1/oneclick-login", {}, label="R4")

    # R5: candidate password-login routes
    print("\n--- R5: other candidate login routes ---")
    for path in ("/userapi/v1/login", "/userapi/overseasv1/login",
                 "/userapi/v1/email-login", "/userapi/v1/password-login"):
        post(path, {"email": email, "password": pwd,
                    "source_id": "autoclaw", "device_id": str(uuid.uuid4())},
             label="R5")

    print("\nProbe complete.")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
