"""
confluence_patch_checkboxes.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Converts all "pick one" / "select one" fields on the HLD page to
interactive Confluence task-list checkboxes (one checkbox per option).
Architects tick the right box when filling out the template.

Fields converted:
  Section 1:
    - Version status          : 0.1 DRAFT / In Review / Approved
    - Data Sensitivity        : Official / Official-Sensitive / Personal Data (can be combined)
    - Target Cloud Platform   : AWS (HALO) / Azure (PHECloud) / OpenShift (OCP) / Hybrid / Multi-cloud
    - Architecture Tier       : Tier 1 / Tier 2 / Tier 3
  Section 5:
    - FR Priority             : Must Have / Should Have / Could Have / Won't Have  (per row header)
    - NFR Priority            : High / Medium / Low (per row header)
  Section 7 options:
    - Decision Status per option: Preferred / Candidate / Rejected
  Section 8 patterns:
    - Selected? column        : single Yes checkbox (unchecked = No)
  Section 8h connectivity:
    - Selected? column        : single Yes checkbox (unchecked = No)
  Section 16 LLD:
    - Status column           : Draft / In Progress / Complete / Signed Off
"""

import json
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
PAGE_ID    = "520783944"


# ─── Helper: build a Confluence task-list with N options ─────────────────────
def tasklist(*options: str) -> str:
    """Return an ac:task-list with one incomplete task per option."""
    items = ""
    for opt in options:
        items += (
            f'<ac:task>'
            f'<ac:task-status>incomplete</ac:task-status>'
            f'<ac:task-body><span>{opt}</span></ac:task-body>'
            f'</ac:task>'
        )
    return f'<ac:task-list>{items}</ac:task-list>'


# ─── Task-list HTML for each field ───────────────────────────────────────────

TL_VERSION = tasklist(
    "0.1 – DRAFT",
    "0.2 – In Review",
    "1.0 – Approved",
)

TL_SENSITIVITY = tasklist(
    "Official",
    "Official-Sensitive",
    "Official-Sensitive (Personal Data / Special Category)",
)

TL_PLATFORM = tasklist(
    "AWS (HALO Landing Zone)",
    "Azure (PHECloud Landing Zone)",
    "OpenShift (OCP – On-Premises)",
    "Hybrid (AWS + On-Prem)",
    "Hybrid (Azure + On-Prem)",
    "Multi-Cloud (AWS + Azure)",
    "Multi-Cloud + On-Prem (all four environments)",
)

TL_TIER = tasklist(
    "Tier 1 – Strategic Platform (enterprise-wide shared service, e.g. EDAP, APIM, Sentinel – any cloud)",
    "Tier 2 – Managed Integration (feeds or consumes a Tier 1 platform – AWS, Azure, OpenShift, or hybrid)",
    "Tier 3 – Project Workload (standalone solution deployed into an approved UKHSA landing zone)",
)

TL_MOSCO = tasklist("Must Have", "Should Have", "Could Have", "Won't Have")

TL_NFR_PRIORITY = tasklist("High", "Medium", "Low")

TL_OPTION_STATUS = tasklist("Preferred", "Candidate", "Rejected")

TL_YN = tasklist("Yes")                   # single Yes — unchecked means No

TL_CHECKBOX = tasklist("Yes")             # single Yes for CONN Selected? column

TL_LLD_STATUS = tasklist("Draft", "In Progress", "Complete", "Signed Off")

TL_FR_STATUS  = tasklist("Draft", "In Progress", "Complete")


# ─── Replacement helpers ──────────────────────────────────────────────────────

def replace_cell_content(body: str, cell_text: str, replacement: str, *, max_replacements: int = 50) -> tuple[str, int]:
    """Replace the CONTENT of every <td> cell that exactly matches cell_text."""
    # We match <td...>CONTENT</td> where CONTENT stripped == cell_text stripped
    pattern = re.compile(
        r'(<td[^>]*>)\s*' + re.escape(cell_text) + r'\s*(</td>)',
        re.DOTALL
    )
    new_body, count = pattern.subn(lambda m: m.group(1) + replacement + m.group(2), body, count=max_replacements)
    return new_body, count


