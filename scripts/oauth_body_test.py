#!/usr/bin/env python3
"""Test the corrected web body contract for google-oauth-url.

device_id must be 32-hex (UUID without dashes). Test matrix:
  A. no rid        -> does server demand the captcha rid?
  B. bogus rid     -> does server validate it with Shumei backend?
  C. dashed uuid   -> format sensitivity check
"""
import sys, os, json, time, uuid, hashlib
import urllib3
urllib3.disable_warnings()

REPO = "/home/z/my-project/repos/autoclaw-autologin"
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ["OWL_PROXY_ENABLED"] = "0"

import requests

APP_ID = "100003"
APP_KEY = "38d2391985e2369a5fb8227d8e6cd5e5"
BASE = "https://autoglm-api.autoglm.ai"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def headers():
    ts = int(time.time())
    sign = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    return {
        "X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": str(ts), "X-Auth-Sign": sign,
        "X-Lang": "en", "X-Product": "rumination", "X-Agent-OS": "web",
        "X-Finger-Print-ID": uuid.uuid4().hex,
        "Origin": "https://autoglm.ai", "Referer": "https://autoglm.ai/login",
        "Content-Type": "application/json", "User-Agent": UA,
    }

def post(path, body):
    r = requests.post(BASE + path, headers=headers(), json=body, timeout=20, verify=False)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"_raw": r.text[:150]}

def show(label, sc, d):
    slim = {k: d.get(k) for k in ("code", "msg") if k in d}
    data = d.get("data")
    if isinstance(data, dict):
        slim["data_keys"] = sorted(data.keys())
        if data.get("oauth_url"):
            slim["oauth_url"] = data["oauth_url"][:130]
    if "_raw" in d: slim["_raw"] = d["_raw"]
    print(f"{label:<38} HTTP {sc} {json.dumps(slim, ensure_ascii=False)[:300]}")

def main():
    did32 = uuid.uuid4().hex  # 32 hex chars, no dashes
    did_dash = str(uuid.uuid4())
    nav = "https://autoglm.ai/login/oauth-callback/google"

    sc, d = post("/userapi/overseasv1/google-oauth-url",
                 {"device_id": did32, "source_id": "web", "navigate_uri": nav})
    show("A: 32hex, NO rid", sc, d)

    sc, d = post("/userapi/overseasv1/google-oauth-url",
                 {"device_id": did32, "source_id": "web", "navigate_uri": nav,
                  "rid": "bogus-rid-probe"})
    show("B: 32hex, bogus rid", sc, d)

    sc, d = post("/userapi/overseasv1/google-oauth-url",
                 {"device_id": did_dash, "source_id": "web", "navigate_uri": nav})
    show("C: dashed uuid, no rid", sc, d)

if __name__ == "__main__":
    main()
