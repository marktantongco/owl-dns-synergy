#!/usr/bin/env python3
"""Day-3.5 gate-escalation probe (Task 17-b follow-up).

Matrix probe verdict: our Aliyun WAF discriminates on User-Agent ONLY (desktop
UA passes on every TLS stack; python-requests + SDK UAs get 405). TLS is NOT
fingerprinted on this upstream. Production shape already optimal at edge.

Remaining blockers on /userapi/overseasv1/google-oauth-url:
  X-Tm=win    -> 631002 "This version is no longer supported..." (version gate)
  X-Tm=win32  -> 400001 "Request data error"                     (body validation)

This probe:
  A) Dumps the FULL 631002 body (may embed download_url => version oracle)
  B) Escalates X-Version far beyond 4.0.0 + format variants on tm=win
  C) Fuzzes body fields on tm=win32 to satisfy 400001 validation
  D) Sweeps X-Tm x best body (darwin/android/ios/web/harmony/win32/win64)
  E) Version-oracle endpoints (update-check style routes)
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
warnings.filterwarnings("ignore")

sys.path.insert(0, "/home/z/my-project/repos/autoclaw-autologin")
from config import APP_ID, APP_KEY, PRODUCT, USER_API_BASE

BASE = USER_API_BASE
OUT = "/home/z/my-project/scripts/waf_gate_results.json"
DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "autoclaw/{v} Chrome/120.0.0.0 Electron/28.0.0 Safari/537.36")
OAUTH = "/userapi/overseasv1/google-oauth-url"


def hdrs(version="2.5.0", tm="win", extra=None):
    ts = str(int(time.time()))
    sg = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    h = {
        "X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sg,
        "X-Product": PRODUCT, "X-Version": version, "X-Tm": tm,
        "X-Trace-Id": str(uuid.uuid4()), "Content-Type": "application/json",
        "User-Agent": DESKTOP_UA.format(v=version),
        "Accept": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def post(path, body, h, label, full=False):
    try:
        r = requests.post(BASE + path, headers=h, json=body, timeout=12,
                          verify=False)
        try:
            d = r.json()
            code, msg = d.get("code"), str(d.get("msg", ""))[:110]
            data = d.get("data")
        except Exception:
            d, code, msg, data = None, f"HTTP {r.status_code} non-JSON", "", None
        print(f"[{label}] code={code} msg={msg}")
        if data is not None:
            print(f"    data: {json.dumps(data, ensure_ascii=False)[:300]}")
        if full and d is not None:
            print(f"    FULL: {json.dumps(d, ensure_ascii=False)[:600]}")
        return code, d
    except Exception as exc:
        print(f"[{label}] ERROR {str(exc)[:90]}")
        return None, None


def base_body():
    return {"source_id": "autoclaw", "device_id": str(uuid.uuid4()),
            "navigate_uri": "http://localhost:18432/auth/callback-google"}


results = []


def rec(section, label, code, body=None, headers=None):
    results.append({"section": section, "label": label, "code": str(code),
                    "body": body, "headers": {k: v for k, v in
                                              (headers or {}).items()
                                              if k != "X-Auth-Sign"}})


def a_full_dump():
    print("=" * 90)
    print("A) FULL 631002 body dump (tm=win v=2.5.0)")
    print("=" * 90)
    code, d = post(OAUTH, base_body(), hdrs("2.5.0", "win"), "A full", full=True)
    rec("A", "full-dump", code, base_body(), hdrs("2.5.0", "win"))


def b_version_escalation():
    print("\n" + "=" * 90)
    print("B) X-Version escalation + format variants (tm=win)")
    print("=" * 90)
    versions = ["2.5.0", "3.0.0", "4.0.0", "4.1.0", "4.2.0", "4.2.2",
                "4.5.0", "5.0.0", "6.0.0", "10.0.0", "100.0.0",
                "2.5", "2.5.0.0", "2.5.0-beta", "2.5.0-rc1", "25.0.0",
                "0.0.1"]
    for v in versions:
        code, d = post(OAUTH, base_body(), hdrs(v, "win"), f"B v={v}")
        rec("B", f"v={v}", code, base_body(), hdrs(v, "win"))
        if code == 0:
            print("    *** GATE OPENED at version", v, "***")
            with open("/home/z/my-project/scripts/.oauth_url_live.json",
                      "w") as f:
                json.dump(d.get("data"), f)
            break
        time.sleep(0.35)


def c_body_fuzz():
    print("\n" + "=" * 90)
    print("C) Body-shape fuzz on tm=win32 (400001 'Request data error')")
    print("=" * 90)
    did = str(uuid.uuid4())
    variants = [
        ("c1 baseline", base_body()),
        ("c2 no navigate_uri", {"source_id": "autoclaw", "device_id": did}),
        ("c3 no source_id", {"device_id": did,
                             "navigate_uri": "http://localhost:18432/"
                                             "auth/callback-google"}),
        ("c4 no device_id", {"source_id": "autoclaw",
                             "navigate_uri": "http://localhost:18432/"
                                             "auth/callback-google"}),
        ("c5 empty body", {}),
        ("c6 https callback", {"source_id": "autoclaw", "device_id": did,
                               "navigate_uri": "https://localhost:18432/"
                                               "auth/callback-google"}),
        ("c7 deep-link callback", {"source_id": "autoclaw", "device_id": did,
                                   "navigate_uri": "autoclaw://auth/"
                                                   "callback-google"}),
        ("c8 +platform", {**base_body(), "platform": "win32"}),
        ("c9 +os/version", {**base_body(), "os": "windows",
                            "version": "2.5.0"}),
        ("c10 +device_name", {**base_body(), "device_name": "DESKTOP-PROBE"}),
        ("c11 +app_version", {**base_body(), "app_version": "2.5.0"}),
        ("c12 +channel", {**base_body(), "channel": "official"}),
        ("c13 +login_type", {**base_body(), "login_type": "google"}),
        ("c14 +state", {**base_body(), "state": str(uuid.uuid4())}),
        ("c15 google source", {"source_id": "google", "device_id": did,
                               "navigate_uri": "http://localhost:18432/"
                                               "auth/callback-google"}),
        ("c16 +redirect_uri", {**base_body(),
                               "redirect_uri": "http://localhost:18432/"
                                               "auth/callback-google"}),
    ]
    for name, body in variants:
        code, d = post(OAUTH, body, hdrs("2.5.0", "win32"), f"C {name}")
        rec("C", name, code, body, hdrs("2.5.0", "win32"))
        if code == 0:
            with open("/home/z/my-project/scripts/.oauth_url_live.json",
                      "w") as f:
                json.dump(d.get("data"), f)
            break
        time.sleep(0.35)


def d_tm_sweep():
    print("\n" + "=" * 90)
    print("D) X-Tm sweep with baseline body (v=2.5.0)")
    print("=" * 90)
    for tm in ("win", "win32", "win64", "darwin", "android", "ios", "web",
               "harmony", "linux"):
        code, d = post(OAUTH, base_body(), hdrs("2.5.0", tm), f"D tm={tm}")
        rec("D", f"tm={tm}", code, base_body(), hdrs("2.5.0", tm))
        time.sleep(0.35)


def e_version_oracles():
    print("\n" + "=" * 90)
    print("E) Version-oracle endpoints (find the REAL latest client version)")
    print("=" * 90)
    candidates = [
        ("GET", "/userapi/v1/version"), ("GET", "/userapi/v1/app/version"),
        ("GET", "/userapi/overseasv1/version"),
        ("GET", "/userapi/v1/check-update"),
        ("GET", "/userapi/v1/app-version"),
        ("GET", "/version"), ("GET", "/userapi/v1/config"),
        ("GET", "/userapi/v1/latest"),
        ("POST", "/userapi/v1/update/check"),
    ]
    for method, path in candidates:
        h = hdrs("2.5.0", "win")
        try:
            if method == "GET":
                r = requests.get(BASE + path, headers=h, timeout=10,
                                 verify=False)
            else:
                r = requests.post(BASE + path, headers=h, json={},
                                  timeout=10, verify=False)
            ct = r.headers.get("Content-Type", "")
            if "html" in ct:
                print(f"[E {method} {path}] HTTP {r.status_code} WAF-HTML")
                rec("E", f"{method} {path}", "WAF-HTML")
                continue
            try:
                d = r.json()
                print(f"[E {method} {path}] HTTP {r.status_code} "
                      f"code={d.get('code')} "
                      f"msg={str(d.get('msg'))[:60]} "
                      f"data={json.dumps(d.get('data'), ensure_ascii=False)[:200]}")
                rec("E", f"{method} {path}", d.get("code"))
            except Exception:
                print(f"[E {method} {path}] HTTP {r.status_code} "
                      f"non-JSON ({ct[:30]})")
                rec("E", f"{method} {path}", f"HTTP {r.status_code}")
        except Exception as exc:
            print(f"[E {method} {path}] ERROR {str(exc)[:70]}")
            rec("E", f"{method} {path}", None)
        time.sleep(0.3)


if __name__ == "__main__":
    a_full_dump()
    b_version_escalation()
    c_body_fuzz()
    d_tm_sweep()
    e_version_oracles()
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(results)} records -> {OUT}")
    print("Day-3.5 gate-escalation probe complete.")
