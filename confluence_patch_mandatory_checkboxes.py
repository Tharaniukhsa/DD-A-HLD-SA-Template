"""
confluence_patch_mandatory_checkboxes.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Converts the plain "Y" text in INF-01 and INF-05 rows on the live HLD page
to pre-ticked (complete) Confluence task-list checkboxes, indicating they
are mandatory and always applied.
Idempotent — safe to re-run.
"""

import os
import sys
import requests
import urllib3
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()
BASE_URL   = os.getenv("CONFLUENCE_BASE_URL", "").rstrip("/")
USER_EMAIL = os.getenv("CONFLUENCE_USER_EMAIL", "")
API_TOKEN  = os.getenv("CONFLUENCE_API_TOKEN", "")
TLS_VERIFY = os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").lower() != "true"
PAGE_ID    = "520783944"

# Pre-ticked (complete) checkbox — visually shows as already done / mandatory
MANDATORY_YES = (
    '<ac:task-list>'
    '<ac:task><ac:task-status>complete</ac:task-status>'
    '<ac:task-body>Yes (Mandatory)</ac:task-body></ac:task>'
    '</ac:task-list>'
)


def get_page(session, auth):
    url = f"{BASE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"
    r = session.get(url, auth=auth, verify=TLS_VERIFY)
    r.raise_for_status()
    data = r.json()
    return data["body"]["storage"]["value"], data["version"]["number"], data["title"]


def push_page(session, auth, body, version, title):
    url = f"{BASE_URL}/rest/api/content/{PAGE_ID}"
    payload = {
        "version": {"number": version + 1},
        "title": title,
        "type": "page",
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    r = session.put(url, auth=auth, json=payload, verify=TLS_VERIFY)
    r.raise_for_status()
    return r.json()["version"]["number"]


def main():
    if not all([BASE_URL, USER_EMAIL, API_TOKEN]):
        sys.exit("Missing credentials in .env")

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    auth = HTTPBasicAuth(USER_EMAIL, API_TOKEN)

    print(f"Fetching page {PAGE_ID} …")
    body, version, title = get_page(session, auth)
    print(f"  Version : {version}  Size: {len(body):,} chars\n")

    # These exact strings appear in the live page cells for mandatory rows
    # The live page wraps cell content in <p local-id="..."> so we match the td boundary
    replacements = [
        # INF-01 — plain Y (may be wrapped in <p local-id="..."> on live page)
        ("UKHSA-INF-01", "><td>Y</td>", f"><td>{MANDATORY_YES}</td>"),
        ("UKHSA-INF-01", "><td><p", None),  # marker — check if already done
        # INF-05
        ("UKHSA-INF-05", "><td>Y</td>", f"><td>{MANDATORY_YES}</td>"),
    ]

    changes = []
    new_body = body

    # Check both patterns exist as plain Y
    inf01_plain = "INF-01" in body and "><td>Y</td>" in body[body.find("INF-01"):body.find("INF-01")+500]
    inf05_plain = "INF-05" in body and "><td>Y</td>" in body[body.find("INF-05"):body.find("INF-05")+500]

    # Also check for <p local-id="...">Y</p> variant
    import re
    inf01_p = bool(re.search(r'UKHSA-INF-01.*?<td[^>]*>(?:<p[^>]*>)?Y(?:</p>)?</td>', body[:body.find("INF-01")+2000], re.DOTALL))
    inf05_p = bool(re.search(r'UKHSA-INF-05.*?<td[^>]*>(?:<p[^>]*>)?Y(?:</p>)?</td>', body[:body.find("INF-05")+2000] if "INF-05" in body else "", re.DOTALL))

    # Guard: already done?
    already_inf01 = "complete" in body[body.find("INF-01"):body.find("INF-01")+500] if "INF-01" in body else False
    already_inf05 = "complete" in body[body.find("INF-05"):body.find("INF-05")+500] if "INF-05" in body else False

    if already_inf01 and already_inf05:
        print("✔ INF-01 and INF-05 already have pre-ticked checkboxes — nothing to do.")
        return

    # Replace plain Y in INF-01 row
    if not already_inf01:
        # Match: INF-01 row, find the Selected? td with Y
        pat = re.compile(
            r'(UKHSA-INF-01</td>.*?<td[^>]*>)'
            r'(?:<p[^>]*>)?Y(?:</p>)?'
            r'(</td>)',
            re.DOTALL,
        )
        new_body, n = pat.subn(r'\g<1>' + MANDATORY_YES + r'\2', new_body, count=1)
        if n:
            changes.append("INF-01 → pre-ticked Yes (Mandatory) checkbox")
        else:
            changes.append("INF-01 — could not find plain Y cell to replace")

    # Replace plain Y in INF-05 row
    if not already_inf05:
        pat = re.compile(
            r'(UKHSA-INF-05</td>.*?<td[^>]*>)'
            r'(?:<p[^>]*>)?Y(?:</p>)?'
            r'(</td>)',
            re.DOTALL,
        )
        new_body, n = pat.subn(r'\g<1>' + MANDATORY_YES + r'\2', new_body, count=1)
        if n:
            changes.append("INF-05 → pre-ticked Yes (Mandatory) checkbox")
        else:
            changes.append("INF-05 — could not find plain Y cell to replace")

    print("Changes:")
    for c in changes:
        print(f"  ✔ {c}")

    if new_body == body:
        print("\nNo changes applied.")
        return

    print(f"\nSize after patch: {len(new_body):,} chars (delta: {len(new_body)-len(body):+,})")
    print("Pushing update …")
    new_ver = push_page(session, auth, new_body, version, title)
    print(f"\n✅  Done — page updated to version {new_ver}")
    print(f"   {BASE_URL}/spaces/CDA/pages/{PAGE_ID}")


if __name__ == "__main__":
    main()
