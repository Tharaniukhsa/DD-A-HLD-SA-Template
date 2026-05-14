"""
setup_project.py — Bootstrap a new project from the architecture template.

Creates the full Confluence page hierarchy for a project and writes a
project-specific .env.<slug> file ready to use with all other scripts.

Usage:
    python setup_project.py

You will be prompted for:
  - Project name   (e.g. "LENS Data Platform")
  - Confluence parent page ID  (the page to create everything under)

What it creates in Confluence:
  <Parent page>
  └── <Project Name> — Solution Architecture (HLD)
       ├── Architecture Diagrams
       ├── Low-Level Design (LLD) Solution Architecture Template
       └── Architectural Decision Records (ADR)

What it writes locally:
  .env.<project-slug>   (copy of your base .env + new page IDs)
"""

import os
import re
import sys

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

# ── TLS / auth helpers (same pattern as all other scripts) ──────────────────

def _get_verify():
    ca = (os.getenv("CONFLUENCE_CA_BUNDLE") or "").strip()
    if ca and os.path.exists(ca):
        return ca
    if os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").strip().lower() in {"1", "true", "yes"}:
        return False
    try:
        import certifi
        return certifi.where()
    except ImportError:
        return True


def _make_request(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    api_token  = (os.getenv("CONFLUENCE_API_TOKEN")  or "").strip()
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    verify = _get_verify()

    if api_token:
        s = requests.Session()
        s.headers.update(session.headers)
        s.headers["Authorization"] = f"Bearer {api_token}"
        try:
            r = s.request(method, url, verify=verify, **kwargs)
            if r.status_code != 403:
                return r
        except Exception:
            pass

    if user_email and api_token:
        s = requests.Session()
        s.headers.update(session.headers)
        s.auth = HTTPBasicAuth(user_email, api_token)
        return s.request(method, url, verify=verify, **kwargs)

    return session.request(method, url, verify=verify, **kwargs)


# ── Confluence helpers ───────────────────────────────────────────────────────

def _find_page(session, base_url, space_key, title):
    r = _make_request(session, "GET", f"{base_url}/rest/api/content",
                      params={"spaceKey": space_key, "title": title,
                              "expand": "version,body.storage"},
                      headers={"Content-Type": "application/json"})
    results = r.json().get("results", [])
    return results[0] if results else None


def _create_page(session, base_url, space_key, parent_id, title, body_html):
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "ancestors": [{"id": parent_id}],
        "body": {"storage": {"value": body_html, "representation": "storage"}},
    }
    r = _make_request(session, "POST", f"{base_url}/rest/api/content",
                      json=payload,
                      headers={"Content-Type": "application/json"})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create '{title}': {r.status_code} {r.text[:400]}")
    return r.json()


def _upsert_page(session, base_url, space_key, parent_id, title, body_html):
    """Return existing page if found, otherwise create it."""
    existing = _find_page(session, base_url, space_key, title)
    if existing:
        print(f"  ✓ Already exists: {title}  (ID: {existing['id']})")
        return existing
    page = _create_page(session, base_url, space_key, parent_id, title, body_html)
    print(f"  + Created: {title}  (ID: {page['id']})")
    return page


# ── Page bodies ─────────────────────────────────────────────────────────────

def _fetch_live_template(session, base_url, space_key):
    """
    Fetch the live HLD template page body from Confluence.
    Tries the known template page ID first, then searches by title.
    Returns the raw storage HTML or None.
    """
    # Known template page IDs (original LENS template)
    candidate_ids = ["520783944"]
    candidate_titles = [
        "High-level Design (HLD) Solution Architecture Template",
        "High-level Design (HLD) Solution Architecture",
    ]
    for pid in candidate_ids:
        try:
            r = _make_request(session, "GET",
                              f"{base_url}/rest/api/content/{pid}",
                              params={"expand": "body.storage"},
                              headers={"Content-Type": "application/json"})
            if r.status_code == 200:
                body = r.json().get("body", {}).get("storage", {}).get("value", "")
                if len(body) > 5000:
                    print(f"  Using live template from Confluence page {pid}")
                    return body
        except Exception:
            pass
    for title in candidate_titles:
        try:
            r = _make_request(session, "GET",
                              f"{base_url}/rest/api/content",
                              params={"spaceKey": space_key, "title": title,
                                      "expand": "body.storage"},
                              headers={"Content-Type": "application/json"})
            results = r.json().get("results", [])
            if results:
                body = results[0].get("body", {}).get("storage", {}).get("value", "")
                if len(body) > 5000:
                    print(f"  Using live template: '{title}'")
                    return body
        except Exception:
            pass
    # Fall back to local synced file
    synced = os.path.join(os.path.dirname(__file__), "main_page_template.synced.html")
    if os.path.exists(synced):
        print("  Using local synced template (main_page_template.synced.html)")
        with open(synced, encoding="utf-8") as f:
            return f.read()
    return None


