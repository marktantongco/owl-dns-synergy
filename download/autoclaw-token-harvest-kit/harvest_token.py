#!/usr/bin/env python3
"""AutoClaw desktop-token harvester (cross-platform, stdlib only).

Scans the AutoClaw desktop app's Chromium Local Storage (leveldb files) for
JWT-shaped access/refresh tokens, validates structure (exp / jti-email),
and emits a credential file ready for:

  * ACLAW_IMPORT_DIR drop-in            (*.json, auto-format: autoclaw2api)
  * POST /api/tokens/import             (same JSON body)
  * scripts/smoke_test_messages_live.py --token-file <file>

Usage:
  python harvest_token.py                     # auto-locate + scan
  python harvest_token.py "C:\\path\\to\\Local Storage\\leveldb"
  python harvest_token.py --out autoclaw_token.json

No network access. Nothing leaves the machine.
"""
import argparse
import base64
import datetime
import glob
import json
import os
import re
import shutil
import sys
import tempfile

JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}")

CANDIDATE_ROOTS = [
    # Windows
    os.path.expandvars(r"%LOCALAPPDATA%\\AutoClaw"),
    os.path.expandvars(r"%APPDATA%\\AutoClaw"),
    os.path.expandvars(r"%LOCALAPPDATA%\\autoclaw"),
    os.path.expandvars(r"%APPDATA%\\autoclaw"),
    os.path.expandvars(r"%LOCALAPPDATA%\\Programs\\AutoClaw"),
    os.path.expandvars(r"%USERPROFILE%\\AppData\\Roaming\\AutoClaw"),
    # macOS
    os.path.expanduser("~/Library/Application Support/AutoClaw"),
    os.path.expanduser("~/Library/Application Support/autoclaw"),
    # Linux
    os.path.expanduser("~/.config/AutoClaw"),
    os.path.expanduser("~/.config/autoclaw"),
]


def b64u_json(seg):
    seg += "=" * (-len(seg) % 4)
    return json.loads(base64.urlsafe_b64decode(seg))


def jwt_payload(tok):
    try:
        parts = tok.split(".")
        if len(parts) < 2:
            return None
        return b64u_json(parts[1])
    except Exception:
        return None


def find_leveldb_dirs():
    """Yield candidate leveldb directories."""
    seen = set()
    for root in CANDIDATE_ROOTS:
        if not os.path.isdir(root):
            continue
        for pat in ("**/Local Storage/leveldb", "Local Storage/leveldb",
                    "**/leveldb"):
            for d in glob.glob(os.path.join(root, pat), recursive=True):
                if d not in seen:
                    seen.add(d)
                    yield d


def scan_dir(d):
    """Extract candidate JWT strings from leveldb files in dir d."""
    hits = {}
    tmp = tempfile.mkdtemp(prefix="aclaw-ls-")
    try:
        for fp in glob.glob(os.path.join(d, "*")):
            base = os.path.basename(fp)
            if not re.match(r"^\d{6}", base) and not base.endswith(".log"):
                continue
            try:
                shutil.copy2(fp, os.path.join(tmp, base))
            except OSError:
                continue
        for fp in glob.glob(os.path.join(tmp, "*")):
            try:
                blob = open(fp, "rb").read()
            except OSError:
                continue
            for m in JWT_RE.finditer(blob.decode("utf-8", "ignore")):
                tok = m.group(0)
                hits.setdefault(tok, fp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return hits


def classify(hits):
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    records = []
    for tok, src in hits.items():
        payload = jwt_payload(tok)
        if not payload:
            continue
        exp = payload.get("exp")
        email = payload.get("jti") or payload.get("email") or payload.get("sub")
        if not email or "@" not in str(email):
            # AutoClaw jti carries the login email; skip non-account JWTs
            continue
        records.append({
            "email": str(email).lower(),
            "access_token": tok,
            "expired": bool(exp and now >= int(exp)),
            "exp": exp,
            "user_id": payload.get("id") or payload.get("uid") or "",
            "device_id": "",       # minted by the importer if absent
            "source": src,
        })
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("leveldb_dir", nargs="?", default=None)
    ap.add_argument("--out", default="autoclaw_token.json")
    ap.add_argument("--allow-expired", action="store_true",
                    help="emit even if exp passed (importer will refresh)")
    args = ap.parse_args()

    dirs = [args.leveldb_dir] if args.leveldb_dir else list(find_leveldb_dirs())
    if not dirs:
        print("No AutoClaw Local Storage directory found.")
        print("Looked in:\n  " + "\n  ".join(CANDIDATE_ROOTS))
        print("Tip: pass the path explicitly, e.g.")
        print('  python harvest_token.py '
              '"%LOCALAPPDATA%\\AutoClaw\\Local Storage\\leveldb"')
        return 2

    all_records = {}
    for d in dirs:
        print(f"scanning: {d}")
        hits = scan_dir(d)
        for rec in classify(hits):
            prev = all_records.get(rec["email"])
            if prev is None or (prev["expired"] and not rec["expired"]):
                all_records[rec["email"]] = rec

    if not all_records:
        print("No account JWTs found (logged out?). Log into the desktop "
              "app first, then re-run.")
        return 1

    out_records = []
    for rec in all_records.values():
        if rec["expired"] and not args.allow_expired:
            print(f"  skip {rec['email']}: token expired "
                  f"(exp={rec['exp']}) — re-login in the desktop app or "
                  f"use --allow-expired")
            continue
        out_records.append({
            "email": rec["email"],
            "access_token": rec["access_token"],
            "refresh_token": "",
            "user_id": rec["user_id"],
            "device_id": rec["device_id"] or "",
            "source_id": "desktop-ls",
        })

    if not out_records:
        return 1
    payload = out_records[0] if len(out_records) == 1 else \
        {"accounts": [{**r, "device_id": r["device_id"] or "imported"}
                      for r in out_records]}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"wrote {args.out} with {len(out_records)} record(s):")
    for r in out_records:
        exp_s = (datetime.datetime.fromtimestamp(
            jwt_payload(r["access_token"])["exp"]).strftime("%Y-%m-%d %H:%M"))
        print(f"  {r['email']}  exp={exp_s}")
    print("\nNext — any one of:")
    print(f"  1. copy {args.out} into the proxy's ACLAW_IMPORT_DIR")
    print(f"  2. curl -X POST http://127.0.0.1:31000/api/tokens/import "
          f"-d @{args.out}")
    print(f"  3. python scripts/smoke_test_messages_live.py "
          f"--token-file {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
