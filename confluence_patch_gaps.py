"""
confluence_patch_gaps.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Targeted patches for the 4 identified content gaps on the live HLD page
(ID 520783944, version 134).  Safe to re-run — each patch checks first.

Gaps:
  1. Section 1 — missing "Architecture Tier" row
  2. Section 7 — missing explicit "Selected Option" row + Decision Rationale box
  3. Section 20 — missing Connectivity / ZPA / OCP acronyms sub-table
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

# ─── Patch 1 content ─────────────────────────────────────────────────────────
# New row for Section 1 table — inserts after "Target Cloud Platform" row

ROW_ARCH_TIER = """\
<tr><td>Architecture Tier</td><td>EDAP Tier 1 (Strategic Platform) / Tier 2 (Managed Integration) / Tier 3 (Project Workload) &mdash; select one</td></tr>"""

# ─── Patch 2 content ─────────────────────────────────────────────────────────
# New row + decision rationale block for Section 7 options table

ROW_SELECTED_OPTION = """\
<tr><td><strong>Selected Option</strong></td><td><em>State which option is recommended (e.g. Option A)</em></td><td><em>Summary of selected approach</em></td><td></td><td></td><td></td><td><strong>Selected</strong></td></tr>"""

DECISION_RATIONALE_BLOCK = """\
<h4 style="color:#B45309; margin-top:16px;">Architecture Decision Rationale</h4>
<table>
  <tbody>
    <tr><th style="width:200px">Selected Option</th><td><em>State the option chosen (e.g. Option A &mdash; SFTP to S3 plus Lambda validation)</em></td></tr>
    <tr><th>Decision Date</th><td><em>Date architecture decision was agreed</em></td></tr>
    <tr><th>Decision Owner</th><td><em>Named architect or architecture board</em></td></tr>
    <tr><th>Rationale</th><td><em>2&ndash;4 sentences explaining why this option was selected over the alternatives. Reference the evaluation criteria scores from 7a.</em></td></tr>
    <tr><th>Key Assumptions</th><td><em>List the main assumptions this decision depends on (e.g. source system can support SFTP push, DX circuit available by Q2)</em></td></tr>
    <tr><th>Risks / Caveats</th><td><em>Any conditions or constraints that could invalidate this decision</em></td></tr>
    <tr><th>Review Trigger</th><td><em>State the condition that would cause this decision to be revisited (e.g. if source system adds REST API, migrate from SFTP to API-first)</em></td></tr>
  </tbody>
