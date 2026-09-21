#!/usr/bin/env python3
"""Print condensed README heads for selected repos from recon_results.json."""
import json

FOCUS = [
    "Prodigalgal/any2api",
    "izaart95-jpg/GLM-Free-API",
    "Jobenas/phantom",
    "getphantomsignal/phantomsignal",
    "EfrainGaray/phantomrelay",
    "zackiles/cdp-proxy-interceptor",
    "javapuppteernodejs/bypass-awswaf-crawl4ai",
    "MrAlony/oc-quota",
    "jianlingzhong/opencode-gemini-rotator",
    "tpaine1737/scraping-skill",
    "huanglong0719/ds2api-browser-proxy",
    "angyedz/QwenFreeApi",
    "Goodnessmbakara/agentrouter-opencode-proxy",
    "ZeroHomer/dsh-opencode-zen-bypass",
    "aleks-spv/opencode_retrypush",
    "fengkiej/openai-compatible_opencode-fix",
]

data = json.load(open("/home/z/my-project/scripts/recon_results.json"))
for e in data:
    if e["repo"] not in FOCUS:
        continue
    print("=" * 100)
    print(f"REPO: {e['repo']}  lang={e.get('language')} stars={e.get('stars')} pushed={e.get('pushed_at')}")
    print(f"DESC: {e.get('description')}")
    head = (e.get("readme_head") or "(no readme)")[:2400]
    print(head)
    print()
