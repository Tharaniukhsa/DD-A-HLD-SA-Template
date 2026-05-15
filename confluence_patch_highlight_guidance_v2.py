"""
confluence_patch_highlight_guidance_v2.py
==========================================
Replaces the broken panel-macro wrappers with the same inline div styling
that the HLD page already uses for its section colour-coding.

Colour scheme (matches the section divs in confluence_enhance_main_page.py):
  ▶  How to Use This Page           → blue   (#E6F0FF / #0052CC)
  ⚡ Fast-Fill Guidance              → amber  (#FFF8E6 / #E6A817)
  🔍 Pattern Quick-Reference        → teal   (#E6F7F7 / #00838F)

Structure applied:
  <div style="background-color: ...; border-left: 5px solid ...; padding: 15px; margin: 10px 0; border-radius: 4px;">
    <ac:structured-macro ac:name="expand">
      ...
    </ac:structured-macro>
  </div>

Pages:
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
# Div styles — same as the section colour-coding in confluence_enhance_main_page.py
# ---------------------------------------------------------------------------
DIV_STYLE = (
    "background-color: {bg}; border-left: 5px solid {border}; "
    "padding: 15px; margin: 10px 0; border-radius: 4px;"
)

GUIDANCE_SECTIONS = [
    ("How to Use",              {"bg": "#E6F0FF", "border": "#0052CC"}),
    ("Fast-Fill",               {"bg": "#FFF8E6", "border": "#E6A817"}),
    ("Pattern Quick-Reference", {"bg": "#E6F7F7", "border": "#00838F"}),
]


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
            time.sleep(4)


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
            time.sleep(4)


def find_expand_boundaries(body: str, title_fragment: str) -> tuple[int, int] | None:
    """
    Locate the start and end of the <ac:structured-macro ac:name="expand">
    whose title parameter contains title_fragment.
    Returns (start, end) byte positions, or None if not found.
    Handles nested structured macros correctly.
    """
    idx = body.find(title_fragment)
    if idx == -1:
        return None

    # Find the expand macro that contains this title (scan backwards)
    expand_start = body.rfind('<ac:structured-macro ac:name="expand"', 0, idx)
    if expand_start == -1:
        return None

    # Walk forward counting nested <ac:structured-macro> tags to find
    # the matching </ac:structured-macro> for this expand
    pos = expand_start + len('<ac:structured-macro')
    depth = 1
    while depth > 0:
        next_open  = body.find('<ac:structured-macro', pos)
        next_close = body.find('</ac:structured-macro>', pos)
        if next_close == -1:
            return None
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 1
        else:
            depth -= 1
            pos = next_close + len('</ac:structured-macro>')
    return (expand_start, pos)


def apply_div_style(body: str, title_fragment: str, colours: dict) -> tuple[str, str]:
    """
    Finds the guidance expand (with or without an enclosing panel macro),
    strips any panel wrapper, and wraps the bare expand in a styled div.
    Returns (new_body, status_message).
    """
    style = DIV_STYLE.format(**colours)

    boundaries = find_expand_boundaries(body, title_fragment)
    if boundaries is None:
        return body, f"  ⚠️  '{title_fragment}' expand not found — skipped"

    exp_start, exp_end = boundaries
    expand_xml = body[exp_start:exp_end]

    # Check if this expand is already wrapped in a styled div
    # (look at what immediately precedes the expand)
    pre = body[max(0, exp_start - 200):exp_start]
    if 'border-left:' in pre and '<div style=' in pre:
        return body, f"  ⏭  '{title_fragment}' already div-styled — skipped"

    # Check if a panel macro wraps this expand; if so, include the panel
    # in what we replace (panel start..panel end → div + expand)
    panel_prefix = '<ac:structured-macro ac:name="panel"'
    panel_candidate = body.rfind(panel_prefix, max(0, exp_start - 600), exp_start)

    region_start = exp_start
    region_end   = exp_end

    if panel_candidate != -1:
        # Verify that the panel's <ac:rich-text-body> comes between
        # the panel start and the expand start
        rtb_pos = body.find('<ac:rich-text-body>', panel_candidate, exp_start)
        if rtb_pos != -1:
            # Find where the panel closes: after exp_end, find </ac:rich-text-body>
            # then </ac:structured-macro>
            rtb_close  = body.find('</ac:rich-text-body>', exp_end)
            mac_close  = body.find('</ac:structured-macro>', rtb_close if rtb_close != -1 else exp_end)
            if mac_close != -1:
                region_start = panel_candidate
                region_end   = mac_close + len('</ac:structured-macro>')

    replacement = f'<div style="{style}">{expand_xml}</div>'
    new_body = body[:region_start] + replacement + body[region_end:]
    return new_body, f"  ✔  '{title_fragment}' styled with div ({colours['border']})"


# ---------------------------------------------------------------------------
# Per-page patch
# ---------------------------------------------------------------------------

def patch_page(page_id: str, label: str) -> None:
    print(f"\n🎨 Applying div colour styling on {label} ({page_id})…")
    page    = get_page(page_id)
    title   = page["title"]
    version = page["version"]["number"]
    body    = page["body"]["storage"]["value"]
    original = body

    for title_fragment, colours in GUIDANCE_SECTIONS:
        body, msg = apply_div_style(body, title_fragment, colours)
        print(msg)

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
        patch_page(HLD_PAGE_ID, "Main HLD page")
    except Exception as e:
        print(f"  ❌ HLD page failed: {e}")

    try:
        patch_page(QUEST_PAGE_ID, "Questionnaire page")
    except Exception as e:
        print(f"  ❌ Questionnaire page failed: {e}")

    print("\n✅ Done.")
