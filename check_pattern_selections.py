#!/usr/bin/env python3
"""Show which patterns are marked as selected on the HLD main page."""
import os, warnings; warnings.filterwarnings("ignore")
from dotenv import load_dotenv; load_dotenv()
import requests
from bs4 import BeautifulSoup

base = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
token = os.getenv("CONFLUENCE_API_TOKEN", "").strip()
email = os.getenv("CONFLUENCE_EMAIL", "").strip()
session = requests.Session()
session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
if token and "@" in token:
    # PAT in email format — use basic auth
    parts = token.split(":", 1)
    session.auth = (parts[0], parts[1]) if len(parts) == 2 else (email, token)
elif token:
    session.headers["Authorization"] = f"Bearer {token}"

# Try by ID directly
r = session.get(f"{base}/rest/api/content/520783944?expand=body.storage", verify=False)
data = r.json()
if "body" not in data:
    print("Could not fetch HLD page:", r.status_code, data); exit(1)
html = data["body"]["storage"]["value"]
soup = BeautifulSoup(html, "html.parser")

selected, unselected = [], []
for t in soup.find_all("table"):
    ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
    j = " ".join(ths)
    if "pattern id" not in j or "selected" not in j:
        continue
    sid = next((i for i, h in enumerate(ths) if "selected" in h), None)
    iid = next((i for i, h in enumerate(ths) if "pattern id" in h), None)
    if sid is None or iid is None:
        continue
    for tr in t.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) <= max(sid, iid) or not cells[iid]:
            continue
        v = cells[sid].strip().upper()
        if v in ("Y", "YES") or any(c in cells[sid] for c in ("\u2611", "\u2713", "\u2714")):
            selected.append((cells[iid], cells[sid]))
        else:
            unselected.append((cells[iid], cells[sid]))

print(f"\nSelected patterns ({len(selected)}):")
for pid, val in selected:
    print(f"  {pid:30s} → {val!r}")

print(f"\nNot selected ({len(unselected)}):")
for pid, val in unselected:
    print(f"  {pid:30s} → {val!r}")
