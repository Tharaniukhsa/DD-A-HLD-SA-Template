"""
confluence_patch_questionnaire_connectivity.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adds Section 12 (Connectivity Options) to the live Data Solution Architecture
Questionnaire page, and renumbers the old Section 12 to 13 and 13 to 14.
Idempotent — safe to re-run.
"""

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

# Live questionnaire page ID
PAGE_ID = "521438060"

SINGLE_YES = (
    '<ac:task-list><ac:task><ac:task-status>incomplete</ac:task-status>'
    '<ac:task-body>Yes</ac:task-body></ac:task></ac:task-list>'
)

CONN_SECTION_HTML = f"""
<hr />

<h2>12. Connectivity Options</h2>

<p><em>Select the UKHSA-approved network connectivity option(s) required for this workload. These must also be documented in Section 11 (Architecture Connections) and Section 13b (Network Segmentation) of the main HLD page. Source: UKHSA Cloud Strategy &amp; Approved Patterns v1.2 / UKHSA-INF-02 / ADR-010.</em></p>

<h3>12.1 On-Premises ↔ Cloud</h3>
<table>
  <thead><tr><th>ID</th><th>Name</th><th>From → To</th><th>When to Use</th><th>Selected?</th><th>Notes (circuit ID, bandwidth, DR pair)</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>CONN-01</strong></td><td>AWS Direct Connect</td><td>On-Prem DC / OCP → AWS</td>
      <td>Primary production path; consistent bandwidth; OFFICIAL-SENSITIVE data</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-02</strong></td><td>AWS Site-to-Site VPN</td><td>On-Prem DC / OCP → AWS</td>
      <td>Dev/test or Direct Connect warm-standby failover only</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-03</strong></td><td>Azure ExpressRoute</td><td>On-Prem DC / OCP → Azure</td>
      <td>Primary production path to Azure; high-volume; OFFICIAL-SENSITIVE data</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-04</strong></td><td>Azure VPN Gateway (S2S)</td><td>On-Prem DC / OCP → Azure</td>
      <td>Dev/test or ExpressRoute warm-standby failover only</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-17</strong></td><td>OpenShift → AWS via PrivateLink</td><td>OpenShift (OCP) → AWS</td>
      <td>OCP workloads consuming AWS services without traversing the internet</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-18</strong></td><td>OpenShift → Azure via ExpressRoute</td><td>OpenShift (OCP) → Azure</td>
      <td>OCP workloads consuming Azure services; uses shared ExpressRoute circuit</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
  </tbody>
</table>

<h3>12.2 Cloud ↔ Cloud (AWS ↔ Azure)</h3>
<table>
  <thead><tr><th>ID</th><th>Name</th><th>From → To</th><th>When to Use</th><th>Selected?</th><th>Notes</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>CONN-05</strong></td><td>Equinix / Megaport Fabric</td><td>AWS → Azure</td>
      <td>Production multi-cloud; private backbone; avoid internet cross-cloud traffic</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-06</strong></td><td>AWS ↔ Azure Internet VPN (Interim)</td><td>AWS ↔ Azure</td>
      <td>Dev/test or interim only — must declare migration date to CONN-05</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
  </tbody>
</table>

<h3>12.3 Within AWS (Intra-Cloud Routing)</h3>
<table>
  <thead><tr><th>ID</th><th>Name</th><th>When to Use</th><th>Selected?</th><th>Notes</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>CONN-07</strong></td><td>AWS Transit Gateway</td>
      <td>Multi-VPC / multi-account centralised routing</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-08</strong></td><td>AWS VPC Peering</td>
      <td>Low-traffic, same-region VPC-to-VPC (prefer Transit Gateway for scale)</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-09</strong></td><td>AWS PrivateLink (VPC Endpoints)</td>
      <td>Private access to AWS services or partner services without NAT/IGW</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
  </tbody>
</table>

<h3>12.4 Within Azure (Intra-Cloud Routing)</h3>
<table>
  <thead><tr><th>ID</th><th>Name</th><th>When to Use</th><th>Selected?</th><th>Notes</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>CONN-10</strong></td><td>Azure VNet Peering</td>
      <td>Low-latency VNet-to-VNet within same region or cross-region</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-11</strong></td><td>Azure Private Endpoint</td>
      <td>Private access to PaaS services (Storage, SQL, Key Vault) without public IP</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-12</strong></td><td>Azure Virtual WAN</td>
      <td>Hub-and-spoke at scale; replaces multiple VNet peerings across regions</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
  </tbody>
</table>

<h3>12.5 Public-Facing / External Ingress</h3>
<table>
  <thead><tr><th>ID</th><th>Name</th><th>When to Use</th><th>Selected?</th><th>Notes (public hostname, TPS estimate)</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>CONN-13</strong></td><td>Internet Gateway + WAF + CloudFront</td>
      <td>Public-facing AWS workloads; CDN + edge WAF required</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-14</strong></td><td>Azure Front Door + WAF</td>
      <td>Public-facing Azure workloads; global load balancing + WAF</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
  </tbody>
</table>

<h3>12.6 Zero-Trust End-User Access</h3>
<table>
  <thead><tr><th>ID</th><th>Name</th><th>When to Use</th><th>Selected?</th><th>Notes (ZPA app segment or ZIA policy)</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>CONN-15</strong></td><td>zScaler ZPA (Zero Trust App Access)</td>
      <td>End-user access to internal cloud apps without VPN; replaces split-tunnel</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
    <tr>
      <td><strong>CONN-16</strong></td><td>zScaler ZIA (Secure Internet Egress)</td>
      <td>Controlled internet egress from cloud workloads; DLP + threat inspection</td>
      <td>{SINGLE_YES}</td><td></td>
    </tr>
  </tbody>
</table>
"""


