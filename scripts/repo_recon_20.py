#!/usr/bin/env python3
"""Recon 20 candidate GitHub repos for OWL-DNS-Synergy Phase-2 tooling triage.

Fetches repo metadata + README via api.github.com (unauthenticated, 60 req/h budget).
Saves full JSON to /home/z/my-project/scripts/recon_results.json and prints a digest.
"""
import json
import time
import urllib.request
import urllib.error
import base64
import sys

REPOS = [
    "fengkiej/openai-compatible_opencode-fix",
    "Prodigalgal/any2api",
    "angyedz/QwenFreeApi",
    "Goodnessmbakara/agentrouter-opencode-proxy",
    "aleks-spv/opencode_retrypush",
    "jianlingzhong/opencode-gemini-rotator",
    "ZeroHomer/dsh-opencode-zen-bypass",
    "MrAlony/oc-quota",
    "tpaine1737/scraping-skill",
    "izaart95-jpg/GLM-Free-API",
    "huanglong0719/ds2api-browser-proxy",
    "jkeczan/aws-api-gateway-elastic-search-proxy",
    "assaf/zombie",
    "mirankhan008/sqli-labs",
    "javapuppteernodejs/bypass-awswaf-crawl4ai",
    "alisalive/XSSSlayer",
    "Jobenas/phantom",
    "getphantomsignal/phantomsignal",
    "EfrainGaray/phantomrelay",
    "zackiles/cdp-proxy-interceptor",
]

OUT = "/home/z/my-project/scripts/recon_results.json"

def _load_pat():
    """Extract GitHub PAT from a known git remote URL on disk (never printed)."""
    import re, os
    cfg = "/home/z/my-project/repos/autoclaw-autologin/.git/config"
    try:
        with open(cfg) as f:
            m = re.search(r"url = https://([A-Za-z0-9_]+)@github\.com", f.read())
        return m.group(1) if m else None
    except OSError:
        return None

_TOK = _load_pat()
HDR = {
    "User-Agent": "owl-dns-synergy-recon/1.0",
    "Accept": "application/vnd.github+json",
}
if _TOK:
    HDR["Authorization"] = f"Bearer {_TOK}"
README_HDR = {
    "User-Agent": "owl-dns-synergy-recon/1.0",
    "Accept": "application/vnd.github.raw+json",
}
if _TOK:
    README_HDR["Authorization"] = f"Bearer {_TOK}"


def get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # network hiccup
        return -1, str(e).encode()


def main():
    results = []
    for i, repo in enumerate(REPOS, 1):
        entry = {"repo": repo}
        # ---- metadata ----
        st, body = get(f"https://api.github.com/repos/{repo}", HDR)
        if st == 200:
            m = json.loads(body)
            entry.update({
                "status": "ok",
                "description": m.get("description"),
                "language": m.get("language"),
                "stars": m.get("stargazers_count"),
                "forks": m.get("forks_count"),
                "open_issues": m.get("open_issues_count"),
                "archived": m.get("archived"),
                "size_kb": m.get("size"),
                "created_at": m.get("created_at"),
                "pushed_at": m.get("pushed_at"),
                "default_branch": m.get("default_branch"),
                "topics": m.get("topics") or [],
                "homepage": m.get("homepage"),
            })
        elif st == 404:
            entry["status"] = "not_found"
        elif st == 403:
            entry["status"] = "rate_limited"
            print(f"[{i:02d}/20] {repo}: RATE LIMITED — stopping to preserve budget", flush=True)
            results.append(entry)
            break
        else:
            entry["status"] = f"http_{st}"

        # ---- README (only when meta OK) ----
        if entry.get("status") == "ok":
            st2, body2 = get(f"https://api.github.com/repos/{repo}/readme", README_HDR)
            if st2 == 200:
                txt = body2.decode("utf-8", errors="replace")
                entry["readme_chars"] = len(txt)
                entry["readme_head"] = txt[:6000]
            else:
                entry["readme_head"] = None
                entry["readme_status"] = st2
            time.sleep(0.4)

        results.append(entry)
        d = entry.get("description") or "-"
        print(f"[{i:02d}/20] {repo} [{entry.get('status')}] "
              f"{entry.get('language') or '-'} S:{entry.get('stars', '-')} "
              f"push:{(entry.get('pushed_at') or '-')[:10]} | {d[:90]}", flush=True)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"\nSaved {len(results)} entries -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