def _blank_table_body(rows=5, cols=5):
    return "".join(f"<tr>{'<td></td>' * cols}</tr>" for _ in range(rows))


def _hld_body(project_name, session=None, base_url=None, space_key=None):
    """
    Build HLD body from the live Confluence template, cleared of all
    project-specific sample data so each new project starts blank.
    """
    import re as _re

    body = None
    if session and base_url and space_key:
        body = _fetch_live_template(session, base_url, space_key)

    if not body:
        print("  [warn] Could not fetch live template — using local synced file or skeleton.")
        synced = os.path.join(os.path.dirname(__file__), "main_page_template.synced.html")
        if os.path.exists(synced):
            with open(synced, encoding="utf-8") as f:
                body = f.read()

    if not body:
        return f"<h1>{project_name} — High-Level Design (HLD) Solution Architecture</h1><p>Fill in this page using the HLD template guidance.</p>"

    # ── 1. Update the page title
    body = _re.sub(
        r'<h1[^>]*>[^<]*(?:HLD|High-Level Design|High-level Design)[^<]*</h1>',
        f'<h1 style="color: #003366; border-bottom: 4px solid #003366; padding-bottom: 10px;">'
        f'{project_name} — High-Level Design (HLD) Solution Architecture</h1>',
        body,
        flags=_re.IGNORECASE,
    )

    # ── 2. Clear Architecture Components table (Section 10) — keep header row only
    body = _re.sub(
        r'(<h[1-4][^>]*>\s*10\.\s*Architecture Components.*?<tbody>)'
        r'(.*?)'
        r'(</tbody>)',
        r'\g<1>' + "".join(
            f'<tr><td>{i}</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>'
            for i in range(1, 9)
        ) + r'\g<3>',
        body,
        flags=_re.DOTALL | _re.IGNORECASE,
    )

    # ── 3. Clear Architecture Connections table (Section 11)
    body = _re.sub(
        r'(<h[1-4][^>]*>\s*11\.\s*Architecture Connections.*?<tbody>)'
        r'(.*?)'
        r'(</tbody>)',
        r'\g<1>' + "".join('<tr><td></td><td></td><td></td><td></td><td></td></tr>' for _ in range(5)) + r'\g<3>',
        body,
        flags=_re.DOTALL | _re.IGNORECASE,
    )

    # ── 4. Clear Context Entities table (Section 9)
    body = _re.sub(
        r'(<h[1-4][^>]*>\s*9\.\s*Context Entities.*?<tbody>)'
        r'(.*?)'
        r'(</tbody>)',
        r'\g<1>' + "".join('<tr><td></td><td></td><td></td><td></td></tr>' for _ in range(5)) + r'\g<3>',
        body,
        flags=_re.DOTALL | _re.IGNORECASE,
    )

    # ── 5. Clear Data Flow Entries table (Section 13)
    body = _re.sub(
        r'(<h[1-4][^>]*>\s*13\.\s*Data Flow Entries.*?<tbody>)'
        r'(.*?)'
        r'(</tbody>)',
        r'\g<1>' + "".join(f'<tr><td>F{i}</td><td></td><td></td><td></td><td></td></tr>' for i in range(1, 6)) + r'\g<3>',
        body,
        flags=_re.DOTALL | _re.IGNORECASE,
    )

    # ── 6. Clear Dataset Inventory table (Section 14)
    body = _re.sub(
        r'(<h[1-4][^>]*>\s*14\.\s*Dataset Inventory.*?<tbody>)'
        r'(.*?)'
        r'(</tbody>)',
        r'\g<1>' + "".join('<tr><td></td><td></td><td></td><td></td><td></td></tr>' for _ in range(3)) + r'\g<3>',
        body,
        flags=_re.DOTALL | _re.IGNORECASE,
    )

    # ── 7. Clear Dataset Relationships table (Section 15)
    body = _re.sub(
        r'(<h[1-4][^>]*>\s*15\.\s*Dataset Relationships.*?<tbody>)'
        r'(.*?)'
        r'(</tbody>)',
        r'\g<1>' + "".join('<tr><td></td><td></td><td></td></tr>' for _ in range(3)) + r'\g<3>',
        body,
        flags=_re.DOTALL | _re.IGNORECASE,
    )

    # ── 8. Reset all Pattern Selection Y/N cells to blank (Section 8)
    body = _re.sub(
        r'(<h[1-4][^>]*>\s*8\.\s*Pattern Selection.*?<tbody>)(.*?)(</tbody>)',
        lambda m: m.group(1) + _re.sub(
            r'(<tr><td>[^<]*</td><td>[^<]*</td><td>)[YyNn]?(</td>)',
            r'\g<1>\g<2>', m.group(2)
        ) + m.group(3),
        body,
        flags=_re.DOTALL | _re.IGNORECASE,
    )

    # ── 9. Remove sections 5a and 5b (Roadmaps / Use case details) ──────────
    #       These are LENS-specific sub-sections baked into the live template.
    #       They create confusing "5a / 6" numbering on new project pages.
    for pat in [
        # styled div wrappers (from _ensure_roadmaps_and_use_case_details)
        r'<!-- SECTION 5[AB][^-]*-->.*?(?=<!-- SECTION|\Z)',
        r'<div[^>]*>(?:\s*<h2[^>]*id="section5[ab]"[^>]*>|\s*<h2[^>]*>\s*5[ab]\.\s*(?:Roadmaps|Use case details)\s*</h2>).*?</div>',
        # plain h2 headings + content that survived Confluence round-trip
        r'<h2[^>]*>\s*5[ab]\.\s*(?:Roadmaps|Use case details)\s*</h2>.*?(?=<h[12])',
    ]:
        body = _re.sub(pat, '', body, flags=_re.DOTALL | _re.IGNORECASE)

    # ── 10. Remove the first two info/tip boxes at the top of the page ──────
    #        Box 1: "⚡ Fast-Fill Guidance" (ac:name="tip")
    #        Box 2: "▶ How to Use This Page" (ac:name="info")
    #        These contain LENS-specific project-type examples and should be blank on new projects.
    def _remove_first_macro(html, macro_name):
        pat = (
            r'<ac:structured-macro\s+ac:name="' + macro_name + r'"[^>]*>'
            r'.*?</ac:structured-macro>'
        )
        m = _re.search(pat, html, flags=_re.DOTALL)
        if m:
            html = html[:m.start()] + html[m.end():]
        return html

    body = _remove_first_macro(body, 'tip')   # Fast-Fill Guidance box
    body = _remove_first_macro(body, 'info')  # How to Use This Page box

    # ── 11. Clear sample values from Section 1 (Solution Overview) table ────
    body = _re.sub(
        r'(<h[1-4][^>]*>\s*1\.\s*Solution Overview.*?<tbody>)(.*?)(</tbody>)',
        lambda m: m.group(1) + _re.sub(
            r'(<tr><td>[^<]+</td><td>)(?:e\.g\.[^<]*|Named[^<]*|Key[^<]*|Formal[^<]*|AWS[^<]*|Official[^<]*|Capability[^<]*|TBC[^<]*)(</td></tr>)',
            r'\g<1>\g<2>', m.group(2)
        ) + m.group(3),
        body,
        flags=_re.DOTALL | _re.IGNORECASE,
    )

    return body


