"""
confluence_patch_remove_placeholder.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Removes the "13. Auto-Generated Diagrams (Placeholder)" section from the
live questionnaire page and renumbers "14. Related Documents" -> "13."
Now redundant because the "Sync to HLD" trigger checkbox handles everything.
Idempotent — safe to re-run.
"""

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
PAGE_ID    = "521438060"


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


def patch_body(body: str) -> tuple:
    changes = []

    # Guard: already removed?
    if "Auto-Generated Diagrams" not in body:
        return body, ["Placeholder section already removed — nothing to do"]

    # Remove the entire Section 13 block — from its <hr/> up to (but not including)
    # the next <hr/> that precedes Section 14
    removed = re.sub(
        r'<hr\s*/>\s*<h2[^>]*>\s*1[34]\.\s*Auto-Generated Diagrams.*?(?=<hr\s*/>)',
        '',
        body,
        count=1,
        flags=re.DOTALL,
    )

    if removed == body:
        # Fallback: try matching just the heading + content up to the next h2
        removed = re.sub(
            r'<h2[^>]*>\s*1[34]\.\s*Auto-Generated Diagrams.*?(?=<h2)',
            '',
            body,
            count=1,
            flags=re.DOTALL,
        )

    if removed != body:
        changes.append("Removed '13. Auto-Generated Diagrams (Placeholder)' section")
        body = removed

    # Renumber "14. Related Documents" -> "13."
    new_body, n = re.subn(
        r'(<h2[^>]*>)\s*14\.\s*(Related Documents)',
        r'\g<1>13. \2',
        body,
        count=1,
    )
    if n:
        changes.append("Renumbered 'Related Documents' 14 → 13")
        body = new_body

    if not changes:
        changes.append("Nothing matched — no changes made")

    return body, changes


def main():
    if not all([BASE_URL, USER_EMAIL, API_TOKEN]):
        sys.exit("Missing credentials in .env")

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    auth = HTTPBasicAuth(USER_EMAIL, API_TOKEN)

    print(f"Fetching questionnaire page {PAGE_ID} …")
    body, version, title = get_page(session, auth)
    print(f"  Version : {version}  Size: {len(body):,} chars\n")

    new_body, changes = patch_body(body)

    print("Changes:")
    for c in changes:
        print(f"  ✔ {c}")

    if new_body == body:
        print("\nNo changes needed.")
        return

    print(f"\nSize after patch: {len(new_body):,} chars (delta: {len(new_body)-len(body):+,})")
    print("Pushing update …")
    new_ver = push_page(session, auth, new_body, version, title)
    print(f"\n✅  Done — questionnaire updated to version {new_ver}")
    print(f"   {BASE_URL}/spaces/CDA/pages/{PAGE_ID}")


if __name__ == "__main__":
    main()
