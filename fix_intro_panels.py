"""
fix_intro_panels.py
-------------------
One-shot script to replace the Fast-Fill Guidance (tip macro) and
How to Use (info macro) intro panels on the HLD main page.

The enhance script uses _ensure_* functions that only ADD missing
content, so existing panels are never overwritten.  This script
directly replaces them.
"""
import json
import os
import re

import certifi
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

# ── Auth ──────────────────────────────────────────────────────────────────────
BASE_URL = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
EMAIL    = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
TOKEN    = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
PAGE_ID  = "520783944"   # HLD main page

if not TOKEN:
    raise EnvironmentError("Set CONFLUENCE_API_TOKEN env var (and optionally CONFLUENCE_USER_EMAIL).")


def _get_tls_verify():
    ca_bundle = (os.getenv("CONFLUENCE_CA_BUNDLE") or "").strip()
    if ca_bundle and os.path.exists(ca_bundle):
        return ca_bundle
    if os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").strip().lower() in {"1", "true", "yes"}:
        return False
    return certifi.where()


def _make_request(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    """Bearer first, Basic fallback."""
    verify = _get_tls_verify()
    base_headers = dict(kwargs.pop("headers", {}) or {})

    if TOKEN:
        bearer_headers = dict(base_headers)
        bearer_headers["Authorization"] = f"Bearer {TOKEN}"
        resp = session.request(method, url, verify=verify, headers=bearer_headers, auth=None, **kwargs)
        if resp.status_code != 403:
            return resp

    if EMAIL and TOKEN:
        resp = session.request(
            method, url, verify=verify, headers=base_headers,
            auth=HTTPBasicAuth(EMAIL, TOKEN), **kwargs,
        )
        return resp

    return session.request(method, url, verify=verify, headers=base_headers, **kwargs)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return s


# ── New panel content ─────────────────────────────────────────────────────────

NEW_FAST_FILL_BODY = """\
<ul>
  <li>Write short, decision-ready content first. One sentence or one bullet per cell is enough for the first workshop pass.</li>
  <li>For each section, capture the business problem, the architectural impact, and the decision or action needed.</li>
  <li>Where useful, use named options, systems, teams, and measures rather than generic wording.</li>
</ul>"""

NEW_HOW_TO_USE_BODY = """\
<ol>
  <li><strong>Discovery</strong> \u2013 fill in Sections 1\u20136 (Overview, Introduction, Background, Pain Points, Functional Requirements, Non-Functional Requirements) with the project team.</li>
  <li><strong>Design</strong> \u2013 complete Sections 7\u201314 (HLD options, pattern selection, components, connections, data flows, datasets, relationships, network segmentation).</li>
  <li><strong>Generate diagrams</strong> \u2013 run <code>confluence_update_diagrams.py</code> to auto-create all diagrams from the tables above.</li>
  <li><strong>Implementation pack</strong> \u2013 run <code>confluence_generate_implementation_pack.py</code> to output Terraform scaffolds and delivery summary.</li>
</ol>"""


# ── Replacement helpers ───────────────────────────────────────────────────────

def _replace_macro_body(html: str, macro_name: str, new_body: str) -> str:
    """Replace the ac:rich-text-body inside the FIRST macro with the given name."""
    # Pattern: <ac:structured-macro ac:name="tip" ...>...<ac:rich-text-body>...</ac:rich-text-body>...</ac:structured-macro>
    # We use a non-greedy match for the rich-text-body block.
    pattern = (
        r'(<ac:structured-macro\s+ac:name="' + re.escape(macro_name) + r'"[^>]*>)'
        r'(.*?)'
        r'(<ac:rich-text-body>)(.*?)(</ac:rich-text-body>)'
        r'(.*?)(</ac:structured-macro>)'
    )
    def replacer(m):
        return m.group(1) + m.group(2) + m.group(3) + new_body + m.group(5) + m.group(6) + m.group(7)

    new_html, count = re.subn(pattern, replacer, html, count=1, flags=re.DOTALL)
    if count == 0:
        print(f"  WARNING: macro '{macro_name}' not found — panel not replaced.")
    else:
        print(f"  Replaced '{macro_name}' macro body ({count} occurrence).")
    return new_html


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    s = _session()

    # 1. Fetch current page
    print(f"Fetching page {PAGE_ID}...")
    resp = _make_request(
        s, "GET",
        f"{BASE_URL}/rest/api/content/{PAGE_ID}",
        params={"expand": "body.storage,version"},
    )
    resp.raise_for_status()
    data = resp.json()

    version_num  = data["version"]["number"]
    page_title   = data["title"]
    current_body = data["body"]["storage"]["value"]

    print(f"  Title:   {page_title}")
    print(f"  Version: {version_num}")
    print(f"  Body length: {len(current_body)} chars")

    # 2. Replace the two intro panel macros
    updated_body = _replace_macro_body(current_body, "tip",  NEW_FAST_FILL_BODY)
    updated_body = _replace_macro_body(updated_body, "info", NEW_HOW_TO_USE_BODY)

    if updated_body == current_body:
        print("No changes made — both macros may be missing or already up-to-date.")
        return

    # 3. Push back to Confluence
    print(f"Pushing updated body (version {version_num + 1})...")
    payload = {
        "version": {"number": version_num + 1},
        "title": page_title,
        "type": "page",
        "body": {"storage": {"value": updated_body, "representation": "storage"}},
    }
    put_resp = _make_request(
        s, "PUT",
        f"{BASE_URL}/rest/api/content/{PAGE_ID}",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    if put_resp.status_code not in (200, 201):
        raise RuntimeError(f"PUT failed: {put_resp.status_code}\n{put_resp.text}")

    result = put_resp.json()
    links  = result.get("_links", {})
    url    = f"{links.get('base', BASE_URL)}{links.get('webui', '')}"
    print(f"Done: {url}")

    # 4. Update local synced template to reflect the change
    synced_path = os.path.join(os.path.dirname(__file__), "main_page_template.synced.html")
    with open(synced_path, "w", encoding="utf-8") as f:
        f.write(updated_body)
    print(f"Synced template updated: {synced_path}")


if __name__ == "__main__":
    main()
