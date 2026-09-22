#!/usr/bin/env python3
"""Minimal camoufox smoke test: launch, goto, title, exit."""
import time

from camoufox.sync_api import Camoufox

print("launching...", flush=True)
t0 = time.time()
try:
    with Camoufox(headless="virtual", geoip=False) as browser:
        print(f"browser up in {time.time()-t0:.1f}s", flush=True)
        ctx = browser.contexts[0] if browser.contexts else \
            browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://example.com", timeout=30000)
        print("title:", page.title(), flush=True)
        page.wait_for_timeout(2000)
        print("done", flush=True)
except Exception as e:
    import traceback
    traceback.print_exc()
    print("ERROR:", e, flush=True)
