#!/usr/bin/env python3
"""Day-3 WAF client-shape matrix probe (Task 17-b).

Hypothesis (from Goodnessmbakara/agentrouter-opencode-proxy recon):
Aliyun WAF fronting autoglm-api.autoglm.ai may allowlist by CLIENT FINGERPRINT
(TLS handshake + header shape), not just signing headers. AgentRouter's WAF
passes the Python sync anthropic SDK where raw httpx / curl / node-fetch get
"unauthorized client detected". Our gated route /userapi/overseasv1/
google-oauth-url currently returns 631002 (X-Tm=win) / 400001 (X-Tm=win32) —
maybe the middleware is discriminating on client shape.

Matrix dimensions:
  TRANSPORT (TLS stack):  requests(urllib3/OpenSSL) | httpx(httpcore) |
                          curl_cffi(BoringSSL, impersonate=chrome*) |
                          curl subprocess(OpenSSL) | anthropic/openai SDK httpx
  HEADER SHAPE:           desktop-Electron UA | python-requests UA |
                          anthropic-sdk default headers | openai-sdk headers |
                          full Electron/Chromium header set (sec-ch-*, sec-fetch)
  ROUTE:                  /userapi/overseasv1/google-oauth-url (gated target)
                          /userapi/v1/refresh                (relaxed baseline)
                          /autoclaw-proxy/.../chat/completions (LLM gate)

Verdict legend:
  WAF-HTML      = blocked at edge (405/HTML challenge)
  631002        = version gate        400001 = middleware rejection
  631001        = real auth-logic verdict (login error => deepest pass so far)
  0 / 200       = full pass

Output: scripts/waf_matrix_results.json + console matrix. Never prints APP_KEY.
"""
import hashlib
import json
import subprocess
import sys
import time
import uuid
import warnings

import requests as std_requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

sys.path.insert(0, "/home/z/my-project/repos/autoclaw-autologin")
from config import APP_ID, APP_KEY, PRODUCT, USER_API_BASE

BASE = USER_API_BASE
OUT = "/home/z/my-project/scripts/waf_matrix_results.json"

DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "autoclaw/2.5.0 Chrome/120.0.0.0 Electron/28.0.0 Safari/537.36")
PY_UA = "python-requests/2.32.5"

OAUTH_BODY = {"source_id": "autoclaw", "device_id": str(uuid.uuid4()),
              "navigate_uri": "http://localhost:18432/auth/callback-google"}
