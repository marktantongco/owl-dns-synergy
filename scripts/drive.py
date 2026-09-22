#!/usr/bin/env python3
"""Send a single JSON command to the persistent camoufox driver FIFO."""
import json
import sys
import time

FIFO = "/home/z/my-project/scripts/.camoufox_fifo"
LOG = "/home/z/my-project/scripts/.camoufox_log.jsonl"


def send(cmd, wait=0.0, marker=None):
    before = 0
    try:
        for _ in open(LOG, "rb"):
            before += 1
    except FileNotFoundError:
        pass
    with open(FIFO, "w") as f:
        f.write(json.dumps(cmd) + "\n")
    time.sleep(wait)
    # read new lines
    out = []
    with open(LOG) as f:
        for i, line in enumerate(f):
            if i < before:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


if __name__ == "__main__":
    cmd = json.loads(sys.argv[1])
    wait = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    res = send(cmd, wait)
    for e in res:
        if e.get("ev") == "ok" and e.get("cmd") == "snapshot":
            for el in e.get("elements", []):
                print(f"{el['tag']:8s} | {el['text'][:44]:44s} | {el['sel']}")
        elif e.get("ev") == "ok" and e.get("cmd") == "eval":
            print("EVAL:", str(e.get("value"))[:800])
        elif e.get("ev") in ("ok", "clicked", "err", "resp"):
            print(json.dumps(e, ensure_ascii=False)[:600])
    if not res:
        print("(no new events)")
