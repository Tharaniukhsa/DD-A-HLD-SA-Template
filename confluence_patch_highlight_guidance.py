"""
confluence_patch_highlight_guidance.py
=======================================
Wraps each guidance 'expand' macro in a coloured panel macro so they
visually stand out on the page while remaining collapsible.

Colour scheme (consistent across both pages):
  ⚡ Fast-Fill Guidance         → amber  (#FFF8E6 / #E6A817)
  ▶  How to Use This Page       → blue   (#E6F0FF / #0052CC)
  🔍 Pattern Quick-Reference    → teal   (#E6F7F7 / #00838F)

Pages patched:
  - Main HLD page      520783944
  - Questionnaire page 521438060
"""

import os
import re
import sys
import time
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

BASE_URL   = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki")
USER_EMAIL = os.getenv("CONFLUENCE_USER_EMAIL")
API_TOKEN  = os.getenv("CONFLUENCE_API_TOKEN")
SKIP_SSL   = os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "true").lower() == "true"

AUTH    = HTTPBasicAuth(USER_EMAIL, API_TOKEN)
VERIFY  = not SKIP_SSL
HEADERS = {"Content-Type": "application/json"}

HLD_PAGE_ID   = "520783944"
QUEST_PAGE_ID = "521438060"

# ---------------------------------------------------------------------------
# Panel wrapper colours
# ---------------------------------------------------------------------------
COLOUR_BLUE  = {"bg": "#E6F0FF", "border": "#0052CC"}   # How to Use
COLOUR_AMBER = {"bg": "#FFF8E6", "border": "#E6A817"}   # Fast-Fill
COLOUR_TEAL  = {"bg": "#E6F7F7", "border": "#00838F"}   # Pattern Quick-Ref

# Guidance sections to highlight: (title_fragment, colour)
GUIDANCE_SECTIONS = [
    ("How to Use",          COLOUR_BLUE),
    ("Fast-Fill",           COLOUR_AMBER),
    ("Pattern Quick-Reference", COLOUR_TEAL),
]


def panel_wrap(inner_xml: str, colour: dict) -> str:
    """Wrap inner_xml in a Confluence panel macro with the given colour."""
    return (
        '<ac:structured-macro ac:name="panel">'
        f'<ac:parameter ac:name="bgColor">{colour["bg"]}</ac:parameter>'
        f'<ac:parameter ac:name="borderColor">{colour["border"]}</ac:parameter>'
        '<ac:parameter ac:name="borderWidth">2</ac:parameter>'
        '<ac:rich-text-body>'
        + inner_xml
        + '</ac:rich-text-body>'
        '</ac:structured-macro>'
    )


def already_highlighted(body: str, title_fragment: str) -> bool:
    """True if the expand for this section is already inside a panel macro."""
    # Find the expand with this title, check if 'panel' appears just before it
    pattern = re.compile(
        r'ac:name="panel"[^>]*>.*?'
        r'<ac:parameter\s+ac:name="title">[^<]*' + re.escape(title_fragment) + r'[^<]*</ac:parameter>',
        re.DOTALL
    )
    return bool(pattern.search(body))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_page(page_id: str) -> dict:
    for attempt in range(3):
        try:
            r = requests.get(
                f"{BASE_URL}/rest/api/content/{page_id}",
                params={"expand": "body.storage,version"},
                auth=AUTH, headers=HEADERS, verify=VERIFY, timeout=30
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  Retry {attempt + 1}: {e}")
            time.sleep(3)


def update_page(page_id: str, title: str, version: int, new_body: str) -> None:
    payload = {
        "id": page_id,
        "type": "page",
        "title": title,
        "version": {"number": version + 1},
        "body": {"storage": {"value": new_body, "representation": "storage"}}
    }
    for attempt in range(3):
        try:
            r = requests.put(
                f"{BASE_URL}/rest/api/content/{page_id}",
                json=payload, auth=AUTH, headers=HEADERS, verify=VERIFY, timeout=60
            )
            r.raise_for_status()
            print(f"  ✅ Page {page_id} updated to version {version + 1}")
            return
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  Retry {attempt + 1}: {e}")
            time.sleep(3)


# ---------------------------------------------------------------------------
# Core: wrap each guidance expand macro in a panel
# ---------------------------------------------------------------------------

def highlight_page(page_id: str, label: str) -> None:
    print(f"\n🎨 Highlighting guidance sections on {label} ({page_id})…")
    page    = get_page(page_id)
    title   = page["title"]
    version = page["version"]["number"]
    body    = page["body"]["storage"]["value"]
    original = body

    for title_fragment, colour in GUIDANCE_SECTIONS:
        if already_highlighted(body, title_fragment):
            print(f"  ⏭  '{title_fragment}' already highlighted — skipped")
            continue

        # Match the full expand macro for this section
        pattern = re.compile(
            r'(<ac:structured-macro\s+ac:name="expand"[^>]*>'
            r'(?:(?!</ac:structured-macro>).)*?'       # non-greedy scan
            r'<ac:parameter\s+ac:name="title">[^<]*'
            + re.escape(title_fragment)
            + r'[^<]*</ac:parameter>'
            r'.*?</ac:structured-macro>)',
            re.DOTALL
        )
        m = pattern.search(body)
        if not m:
            print(f"  ⚠️  '{title_fragment}' expand macro not found")
            continue

        expand_xml = m.group(1)
        highlighted = panel_wrap(expand_xml, colour)
        body = body[:m.start()] + highlighted + body[m.end():]
        print(f"  ✔  '{title_fragment}' wrapped in {colour['border']} panel")

    if body == original:
        print("  ℹ️  No changes needed")
        return

    update_page(page_id, title, version, body)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not USER_EMAIL or not API_TOKEN:
        print("❌ CONFLUENCE_USER_EMAIL / CONFLUENCE_API_TOKEN not set in .env")
        sys.exit(1)

    try:
        highlight_page(HLD_PAGE_ID, "Main HLD page")
    except Exception as e:
        print(f"  ❌ HLD page failed: {e}")

    try:
        highlight_page(QUEST_PAGE_ID, "Questionnaire page")
    except Exception as e:
        print(f"  ❌ Questionnaire page failed: {e}")

    print("\n✅ Done.")
