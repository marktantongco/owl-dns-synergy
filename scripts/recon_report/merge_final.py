#!/usr/bin/env python3
"""Merge Template-07 cover (page 0) + ReportLab body into the final deliverable."""
from pypdf import PdfReader, PdfWriter

A4_W, A4_H = 595.28, 841.89
BASE = "/home/z/my-project/scripts/recon_report"
OUT = "/home/z/my-project/download/OWL-DNS-Synergy-20-Repo-Tooling-Recon.pdf"


def normalize(page):
    w, h = float(page.mediabox.width), float(page.mediabox.height)
    if abs(w - A4_W) > 0.1 or abs(h - A4_H) > 0.1:
        page.scale_to(A4_W, A4_H)
    return page


writer = PdfWriter()
writer.add_page(normalize(PdfReader(f"{BASE}/cover.pdf").pages[0]))
for p in PdfReader(f"{BASE}/body.pdf").pages:
    writer.add_page(normalize(p))
writer.add_metadata({
    "/Title": "20-Repo Tooling Recon and Orchestration Blueprint - OWL-DNS-Synergy",
    "/Author": "Z.ai",
    "/Creator": "Z.ai",
    "/Subject": "External dependency triage for OWL-DNS-Synergy Phase-2/3",
})
with open(OUT, "wb") as f:
    writer.write(f)
print("final:", OUT, "pages:", len(writer.pages))