def _diagrams_body(project_name, hld_page_id):
    return f"""<h1>{project_name} — Architecture Diagrams</h1>
<p><em>All auto-generated diagrams for the {project_name} project. Diagrams are embedded from <code>.drawio</code> attachments and refreshed by running <code>confluence_update_diagrams.py</code>.</em></p>
<ac:structured-macro ac:name="info" ac:schema-version="1">
  <ac:parameter ac:name="title">How to refresh diagrams</ac:parameter>
  <ac:rich-text-body>
    <p>Fill in the HLD tables, then run: <code>python confluence_update_diagrams.py</code></p>
  </ac:rich-text-body>
</ac:structured-macro>

<h2>1. Solution Architecture</h2>
<p><strong>[[DIAGRAM:solution-architecture]]</strong></p>

<h2>2. Data Flow Diagram</h2>
<p><strong>[[DIAGRAM:data-flow]]</strong></p>

<h2>3. Dataset Relationship Diagram</h2>
<p><strong>[[DIAGRAM:data-relationship]]</strong></p>

<h2>4. Context View Diagram</h2>
<p><strong>[[DIAGRAM:context-view]]</strong></p>

<h2>5. Logical View Diagram</h2>
<p><strong>[[DIAGRAM:logical-view]]</strong></p>

<h2>6. Authentication Flow Diagram</h2>
<p><strong>[[DIAGRAM:authentication-flow]]</strong></p>

<h2>7. Network Segregation Diagram</h2>
<p><strong>[[DIAGRAM:network-segregation]]</strong></p>
"""


