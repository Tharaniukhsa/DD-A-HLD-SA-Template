"""
confluence_watch_questionnaire.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Watches the questionnaire page for a "Sync to HLD" trigger checkbox.
When an architect ticks it and saves, the watcher:
  1. Detects the ticked checkbox (within ~30 seconds)
  2. Runs confluence_sync_questionnaire_to_main.py automatically
  3. Unticks the checkbox on the page
  4. Updates the "Last synced: ..." timestamp in the panel

Setup (one-time, adds the trigger panel to the questionnaire):
    python confluence_setup_sync_trigger.py

Then start the watcher:
    python confluence_watch_questionnaire.py

Run in background (silent, survives closing the terminal):
    Start-Process pythonw -ArgumentList "confluence_watch_questionnaire.py" -WindowStyle Hidden

Stop with Ctrl+C.
"""

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime

import requests
import urllib3
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

BASE_URL         = os.getenv("CONFLUENCE_BASE_URL", "").rstrip("/")
USER_EMAIL       = os.getenv("CONFLUENCE_USER_EMAIL", "")
API_TOKEN        = os.getenv("CONFLUENCE_API_TOKEN", "")
TLS_VERIFY       = os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").lower() != "true"
QUESTIONNAIRE_ID = "521438060"
SYNC_SCRIPT      = os.path.join(os.path.dirname(__file__), "confluence_sync_questionnaire_to_main.py")
PYTHON           = sys.executable

# Matches the trigger task when the "Sync to HLD" task is TICKED (complete)
_TRIGGER_TICKED = re.compile(
    r'<ac:task-list>'
    r'\s*<ac:task>'
    r'\s*<ac:task-status>complete</ac:task-status>'
    r'\s*<ac:task-body>Sync to HLD</ac:task-body>'
    r'\s*</ac:task>'
    r'\s*</ac:task-list>',
    re.DOTALL,
)

# What we reset the trigger to after a successful sync (unticked)
_TRIGGER_RESET = (
    '<ac:task-list>'
    '<ac:task>'
    '<ac:task-status>incomplete</ac:task-status>'
    '<ac:task-body>Sync to HLD</ac:task-body>'
    '</ac:task>'
    '</ac:task-list>'
)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_page(session, auth) -> tuple:
    url = f"{BASE_URL}/rest/api/content/{QUESTIONNAIRE_ID}?expand=body.storage,version"
    r = session.get(url, auth=auth, verify=TLS_VERIFY, timeout=30)
    r.raise_for_status()
    data = r.json()
    return (
        data["body"]["storage"]["value"],
        data["version"]["number"],
        data["title"],
    )


def push_page(session, auth, body: str, version: int, title: str) -> int:
    url = f"{BASE_URL}/rest/api/content/{QUESTIONNAIRE_ID}"
    payload = {
        "version": {"number": version + 1},
        "title": title,
        "type": "page",
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    r = session.put(url, auth=auth, json=payload, verify=TLS_VERIFY, timeout=30)
    r.raise_for_status()
    return r.json()["version"]["number"]


def is_triggered(body: str) -> bool:
    """Return True if the 'Sync to HLD' checkbox is currently ticked."""
    return bool(_TRIGGER_TICKED.search(body))


def reset_trigger(session, auth, body: str, version: int, title: str, sync_ok: bool) -> int:
    """Untick the checkbox and update the Last synced timestamp."""
    ts = datetime.now().strftime("%d %b %Y %H:%M")
    status = f"Synced {ts}" if sync_ok else f"Sync FAILED at {ts} — check watcher terminal"

    # Untick the checkbox
    new_body = _TRIGGER_TICKED.sub(_TRIGGER_RESET, body, count=1)

    # Update the "Last synced:" line inside the panel
    new_body = re.sub(
        r'<em>Last synced:\s*<strong>[^<]*</strong></em>',
        f'<em>Last synced: <strong>{status}</strong></em>',
        new_body,
        count=1,
    )
    return push_page(session, auth, new_body, version, title)


def run_sync() -> bool:
    """Run the sync script. Returns True on success."""
    print(f"[{now()}] Running sync ...", flush=True)
    result = subprocess.run([PYTHON, SYNC_SCRIPT], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        print(f"         {line}", flush=True)
    if result.returncode != 0:
        print(f"[{now()}] Sync exited with code {result.returncode}", flush=True)
        for line in result.stderr.splitlines():
            print(f"         {line}", flush=True)
        return False
    print(f"[{now()}] Sync complete.", flush=True)
    return True


def watch(poll_seconds: int) -> None:
    if not all([BASE_URL, USER_EMAIL, API_TOKEN]):
        sys.exit("ERROR: Missing CONFLUENCE_BASE_URL / USER_EMAIL / API_TOKEN in .env")

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    auth = HTTPBasicAuth(USER_EMAIL, API_TOKEN)

    print(f"[{now()}] Watching questionnaire page {QUESTIONNAIRE_ID}")
    print(f"[{now()}] Checking every {poll_seconds}s -- press Ctrl+C to stop.")
    print(f"[{now()}] Tick the 'Sync to HLD' checkbox on the questionnaire page to trigger a sync.\n",
          flush=True)

    last_version = -1

    while True:
        time.sleep(poll_seconds)
        try:
            body, version, title = get_page(session, auth)
        except Exception as exc:
            print(f"[{now()}] Poll failed: {exc} -- retrying.", flush=True)
            continue

        if version == last_version:
            continue   # page unchanged -- silent skip

        last_version = version

        if is_triggered(body):
            print(f"[{now()}] 'Sync to HLD' ticked (page v{version}) -- starting sync ...",
                  flush=True)
            sync_ok = run_sync()
            try:
                new_ver = reset_trigger(session, auth, body, version, title, sync_ok)
                print(f"[{now()}] Checkbox reset, questionnaire now v{new_ver}", flush=True)
            except Exception as exc:
                print(f"[{now()}] Could not reset checkbox: {exc}", flush=True)
            print(flush=True)
        else:
            print(f"[{now()}] Page updated to v{version} (no sync trigger -- no action).",
                  flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Watch questionnaire for 'Sync to HLD' checkbox trigger."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        metavar="SECONDS",
        help="Poll interval in seconds (default: 30)",
    )
    args = parser.parse_args()
    try:
        watch(args.interval)
    except KeyboardInterrupt:
        print(f"\n[{now()}] Stopped.", flush=True)


if __name__ == "__main__":
    main()
