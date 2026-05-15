"""
confluence_setup_sync_trigger.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
One-time setup: adds a "Sync to HLD" trigger panel at the very top of the
questionnaire page.

The panel contains:
  - A single checkbox:  ☐ Sync to HLD
  - A "Last synced" info line (kept up-to-date by the watcher automatically)

Workflow for architects:
  1. Fill in / update the questionnaire
  2. Tick the "Sync to HLD" checkbox and Save the page
  3. The watcher detects the tick within ~30 seconds and:
       a. Runs confluence_sync_questionnaire_to_main.py
       b. Unticks the checkbox automatically
       c. Updates the "Last synced" timestamp on the page

Idempotent — safe to re-run; won't add the panel twice.
"""

import os
import sys
import requests
import urllib3
from datetime import datetime, timezone
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()
BASE_URL   = os.getenv("CONFLUENCE_BASE_URL", "").rstrip("/")
USER_EMAIL = os.getenv("CONFLUENCE_USER_EMAIL", "")
API_TOKEN  = os.getenv("CONFLUENCE_API_TOKEN", "")
TLS_VERIFY = os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").lower() != "true"
PAGE_ID    = "521438060"

# ── The trigger panel HTML ────────────────────────────────────────────────────
# Uses a Confluence info macro as a styled container, with a task-list inside.
TRIGGER_PANEL = """\
<ac:structured-macro ac:name="info" ac:schema-version="1">
  <ac:parameter ac:name="title">&#128257; Sync to HLD</ac:parameter>
  <ac:rich-text-body>
    <p>
      <strong>Tick the checkbox below and Save this page to push your selections to the main HLD page.</strong>
      The watcher will detect it and sync automatically (usually within 30 seconds).
    </p>
    <ac:task-list>
      <ac:task>
        <ac:task-status>incomplete</ac:task-status>
        <ac:task-body>Sync to HLD</ac:task-body>
      </ac:task>
    </ac:task-list>
    <p><em>Last synced: <strong>Never</strong></em></p>
  </ac:rich-text-body>
</ac:structured-macro>
"""

TRIGGER_MARKER = "Sync to HLD"   # unique string used to detect panel presence


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

    print(f"Fetching questionnaire page {PAGE_ID} …")
    body, version, title = get_page(session, auth)
    print(f"  Version : {version}  Size: {len(body):,} chars")

    if TRIGGER_MARKER in body and "ac:task-list" in body[:body.find(TRIGGER_MARKER) + 200]:
        print("\n✔ Sync trigger panel already present — nothing to do.")
        return

    # Prepend the panel before all existing content
    new_body = TRIGGER_PANEL + "\n" + body

    print("\nAdding 'Sync to HLD' trigger panel at top of questionnaire …")
    new_ver = push_page(session, auth, new_body, version, title)
    print(f"\n✅  Done — questionnaire updated to version {new_ver}")
    print(f"   {BASE_URL}/spaces/CDA/pages/{PAGE_ID}")
    print("\nArchitects can now tick '☐ Sync to HLD' and save to trigger an automatic sync.")
    print("Start the watcher:  & '.venv\\Scripts\\python.exe' confluence_watch_questionnaire.py")


if __name__ == "__main__":
    main()
