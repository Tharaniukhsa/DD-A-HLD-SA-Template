"""
confluence_patch_selected_header.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Cleans up the "Selected? (Y/N)" column headers on the live HLD page
to just "Selected?" — consistent with the single-Yes checkbox approach.
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

    count_yn   = body.count("Selected? (Y/N)")
    count_yn2  = body.count("Selected?&nbsp;(Y/N)")

    new_body = body.replace("Selected? (Y/N)", "Selected?")
    new_body = new_body.replace("Selected?&nbsp;(Y/N)", "Selected?")

    total = count_yn + count_yn2
    if total == 0:
        print("✔ Headers already clean — nothing to do.")
        return

    print(f"Replacing {total} 'Selected? (Y/N)' header(s) → 'Selected?'")
    print(f"Pushing update …")
    new_ver = push_page(session, auth, new_body, version, title)
    print(f"\n✅  Done — page updated to version {new_ver}")


if __name__ == "__main__":
    main()