</table>"""

# ─── Patch 3 content ─────────────────────────────────────────────────────────
# New sub-section in Section 20 for Connectivity / ZPA / OCP terms

SECTION_20_CONN_ACRONYMS = """\
<h3 local-id="acronyms-connectivity">Connectivity &amp; Zero Trust</h3>
<table data-layout="default">
  <thead><tr><th>Acronym</th><th>Full Form</th><th>Description</th></tr></thead>
  <tbody>
    <tr><td>DX</td><td>AWS Direct Connect</td><td>Dedicated private network connection from UKHSA on-premises data centres to AWS &mdash; primary hybrid path (UKHSA-INF-02).</td></tr>
    <tr><td>ER</td><td>Azure ExpressRoute</td><td>Dedicated private circuit from UKHSA on-premises to Azure &mdash; primary hybrid path for Azure workloads.</td></tr>
    <tr><td>TGW</td><td>AWS Transit Gateway</td><td>Central routing hub connecting multiple AWS VPCs and on-premises networks. Mandatory for all multi-VPC UKHSA AWS deployments.</td></tr>
    <tr><td>VWAN</td><td>Azure Virtual WAN</td><td>Azure hub-and-spoke networking service. Mandatory for all multi-VNet UKHSA Azure deployments.</td></tr>
    <tr><td>PE</td><td>Azure Private Endpoint / AWS PrivateLink</td><td>Private IP connectivity to PaaS services within VNet/VPC without traversing the public internet. Mandatory for all PaaS in production.</td></tr>
    <tr><td>WAF</td><td>Web Application Firewall</td><td>Managed Layer-7 filtering for public-facing HTTP/S endpoints. Mandatory for all internet-facing UKHSA workloads (SEC-APS-03).</td></tr>
    <tr><td>ZPA</td><td>Zscaler Private Access</td><td>Zero Trust Network Access (ZTNA) solution for end-user access to private applications. Replaces VPN for user access (ADR-010 target state).</td></tr>
    <tr><td>ZIA</td><td>Zscaler Internet Access</td><td>Cloud-delivered secure web gateway / internet egress. Target state to replace on-premises proxy backhaul.</td></tr>
    <tr><td>ZTNA</td><td>Zero Trust Network Access</td><td>Architecture model where access is verified per-request based on identity, device posture, and context rather than network location.</td></tr>
    <tr><td>MPLS</td><td>Multiprotocol Label Switching</td><td>UKHSA WAN technology (Virgin Media MPLS) connecting on-premises sites and data centres.</td></tr>
    <tr><td>CONN-XX</td><td>Connectivity Option reference IDs</td><td>UKHSA approved connectivity pattern identifiers (CONN-01 to CONN-18). See Section 8h of this document for the full reference table.</td></tr>
    <tr><td>OCP</td><td>OpenShift Container Platform</td><td>Red Hat on-premises Kubernetes platform. Fourth internal UKHSA environment alongside On-Prem DC, AWS (HALO), and Azure (PHECloud). Defined in UKHSA-INF-07.</td></tr>
    <tr><td>SDN</td><td>Software-Defined Networking</td><td>Network virtualisation approach where control plane is separated from data plane, enabling programmable network configuration.</td></tr>
    <tr><td>BGP</td><td>Border Gateway Protocol</td><td>Routing protocol used between on-premises routers and AWS Direct Connect / Azure ExpressRoute for dynamic route advertisement.</td></tr>
  </tbody>