def _lld_body(project_name):
    return f"""<h1>{project_name} — Low-Level Design (LLD)</h1>
<p><em>Run <code>python confluence_update_lld_diagrams.py</code> to populate this page fully from the HLD.</em></p>
"""


def _adr_body(project_name):
    return f"""<h1>{project_name} — Architectural Decision Records</h1>
<p>Log of all architectural decisions for the {project_name} project.</p>
<table>
  <thead><tr><th>ADR ID</th><th>Title</th><th>Status</th><th>Date</th><th>Summary</th></tr></thead>
  <tbody>
    <tr><td>ADR-001</td><td></td><td>Proposed</td><td></td><td></td></tr>
  </tbody>
</table>
"""


# ── .env writer ──────────────────────────────────────────────────────────────

def _write_env(slug, base_url, space_key, hld_id, diagrams_id, lld_id):
    path = f".env.{slug}"
    existing_token  = (os.getenv("CONFLUENCE_API_TOKEN")  or "").strip()
    existing_email  = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    existing_ca     = (os.getenv("CONFLUENCE_CA_BUNDLE")  or "").strip()
    existing_ssl    = (os.getenv("CONFLUENCE_SKIP_SSL_VERIFY") or "false").strip()

    lines = [
        f"# Auto-generated by setup_project.py",
        f"# Project: {slug}",
        f"",
        f"# ── Confluence connection ──────────────────────────────────────────",
        f"CONFLUENCE_BASE_URL={base_url}",
        f"CONFLUENCE_SPACE_KEY={space_key}",
        f"CONFLUENCE_USER_EMAIL={existing_email}",
        f"CONFLUENCE_API_TOKEN={existing_token}",
        f"",
        f"# ── Page IDs ───────────────────────────────────────────────────────",
        f"# Used by confluence_update_lld_diagrams.py",
        f"CONFLUENCE_MAIN_PAGE_ID={hld_id}",
        f"CONFLUENCE_LLD_PAGE_ID={lld_id}",
        f"# Used by confluence_update_diagrams.py",
        f"CONFLUENCE_SOURCE_PAGE_ID={hld_id}",
        f"CONFLUENCE_TARGET_PAGE_ID={diagrams_id}",
        f"",
        f"# ── Page titles (used if IDs not set) ─────────────────────────────",
        f"CONFLUENCE_MAIN_PAGE_TITLE=",
        f"CONFLUENCE_LLD_PAGE_TITLE=",
        f"CONFLUENCE_TARGET_PAGE_TITLE=Architecture Diagrams",
        f"",
        f"# ── Optional: EDAP / UKHSA pattern overrides ──────────────────────",
        f"# Leave blank — patterns are auto-read from HLD Section 8 tick boxes.",
        f"# EDAP_PATTERN_IDS=EDAP-INT-01,EDAP-INT-05",
        f"# UKHSA_PATTERN_IDS=1A,3C,UKHSA-INF-02",
        f"# EDAP_AUTO_DETECT=false",
        f"",
        f"# ── SSL ────────────────────────────────────────────────────────────",
    ]
    if existing_ca:
        lines.append(f"CONFLUENCE_CA_BUNDLE={existing_ca}")
    lines.append(f"CONFLUENCE_SKIP_SSL_VERIFY={existing_ssl}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    base_url   = os.getenv("CONFLUENCE_BASE_URL", "").rstrip("/")
    space_key  = os.getenv("CONFLUENCE_SPACE_KEY", "").strip()

    print("=" * 70)
    print("  ARCHITECTURE TEMPLATE — NEW PROJECT SETUP")
    print("=" * 70)

    if not base_url:
        base_url = input("\nConfluence base URL (e.g. https://ukhsa.atlassian.net/wiki): ").strip().rstrip("/")
    if not space_key:
        space_key = input("Confluence space key (e.g. CDA): ").strip()

    project_name = input("\nProject name (e.g. LENS Data Platform): ").strip()
    if not project_name:
        print("ERROR: project name is required."); sys.exit(1)

    parent_id = input(
        "Parent page ID — the Confluence page to create everything under\n"
        "  (open the page in a browser; the number in the URL is the ID): "
    ).strip()
    if not parent_id:
        print("ERROR: parent page ID is required."); sys.exit(1)

    # derive a slug for filenames/env key
    slug = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    print(f"\nCreating pages in space '{space_key}' under page ID {parent_id} ...\n")

    hld_title      = f"{project_name} — High-Level Design (HLD) Solution Architecture"
    diagrams_title = f"{project_name} — Architecture Diagrams"
    lld_title      = f"{project_name} — Low-Level Design (LLD) Solution Architecture"
    adr_title      = f"{project_name} — Architectural Decision Records"

    try:
        hld_page      = _upsert_page(session, base_url, space_key, parent_id,
                                     hld_title, _hld_body(project_name, session, base_url, space_key))
        diagrams_page = _upsert_page(session, base_url, space_key, hld_page["id"],
                                     diagrams_title, _diagrams_body(project_name, hld_page["id"]))
        lld_page      = _upsert_page(session, base_url, space_key, hld_page["id"],
                                     lld_title, _lld_body(project_name))
        _upsert_page(session, base_url, space_key, hld_page["id"],
                     adr_title, _adr_body(project_name))
    except RuntimeError as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)

    env_path = _write_env(slug, base_url, space_key,
                          hld_page["id"], diagrams_page["id"], lld_page["id"])

    print(f"""
{'=' * 70}
  SETUP COMPLETE
{'=' * 70}

  Pages created:
    HLD:      {base_url}/spaces/{space_key}/pages/{hld_page['id']}
    Diagrams: {base_url}/spaces/{space_key}/pages/{diagrams_page['id']}
    LLD:      {base_url}/spaces/{space_key}/pages/{lld_page['id']}

  Project env file saved: {env_path}

  NEXT STEPS
  ──────────
  1.  Fill in the HLD tables (Architecture Components, Connections,
      Section 8 Pattern Selection, Section 12 Network Segmentation).

  2.  Run the scripts using your project env file:

      $env:CONFLUENCE_MAIN_PAGE_ID="{hld_page['id']}"
      $env:CONFLUENCE_SOURCE_PAGE_ID="{hld_page['id']}"
      $env:CONFLUENCE_LLD_PAGE_ID="{lld_page['id']}"
      $env:CONFLUENCE_TARGET_PAGE_ID="{diagrams_page['id']}"

      -- or use the env file directly:
      Get-Content .env.{slug} | ForEach-Object {{
          if ($_ -match '^([^#=]+)=(.*)$') {{
              [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
          }}
      }}

  3.  python confluence_update_diagrams.py       # generates HLD diagrams
  4.  python confluence_update_lld_diagrams.py   # populates LLD page
  5.  python confluence_generate_implementation_pack.py  # Terraform + JSON
{'=' * 70}
""")


if __name__ == "__main__":
    main()
