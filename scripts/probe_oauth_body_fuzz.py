#!/usr/bin/env python3
"""Probe 4: oauth-url body schema fuzz on the gate-passing platform headers
(X-Tm: darwin / win32 / android) + overseasv2 route discovery.

Goal: turn 400001 "Request data error" into a live oauth_url payload.
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
from config import APP_ID, APP_KEY, PRODUCT, USER_API_BASE

BASE = USER_API_BASE
DID = str(uuid.uuid4())
NAV = "http://localhost:18432/auth/callback-google"


def hdrs(version="2.5.0", platform="darwin", product="autoclaw", ua=None):
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    return {
        "X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sign,
        "X-Product": product, "X-Version": version, "X-Tm": platform,
        "X-Trace-Id": str(uuid.uuid4()), "Content-Type": "application/json",
        "User-Agent": ua or ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) "
                             f"autoclaw/{version} Chrome/120.0.0.0 "
                             "Electron/28.0.0 Safari/537.36"),
    }


def post(path, body, headers, label="", show_data=True):
    try:
        r = requests.post(BASE + path, headers=headers, json=body,
                          timeout=12, verify=False)
        try:
            d = r.json()
            code, msg = d.get("code"), str(d.get("msg", ""))[:80]
        except Exception:
            d, code, msg = None, f"HTTP {r.status_code} non-JSON", ""
        hit = ""
        if code == 0 and isinstance(d, dict) and isinstance(d.get("data"), dict):
            hit = "  *** LIVE ***"
            if show_data:
                print(f"[{label}] {path} -> code=0{hit}")
                for k, v in d["data"].items():
                    print(f"      {k}: {str(v)[:100]}")
                with open("/home/z/my-project/scripts/.oauth_url_live.json",
                          "w") as f:
                    json.dump(d["data"], f)
                return code, d
        print(f"[{label}] {path} -> code={code} msg={msg}{hit}")
        return code, d
    except Exception as exc:
        print(f"[{label}] {path} -> ERROR {str(exc)[:90]}")
        return None, None


def part_g_routes():
    print("=" * 78)
    print("G) v2 route discovery (darwin header)")
    print("=" * 78)
    h = hdrs()
    body = {"source_id": "autoclaw", "device_id": DID, "navigate_uri": NAV}
    for p in ("/userapi/overseasv2/google-oauth-url",
              "/userapi/v2/google-oauth-url",
              "/userapi/overseasv2/google-oauth-login",
              "/userapi/v2/oauth-url", "/userapi/overseasv1/oauth-url"):
        post(p, body, h, label="G")


def part_h_body_fuzz():
    print("\n" + "=" * 78)
    print("H) oauth-url body fuzz (X-Tm: darwin)")
    print("=" * 78)
    h = hdrs()
    variants = [
        ("h0 empty", {}),
        ("h1 did only", {"device_id": DID}),
        ("h2 full (current)", {"source_id": "autoclaw", "device_id": DID,
                               "navigate_uri": NAV}),
        ("h3 no navigate", {"source_id": "autoclaw", "device_id": DID}),
        ("h4 no source", {"device_id": DID, "navigate_uri": NAV}),
        ("h5 nav 127.0.0.1", {"source_id": "autoclaw", "device_id": DID,
                              "navigate_uri": "http://127.0.0.1:18432/auth/callback-google"}),
        ("h6 deep link", {"source_id": "autoclaw", "device_id": DID,
                          "navigate_uri": "autoclaw://auth/callback"}),
        ("h7 https callback", {"source_id": "autoclaw", "device_id": DID,
                               "navigate_uri": "https://autoclaw.ai/auth/callback-google"}),
        ("h8 +platform field", {"source_id": "autoclaw", "device_id": DID,
                                "navigate_uri": NAV, "platform": "darwin"}),
        ("h9 +version field", {"source_id": "autoclaw", "device_id": DID,
                               "navigate_uri": NAV, "version": "2.5.0"}),
        ("h10 +locale", {"source_id": "autoclaw", "device_id": DID,
                         "navigate_uri": NAV, "locale": "en-US"}),
        ("h11 mac source_id", {"source_id": "autoclaw_mac",
                               "device_id": DID, "navigate_uri": NAV}),
        ("h12 source=desktop", {"source_id": "desktop", "device_id": DID,
                                "navigate_uri": NAV}),
    ]
    for name, body in variants:
        post("/userapi/overseasv1/google-oauth-url", body, h, label=name)


def part_i_android():
    print("\n" + "=" * 78)
    print("I) android profile oauth-url (okhttp UA)")
    print("=" * 78)
    h = hdrs(platform="android", ua="okhttp/4.12.0")
    variants = [
        ("i1 full", {"source_id": "autoclaw", "device_id": DID,
                     "navigate_uri": NAV}),
        ("i2 +pkg", {"source_id": "autoclaw", "device_id": DID,
                     "navigate_uri": NAV, "package_name": "ai.autoclaw.app"}),
    ]
    for name, body in variants:
        post("/userapi/overseasv1/google-oauth-url", body, h, label=name)


def part_j_mac_profile():
    print("\n" + "=" * 78)
    print("J) darwin UA variants")
    print("=" * 78)
    for ua in ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
               "AppleWebKit/537.36 (KHTML, like Gecko) autoclaw/2.5.0 "
               "Chrome/120.0.0.0 Electron/28.0.0 Safari/537.36",
               "okhttp/4.12.0"):
        h = hdrs(ua=ua)
        post("/userapi/overseasv1/google-oauth-url",
             {"source_id": "autoclaw", "device_id": DID,
              "navigate_uri": NAV}, h, label=f"J ua={ua[:40]}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    part_g_routes()
    part_h_body_fuzz()
    part_i_android()
    part_j_mac_profile()
    print("\nProbe-4 complete.")