</table>"""


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

    # ── PATCH 0: Fix Architecture Tier description — remove EDAP-specific label ─
    old_tier = (
        "EDAP Tier 1 (Strategic Platform) / Tier 2 (Managed Integration) / "
        "Tier 3 (Project Workload) &mdash; select one"
    )
    new_tier = (
        "<strong>Tier 1</strong> &mdash; Strategic Platform "
        "(enterprise-wide shared service, e.g. EDAP, APIM, Sentinel &mdash; any cloud) / "
        "<strong>Tier 2</strong> &mdash; Managed Integration "
        "(workload that feeds or consumes a Tier 1 platform &mdash; AWS, Azure, OpenShift, or hybrid) / "
        "<strong>Tier 3</strong> &mdash; Project Workload "
        "(standalone solution deployed into an approved UKHSA landing zone: "
        "AWS HALO, Azure PHECloud, On-Premises OpenShift, or multi-cloud) &mdash; select one"
    )
    if old_tier in body:
        body = body.replace(old_tier, new_tier, 1)
        changes.append("Section 1: Fixed Architecture Tier — removed EDAP-specific label, made platform-agnostic")
    else:
        changes.append("Section 1: Architecture Tier text already updated — skipped")

    # ── PATCH 1: Add Architecture Tier row to Section 1 table ───────────────
    if "Architecture Tier" not in body:
        # Insert after the "Target Cloud Platform" row
        target_row = re.search(
            r'(<tr[^>]*>.*?Target Cloud Platform.*?</tr>)',
            body, re.DOTALL
        )
        if target_row:
            insert_at = target_row.end()
            body = body[:insert_at] + "\n" + ROW_ARCH_TIER + body[insert_at:]
            changes.append("Section 1: Added 'Architecture Tier' row after 'Target Cloud Platform'")
        else:
            # Fallback: insert before the closing </tbody> of Section 1's table
            sec1_end = re.search(
                r'(1\. Solution Overview.*?</tbody>)',
                body, re.DOTALL
            )
            if sec1_end:
                pos = sec1_end.end() - len("</tbody>")
                body = body[:pos] + "\n" + ROW_ARCH_TIER + "\n" + body[pos:]
                changes.append("Section 1: Added 'Architecture Tier' row (fallback position)")
            else:
                changes.append("WARNING: Section 1 table not found — Architecture Tier not added")
    else:
        changes.append("Section 1: Architecture Tier already present — skipped")

    # ── PATCH 2: Add Selected Option row + Decision Rationale to Section 7 ──
    if not re.search(r'Selected Option|Recommended Option', body, re.IGNORECASE):
        # Find the closing </tbody></table> of the Section 7 options comparison table
        # Anchor: section 7 heading → first table's </table>
        sec7_m = re.search(
            r'(<h2[^>]*>7\.[^<]*</h2>.*?)(</table>)',
            body, re.DOTALL
        )
        if sec7_m:
            # Insert the Selected Option row before the first </table> in section 7
            insert_at = sec7_m.start(2)
            selected_row_wrapped = "\n<tbody>" + ROW_SELECTED_OPTION + "</tbody>"
            body = body[:insert_at] + selected_row_wrapped + body[insert_at:]
            changes.append("Section 7: Added 'Selected Option' row to options table")

            # Now add the decision rationale block after the 7a evaluation table
            # Anchor: look for the 7a heading
            sec7a_m = re.search(
                r'(<h3[^>]*>7a\.[^<]*</h3>.*?)(</table>)',
                body, re.DOTALL
            )
            if sec7a_m:
                insert_at2 = sec7a_m.end()
                body = body[:insert_at2] + "\n\n" + DECISION_RATIONALE_BLOCK + "\n\n" + body[insert_at2:]
                changes.append("Section 7: Added 'Decision Rationale' block after 7a table")
            else:
                changes.append("WARNING: Section 7a not found — Decision Rationale block not added")
        else:
            changes.append("WARNING: Section 7 options table not found")
    else:
        changes.append("Section 7: Selected Option already present — skipped")

    # ── PATCH 3: Add Connectivity & Zero Trust acronyms sub-section to Sec 20 ─
    if "CONN-XX" not in body and "Connectivity &amp; Zero Trust" not in body:
        # Find the last </table> in Section 20 (before end of body or next h2)
        sec20_m = re.search(r'<h2[^>]*>20\. Acronyms', body, re.DOTALL)
        if sec20_m:
            sec20_start = sec20_m.start()
            # Find the last </table> within section 20 (end of doc)
            sec20_body = body[sec20_start:]
            last_table_end = None
            for m in re.finditer(r'</table>', sec20_body):
                last_table_end = m.end()
            if last_table_end is not None:
                insert_at3 = sec20_start + last_table_end
                body = body[:insert_at3] + "\n\n" + SECTION_20_CONN_ACRONYMS + body[insert_at3:]
                changes.append("Section 20: Added 'Connectivity & Zero Trust' acronyms sub-table")
            else:
                changes.append("WARNING: Could not find table end in Section 20")
        else:
            changes.append("WARNING: Section 20 heading not found")
    else:
        changes.append("Section 20: Connectivity acronyms already present — skipped")

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
        symbol = "✔" if not c.startswith("WARNING") else "⚠"
        print(f"  {symbol} {c}")

    if new_body == body:
        print("\nNo changes needed — page is already up to date.")
        return

    print(f"\nSize after patch: {len(new_body):,} chars (delta: +{len(new_body)-len(body):,})")
    print("Pushing update to Confluence …")
    result = update_page(get_session(), ver, title, new_body)
    new_ver = result["version"]["number"]
    print(f"\n✅  Done — page updated to version {new_ver}")
    print(f"   {BASE_URL}/spaces/CDA/pages/{PAGE_ID}")


if __name__ == "__main__":
    main()