def replace_first_cell_content(body: str, cell_text_pattern: str, replacement: str) -> tuple[str, int]:
    """Replace first matching <td> cell whose text matches a regex pattern."""
    pattern = re.compile(
        r'(<td[^>]*>)\s*' + cell_text_pattern + r'\s*(</td>)',
        re.DOTALL
    )
    new_body, count = pattern.subn(lambda m: m.group(1) + replacement + m.group(2), body, count=1)
    return new_body, count


# ─────────────────────────────────────────────────────────────────────────────

def get_session() -> requests.Session:
    s = requests.Session()
    s.auth = HTTPBasicAuth(USER_EMAIL, API_TOKEN)
    s.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
    return s


def fetch_page(session: requests.Session) -> dict:
    resp = session.get(
        f"{BASE_URL}/rest/api/content/{PAGE_ID}",
        params={"expand": "body.storage,version,title"},
        verify=TLS_VERIFY,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def update_page(session: requests.Session, version: int, title: str, body: str) -> dict:
    payload = {
        "version": {"number": version + 1},
        "title": title,
        "type": "page",
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    resp = session.put(
        f"{BASE_URL}/rest/api/content/{PAGE_ID}",
        data=json.dumps(payload),
        verify=TLS_VERIFY,
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        print(f"ERROR {resp.status_code}: {resp.text[:800]}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def patch_body(body: str) -> tuple[str, list[str]]:
    changes: list[str] = []

    # Guard: skip if all three Section 1 choice fields are already converted
    sec1_done = (
        "0.1 &ndash; DRAFT" not in body
        and "AWS / Azure / Hybrid" not in body
        and "e.g. Official / Official-Sensitive / Personal Data" not in body
    )
    if sec1_done and body.count("<ac:task-list>") > 50:
        return body, ["All checkboxes already applied — nothing to do"]

    # ── Section 1: Version ───────────────────────────────────────────────────
    # Cells are wrapped in <p local-id="..."> on the live page
    ver_pat = re.compile(r'(<td[^>]*>)\s*<p[^>]*>\s*0\.1 &ndash; DRAFT\s*</p>\s*(</td>)', re.DOTALL)
    body, n = ver_pat.subn(lambda m: m.group(1) + TL_VERSION + m.group(2), body, count=1)
    if n == 0:
        body, n = replace_cell_content(body, "0.1 &ndash; DRAFT", TL_VERSION)
    changes.append(f"Section 1 Version → task-list ({n} cells)")

    # ── Section 1: Data Sensitivity ──────────────────────────────────────────
    sens_pat = re.compile(r'(<td[^>]*>)\s*<p[^>]*>\s*e\.g\. Official / Official-Sensitive / Personal Data\s*</p>\s*(</td>)', re.DOTALL)
    body, n = sens_pat.subn(lambda m: m.group(1) + TL_SENSITIVITY + m.group(2), body, count=1)
    if n == 0:
        body, n = replace_cell_content(body, "e.g. Official / Official-Sensitive / Personal Data", TL_SENSITIVITY)
    changes.append(f"Section 1 Data Sensitivity → task-list ({n} cells)")

    # ── Section 1: Target Cloud Platform ─────────────────────────────────────
    plat_pat = re.compile(r'(<td[^>]*>)\s*<p[^>]*>\s*AWS / Azure / Hybrid\s*</p>\s*(</td>)', re.DOTALL)
    body, n = plat_pat.subn(lambda m: m.group(1) + TL_PLATFORM + m.group(2), body, count=1)
    if n == 0:
        body, n = replace_cell_content(body, "AWS / Azure / Hybrid", TL_PLATFORM)
    changes.append(f"Section 1 Target Cloud Platform → task-list ({n} cells)")

    # ── Section 1: Architecture Tier ─────────────────────────────────────────
    # The tier text is long — match by partial prefix
    tier_pat = re.compile(
        r'(<td[^>]*>)\s*<strong>Tier 1</strong>[^<]*Strategic Platform.*?(&mdash; select one)\s*(</td>)',
        re.DOTALL
    )
    body, n = tier_pat.subn(lambda m: m.group(1) + TL_TIER + m.group(3), body, count=1)
    changes.append(f"Section 1 Architecture Tier → task-list ({n} cells)")

    # ── Section 5: FR Priority column — replace plain "Must Have" etc cells ──
    # These appear as standalone text in the Priority column
    for label in ("Must Have", "Should Have", "Could Have", "Won&apos;t Have", "Won't Have"):
        body, n = replace_cell_content(body, label, TL_MOSCO)
        if n:
            changes.append(f"Section 5 FR Priority '{label}' → task-list ({n} cells)")

    # ── Section 5: NFR Priority column ───────────────────────────────────────
    # NFR rows have cells with just "High" or "Medium"
    for label, tl in (("High", TL_NFR_PRIORITY), ("Medium", TL_NFR_PRIORITY)):
        # Only replace cells in NFR rows (rows that start with NFR)
        # We do this contextually: replace <td>High</td> that appears right after NFR row context
        pass  # handled below with targeted pattern

    # Target NFR status cells: pattern is <td>High</td> preceded by NFR cell in same row
    nfr_row_pat = re.compile(
        r'(<tr[^>]*>)(.*?NFR[0-9].*?)(</tr>)',
        re.DOTALL
    )
    def fix_nfr_row(m):
        row_html = m.group(2)
        # Replace priority cells
        for lbl in ("High", "Medium", "Low"):
            row_html = re.sub(
                r'(<td[^>]*>)\s*' + lbl + r'\s*(</td>)',
                lambda mm, l=lbl: mm.group(1) + TL_NFR_PRIORITY + mm.group(2),
                row_html
            )
        # Replace status cells (Draft)
        row_html = re.sub(
            r'(<td[^>]*>)\s*Draft\s*(</td>)',
            lambda mm: mm.group(1) + TL_FR_STATUS + mm.group(2),
            row_html
        )
        return m.group(1) + row_html + m.group(3)

    body, nfr_count = nfr_row_pat.subn(fix_nfr_row, body)
    changes.append(f"Section 5 NFR priority + status → task-list ({nfr_count} rows)")

    # ── Section 5: FR status cells (Draft) ───────────────────────────────────
    fr_row_pat = re.compile(
        r'(<tr[^>]*>)(.*?<td[^>]*>\s*FR[0-9].*?)(</tr>)',
        re.DOTALL
    )
    def fix_fr_row(m):
        row_html = m.group(2)
        # Replace MoSCoW cells
        for lbl in ("Must Have", "Should Have", "Could Have"):
            row_html = re.sub(
                r'(<td[^>]*>)\s*' + re.escape(lbl) + r'\s*(</td>)',
                lambda mm: mm.group(1) + TL_MOSCO + mm.group(2),
                row_html
            )
        # Replace status Draft cells
        row_html = re.sub(
            r'(<td[^>]*>)\s*Draft\s*(</td>)',
            lambda mm: mm.group(1) + TL_FR_STATUS + mm.group(2),
            row_html
        )
        return m.group(1) + row_html + m.group(3)

    body, fr_count = fr_row_pat.subn(fix_fr_row, body)
    changes.append(f"Section 5 FR MoSCoW + status → task-list ({fr_count} rows)")

    # ── Section 7: Option decision status ────────────────────────────────────
    for status in ("Preferred", "Candidate", "Rejected"):
        body, n = replace_cell_content(body, status, TL_OPTION_STATUS)
        if n:
            changes.append(f"Section 7 option status '{status}' → task-list ({n} cells)")

    # ── Section 8 patterns: Selected? (Y/N) empty cells in pattern tables ────
    # The "Selected? (Y/N)" column cells are empty <td></td>
    # Strategy: replace empty <td></td> that appear in rows containing pattern IDs
    pattern_row_pat = re.compile(
        r'(<tr[^>]*>)(.*?UKHSA-(?:INF|DAT|SEC)|.*?TSA-(?:NET|IDN)|.*?SBD-[0-9])(.*?)(</tr>)',
        re.DOTALL
    )
    def fix_pattern_row(m):
        row = m.group(2) + m.group(3)
        # Replace first empty td (the Selected? column)
        row = re.sub(
            r'(<td[^>]*>)\s*(</td>)',
            lambda mm: mm.group(1) + TL_YN + mm.group(2),
            row, count=1
        )
        return m.group(1) + row + m.group(4)

    body, pat_count = pattern_row_pat.subn(fix_pattern_row, body)
    changes.append(f"Section 8 pattern Selected? columns → task-list ({pat_count} rows)")

    # ── Section 8h: CONN Selected? column (last empty td in each CONN row) ───
    conn_row_pat = re.compile(
        r'(<tr[^>]*>)(.*?CONN-[0-9][0-9].*?)(</tr>)',
        re.DOTALL
    )
    def fix_conn_row(m):
        row = m.group(2)
        # Replace LAST empty <td></td> (the Selected? column is last)
        empties = [(mo.start(), mo.end()) for mo in re.finditer(r'<td[^>]*>\s*</td>', row)]
        if empties:
            last_start, last_end = empties[-1]
            row = row[:last_start] + "<td>" + TL_CHECKBOX + "</td>" + row[last_end:]
        return m.group(1) + row + m.group(3)

    body, conn_count = conn_row_pat.subn(fix_conn_row, body)
    changes.append(f"Section 8h CONN Selected? → checkbox ({conn_count} rows)")

    # ── Section 16 LLD: Status column ────────────────────────────────────────
    lld_row_pat = re.compile(
        r'(<tr[^>]*>)(.*?(?:Component Spec|API Contract|Schema|IAM|NFR Control|Monitoring|DR \/ Backup).*?)(</tr>)',
        re.DOTALL
    )
    def fix_lld_row(m):
        row = m.group(2)
        row = re.sub(
            r'(<td[^>]*>)\s*Draft\s*(</td>)',
            lambda mm: mm.group(1) + TL_LLD_STATUS + mm.group(2),
            row
        )
        return m.group(1) + row + m.group(3)

    body, lld_count = lld_row_pat.subn(fix_lld_row, body)
    changes.append(f"Section 16 LLD status → task-list ({lld_count} rows)")

    return body, changes


def main() -> None:
    if not all([BASE_URL, USER_EMAIL, API_TOKEN]):
        print("ERROR: Missing Confluence credentials in .env")
        sys.exit(1)

    print(f"Fetching page {PAGE_ID} …")
    page  = fetch_page(get_session())
    title = page["title"]
    ver   = page["version"]["number"]
    body  = page["body"]["storage"]["value"]

    print(f"  Title   : {title}")
    print(f"  Version : {ver}")
    print(f"  Size    : {len(body):,} chars")

    new_body, changes = patch_body(body)

    print("\nChanges to apply:")
    for c in changes:
        print(f"  ✔ {c}")

    if new_body == body:
        print("\nNo changes needed — page already has interactive checkboxes.")
        return

    print(f"\nSize after patch: {len(new_body):,} chars (delta: +{len(new_body)-len(body):,})")
    print("Pushing update to Confluence …")
    result = update_page(get_session(), ver, title, new_body)
    new_ver = result["version"]["number"]
    print(f"\n✅  Done — page updated to version {new_ver}")
    print(f"   {BASE_URL}/spaces/CDA/pages/{PAGE_ID}")


if __name__ == "__main__":
    main()
