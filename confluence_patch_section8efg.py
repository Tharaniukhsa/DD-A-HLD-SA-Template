"""
confluence_patch_section8efg.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Surgically patches the live HLD page (ID 520783944) to:
  - Replace the existing Section 8e block (Infrastructure & Platform Patterns)
    with the updated version including UKHSA-INF-07 (OpenShift)
  - Insert Section 8f (Target State Architecture – Networking & Identity)
    if it is missing
  - Insert Section 8g (Connectivity Options Reference, 18 CONN options)
    if it is missing

Safe: reads the current page body, applies targeted string replacements,
then PUTs the result back. Does NOT touch any other section.
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

# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()
BASE_URL   = os.getenv("CONFLUENCE_BASE_URL", "").rstrip("/")
USER_EMAIL = os.getenv("CONFLUENCE_USER_EMAIL", "")
API_TOKEN  = os.getenv("CONFLUENCE_API_TOKEN", "")
TLS_VERIFY = os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").lower() != "true"
PAGE_ID    = "520783944"
# ─────────────────────────────────────────────────────────────────────────────

# ─── New HTML blocks ──────────────────────────────────────────────────────────

SECTION_8E = """\
  <h3 id="section8e" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8e. Infrastructure &amp; Platform Patterns</h3>
  <p><em>UKHSA-approved infrastructure patterns. INF-01 (Landing Zone) and INF-05 (Federated Identity) are mandatory for all cloud workloads.</em></p>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected? (Y/N)</th><th>Notes / Justification</th></tr></thead>
  <tbody>
    <tr><td>UKHSA-INF-01</td><td>UKHSA Cloud Landing Zone</td><td>Y</td><td><strong>Mandatory</strong> &mdash; all cloud workloads must deploy into an approved UKHSA LZ (AWS or Azure)</td></tr>
    <tr><td>UKHSA-INF-02</td><td>Hybrid Cloud Connectivity</td><td></td><td>Secure AWS Direct Connect / Azure ExpressRoute with IPsec VPN backup</td></tr>
    <tr><td>UKHSA-INF-03</td><td>Multi-Cloud Account Governance</td><td></td><td>AWS Organizations / Azure Management Groups with centralised policy enforcement</td></tr>
    <tr><td>UKHSA-INF-04</td><td>Split-Horizon DNS</td><td></td><td>Route 53 as strategic DNS resolver with conditional forwarding to on-prem</td></tr>
    <tr><td>UKHSA-INF-05</td><td>Federated Identity (Entra ID Golden Source)</td><td>Y</td><td><strong>Mandatory</strong> &mdash; Microsoft Entra ID as single IdP federated to AWS, SaaS, and all workloads</td></tr>
    <tr><td>UKHSA-INF-06</td><td>Approved Platform Portfolio</td><td></td><td>Use UKHSA-approved platforms: EDAP (analytics), APIM (APIs), Sentinel (SIEM)</td></tr>
    <tr><td>UKHSA-INF-07</td><td>OpenShift Container Platform (On-Premises)</td><td></td><td>UKHSA on-premises Kubernetes via Red Hat OpenShift; fourth internal environment alongside AWS and Azure</td></tr>
  </tbody>
</table>"""

SECTION_8F = """\
  <h3 id="section8f" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8f. Target State Architecture &ndash; Networking &amp; Identity</h3>
  <p><em>UKHSA TSA patterns define the strategic target networking and identity architecture all new solutions should align to.</em></p>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected? (Y/N)</th><th>Notes / Justification</th></tr></thead>
  <tbody>
    <tr><td>TSA-NET-01</td><td>Zero-Trust Network Access (ZTNA)</td><td></td><td>Replace implicit trust with identity-verified, device-checked, context-aware access</td></tr>
    <tr><td>TSA-NET-02</td><td>Centralised Ingress (ALB + WAF)</td><td></td><td>Single WAF-protected ingress point for all public-facing workloads</td></tr>
    <tr><td>TSA-IDN-01</td><td>Passwordless Authentication</td><td></td><td>FIDO2 / Windows Hello / Certificate-based auth via Entra ID</td></tr>
    <tr><td>TSA-IDN-02</td><td>Privileged Identity Management (PIM)</td><td></td><td>Just-in-time, time-limited elevation of privileged roles via Entra PIM</td></tr>
  </tbody>