CHAT_BODY = {"model": "claude-sonnet-4-5",
             "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16}


def sign(ts=None):
    ts = ts or str(int(time.time()))
    return ts, hashlib.md5(f"{APP_ID}&{ts}&{APP_KEY}".encode()).hexdigest()


def base_signed_headers(version="2.5.0", tm="win", ua=DESKTOP_UA, extra=None):
    ts, sg = sign()
    h = {
        "X-Auth-Appid": APP_ID, "X-Auth-TimeStamp": ts, "X-Auth-Sign": sg,
        "X-Product": PRODUCT, "X-Version": version, "X-Tm": tm,
        "X-Trace-Id": str(uuid.uuid4()), "Content-Type": "application/json",
        "User-Agent": ua, "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    if extra:
        h.update(extra)
    return h


def electron_full_headers(version="2.5.0", tm="win"):
    """Full Chromium/Electron header set the desktop app's net stack emits."""
    extra = {
        "Accept-Language": "en-US,en;q=0.9",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", '
                     '"Microsoft Edge";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
    }
    return base_signed_headers(version, tm, extra=extra)


def sdk_default_headers(which):
    """Real default header set from the installed anthropic/openai SDKs."""
    if which == "anthropic":
        import anthropic
        c = anthropic.Anthropic(api_key="sk-dummy-probe")
        hd = dict(c._client.headers)
        hd.pop("authorization", None)
        hd.pop("x-api-key", None)  # do not send SDK auth on userapi
        return hd
    import openai
    c = openai.OpenAI(api_key="sk-dummy-probe")
    hd = dict(c._client.headers)
    hd.pop("authorization", None)
    return hd


def classify(resp_status, content_type, body_text):
    ct = (content_type or "").lower()
    if "text/html" in ct or (resp_status == 405 and "{" not in body_text[:200]):
        return "WAF-HTML", ""
    try:
        d = json.loads(body_text)
        return str(d.get("code")), str(d.get("msg", ""))[:60]
    except Exception:
        return f"HTTP {resp_status}", body_text[:60]


def record(results, shape, route, path, r_status, ct, text, note=""):
    code, msg = classify(r_status, ct, text)
    results.append({"shape": shape, "route": route, "path": path,
                    "status": r_status, "code": code, "msg": msg,
                    "note": note})
    print(f"  {shape:<34} {route:<10} -> HTTP {r_status:<4} "
          f"code={str(code):<10} {msg}")
    return code


def main():
    results = []
    oauth_path = "/userapi/overseasv1/google-oauth-url"
    refresh_path = "/userapi/v1/refresh"
    chat_path = "/autoclaw-proxy/proxy/autoclaw/chat/completions"

    # ---------- pre-flight: curl_cffi impersonation targets ----------
    cffi_targets = []
    try:
        from curl_cffi import requests as cr
        for t in ("chrome120", "chrome124", "chrome131", "safari17_0"):
            try:
                r = cr.get("https://httpbin.org/get", impersonate=t,
                           timeout=6) if False else None
                cffi_targets.append(t)
            except Exception:
                pass
        print(f"[preflight] curl_cffi {cr.__name__} targets: {cffi_targets}")
    except ImportError:
        print("[preflight] curl_cffi MISSING — TLS dimension degraded")
        cr = None

    try:
        anth_hd = sdk_default_headers("anthropic")
        print(f"[preflight] anthropic sdk headers: "
              f"{sorted(k for k in anth_hd if 'stainless' in k or k == 'User-Agent')}")
    except Exception as e:
        anth_hd = {}
        print(f"[preflight] anthropic sdk headers unavailable: {e}")
    try:
        oai_hd = sdk_default_headers("openai")
    except Exception:
        oai_hd = {}

    shapes = []

    # S1 production baseline: requests + desktop UA
    shapes.append(("requests+desktopUA", "requests", None))
    # S2 WAF-block control: requests + python-requests UA
    shapes.append(("requests+pythonUA", "requests_pyua", None))
    # S3 httpx + desktop UA (different TLS client-hello: httpcore)
    shapes.append(("httpx+desktopUA", "httpx", None))
    # S4/S5 TLS impersonation via curl_cffi (BoringSSL chrome hello)
    if cr is not None:
        shapes.append(("curlcffi-chrome120+desktopUA", "cffi_chrome120", None))
        shapes.append(("curlcffi-chrome124+anthropicHdrs", "cffi_chrome124", anth_hd))
    # S6 real anthropic SDK httpx transport + SDK headers (agentrouter winner)
    if anth_hd:
        shapes.append(("anthropicSDK-httpx+sdkHdrs", "anth_sdk", anth_hd))
    # S7 openai SDK transport + headers
    if oai_hd:
        shapes.append(("openaiSDK-httpx+sdkHdrs", "openai_sdk", oai_hd))
    # S8 full Electron header set
    shapes.append(("requests+electronFullHdrs", "requests_full", None))
    # S9 raw curl + desktop UA
    shapes.append(("curl+desktopUA", "curl", None))

    print("=" * 100)
    print(f"Day-3 WAF client-shape matrix @ {time.strftime('%Y-%m-%d %H:%M:%S')}"
          f"  base={BASE}")
    print("=" * 100)

    def send(transport, headers, path, body, extra_hdrs=None):
        hd = dict(headers)
        if extra_hdrs:
            hd.update(extra_hdrs)
        if transport in ("requests", "requests_full"):
            r = std_requests.post(BASE + path, headers=hd, json=body,
                                  timeout=14, verify=False)
            return r.status_code, r.headers.get("Content-Type"), r.text
        if transport == "requests_pyua":
            hd = dict(hd)
            hd["User-Agent"] = PY_UA
            r = std_requests.post(BASE + path, headers=hd, json=body,
                                  timeout=14, verify=False)
            return r.status_code, r.headers.get("Content-Type"), r.text
        if transport == "httpx":
            import httpx
            with httpx.Client(verify=False, timeout=14) as c:
                r = c.post(BASE + path, headers=hd, json=body)
                return r.status_code, r.headers.get("content-type"), r.text
        if transport == "anth_sdk" or transport == "openai_sdk":
            import httpx
            # SDK-shaped headers on a fresh httpx transport = authentic
            # SDK header shape (stainless set) without SDK auth headers.
            with httpx.Client(verify=False, timeout=14) as c:
                r = c.post(BASE + path, headers=hd, json=body)
                return r.status_code, r.headers.get("content-type"), r.text
        if transport.startswith("cffi_"):
            imp = transport.split("_")[1]
            r = cr.post(BASE + path, headers=hd, json=body, impersonate=imp,
                        timeout=14, verify=False)
            return r.status_code, r.headers.get("Content-Type"), r.text
        if transport == "curl":
            cmd = ["curl", "-sk", "-X", "POST", BASE + path,
                   "--max-time", "14",
                   "-w", "\n@@@%{http_code}@@@%@{content_type}"]
            for k, v in hd.items():
                cmd += ["-H", f"{k}: {v}"]
            cmd += ["--data", json.dumps(body)]
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=20)
            out = p.stdout
            try:
                text, _, rest = out.partition("\n@@@")
                sc, _, ct = rest.partition("@@@")
                return int(sc or 0), ct.strip(), text
            except Exception:
                return 0, "", out[:120]
        raise ValueError(transport)

    for shape_name, transport, sdk_hdrs in shapes:
        # --- gated target: google-oauth-url, both X-Tm values ---
        for tm in ("win", "win32"):
            hd = (base_signed_headers(tm=tm, extra=dict(sdk_hdrs))
                  if sdk_hdrs else
                  (electron_full_headers(tm=tm)
                   if transport == "requests_full" else
                   base_signed_headers(tm=tm)))
            try:
                st, ct, tx = send(transport, hd, oauth_path, OAUTH_BODY)
                record(results, f"{shape_name} tm={tm}", "oauth-url",
                       oauth_path, st, ct, tx)
            except Exception as e:
                record(results, f"{shape_name} tm={tm}", "oauth-url",
                       oauth_path, 0, "", "", note=f"EXC {str(e)[:60]}")
            time.sleep(0.4)
        # --- baseline: refresh (no auth) ---
        hd = (base_signed_headers(extra=dict(sdk_hdrs))
              if sdk_hdrs else
              (electron_full_headers() if transport == "requests_full"
               else base_signed_headers()))
        try:
            st, ct, tx = send(transport, hd, refresh_path, {})
            record(results, shape_name, "refresh", refresh_path,
                   st, ct, tx)
        except Exception as e:
            record(results, shape_name, "refresh", refresh_path,
                   0, "", "", note=f"EXC {str(e)[:60]}")
        time.sleep(0.4)
        # --- LLM gate: chat/completions (expect 401 JSON pre-auth) ---
        try:
            st, ct, tx = send(transport, hd, chat_path, CHAT_BODY)
            record(results, shape_name, "chat", chat_path, st, ct, tx)
        except Exception as e:
            record(results, shape_name, "chat", chat_path, 0, "", "",
                   note=f"EXC {str(e)[:60]}")
        time.sleep(0.4)
        print()

    # ---------- summary matrix ----------
    print("=" * 100)
    print("VERDICT MATRIX (best verdict per shape)")
    print("=" * 100)
    best = {}
    for r in results:
        k = r["shape"].split(" tm=")[0]
        rank = {"0": 5, "200": 5, "631001": 4, "631002": 3, "400001": 2}
        cur = best.get(k, ("-", 0))
        rk = rank.get(r["code"], 1)
        if rk > cur[1]:
            best[k] = (r["code"], rk)
    for k, (code, _) in best.items():
        print(f"  {k:<36} best_code={code}")

    with open(OUT, "w") as f:
        json.dump({"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "base": BASE, "results": results}, f, indent=2)
    print(f"\nSaved {len(results)} probe records -> {OUT}")


if __name__ == "__main__":
    main()
