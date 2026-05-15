"""
confluence_patch_simplify_checkboxes.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Converts all "Yes / No" two-option task-lists in the HLD page to a single
"Yes" checkbox (unchecked = implicitly No — no separate No box needed).
Also renames any "Select" single-checkbox to "Yes" for consistency.

Run once to update the live page; idempotent thereafter.
"""

import json
import os
import re
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

# ─── Single-Yes task-list template ───────────────────────────────────────────
SINGLE_YES = (
    '<ac:task-list>'
    '<ac:task><ac:task-status>incomplete</ac:task-status>'
    '<ac:task-body>Yes</ac:task-body></ac:task>'
    '</ac:task-list>'
)


def patch_body(body: str) -> tuple[str, list[str]]:
    changes = []

    # 1. Yes/No task-list → single Yes
    #    Matches both <span>Yes</span> and bare Yes variants
    yes_no_pat = re.compile(
        r'<ac:task-list>'
        r'<ac:task><ac:task-status>incomplete</ac:task-status>'
        r'<ac:task-body>(?:<span>)?Yes(?:</span>)?</ac:task-body></ac:task>'
        r'<ac:task><ac:task-status>incomplete</ac:task-status>'
        r'<ac:task-body>(?:<span>)?No(?:</span>)?</ac:task-body></ac:task>'
        r'</ac:task-list>',
        re.DOTALL,
    )
    count = len(yes_no_pat.findall(body))
    if count:
        body = yes_no_pat.sub(SINGLE_YES, body)
        changes.append(f"Yes/No → single Yes  ({count} task-lists)")

    # 2. "Select" single checkbox → "Yes"
    select_pat = re.compile(
        r'<ac:task-list>'
        r'<ac:task><ac:task-status>incomplete</ac:task-status>'
        r'<ac:task-body>(?:<span>)?Select(?:</span>)?</ac:task-body></ac:task>'
        r'</ac:task-list>',
        re.DOTALL,
    )
    count2 = len(select_pat.findall(body))
    if count2:
        body = select_pat.sub(SINGLE_YES, body)
        changes.append(f"'Select' → single Yes  ({count2} task-lists)")

    if not changes:
        changes.append("Already simplified — nothing to do")

    return body, changes


# ─── Confluence helpers ───────────────────────────────────────────────────────

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
        sys.exit("Missing CONFLUENCE_BASE_URL / USER_EMAIL / API_TOKEN in .env")

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    auth = HTTPBasicAuth(USER_EMAIL, API_TOKEN)

    print(f"Fetching page {PAGE_ID} …")
    body, version, title = get_page(session, auth)
    print(f"  Title   : {title}")
    print(f"  Version : {version}")
    print(f"  Size    : {len(body):,} chars\n")

    new_body, changes = patch_body(body)

    print("Changes:")
    for c in changes:
        print(f"  ✔ {c}")

    if new_body == body:
        print("\nNo changes needed — page already uses single-Yes checkboxes.")
        return

    print(f"\nSize after patch: {len(new_body):,} chars (delta: {len(new_body)-len(body):+,})")
    print("Pushing update to Confluence …")
    new_ver = push_page(session, auth, new_body, version, title)
    print(f"\n✅  Done — page updated to version {new_ver}")
    print(f"   {BASE_URL}/spaces/CDA/pages/{PAGE_ID}")


if __name__ == "__main__":
    main()
