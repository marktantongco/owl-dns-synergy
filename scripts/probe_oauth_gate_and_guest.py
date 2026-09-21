#!/usr/bin/env python3
"""Probe 3: last pure-HTTP harvest options.
  D) google-oauth-login gate status (random code/state — verdict shape)
  E) google-oauth-url with X-Tm / X-Product / UA variants
  F) guest/visitor login route discovery
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


def hdrs(version="2.5.0", platform="win", product="autoclaw", ua=None):
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


def post(path, body, headers, label=""):
    try:
        r = requests.post(BASE + path, headers=headers, json=body,
                          timeout=12, verify=False)
        try:
            d = r.json()
            code, msg = d.get("code"), str(d.get("msg", ""))[:72]
        except Exception:
            d, code, msg = None, f"HTTP {r.status_code} non-JSON", ""
        print(f"[{label}] {path} -> code={code} msg={msg}")
        return code, d
    except Exception as exc:
        print(f"[{label}] {path} -> ERROR {str(exc)[:90]}")
        return None, None


def part_d():
    print("=" * 78)
    print("D) google-oauth-login gate status (random code+state)")
    print("=" * 78)
    body = {"code": "probe-" + uuid.uuid4().hex[:16],
            "state": uuid.uuid4().hex,
            "navigate_uri": "http://localhost:18432/auth/callback-google",
            "device_id": str(uuid.uuid4()), "source_id": "autoclaw"}
    post("/userapi/overseasv1/google-oauth-login", body, hdrs(), label="D")


def part_e():
    print("\n" + "=" * 78)
    print("E) google-oauth-url header-variant matrix")
    print("=" * 78)
    body = {"source_id": "autoclaw", "device_id": str(uuid.uuid4()),
            "navigate_uri": "http://localhost:18432/auth/callback-google"}
    for tm in ("win32", "windows", "darwin", "win64"):
        post("/userapi/overseasv1/google-oauth-url", body,
             hdrs(platform=tm), label=f"E tm={tm}")
    for prod in ("autoclaw-pro", "autoclaw_desktop", "zai", "chat"):
        post("/userapi/overseasv1/google-oauth-url", body,
             hdrs(product=prod), label=f"E prod={prod}")
    # okhttp mobile UA + android tm (mobile app profile)
    h = hdrs(platform="android",
             ua="okhttp/4.12.0")
    post("/userapi/overseasv1/google-oauth-url", body, h, label="E okhttp/android")
    # unknown-version style (some apps send build numbers)
    for v in ("100", "26.0", "2.5", "latest"):
        post("/userapi/overseasv1/google-oauth-url", body,
             hdrs(version=v), label=f"E v={v}")


def part_f():
    print("\n" + "=" * 78)
    print("F) guest/visitor login route discovery")
    print("=" * 78)
    did = str(uuid.uuid4())
    h = hdrs()
    for path in ("/userapi/v1/guest-login", "/userapi/v1/visitor-login",
                 "/userapi/v1/tourist-login", "/userapi/v1/anonymous-login",
                 "/userapi/overseasv1/guest-login", "/userapi/v1/register",
                 "/userapi/v1/device-login", "/userapi/v1/tourist"):
        body = {"source_id": "autoclaw", "device_id": did}
        post(path, body, h, label="F")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    part_d()
    part_e()
    part_f()
    print("\nProbe-3 complete.")