</table>"""

SECTION_8G = """\
  <h3 id="section8g" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8g. Connectivity Options Reference</h3>
  <p><em>
    All UKHSA-approved network connectivity options for the four internal environments (On-Premises DC, OpenShift, AWS, Azure)
    and external-facing ingress. Select the option(s) applicable to this project and document the connection type in
    Section 11 (Architecture Connections) and Section 13b (Network Segmentation Inputs).
    Source: <strong>UKHSA Cloud Strategy &amp; Approved Patterns v1.2</strong> + UKHSA-INF-02 / ADR-010.
  </em></p>

  <p><strong>Availability key:</strong>
    <ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro>
    &nbsp;Live in production at UKHSA &nbsp;|&nbsp;
    <ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro>
    &nbsp;Target state &mdash; approved but not yet fully deployed &nbsp;|&nbsp;
    <ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Red</ac:parameter><ac:parameter ac:name="title">Not Available</ac:parameter></ac:structured-macro>
    &nbsp;Not approved for UKHSA use
  </p>

  <h4 style="color:#374151; margin-top:16px;">Category 1 &mdash; On-Premises &harr; Cloud</h4>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>From</th><th>To</th><th>Use When</th><th>Bandwidth</th><th>Indicative Cost (&pound;/mo)</th><th>Availability</th><th>Selected?</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>CONN-01</strong></td><td>AWS Direct Connect</td><td>On-Prem DC / OCP</td><td>AWS</td>
        <td>Primary production path; consistent bandwidth; OFFICIAL-SENSITIVE data</td>
        <td>1&ndash;10 Gbps dedicated</td><td>&pound;140&ndash;280 port + &pound;0.02/GB out</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-02</strong></td><td>AWS Site-to-Site VPN</td><td>On-Prem DC / OCP / Remote Site</td><td>AWS</td>
        <td>Dev/test or DX warm-standby failover only &mdash; not for production primary</td>
        <td>Up to 2.5 Gbps (2 tunnels)</td><td>&pound;30&ndash;50 + &pound;0.05/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-03</strong></td><td>Azure ExpressRoute</td><td>On-Prem DC / OCP</td><td>Azure</td>
        <td>Primary production path to Azure; high-volume; OFFICIAL-SENSITIVE data</td>
        <td>50 Mbps&ndash;10 Gbps</td><td>&pound;200&ndash;400 circuit + &pound;0.02/GB out</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-04</strong></td><td>Azure VPN Gateway (S2S)</td><td>On-Prem DC / OCP / Remote Site</td><td>Azure</td>
        <td>Dev/test or ExpressRoute warm-standby failover only</td>
        <td>Up to 10 Gbps (VpnGw5)</td><td>&pound;160&ndash;420 gateway + &pound;0.05/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-17</strong></td><td>OpenShift &rarr; AWS via PrivateLink</td><td>OpenShift (OCP)</td><td>AWS</td>
        <td>OCP pods calling AWS services (S3, SQS, RDS) without public internet</td>
        <td>Shared with DX circuit</td><td>&pound;6&ndash;10/endpoint + DX transfer</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-18</strong></td><td>OpenShift &rarr; Azure via ExpressRoute</td><td>OpenShift (OCP)</td><td>Azure</td>
        <td>OCP pods accessing Azure Key Vault, Storage, Service Bus over ER private peering</td>
        <td>Shared with ER circuit</td><td>Marginal + &pound;6&ndash;8/endpoint</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <h4 style="color:#374151; margin-top:16px;">Category 2 &mdash; Cloud-to-Cloud (AWS &harr; Azure)</h4>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>From</th><th>To</th><th>Use When</th><th>Bandwidth</th><th>Indicative Cost (&pound;/mo)</th><th>Availability</th><th>Selected?</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>CONN-05</strong></td><td>Equinix / Megaport Fabric</td><td>AWS</td><td>Azure</td>
        <td>&#11088; <strong>Target state</strong> &mdash; large-volume, low-latency, OFFICIAL-SENSITIVE cross-cloud</td>
        <td>1&ndash;10 Gbps private fabric</td><td>&pound;300&ndash;600 fabric port + &pound;0.07/GB AWS egress</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-06</strong></td><td>AWS &harr; Azure Internet VPN (Interim)</td><td>AWS</td><td>Azure</td>
        <td>Dev/test or interim only &mdash; must declare migration date to CONN-05</td>
        <td>Up to 1.25 Gbps/tunnel</td><td>&pound;30&ndash;50 VPN + &pound;0.07/GB AWS + &pound;0.05/GB Azure egress</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <h4 style="color:#374151; margin-top:16px;">Category 3 &mdash; Internal Cloud (within AWS / within Azure)</h4>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Platform</th><th>Use When</th><th>Indicative Cost (&pound;/mo)</th><th>Availability</th><th>Selected?</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>CONN-07</strong></td><td>AWS Transit Gateway</td><td>AWS</td>
        <td>Multi-VPC routing hub &mdash; <strong>mandatory</strong> for all multi-VPC UKHSA AWS deployments</td>
        <td>&pound;30&ndash;80 attachments + &pound;0.02/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-08</strong></td><td>AWS VPC Peering</td><td>AWS</td>
        <td>Simple two-VPC only; use TGW for 3+ VPCs</td>
        <td>&pound;0.01&ndash;0.02/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-09</strong></td><td>AWS PrivateLink (VPC Endpoints)</td><td>AWS</td>
        <td><strong>Mandatory</strong> for all AWS PaaS API calls from private subnets</td>
        <td>&pound;6&ndash;10/endpoint + &pound;0.01/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-10</strong></td><td>Azure VNet Peering</td><td>Azure</td>
        <td>Simple two-VNet only; use Virtual WAN for 3+ VNets</td>
        <td>&pound;0.01&ndash;0.02/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-11</strong></td><td>Azure Private Endpoint</td><td>Azure</td>
        <td><strong>Mandatory</strong> for all Azure PaaS in production; disable public endpoint</td>
        <td>&pound;6&ndash;8/endpoint + &pound;0.01/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-12</strong></td><td>Azure Virtual WAN</td><td>Azure</td>
        <td>Multi-VNet routing hub &mdash; <strong>mandatory</strong> for all multi-VNet UKHSA Azure deployments</td>
        <td>&pound;200&ndash;400 hub + &pound;0.02/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <h4 style="color:#374151; margin-top:16px;">Category 4 &mdash; Internet-Facing Ingress</h4>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Platform</th><th>Use When</th><th>Indicative Cost (&pound;/mo)</th><th>Availability</th><th>Selected?</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>CONN-13</strong></td><td>Internet Gateway + WAF + CloudFront</td><td>AWS</td>
        <td>Any public-facing AWS workload &mdash; WAF is <strong>mandatory</strong> (SEC-APS-03)</td>
        <td>&pound;20&ndash;100 (WAF rules + CloudFront)</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-14</strong></td><td>Azure Front Door + WAF</td><td>Azure</td>
        <td>Any public-facing Azure workload &mdash; WAF is <strong>mandatory</strong></td>
        <td>&pound;50&ndash;200</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <h4 style="color:#374151; margin-top:16px;">Category 5 &mdash; Zero Trust / SASE (End-User Access)</h4>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Use When</th><th>Indicative Cost</th><th>Availability</th><th>Selected?</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>CONN-15</strong></td><td>zScaler ZPA (Zero Trust App Access)</td>
        <td>All remote/end-user access to private applications &mdash; <strong>replaces VPN</strong> (ADR-010 target state)</td>
        <td>Per-user licence (contact CCoE)</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-16</strong></td><td>zScaler ZIA (Secure Internet Egress)</td>
        <td>All outbound internet from UKHSA devices and cloud workloads &mdash; replaces on-prem proxy</td>
        <td>Per-user licence (contact CCoE)</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <ac:structured-macro ac:name="info">
    <ac:parameter ac:name="title">Where to find full details</ac:parameter>
    <ac:rich-text-body>
      <p>Full technical details for each option (best practices, when not to use, redundancy approach) are stored in
      <strong>ukhsa_patterns_knowledge_base.py &rarr; CONNECTIVITY_OPTIONS</strong> in the architecture automation repository.
      See the <strong>CONNECTIVITY_SELECTION_GUIDE</strong> dict for the recommended primary/secondary option per environment pair.</p>
    </ac:rich-text-body>
  </ac:structured-macro>"""

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
        print(f"ERROR {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def patch_body(body: str) -> tuple[str, list[str]]:
    """Apply targeted patches. Returns (new_body, list_of_changes_made).

    Live page structure (uses local-id, not id attributes):
      8a Ingestion | 8b Processing | 8c Storage | 8d Governance
      8e Secure by Design Coverage Matrix   ← already on live page
      ── MISSING ──  8f Infrastructure & Platform Patterns
      ── MISSING ──  8g Target State Architecture – Networking & Identity
      ── MISSING ──  8h Connectivity Options Reference

    Strategy:
      • Guard against double-insertion by checking heading text.
      • If any of our new sections already exist (by heading text) skip them.
      • Otherwise find the end of the existing 8e block (by matching its
        heading text) and insert our new sections there.
    """
    changes: list[str] = []

    # Sentinel texts to detect whether sections already exist on the live page
    HAS_8F_INFRA   = "8f. Infrastructure" in body or "Infrastructure &amp; Platform Patterns" in body and "UKHSA-INF-07" in body
    HAS_8G_TSA     = "8g. Target State" in body or ("Target State" in body and "TSA-NET-01" in body)
    HAS_8H_CONN    = "8h. Connectivity Options" in body or ("Connectivity Options Reference" in body and "CONN-01" in body)

    if HAS_8F_INFRA and HAS_8G_TSA and HAS_8H_CONN:
        return body, ["All three sections already present — nothing to do"]

    # ── Find the insertion point: end of the 8e "Secure by Design" block ────
    # The live page heading is:  8e. Secure by Design Coverage Matrix
    # Followed by a <table>. We want to insert AFTER that table's </table>.
    # Pattern: match everything from the 8e heading up to (not including)
    # the next <h2 or <h3 heading.
    pat_8e_block = re.compile(
        r'(<h3[^>]*>8e\.[^<]*</h3>.*?</table>)',
        re.DOTALL,
    )
    m_8e = pat_8e_block.search(body)

    if not m_8e:
        # Fallback: try matching by the text content without number prefix
        pat_8e_block = re.compile(
            r'(<h3[^>]*>(?:8e\.)?[^<]*Secure by Design[^<]*</h3>.*?</table>)',
            re.DOTALL,
        )
        m_8e = pat_8e_block.search(body)

    if not m_8e:
        return body, ["ERROR: Could not find 8e (Secure by Design) block to anchor insertion point"]

    insert_pos = m_8e.end()

    # Build the block(s) to insert
    insert_html = ""

    if not HAS_8F_INFRA:
        insert_html += "\n\n" + SECTION_8E.replace(
            'id="section8e"', 'id="section8f-infra"'
        ).replace(
            ">8e. Infrastructure", ">8f. Infrastructure"
        )
        changes.append("8f (Infrastructure & Platform Patterns) inserted after 8e")

    if not HAS_8G_TSA:
        insert_html += "\n\n" + SECTION_8F.replace(
            'id="section8f"', 'id="section8g-tsa"'
        ).replace(
            ">8f. Target State", ">8g. Target State"
        )
        changes.append("8g (Target State Architecture) inserted")

    if not HAS_8H_CONN:
        insert_html += "\n\n" + SECTION_8G.replace(
            'id="section8g"', 'id="section8h-conn"'
        ).replace(
            ">8g. Connectivity Options", ">8h. Connectivity Options"
        )
        changes.append("8h (Connectivity Options Reference) inserted")

    body = body[:insert_pos] + insert_html + body[insert_pos:]
    return body, changes


def main() -> None:
    if not all([BASE_URL, USER_EMAIL, API_TOKEN]):
        print("ERROR: CONFLUENCE_BASE_URL / CONFLUENCE_USER_EMAIL / CONFLUENCE_API_TOKEN not set in .env")
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
        print("\nNo changes needed — page is already up to date.")
        return

    print(f"\nSize after patch: {len(new_body):,} chars")
    print("Pushing update to Confluence …")
    result = update_page(get_session(), ver, title, new_body)
    new_ver = result["version"]["number"]
    print(f"\n✅  Done — page updated to version {new_ver}")
    print(f"   {BASE_URL}/wiki/spaces/CDA/pages/{PAGE_ID}")


if __name__ == "__main__":
    main()
