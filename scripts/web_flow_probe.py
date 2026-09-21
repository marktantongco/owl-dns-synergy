#!/usr/bin/env python3
"""Replicate the WEB login fingerprint (from autoglm.ai bundle) against
google-oauth-url + zai-oauth-url. The 631002 gate previously hit only the
DESKTOP fingerprint (X-Product autoclaw, X-Version, source_id autoclaw)."""
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
WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def web_headers():
    ts = int(time.time())
    sign = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    return {
        "X-Auth-Appid": APP_ID,
        "X-Auth-TimeStamp": str(ts),
        "X-Auth-Sign": sign,
        "X-Lang": "en",
        "X-Product": "rumination",
        "X-Agent-OS": "web",
        "X-Finger-Print-ID": str(uuid.uuid4()),
        "Origin": "https://autoglm.ai",
        "Referer": "https://autoglm.ai/login",
        "Content-Type": "application/json",
        "User-Agent": WEB_UA,
    }

def post(path, body):
    r = requests.post(BASE + path, headers=web_headers(), json=body,
                      timeout=20, verify=False)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"_raw": r.text[:150]}

def show(label, sc, d):
    slim = {k: d.get(k) for k in ("code", "msg") if k in d}
    if "data" in d and d["data"] and isinstance(d["data"], dict):
        slim["data_keys"] = sorted(d["data"].keys())
        if "oauth_url" in d["data"]:
            slim["oauth_url"] = d["data"]["oauth_url"][:110]
    if "_raw" in d: slim["_raw"] = d["_raw"]
    print(f"{label:<44} HTTP {sc} {json.dumps(slim, ensure_ascii=False)[:260]}")

def main():
    did = str(uuid.uuid4())

    print("=== WEB fingerprint: google-oauth-url ===")
    body = {"device_id": did, "source_id": "web",
            "navigate_uri": "https://autoglm.ai/login/oauth-callback/google"}
    sc, d = post("/userapi/overseasv1/google-oauth-url", body)
    show("google-oauth-url {web}", sc, d)

    print("=== WEB fingerprint: zai-oauth-url ===")
    body2 = {"device_id": did, "source_id": "web",
             "navigate_uri": "https://autoglm.ai/login/oauth-callback/zai"}
    sc, d = post("/userapi/overseasv1/zai-oauth-url", body2)
    show("zai-oauth-url {web}", sc, d)

    print("=== guest login reachability ===")
    sc, d = post("/userapi/v1/auth/guest", {})
    show("auth/guest {}", sc, d)

if __name__ == "__main__":
    main()
