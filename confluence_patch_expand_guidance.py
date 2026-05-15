"""
confluence_patch_expand_guidance.py
====================================
Patches both live Confluence pages to:
  1. Main HLD page (520783944):
     - Replace 'tip' macro (Fast-Fill Guidance) → 'expand' macro
     - Replace 'info' macro (How to Use) → 'expand' macro
     (Order stays the same — both are already BEFORE the ToC.)

  2. Questionnaire page (521438060):
     - Move 'How to Use', 'Fast-Fill Guidance', and 'Pattern Quick-Reference'
       sections to appear BEFORE the Table of Contents.
     - Wrap all three in 'expand' (collapsible) macros.
     - The 'Sync to HLD' trigger panel stays at the very top.

Run:
    python confluence_patch_expand_guidance.py
"""

import os
import re
import sys
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

HLD_PAGE_ID  = "520783944"
QUEST_PAGE_ID = "521438060"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_page(page_id: str) -> dict:
    r = requests.get(
        f"{BASE_URL}/rest/api/content/{page_id}",
        params={"expand": "body.storage,version"},
        auth=AUTH, headers=HEADERS, verify=VERIFY
    )
    r.raise_for_status()
    return r.json()


def update_page(page_id: str, title: str, version: int, new_body: str) -> None:
    payload = {
        "id": page_id,
        "type": "page",
        "title": title,
        "version": {"number": version + 1},
        "body": {"storage": {"value": new_body, "representation": "storage"}}
    }
    r = requests.put(
        f"{BASE_URL}/rest/api/content/{page_id}",
        json=payload, auth=AUTH, headers=HEADERS, verify=VERIFY
    )
    r.raise_for_status()
    print(f"  ✅ Page {page_id} updated to version {version + 1}")


# ---------------------------------------------------------------------------
# Patch 1 — Main HLD page: tip/info → expand
# ---------------------------------------------------------------------------

def patch_hld_page() -> None:
    print("\n📄 Patching Main HLD page (520783944)…")
    page    = get_page(HLD_PAGE_ID)
    title   = page["title"]
    version = page["version"]["number"]
    body    = page["body"]["storage"]["value"]

    original = body

    # Replace Fast-Fill tip macro → expand (match on macro name + unique title text)
    body = re.sub(
        r'<ac:structured-macro\s+ac:name="tip"(\s[^>]*)?>(\s*)'
        r'(<ac:parameter\s+ac:name="title">[^<]*Fast-Fill[^<]*</ac:parameter>)',
        r'<ac:structured-macro ac:name="expand">\2\3',
        body,
        count=1,
        flags=re.DOTALL
    )

    # Replace How to Use info macro → expand (match on macro name + unique title text)
    body = re.sub(
        r'<ac:structured-macro\s+ac:name="info"(\s[^>]*)?>(\s*)'
        r'(<ac:parameter\s+ac:name="title">[^<]*How to Use[^<]*</ac:parameter>)',
        r'<ac:structured-macro ac:name="expand">\2\3',
        body,
        count=1,
        flags=re.DOTALL
    )

    if body == original:
        print("  ⚠️  No changes detected — tip/info macros may already be expand or not found.")
        return

    update_page(HLD_PAGE_ID, title, version, body)


# ---------------------------------------------------------------------------
# Patch 2 — Questionnaire page: reorder + wrap in expand
# ---------------------------------------------------------------------------

# Confluence may encode headings with local-id attributes, e.g.:
# <h2 local-id="...">📄 Contents</h2>
# We use regex patterns to find section boundaries flexibly.