def patch_body(body: str) -> tuple[str, list[str]]:
    changes = []

    # Idempotency guard
    if "CONN-01" in body and "12. Connectivity Options" in body:
        return body, ["Connectivity section already present — nothing to do"]

    # Find the old "12. Auto-Generated Diagrams" heading and insert before it
    # Handle both plain <h2> and <h2 ...> variants, with varying numbering
    target_pat = re.compile(
        r'(<hr\s*/>[\s\S]*?)'   # <hr/> before section 12
        r'(<h2[^>]*>)'           # open <h2>
        r'(12\.|13\.)'           # "12." or "13." (already renumbered?)
        r'([^<]*Auto-Generated[^<]*</h2>)',
        re.DOTALL,
    )
    m = target_pat.search(body)
    if not m:
        # fallback: search for just the heading
        alt = re.search(r'(<h2[^>]*>)\s*1[23]\.\s*Auto-Generated', body, re.DOTALL)
        if not alt:
            return body, ["ERROR: Could not locate Auto-Generated Diagrams section to insert before"]
        insert_pos = alt.start()
    else:
        insert_pos = m.start(2)  # start of the <h2> tag

    # Insert connectivity section before the auto-diagrams heading
    body = body[:insert_pos] + CONN_SECTION_HTML + "\n" + body[insert_pos:]
    changes.append("Added Section 12 (Connectivity Options) with 18 CONN options")

    # Renumber "12. Auto-Generated" → "13." and "13. Related" → "14."
    body = re.sub(r'(<h2[^>]*>)\s*12\.(\s*Auto-Generated)', r'\g<1>13.\2', body, count=1)
    body = re.sub(r'(<h2[^>]*>)\s*13\.(\s*Related)', r'\g<1>14.\2', body, count=1)
    changes.append("Renumbered Auto-Generated Diagrams → 13, Related Documents → 14")

    return body, changes


def get_page(session, auth):
    url = f"{BASE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"
    r = session.get(url, auth=auth, verify=TLS_VERIFY)
    r.raise_for_status()
    data = r.json()
    return data["body"]["storage"]["value"], data["version"]["number"], data["title"]


def push_page(session, auth, body, version, title):
    url = f"{BASE_URL}/rest/api/content/{PAGE_ID}"
    payload = {
        "version": {"number": version + 1},
        "title": title,
        "type": "page",
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    r = session.put(url, auth=auth, json=payload, verify=TLS_VERIFY)
    r.raise_for_status()
    return r.json()["version"]["number"]


def main():
    if not all([BASE_URL, USER_EMAIL, API_TOKEN]):
        sys.exit("Missing CONFLUENCE_BASE_URL / USER_EMAIL / API_TOKEN in .env")

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    auth = HTTPBasicAuth(USER_EMAIL, API_TOKEN)

    print(f"Fetching questionnaire page {PAGE_ID} …")
    body, version, title = get_page(session, auth)
    print(f"  Title   : {title}")
    print(f"  Version : {version}")
    print(f"  Size    : {len(body):,} chars\n")

    new_body, changes = patch_body(body)

    print("Changes:")
    for c in changes:
        print(f"  ✔ {c}")

    if new_body == body:
        print("\nNo changes needed.")
        return

    print(f"\nSize after patch: {len(new_body):,} chars (delta: {len(new_body)-len(body):+,})")
    print("Pushing update to Confluence …")
    new_ver = push_page(session, auth, new_body, version, title)
    print(f"\n✅  Done — questionnaire updated to version {new_ver}")
    print(f"   {BASE_URL}/spaces/CDA/pages/{PAGE_ID}")


if __name__ == "__main__":
    main()
