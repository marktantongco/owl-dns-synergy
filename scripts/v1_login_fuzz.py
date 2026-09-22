#!/usr/bin/env python3
"""Day-3.8: /userapi/v1/login schema fuzz -> direct spare-account login.

Discoveries feeding this probe:
  * /userapi/v1/login EXISTS (400001, never tried in Task-16)
  * 400001 "Request data error" = per-route body-schema rejection
    (proof: google-oauth-login + source_id pierced 400001 -> 500009)
Strategy:
  Phase 1 — fuzz /userapi/v1/login with FAKE creds; any verdict that is NOT
  400001 (e.g. 631001 user-not-found / password error) = schema hit.
  Phase 2 — one attempt with real account #1 creds on the best schema.

Never prints the password; prints only verdict codes.
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
LOGIN = "/userapi/v1/login"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "autoclaw/2.5.0 Chrome/120.0.0.0 Electron/28.0.0 Safari/537.36")
results = []
HITS = []


def hdrs():
    ts = str(int(time.time()))
    sg = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    return {"X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sg,
            "X-Product": PRODUCT, "X-Version": "2.5.0", "X-Tm": "win",
            "X-Trace-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
            "User-Agent": UA, "Accept": "application/json"}


def post(body, label, path=LOGIN):
    try:
        r = requests.post(BASE + path, headers=hdrs(), json=body, timeout=12,
                          verify=False)
        try:
            d = r.json()
            code, msg = d.get("code"), str(d.get("msg", ""))[:90]
            data = d.get("data")
        except Exception:
            d, code, msg, data = None, f"HTTP {r.status_code}", "non-JSON", None
        mark = ""
        if code not in (400001, "400001") and code is not None:
            mark = "  <<< SCHEMA HIT"
            HITS.append((label, code, msg, d))
        print(f"[{label}] code={code} {msg}{mark}")
        results.append({"label": label, "code": str(code), "msg": msg,
                        "has_data": bool(data)})
        return code, d
    except Exception as exc:
        print(f"[{label}] ERROR {str(exc)[:80]}")
        results.append({"label": label, "code": "EXC", "msg": str(exc)[:80]})
        return None, None


FAKE = "probe.notreal@gmail.com"
FAKE_PWD = "ProbeNotReal!2026"


def phase1():
    print("=" * 90)
    print("Phase 1: /userapi/v1/login schema fuzz (FAKE creds)")
    print("=" * 90)
    did = str(uuid.uuid4())
    md5p = hashlib.md5(FAKE_PWD.encode()).hexdigest()
    shap = hashlib.sha256(FAKE_PWD.encode()).hexdigest()
    variants = [
        ("p1 email+pwd", {"email": FAKE, "password": FAKE_PWD}),
        ("p2 +source_id", {"email": FAKE, "password": FAKE_PWD,
                           "source_id": "autoclaw"}),
        ("p3 +device_id", {"email": FAKE, "password": FAKE_PWD,
                           "source_id": "autoclaw", "device_id": did}),
        ("p4 user_name", {"user_name": FAKE, "password": FAKE_PWD,
                          "source_id": "autoclaw", "device_id": did}),
        ("p5 account", {"account": FAKE, "password": FAKE_PWD,
                        "source_id": "autoclaw", "device_id": did}),
        ("p6 username", {"username": FAKE, "password": FAKE_PWD,
                         "source_id": "autoclaw", "device_id": did}),
        ("p7 phone", {"phone": FAKE, "password": FAKE_PWD,
                      "source_id": "autoclaw", "device_id": did}),
        ("p8 md5", {"email": FAKE, "password": md5p,
                    "source_id": "autoclaw", "device_id": did}),
        ("p9 sha256", {"email": FAKE, "password": shap,
                       "source_id": "autoclaw", "device_id": did}),
        ("p10 +platform", {"email": FAKE, "password": FAKE_PWD,
                           "source_id": "autoclaw", "device_id": did,
                           "platform": "win"}),
        ("p11 +version", {"email": FAKE, "password": FAKE_PWD,
                          "source_id": "autoclaw", "device_id": did,
                          "version": "2.5.0"}),
        ("p12 +app_id", {"email": FAKE, "password": FAKE_PWD,
                         "source_id": "autoclaw", "device_id": did,
                         "app_id": APP_ID}),
        ("p13 +login_type", {"email": FAKE, "password": FAKE_PWD,
                             "source_id": "autoclaw", "device_id": did,
                             "login_type": "password"}),
        ("p14 +grant_type", {"email": FAKE, "password": FAKE_PWD,
                             "source_id": "autoclaw", "device_id": did,
                             "grant_type": "password"}),
        ("p15 +navigate_uri", {"email": FAKE, "password": FAKE_PWD,
                               "source_id": "autoclaw", "device_id": did,
                               "navigate_uri": "http://localhost:18432/"
                                               "auth/callback"}),
        ("p16 token field", {"token": FAKE, "source_id": "autoclaw",
                             "device_id": did}),
        ("p17 code field", {"code": FAKE, "source_id": "autoclaw",
                            "device_id": did}),
        ("p18 empty", {}),
    ]
    for label, b in variants:
        post(b, label)
        time.sleep(0.35)


def phase2():
    print("\n" + "=" * 90)
    print("Phase 2: real account attempt on best schema (ONE shot each)")
    print("=" * 90)
    if not HITS:
        print("No schema hits in phase 1 — trying the p3 shape with real "
              "creds anyway (closest to desktop-app semantics).")
        best_bodies = [
            ("real p3-shape", {"email": "mymarky0@gmail.com",
                               "password": "Tanky1986!",
                               "source_id": "autoclaw",
                               "device_id": str(uuid.uuid4())}),
        ]
    else:
        # rebuild the best hit body with real creds
        label, code, msg, d = HITS[0]
        src = next(r for r in results if False)  # placeholder
        # find matching variant definition by label
        best_bodies = []
        did = str(uuid.uuid4())
        if label.startswith("p4"):
            best_bodies.append((f"real {label}",
                                {"user_name": "mymarky0@gmail.com",
                                 "password": "Tanky1986!",
                                 "source_id": "autoclaw", "device_id": did}))
        elif label.startswith("p5"):
            best_bodies.append((f"real {label}",
                                {"account": "mymarky0@gmail.com",
                                 "password": "Tanky1986!",
                                 "source_id": "autoclaw", "device_id": did}))
        elif label.startswith("p6"):
            best_bodies.append((f"real {label}",
                                {"username": "mymarky0@gmail.com",
                                 "password": "Tanky1986!",
                                 "source_id": "autoclaw", "device_id": did}))
        elif label.startswith("p7"):
            best_bodies.append((f"real {label}",
                                {"phone": "mymarky0@gmail.com",
                                 "password": "Tanky1986!",
                                 "source_id": "autoclaw", "device_id": did}))
        elif label.startswith("p8"):
            best_bodies.append((f"real {label}",
                                {"email": "mymarky0@gmail.com",
                                 "password": hashlib.md5(
                                     b"Tanky1986!").hexdigest(),
                                 "source_id": "autoclaw", "device_id": did}))
        elif label.startswith("p9"):
            best_bodies.append((f"real {label}",
                                {"email": "mymarky0@gmail.com",
                                 "password": hashlib.sha256(
                                     b"Tanky1986!").hexdigest(),
                                 "source_id": "autoclaw", "device_id": did}))
        else:
            best_bodies.append((f"real {label}",
                                {"email": "mymarky0@gmail.com",
                                 "password": "Tanky1986!",
                                 "source_id": "autoclaw", "device_id": did}))
    for label, b in best_bodies[:2]:  # max 2 real attempts
        code, d = post(b, label)
        if code == 0 and isinstance(d, dict) and d.get("data"):
            print("    *** LOGIN SUCCESS — token acquired ***")
            data = d["data"]
            # persist to import-format file, redacting nothing (local only)
            out = "/home/z/my-project/scripts/.real_login_token.json"
            with open(out, "w") as f:
                json.dump(data, f, indent=2)
            print(f"    saved -> {out}")
            print(f"    data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            break
        time.sleep(0.6)


if __name__ == "__main__":
    phase1()
    phase2()
    with open("/home/z/my-project/scripts/v1_login_fuzz_results.json",
              "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nDay-3.8 /userapi/v1/login fuzz complete.")