def patch_questionnaire_page() -> None:
    print("\n📋 Patching Questionnaire page (521438060)…")
    page    = get_page(QUEST_PAGE_ID)
    title   = page["title"]
    version = page["version"]["number"]
    body    = page["body"]["storage"]["value"]

    # ---- Locate the Table of Contents section ----
    # Live page has <h2 local-id="..."> — use flexible attribute matching
    toc_pattern = re.compile(
        r'(<h2[^>]*>[^<]*Contents[^<]*</h2>\s*'
        r'<ac:structured-macro\s+ac:name="toc".*?</ac:structured-macro>)',
        re.DOTALL
    )
    toc_match = toc_pattern.search(body)
    if not toc_match:
        print("  ⚠️  Table of Contents section not found — aborting questionnaire patch.")
        return
    toc_block = toc_match.group(1)

    # ---- Locate the How to Use section ----
    # Live page has <hr local-id="..." /> — use <hr[^>]*/> to match any hr variant
    how_to_use_pattern = re.compile(
        r'<hr[^>]*/>\s*'
        r'<h2[^>]*>[^<]*How to Use[^<]*</h2>\s*'
        r'(<ac:structured-macro\s+ac:name="info".*?</ac:structured-macro>)',
        re.DOTALL
    )
    how_match = how_to_use_pattern.search(body)
    if not how_match:
        print("  ⚠️  'How to Use' section not found — aborting questionnaire patch.")
        return
    how_to_use_inner = how_match.group(1)  # Just the info macro body

    # ---- Locate the Fast-Fill Guidance section ----
    fast_fill_pattern = re.compile(
        r'<hr[^>]*/>\s*'
        r'<h2[^>]*>[^<]*Fast-Fill[^<]*</h2>\s*'
        r'(.*?)'
        r'(?=<hr[^>]*/>)',
        re.DOTALL
    )
    ff_match = fast_fill_pattern.search(body)
    if not ff_match:
        print("  ⚠️  'Fast-Fill Guidance' section not found — aborting questionnaire patch.")
        return
    fast_fill_inner = ff_match.group(1).strip()  # p + table

    # ---- Locate the Pattern Quick-Reference section ----
    pqr_pattern = re.compile(
        r'<hr[^>]*/>\s*'
        r'<h2[^>]*>[^<]*Pattern Quick-Reference[^<]*</h2>\s*'
        r'(.*?)'
        r'(?=<hr[^>]*/>)',
        re.DOTALL
    )
    pqr_match = pqr_pattern.search(body)
    if not pqr_match:
        print("  ⚠️  'Pattern Quick-Reference' section not found — aborting questionnaire patch.")
        return
    pqr_inner = pqr_match.group(1).strip()  # p + table

    # ---- Build the three expand macros ----
    # Extract the rich-text-body content from the info macro for How to Use
    # The info macro itself becomes the body of the expand macro
    htu_body_match = re.search(
        r'<ac:rich-text-body>(.*?)</ac:rich-text-body>',
        how_to_use_inner, re.DOTALL
    )
    how_to_use_body = htu_body_match.group(1).strip() if htu_body_match else how_to_use_inner

    expand_how_to_use = (
        '<ac:structured-macro ac:name="expand">\n'
        '  <ac:parameter ac:name="title">&#9654; How to Use This Page</ac:parameter>\n'
        '  <ac:rich-text-body>\n'
        + how_to_use_body + '\n'
        '  </ac:rich-text-body>\n'
        '</ac:structured-macro>'
    )

    expand_fast_fill = (
        '<ac:structured-macro ac:name="expand">\n'
        '  <ac:parameter ac:name="title">&#9889; Fast-Fill Guidance &#8212; Which Sections to Complete First</ac:parameter>\n'
        '  <ac:rich-text-body>\n'
        + fast_fill_inner + '\n'
        '  </ac:rich-text-body>\n'
        '</ac:structured-macro>'
    )

    expand_pqr = (
        '<ac:structured-macro ac:name="expand">\n'
        '  <ac:parameter ac:name="title">&#128270; Pattern Quick-Reference</ac:parameter>\n'
        '  <ac:rich-text-body>\n'
        + pqr_inner + '\n'
        '  </ac:rich-text-body>\n'
        '</ac:structured-macro>'
    )

    # ---- New guidance block (replaces old ToC + hr + guidance sections) ----
    new_guidance_block = (
        '\n' + expand_how_to_use + '\n\n'
        + expand_fast_fill + '\n\n'
        + expand_pqr + '\n\n'
        + toc_block
    )

    # ---- Find the region to replace ----
    # The region starts at the ToC and ends just after the Pattern Quick-Reference table
    # (the hr after Pattern Quick-Reference is the separator before Section 1 — keep it)
    region_start = toc_match.start()

    # End of region = end of Pattern Quick-Reference content (the <hr /> that follows stays)
    pqr_end = pqr_match.end()

    original = body
    body = body[:region_start] + new_guidance_block + body[pqr_end:]

    if body == original:
        print("  ⚠️  No changes applied — page may already be in the correct structure.")
        return

    update_page(QUEST_PAGE_ID, title, version, body)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not USER_EMAIL or not API_TOKEN:
        print("❌ CONFLUENCE_USER_EMAIL / CONFLUENCE_API_TOKEN not set in .env")
        sys.exit(1)

    try:
        patch_hld_page()
    except Exception as e:
        print(f"  ❌ HLD page patch failed: {e}")

    try:
        patch_questionnaire_page()
    except Exception as e:
        print(f"  ❌ Questionnaire patch failed: {e}")

    print("\n✅ Done.")
