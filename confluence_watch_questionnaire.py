"""
confluence_watch_questionnaire.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Watches the Confluence questionnaire page for version changes and automatically
runs confluence_sync_questionnaire_to_main.py whenever a new version is detected.

Usage:
    python confluence_watch_questionnaire.py            # poll every 2 minutes (default)
    python confluence_watch_questionnaire.py --interval 5   # poll every 5 minutes

Stop with Ctrl+C.

How it works:
    1. Every <interval> minutes, check the questionnaire page version number via the API.
    2. If the version has increased since last check, trigger the sync script immediately.
    3. Print a timestamped log of every check and every sync run.

To run in the background (so you can close the terminal):
    Start-Process pythonw -ArgumentList "confluence_watch_questionnaire.py" -WindowStyle Hidden
"""

import argparse
import os
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

BASE_URL          = os.getenv("CONFLUENCE_BASE_URL", "").rstrip("/")
USER_EMAIL        = os.getenv("CONFLUENCE_USER_EMAIL", "")
API_TOKEN         = os.getenv("CONFLUENCE_API_TOKEN", "")
TLS_VERIFY        = os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").lower() != "true"
QUESTIONNAIRE_ID  = "521438060"   # Data Solution Architecture Questionnaire
SYNC_SCRIPT       = os.path.join(os.path.dirname(__file__), "confluence_sync_questionnaire_to_main.py")
PYTHON            = sys.executable   # same venv python that runs this watcher


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_version(session: requests.Session, auth: HTTPBasicAuth) -> int:
    """Return the current version number of the questionnaire page."""
    url = f"{BASE_URL}/rest/api/content/{QUESTIONNAIRE_ID}?expand=version"
    r = session.get(url, auth=auth, verify=TLS_VERIFY, timeout=30)
    r.raise_for_status()
    return r.json()["version"]["number"]


def run_sync() -> bool:
    """Run the sync script. Returns True if it succeeded."""
    print(f"[{now()}] ▶ Running sync …", flush=True)
    result = subprocess.run(
        [PYTHON, SYNC_SCRIPT],
        capture_output=True,
        text=True,
    )
    # Print sync output indented
    for line in result.stdout.splitlines():
        print(f"         {line}", flush=True)
    if result.returncode != 0:
        print(f"[{now()}] ⚠  Sync exited with code {result.returncode}", flush=True)
        for line in result.stderr.splitlines():
            print(f"         {line}", flush=True)
        return False
    print(f"[{now()}] ✅ Sync complete.", flush=True)
    return True


def watch(interval_minutes: int) -> None:
    if not all([BASE_URL, USER_EMAIL, API_TOKEN]):
        sys.exit("ERROR: Missing CONFLUENCE_BASE_URL / USER_EMAIL / API_TOKEN in .env")

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    auth = HTTPBasicAuth(USER_EMAIL, API_TOKEN)

    print(f"[{now()}] 👀 Watching questionnaire page {QUESTIONNAIRE_ID}")
    print(f"[{now()}]    Polling every {interval_minutes} min — press Ctrl+C to stop.\n", flush=True)

    # Get the starting version without syncing
    try:
        last_version = get_version(session, auth)
    except Exception as exc:
        sys.exit(f"ERROR: Could not fetch questionnaire page — {exc}")

    print(f"[{now()}] ℹ  Current version: {last_version}  (watching for changes …)\n", flush=True)

    while True:
        time.sleep(interval_minutes * 60)
        try:
            current_version = get_version(session, auth)
        except Exception as exc:
            print(f"[{now()}] ⚠  Poll failed: {exc} — will retry next interval.", flush=True)
            continue

        if current_version > last_version:
            print(
                f"[{now()}] 🔔 Questionnaire updated: v{last_version} → v{current_version}",
                flush=True,
            )
            last_version = current_version
            run_sync()
            print(flush=True)
        else:
            print(f"[{now()}]    No change (still v{current_version})", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-sync HLD when the questionnaire page changes."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        metavar="MINUTES",
        help="How often to poll (default: 2 minutes)",
    )
    args = parser.parse_args()
    try:
        watch(args.interval)
    except KeyboardInterrupt:
        print(f"\n[{now()}] Stopped.", flush=True)


if __name__ == "__main__":
    main()
