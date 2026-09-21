#!/usr/bin/env python3
"""Probe 2: version-gate escalation + app-login body-shape fuzzing.

A) google-oauth-url with escalating X-Version (2.5.0 -> 4.x) to find the
   631002 version gate boundary. On success, persist oauth_url.
B) app-login body-shape fuzz: field-name variants, password hashing modes,
   extra fields. Any non-400001 verdict is a schema hit.
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
EMAIL, PWD = "mymarky0@gmail.com", "Tanky1986!"
DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "autoclaw/{v} Chrome/120.0.0.0 Electron/28.0.0 Safari/537.36")


def hdrs(version, platform="win", ua=None):
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    return {
        "X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sign,
        "X-Product": PRODUCT, "X-Version": version, "X-Tm": platform,
        "X-Trace-Id": str(uuid.uuid4()), "Content-Type": "application/json",
        "User-Agent": ua or DESKTOP_UA.format(v=version),
    }


def post(path, body, headers, label=""):
    try:
        r = requests.post(BASE + path, headers=headers, json=body,
                          timeout=12, verify=False)
        try:
            d = r.json()
            code, msg = d.get("code"), str(d.get("msg", ""))[:70]
            extra = d.get("data") if isinstance(d.get("data"), dict) else None
        except Exception:
            d, code, msg, extra = None, f"HTTP {r.status_code} non-JSON", "", None
        print(f"[{label}] {path} v={headers['X-Version']:>6} "
              f"tm={headers['X-Tm']:>5} -> code={code} msg={msg}")
        if extra:
            keys = {k: (str(v)[:40] if isinstance(v, str) else v)
                    for k, v in extra.items()}
            print(f"    data keys: {keys}")
        return code, d
    except Exception as exc:
        print(f"[{label}] {path} -> ERROR {str(exc)[:90]}")
        return None, None


def part_a_versions():
    print("=" * 78)
    print("A) google-oauth-url version-gate escalation")
    print("=" * 78)
    body = {"source_id": "autoclaw", "device_id": str(uuid.uuid4()),
            "navigate_uri": "http://localhost:18432/auth/callback-google"}
    live = None
    for v in ("2.5.0", "2.6.0", "2.7.0", "2.8.0", "3.0.0", "3.1.0",
              "4.0.0", "1.17.6", "1.18.0"):
        code, d = post("/userapi/overseasv1/google-oauth-url", body,
                       hdrs(v), label="A")
        if code == 0 and isinstance(d, dict):
            live = d["data"]
            print(f"    *** LIVE at version {v} ***")
            break
        if code not in (631002,):
            print(f"    (non-version verdict at {v}: {code})")
    if live:
        with open("/home/z/my-project/scripts/.oauth_url_live.json", "w") as f:
            json.dump(live, f)
    return live


def part_b_applogin():
    print("\n" + "=" * 78)
    print("B) app-login body-shape fuzzing (version 2.5.0)")
    print("=" * 78)
    h = hdrs("2.5.0")
    md5pwd = hashlib.md5(PWD.encode()).hexdigest()
    shapwd = hashlib.sha256(PWD.encode()).hexdigest()
    did = str(uuid.uuid4())
    variants = [
        ("v1 email+password", {"email": EMAIL, "password": PWD}),
        ("v2 user_name+password", {"user_name": EMAIL, "password": PWD}),
        ("v3 account+password", {"account": EMAIL, "password": PWD}),
        ("v4 username+password", {"username": EMAIL, "password": PWD}),
        ("v5 email+passwd", {"email": EMAIL, "passwd": PWD}),
        ("v6 phone+password", {"phone": EMAIL, "password": PWD}),
        ("v7 md5 password", {"email": EMAIL, "password": md5pwd}),
        ("v8 sha256 password", {"email": EMAIL, "password": shapwd}),
        ("v9 full app-ish", {"email": EMAIL, "password": PWD,
                             "source_id": "autoclaw", "device_id": did,
                             "platform": "windows", "version": "2.5.0"}),
        ("v10 login_type", {"email": EMAIL, "password": PWD,
                            "login_type": "password", "source_id": "autoclaw",
                            "device_id": did}),
        ("v11 grant_type", {"email": EMAIL, "password": PWD,
                            "grant_type": "password", "device_id": did}),
        ("v12 code-only (oneclick-style)", {"code": "", "device_id": did}),
        ("v13 token-only", {"token": "x" * 20, "device_id": did}),
    ]
    for name, body in variants:
        post("/userapi/v1/app-login", body, h, label=f"B {name}")


def part_c_tm_plat():
    print("\n" + "=" * 78)
    print("C) platform variants on app-login (maybe win-gated)")
    print("=" * 78)
    for tm in ("android", "ios", "mac", "web"):
        h = hdrs("2.5.0", platform=tm)
        post("/userapi/v1/app-login",
             {"email": EMAIL, "password": PWD, "source_id": "autoclaw",
              "device_id": str(uuid.uuid4())}, h, label=f"C tm={tm}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    part_a_versions()
    part_b_applogin()
    part_c_tm_plat()
    print("\nProbe-2 complete.")
