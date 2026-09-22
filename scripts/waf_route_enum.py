#!/usr/bin/env python3
"""Day-3.7: two-track probe after gap closure.

Track A — oauth-login verdict restoration:
  Task-16 got 631001 on garbage code/state; today same shape -> 400001.
  Test realistic Google code/state formats (4/0AVxxx, 80-120 chars,
  base64url state 43 chars) to see if 400001 is schema validation.

Track B — overseasv1 route enumeration:
  If a direct email/password login route exists under /userapi/overseasv1/,
  the spare accounts can log in WITHOUT the gated Google OAuth step-1.
  Distinguish: code=404 "Not Found" (no route) vs 400001 (route exists,
  middleware) vs schema-specific verdicts.
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
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "autoclaw/2.5.0 Chrome/120.0.0.0 Electron/28.0.0 Safari/537.36")
results = []


def hdrs():
    ts = str(int(time.time()))
    sg = hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()
    return {"X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sg,
            "X-Product": PRODUCT, "X-Version": "2.5.0", "X-Tm": "win",
            "X-Trace-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
            "User-Agent": UA, "Accept": "application/json"}


def post(path, body, label):
    try:
        r = requests.post(BASE + path, headers=hdrs(), json=body, timeout=12,
                          verify=False)
        try:
            d = r.json()
            code, msg = d.get("code"), str(d.get("msg", ""))[:80]
        except Exception:
            d, code, msg = None, f"HTTP {r.status_code}", "non-JSON/HTML"
        print(f"[{label}] {path} -> code={code} {msg}")
        results.append({"label": label, "path": path, "code": str(code),
                        "msg": msg})
        return code, d
    except Exception as exc:
        print(f"[{label}] {path} -> ERROR {str(exc)[:80]}")
        results.append({"label": label, "path": path, "code": "EXC"})
        return None, None


def track_a():
    print("=" * 90)
    print("A) oauth-login with realistic Google code/state formats")
    print("=" * 90)
    did = str(uuid.uuid4())
    import string
    rng = "".join(__import__("random").choices(
        string.ascii_letters + string.digits + "-_", k=43))
    cases = [
        ("a1 garbage (task16 control)", {"code": "x" * 32, "state": "y" * 32,
                                         "device_id": did}),
        ("a2 realistic google code", {"code": "4/0AanRRrt"
                                      + "Q" * 100, "state": rng,
                                      "device_id": did}),
        ("a3 empty code", {"code": "", "state": rng, "device_id": did}),
        ("a4 no state", {"code": "4/0AanRRrt" + "Q" * 100,
                         "device_id": did}),
        ("a5 + navigate_uri", {"code": "4/0AanRRrt" + "Q" * 100,
                               "state": rng, "device_id": did,
                               "navigate_uri": "http://localhost:18432/"
                                               "auth/callback-google"}),
        ("a6 + source_id", {"code": "4/0AanRRrt" + "Q" * 100,
                            "state": rng, "device_id": did,
                            "source_id": "autoclaw"}),
    ]
    for label, b in cases:
        post("/userapi/overseasv1/google-oauth-login", b, label)
        time.sleep(0.4)


def track_b():
    print("\n" + "=" * 90)
    print("B) /userapi/overseasv1/* + /userapi/v1/* login-route enumeration")
    print("=" * 90)
    did = str(uuid.uuid4())
    b = {"email": "mymarky0@gmail.com", "password": "ProbeNotReal123!",
         "device_id": did, "source_id": "autoclaw",
         "navigate_uri": "http://localhost:18432/auth/callback-google"}
    routes = [
        "/userapi/overseasv1/email-login",
        "/userapi/overseasv1/mail-login",
        "/userapi/overseasv1/password-login",
        "/userapi/overseasv1/account-login",
        "/userapi/overseasv1/login",
        "/userapi/overseasv1/user-login",
        "/userapi/overseasv1/email-register",
        "/userapi/overseasv1/register",
        "/userapi/overseasv1/sso-login",
        "/userapi/overseasv1/token-login",
        "/userapi/overseasv1/apple-login",
        "/userapi/overseasv1/github-login",
        "/userapi/overseasv1/oauth-login",
        "/userapi/overseasv1/google-login",
        "/userapi/overseasv1/google-oauth-callback",
        "/userapi/overseasv1/google-oauth-token",
        "/userapi/v1/email-login",
        "/userapi/v1/login",
        "/userapi/v1/oauth-login",
        "/userapi/v1/sso-login",
        "/userapi/overseasv1/oneclick-login",
        "/userapi/overseasv1/app-login",
        "/userapi/overseasv1/refresh",
        "/userapi/overseasv1/v1/refresh",
        "/userapi/overseasv1/user-profile",
    ]
    found = []
    for p in routes:
        code, d = post(p, b, "B")
        # 404 = absent; anything else = route exists
        if code not in (404, "404"):
            found.append(p)
        time.sleep(0.35)
    print("\nExisting routes (non-404):")
    for p in found:
        print("  *", p)


if __name__ == "__main__":
    track_a()
    track_b()
    with open("/home/z/my-project/scripts/waf_route_enum_results.json",
              "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nDay-3.7 two-track probe complete.")
