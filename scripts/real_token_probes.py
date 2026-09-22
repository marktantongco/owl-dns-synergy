#!/usr/bin/env python3
"""Task 17-d follow-up: with the REAL zai-oauth token, probe
  A) /agent-assetmgr wallets + ledgers (point balance)
  B) /autoclaw-proxy/proxy/autoclaw-model-config (valid model list)
  C) daily check-in / bonus routes (first-login free points?)
"""
import json
import sys
import warnings

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

sys.path.insert(0, "/home/z/my-project/repos/autoclaw-autologin")
from config import USER_API_BASE

rec = json.load(open("/home/z/my-project/scripts/zai_token_record.json"))[0]
tok = rec["access_token"]
auth = tok if tok.startswith("Bearer ") else "Bearer " + tok

h = {
    "authorization": auth,
    "Content-Type": "application/json",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/131.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "X-Product": "rumination", "X-Tm": "web", "X-Version": "1.44.0",
}


def get(path, label):
    r = requests.get(USER_API_BASE + path, headers=h, timeout=15,
                     verify=False)
    try:
        d = r.json()
        print(f"[{label}] {r.status_code} code={d.get('code')} "
              f"msg={str(d.get('msg'))[:60]}")
        data = d.get("data")
        if data is not None:
            print("   data:", json.dumps(data, ensure_ascii=False)[:700])
        return d
    except Exception:
        print(f"[{label}] {r.status_code} non-JSON {r.text[:120]}")
        return None


def post(path, body, label):
    r = requests.post(USER_API_BASE + path, headers=h, json=body, timeout=15,
                      verify=False)
    try:
        d = r.json()
        print(f"[{label}] {r.status_code} code={d.get('code')} "
              f"msg={str(d.get('msg'))[:60]}")
        data = d.get("data")
        if data is not None:
            print("   data:", json.dumps(data, ensure_ascii=False)[:700])
        return d
    except Exception:
        print(f"[{label}] {r.status_code} non-JSON {r.text[:120]}")
        return None


print("=" * 90)
print("A) wallet + ledger")
print("=" * 90)
get("/agent-assetmgr/api/v2/wallets?biz_app_id=autoclaw", "wallets")
get("/agent-assetmgr/api/v1/ledgers_std?asset_type=point&wallet_type=all",
    "ledgers")

print()
print("=" * 90)
print("B) model-config (with token)")
print("=" * 90)
d = get("/autoclaw-proxy/proxy/autoclaw-model-config", "model-config")
if d and d.get("data"):
    data = d["data"]
    models = data if isinstance(data, list) else data.get("models", [])
    if isinstance(models, list):
        names = []
        for m in models:
            n = m.get("model_name") or m.get("name") if isinstance(m, dict) \
                else str(m)
            lvl = m.get("creditConsumptionLevel", "?") \
                if isinstance(m, dict) else "?"
            names.append(f"{n}[{lvl}]")
        print("MODELS:", ", ".join(names))
    json.dump(d, open("/home/z/my-project/scripts/.model_config_live.json",
                      "w"), ensure_ascii=False, indent=2)
    print("saved -> .model_config_live.json")

print()
print("=" * 90)
print("C) check-in / bonus routes")
print("=" * 90)
post("/agent-assetmgr/api/v1/checkin", {}, "checkin")
post("/agent-assetmgr/api/v1/daily-checkin", {}, "daily-checkin")
post("/userapi/v1/checkin", {}, "userapi-checkin")
get("/agent-assetmgr/api/v1/tasks", "tasks")
