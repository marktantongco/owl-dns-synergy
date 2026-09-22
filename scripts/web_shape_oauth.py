#!/usr/bin/env python3
"""Day-3.9: WEB-CLIENT-SHAPED google-oauth-url probe (the decisive one).

Recipe reverse-engineered from the autoglm.ai web bundle (index-Dg1UNjIK.js):
  headers: X-Auth-Appid 100003 (same APP_KEY sign), X-Product "rumination",
           X-Tm <screen store>, X-Version "1.44.0" (pkg.version),
           X-Finger-Print-ID <FingerprintJS visitorId 32-hex>, X-Lang,
           real Chrome UA (web requests originate in-browser)
  body:    withWebInfo() = {device_id: <localStorage uuid>,
                            source_id: "web", ...}
           oauthGoogleUrl -> /userapi/overseasv1/google-oauth-url
  redirect allowlist: https://autoglm.ai/login/oauth-callback/google

Prior probes failed because we sent the DESKTOP shape (X-Product autoclaw,
source_id autoclaw, no fingerprint). If this returns code=0 we receive
{oauth_url, state} -> stealth-browser Google login -> exchange -> TOKEN.
"""
import hashlib
import json
import random
import string
import sys
import time
import uuid
import warnings

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

sys.path.insert(0, "/home/z/my-project/repos/autoclaw-autologin")
from config import APP_ID, APP_KEY

BASE = "https://autoglm-api.autoglm.ai"
OAUTH_URL = "/userapi/overseasv1/google-oauth-url"
CHROME_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
             "AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/131.0.0.0 Safari/537.36")
OUT = "/home/z/my-project/scripts/.oauth_url_live.json"
results = []


def fp_id():
    """FingerprintJS-visitorId-shaped value (32 hex chars)."""
    return "".join(random.choices("0123456789abcdef", k=32))


def web_headers(fingerprint=None, tm="web", version="1.44.0",
                product="rumination", lang="en", ua=CHROME_UA, auth=None):
    ts = str(int(time.time()))
    sg = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    h = {"X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sg,
         "X-Product": product, "X-Tm": tm, "X-Version": version,
         "X-Finger-Print-ID": fingerprint or fp_id(), "X-Lang": lang,
         "Content-Type": "application/json", "User-Agent": ua,
         "Origin": "https://autoglm.ai", "Referer": "https://autoglm.ai/login",
         "Accept": "application/json, text/plain, */*",
         "Accept-Language": "en-US,en;q=0.9",
         "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
         "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
         "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors",
         "Sec-Fetch-Site": "cross-site"}
    if auth:
        h["authorization"] = auth
    return h


def post(path, body, h, label):
    try:
        r = requests.post(BASE + path, headers=h, json=body, timeout=14,
                          verify=False)
        try:
            d = r.json()
            code, msg = d.get("code"), str(d.get("msg", ""))[:90]
            data = d.get("data")
        except Exception:
            d, code, msg, data = None, f"HTTP {r.status_code}", "non-JSON", None
        print(f"[{label}] code={code} {msg}")
        if data:
            print(f"    data: {json.dumps(data, ensure_ascii=False)[:300]}")
        results.append({"label": label, "code": str(code), "msg": msg,
                        "data": data})
        return code, d
    except Exception as exc:
        print(f"[{label}] ERROR {str(exc)[:90]}")
        results.append({"label": label, "code": "EXC", "msg": str(exc)[:90]})
        return None, None


def main():
    did = str(uuid.uuid4())
    navigate = "https://autoglm.ai/login/oauth-callback/google"

    # V1 — full web shape (the decisive attempt)
    body = {"device_id": did, "source_id": "web", "navigate_uri": navigate}
    code, d = post(OAUTH_URL, body, web_headers(), "V1 full-web-shape")
    if code == 0 and isinstance(d, dict) and d.get("data"):
        with open(OUT, "w") as f:
            json.dump({"data": d["data"], "device_id": did,
                       "navigate_uri": navigate,
                       "fingerprint": h_fp}, f)
        print("*** OAUTH URL ACQUIRED — see", OUT, "***")
        return

    # V2 — control: no X-Finger-Print-ID (is the fingerprint the key?)
    h = web_headers()
    h.pop("X-Finger-Print-ID")
    post(OAUTH_URL, body, h, "V2 no-fingerprint")
    time.sleep(0.4)

    # V3 — control: desktop source_id with web shape
    post(OAUTH_URL, {"device_id": did, "source_id": "autoclaw",
                     "navigate_uri": navigate},
         web_headers(), "V3 web-hdrs+autoclaw-src")
    time.sleep(0.4)

    # V4 — X-Tm desktop value variant
    post(OAUTH_URL, body, web_headers(tm="desktop"), "V4 tm=desktop")
    time.sleep(0.4)

    # V5 — zai oauth-url variant (bonus route seen in bundle)
    post("/userapi/overseasv1/zai-oauth-url", body, web_headers(),
         "V5 zai-oauth-url")
    time.sleep(0.4)

    # V6 — same-origin navigate (root)
    post(OAUTH_URL, {"device_id": did, "source_id": "web",
                     "navigate_uri": "https://autoglm.ai/"},
         web_headers(), "V6 navigate-root")

    with open("/home/z/my-project/scripts/web_shape_oauth_results.json",
              "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nDay-3.9 web-shape probe complete.")


if __name__ == "__main__":
    main()
