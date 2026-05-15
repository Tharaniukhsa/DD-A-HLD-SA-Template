import html
import json
import os
import sys
import re
import xml.etree.ElementTree as ET
from io import BytesIO

import certifi
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from requests_negotiate_sspi import HttpNegotiateAuth

load_dotenv()

SECURE_BY_DESIGN_SAT_URL = "https://phecloud.sharepoint.com/:x:/r/sites/SecureByDesign/_layouts/15/Doc.aspx?sourcedoc=%7BDE70096D-47CA-4190-A8EB-710D5D15E178%7D&file=UKHSA%20Secure%20by%20Design%20-%20SAT%20-%20TEMPLATE%20v2.6.xlsx&action=default&mobileredirect=true"


def _make_request(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    """
    Make HTTP request with automatic auth fallback.
    Tries primary auth first (Bearer), then falls back to Basic if 403 received.
    """
    api_token = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    verify = kwargs.pop("verify", get_tls_verify())
    
    base_headers = dict(kwargs.pop("headers", {}) or {})

    # Try Bearer auth first if we have a token.
    if api_token:
      bearer_headers = dict(base_headers)
      bearer_headers["Authorization"] = f"Bearer {api_token}"
      try:
        resp = session.request(method, url, verify=verify, headers=bearer_headers, auth=None, **kwargs)
        if resp.status_code != 403:
          return resp
      except requests.RequestException:
        pass

    # Fallback to Basic auth if we have email + token.
    if user_email and api_token:
      resp = session.request(
        method,
        url,
        verify=verify,
        headers=base_headers,
        auth=HTTPBasicAuth(user_email, api_token),
        **kwargs,
      )
      return resp
    
    # Last resort: use session as-is
    return session.request(method, url, verify=verify, headers=base_headers, **kwargs)


def get_tls_verify():
    ca_bundle = (os.getenv("CONFLUENCE_CA_BUNDLE") or "").strip()
    if ca_bundle:
        if not os.path.exists(ca_bundle):
            raise ValueError(f"CONFLUENCE_CA_BUNDLE path does not exist: {ca_bundle}")
        return ca_bundle
    if os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").strip().lower() in {"1", "true", "yes"}:
        print("Warning: SSL verification is disabled. Use for temporary testing only.")
        return False
    return certifi.where()


def _accept_headers() -> dict:
    return {"Accept": "application/json"}


def _json_headers() -> dict:
    return {"Accept": "application/json", "Content-Type": "application/json"}


def find_page_by_title(session: requests.Session, base_url: str, space_key: str, title: str) -> dict:
    resp = _make_request(
        session, "GET",
        f"{base_url}/rest/api/content",
        params={"spaceKey": space_key, "title": title, "expand": "body.storage,version"},
        headers=_accept_headers(),
        verify=get_tls_verify(),
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        raise ValueError(f"Page not found: '{title}' in space '{space_key}'")
    return results[0]


def update_page_body(session: requests.Session, base_url: str, page_id: str, version_number: int, title: str, body_html: str) -> dict:
    payload = {
        "version": {"number": version_number + 1},
        "title": title,
        "type": "page",
        "body": {"storage": {"value": body_html, "representation": "storage"}},
    }
    resp = _make_request(
        session, "PUT",
        f"{base_url}/rest/api/content/{page_id}",
        data=json.dumps(payload),
        headers=_json_headers(),
        verify=get_tls_verify(),
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to update page: {resp.status_code} {resp.text}")
    return resp.json()


def upload_attachment(session: requests.Session, base_url: str, page_id: str, filename: str, content: bytes) -> dict:
    url = f"{base_url}/rest/api/content/{page_id}/child/attachment"

    check = _make_request(
        session, "GET",
        url,
        params={"filename": filename},
        headers=_accept_headers(),
        verify=get_tls_verify(),
        timeout=30,
    )
    existing = check.json().get("results", []) if check.status_code == 200 else []

    # Prepare file upload
    file_bytes = content if isinstance(content, bytes) else content.encode("utf-8")

    def _make_files_payload():
        return {"file": (filename, BytesIO(file_bytes), "application/octet-stream")}

    # Use direct session for file uploads (auth fallback handled via headers)
    api_token = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    verify = get_tls_verify()
    
    resp = None
    upload_headers = {"X-Atlassian-Token": "no-check"}
    upload_url = f"{url}/{existing[0]['id']}/data" if existing else url
    original_content_type = session.headers.pop("Content-Type", None)

    try:
      # Try Bearer auth first.
      if api_token:
        bearer_headers = dict(upload_headers)
        bearer_headers["Authorization"] = f"Bearer {api_token}"
        try:
          resp = session.post(
            upload_url,
            files=_make_files_payload(),
            headers=bearer_headers,
            auth=None,
            verify=verify,
            timeout=30,
          )
          if resp.status_code not in (200, 201, 403, 409):
            raise RuntimeError(f"Failed to upload attachment '{filename}': {resp.status_code} {resp.text}")
          if resp.status_code == 409:
            # Version conflict: refresh attachment ID and retry once.
            check2 = _make_request(session, "GET", url, params={"filename": filename},
                                   headers={"Accept": "application/json"}, verify=verify, timeout=30)
            existing2 = check2.json().get("results", []) if check2.status_code == 200 else []
            upload_url = f"{url}/{existing2[0]['id']}/data" if existing2 else url
            resp = session.post(upload_url, files=_make_files_payload(), headers=bearer_headers,
                                auth=None, verify=verify, timeout=30)
          if resp.status_code not in (200, 201, 403):
            raise RuntimeError(f"Failed to upload attachment '{filename}': {resp.status_code} {resp.text}")
          if resp.status_code != 403:
            return resp.json()
        except requests.RequestException:
          pass

      # Fallback to Basic auth.
      if user_email and api_token:
        resp = session.post(
          upload_url,
          files=_make_files_payload(),
          headers=upload_headers,
          auth=HTTPBasicAuth(user_email, api_token),
          verify=verify,
          timeout=30,
        )
        if resp.status_code not in (200, 201):
          raise RuntimeError(f"Failed to upload attachment '{filename}': {resp.status_code} {resp.text}")
        return resp.json()
    finally:
      if original_content_type is not None:
        session.headers["Content-Type"] = original_content_type
    
    raise RuntimeError(f"Failed to upload attachment '{filename}': No valid authentication")


def attachment_link(base_url: str, attachment: dict) -> str:
    download = attachment.get("_links", {}).get("download", "")
    if download.startswith("http"):
        return download
    return f"{base_url}{download}"


def page_link(base_url: str, page: dict) -> str:
  links = page.get("_links", {})
  webui = links.get("webui", "")
  if webui.startswith("http"):
    return webui
  page_base = links.get("base", base_url)
  return f"{page_base}{webui}"


def create_page(session: requests.Session, base_url: str, space_key: str, title: str, body_html: str, parent_page_id: str) -> dict:
  payload = {
    "type": "page",
    "title": title,
    "space": {"key": space_key},
    "ancestors": [{"id": parent_page_id}],
    "body": {"storage": {"value": body_html, "representation": "storage"}},
  }
  resp = _make_request(
    session, "POST",
    f"{base_url}/rest/api/content",
    data=json.dumps(payload),
    headers=_json_headers(),
    verify=get_tls_verify(),
    timeout=30,
  )
  if resp.status_code not in (200, 201):
    raise RuntimeError(f"Failed to create page '{title}': {resp.status_code} {resp.text}")
  return resp.json()


def upsert_child_page(session: requests.Session, base_url: str, space_key: str, parent_page_id: str, title: str, body_html: str) -> dict:
  try:
    existing = find_page_by_title(session, base_url, space_key, title)
  except ValueError:
    return create_page(session, base_url, space_key, title, body_html, parent_page_id)
  return update_page_body(session, base_url, existing["id"], existing["version"]["number"], existing["title"], body_html)


# PATTERNS PAGE FUNCTIONALITY REMOVED - No longer publishing patterns as separate page
def build_patterns_reference_html(source_download_link: str) -> str:
    """Retained for compatibility; patterns content is no longer published from this script."""
    _ = source_download_link
    return ""


def build_main_html(plan_link: str) -> str:  # noqa: C901
    return f"""
<h1 style="color: #003366; border-bottom: 4px solid #003366; padding-bottom: 10px;">High-level Design (HLD) Solution Architecture Template</h1>
<p><em>Single source of truth: complete this page during discovery workshops. The tables below drive automated diagram generation and Terraform delivery output.</em></p>

<ac:structured-macro ac:name="tip">
  <ac:parameter ac:name="title">⚡ Fast-Fill Guidance — Which Sections to Complete First</ac:parameter>
  <ac:rich-text-body>
    <p><strong>Use this guide to prioritise which sections to fill based on your project type:</strong></p>
    <table>
      <thead><tr><th>Project Type</th><th>Fill First</th><th>Mandatory Patterns (Section 8)</th><th>Skip / Later</th></tr></thead>
      <tbody>
        <tr>
          <td><strong>New data pipeline / analytics on AWS</strong><br/><em>e.g. disease surveillance, lab data ingestion</em></td>
          <td>Sections 1–6, then 9 (Context), 10 (Components), 11 (Connections), 13 (Data Flows)</td>
          <td>INF-01, INF-05, 3C, 6A, 6B, 6C, 7A, 7B, 8a (Backup)<br/>+ pick ingestion: 1B or 1C or 1D</td>
          <td>TSA-NET-02 unless public-facing; Section 17 (Cost) until option agreed</td>
        </tr>
        <tr>
          <td><strong>Public-facing API or web application</strong><br/><em>e.g. data portal, UKHSA public dashboard</em></td>
          <td>Sections 1–6, then 8 (Pattern Selection: TSA-NET-02, 6A–C), 10–11</td>
          <td>INF-01, INF-04, INF-05, TSA-NET-02 (ALB+WAF), 6A, 6B, 6C, 7A, 7B, 8a</td>
          <td>1D (streaming) unless real-time needed; 3D (time-series) unless metrics</td>
        </tr>
        <tr>
          <td><strong>Hybrid / on-prem + cloud workload</strong><br/><em>e.g. HALO LZ migration, legacy system lift</em></td>
          <td>Sections 1–4 (esp. As-Is in 3a/3b), then 8 (INF-02, INF-04), 10 (Components)</td>
          <td>INF-01, INF-02 (Direct Connect/VPN), INF-04 (Split DNS), INF-05, 6A, 6B, 6C</td>
          <td>TSA-NET-02 unless public endpoint; Sections 15–17 after design agreed</td>
        </tr>
        <tr>
          <td><strong>ML / data science platform</strong><br/><em>e.g. SageMaker, EMR Spark, model training</em></td>
          <td>Sections 1–6, then 8 (2C, 3C, 5A, 5C, INF-06), 13 (Data Flows)</td>
          <td>INF-01, INF-05, 3C, 2C, 5A, 6A, 6B, 6C, 6D (if PII), 7A, 8a</td>
          <td>TSA-NET-02 unless model API is public; 3B unless BI reporting also needed</td>
        </tr>
        <tr>
          <td><strong>Real-time / streaming system</strong><br/><em>e.g. IoT, live alerting, event-driven pipeline</em></td>
          <td>Sections 1–6, then 8 (1D, 2B, 3D, 4A), 10 (Components), 11 (Connections)</td>
          <td>INF-01, INF-05, 1D, 2B, 3D, 6A, 6B, 6C, 7A, 7B, 8a</td>
          <td>1B (batch) not needed; 3B only if historical reporting also required</td>
        </tr>
        <tr>
          <td><strong>Lightweight / one-off data transfer</strong><br/><em>e.g. single on-prem extract to S3, one-time file migration</em></td>
          <td>Sections 1–2 (Overview + Introduction), 9 (Context), 10 (Components), 11 (Connections)</td>
          <td>INF-01, INF-02 (Direct Connect/VPN or SFTP), 6A, 6B, 6C</td>
          <td>Sections 3–7 (Background, Pain Points, Requirements, HLD Options); Sections 12–19 unless data is sensitive or recurring</td>
        </tr>
      </tbody>
    </table>
    <p>&#128204; <strong>INF-01 (Landing Zone) and INF-05 (Federated Identity via Entra ID) are mandatory for ALL workloads</strong> — they are applied automatically even if not explicitly selected in Section 8.</p>
    <p>&#128204; <strong>6A (Access Control), 6B (Encryption), 6C (Network Security) and 7A (Centralised Logging) are also mandatory</strong> for all new data workloads under UKHSA Secure by Design policy.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<ac:structured-macro ac:name="info">
  <ac:parameter ac:name="title">▶ How to Use This Page — Step-by-Step</ac:parameter>
  <ac:rich-text-body>
    <p><strong>Recommended approach: use the Data Solution Architecture Questionnaire to drive this page automatically.</strong></p>
    <ol>
      <li><strong>Fill in the <a href="/wiki/spaces/CDA/pages/521438060/Data+Solution+Architecture+Questionnaire">Data Solution Architecture Questionnaire</a></strong> — tick patterns, add context, and run the sync script. It will populate Sections 9–14 of this page and regenerate all diagrams automatically.<br/>
      <code>python confluence_sync_questionnaire_to_main.py</code></li>
      <li><strong>Or fill this page directly — follow this sequence:</strong>
        <ul>
          <li><strong>Sections 1–2</strong> (Solution Overview + Introduction): front-sheet for governance, plain-English description, business outcomes, strategic alignment</li>
          <li><strong>Sections 3–4</strong> (Background + Pain Points): as-is architecture snapshot and current pain points — drives the "why we're changing" narrative</li>
          <li><strong>Sections 5–6</strong> (Functional + Non-Functional Requirements): what the solution must do and at what performance/security levels</li>
          <li><strong>Section 7</strong> (HLD Options): 2–3 architectural options with pros/cons and evaluation criteria — needed for governance gate</li>
          <li><strong>Section 8</strong> (Pattern Selection — 8a to 8f): select approved UKHSA patterns for ingestion, processing, storage, integration, governance/security, infrastructure (INF), and target state (TSA). <strong>INF-01 and INF-05 are always mandatory.</strong></li>
          <li><strong>Section 9</strong> (Context Entities): external actors, systems, and partners — drives the Context View diagram</li>
          <li><strong>Section 10</strong> (Architecture Components): every component with its layer, technology, and cloud — drives the Solution Architecture and Logical View diagrams</li>
          <li><strong>Section 11</strong> (Architecture Connections): source → destination flows with protocol and auth — drives all connection diagrams</li>
          <li><strong>Section 12</strong> (Data Flow Entries): each distinct data movement with source, destination, format, protocol, frequency, and sensitivity</li>
          <li><strong>Section 13</strong> (Dataset Inventory): named datasets, source systems, volume, and retention — drives the Dataset Relationship diagram</li>
          <li><strong>Section 13b</strong> (Network Segmentation Inputs): VPC/subnet CIDRs, connectivity type, and security group rules — drives the Network Segregation diagram</li>
          <li><strong>Section 14</strong> (Auto-Generated Diagrams): run diagram generation once Sections 9–13b are complete</li>
        </ul>
      </li>
      <li><strong>Run diagram generation</strong> after Sections 9–14 are populated:<br/>
      <code>python confluence_update_diagrams.py</code><br/>
      This generates: Solution Architecture, Data Flow, Dataset Relationship, Context View, Logical View, Authentication Flow, and Network Segregation diagrams.</li>
      <li><strong>Complete Sections 15–16</strong> (LLD Summary + Cost Comparison) after HLD options are agreed at governance review.</li>
      <li><strong>Complete Section 17</strong> (Implementation Handover) before handing over to the delivery team — then generate the implementation pack.</li>
      <li><strong>Generate the implementation pack</strong> (Terraform scaffolds + delivery summary):<br/>
      <code>python confluence_generate_implementation_pack.py</code></li>
    </ol>
    <p>&#9888; <strong>Do not edit the Architecture Diagrams child page or the LLD page directly.</strong> They are fully generated from this page — any manual edits will be overwritten on the next run.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<!-- TABLE OF CONTENTS / INDEX -->
<h2>📑 Table of Contents</h2>
<ac:structured-macro ac:name="toc">
  <ac:parameter ac:name="style">none</ac:parameter>
</ac:structured-macro>

<!-- SECTION 1: SOLUTION OVERVIEW -->
<div style="background-color: #e8f0f7; border-left: 5px solid #0052CC; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section1" style="color: #0052CC; margin-top: 0;">1. Solution Overview</h2>
  <p><em>Use this section as the front sheet for governance review. Keep each value concise and decision-oriented.</em></p>
  <table>
  <thead><tr><th>Field</th><th>Value</th></tr></thead>
  <tbody>
    <tr><td>Solution Name</td><td>e.g. National Surveillance Data Exchange</td></tr>
    <tr><td>Version</td><td>0.1 – DRAFT</td></tr>
    <tr><td>Date</td><td>e.g. 08 May 2026</td></tr>
    <tr><td>Solution Architect</td><td>Named accountable architect</td></tr>
    <tr><td>Business Owner</td><td>Named senior business owner</td></tr>
    <tr><td>Primary Stakeholders</td><td>Key delivery, operational, and business stakeholders</td></tr>
    <tr><td>LeanIX Business Capability ID</td><td>Capability reference or “TBC”</td></tr>
    <tr><td>Data Sensitivity Classification</td><td>e.g. Official / Official-Sensitive / Personal Data</td></tr>
    <tr><td>Target Cloud Platform</td><td>AWS / Azure / Hybrid</td></tr>
    <tr><td>Programme / Project Name</td><td>Formal programme, portfolio, or project name</td></tr>
  </tbody>
</table>
</div>

<!-- SECTION 2: INTRODUCTION -->
<div style="background-color: #f0e8f7; border-left: 5px solid #6B46C1; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section2" style="color: #6B46C1; margin-top: 0;">2. Introduction</h2>
  <p><em>Describe what this solution is, why it is needed, and how it fits into the wider UKHSA operating and data landscape.</em></p>
  <table>
  <thead><tr><th>Field</th><th>Detail</th></tr></thead>
  <tbody>
    <tr><td>Solution Description</td><td>What the service does in plain English</td></tr>
    <tr><td>Business Capability Supported</td><td>Which capability, service line, or mission outcome this supports</td></tr>
    <tr><td>Key Users / Data Consumers</td><td>Who uses the outputs and what decisions or services they support</td></tr>
    <tr><td>Strategic Alignment (e.g. Data Strategy, Cloud First)</td><td>Policies, strategies, or transformation drivers this aligns to</td></tr>
    <tr><td>Expected Business Outcomes</td><td>2-4 measurable outcomes, e.g. reduced manual effort, faster reporting, improved quality</td></tr>
    <tr><td>Out of Scope</td><td>Explicit exclusions to avoid ambiguity during design</td></tr>
  </tbody>
</table>
</div>

<!-- SECTION 3: BACKGROUND -->
<div style="background-color: #f7f0e8; border-left: 5px solid #D97706; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section3" style="color: #D97706; margin-top: 0;">3. Background</h2>
  <p><em>Summarise why the work started, what exists today, and what the target end-state needs to achieve.</em></p>
  <table>
  <thead><tr><th>Field</th><th>Detail</th></tr></thead>
  <tbody>
    <tr><td>Trigger / Business Driver</td><td>What event, issue, or mandate has triggered the need for change</td></tr>
    <tr><td>Current State (As-Is)</td><td>One-paragraph summary of today’s process, systems, and known issues</td></tr>
    <tr><td>Desired Future State (To-Be)</td><td>What better looks like from a business and architecture point of view</td></tr>
    <tr><td>Related Projects / Programmes</td><td>List connected initiatives, platforms, or dependencies</td></tr>
    <tr><td>Key Dependencies</td><td>Teams, suppliers, services, or approvals required</td></tr>
    <tr><td>Constraints (technical, policy, budget)</td><td>Hard constraints the design must work within</td></tr>
    <tr><td>Assumptions</td><td>Assumptions currently driving scope or solution choices</td></tr>
    <tr><td>Risks</td><td>Initial delivery, operational, security, or data risks</td></tr>
  </tbody>
</table>

<h3 id="section3a" style="color: #D97706; margin-top: 20px; border-top: 2px solid #D97706; padding-top: 10px;">3a. As-Is Architecture Snapshot</h3>
<p><em>Capture the current-state architecture in a structured, easy-to-fill format before defining the target solution.</em></p>
<table>
  <thead><tr><th>Current-State Area</th><th>Detail</th></tr></thead>
  <tbody>
    <tr><td>Business Process / User Journey</td><td>What happens today from data capture to data use</td></tr>
    <tr><td>Current Users / Teams</td><td>Which teams operate, support, or depend on the current service</td></tr>
    <tr><td>Current Source Systems</td><td>Named upstream source systems and data providers</td></tr>
    <tr><td>Current Applications / Platforms</td><td>Key applications, tools, or platforms in use today</td></tr>
    <tr><td>Current Data Stores</td><td>Databases, file shares, data lakes, warehouses, spreadsheets, etc.</td></tr>
    <tr><td>Current Integrations / Interfaces</td><td>APIs, SFTP, batch files, email, manual extract, CDC, messaging, etc.</td></tr>
    <tr><td>Current Hosting / Environment</td><td>On-prem, cloud tenant, managed service, local desktop, shared drive, etc.</td></tr>
    <tr><td>Current Identity / Access Model</td><td>How users and systems authenticate and are authorised today</td></tr>
    <tr><td>Current Monitoring / Support Model</td><td>Who supports it and what monitoring or alerting exists</td></tr>
    <tr><td>Known As-Is Issues / Technical Debt</td><td>Failures, manual workarounds, unsupported tech, resilience gaps, data quality issues</td></tr>
  </tbody>
</table>

<h3 id="section3b" style="color: #D97706; margin-top: 20px; border-top: 2px solid #D97706; padding-top: 10px;">3b. As-Is Architecture Detail</h3>
<p><em>Use this table for a fillable current-state architecture inventory. This can also be used as the source for drawing a manual As-Is architecture diagram if needed.</em></p>
<table>
  <thead><tr><th>Current Component / System</th><th>Type</th><th>Purpose</th><th>Key Interfaces</th><th>Pain Points / Constraints</th></tr></thead>
  <tbody>
    <tr><td>e.g. LIMS</td><td>Source system</td><td>Captures laboratory events</td><td>CSV batch to shared drive</td><td>Manual handling, delayed updates</td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>
</div>

<!-- SECTION 4: PAIN POINTS -->
<div style="background-color: #fee8e8; border-left: 5px solid #DC2626; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section4" style="color: #DC2626; margin-top: 0;">4. Pain Points / Problem Statement</h2>
  <p><em>Capture specific problems this solution must address. Each pain point should map to at least one requirement below.</em></p>
  <table>
  <thead>
    <tr><th>ID</th><th>Pain Point</th><th>Impacted Team / Process</th><th>Business Impact</th><th>Priority (H/M/L)</th><th>Linked Requirement</th></tr>
  </thead>
  <tbody>
    <tr><td>PP1</td><td></td><td></td><td></td><td>High</td><td></td></tr>
    <tr><td>PP2</td><td></td><td></td><td></td><td>High</td><td></td></tr>
    <tr><td>PP3</td><td></td><td></td><td></td><td>Medium</td><td></td></tr>
    <tr><td>PP4</td><td></td><td></td><td></td><td>Medium</td><td></td></tr>
    <tr><td>PP5</td><td></td><td></td><td></td><td>Low</td><td></td></tr>
  </tbody>
</table>
</div>

<!-- SECTION 5: FUNCTIONAL REQUIREMENTS -->
<div style="background-color: #e8f8e8; border-left: 5px solid #16A34A; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section5" style="color: #16A34A; margin-top: 0;">5. Functional Requirements</h2>
  <p><em>What the system must do. Use MoSCoW prioritisation: Must Have / Should Have / Could Have / Won&#39;t Have.</em></p>
  <table>
  <thead>
    <tr><th>ID</th><th>Requirement</th><th>Acceptance Criteria</th><th>Priority (MoSCoW)</th><th>Linked Pain Point</th><th>Owner</th><th>Status</th></tr>
  </thead>
  <tbody>
    <tr><td>FR1</td><td></td><td></td><td>Must Have</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>FR2</td><td></td><td></td><td>Must Have</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>FR3</td><td></td><td></td><td>Must Have</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>FR4</td><td></td><td></td><td>Should Have</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>FR5</td><td></td><td></td><td>Should Have</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>FR6</td><td></td><td></td><td>Could Have</td><td></td><td></td><td>Draft</td></tr>
  </tbody>
</table>

<!-- SECTION 6: NON-FUNCTIONAL REQUIREMENTS -->
</div>
<div style="background-color: #f8e8ff; border-left: 5px solid #9333EA; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section6" style="color: #9333EA; margin-top: 0;">6. Non-Functional Requirements</h2>
  <p><em>Quality attributes, service levels, and constraints. These drive pattern selection and NFR controls in the LLD.</em></p>
<table>
  <thead>
    <tr><th>ID</th><th>NFR Category</th><th>Requirement</th><th>Target / SLA</th><th>Measurement Method</th><th>Priority (H/M/L)</th><th>Status</th></tr>
  </thead>
  <tbody>
    <tr><td>NFR1</td><td>Performance / Throughput</td><td></td><td></td><td></td><td>High</td><td>Draft</td></tr>
    <tr><td>NFR2</td><td>Availability / Resilience</td><td></td><td></td><td></td><td>High</td><td>Draft</td></tr>
    <tr><td>NFR3</td><td>Scalability</td><td></td><td></td><td></td><td>High</td><td>Draft</td></tr>
    <tr><td>NFR4</td><td>Security &amp; Access Control</td><td></td><td></td><td></td><td>High</td><td>Draft</td></tr>
    <tr><td>NFR5</td><td>Data Governance &amp; Quality</td><td></td><td></td><td></td><td>High</td><td>Draft</td></tr>
    <tr><td>NFR6</td><td>Compliance / Regulatory</td><td></td><td></td><td></td><td>High</td><td>Draft</td></tr>
    <tr><td>NFR7</td><td>Observability &amp; Monitoring</td><td></td><td></td><td></td><td>Medium</td><td>Draft</td></tr>
    <tr><td>NFR8</td><td>Maintainability / Operability</td><td></td><td></td><td></td><td>Medium</td><td>Draft</td></tr>
    <tr><td>NFR9</td><td>Cost Efficiency</td><td></td><td></td><td></td><td>Medium</td><td>Draft</td></tr>
    <tr><td>NFR10</td><td>Disaster Recovery / RTO/RPO</td><td></td><td></td><td></td><td>High</td><td>Draft</td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 7: HLD OPTIONS -->
<div style="background-color: #f0ede8; border-left: 5px solid #B45309; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section7" style="color: #B45309; margin-top: 0;">7. Architecture Decision – HLD Options</h2>
<p><em>Use this section to compare the shortlisted solution options and make an explicit architecture decision.</em></p>
<table>
  <thead>
    <tr><th>Option</th><th>Summary</th><th>Key Services / Patterns</th><th>Pros</th><th>Cons</th><th>Addresses Pain Points</th><th>Decision Status</th></tr>
  </thead>
  <tbody>
    <tr><td>Option A</td><td>Short name and one-line description of the approach</td><td>Named services, platforms, and pattern IDs</td><td>Main strengths</td><td>Main drawbacks</td><td>PP1, PP2, etc.</td><td>Candidate</td></tr>
    <tr><td>Option B</td><td></td><td></td><td></td><td></td><td></td><td>Candidate</td></tr>
    <tr><td>Option C</td><td></td><td></td><td></td><td></td><td></td><td>Candidate</td></tr>
  </tbody>
</table>

  <h3 id="section7a" style="color: #B45309; margin-top: 20px; border-top: 2px solid #B45309; padding-top: 10px;">7a. Option Evaluation Criteria</h3>
<table>
  <thead><tr><th>Criterion</th><th>How to Assess</th><th>Relative Weight (H/M/L)</th></tr></thead>
  <tbody>
    <tr><td>Strategic Fit</td><td>Alignment to business outcomes, operating model, and target state</td><td>High</td></tr>
    <tr><td>Technical Fit</td><td>Ability to satisfy FRs, NFRs, and integration constraints</td><td>High</td></tr>
    <tr><td>Delivery Complexity</td><td>Implementation effort, dependencies, and migration impact</td><td>Medium</td></tr>
    <tr><td>Operational Complexity</td><td>Supportability, monitoring, resilience, and skills needed</td><td>Medium</td></tr>
    <tr><td>Cost</td><td>Build cost and ongoing run cost over the expected lifecycle</td><td>Medium</td></tr>
    <tr><td>Risk</td><td>Security, compliance, data, and supplier risk exposure</td><td>High</td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 8: PATTERN SELECTION -->
<div style="background-color: #f0f8f0; border-left: 5px solid #059669; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section8" style="color: #059669; margin-top: 0;">8. Pattern Selection</h2>
<p><em>Select the approved UKHSA patterns for the chosen HLD option. See the UKHSA Cloud Strategy & Approved patterns.md file for pattern reference.</em></p>
<p><em>Secure by Design reference:</em> <a href=""" + html.escape(SECURE_BY_DESIGN_SAT_URL, quote=True) + """>UKHSA Secure by Design - SAT Template v2.6</a></p>

  <h3 id="section8a" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8a. Data Ingestion Patterns</h3>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected?</th><th>Notes / Justification</th></tr></thead>
  <tbody>
    <tr><td>1A</td><td>API / Web Service Pull</td><td></td><td>Pull from REST / GraphQL / SOAP APIs on schedule or event</td></tr>
    <tr><td>1B</td><td>Batch File Upload</td><td></td><td>Bulk scheduled file transfers via SFTP / S3 upload</td></tr>
    <tr><td>1C</td><td>Database Replication</td><td></td><td>DMS / CDC sync of on-prem or operational DB to cloud</td></tr>
    <tr><td>1D</td><td>Streaming Ingestion</td><td></td><td>High-speed sensor data, metrics, IoT or event streams</td></tr>
  </tbody>
</table>

  <h3 id="section8b" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8b. Data Processing Patterns</h3>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected?</th><th>Notes / Justification</th></tr></thead>
  <tbody>
    <tr><td>2A</td><td>Batch ETL</td><td></td><td>Nightly / scheduled large-volume data transformation</td></tr>
    <tr><td>2B</td><td>Real-time Stream Processing</td><td></td><td>Continuous event processing with sub-second latency</td></tr>
    <tr><td>2C</td><td>Scheduled Spark / ML Jobs</td><td></td><td>ML model training or large-scale Spark processing</td></tr>
    <tr><td>2D</td><td>Federated Query</td><td></td><td>Cross-dataset analysis without copying data (Athena / Redshift Spectrum)</td></tr>
  </tbody>
</table>

  <h3 id="section8c" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8c. Data Storage Patterns</h3>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected?</th><th>Notes / Justification</th></tr></thead>
  <tbody>
    <tr><td>3A</td><td>Transactional Database (OLTP)</td><td></td><td>ACID transactions for operational systems (RDS / Aurora / Azure SQL)</td></tr>
    <tr><td>3B</td><td>Data Warehouse (OLAP)</td><td></td><td>Historical reporting and complex analytical queries (Redshift / Synapse)</td></tr>
    <tr><td>3C</td><td>Data Lake (Bronze / Silver / Gold)</td><td></td><td>Centralised raw, conformed, and curated storage (S3 / ADLS)</td></tr>
    <tr><td>3D</td><td>Time-Series Database</td><td></td><td>Lab capacity, infection rates, or metrics per minute / second</td></tr>
    <tr><td>3E</td><td>Document Store</td><td></td><td>Nested, variable-structure, or schema-flexible data (DynamoDB / CosmosDB)</td></tr>
  </tbody>
</table>

  <h3 id="section8d" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8d. Governance, Security &amp; Operational Patterns</h3>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Layer</th><th>Selected?</th><th>Notes</th></tr></thead>
  <tbody>
    <tr><td>4A</td><td>Event-Driven Pipelines</td><td>Integration</td><td></td><td>Loosely-coupled services reacting to data changes or domain events</td></tr>
    <tr><td>4B</td><td>ETL Orchestration</td><td>Integration</td><td></td><td>Multi-step workflows with dependencies, retries, and branching</td></tr>
    <tr><td>4C</td><td>Data Replication &amp; Sync</td><td>Integration</td><td></td><td>HA, compliance archiving, or multi-region data copies</td></tr>
    <tr><td>5A</td><td>Centralised Data Catalogue</td><td>Governance</td><td></td><td>Discoverability, metadata management, and access control (Glue Catalog / Purview)</td></tr>
    <tr><td>5B</td><td>Data Quality &amp; Validation</td><td>Governance</td><td></td><td>Automated quality checks before promoting data between layers</td></tr>
    <tr><td>5C</td><td>Data Lineage &amp; Audit Trail</td><td>Governance</td><td></td><td>Regulatory compliance, root-cause analysis, and data provenance tracking</td></tr>
    <tr><td>6A</td><td>Access Control</td><td>Security</td><td></td><td>Fine-grained identity-based access to all data assets (IAM / Lake Formation)</td></tr>
    <tr><td>6B</td><td>Encryption &amp; Key Management</td><td>Security</td><td></td><td>Data at-rest and in-transit encryption with managed key lifecycle (KMS / Key Vault)</td></tr>
    <tr><td>6C</td><td>Network Security &amp; Isolation</td><td>Security</td><td></td><td>Network controls preventing data exfiltration and lateral movement</td></tr>
    <tr><td>6D</td><td>Data Masking &amp; Anonymisation</td><td>Security</td><td></td><td>PII / sensitive data de-identification for non-production and analytics use</td></tr>
    <tr><td>7A</td><td>Centralised Logging</td><td>Monitoring</td><td></td><td>Unified audit trail, security investigation, and operational diagnostics</td></tr>
    <tr><td>7B</td><td>Performance Monitoring &amp; Alerting</td><td>Monitoring</td><td></td><td>Proactive detection of degradation, capacity issues, or SLA breaches</td></tr>
    <tr><td>7C</td><td>Cost Tracking &amp; Optimisation</td><td>Monitoring</td><td></td><td>FinOps — spend visibility, anomaly detection, and rightsizing</td></tr>
    <tr><td>8A</td><td>High Availability (Multi-AZ)</td><td>Resilience</td><td></td><td>Active-active or active-standby within a region for zero RPO/RTO targets</td></tr>
    <tr><td>8B</td><td>Disaster Recovery (Cross-Region)</td><td>Resilience</td><td></td><td>Warm / cold standby in a second region to meet BCDR requirements</td></tr>
    <tr><td>8C</td><td>Backup &amp; Point-in-Time Recovery</td><td>Resilience</td><td></td><td>Automated backups with tested restore capability within agreed RTO</td></tr>
    <tr><td>SBD-01</td><td>Threat Modelling &amp; Abuse Cases</td><td>Security</td><td></td><td>Apply SAT template checkpoints before Gate 2</td></tr>
    <tr><td>SBD-02</td><td>Secure SDLC &amp; Supply Chain Assurance</td><td>Security</td><td></td><td>Enforce SAST / DAST / SCA and signed artifact controls</td></tr>
    <tr><td>SBD-03</td><td>Privacy by Design (DPIA / DSA Controls)</td><td>Governance</td><td></td><td>Link data protection controls to datasets and flows</td></tr>
    <tr><td>SBD-04</td><td>Continuous Security Assurance</td><td>Governance</td><td></td><td>Operational control testing, evidence, and remediation tracking</td></tr>
  </tbody>
</table>

  <h3 id="section8e" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8e. Infrastructure &amp; Platform Patterns</h3>
  <p><em>UKHSA-approved infrastructure patterns. INF-01 (Landing Zone) and INF-05 (Federated Identity) are mandatory for all cloud workloads.</em></p>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected?</th><th>Notes / Justification</th></tr></thead>
  <tbody>
    <tr><td>UKHSA-INF-01</td><td>UKHSA Cloud Landing Zone</td><td>Y</td><td><strong>Mandatory</strong> — all cloud workloads must deploy into an approved UKHSA LZ (AWS or Azure)</td></tr>
    <tr><td>UKHSA-INF-02</td><td>Hybrid Cloud Connectivity</td><td></td><td>Secure AWS Direct Connect / Azure ExpressRoute with IPsec VPN backup</td></tr>
    <tr><td>UKHSA-INF-03</td><td>Multi-Cloud Account Governance</td><td></td><td>AWS Organizations / Azure Management Groups with centralised policy enforcement</td></tr>
    <tr><td>UKHSA-INF-04</td><td>Split-Horizon DNS</td><td></td><td>Route 53 as strategic DNS resolver with conditional forwarding to on-prem</td></tr>
    <tr><td>UKHSA-INF-05</td><td>Federated Identity (Entra ID Golden Source)</td><td>Y</td><td><strong>Mandatory</strong> — Microsoft Entra ID as single IdP federated to AWS, SaaS, and all workloads</td></tr>
    <tr><td>UKHSA-INF-06</td><td>Approved Platform Portfolio</td><td></td><td>Use UKHSA-approved platforms: EDAP (analytics), APIM (APIs), Sentinel (SIEM)</td></tr>
  </tbody>
</table>

  <h3 id="section8f" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8f. Target State Architecture – Networking &amp; Identity</h3>
  <p><em>UKHSA TSA patterns define the strategic target networking and identity architecture all new solutions should align to.</em></p>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected?</th><th>Notes / Justification</th></tr></thead>
  <tbody>
    <tr><td>TSA-NET-01</td><td>Zero-Trust Network Access (ZTNA)</td><td></td><td>Replace implicit trust with identity-verified, device-checked, context-aware access</td></tr>
    <tr><td>TSA-NET-02</td><td>Centralised Ingress (ALB + WAF)</td><td></td><td>Single WAF-protected ingress point for all public-facing workloads</td></tr>
    <tr><td>TSA-IDN-01</td><td>Passwordless Authentication</td><td></td><td>FIDO2 / Windows Hello / Certificate-based auth via Entra ID</td></tr>
    <tr><td>TSA-IDN-02</td><td>Privileged Identity Management (PIM)</td><td></td><td>Just-in-time, time-limited elevation of privileged roles via Entra PIM</td></tr>
  </tbody>
</table>

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
    &nbsp;Target state — approved but not yet fully deployed &nbsp;|&nbsp;
    <ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Red</ac:parameter><ac:parameter ac:name="title">Not Available</ac:parameter></ac:structured-macro>
    &nbsp;Not approved for UKHSA use
  </p>

  <h4 style="color:#374151; margin-top:16px;">Category 1 — On-Premises ↔ Cloud</h4>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>From</th><th>To</th><th>Use When</th><th>Bandwidth</th><th>Indicative Cost (£/mo)</th><th>Availability</th><th>Selected?</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>CONN-01</strong></td><td>AWS Direct Connect</td><td>On-Prem DC / OCP</td><td>AWS</td>
        <td>Primary production path; consistent bandwidth; OFFICIAL-SENSITIVE data</td>
        <td>1–10 Gbps dedicated</td><td>£140–280 port + £0.02/GB out</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-02</strong></td><td>AWS Site-to-Site VPN</td><td>On-Prem DC / OCP / Remote Site</td><td>AWS</td>
        <td>Dev/test or DX warm-standby failover only — not for production primary</td>
        <td>Up to 2.5 Gbps (2 tunnels)</td><td>£30–50 + £0.05/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-03</strong></td><td>Azure ExpressRoute</td><td>On-Prem DC / OCP</td><td>Azure</td>
        <td>Primary production path to Azure; high-volume; OFFICIAL-SENSITIVE data</td>
        <td>50 Mbps–10 Gbps</td><td>£200–400 circuit + £0.02/GB out</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-04</strong></td><td>Azure VPN Gateway (S2S)</td><td>On-Prem DC / OCP / Remote Site</td><td>Azure</td>
        <td>Dev/test or ExpressRoute warm-standby failover only</td>
        <td>Up to 10 Gbps (VpnGw5)</td><td>£160–420 gateway + £0.05/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-17</strong></td><td>OpenShift → AWS via PrivateLink</td><td>OpenShift (OCP)</td><td>AWS</td>
        <td>OCP pods calling AWS services (S3, SQS, RDS) without public internet</td>
        <td>Shared with DX circuit</td><td>£6–10/endpoint + DX transfer</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-18</strong></td><td>OpenShift → Azure via ExpressRoute</td><td>OpenShift (OCP)</td><td>Azure</td>
        <td>OCP pods accessing Azure Key Vault, Storage, Service Bus over ER private peering</td>
        <td>Shared with ER circuit</td><td>Marginal + £6–8/endpoint</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <h4 style="color:#374151; margin-top:16px;">Category 2 — Cloud-to-Cloud (AWS ↔ Azure)</h4>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>From</th><th>To</th><th>Use When</th><th>Bandwidth</th><th>Indicative Cost (£/mo)</th><th>Availability</th><th>Selected?</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>CONN-05</strong></td><td>Equinix / Megaport Fabric</td><td>AWS</td><td>Azure</td>
        <td>⭐ <strong>Target state</strong> — large-volume, low-latency, OFFICIAL-SENSITIVE cross-cloud</td>
        <td>1–10 Gbps private fabric</td><td>£300–600 fabric port + £0.07/GB AWS egress</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-06</strong></td><td>AWS ↔ Azure Internet VPN (Interim)</td><td>AWS</td><td>Azure</td>
        <td>Dev/test or interim only — must declare migration date to CONN-05</td>
        <td>Up to 1.25 Gbps/tunnel</td><td>£30–50 VPN + £0.07/GB AWS + £0.05/GB Azure egress</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <h4 style="color:#374151; margin-top:16px;">Category 3 — Internal Cloud (within AWS / within Azure)</h4>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Platform</th><th>Use When</th><th>Indicative Cost (£/mo)</th><th>Availability</th><th>Selected?</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>CONN-07</strong></td><td>AWS Transit Gateway</td><td>AWS</td>
        <td>Multi-VPC routing hub — <strong>mandatory</strong> for all multi-VPC UKHSA AWS deployments</td>
        <td>£30–80 attachments + £0.02/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-08</strong></td><td>AWS VPC Peering</td><td>AWS</td>
        <td>Simple two-VPC only; use TGW for 3+ VPCs</td>
        <td>£0.01–0.02/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-09</strong></td><td>AWS PrivateLink (VPC Endpoints)</td><td>AWS</td>
        <td><strong>Mandatory</strong> for all AWS PaaS API calls from private subnets</td>
        <td>£6–10/endpoint + £0.01/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-10</strong></td><td>Azure VNet Peering</td><td>Azure</td>
        <td>Simple two-VNet only; use Virtual WAN for 3+ VNets</td>
        <td>£0.01–0.02/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-11</strong></td><td>Azure Private Endpoint</td><td>Azure</td>
        <td><strong>Mandatory</strong> for all Azure PaaS in production; disable public endpoint</td>
        <td>£6–8/endpoint + £0.01/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-12</strong></td><td>Azure Virtual WAN</td><td>Azure</td>
        <td>Multi-VNet routing hub — <strong>mandatory</strong> for all multi-VNet UKHSA Azure deployments</td>
        <td>£200–400 hub + £0.02/GB</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <h4 style="color:#374151; margin-top:16px;">Category 4 — Internet-Facing Ingress</h4>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Platform</th><th>Use When</th><th>Indicative Cost (£/mo)</th><th>Availability</th><th>Selected?</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>CONN-13</strong></td><td>Internet Gateway + WAF + CloudFront</td><td>AWS</td>
        <td>Any public-facing AWS workload — WAF is <strong>mandatory</strong> (SEC-APS-03)</td>
        <td>£20–100 (WAF rules + CloudFront)</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-14</strong></td><td>Azure Front Door + WAF</td><td>Azure</td>
        <td>Any public-facing Azure workload — WAF is <strong>mandatory</strong></td>
        <td>£50–200</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Green</ac:parameter><ac:parameter ac:name="title">Available</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <h4 style="color:#374151; margin-top:16px;">Category 5 — Zero Trust / SASE (End-User Access)</h4>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Use When</th><th>Indicative Cost</th><th>Availability</th><th>Selected?</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>CONN-15</strong></td><td>zScaler ZPA (Zero Trust App Access)</td>
        <td>All remote/end-user access to private applications — <strong>replaces VPN</strong> (ADR-010 target state)</td>
        <td>Per-user licence (contact CCoE)</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
      <tr>
        <td><strong>CONN-16</strong></td><td>zScaler ZIA (Secure Internet Egress)</td>
        <td>All outbound internet from UKHSA devices and cloud workloads — replaces on-prem proxy</td>
        <td>Per-user licence (contact CCoE)</td>
        <td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">Yellow</ac:parameter><ac:parameter ac:name="title">In Progress</ac:parameter></ac:structured-macro></td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <ac:structured-macro ac:name="info">
    <ac:parameter ac:name="title">Where to find full details</ac:parameter>
    <ac:rich-text-body>
      <p>Full technical details for each option (best practices, when not to use, redundancy approach) are stored in <strong>ukhsa_patterns_knowledge_base.py → CONNECTIVITY_OPTIONS</strong> in the architecture automation repository.
      See the <strong>CONNECTIVITY_SELECTION_GUIDE</strong> dict for the recommended primary/secondary option per environment pair.</p>
    </ac:rich-text-body>
  </ac:structured-macro>

</div>
<!-- SECTION 9: CONTEXT ENTITIES -->
<div style="background-color: #f0e8f8; border-left: 5px solid #7C3AED; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section9" style="color: #7C3AED; margin-top: 0;">9. Context Entities</h2>
<p><em>Define external actors, systems, and partners that interact with this solution. Drives the <strong>Context View diagram</strong>.</em></p>
<table>
  <thead><tr><th>Entity Name</th><th>Type (User / System / Partner / Service)</th><th>Interaction Description</th><th>Direction (In / Out / Both)</th></tr></thead>
  <tbody>
    <tr><td>On-Prem Business App</td><td>System</td><td>Produces daily surveillance files via SFTP export</td><td>Out</td></tr>
    <tr><td>On-Prem SFTP Server</td><td>System</td><td>Stages and relays files for secure cloud transfer</td><td>Both</td></tr>
    <tr><td>UKHSA Intra Identity (Azure Entra ID)</td><td>Service</td><td>Provides SSO and MFA authentication for transfer users and support access</td><td>Both</td></tr>
    <tr><td>Data Analyst Team</td><td>User</td><td>Consumes validated data outputs</td><td>In</td></tr>
    <tr><td>Security Operations</td><td>Service</td><td>Reviews logs and alerts</td><td>In</td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 10: ARCHITECTURE COMPONENTS -->
<div style="background-color: #f8f0e8; border-left: 5px solid #EA580C; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section10" style="color: #EA580C; margin-top: 0;">10. Architecture Components</h2>
<p><em>Drives the <strong>Solution Architecture</strong> and <strong>Logical View</strong> diagrams. Valid layers: <strong>Edge, Network, Platform, Application, Data, Security, Governance</strong></em></p>
<table>
  <thead>
    <tr><th>No</th><th>Component Name</th><th>Layer</th><th>Technology / Service</th><th>Cloud (AWS/Azure/Both)</th><th>Description</th><th>Links to FR/NFR</th></tr>
  </thead>
  <tbody>
    <tr><td colspan="7"><strong>Core Infrastructure Components</strong></td></tr>
    <tr><td>1</td><td></td><td>Edge</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>2</td><td></td><td>Network</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>3</td><td></td><td>Platform</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>4</td><td></td><td>Application</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>5</td><td></td><td>Data</td><td></td><td></td><td></td><td></td></tr>
    <tr><td colspan="7"><strong>Security Layer Components</strong></td></tr>
    <tr><td>6</td><td>Identity & Access Management (IAM)</td><td>Security</td><td>AWS IAM / Azure Entra ID</td><td>Both</td><td>User authentication, authorization, and role-based access control across all layers</td><td>NFR4</td></tr>
    <tr><td>7</td><td>Encryption at Rest & Transit</td><td>Security</td><td>AWS KMS / Azure Key Vault</td><td>Both</td><td>Data encryption for storage and network communications</td><td>NFR4, NFR5</td></tr>
    <tr><td>8</td><td>Secret Management</td><td>Security</td><td>AWS Secrets Manager / Azure Key Vault</td><td>Both</td><td>Secure storage and rotation of credentials, API keys, database passwords</td><td>NFR4</td></tr>
    <tr><td>9</td><td>Network Security & DDoS Protection</td><td>Security</td><td>AWS WAF, Shield / Azure DDoS Protection</td><td>Both</td><td>Web application firewall and distributed denial-of-service mitigation</td><td>NFR2, NFR4</td></tr>
    <tr><td>10</td><td>Threat Detection & Response</td><td>Security</td><td>AWS GuardDuty / Azure Defender</td><td>Both</td><td>Continuous monitoring for threats and automated incident response</td><td>NFR4</td></tr>
    <tr><td colspan="7"><strong>Governance Layer Components</strong></td></tr>
    <tr><td>11</td><td>Audit Logging & Compliance Monitoring</td><td>Governance</td><td>AWS CloudTrail / Azure Activity Log</td><td>Both</td><td>Complete audit trail of all API calls, user actions, and configuration changes</td><td>NFR6</td></tr>
    <tr><td>12</td><td>Policy Enforcement & Management</td><td>Governance</td><td>AWS Config / Azure Policy</td><td>Both</td><td>Automated policy compliance checking and remediation across infrastructure</td><td>NFR6</td></tr>
    <tr><td>13</td><td>Data Lineage & Governance</td><td>Governance</td><td>AWS Glue / Azure Purview</td><td>Both</td><td>Track data provenance, ownership, and transformation lineage for governance</td><td>NFR5, NFR6</td></tr>
    <tr><td>14</td><td>Cost Optimization & Usage Monitoring</td><td>Governance</td><td>AWS Cost Explorer / Azure Cost Management</td><td>Both</td><td>Monitor spend, optimize resource utilization, and enforce cost controls</td><td>NFR9</td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 11: ARCHITECTURE CONNECTIONS -->
<div style="background-color: #e8f8f8; border-left: 5px solid #0891B2; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section11" style="color: #0891B2; margin-top: 0;">11. Architecture Connections</h2>
<p><em>Define how components communicate. Drives connection arrows on the <strong>Solution Architecture diagram</strong>.</em></p>
<table>
  <thead>
    <tr><th>From Component</th><th>To Component</th><th>Connection Label / Protocol</th><th>Port / Auth</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 12: DATA FLOW ENTRIES -->
<div style="background-color: #f8e8f8; border-left: 5px solid #E11D48; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section12" style="color: #E11D48; margin-top: 0;">12. Data Flow Entries</h2>
<p><em>Drives the <strong>Data Flow Diagram (DFD)</strong>. Capture each distinct data movement between components or external entities.</em></p>
<table>
  <thead>
    <tr><th>Flow ID</th><th>Source</th><th>Destination</th><th>Data Description</th><th>Format</th><th>Protocol / Method</th><th>Frequency</th><th>Sensitivity</th></tr>
  </thead>
  <tbody>
    <tr><td>F1</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>F2</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>F3</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>F4</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 13: DATASET INVENTORY -->
<div style="background-color: #f8f0e8; border-left: 5px solid #D97706; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section13" style="color: #D97706; margin-top: 0;">13. Dataset Inventory</h2>
<p><em>Drives the <strong>Dataset Relationship diagram</strong>.</em></p>
<table>
  <thead>
    <tr><th>ID</th><th>Dataset Name</th><th>Type (Structured/Semi/Unstructured)</th><th>Source System</th><th>Primary Key</th><th>Sensitivity</th><th>Volume Estimate</th><th>Retention Period</th></tr>
  </thead>
  <tbody>
    <tr><td>D1</td><td>Patient Demographics</td><td>Structured</td><td>UKHSA On-Prem</td><td>patient_id</td><td>Official-Sensitive</td><td>100GB</td><td>7 years</td></tr>
    <tr><td>D2</td><td>Medical History</td><td>Structured</td><td>UKHSA On-Prem</td><td>record_id</td><td>Official-Sensitive</td><td>500GB</td><td>10 years</td></tr>
    <tr><td>D3</td><td>Lab Results</td><td>Structured</td><td>UKHSA AWS</td><td>result_id</td><td>Official-Sensitive</td><td>250GB</td><td>5 years</td></tr>
    <tr><td>D4</td><td>Audit Trail</td><td>Structured</td><td>UKHSA AWS</td><td>audit_id</td><td>Secret</td><td>50GB</td><td>3 years</td></tr>
  </tbody>
</table>

  <h3 id="section13a" style="color: #D97706; margin-top: 20px; border-top: 2px solid #D97706; padding-top: 10px;">Dataset Relationships</h3>
<p><em>Define how datasets relate. Drives the ERD-style <strong>Dataset Relationship diagram</strong>.</em></p>
<table>
  <thead>
    <tr><th>From Dataset</th><th>To Dataset</th><th>Relationship Type (1:1 / 1:N / M:N)</th><th>Key Mapping (e.g. patient_id)</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr><td>Patient Demographics</td><td>Medical History</td><td>1:N</td><td>patient_id → patient_id</td><td>One patient has many medical records</td></tr>
    <tr><td>Patient Demographics</td><td>Lab Results</td><td>1:N</td><td>patient_id → patient_id</td><td>One patient has many lab results</td></tr>
    <tr><td>Medical History</td><td>Lab Results</td><td>M:N</td><td>record_id ↔ lab_id</td><td>Multiple records can have multiple lab tests</td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 13B: NETWORK SEGMENTATION INPUTS -->
<div style="background-color: #eef6ff; border-left: 5px solid #1D4ED8; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section13b" style="color: #1D4ED8; margin-top: 0;">13b. Network Segmentation Inputs</h2>
<p><em>Provides explicit inputs for the <strong>Network Segregation diagram</strong> so it matches AWS reference architecture clarity.</em></p>
<table>
  <thead>
    <tr><th>Parameter</th><th>Value</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr><td>VPC CIDR</td><td>10.0.0.0/16</td><td>Primary workload VPC range</td></tr>
    <tr><td>Public Subnet CIDR</td><td>10.0.1.0/24</td><td>Ingress / ALB</td></tr>
    <tr><td>Private Subnet CIDR</td><td>10.0.2.0/24</td><td>Application runtime</td></tr>
    <tr><td>Data Subnet CIDR</td><td>10.0.3.0/24</td><td>RDS/data services</td></tr>
    <tr><td>On-Prem CIDR</td><td>172.16.0.0/16</td><td>Corporate/legacy network</td></tr>
    <tr><td>Connectivity Type</td><td>Site-to-Site VPN</td><td>Or Direct Connect + VPN backup</td></tr>
    <tr><td>Public Ingress Path</td><td>Internet -> IGW -> ALB</td><td>North-south ingress</td></tr>
    <tr><td>Private Ingress Path</td><td>On-prem -> VPN -> Private Route Table -> EKS</td><td>Hybrid private access</td></tr>
    <tr><td>Public SG Rules</td><td>HTTP(80), HTTPS(443)</td><td>Internet-facing controls</td></tr>
    <tr><td>Private SG Rules</td><td>Internal east-west only</td><td>No direct internet</td></tr>
    <tr><td>Data SG Rules</td><td>DB ports (3306, 5432, 6379)</td><td>Strict application-to-data only</td></tr>
    <tr><td>Public Route</td><td>0.0.0.0/0 via IGW</td><td>Public subnet route table</td></tr>
    <tr><td>Private Route</td><td>On-prem CIDR via VPN</td><td>Private subnet route table</td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 14: AUTO-GENERATED DIAGRAMS -->
<div style="background-color: #e8f8f0; border-left: 5px solid #059669; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section14" style="color: #059669; margin-top: 0;">14. Auto-Generated Diagrams</h2>
<p><em>All architectural diagrams are auto-generated from the tables above (Sections 10-13b) and maintained on a separate page for clarity and editability.</em></p>

<p><strong>To generate or update diagrams:</strong> Run <code>confluence_update_diagrams.py</code> after completing the architecture tables.</p>

<p style="margin-top: 15px; font-size: 16px;"><strong><ac:link><ri:page ri:space-key="CDA" ri:content-title="Architecture Diagrams" /></ac:link></strong></p>
<p style="margin-top: 10px; font-size: 16px;"><strong><ac:link><ri:page ri:space-key="CDA" ri:content-title="Architecture Patterns Reference" /></ac:link></strong></p>

<p><em>Use the <strong>Architecture Patterns Reference</strong> page to pick reusable Security, Network, Governance, DPIA/DSA, and EDAP-aligned integration patterns.</em></p>

<h3>Diagram Types Generated</h3>
<ul>
  <li><strong>Context View</strong> – System boundary and external entities</li>
  <li><strong>Logical View</strong> – Services by responsibility and interaction</li>
  <li><strong>Solution Architecture</strong> – Layer-based component view (Edge, Network, Platform, Application, Data, Security, Governance)</li>
  <li><strong>Data Flow Diagram (DFD)</strong> – All data movements between components</li>
  <li><strong>Dataset Relationship Diagram (ERD)</strong> – Datasets and their relationships</li>
  <li><strong>Authentication Flow</strong> – OAuth2/Cognito authentication sequence</li>
  <li><strong>Network Segregation</strong> – VPC, subnets, and security group configuration</li>
</ul>

</div>
<!-- SECTION 15: LLD SUMMARY -->
<div style="background-color: #f8e8e8; border-left: 5px solid #B91C1C; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section15" style="color: #B91C1C; margin-top: 0;">15. Low-Level Design (LLD) Summary</h2>
<p><em>Final design decisions agreed after HLD review. Updated before handover to engineering.</em></p>
<table>
  <thead><tr><th>LLD Area</th><th>Implementation Detail</th><th>Decision Owner</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>Component Specifications</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>API Contracts / Interfaces</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>Schema / Data Model</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>IAM / RBAC Design</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>NFR Controls Implementation</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>Monitoring &amp; Alerting Setup</td><td></td><td></td><td>Draft</td></tr>
    <tr><td>DR / Backup Configuration</td><td></td><td></td><td>Draft</td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 16: COST COMPARISON -->
<div style="background-color: #f0f8f8; border-left: 5px solid #0369A1; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section16" style="color: #0369A1; margin-top: 0;">16. Solution Option Cost Comparison</h2>
<p><em>Compare the shortlisted solution options from Section 7, including indicative build and run costs. Capture assumptions clearly so reviewers can understand what is included or excluded.</em></p>
<table>
  <thead>
    <tr><th>Cost Area</th><th>Option A (£ / month)</th><th>Option B (£ / month)</th><th>Option C (£ / month)</th><th>Notes / Assumptions</th></tr>
  </thead>
  <tbody>
    <tr><td>Storage</td><td></td><td></td><td></td><td>Volumes, retention, replication assumptions</td></tr>
    <tr><td>Compute / Processing</td><td></td><td></td><td></td><td>Batch frequency, peak load, scaling assumptions</td></tr>
    <tr><td>Data Transfer / Networking</td><td></td><td></td><td></td><td>Ingress, egress, private connectivity, cross-region traffic</td></tr>
    <tr><td>Monitoring / Logging</td><td></td><td></td><td></td><td>Expected log retention and alerting coverage</td></tr>
    <tr><td>Security / IAM</td><td></td><td></td><td></td><td>KMS, secrets, PAM, identity integration, audit needs</td></tr>
    <tr><td>Managed Services / Licensing</td><td></td><td></td><td></td><td>Third-party tooling, enterprise licences, support plans</td></tr>
    <tr><td><strong>Total Indicative Run Cost</strong></td><td><strong></strong></td><td><strong></strong></td><td><strong></strong></td><td>Document whether VAT, contingency, and support are included</td></tr>
  </tbody>
</table>

  <h3 id="section16a" style="color: #0369A1; margin-top: 20px; border-top: 2px solid #0369A1; padding-top: 10px;">16a. Option-Level Comparison Summary</h3>
<table>
  <thead><tr><th>Option</th><th>Delivery Cost (£ one-off)</th><th>Key Benefits</th><th>Key Risks / Trade-offs</th><th>Preferred? (Y/N)</th></tr></thead>
  <tbody>
    <tr><td>Option A</td><td></td><td>Why this option is attractive</td><td>Main trade-offs, dependencies, or uncertainties</td><td></td></tr>
    <tr><td>Option B</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>Option C</td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 17: IMPLEMENTATION HANDOVER -->
<div style="background-color: #f0e8f8; border-left: 5px solid #6366F1; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section17" style="color: #6366F1; margin-top: 0;">17. Implementation Handover</h2>
<p><em>After architecture sign-off, generate the implementation pack for the engineering delivery team.</em></p>
<table>
  <thead><tr><th>Deliverable</th><th>Output Location</th><th>Generated By</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>Terraform (AWS)</td><td><code>output/terraform/aws/main.tf</code></td><td>confluence_generate_implementation_pack.py</td><td>Pending</td></tr>
    <tr><td>Terraform (Azure)</td><td><code>output/terraform/azure/main.tf</code></td><td>confluence_generate_implementation_pack.py</td><td>Pending</td></tr>
    <tr><td>Implementation Summary JSON</td><td><code>output/implementation/summary.json</code></td><td>confluence_generate_implementation_pack.py</td><td>Pending</td></tr>
    <tr><td>draw.io Diagrams (local)</td><td><code>output/generated/*.drawio</code></td><td>confluence_update_diagrams.py</td><td>Pending</td></tr>
  </tbody>
</table>

</div>
<!-- REFERENCE DOCUMENTS -->
<div style="background-color: #f8f8f0; border-left: 5px solid #78350F; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="reference" style="color: #78350F; margin-top: 0;">Reference Documents</h2>
</div>
<ul>
  <li><strong>UKHSA Cloud Strategy & Approved patterns.md</strong> – UKHSA-approved patterns and cloud strategy reference (local file)</li>
  <li><a href="{plan_link}">QUESTIONNAIRE_PLAN.md</a> – Questionnaire planning notes</li>
</ul>
"""


def build_approved_patterns_page_html() -> str:
  """Create a dedicated reusable approved-patterns reference page."""
  secure_by_design_link = html.escape(SECURE_BY_DESIGN_SAT_URL, quote=True)
  return """
<h1>Architecture Patterns Reference</h1>

<p><em>Reusable reference designs for Security, Network, Governance, DPIA/DSA, and EDAP integration patterns. Use this page to select a baseline structure quickly for new HLD designs. EDAP integration patterns are sourced from the <a href="https://ukhsa.atlassian.net/wiki/spaces/EDAP/pages/165353198/AWS+High+Level+Design">EDAP AWS High Level Design</a> and <a href="https://ukhsa.atlassian.net/wiki/spaces/EDAP/pages/165357494/AWS+Technical+Design">EDAP AWS Technical Design</a> pages.</em></p>

<ac:structured-macro ac:name="info">
  <ac:parameter ac:name="title">How to Use This Page</ac:parameter>
  <ac:rich-text-body>
    <ol>
      <li>Select the required domain pattern(s) from the catalog below.</li>
      <li>Copy the pattern ID(s) and rationale into Section 8 (Pattern Selection) on the main HLD page.</li>
      <li>Apply mandatory controls listed for each pattern at all layers.</li>
      <li>For analytics workloads, ensure EDAP integration is explicit in the selected pattern.</li>
    </ol>
  </ac:rich-text-body>
</ac:structured-macro>

<h2>Policy and Standards Coverage</h2>
<table>
  <thead><tr><th>Domain</th><th>Reference</th></tr></thead>
  <tbody>
    <tr><td>Security baseline</td><td><a href=\"https://www.cisecurity.org/cis-benchmarks\">CIS Benchmarks</a></td></tr>
    <tr><td>Enterprise guardrails</td><td><a href=\"https://ukhsa.atlassian.net/wiki/spaces/AT/pages/170626343/Enterprise+Guide+Rails+Catalogue+Strategic?pageId=170626343\">Enterprise Guide Rails Catalogue</a></td></tr>
    <tr><td>Frameworks and legislation</td><td><a href=\"https://ukhsa.atlassian.net/wiki/spaces/CCE/pages/176654107/Frameworks+and+Legislations\">Security Frameworks and Legislations</a></td></tr>
    <tr><td>Network architecture</td><td><a href=\"https://ukhsa.atlassian.net/wiki/spaces/HALO/pages/172255190/Network+Design\">Network Design</a> | <a href=\"https://ukhsa.atlassian.net/wiki/spaces/HIDM/pages/167629598/Strategic+Network+Summary\">Strategic Network Summary</a> | <a href=\"https://ukhsa.atlassian.net/wiki/spaces/AT/pages/170627256/Cloud+Network+Security+Pattern\">Cloud Network Security Pattern</a></td></tr>
    <tr><td>Governance controls</td><td><a href=\"https://ukhsa.atlassian.net/wiki/spaces/UAOM/pages/484737698/Governance+controls\">Governance controls</a> | <a href=\"https://ukhsa.atlassian.net/wiki/spaces/EDCE/pages/448954953/Governance+Domains\">Governance Domains</a> | <a href=\"https://ukhsa.atlassian.net/wiki/spaces/ICTPMO/pages/175112629/Governance+risks+and+issues\">Governance risks and issues</a></td></tr>
    <tr><td>DPIA / Data sharing</td><td><a href=\"https://ukhsa.atlassian.net/wiki/spaces/HALO/pages/172194466/UKHSA+Cloud+Platform+Data+Protection+Impact+Assessment+DPIA+Review+Process\">DPIA Review Process</a> | <a href=\"https://ukhsa.atlassian.net/wiki/spaces/EDGE/pages/164039010/Data+sharing+arrangements+WIP\">Data sharing arrangements (WIP)</a></td></tr>
    <tr><td>ITSM operations</td><td><a href=\"https://ukhsa.atlassian.net/wiki/spaces/ISM/pages/167627576/ITSM+Problem+Management+Policy\">ITSM Problem Management Policy</a></td></tr>
    <tr><td>Secure by Design</td><td><a href=\""" + secure_by_design_link + "\">UKHSA Secure by Design - SAT Template v2.6</a></td></tr>
  </tbody>
</table>

<h2>Approved Pattern Catalog</h2>
<table>
  <thead><tr><th>Pattern ID</th><th>Domain</th><th>Reusable Structure</th><th>Use When</th><th>Mandatory Controls</th><th>EDAP Alignment</th></tr></thead>
  <tbody>
    <tr><td>SEC-01</td><td>Security</td><td>Zero-Trust baseline (IAM, RBAC, KMS, secrets, audit)</td><td>All cloud solutions</td><td>CIS hardening, least privilege, encryption in transit/at rest, audit logging</td><td>Required for EDAP-integrated analytics workloads</td></tr>
    <tr><td>NET-01</td><td>Network</td><td>Segmented VPC (public/private/data subnets, SG/NACL, controlled routes)</td><td>Any workload with private data or hybrid connectivity</td><td>Cloud Network Security Pattern, route isolation, explicit ingress/egress paths</td><td>Use for EDAP producer/consumer connectivity patterns</td></tr>
    <tr><td>GOV-01</td><td>Governance</td><td>Policy and assurance overlay (control owners, evidence, review cadence)</td><td>Regulated or high-impact solutions</td><td>Governance controls/domains, risk register linkage, decision traceability</td><td>Map controls to EDAP data and platform ownership</td></tr>
    <tr><td>DPIA-01</td><td>Data protection</td><td>DPIA + DSA integrated design gate</td><td>Personal data or cross-team sharing</td><td>DPIA completion criteria, DSA checkpoints, minimisation and retention controls</td><td>Mandatory for analytics onboarding to EDAP</td></tr>
    <tr><td>OPS-01</td><td>Operations</td><td>ITSM-ready operating model (incident/problem/change, observability)</td><td>Production service handover</td><td>ITSM policy alignment, runbooks, alerting and ownership model</td><td>Align EDAP support boundaries and escalation paths</td></tr>
    <tr><td>SBD-01</td><td>Secure by Design</td><td>Threat modelling and abuse-case analysis baseline</td><td>New capabilities or material architecture changes</td><td>Documented threat model, trust boundaries, mitigations linked to NFR4/NFR6</td><td>Required before promoting to beta/live gates</td></tr>
    <tr><td>SBD-02</td><td>Secure by Design</td><td>Secure SDLC and supply chain assurance</td><td>Any CI/CD-based deployment</td><td>SAST/DAST/SCA gates, signed artifacts, dependency governance, change approvals</td><td>Required for automated deployment pathways</td></tr>
    <tr><td>SBD-03</td><td>Secure by Design</td><td>Data protection and privacy-by-design controls</td><td>Sensitive, personal, or shared data processing</td><td>DPIA checkpoints, minimisation, retention, masking/tokenisation, lawful basis</td><td>Map controls to dataset inventory and flows</td></tr>
    <tr><td>SBD-04</td><td>Secure by Design</td><td>Security telemetry and continuous assurance pattern</td><td>Operational services requiring ongoing compliance visibility</td><td>Central logging, alerting, audit evidence, policy drift detection, periodic control testing</td><td>Feed governance and operational review cadences</td></tr>
  </tbody>
</table>

<h2>Pattern Diagrams (Reference)</h2>
<p><em>These blocks are the dedicated locations for approved-pattern diagrams and explanations.</em></p>

<h3>Security Pattern Diagram (SEC-01)</h3>
<p><strong>Diagram block:</strong> [[DIAGRAM:approved-pattern-security]]</p>
<p><strong>Explanation:</strong> Shows baseline controls at all layers: identity, encryption, secrets, logging, and monitoring.</p>

<h3>Network Pattern Diagram (NET-01)</h3>
<p><strong>Diagram block:</strong> [[DIAGRAM:approved-pattern-network]]</p>
<p><strong>Explanation:</strong> Shows segmented network structure with ingress, private east-west paths, and data subnet isolation.</p>

<h3>Governance Controls Pattern (GOV-01)</h3>
<p><strong>Diagram block:</strong> [[DIAGRAM:approved-pattern-governance]]</p>
<p><strong>Explanation:</strong> Shows governance domains, control ownership, evidence points, and risk/issue integration.</p>

<h3>DPIA + DSA Pattern (DPIA-01)</h3>
<p><strong>Diagram block:</strong> [[DIAGRAM:approved-pattern-dpia-dsa]]</p>
<p><strong>Explanation:</strong> Shows privacy impact assessment and data sharing checkpoints through design, build, and operate stages.</p>

<h3>EDAP Integration Pattern (EDAP-01)</h3>
<p><strong>Diagram block:</strong> [[DIAGRAM:approved-pattern-edap]]</p>
<p><strong>Explanation:</strong> Shows how new analytics services integrate with EDAP as the target AWS analytics platform.</p>

<h2>Design Pick Checklist</h2>
<ul>
  <li>Selected pattern IDs captured in Section 8 of the main HLD page.</li>
  <li>Security and governance controls applied at Edge, Network, Platform, Application, and Data layers.</li>
  <li>DPIA/DSA obligations identified and linked to design decisions.</li>
  <li>EDAP integration confirmed for analytics requirements (or exception justified).</li>
</ul>

<h2>EDAP Integration Patterns</h2>
<p><em>The following patterns are sourced from the UKHSA Enterprise Data Analytics Platform (EDAP) — UKHSA's approved AWS analytical platform. All new data solutions with an analytics or reporting requirement must evaluate these patterns before designing a bespoke alternative.</em></p>
<p><strong>EDAP References:</strong>
  <a href="https://ukhsa.atlassian.net/wiki/spaces/EDAP/pages/165353198/AWS+High+Level+Design">EDAP AWS High Level Design</a> |
  <a href="https://ukhsa.atlassian.net/wiki/spaces/EDAP/pages/165357494/AWS+Technical+Design">EDAP AWS Technical Design</a>
</p>

<ac:structured-macro ac:name="info">
  <ac:parameter ac:name="title">EDAP Mandate</ac:parameter>
  <ac:rich-text-body>
    <p>Analytics workloads must integrate with EDAP as the target AWS analytics platform unless a formal exception is approved via the Architecture Review Board. Document your EDAP decision in Section 8 (Pattern Selection) of the HLD.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h3>EDAP-INT-01: Source2Ingest – SFTP Push Pattern</h3>
<p><em>Reference: EDAP AWS Technical Design §6.1</em></p>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>EDAP-INT-01</td></tr>
    <tr><th>Name</th><td>Source2Ingest – SFTP Push</td></tr>
    <tr><th>Use When</th><td>A third-party system initiates a file transfer into EDAP using SFTP protocol (push from external source)</td></tr>
    <tr><th>Integration Mechanism</th><td>Third party → Network Load Balancer (port 22, Elastic IPs per AZ) → AWS Transfer Family Server (VPC-hosted, Internal) → S3 Ingestion/Staging bucket → EventBridge notification → Antivirus scan → S3 Ingestion/Cleared → Step Functions Ingestion2Raw workflow</td></tr>
    <tr><th>Approved AWS Services</th><td>AWS Transfer Family (SFTP, domain: S3), Network Load Balancer, Amazon S3 (Ingestion Layer: Staging + Cleared sublayers), Amazon EventBridge, AWS IAM (per-user scoped S3 roles), AWS CloudWatch Logs</td></tr>
    <tr><th>Network Path</th><td>VPC-hosted Transfer Family endpoint (Internal access). Elastic IPs attached to NLB in public subnets per AZ. IP filtering performed by external firewall or Network ACL. No public S3 access — all traffic within VPC via S3 Gateway VPC Endpoint.</td></tr>
    <tr><th>Authentication</th><td>Service-managed identity provider on Transfer Family. Each source system has a dedicated Transfer Family user mapped to its own S3 bucket/prefix. IAM role per user scoped to target prefix only (trust: transfer.amazonaws.com).</td></tr>
    <tr><th>File Processing</th><td>Files land in Ingestion/Staging. Cloud Storage Security antivirus scans each file. Clean files move to Ingestion/Cleared (triggers I2R). Infected files quarantined. EventBridge filters error folders to suppress reprocessing loops.</td></tr>
    <tr><th>Encryption</th><td>SSE-KMS on all Ingestion S3 buckets. Bucket policy rejects unencrypted uploads and non-KMS encryption. Lifecycle rule moves objects to low-cost storage after 2 years. Transfer Family security policy: TransferSecurityPolicy-2020-06.</td></tr>
    <tr><th>Logging</th><td>Transfer Family activity logged to CloudWatch Logs group /aws/transfer/&lt;server-name&gt; via dedicated IAM logging role. S3 data events via CloudTrail.</td></tr>
  </tbody>
</table>

<h3>EDAP-INT-02: Source2Ingest – Pull-Based Ingestion Pattern</h3>
<p><em>Reference: EDAP AWS Technical Design §6.2 (SFTP Pull), §6.3 (REST API Pull), §6.5 (S3 Pull), §6.8 (Screen Scraping)</em></p>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>EDAP-INT-02</td></tr>
    <tr><th>Name</th><td>Source2Ingest – Pull-Based Ingestion (SFTP / REST API / S3)</td></tr>
    <tr><th>Use When</th><td>EDAP must retrieve data from an external system on a schedule — remote SFTP server, REST API, external S3 bucket, or web source</td></tr>
    <tr><th>Integration Mechanism</th><td>EventBridge scheduled rule → ECS Fargate task (containerised client: RClone for SFTP, custom Python for APIs, AWS Sync for S3) → AppConfig (task config, versioned JSON) + Secrets Manager (credentials) → S3 Ingestion/Staging bucket</td></tr>
    <tr><th>Approved AWS Services</th><td>Amazon ECS (Fargate), Amazon ECR (private repositories, vulnerability scanning enabled), Amazon EventBridge (scheduling), AWS AppConfig (configuration), AWS Secrets Manager (credentials), Amazon S3 (Ingestion Layer), AWS IAM</td></tr>
    <tr><th>Network Path</th><td>Fargate tasks run in private subnets. S3 and AppConfig accessed via VPC Gateway/Interface Endpoints. External API/SFTP calls routed through NAT Gateway in public subnets. ECR images pulled via ECR VPC Endpoint.</td></tr>
    <tr><th>Configuration</th><td>All task parameters (origin, credentials reference, target bucket/prefix, directories) stored in AWS AppConfig as versioned JSON documents. Credential secrets stored in AWS Secrets Manager — never in AppConfig or task definition.</td></tr>
    <tr><th>AppFlow Alternative</th><td>Where an Amazon AppFlow native connector exists for the source SaaS system, AppFlow is the preferred option over a custom Fargate container (per Prefer Native AWS Services principle).</td></tr>
    <tr><th>Mandatory Controls</th><td>ECR repositories private; images scanned on push; task IAM role scoped to target S3 prefix only; concurrent executions limited by EventBridge schedule configuration; logs written to CloudWatch via awslogs driver.</td></tr>
  </tbody>
</table>

<h3>EDAP-INT-03: Source2Ingest – Streaming and Event Ingestion Pattern</h3>
<p><em>Reference: EDAP AWS Technical Design §6.4 (Stream), §6.13 (Event)</em></p>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>EDAP-INT-03</td></tr>
    <tr><th>Name</th><td>Source2Ingest – Streaming and Event-Based Ingestion</td></tr>
    <tr><th>Use When</th><td>A third-party system sends continuous streamed records or discrete EventBridge events that must land directly in the EDAP Raw Layer in near-real-time (bypasses Ingestion Layer)</td></tr>
    <tr><th>Integration Mechanism</th><td><strong>Streaming:</strong> Source → Kinesis Firehose Delivery Stream (Direct PUT) → Lambda transformation (RRD tagging + Parquet conversion, AppConfig-driven) → S3 Raw Layer (Parquet, Snappy compressed). <strong>Event:</strong> Third-party EventBridge source → EventBridge Rule (cross-account) → Kinesis Firehose → Lambda → S3 Raw Layer.</td></tr>
    <tr><th>Approved AWS Services</th><td>Amazon Kinesis Data Firehose, AWS Lambda (data transformation + RRD tagging), Amazon EventBridge (cross-account event bus rules), Amazon S3 (Raw Layer), AWS AppConfig (transformation config), AWS KMS (stream + bucket encryption)</td></tr>
    <tr><th>Data Format</th><td>Kinesis Firehose record format conversion enabled. Output: Apache Parquet, Snappy compression. Schema derived from Glue Data Catalog. RRD metadata columns added by Lambda (SourceSystemId, DataPipelineId, VisibilityCode, timestamps).</td></tr>
    <tr><th>Error Handling</th><td>Failed Lambda transformation records delivered to S3 processing-failed prefix. CloudWatch Firehose metrics monitored. Lambda logs errors to CloudWatch under /aws/lambda/&lt;function-name&gt;.</td></tr>
    <tr><th>Kafka Integration</th><td>Kafka sources use AWSLabs kinesis-kafka-connector in a Fargate container. Connector config fetched from AppConfig on startup (topics, Delivery Stream target).</td></tr>
    <tr><th>Mandatory Controls</th><td>KMS CMK encryption on Firehose queue and target S3 bucket; EventBridge resource policy restricts source accounts; IAM role per stream source scoped to target Firehose only; persistence KMS-configured on Delivery Stream; buffer size/timeout configured per stream requirements.</td></tr>
  </tbody>
</table>

<h3>EDAP-INT-04: Source2Ingest – Azure / Cross-Cloud Object Storage Ingestion Pattern</h3>
<p><em>Reference: EDAP AWS Technical Design §6.7 (Azure Object Storage Pull), §6.10 (S3 Replication), §6.12 (DMS)</em></p>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>EDAP-INT-04</td></tr>
    <tr><th>Name</th><td>Source2Ingest – Azure / Cross-Cloud and Database Migration Ingestion</td></tr>
    <tr><th>Use When</th><td>Source data resides in Azure Blob Storage, an external AWS S3 bucket, or an external relational database requiring bulk or incremental migration into EDAP</td></tr>
    <tr><th>Integration Mechanism</th><td><strong>Azure Blob:</strong> AWS DataSync Agent (deployed as VHD in Azure) → DataSync Task (scheduled) → S3 Ingestion/Staging. <strong>External S3:</strong> AWS DataSync S3 Locations (source + target) → DataSync Task → S3 Ingestion/Staging. <strong>Database:</strong> AWS DMS Replication Task (per source database) → S3 Ingestion Layer.</td></tr>
    <tr><th>Approved AWS Services</th><td>AWS DataSync (tasks, schedules, S3/Azure locations), AWS DataSync Agent (VHD deployment in Azure), AWS DMS (Database Migration Service), Amazon S3 (Ingestion Layer), AWS IAM (source + target roles), AWS CloudWatch (DataSync monitoring)</td></tr>
    <tr><th>Authentication – Azure</th><td>AWS DataSync Agent authenticates to Azure Blob using Azure storage account credentials. UKHSA Azure AD (Entra ID) federated to AWS IAM via IAM Federation for human-operated tasks. AD Connector for AWS Workspaces user authentication.</td></tr>
    <tr><th>Network Path</th><td>DataSync Agent in Azure communicates outbound to AWS DataSync service endpoints over HTTPS. No inbound firewall rules required in Azure. DataSync Agent in AWS scenario uses IAM roles; no agent required for AWS-to-AWS S3 transfers.</td></tr>
    <tr><th>Alternative (SFTP Pull)</th><td>For Azure-sourced data that does not use Blob Storage, the SFTP Pull Fargate pattern (EDAP-INT-02) using RClone with Azure as source is a supported alternative.</td></tr>
    <tr><th>Mandatory Controls</th><td>DataSync CloudWatch log group configured with resource policy granting DataSync permissions; IAM roles scoped to source/target prefixes; KMS encryption on target S3 buckets; DMS source endpoints require read-only database credentials in Secrets Manager; CloudTrail data events on Ingestion buckets.</td></tr>
  </tbody>
</table>

<h3>EDAP-INT-05: Ingestion-to-Raw (I2R) Processing Pipeline Pattern</h3>
<p><em>Reference: EDAP AWS Technical Design §8 (Ingestion2Raw), §8.1 (RRD Tagging), §10 (Raw2Conform)</em></p>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>EDAP-INT-05</td></tr>
    <tr><th>Name</th><td>Ingestion2Raw and Raw2Conform Processing Pipeline</td></tr>
    <tr><th>Use When</th><td>File-based ingested data in the Ingestion/Cleared sublayer must be validated, quality-checked, transformed to Parquet, RRD-tagged, and written to the Raw Layer; and subsequently conformed and written to the Conform Layer</td></tr>
    <tr><th>Integration Mechanism</th><td><strong>I2R:</strong> EventBridge (S3 Ingestion/Cleared object created) → Step Functions I2R Workflow → Lambda (file format check → integrity check) → Glue DataBrew Profile Job (data quality) → Glue Job (Parquet transform + RRD tagging + Snappy compression) → S3 Raw Layer → Glue Crawler → Glue Data Catalog → Lake Formation. <strong>R2C:</strong> EventBridge (S3 Raw object or schedule) → Step Functions R2C Workflow → Glue Job (generic transform/copy, lookup, DataBrew transforms) → S3 Conform Layer → Redshift Spectrum (external tables) → Glue Crawler → Lake Formation.</td></tr>
    <tr><th>Approved AWS Services</th><td>AWS Step Functions, AWS Lambda, AWS Glue (Jobs + DataBrew + Crawlers), Amazon S3 (Ingestion / Raw / Conform layers), Amazon SQS (lineage messages), AWS AppConfig (pipeline configuration), AWS Lake Formation (TBAC, filters, grants), Amazon Redshift (Spectrum external tables), AWS KMS, Amazon DynamoDB (workflow synchronisation)</td></tr>
    <tr><th>RRD Tagging</th><td>Every Parquet file written to Raw Layer includes RRD metadata columns: CreatedBy, CreatedDate, LastUpdatedBy, LastUpdatedDate, SourceSystemId (format: S-XXXXXXXX), DataPipelineId (format: P-XXXXXXXX), SourceFileName, VisibilityCode (default: V-ZZZZZZ). Added by the Glue Parquet Transform Job and Lambda in streaming path.</td></tr>
    <tr><th>Configuration</th><td>All I2R and R2C workflow steps driven by AppConfig versioned JSON per feed. Enables single generic Step Functions state machine for all feeds. Feed-specific Glue DataBrew Profile Jobs and transformation configs registered per origin.</td></tr>
    <tr><th>Data Lineage</th><td>Every workflow step emits OpenLineage format messages to SQS Lineage Queue on START and END. Messages include job name, hierarchy, versions, data sources/targets, column-level lineage, SQL executed. Consumed by Data Governance tool.</td></tr>
    <tr><th>Access Control</th><td>All Lambda and Glue Jobs use VPC network interfaces. S3 and service access via VPC Endpoints (Gateway for S3, Interface for others). Lake Formation Tag-Based Access Control (TBAC) on Raw and Conform layer tables. Column-level and row-level grants per role.</td></tr>
    <tr><th>Mandatory Controls</th><td>SSE-KMS on all Raw and Conform S3 buckets; bucket policy rejects non-KMS uploads; Lifecycle rules per bucket; EventBridge filters error prefixes to prevent reprocessing loops; Glue job continuous logging to CloudWatch (/aws-glue/jobs/logs-v2); DataBrew quality failures halt pipeline and raise CloudWatch alarm.</td></tr>
  </tbody>
</table>

<h3>EDAP-INT-06: Analytics Access, Virtualisation and Export Pattern</h3>
<p><em>Reference: EDAP AWS Technical Design §14 (Export), §15 (Power BI), §16 (Data Virtualisation), §17 (Data Science), §18.6 (End User Auth)</em></p>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>EDAP-INT-06</td></tr>
    <tr><th>Name</th><td>Analytics Access, Data Virtualisation and Export</td></tr>
    <tr><th>Use When</th><td>Data scientists, BI dashboards, or external consumers need to query, visualise, or export data from EDAP's Raw, Conform, or DataMart layers</td></tr>
    <tr><th>Integration Mechanism</th><td><strong>Ad-hoc Query (Data Scientists):</strong> Azure AD → IAM Federation → Athena Workgroup (per user) → Lake Formation → S3 Raw/Conform (Parquet) via Glue Catalog. Athena JDBC/ODBC with Azure AD integration for authentication. <strong>Dashboards (Power BI):</strong> Power BI Gateway (EC2, Windows, ≥2 instances, private subnets, multi-AZ) → Redshift (direct VPC) or Athena (VPC Endpoint). Power BI Service connects via HTTPS to Microsoft Azure Service Bus. <strong>Data Science/ML:</strong> SageMaker Notebook (VPC-only domain) → Lake Formation → Conform/DataMart via VPC Endpoints or Athena Federated Queries (Redshift Connector Lambda). <strong>Export API:</strong> Redshift Data API → API Gateway (Route53) → authenticated consumer. <strong>Scheduled Export:</strong> Step Functions Export Flow → Glue Job → Export Store (S3, Parquet) or Kinesis Data Stream.</td></tr>
    <tr><th>Approved AWS Services</th><td>Amazon Athena (Workgroups, Federated Queries), Amazon Redshift (RA3 nodes, Spectrum, Data API), AWS Lake Formation, AWS Glue Data Catalog, Amazon QuickSight (Enterprise, VPC connection), Amazon SageMaker (Notebook instances, Model Registry, Batch Transform), Amazon WorkSpaces (AD Connector, Amazon Linux bundles), AWS Step Functions (Export Flow), Amazon Kinesis Data Streams (Export Stream), Amazon API Gateway, Amazon Route53, AWS KMS</td></tr>
    <tr><th>Authentication</th><td>UKHSA Azure AD (Entra ID) federated to AWS IAM via IAM Federation. AD Connector bridges Azure AD to AWS Workspaces directory. MFA enforced for all user accounts. Athena access authenticated via Azure AD using Athena JDBC/ODBC drivers. Redshift user-activity logs sent to CloudWatch. IAM roles are read-only on required datasets only.</td></tr>
    <tr><th>Data Scientist Workspaces</th><td>Amazon WorkSpaces in a dedicated VPC (separate from processing VPC per AWS recommendation). Predefined Amazon Linux hardened bundles with pre-installed git client. OS patches managed at OS level; tool patches via Amazon WorkSpaces Application Manager.</td></tr>
    <tr><th>Export Controls</th><td>Export Store S3 buckets: SSE-KMS encryption, lifecycle rules. Export Flow triggered by: scheduled EventBridge rules, S3 event notifications, manual API/Console invocation, or end-of-pipeline EventBridge events. All exported files crawled and registered in Glue Catalog. Kinesis Data Streams per export topic: SSE-KMS encrypted.</td></tr>
    <tr><th>Mandatory Controls</th><td>Athena per-user Workgroup with dedicated S3 query results bucket (SSE-KMS); Lake Formation fine-grained access enforced for all Athena and Redshift Spectrum queries; Power BI Gateway RDP access restricted by Security Group; Redshift not internet-facing (private subnets); all Redshift audit logs to CloudWatch; API Gateway with Route53 for Export REST API; QuickSight Enterprise enabled in account.</td></tr>
  </tbody>
</table>

<h3>EDAP Integration Pattern Summary</h3>
<table>
  <thead>
    <tr><th>Pattern ID</th><th>Name</th><th>Primary Use Case</th><th>Key AWS Services</th><th>EDAP Layer</th></tr>
  </thead>
  <tbody>
    <tr><td>EDAP-INT-01</td><td>Source2Ingest – SFTP Push</td><td>Third-party pushes files via SFTP into EDAP</td><td>Transfer Family, NLB, S3, EventBridge, Antivirus (Cloud Storage Security)</td><td>Ingestion (Staging → Cleared)</td></tr>
    <tr><td>EDAP-INT-02</td><td>Source2Ingest – Pull Ingestion</td><td>EDAP pulls from SFTP servers, REST APIs, or S3</td><td>ECS Fargate, ECR, AppConfig, Secrets Manager, EventBridge, S3</td><td>Ingestion (Staging)</td></tr>
    <tr><td>EDAP-INT-03</td><td>Source2Ingest – Streaming / Event</td><td>Continuous streamed records or EventBridge events into Raw Layer</td><td>Kinesis Firehose, Lambda, EventBridge, AppConfig, KMS</td><td>Raw (direct — bypasses Ingestion)</td></tr>
    <tr><td>EDAP-INT-04</td><td>Source2Ingest – Azure / Cross-Cloud</td><td>Sync from Azure Blob, external S3, or external databases</td><td>AWS DataSync, DataSync Agent (Azure VHD), AWS DMS, S3, IAM</td><td>Ingestion (Staging)</td></tr>
    <tr><td>EDAP-INT-05</td><td>Ingestion2Raw + Raw2Conform Pipeline</td><td>Transform, quality-check, RRD-tag, Parquet-convert and govern ingested data</td><td>Step Functions, Glue (Jobs/DataBrew/Crawlers), Lambda, Lake Formation, SQS (lineage), AppConfig, Redshift Spectrum</td><td>Ingestion/Cleared → Raw → Conform</td></tr>
    <tr><td>EDAP-INT-06</td><td>Analytics Access and Export</td><td>Query, visualise, ML, and export data from EDAP layers</td><td>Athena, Redshift, Lake Formation, SageMaker, WorkSpaces, Power BI Gateway, QuickSight, API Gateway, Kinesis Streams</td><td>Raw / Conform / DataMart</td></tr>
  </tbody>
</table>

<!-- ============================================================ -->
<!-- SECTION: UKHSA INFRASTRUCTURE PATTERNS                        -->
<!-- Source: Baseline Current State Architecture (Sections 3–6)   -->
<!-- ============================================================ -->

<h2>UKHSA Infrastructure Patterns</h2>
<p><em>Sourced from the <strong>UKHSA Baseline Current State Architecture</strong>. These patterns define the approved landing zone, connectivity, identity, DNS, and platform structures that all workloads must align with. Deviations require Architecture Review Board approval.</em></p>

<h3>UKHSA-INF-01: Landing Zone Pattern</h3>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>UKHSA-INF-01</td></tr>
    <tr><th>Name</th><td>UKHSA Strategic Landing Zone Placement</td></tr>
    <tr><th>Strategic Landing Zones</th><td><strong>UKHSA Azure LZ</strong> (PHECloud tenant) — primary Azure target; <strong>UKHSA AWS LZ</strong> (HALO / Test &amp; Trace accounts) — primary AWS target</td></tr>
    <tr><th>Legacy LZs (Decommissioning)</th><td>PHE Azure LZ, NIHP Azure LZ, PHE AWS LZ — all being decommissioned. No new workloads permitted.</td></tr>
    <tr><th>Mandate</th><td>All new workloads must be deployed to a strategic landing zone only. Existing workloads in legacy LZs must have a migration plan to the strategic target.</td></tr>
    <tr><th>Key Observations (Baseline)</th><td>Lift-and-shift migrations limit cloud-native capabilities. Workloads in wrong LZs create security and compliance risk. Legacy LZs add complexity and security exposure. No standardised data lifecycle controls exist across LZs.</td></tr>
    <tr><th>Reference Section</th><td>Baseline Current State Architecture §3</td></tr>
  </tbody>
</table>

<h3>UKHSA-INF-02: Hybrid Connectivity Pattern</h3>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>UKHSA-INF-02</td></tr>
    <tr><th>Name</th><td>Hybrid Cloud Connectivity (Direct Connect + ExpressRoute)</td></tr>
    <tr><th>AWS Connectivity</th><td>AWS Direct Connect to on-premises data centres (Porton Down + Colindale)</td></tr>
    <tr><th>Azure Connectivity</th><td>Azure ExpressRoute to on-premises data centres (Porton Down + Colindale)</td></tr>
    <tr><th>WAN</th><td>Virgin Media MPLS WAN connecting sites and data centres</td></tr>
    <tr><th>Internet Access</th><td>No direct internet to cloud landing zones. All internet-bound traffic currently routed through on-premises data centres (bottleneck — target state will address).</td></tr>
    <tr><th>East-West (Azure ↔ AWS)</th><td>Cross-cloud traffic currently routed via on-premises data centres. No direct LZ-to-LZ connectivity (gap to be addressed in target state).</td></tr>
    <tr><th>Firewall</th><td>Palo Alto firewalls manage North-South (N/S) traffic at DC perimeter</td></tr>
    <tr><th>Key Observations (Baseline)</th><td>Traffic to strategic LZs still routed through legacy infrastructure (latency, complexity, security risk). No direct connectivity between strategic LZs across cloud providers. Internet-bound traffic via on-prem creates bottlenecks. Centralised firewalls limit scalability.</td></tr>
    <tr><th>Reference Section</th><td>Baseline Current State Architecture §4</td></tr>
  </tbody>
</table>

<h3>UKHSA-INF-03: Zero Trust End-User Access Pattern</h3>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>UKHSA-INF-03</td></tr>
    <tr><th>Name</th><td>Zero Trust End-User Internet Access (zScaler)</td></tr>
    <tr><th>Technology</th><td>zScaler Zero Trust Exchange — cloud-native ZTNA/SWG proxy for all end-user internet access</td></tr>
    <tr><th>Mandate</th><td>No direct internet traversal for end users. All outbound internet traffic inspected via zScaler Zero Trust Exchange.</td></tr>
    <tr><th>ADR Alignment</th><td>ADR-010 (Zero Trust Network Architecture)</td></tr>
    <tr><th>Reference Section</th><td>Baseline Current State Architecture §4</td></tr>
  </tbody>
</table>

<h3>UKHSA-INF-04: Split-Horizon DNS Pattern</h3>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>UKHSA-INF-04</td></tr>
    <tr><th>Name</th><td>Split-Horizon DNS Architecture</td></tr>
    <tr><th>Public DNS — Legacy</th><td>ukhsa.gov.uk and phe.gov.uk hosted in PHE Azure LZ (legacy). Not yet in AWS — limits AWS-native integration.</td></tr>
    <tr><th>Public DNS — Strategic</th><td>test-and-trace.gov.uk hosted in AWS (strategic target). Route 53 used for cloud-native DNS resolution.</td></tr>
    <tr><th>Private DNS</th><td>All landing zones and on-premises data centres (Porton + Colindale) resolve private DNS from on-premises DC DNS servers. DNS queries forwarded between multiple DCs (latency/complexity).</td></tr>
    <tr><th>Key Observations (Baseline)</th><td>DNS queries forwarded between multiple DCs add latency and complexity. ukhsa.gov.uk/phe.gov.uk not in AWS limits AWS-native DNS integration. Target state should consolidate DNS into Route 53 with Private Hosted Zones.</td></tr>
    <tr><th>Reference Section</th><td>Baseline Current State Architecture §4</td></tr>
  </tbody>
</table>

<h3>UKHSA-INF-05: Federated Identity Pattern</h3>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>UKHSA-INF-05</td></tr>
    <tr><th>Name</th><td>Federated Identity — Microsoft Entra ID as Golden Source</td></tr>
    <tr><th>Golden Source IdP</th><td>Microsoft Entra ID (UKHSA tenant, PHECloud) — single source of truth for all identities</td></tr>
    <tr><th>AWS Integration</th><td>SCIM provisioning from Entra ID → AWS IAM Identity Center. Federated SSO for all AWS console and CLI access.</td></tr>
    <tr><th>On-Prem Sync</th><td>Entra ID ↔ on-premises Active Directory sync via Entra ID Connect</td></tr>
    <tr><th>SaaS Federation</th><td>Entra ID federated to: Microsoft 365, Atlassian (Confluence/Jira), MAPS, CIMS, and other approved SaaS platforms</td></tr>
    <tr><th>MFA</th><td>MFA enforced for all user accounts. No exceptions without ARB approval.</td></tr>
    <tr><th>Local Accounts Prohibition</th><td>Local user accounts in workload accounts are prohibited. Enforced via AWS Service Control Policies (SCPs) at the Organization level.</td></tr>
    <tr><th>Key Observations (Baseline)</th><td>Use of local accounts in workload accounts creates credential sprawl and audit risk. Centralised identity team creates bottlenecks — delegated administration model needed. RBAC using centrally managed identities required.</td></tr>
    <tr><th>ADR Alignment</th><td>ADR-010 (Zero Trust)</td></tr>
    <tr><th>Reference Section</th><td>Baseline Current State Architecture §5</td></tr>
  </tbody>
</table>

<h3>UKHSA-INF-06: Platform-in-Platform Pattern</h3>
<table>
  <tbody>
    <tr><th>Pattern ID</th><td>UKHSA-INF-06</td></tr>
    <tr><th>Name</th><td>Approved Platform Portfolio (Platform-in-Platform)</td></tr>
    <tr><th>Approved Compute Platforms</th><td>
      <strong>EDAP</strong> — AWS-hosted enterprise data analytics platform (mandatory for analytics workloads)<br/>
      <strong>VMware on Azure</strong> — legacy virtualisation in Azure LZ (migration target; new VMware deployments discouraged)<br/>
      <strong>HPC (High Performance Computing)</strong> — on-premises at Porton Down and Colindale DCs
    </td></tr>
    <tr><th>Approved Shared Services</th><td>
      <strong>Microsoft Sentinel</strong> — SIEM/SOAR for centralised security monitoring<br/>
      <strong>Azure API Management (APIM)</strong> — centralised API gateway and lifecycle management<br/>
      <strong>Azure Virtual Desktop (AVD)</strong> — virtual desktop infrastructure (replacing legacy VDI)<br/>
      <strong>SGSS</strong> — shared government security service<br/>
      <strong>Atlassian</strong> — Confluence and Jira (hosted + Atlassian Cloud)
    </td></tr>
    <tr><th>Key Observations (Baseline)</th><td>Key applications remain in legacy LZs, increasing technical debt and security risk. VMware on Azure limits scalability and prevents use of Azure-native services. Strategic workloads must be refactored during migration to benefit from cloud-native services.</td></tr>
    <tr><th>Reference Section</th><td>Baseline Current State Architecture §6</td></tr>
  </tbody>
</table>

<h3>Infrastructure Pattern Summary</h3>
<table>
  <thead>
    <tr><th>Pattern ID</th><th>Name</th><th>Area</th><th>Key Technology</th><th>Mandate</th></tr>
  </thead>
  <tbody>
    <tr><td>UKHSA-INF-01</td><td>Strategic Landing Zone Placement</td><td>Landing Zones</td><td>UKHSA Azure LZ (PHECloud), UKHSA AWS LZ (HALO)</td><td>All new workloads to strategic LZs only</td></tr>
    <tr><td>UKHSA-INF-02</td><td>Hybrid Cloud Connectivity</td><td>Networking</td><td>AWS Direct Connect, Azure ExpressRoute, Virgin Media MPLS, Palo Alto</td><td>No direct internet to LZs; on-prem DC as transit hub</td></tr>
    <tr><td>UKHSA-INF-03</td><td>Zero Trust End-User Access</td><td>Networking / Security</td><td>zScaler Zero Trust Exchange</td><td>All user internet traffic via zScaler — no direct traversal</td></tr>
    <tr><td>UKHSA-INF-04</td><td>Split-Horizon DNS</td><td>Networking / DNS</td><td>Route 53 (strategic), on-prem DC DNS (private), Azure (legacy public)</td><td>Private DNS resolved from on-prem DCs; public DNS per domain</td></tr>
    <tr><td>UKHSA-INF-05</td><td>Federated Identity</td><td>Identity &amp; Access</td><td>Microsoft Entra ID, AWS IAM Identity Center, SCIM, MFA, SCPs</td><td>No local accounts; federated auth mandatory; MFA enforced</td></tr>
    <tr><td>UKHSA-INF-06</td><td>Platform Portfolio</td><td>Platforms &amp; Services</td><td>EDAP, VMware/Azure, HPC, Sentinel, APIM, AVD, Atlassian</td><td>EDAP mandatory for analytics; VMware migration in progress</td></tr>
  </tbody>
</table>

<!-- ============================================================ -->
<!-- SECTION: UKHSA APPROVED DATA PATTERNS (28 PATTERNS, 8 LAYERS) -->
<!-- Source: UKHSA Cloud Strategy & Approved Patterns              -->
<!-- ============================================================ -->

<h2>UKHSA Approved Data Patterns</h2>
<p><em>Sourced from the <strong>UKHSA Cloud Strategy &amp; Approved Patterns</strong>. These 28 patterns cover the full data lifecycle across 8 layers. All new data workloads must select from this catalogue or document a justified exception via the Architecture Review Board.</em></p>

<h3>Layer 1 — Data Ingestion</h3>
<table>
  <thead>
    <tr><th>Pattern ID</th><th>Name</th><th>Use When</th><th>Approved AWS Services</th></tr>
  </thead>
  <tbody>
    <tr><td>1A</td><td>Direct API Ingestion</td><td>Real-time or continuous feeds from external APIs</td><td>API Gateway, SQS, EventBridge</td></tr>
    <tr><td>1B</td><td>Batch File Upload</td><td>Bulk scheduled file transfers from external sources</td><td>Amazon S3, AWS Glue, AWS Transfer Family (SFTP)</td></tr>
    <tr><td>1C</td><td>Database Replication</td><td>Sync operational/on-prem database to cloud for analytics or DR</td><td>AWS DMS, Amazon RDS, Amazon Aurora</td></tr>
    <tr><td>1D</td><td>Streaming Ingestion</td><td>High-speed sensor data, metrics, IoT, or event streams</td><td>Amazon Kinesis, Amazon MSK (Kafka), AWS Lambda</td></tr>
  </tbody>
</table>

<h3>Layer 2 — Data Processing</h3>
<table>
  <thead>
    <tr><th>Pattern ID</th><th>Name</th><th>Use When</th><th>Approved AWS Services</th></tr>
  </thead>
  <tbody>
    <tr><td>2A</td><td>Batch ETL</td><td>Nightly or scheduled large-volume data transformation jobs</td><td>AWS Glue, AWS Step Functions, AWS Glue DataBrew</td></tr>
    <tr><td>2B</td><td>Real-Time Stream Processing</td><td>Instant anomaly detection, live dashboards, or real-time alerting</td><td>Amazon Kinesis Data Analytics, AWS Lambda</td></tr>
    <tr><td>2C</td><td>Scheduled Spark / ML Jobs</td><td>ML model training or large-scale Spark processing that runs then stops</td><td>Amazon EMR, Amazon SageMaker</td></tr>
    <tr><td>2D</td><td>Federated Query</td><td>Cross-dataset analysis without copying data between stores</td><td>Amazon Athena, Amazon Redshift Spectrum</td></tr>
  </tbody>
</table>

<h3>Layer 3 — Data Storage</h3>
<table>
  <thead>
    <tr><th>Pattern ID</th><th>Name</th><th>Use When</th><th>Approved AWS Services</th><th>ADR Alignment</th></tr>
  </thead>
  <tbody>
    <tr><td>3A</td><td>Transactional Database (OLTP)</td><td>Operational systems requiring ACID transactions</td><td>Amazon Aurora PostgreSQL, Amazon RDS, Amazon DynamoDB</td><td>ADR-001 (Aurora PostgreSQL preferred)</td></tr>
    <tr><td>3B</td><td>Data Warehouse (OLAP)</td><td>Historical reporting and complex analytical queries across large datasets</td><td>Amazon Redshift, Amazon QuickSight</td><td>ADR-003 (&gt;100GB use Redshift Spectrum)</td></tr>
    <tr><td>3C</td><td>Data Lake (Bronze/Silver/Gold)</td><td>Centralised storage for raw, conformed, and curated datasets</td><td>Amazon S3, AWS Glue Data Catalog, AWS Lake Formation</td><td>ADR-002 (S3+Glue not HDFS), ADR-007 (Bronze/Silver/Gold tiers)</td></tr>
    <tr><td>3D</td><td>Time-Series Database</td><td>Lab capacity, infection rates, or any metric captured per minute/second</td><td>Amazon Timestream</td><td></td></tr>
    <tr><td>3E</td><td>Document Store</td><td>Nested, variable-structure, or schema-flexible data</td><td>Amazon DynamoDB, Amazon DocumentDB, Amazon OpenSearch</td><td></td></tr>
  </tbody>
</table>

<h3>Layer 4 — Data Integration</h3>
<table>
  <thead>
    <tr><th>Pattern ID</th><th>Name</th><th>Use When</th><th>Approved AWS Services</th><th>ADR Alignment</th></tr>
  </thead>
  <tbody>
    <tr><td>4A</td><td>Event-Driven Pipelines</td><td>Loosely-coupled services that react to data changes or domain events</td><td>Amazon EventBridge, Amazon SQS, Amazon SNS, AWS Lambda</td><td>ADR-004 (EventBridge over SNS/SQS for routing)</td></tr>
    <tr><td>4B</td><td>ETL Orchestration</td><td>Complex multi-step workflows with dependencies, retries, and branching logic</td><td>AWS Step Functions, Apache Airflow (MWAA)</td><td></td></tr>
    <tr><td>4C</td><td>Data Replication &amp; Sync</td><td>High availability, compliance archiving, or multi-region data copies</td><td>Amazon S3 Cross-Region Replication (CRR), Amazon RDS Read Replicas</td><td></td></tr>
  </tbody>
</table>

<h3>Layer 5 — Data Governance</h3>
<table>
  <thead>
    <tr><th>Pattern ID</th><th>Name</th><th>Use When</th><th>Approved AWS Services</th></tr>
  </thead>
  <tbody>
    <tr><td>5A</td><td>Centralised Data Catalogue</td><td>Discoverability, metadata management, and access control across all datasets</td><td>AWS Glue Data Catalog, AWS Lake Formation</td></tr>
    <tr><td>5B</td><td>Data Quality &amp; Validation</td><td>Automated quality checks before data is promoted between layers</td><td>AWS Glue DataBrew, Glue Quality Checks, Amazon EventBridge (alerting)</td></tr>
    <tr><td>5C</td><td>Data Lineage &amp; Audit Trail</td><td>Regulatory compliance, root-cause analysis, and data provenance tracking</td><td>AWS Lake Formation (lineage), AWS CloudTrail, Amazon S3 access logs</td></tr>
  </tbody>
</table>

<h3>Layer 6 — Security &amp; Compliance (MANDATORY)</h3>
<ac:structured-macro ac:name="warning">
  <ac:parameter ac:name="title">Mandatory — All Data Workloads</ac:parameter>
  <ac:rich-text-body>
    <p>Layer 6 patterns are not optional. Every data workload must implement all four security patterns. Document compliance in Section 8 (Pattern Selection) of the HLD.</p>
  </ac:rich-text-body>
</ac:structured-macro>
<table>
  <thead>
    <tr><th>Pattern ID</th><th>Name</th><th>What It Covers</th><th>Approved AWS Services</th><th>ADR Alignment</th></tr>
  </thead>
  <tbody>
    <tr><td>6A</td><td>Access Control</td><td>Fine-grained identity-based access to data assets</td><td>AWS IAM + Microsoft Entra ID (federated), AWS Lake Formation, Amazon S3 Object Lock, MFA (mandatory)</td><td>ADR-010 (Zero Trust)</td></tr>
    <tr><td>6B</td><td>Encryption &amp; Key Management</td><td>Data at-rest and in-transit encryption with managed key lifecycle</td><td>AWS KMS (customer-managed CMKs for sensitive data), AWS Secrets Manager, AWS ACM, TLS 1.2+ enforced</td><td>ADR-005 (TLS 1.2+), ADR-006 (CMK for sensitive data)</td></tr>
    <tr><td>6C</td><td>Network Security &amp; Isolation</td><td>Network-level controls preventing data exfiltration and lateral movement</td><td>Amazon VPC, Security Groups, VPC Endpoints (Gateway + Interface), AWS PrivateLink, AWS WAF</td><td>ADR-010 (Zero Trust)</td></tr>
    <tr><td>6D</td><td>Data Masking &amp; Anonymisation</td><td>PII/sensitive data de-identification for non-production and analytics use</td><td>AWS Glue DataBrew (masking transforms), AWS Lambda (custom anonymisation), Amazon RDS, Amazon Redshift</td><td></td></tr>
  </tbody>
</table>

<h3>Layer 7 — Monitoring &amp; Observability</h3>
<table>
  <thead>
    <tr><th>Pattern ID</th><th>Name</th><th>Use When</th><th>Approved AWS Services</th></tr>
  </thead>
  <tbody>
    <tr><td>7A</td><td>Centralised Logging</td><td>Unified audit trail, security investigation, and operational diagnostics</td><td>Amazon CloudWatch Logs, AWS X-Ray, Amazon EventBridge, AWS CloudTrail</td></tr>
    <tr><td>7B</td><td>Performance Monitoring &amp; Alerting</td><td>Proactive detection of degradation, capacity issues, or SLA breaches</td><td>Amazon CloudWatch Metrics, CloudWatch Alarms, Amazon SNS</td></tr>
    <tr><td>7C</td><td>Cost Tracking &amp; Optimisation</td><td>FinOps — spend visibility, anomaly detection, and rightsizing recommendations</td><td>AWS Cost Explorer, AWS Budgets, AWS Compute Optimizer</td></tr>
  </tbody>
</table>

<h3>Layer 8 — Resilience &amp; Disaster Recovery</h3>
<table>
  <thead>
    <tr><th>Pattern ID</th><th>Name</th><th>Use When</th><th>Approved AWS Services</th></tr>
  </thead>
  <tbody>
    <tr><td>8A</td><td>Backup &amp; Point-in-Time Recovery</td><td>Data protection against accidental deletion, corruption, or ransomware</td><td>AWS Backup, Amazon RDS automated snapshots, Amazon S3 Versioning</td></tr>
    <tr><td>8B</td><td>Multi-Region Failover</td><td>Business continuity for critical workloads with low RTO/RPO requirements</td><td>Amazon Route 53 (health-check based failover), Amazon S3 Cross-Region Replication, Amazon RDS Read Replicas (cross-region)</td></tr>
  </tbody>
</table>

<!-- ============================================================ -->
<!-- SECTION: UKHSA TARGET STATE ARCHITECTURE                      -->
<!-- Source: Target State Architecture v1.0 (Mar 2025)            -->
<!-- Authors: Thomas Larsen, Dan Farrar — Cloud Architecture Team -->
<!-- ============================================================ -->

<h2>UKHSA Target State Architecture</h2>
<p><em>Sourced from the <strong>UKHSA Target State Architecture v1.0 (March 2025)</strong>, authored by the Cloud Architecture Team (CCoE). This document sets the recommended target state across Landing Zones, Networking, Identity, and Platforms &amp; Services. All new work should align with this target state or document a justified interim decision via the Architecture Review Board.</em></p>

<ac:structured-macro ac:name="info">
  <ac:parameter ac:name="title">Who This Applies To</ac:parameter>
  <ac:rich-text-body>
    <p><strong>Application &amp; delivery teams</strong> — adopt pre-approved designs to accelerate route-to-live.<br/>
    <strong>Platform engineers</strong> — implement shared services consistently across landing zones.<br/>
    <strong>Solution &amp; enterprise architects</strong> — ensure new work aligns with UKHSA Cloud Strategy and these principles.<br/>
    <strong>Governance, risk &amp; compliance leads</strong> — trace design decisions back to the CCF and UKHSA standards.<br/>
    <strong>FinOps practitioners</strong> — understand architectural levers for cost control and financial accountability.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h3>TSA-LZ: Landing Zones Target State</h3>
<p><em>Target State Architecture §2 — Landing Zones</em></p>
<table>
  <thead>
    <tr><th>#</th><th>Principle</th><th>Description</th><th>Key Implementation Steps</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>Standardised &amp; Secure Landing Zones</td><td>All LZs follow a security-hardened baseline for compliance and operational consistency</td><td>Define LZ blueprints; use Terraform / AWS Control Tower (AWS) and Azure Landing Zone Accelerator (Azure); automate account/subscription vending via IaC</td></tr>
    <tr><td>2</td><td>Automated LZ Provisioning</td><td>Reduce manual provisioning through automation and governance controls</td><td>Self-service provisioning pipelines; enforce Azure Policy + AWS SCPs; integrate centralised IAM for automatic role assignments</td></tr>
    <tr><td>3</td><td>Multi-Cloud Strategy &amp; Resilience</td><td>Support workloads across AWS and Azure with consistent governance and resilience</td><td>Define cross-cloud governance framework; implement cloud-agnostic workload placement policies; ensure network interoperability between LZs</td></tr>
    <tr><td>4</td><td>Workload Placement &amp; Segmentation</td><td>Clear guidelines for where workloads deploy based on business and security requirements</td><td>Implement Workload Placement Strategy; restrict non-compliant deployments via LZ Policies; require workload classification before deployment</td></tr>
    <tr><td>5</td><td>LZ Observability &amp; Governance</td><td>Real-time visibility into LZ health, security, and compliance</td><td>Deploy Azure Monitor, AWS CloudWatch, Sentinel/SIEM; automate logging; continuous compliance monitoring via CSPM (AWS Security Hub, Microsoft Defender for Cloud)</td></tr>
    <tr><td>6</td><td>Cost Efficiency &amp; FinOps</td><td>Financial governance tracking and optimising cloud costs per LZ</td><td>Deploy AWS Cost Explorer, Azure Cost Management; automated budget alerts and chargeback models; enforce tagging policies for cost allocation per team/project</td></tr>
    <tr><td>7</td><td>Disaster Recovery &amp; Business Continuity</td><td>LZs designed for high availability and rapid failover</td><td>Multi-region replication for critical workloads; automate backup and failover using AWS Backup and Azure Site Recovery</td></tr>
  </tbody>
</table>

<h4>Shared Responsibility Model (SRM)</h4>
<table>
  <thead>
    <tr><th>Layer</th><th>Responsibility</th><th>Owner</th></tr>
  </thead>
  <tbody>
    <tr><td>Cloud Infrastructure</td><td>Physical security, global networking, hardware management</td><td>AWS / Azure</td></tr>
    <tr><td>Landing Zone Management</td><td>Security baselines, networking, IAM, observability, cost governance, LZ vending, IaC pipelines</td><td>Platform Team (CCoE)</td></tr>
    <tr><td>Application Workloads</td><td>Application security, data encryption, DevSecOps practices, observability, DR runbooks</td><td>Application Teams</td></tr>
  </tbody>
</table>

<h4>OU / Management Group Structure</h4>
<table>
  <thead>
    <tr><th>OU / Management Group</th><th>Purpose</th><th>Security Posture</th></tr>
  </thead>
  <tbody>
    <tr><td>Root</td><td>Top-level container — AWS Organization Root / Azure Tenant Root. Broad org-wide policies applied here.</td><td>Highest — org-wide SCPs/policies</td></tr>
    <tr><td>Core</td><td>Critical shared services: centralised logging, networking, backup accounts</td><td>Locked down — strongest guardrails</td></tr>
    <tr><td>Platform / Connectivity</td><td>Shared networking: hub VNets, VPN gateways, ExpressRoute, Azure Firewall, Transit Gateway</td><td>High — platform team managed</td></tr>
    <tr><td>Platform / Identity</td><td>IAM functions: Azure AD, domain controllers, federation services</td><td>High — centralised identity framework</td></tr>
    <tr><td>Platform / Management</td><td>Logging, monitoring, security tooling, governance — operational visibility</td><td>High — security data consolidation</td></tr>
    <tr><td>Migration</td><td>Onboarding/transitioning workloads — detective controls (not preventive) to allow fixing noncompliant configs</td><td>Lower — graduated compliance path</td></tr>
    <tr><td>Applications (Dev/Pre/Pro)</td><td>Standard workloads by lifecycle stage. Dev = lower controls, Pre = hardening, Pro = strictest guardrails</td><td>Graduated — strictest in Pro</td></tr>
    <tr><td>Application Type N</td><td>Edge-case applications requiring non-standard policies, still with Dev/Pre/Pro subdivision</td><td>Custom — tailored per need</td></tr>
    <tr><td>PolicyStaging</td><td>Test environment for new/updated SCPs, Azure Policies, compliance frameworks before prod rollout</td><td>Controlled — policy validation only</td></tr>
    <tr><td>Sandbox</td><td>Minimal guardrails — experimentation, PoCs, education. No sensitive data or production workloads.</td><td>Low — rapid iteration</td></tr>
    <tr><td>Breakglass</td><td>Emergency troubleshooting — accounts moved here temporarily during critical incidents</td><td>Elevated — monitored, time-limited</td></tr>
    <tr><td>Graveyard / Decommissioned</td><td>Retired or historical workloads retained for compliance/audit. Minimal activity.</td><td>Locked — read-only</td></tr>
    <tr><td>Quarantine</td><td>Strict isolation for compromised or high-risk resources — contains threats, prevents lateral movement</td><td>Maximum — elevated controls</td></tr>
  </tbody>
</table>

<h4>Application Placement Patterns</h4>
<table>
  <thead>
    <tr><th>Pattern</th><th>Isolation Level</th><th>Use When</th></tr>
  </thead>
  <tbody>
    <tr><td>Type 1: Separate Accounts per Environment</td><td>Account-level (highest)</td><td>Full DevOps autonomy required; strict environment separation (Dev/Test/Live in separate accounts)</td></tr>
    <tr><td>Type 2: Shared Account, Isolated VPCs</td><td>VPC-level</td><td>Applications with common characteristics grouped in same account but isolated by VPC. Can combine with Type 1 for two-layer abstraction.</td></tr>
    <tr><td>Type 3: Shared Account + VPC, Isolated Subnets</td><td>Subnet-level (lowest)</td><td>Tightly coupled applications requiring integration. Suitable for smaller teams using managed shared infrastructure. Careful routing required.</td></tr>
  </tbody>
</table>

<h3>TSA-NET: Networking Target State</h3>
<p><em>Target State Architecture §3 — Networking</em></p>
<table>
  <thead>
    <tr><th>#</th><th>Principle</th><th>Description</th><th>Key Implementation Steps</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>Zero Trust Network Architecture (ZTNA)</td><td>All network access authenticated, authorised, and continuously monitored</td><td>Implement ZTNA solutions; enforce least privilege via firewall rules and micro-segmentation; continuous authentication and monitoring</td></tr>
    <tr><td>2</td><td>Cloud-Native Networking</td><td>Replace traditional controls with software-defined networking (SDN) for scalability</td><td>Deploy NaaS; adopt AWS Security Groups / Azure NSGs; use load balancers and cloud gateways instead of VPN concentrators</td></tr>
    <tr><td>3</td><td>Unified Hybrid &amp; Multi-Cloud Networking</td><td>Seamless connectivity across AWS, Azure, and on-premises</td><td>Deploy AWS Direct Connect + Azure ExpressRoute; establish direct AWS↔Azure peering (remove DC reliance); implement unified routing and DNS</td></tr>
    <tr><td>4</td><td>Local Internet Breakout</td><td>Reduce latency by routing cloud workloads directly to internet (not via on-prem)</td><td>Implement direct egress via zScaler / Azure Firewall / AWS IGW; enforce TLS termination at cloud ingress</td></tr>
    <tr><td>5</td><td>Micro-Segmentation &amp; Workload Isolation</td><td>Restrict traffic to necessary scope, limit lateral movement</td><td>Identity-based segmentation (not IP-based); enforce zero-trust between VPCs/VNets; per-service access controls</td></tr>
    <tr><td>6</td><td>Observability &amp; Proactive Monitoring</td><td>Real-time visibility into traffic, performance, and security threats</td><td>AWS VPC Flow Logs, Azure Network Watcher, centralised SIEM (Sentinel/Splunk); automated alerts and incident response playbooks</td></tr>
    <tr><td>7</td><td>DNS Security &amp; Unified Resolution</td><td>Consistent DNS across hybrid and multi-cloud — reduce complexity and risk</td><td>Split-horizon DNS; AWS Route 53 Resolver + Azure DNS Private Zones; enforce DNSSEC</td></tr>
    <tr><td>8</td><td>Decentralised Cloud-Native Firewalls</td><td>Move from central on-prem firewalls to distributed per-workload security controls</td><td>Deploy Azure Firewall, AWS Network Firewall, per-application WAFs; automate firewall rules via IaC</td></tr>
  </tbody>
</table>

<h4>Networking Pattern Options</h4>
<table>
  <thead>
    <tr><th>Area</th><th>Pattern</th><th>Use When</th></tr>
  </thead>
  <tbody>
    <tr><td rowspan="2"><strong>Hybrid Connectivity</strong></td><td>Pattern 1: Private Only (Direct Connect + ExpressRoute)</td><td>High-bandwidth low-latency; sensitive/regulated workloads; minimise attack surface</td></tr>
    <tr><td>Pattern 2: Private + IPSec VPN Overlay</td><td>End-to-end encryption mandated by compliance; extra security layer over private links</td></tr>
    <tr><td rowspan="3"><strong>Inter VPC/VNet</strong></td><td>Pattern 1: AWS Transit Gateway + Azure Virtual WAN</td><td>Multiple VPCs/VNets across multi-region/account; centralised routing; transitive connectivity needed</td></tr>
    <tr><td>Pattern 2: VPC/VNet Peering</td><td>High-bandwidth between specific pairs; avoid TGW/VWAN cost; few interconnections only</td></tr>
    <tr><td>Pattern 3: Hybrid TGW/VWAN + Peering</td><td>Mix of high-bandwidth pairs and broader network; optimise cost and performance</td></tr>
    <tr><td rowspan="2"><strong>Remote Site Ingress</strong></td><td>Option 1: AWS Verified Access (cloud-native ZTNA)</td><td>Lightweight identity-driven access to AWS-hosted private apps without VPN</td></tr>
    <tr><td>Option 2: Zscaler Private Access (ZPA)</td><td>Cloud-delivered ZTNA; environments already using Zscaler; eliminate VPN infrastructure</td></tr>
    <tr><td rowspan="4"><strong>Public Ingress</strong></td><td>Pattern 1: Centralised Ingress (shared ALB + WAF)</td><td>Central policy enforcement; compliance requirements; single point of WAF/firewall filtering</td></tr>
    <tr><td>Pattern 2: Distributed Ingress (regional ALBs + WAF)</td><td>Low-latency for distributed users; per-region scaling; multi-region resiliency</td></tr>
    <tr><td>Pattern 3: Deep Packet Inspection (NGFW before ALB)</td><td>Full packet inspection; IPS/IDS required; TLS decryption; Palo Alto Panorama management</td></tr>
    <tr><td>Pattern 4: WAF Only (ALB + AWS WAF / Azure Front Door)</td><td>Web-based apps; OWASP Top 10 protection; cost-efficient; no DPI needed</td></tr>
    <tr><td rowspan="2"><strong>Egress</strong></td><td>Option 1: Native Cloud Egress (TGW + VWAN + managed firewall)</td><td>Simplicity, cost-efficiency, deep AWS/Azure integration; URL filtering via managed firewall</td></tr>
    <tr><td>Option 2: Zscaler Internet Access (ZIA)</td><td>Consistent global policy; existing Zscaler deployment; comprehensive web threat protection</td></tr>
    <tr><td rowspan="4"><strong>Cloud Inter-Connectivity (AWS↔Azure)</strong></td><td>Pattern 1: Private Connectivity (Equinix Fabric / Megaport)</td><td>High-performance low-latency; regulated workloads; no public internet exposure</td></tr>
    <tr><td>Pattern 2: Zscaler Private Access for Workloads</td><td>Application-layer trust; modern multi-cloud architectures; minimal attack surface; no network peering needed</td></tr>
    <tr><td>Pattern 3: Private Connectivity + IPSec VPN Overlay</td><td>Compliance mandates encryption in transit even over private links</td></tr>
    <tr><td>Pattern 4: IPSec VPN (App-to-App or TGW↔VWAN)</td><td>Incremental inter-cloud networking; start before full private connectivity</td></tr>
    <tr><td rowspan="2"><strong>East-West Segmentation</strong></td><td>Pattern 1: Cloud-Native Firewalls (AWS Network Firewall / Azure Firewall) + SGs/NSGs</td><td>Layer 3/4 stateful inspection; fully managed; native integration; basic logging sufficient</td></tr>
    <tr><td>Pattern 2: Third-Party NGFWs (Palo Alto) + SGs/NSGs</td><td>Layer 7 DPI; application-aware policies; IDS/IPS + TLS decryption; centralised Panorama management</td></tr>
  </tbody>
</table>

<p><strong>DNS naming convention:</strong> <code>*.[workload].[hyperscaler].[parent-domain]</code> — e.g. <code>api.edap.aws.ukhsa.gov.uk</code>. Internal and external DNS use the same naming standard to support PKI certificate validation. DNS zone governance: Root zone managed by Cyber/Networking Team; LZ zones by Platform Engineering; workload zones by application teams via IaC.</p>

<h3>TSA-IDN: Identity Target State</h3>
<p><em>Target State Architecture §4 — Identity</em></p>
<table>
  <thead>
    <tr><th>#</th><th>Principle</th><th>Description</th><th>Key Implementation Steps</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>Identity-Centric Security &amp; Zero Trust</td><td>Verify every access request — MFA, Conditional Access, Least Privilege</td><td>Enable Conditional Access in Entra ID; enforce MFA across all workloads; apply PoLP via automated role provisioning; session-based access reviews</td></tr>
    <tr><td>2</td><td>Centralised Identity Governance &amp; Federated Access</td><td>Entra ID as primary IdP; federation for AWS, SaaS, third-party; SCIM + PIM automation</td><td>All SaaS and AWS via Entra ID federation; enforce SCIM provisioning; configure PIM for JIT admin access</td></tr>
    <tr><td>3</td><td>Eliminate Local User Accounts</td><td>Prohibit local IAM users in AWS and Azure; require centralised auth via federated identity</td><td>Audit existing IAM users; enforce SCPs (AWS) and Azure AD Conditional Access; transition all auth to Entra ID / AWS IAM Identity Center</td></tr>
    <tr><td>4</td><td>RBAC + ABAC</td><td>Standardise RBAC; enforce ABAC for dynamic access decisions based on security posture and job function</td><td>Map existing roles; replace static IAM roles with dynamic ABAC policies; configure JIT access controls</td></tr>
    <tr><td>5</td><td>Delegated Administration with Guardrails</td><td>Shift from fully centralised to delegated admin with strict governance via SCPs and Conditional Access</td><td>Define permission guardrails; allow workload teams to self-manage roles under predefined policies</td></tr>
    <tr><td>6</td><td>Identity Observability &amp; Compliance</td><td>Centralised monitoring via Sentinel, CloudTrail, SIEM; automated access reviews</td><td>Integrate Entra ID logs with Sentinel; CloudTrail anomaly review; automate periodic access reviews</td></tr>
    <tr><td>7</td><td>Secure Identity Lifecycle Management (JML)</td><td>Automate Joiner-Mover-Leaver processes — no orphaned accounts</td><td>Implement Azure Identity Governance; integrate HR systems for automatic role assignment; self-service access request workflows</td></tr>
    <tr><td>8</td><td>Secure Machine Identities &amp; API Auth</td><td>Replace static credentials with workload identities and managed service identities</td><td>AWS IAM Roles + Azure Managed Identities; enforce API auth via OAuth2 and mutual TLS; remove hardcoded credentials</td></tr>
  </tbody>
</table>

<h4>Identity Patterns</h4>
<table>
  <thead>
    <tr><th>Pattern</th><th>Description</th><th>Key Technology</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>IAM Personas</strong></td><td>Baseline roles for all standard access requirements via AWS Identity Center Permission Sets and Azure AD Roles. Policy-as-Code (PaC) enforced. SCPs deny local IAM user creation org-wide. Permission Boundaries prevent privilege escalation.</td><td>AWS IAM Identity Center, Azure AD RBAC, AWS SCPs, Permission Boundaries</td></tr>
    <tr><td><strong>Just-in-Time (JIT) Access</strong></td><td>Temporary elevated access for admin tasks via Entra ID PIM. Requires business justification + manager/security approval. Time-bound with auto-revocation. MFA re-auth required. Full audit in Sentinel + CloudTrail.</td><td>Entra ID PIM (Azure + federated AWS), AWS IAM Role assumption, Azure Sentinel, CloudTrail</td></tr>
    <tr><td><strong>Bespoke Roles</strong></td><td>Only created if no existing persona satisfies the use case. Formal approval: request → security review → PoLP validation. Quarterly review and auto-expiry for idle roles. All activity logged.</td><td>AWS IAM, Azure RBAC, Entra ID PIM, AWS CloudTrail</td></tr>
    <tr><td><strong>Breakglass Access</strong></td><td>Emergency-only access for IdP outage scenarios. Dedicated isolated AWS account / Azure subscription. No standing privileges — admin role assumed only in emergency. Hardware MFA (YubiKey/FIDO2). Time-limited, multi-level approval. Quarterly tested and credential-rotated.</td><td>Dedicated AWS Account, Azure Subscription, AWS Secrets Manager / Azure Key Vault, CloudTrail, Sentinel</td></tr>
    <tr><td><strong>Identity Lifecycle (JML)</strong></td><td>Joiner: HR → Entra ID → auto-provision via SCIM + dynamic groups. Mover: ABAC auto-updates on HR attribute change; previous access revoked immediately. Leaver: Entra ID Lifecycle Workflows auto-disable; SCPs block deactivated accounts; automated alerts on login attempts from terminated users.</td><td>Entra ID Lifecycle Workflows, SCIM, HR integration, AWS IAM Access Analyzer, Entra ID PIM</td></tr>
  </tbody>
</table>

<h3>TSA-PLT: Platforms &amp; Services Target State</h3>
<p><em>Target State Architecture §5 — Platform Designs Catalogue</em></p>
<p>Pre-approved platform designs aligned to the Cloud Control Framework (CCF). All teams should adopt these designs rather than build bespoke alternatives.</p>
<table>
  <thead>
    <tr><th>Domain</th><th>CCF Control</th><th>Design</th><th>Cloud</th></tr>
  </thead>
  <tbody>
    <tr><td>Platform</td><td>—</td><td>AWS Config configured with Service Linked Role</td><td>AWS</td></tr>
    <tr><td>Platform</td><td>—</td><td>Security Hub Standards Update (HLD)</td><td>AWS</td></tr>
    <tr><td>Platform</td><td>—</td><td>Enable Delegated Admin for Centralised Resource Explorer</td><td>AWS</td></tr>
    <tr><td>Data</td><td>DAT-DAC-01</td><td>Preventative guardrail — block creation of public data stores</td><td>AWS</td></tr>
    <tr><td>Data</td><td>DAT-DAC-01</td><td>Detective alerting for public data stores</td><td>AWS</td></tr>
    <tr><td>Data</td><td>DAT-DAC-01</td><td>Azure design — block public data stores</td><td>Azure</td></tr>
    <tr><td>Data</td><td>DAT-DAC-01</td><td>Implement alerting for public data stores</td><td>Azure</td></tr>
    <tr><td>Finance</td><td>FIN-COA-01</td><td>Cost allocation and tagging design</td><td>AWS + Azure</td></tr>
    <tr><td>Finance</td><td>FIN-COB-01</td><td>Budget alerting and cost anomaly detection</td><td>AWS + Azure</td></tr>
    <tr><td>Finance</td><td>FIN-COB-02</td><td>Cost optimisation and rightsizing</td><td>AWS + Azure</td></tr>
    <tr><td>Security</td><td>SEC-APS-03</td><td>Preventative guardrail — resources outside private networks</td><td>AWS + Azure</td></tr>
    <tr><td>Security</td><td>SEC-APS-03</td><td>Detective guardrail — resources outside private networks</td><td>AWS + Azure</td></tr>
    <tr><td>Security</td><td>SEC-APS-03</td><td>Detective guardrail — network resources not created by central team</td><td>AWS</td></tr>
    <tr><td>Security</td><td>SEC-APS-03</td><td>Enable Delegated Admin for Firewall Manager</td><td>AWS</td></tr>
    <tr><td>Security</td><td>SEC-APS-03</td><td>Ingress/Egress options design</td><td>General</td></tr>
    <tr><td>Security</td><td>SEC-IAM-05</td><td>Process for Access Key / Client Secret renewal before 90-day expiry</td><td>AWS + Azure</td></tr>
    <tr><td>Security</td><td>SEC-IAM-07</td><td>RBAC — process for requesting changes to permission sets</td><td>AWS</td></tr>
    <tr><td>Security</td><td>SEC-IAM-07</td><td>Process for requesting enhanced developer permissions</td><td>AWS</td></tr>
    <tr><td>Security</td><td>SEC-IAM-08</td><td>Centralised Root Access design</td><td>AWS</td></tr>
    <tr><td>Security</td><td>SEC-IAM-09</td><td>Federated identity / SSO design</td><td>AWS + Azure</td></tr>
  </tbody>
</table>

<h3>TSA-SUM: Target State — Next Steps &amp; Roadmap</h3>
<p><em>Target State Architecture §6 — Summary &amp; Conclusion</em></p>
<p>The transition state architecture bridges the baseline and target state. By comparing these, gaps are identified and intermediate milestones defined to ensure a smooth, phased migration aligned with organisational goals.</p>
<table>
  <thead>
    <tr><th>Phase</th><th>Activity</th><th>Participants</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Phase I</strong></td>
      <td>Joint workshop to define Terms of Reference (ToR) for future cloud architectural decisions — agree Cloud Strategy principles, long-term target architecture goals, RACI for architectural working group, and appointment of accountable individuals per domain.<br/><br/>Domain-specific target architecture workshops (accounting for in-flight projects) → output: agreed comprehensive cloud architecture documents per domain.</td>
      <td>Cloudscaler (facilitator), representatives from all technology domains, platform engineering and operations functions</td>
    </tr>
    <tr>
      <td><strong>Phase II</strong></td>
      <td>Establish architecture workgroups to develop designs to be delivered by platform engineering and application enablement functions, based on Phase I outputs.</td>
      <td>Architects from relevant technology domains</td>
    </tr>
    <tr>
      <td><strong>Phase III</strong></td>
      <td>Create an enduring governance relationship with the CPE function in the CCoE to drive delivery of Cloud Strategy goals — guidance and oversight of the wider architectural function on a BAU basis.</td>
      <td>Leads from relevant technology domains, CPE lead, CCoE architecture lead</td>
    </tr>
  </tbody>
</table>

<!-- ============================================================ -->
<!-- SECTION: UKHSA ARCHITECTURE DECISION RECORDS (ADRs)          -->
<!-- Source: UKHSA Cloud Strategy & Approved Patterns             -->
<!-- ============================================================ -->

<h2>UKHSA Architecture Decision Records (ADRs)</h2>
<p><em>These 10 ADRs are firm, board-ratified architectural decisions. Deviating from an ADR requires an explicit exception approved by the Architecture Review Board with documented rationale.</em></p>
<table>
  <thead>
    <tr><th>ADR ID</th><th>Decision</th><th>Rationale</th><th>Pattern(s) Affected</th></tr>
  </thead>
  <tbody>
    <tr><td>ADR-001</td><td>Aurora PostgreSQL is the preferred relational database</td><td>Managed, cost-effective, compatible with open-source PostgreSQL tooling; avoids vendor-proprietary lock-in for OLTP workloads</td><td>3A</td></tr>
    <tr><td>ADR-002</td><td>Use Amazon S3 + AWS Glue for object storage — not HDFS</td><td>S3 provides elastic, serverless storage with native AWS integration; HDFS requires managed infrastructure with no cloud-native advantage</td><td>3C</td></tr>
    <tr><td>ADR-003</td><td>Use Amazon Redshift Spectrum for analytical queries &gt;100 GB</td><td>Redshift Spectrum avoids loading large datasets into Redshift storage; queries S3 directly at scale with columnar optimisation</td><td>2D, 3B</td></tr>
    <tr><td>ADR-004</td><td>Use Amazon EventBridge over SNS/SQS for event routing</td><td>EventBridge provides schema registry, content-based filtering, cross-account routing, and native SaaS integrations not available in SNS/SQS alone</td><td>4A</td></tr>
    <tr><td>ADR-005</td><td>TLS 1.2 minimum for all data-in-transit</td><td>TLS 1.0/1.1 are deprecated and vulnerable (POODLE, BEAST). TLS 1.2+ required for NCSC and DSPT compliance.</td><td>6B, EDAP-INT-01</td></tr>
    <tr><td>ADR-006</td><td>Customer-managed KMS keys (CMKs) for all sensitive data</td><td>AWS-managed keys do not provide key rotation control or cross-account access restrictions needed for sensitive/personal data categories</td><td>6B</td></tr>
    <tr><td>ADR-007</td><td>Bronze / Silver / Gold data lake tier naming convention</td><td>Standardises data quality progression: Bronze = raw ingest, Silver = conformed/validated, Gold = curated/aggregated. Maps to EDAP Ingestion/Raw/Conform/DataMart layers.</td><td>3C, EDAP-INT-05</td></tr>
    <tr><td>ADR-008</td><td>Multi-cloud strategy: AWS as primary analytics cloud, Azure as primary SaaS/identity cloud</td><td>Leverages EDAP (AWS) for data analytics and Microsoft Entra ID / M365 / AVD (Azure) for productivity and identity. Avoids single-vendor lock-in.</td><td>UKHSA-INF-01, UKHSA-INF-05</td></tr>
    <tr><td>ADR-009</td><td>Infrastructure as Code (IaC) is mandatory for all cloud resources</td><td>Manual provisioning causes configuration drift, audit failures, and prevents repeatable deployments. Terraform (or CDK) required for all infrastructure.</td><td>All patterns</td></tr>
    <tr><td>ADR-010</td><td>Zero Trust Network Architecture for all new connectivity</td><td>Perimeter-based security is insufficient for hybrid/multi-cloud. Identity-aware, least-privilege access enforced at every layer via zScaler, Entra ID, IAM Identity Center, and SCPs.</td><td>6A, 6C, UKHSA-INF-03, UKHSA-INF-05</td></tr>
  </tbody>
</table>

<!-- ============================================================ -->
<!-- SECTION: BASELINE CURRENT STATE — SUMMARY & OBSERVATIONS     -->
<!-- Source: Baseline Current State Architecture §7               -->
<!-- ============================================================ -->

<h2>Baseline Current State — Key Observations &amp; Target Actions</h2>
<p><em>Sourced from <strong>Baseline Current State Architecture §7 — Summary and Conclusion</strong>. These observations from the baseline inform the Target State Cloud Architecture and the remediation actions required to align with the UKHSA Cloud Strategy.</em></p>
<table>
  <thead>
    <tr><th>Area</th><th>Key Observations (Current State)</th><th>Target State Actions</th><th>Reference</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Cloud Operating Model</strong></td>
      <td>Difficulties establishing cohesive DevOps structure; teams lack empowerment for swift decisions; overly gated governance introduces bottlenecks; excessive artefact requirements delay delivery</td>
      <td>Implement clear DevOps framework with defined roles; introduce flexible governance with predefined guardrails; streamline approvals with automated checks; replace artefacts with reusable templates and tooling; use review boards as exception only</td>
      <td>Baseline §2.4</td>
    </tr>
    <tr>
      <td><strong>Landing Zones</strong></td>
      <td>Lift-and-shift limits cloud-native capability; workloads in wrong LZs create security/compliance risk; legacy LZs not decommissioned; migrated workloads not optimised; no unified observability platform; no standardised data lifecycle controls</td>
      <td>Mandate migration to strategic LZs (UKHSA-INF-01); enforce cloud-native refactoring during migration; decommission legacy LZs with firm timeline; implement unified observability platform; standardise data lifecycle policies</td>
      <td>Baseline §3.4</td>
    </tr>
    <tr>
      <td><strong>Networking</strong></td>
      <td>Strategic LZ traffic routed via legacy infrastructure (latency, complexity); no direct cross-cloud LZ connectivity; internet-bound traffic via on-prem DCs (bottleneck); centralised firewalls limit scalability; DNS forwarding between DCs adds latency; key domains not in AWS</td>
      <td>Redesign network architecture (UKHSA-INF-02); enable direct LZ-to-LZ connectivity (cross-cloud); route internet traffic via zScaler (UKHSA-INF-03); adopt cloud-native security controls; migrate key domains to Route 53 (UKHSA-INF-04)</td>
      <td>Baseline §4.4</td>
    </tr>
    <tr>
      <td><strong>Identity</strong></td>
      <td>Local user accounts in workload accounts create credential sprawl and audit risk; centralised identity team creates bottlenecks and over/under-provisioning; compliance risk from residual local accounts</td>
      <td>Enforce federated authentication via Entra ID + AWS IAM Identity Center (UKHSA-INF-05); prohibit local accounts via SCPs; introduce delegated administration model with guardrails; continuous monitoring for residual local accounts; regular access reviews</td>
      <td>Baseline §5.3</td>
    </tr>
    <tr>
      <td><strong>Platforms &amp; Services</strong></td>
      <td>Key applications in legacy LZs increase technical debt and security risk; VMware on Azure limits scalability and prevents use of Azure-native services; strategic workloads not refactored to cloud-native during migration</td>
      <td>Migrate critical apps to strategic LZs (UKHSA-INF-01, UKHSA-INF-06); implement phased VMware modernisation to Azure-native (VMs, AKS); mandate cloud-native refactoring for strategic workloads; leverage EDAP for all analytics workloads (EDAP-INT-01 to EDAP-INT-06)</td>
      <td>Baseline §6.3</td>
    </tr>
  </tbody>
</table>
"""



def _template_path() -> str:
  """Path where synced page template is stored."""
  return os.path.join(os.path.dirname(__file__), "main_page_template.synced.html")


def save_synced_template(body_html: str) -> None:
  """Persist current Confluence page body as the local source template."""
  path = _template_path()
  with open(path, "w", encoding="utf-8") as f:
    f.write(body_html)


def load_synced_template() -> str | None:
  """Load previously synced template if available."""
  path = _template_path()
  if not os.path.exists(path):
    return None
  with open(path, "r", encoding="utf-8") as f:
    return f.read()


def _update_questionnaire_plan_link(body_html: str, plan_link: str) -> str:
  """Refresh the questionnaire plan hyperlink while preserving manual page content."""
  pattern = (
    r'(<a\s+href=")([^"]*)("[^>]*>\s*QUESTIONNAIRE_PLAN\.md\s*</a>)'
  )
  if re.search(pattern, body_html, flags=re.IGNORECASE):
    return re.sub(pattern, rf"\g<1>{plan_link}\g<3>", body_html, flags=re.IGNORECASE)
  return body_html


def _ensure_network_segmentation_section(body_html: str) -> str:
  """Insert Section 13b if older synced templates do not yet contain it."""
  if "Network Segmentation Inputs" in body_html:
    return body_html

  section_13b = """
<!-- SECTION 13B: NETWORK SEGMENTATION INPUTS -->
<div style="background-color: #eef6ff; border-left: 5px solid #1D4ED8; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section13b" style="color: #1D4ED8; margin-top: 0;">13b. Network Segmentation Inputs</h2>
<p><em>Provides explicit inputs for the <strong>Network Segregation diagram</strong> so it matches AWS reference architecture clarity.</em></p>
<table>
  <thead>
    <tr><th>Parameter</th><th>Value</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr><td>VPC CIDR</td><td>10.0.0.0/16</td><td>Primary workload VPC range</td></tr>
    <tr><td>Public Subnet CIDR</td><td>10.0.1.0/24</td><td>Ingress / ALB</td></tr>
    <tr><td>Private Subnet CIDR</td><td>10.0.2.0/24</td><td>Application runtime</td></tr>
    <tr><td>Data Subnet CIDR</td><td>10.0.3.0/24</td><td>RDS/data services</td></tr>
    <tr><td>On-Prem CIDR</td><td>172.16.0.0/16</td><td>Corporate/legacy network</td></tr>
    <tr><td>Connectivity Type</td><td>Site-to-Site VPN</td><td>Or Direct Connect + VPN backup</td></tr>
    <tr><td>Public Ingress Path</td><td>Internet -> IGW -> ALB</td><td>North-south ingress</td></tr>
    <tr><td>Private Ingress Path</td><td>On-prem -> VPN -> Private Route Table -> EKS</td><td>Hybrid private access</td></tr>
    <tr><td>Public SG Rules</td><td>HTTP(80), HTTPS(443)</td><td>Internet-facing controls</td></tr>
    <tr><td>Private SG Rules</td><td>Internal east-west only</td><td>No direct internet</td></tr>
    <tr><td>Data SG Rules</td><td>DB ports (3306, 5432, 6379)</td><td>Strict application-to-data only</td></tr>
    <tr><td>Public Route</td><td>0.0.0.0/0 via IGW</td><td>Public subnet route table</td></tr>
    <tr><td>Private Route</td><td>On-prem CIDR via VPN</td><td>Private subnet route table</td></tr>
  </tbody>
</table>

</div>
"""

  marker = "<!-- SECTION 14: AUTO-GENERATED DIAGRAMS -->"
  if marker in body_html:
    return body_html.replace(marker, section_13b + "\n" + marker, 1)
  return body_html + section_13b


def _ensure_approved_patterns_link(body_html: str) -> str:
  """Ensure main page has an easy link to the approved patterns reference page."""
  if "Architecture Patterns Reference" in body_html:
    return body_html

  insert_block = (
    '<p style="margin-top: 10px; font-size: 16px;"><strong>'
    '<ac:link><ri:page ri:space-key="CDA" ri:content-title="Architecture Patterns Reference" />'
    '</ac:link></strong></p>'
    '<p><em>Use this page to pick reusable Security, Network, Governance, and EDAP-aligned integration patterns.</em></p>'
  )

  pattern = (
    r'(<p[^>]*>\s*<strong>\s*<ac:link>\s*<ri:page[^>]*content-title="Architecture Diagrams"[^>]*/>'
    r'\s*</ac:link>\s*</strong>\s*</p>)'
  )
  if re.search(pattern, body_html, flags=re.IGNORECASE):
    return re.sub(pattern, r"\1" + insert_block, body_html, count=1, flags=re.IGNORECASE)
  return body_html


def _ensure_secure_by_design_link(body_html: str) -> str:
  """Ensure the Secure by Design SAT template link is visible in Pattern Selection."""
  if "Secure by Design - SAT" in body_html:
    return body_html

  sat_block = (
    '<p><em>Secure by Design reference:</em> '
    f'<a href="{html.escape(SECURE_BY_DESIGN_SAT_URL, quote=True)}">'
    'UKHSA Secure by Design - SAT Template v2.6</a></p>'
  )

  pattern = r'(<h[1-3][^>]*>\s*8\.\s*Pattern Selection\s*</h[1-3]>\s*<p[^>]*>.*?</p>)'
  if re.search(pattern, body_html, flags=re.DOTALL | re.IGNORECASE):
    return re.sub(pattern, r"\1" + sat_block, body_html, count=1, flags=re.DOTALL | re.IGNORECASE)
  return body_html


def _ensure_secure_by_design_pattern_rows(body_html: str) -> str:
  """Append Secure by Design control rows to Section 8d pattern table."""
  if "SBD-01" in body_html:
    return body_html

  sbd_rows = """
    <tr><td>SBD-01</td><td>Threat Modelling &amp; Abuse Cases</td><td>Security</td><td></td><td>Apply SAT template checkpoints before Gate 2</td></tr>
    <tr><td>SBD-02</td><td>Secure SDLC &amp; Supply Chain Assurance</td><td>Security</td><td></td><td>Enforce SAST/DAST/SCA and signed artifact controls</td></tr>
    <tr><td>SBD-03</td><td>Privacy by Design (DPIA/DSA Controls)</td><td>Governance</td><td></td><td>Link data protection controls to datasets and flows</td></tr>
    <tr><td>SBD-04</td><td>Continuous Security Assurance</td><td>Governance</td><td></td><td>Operational control testing, evidence, and remediation tracking</td></tr>
  """

  match = re.search(
    r'(<h[1-3][^>]*>\s*8d\.\s*Governance,\s*Security\s*&amp;\s*Operational\s*Patterns\s*</h[1-3]>.*?<tbody>)(.*?)(</tbody>)',
    body_html,
    flags=re.DOTALL | re.IGNORECASE,
  )
  if not match:
    return body_html

  return body_html[:match.start()] + match.group(1) + match.group(2) + sbd_rows + match.group(3) + body_html[match.end():]


def _ensure_secure_by_design_coverage_matrix(body_html: str) -> str:
  """Insert Secure by Design control traceability matrix after Section 8d."""
  if "Secure by Design Coverage Matrix" in body_html:
    return body_html

  matrix_block = """
  <h3 id="section8d-sbd" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">Secure by Design Coverage Matrix</h3>
<p><em>Trace each Secure by Design control to selected patterns, architecture components, runtime connections, and NFR outcomes.</em></p>
<table>
  <thead><tr><th>SAT Control Ref</th><th>Secure by Design Control</th><th>Pattern ID</th><th>Mapped Components (Section 10)</th><th>Mapped Connections (Section 11)</th><th>NFR Coverage</th><th>Evidence / Gate</th></tr></thead>
  <tbody>
    <tr><td>SAT-01</td><td>Threat modelling and abuse-case analysis completed</td><td>SBD-01</td><td>Threat Modelling &amp; Security Design Review; Validation Processor</td><td>Threat Modelling &amp; Security Design Review -> Policy Enforcement &amp; Management</td><td>NFR4, NFR6</td><td>Gate 2 design review sign-off</td></tr>
    <tr><td>SAT-02</td><td>Identity and access controls designed with least privilege</td><td>SEC-01</td><td>Identity &amp; Access Management (IAM); Validation Processor</td><td>Validation Processor -> Identity &amp; Access Management (IAM)</td><td>NFR4</td><td>Role model + access review evidence</td></tr>
    <tr><td>SAT-03</td><td>Encryption and key management enforced end-to-end</td><td>SEC-01</td><td>Encryption at Rest &amp; Transit; Curated Database; Raw Landing Bucket</td><td>Curated Database -> Encryption at Rest &amp; Transit</td><td>NFR4, NFR5</td><td>KMS/Key Vault policy and config checks</td></tr>
    <tr><td>SAT-04</td><td>Secrets and credentials managed centrally</td><td>SEC-01</td><td>Secret Management; Validation Processor</td><td>Validation Processor -> Secret Management</td><td>NFR4</td><td>Secrets rotation and retrieval audit logs</td></tr>
    <tr><td>SAT-05</td><td>Secure SDLC and software supply chain controls active</td><td>SBD-02</td><td>Secure CI/CD Assurance; Validation Processor</td><td>Validation Processor -> Secure CI/CD Assurance</td><td>NFR4, NFR8</td><td>Pipeline security gate reports</td></tr>
    <tr><td>SAT-06</td><td>Vulnerability and patch management lifecycle implemented</td><td>SBD-02</td><td>Vulnerability &amp; Patch Management</td><td>Policy Enforcement &amp; Management -> Validation Processor</td><td>NFR4, NFR8</td><td>Scan reports and remediation SLA tracking</td></tr>
    <tr><td>SAT-07</td><td>Privacy-by-design, DPIA/DSA and minimisation controls applied</td><td>SBD-03, DPIA-01</td><td>Privacy by Design Controls; Data Lineage &amp; Governance; Curated Database</td><td>Data Lineage &amp; Governance -> Curated Database</td><td>NFR5, NFR6</td><td>DPIA/DSA approvals and retention policy evidence</td></tr>
    <tr><td>SAT-08</td><td>Continuous assurance, logging, monitoring, and governance reporting</td><td>SBD-04, GOV-01, OPS-01</td><td>Audit Logging &amp; Compliance Monitoring; Monitoring and Alerts; Cost Optimization &amp; Usage Monitoring</td><td>Audit Logging &amp; Compliance Monitoring -> Monitoring and Alerts; Cost Optimization &amp; Usage Monitoring -> Monitoring and Alerts</td><td>NFR6, NFR7, NFR9</td><td>Monthly governance review and control attestations</td></tr>
  </tbody>
</table>
"""

  # Preferred insertion: immediately after Section 8d table.
  section_8d_table_pattern = (
    r'(<h[1-3][^>]*>\s*8d\.\s*Governance,\s*Security\s*&amp;\s*Operational\s*Patterns\s*</h[1-3]>.*?</table>)'
  )
  if re.search(section_8d_table_pattern, body_html, flags=re.DOTALL | re.IGNORECASE):
    return re.sub(
      section_8d_table_pattern,
      r'\1\n' + matrix_block,
      body_html,
      count=1,
      flags=re.DOTALL | re.IGNORECASE,
    )

  # Fallback: append to Section 8 block before Section 9 heading.
  marker = re.search(r'<h[1-3][^>]*>\s*9\.\s*Context Entities\s*</h[1-3]>', body_html, flags=re.IGNORECASE)
  if marker:
    return body_html[:marker.start()] + matrix_block + "\n" + body_html[marker.start():]

  return body_html


def _ensure_architecture_components_with_security_governance(body_html: str) -> str:
  """Ensure Architecture Components section includes Security and Governance layers."""
  
  architecture_components_html = """
  <tr><td colspan="7"><strong>Core Infrastructure Components</strong></td></tr>
  <tr><td>1</td><td>On-Prem Business App</td><td>Edge</td><td>On-Prem LoB Application</td><td>Both</td><td>Source business system producing surveillance/event data</td><td>FR1, NFR2</td></tr>
  <tr><td>2</td><td>On-Prem SFTP Server</td><td>Edge</td><td>SFTP Gateway</td><td>Both</td><td>Controlled transfer point for inbound extracts from source systems</td><td>FR1, NFR4</td></tr>
  <tr><td>3</td><td>AWS Transfer Endpoint</td><td>Network</td><td>AWS Transfer Family</td><td>AWS</td><td>Managed secure ingress endpoint for file transfers into cloud zones</td><td>FR1, NFR2, NFR4</td></tr>
  <tr><td>4</td><td>Raw Landing Bucket</td><td>Data</td><td>Amazon S3</td><td>AWS</td><td>Raw intake zone for immutable landing and initial validation triggers</td><td>FR1, NFR5</td></tr>
  <tr><td>5</td><td>Validation Processor</td><td>Application</td><td>AWS Lambda / Container Worker</td><td>Both</td><td>Validates, transforms, and routes incoming data to curated stores and queues</td><td>FR2, NFR1</td></tr>
  <tr><td>6</td><td>Processing Queue</td><td>Platform</td><td>Amazon SQS / Azure Service Bus</td><td>Both</td><td>Asynchronous decoupling for resilient processing and retry behavior</td><td>FR2, NFR2, NFR3</td></tr>
  <tr><td>7</td><td>Curated Database</td><td>Data</td><td>Amazon RDS / Azure SQL</td><td>Both</td><td>Stores validated and curated records for downstream analytics/reporting</td><td>FR3, NFR5</td></tr>
  <tr><td>8</td><td>Monitoring and Alerts</td><td>Platform</td><td>CloudWatch / Azure Monitor</td><td>Both</td><td>Operational metrics, alerting, and incident trigger integration</td><td>NFR7, NFR8</td></tr>
  <tr><td colspan="7"><strong>Security Layer Components</strong></td></tr>
  <tr><td>9</td><td>Identity &amp; Access Management (IAM)</td><td>Security</td><td>AWS IAM / Azure Entra ID</td><td>Both</td><td>User authentication, authorization, and role-based access control across all layers</td><td>NFR4</td></tr>
  <tr><td>10</td><td>Encryption at Rest &amp; Transit</td><td>Security</td><td>AWS KMS / Azure Key Vault</td><td>Both</td><td>Data encryption for storage and network communications</td><td>NFR4, NFR5</td></tr>
  <tr><td>11</td><td>Secret Management</td><td>Security</td><td>AWS Secrets Manager / Azure Key Vault</td><td>Both</td><td>Secure storage and rotation of credentials, API keys, database passwords</td><td>NFR4</td></tr>
  <tr><td>12</td><td>Network Security &amp; DDoS Protection</td><td>Security</td><td>AWS WAF, Shield / Azure DDoS Protection</td><td>Both</td><td>Web application firewall and distributed denial-of-service mitigation</td><td>NFR2, NFR4</td></tr>
  <tr><td>13</td><td>Threat Detection &amp; Response</td><td>Security</td><td>AWS GuardDuty / Azure Defender</td><td>Both</td><td>Continuous monitoring for threats and automated incident response</td><td>NFR4</td></tr>
  <tr><td colspan="7"><strong>Governance Layer Components</strong></td></tr>
  <tr><td>14</td><td>Audit Logging &amp; Compliance Monitoring</td><td>Governance</td><td>AWS CloudTrail / Azure Activity Log</td><td>Both</td><td>Complete audit trail of all API calls, user actions, and configuration changes</td><td>NFR6</td></tr>
  <tr><td>15</td><td>Policy Enforcement &amp; Management</td><td>Governance</td><td>AWS Config / Azure Policy</td><td>Both</td><td>Automated policy compliance checking and remediation across infrastructure</td><td>NFR6</td></tr>
  <tr><td>16</td><td>Data Lineage &amp; Governance</td><td>Governance</td><td>AWS Glue / Azure Purview</td><td>Both</td><td>Track data provenance, ownership, and transformation lineage for governance</td><td>NFR5, NFR6</td></tr>
  <tr><td>17</td><td>Cost Optimization &amp; Usage Monitoring</td><td>Governance</td><td>AWS Cost Explorer / Azure Cost Management</td><td>Both</td><td>Monitor spend, optimize resource utilization, and enforce cost controls</td><td>NFR9</td></tr>
  <tr><td>18</td><td>Threat Modelling &amp; Security Design Review</td><td>Security</td><td>Secure by Design SAT, Architecture Review Checklist</td><td>Both</td><td>Identify trust boundaries, attack paths, and control gaps before implementation</td><td>NFR4, NFR6</td></tr>
  <tr><td>19</td><td>Vulnerability &amp; Patch Management</td><td>Security</td><td>AWS Inspector / Azure Defender Vulnerability Management</td><td>Both</td><td>Continuously scan for vulnerabilities and enforce patch compliance</td><td>NFR4, NFR8</td></tr>
  <tr><td>20</td><td>Secure CI/CD Assurance</td><td>Security</td><td>SAST, DAST, SCA, Artifact Signing</td><td>Both</td><td>Block insecure code and dependencies from promotion across environments</td><td>NFR4, NFR8</td></tr>
  <tr><td>21</td><td>Privacy by Design Controls</td><td>Governance</td><td>DPIA/DSA workflow, Data Classification, Retention Policies</td><td>Both</td><td>Embed lawful processing, minimisation, masking, and retention controls in design</td><td>NFR5, NFR6</td></tr>
  """
  
  # Replace the old architecture components table rows with the new one including Security/Governance
  body_html = re.sub(
    r'(<h[1-3][^>]*>\s*10\.\s*Architecture Components\s*</h[1-3]>.*?<tbody>)(.*?)(</tbody>)',
    r'\1' + architecture_components_html + r'\3',
    body_html,
    flags=re.DOTALL | re.IGNORECASE,
  )
  
  # Also update the valid layers description to include Security and Governance
  body_html = re.sub(
    r'Valid layers:\s*<strong>Edge, Network, Platform, Application, Data</strong>',
    r'Valid layers: <strong>Edge, Network, Platform, Application, Data, Security, Governance</strong>',
    body_html,
    flags=re.IGNORECASE,
  )
  
  return body_html


def _ensure_context_entities_populated(body_html: str) -> str:
  """Ensure Context Entities section includes required entities for C4 context diagram."""
  context_entities_html = """
    <tr><td>On-Prem Business App</td><td>System</td><td>Produces daily surveillance files via SFTP export</td><td>Out</td></tr>
    <tr><td>On-Prem SFTP Server</td><td>System</td><td>Stages and relays files for secure cloud transfer</td><td>Both</td></tr>
    <tr><td>UKHSA Intra Identity (Azure Entra ID)</td><td>Service</td><td>Provides SSO and MFA authentication for transfer users and support access</td><td>Both</td></tr>
    <tr><td>Data Analyst Team</td><td>User</td><td>Consumes validated data outputs</td><td>In</td></tr>
    <tr><td>Security Operations</td><td>Service</td><td>Reviews logs and alerts</td><td>In</td></tr>
  """
  
  # Replace the context entities table rows
  body_html = re.sub(
    r'(<h[1-3][^>]*>\s*9\.\s*Context Entities\s*</h[1-3]>.*?<tbody>)(.*?)(</tbody>)',
    r'\1' + context_entities_html + r'\3',
    body_html,
    flags=re.DOTALL | re.IGNORECASE,
  )
  
  return body_html


def _ensure_secure_by_design_connections(body_html: str) -> str:
  """Add security/governance design-time and runtime control paths to Section 11."""
  if "Threat Modelling &amp; Security Design Review" in body_html and "Secure-by-design control path" in body_html:
    return body_html

  secure_connections_rows = """
    <tr><td>Validation Processor</td><td>Identity &amp; Access Management (IAM)</td><td>Token validation / RBAC decision</td><td>OIDC/OAuth2, IAM role</td><td>Secure-by-design control path</td></tr>
    <tr><td>Validation Processor</td><td>Secret Management</td><td>Retrieve runtime secrets</td><td>TLS + IAM auth</td><td>No embedded credentials in code/config</td></tr>
    <tr><td>Curated Database</td><td>Encryption at Rest &amp; Transit</td><td>Data encryption enforcement</td><td>KMS/Key Vault policy</td><td>Protect data in motion and at rest</td></tr>
    <tr><td>Validation Processor</td><td>Threat Detection &amp; Response</td><td>Security telemetry and alerting</td><td>GuardDuty/Defender integration</td><td>Detect anomalous behavior and respond</td></tr>
    <tr><td>Validation Processor</td><td>Secure CI/CD Assurance</td><td>Deployment gate checks</td><td>Pipeline policy checks</td><td>Only compliant builds promoted to higher environments</td></tr>
    <tr><td>Threat Modelling &amp; Security Design Review</td><td>Policy Enforcement &amp; Management</td><td>Design controls to policy mapping</td><td>Control evidence linkage</td><td>Architecture decisions traceable to controls</td></tr>
    <tr><td>Policy Enforcement &amp; Management</td><td>Validation Processor</td><td>Configuration and policy compliance checks</td><td>Policy API / config scan</td><td>Continuous assurance</td></tr>
    <tr><td>Audit Logging &amp; Compliance Monitoring</td><td>Monitoring and Alerts</td><td>Control evidence and compliance telemetry</td><td>Log forwarding</td><td>Support audits and governance reporting</td></tr>
    <tr><td>Data Lineage &amp; Governance</td><td>Curated Database</td><td>Lineage capture and classification tags</td><td>Metadata sync</td><td>Improve traceability and accountability</td></tr>
    <tr><td>Cost Optimization &amp; Usage Monitoring</td><td>Monitoring and Alerts</td><td>Budget/cost anomaly alerts</td><td>Cost Explorer / Cost Management API</td><td>Operational governance and optimization</td></tr>
  """

  match = re.search(
    r'(<h[1-3][^>]*>\s*11\.\s*Architecture Connections\s*</h[1-3]>.*?<tbody>)(.*?)(</tbody>)',
    body_html,
    flags=re.DOTALL | re.IGNORECASE,
  )
  if not match:
    return body_html

  section_rows = match.group(2)
  if re.search(r'Identity\s*&amp;\s*Access\s*Management|Threat\s*Detection\s*&amp;\s*Response|Policy\s*Enforcement\s*&amp;\s*Management', section_rows, flags=re.IGNORECASE):
    return body_html

  return body_html[:match.start()] + match.group(1) + section_rows + secure_connections_rows + match.group(3) + body_html[match.end():]
        
def _ensure_roadmaps_and_use_case_details(body_html: str) -> str:
  """Ensure HLD page includes Roadmaps and Use case details sections between 1 and 6."""

  gate_roadmap_rows = """
      <tr><td>Gate 1: Discovery to Alpha (Implementation foundation)</td><td>Weeks 0-12 (Q1)</td><td>Discovery complete, architecture baseline agreed, and DEV environment established</td><td>Cost linkage: establish baseline assumptions for Section 17 (compute, storage, security setup, delivery effort)</td></tr>
      <tr><td>Gate 2: Alpha to Private Beta (Initial implementation)</td><td>Weeks 13-24 (Q2)</td><td>Core service implemented across DEV and TEST with limited PRIVATE-BETA environment access</td><td>Cost linkage: validate run-rate assumptions for integration, test automation, monitoring, and support cover</td></tr>
      <tr><td>Gate 3: Private Beta to Public Beta (Scale implementation)</td><td>Weeks 25-36 (Q3)</td><td>PRE-PROD and PUBLIC-BETA environments operational with expanded onboarding and resilience tests</td><td>Cost linkage: refresh Section 17 estimates for scaling, data transfer, observability, and operational readiness</td></tr>
      <tr><td>Gate 4: Public Beta to Live (Production implementation)</td><td>Weeks 37-48 (Q4)</td><td>PROD and DR environments approved for live service with full operational handover</td><td>Cost linkage: confirm business-as-usual costs across production support, resilience controls, and compliance operations</td></tr>
      <tr><td>Gate 5: Live to Decommission (Exit implementation)</td><td>Post-live retirement window</td><td>Service retirement executed with ARCHIVE/DECOM environments and data/service closure controls</td><td>Cost linkage: capture decommission and archive costs, license termination impacts, and end-of-life transition effort</td></tr>
"""

  # Remove previously injected blocks so we can reposition safely/idempotently.
  body_html = re.sub(
    r'<!-- SECTION 13C: ROADMAPS -->.*?</div>\s*<!-- SECTION 13D: USE CASE DETAILS -->.*?</div>',
    '',
    body_html,
    flags=re.DOTALL | re.IGNORECASE,
  )

  # Remove appended styled duplicates introduced by earlier insertion logic.
  body_html = re.sub(
    r'<div[^>]*>\s*<h2[^>]*id="section(?:5|6)a"[^>]*>.*?</h2>.*?</div>',
    '',
    body_html,
    flags=re.DOTALL | re.IGNORECASE,
  )
  body_html = re.sub(
    r'<div[^>]*>\s*<h2[^>]*>\s*[56]a\.\s*Roadmaps\s*</h2>.*?</div>',
    '',
    body_html,
    flags=re.DOTALL | re.IGNORECASE,
  )
  body_html = re.sub(
    r'<div[^>]*>\s*<h2[^>]*id="section(?:5|6)b"[^>]*>.*?</h2>.*?</div>',
    '',
    body_html,
    flags=re.DOTALL | re.IGNORECASE,
  )
  body_html = re.sub(
    r'<div[^>]*>\s*<h2[^>]*>\s*[56]b\.\s*Use case details\s*</h2>.*?</div>',
    '',
    body_html,
    flags=re.DOTALL | re.IGNORECASE,
  )

  # If a roadmap section already exists in Confluence-native storage HTML, normalize
  # its table rows so Gate 1-5 are always present, regardless of section numbering.
  body_html = re.sub(
    r'(<h[1-3][^>]*>\s*(?:\d+[a-z]?\.?\s*)?Roadmaps\s*</h[1-3]>.*?<tbody>)(.*?)(</tbody>)',
    r'\1' + gate_roadmap_rows + r'\3',
    body_html,
    flags=re.DOTALL | re.IGNORECASE,
  )

  # Skip insertion if sections already exist, regardless of numbering (e.g., 6/19).
  has_roadmaps = bool(
    re.search(r'<h[1-3][^>]*>\s*(?:\d+[a-z]?\.?\s*)?Roadmaps\s*</h[1-3]>', body_html, flags=re.IGNORECASE)
  )
  has_use_case = bool(
    re.search(r'<h[1-3][^>]*>\s*(?:\d+[a-z]?\.?\s*)?Use\s+case\s+details\s*</h[1-3]>', body_html, flags=re.IGNORECASE)
  )
  if has_roadmaps and has_use_case:
    return body_html

  new_sections = """
<!-- SECTION 6A: ROADMAPS -->
<div style="background-color: #fff7ed; border-left: 5px solid #ea580c; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section6a" style="color: #c2410c; margin-top: 0;">6a. Roadmaps</h2>
  <p><em>Capture full lifecycle delivery milestones with timeline, environment progression, and linked cost assumptions.</em></p>
  <table>
    <thead>
      <tr><th>Milestone</th><th>Timeline</th><th>Outcome</th><th>Dependencies / Risks</th></tr>
    </thead>
    <tbody>
      <tr><td>Gate 1: Discovery to Alpha (Implementation foundation)</td><td>Weeks 0-12 (Q1)</td><td>Discovery complete, architecture baseline agreed, and DEV environment established</td><td>Cost linkage: establish baseline assumptions for Section 17 (compute, storage, security setup, delivery effort)</td></tr>
      <tr><td>Gate 2: Alpha to Private Beta (Initial implementation)</td><td>Weeks 13-24 (Q2)</td><td>Core service implemented across DEV and TEST with limited PRIVATE-BETA environment access</td><td>Cost linkage: validate run-rate assumptions for integration, test automation, monitoring, and support cover</td></tr>
      <tr><td>Gate 3: Private Beta to Public Beta (Scale implementation)</td><td>Weeks 25-36 (Q3)</td><td>PRE-PROD and PUBLIC-BETA environments operational with expanded onboarding and resilience tests</td><td>Cost linkage: refresh Section 17 estimates for scaling, data transfer, observability, and operational readiness</td></tr>
      <tr><td>Gate 4: Public Beta to Live (Production implementation)</td><td>Weeks 37-48 (Q4)</td><td>PROD and DR environments approved for live service with full operational handover</td><td>Cost linkage: confirm business-as-usual costs across production support, resilience controls, and compliance operations</td></tr>
      <tr><td>Gate 5: Live to Decommission (Exit implementation)</td><td>Post-live retirement window</td><td>Service retirement executed with ARCHIVE/DECOM environments and data/service closure controls</td><td>Cost linkage: capture decommission and archive costs, license termination impacts, and end-of-life transition effort</td></tr>
    </tbody>
  </table>
  <p><strong>Lifecycle costing rule:</strong> each gate above must update Section 17 with revised build/run assumptions for the environments introduced at that stage.</p>
</div>

<!-- SECTION 6B: USE CASE DETAILS -->
<div style="background-color: #f0fdf4; border-left: 5px solid #16a34a; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section6b" style="color: #15803d; margin-top: 0;">6b. Use case details</h2>
  <p><em>Describe key scenarios so architecture decisions remain tied to user and business outcomes.</em></p>
  <table>
    <thead>
      <tr><th>Use Case</th><th>Primary Actor</th><th>Trigger</th><th>Main Flow</th><th>Success Criteria</th></tr>
    </thead>
    <tbody>
      <tr><td>Inbound file ingestion</td><td>Business system</td><td>Scheduled data drop</td><td>Upload -> validate -> queue -> curate</td><td>File processed without data loss</td></tr>
      <tr><td>Operational monitoring</td><td>Support analyst</td><td>Alert raised</td><td>Detect -> triage -> resolve -> close</td><td>Incident resolved within SLA</td></tr>
      <tr><td>Data consumption</td><td>Reporting user</td><td>Dashboard refresh</td><td>Query curated dataset -> render insight</td><td>Trusted and timely reporting output</td></tr>
    </tbody>
  </table>
</div>
"""

  marker = "<!-- SECTION 7: HLD OPTIONS -->"
  if marker in body_html:
    return body_html.replace(marker, new_sections + "\n" + marker, 1)

  # For synced Confluence storage HTML (no SECTION comments), avoid appending at end.
  h2_marker = re.search(r'<h2[^>]*>\s*7\.\s*Architecture Decision\s*&ndash;\s*HLD Options\s*</h2>', body_html, flags=re.IGNORECASE)
  if h2_marker:
    return body_html[:h2_marker.start()] + new_sections + "\n" + body_html[h2_marker.start():]
  return body_html


_FAST_FILL_BODY = """\
    <ac:structured-macro ac:name="expand">
      <ac:parameter ac:name="title">Click to view project-type guidance table</ac:parameter>
      <ac:rich-text-body>
    <p><strong>Use this guide to prioritise which sections to fill based on your project type:</strong></p>
    <table>
      <thead><tr><th>Project Type</th><th>Fill First</th><th>Mandatory Patterns (Section 8)</th><th>Skip / Later</th></tr></thead>
      <tbody>
        <tr>
          <td><strong>New data pipeline / analytics on AWS</strong><br/><em>e.g. disease surveillance, lab data ingestion</em></td>
          <td>Sections 1\u20136, then 9 (Context), 10 (Components), 11 (Connections), 13 (Data Flows)</td>
          <td>INF-01, INF-05, 3C, 6A, 6B, 6C, 7A, 7B, 8a (Backup)<br/>+ pick ingestion: 1B or 1C or 1D</td>
          <td>TSA-NET-02 unless public-facing; Section 17 (Cost) until option agreed</td>
        </tr>
        <tr>
          <td><strong>Public-facing API or web application</strong><br/><em>e.g. data portal, UKHSA public dashboard</em></td>
          <td>Sections 1\u20136, then 8 (Pattern Selection: TSA-NET-02, 6A\u2013C), 10\u201311</td>
          <td>INF-01, INF-04, INF-05, TSA-NET-02 (ALB+WAF), 6A, 6B, 6C, 7A, 7B, 8a</td>
          <td>1D (streaming) unless real-time needed; 3D (time-series) unless metrics</td>
        </tr>
        <tr>
          <td><strong>Hybrid / on-prem + cloud workload</strong><br/><em>e.g. HALO LZ migration, legacy system lift</em></td>
          <td>Sections 1\u20134 (esp. As-Is in 3a/3b), then 8 (INF-02, INF-04), 10 (Components)</td>
          <td>INF-01, INF-02 (Direct Connect/VPN), INF-04 (Split DNS), INF-05, 6A, 6B, 6C</td>
          <td>TSA-NET-02 unless public endpoint; Sections 15\u201317 after design agreed</td>
        </tr>
        <tr>
          <td><strong>ML / data science platform</strong><br/><em>e.g. SageMaker, EMR Spark, model training</em></td>
          <td>Sections 1\u20136, then 8 (2C, 3C, 5A, 5C, INF-06), 13 (Data Flows)</td>
          <td>INF-01, INF-05, 3C, 2C, 5A, 6A, 6B, 6C, 6D (if PII), 7A, 8a</td>
          <td>TSA-NET-02 unless model API is public; 3B unless BI reporting also needed</td>
        </tr>
        <tr>
          <td><strong>Real-time / streaming system</strong><br/><em>e.g. IoT, live alerting, event-driven pipeline</em></td>
          <td>Sections 1\u20136, then 8 (1D, 2B, 3D, 4A), 10 (Components), 11 (Connections)</td>
          <td>INF-01, INF-05, 1D, 2B, 3D, 6A, 6B, 6C, 7A, 7B, 8a</td>
          <td>1B (batch) not needed; 3B only if historical reporting also required</td>
        </tr>
        <tr>
          <td><strong>Lightweight / one-off data transfer</strong><br/><em>e.g. single on-prem extract to S3, one-time file migration</em></td>
          <td>Sections 1\u20132 (Overview + Introduction), 9 (Context), 10 (Components), 11 (Connections)</td>
          <td>INF-01, INF-02 (Direct Connect/VPN or SFTP), 6A, 6B, 6C</td>
          <td>Sections 3\u20137 (Background, Pain Points, Requirements, HLD Options); Sections 12\u201319 unless data is sensitive or recurring</td>
        </tr>
      </tbody>
    </table>
    <p>&#128204; <strong>INF-01 (Landing Zone) and INF-05 (Federated Identity via Entra ID) are mandatory for ALL workloads</strong> \u2014 they are applied automatically even if not explicitly selected in Section 8.</p>
    <p>&#128204; <strong>6A (Access Control), 6B (Encryption), 6C (Network Security) and 7A (Centralised Logging) are also mandatory</strong> for all new data workloads under UKHSA Secure by Design policy.</p>
      </ac:rich-text-body>
    </ac:structured-macro>"""

_HOW_TO_USE_BODY = """\
    <ac:structured-macro ac:name="expand">
      <ac:parameter ac:name="title">Click to view step-by-step instructions</ac:parameter>
      <ac:rich-text-body>
    <p><strong>Recommended approach: use the Data Solution Architecture Questionnaire to drive this page automatically.</strong></p>
    <ol>
      <li><strong>Fill in the <a href="/wiki/spaces/CDA/pages/521438060/Data+Solution+Architecture+Questionnaire">Data Solution Architecture Questionnaire</a></strong> \u2014 tick patterns, add context, and run the sync script. It will populate Sections 9\u201314 of this page and regenerate all diagrams automatically.<br/>
      <code>python confluence_sync_questionnaire_to_main.py</code></li>
      <li><strong>Or fill this page directly \u2014 follow this sequence:</strong>
        <ul>
          <li><strong>Sections 1\u20132</strong> (Solution Overview + Introduction): front-sheet for governance, plain-English description, business outcomes, strategic alignment</li>
          <li><strong>Sections 3\u20134</strong> (Background + Pain Points): as-is architecture snapshot and current pain points \u2014 drives the \u201cwhy we\u2019re changing\u201d narrative</li>
          <li><strong>Sections 5\u20136</strong> (Functional + Non-Functional Requirements): what the solution must do and at what performance/security levels</li>
          <li><strong>Section 7</strong> (HLD Options): 2\u20133 architectural options with pros/cons and evaluation criteria \u2014 needed for governance gate</li>
          <li><strong>Section 8</strong> (Pattern Selection \u2014 8a to 8f): select approved UKHSA patterns for ingestion, processing, storage, integration, governance/security, infrastructure (INF), and target state (TSA). <strong>INF-01 and INF-05 are always mandatory.</strong></li>
          <li><strong>Section 9</strong> (Context Entities): external actors, systems, and partners \u2014 drives the Context View diagram</li>
          <li><strong>Section 10</strong> (Architecture Components): every component with its layer, technology, and cloud \u2014 drives the Solution Architecture and Logical View diagrams</li>
          <li><strong>Section 11</strong> (Architecture Connections): source \u2192 destination flows with protocol and auth \u2014 drives all connection diagrams</li>
          <li><strong>Section 12</strong> (Network Segmentation): VPC/subnet CIDRs, connectivity type, security group rules \u2014 drives the Network Segregation diagram</li>
          <li><strong>Section 13</strong> (Data Flows): numbered flows with sensitivity, format, and frequency</li>
          <li><strong>Section 14</strong> (Dataset Inventory): named datasets and relationships \u2014 drives the Dataset Relationship diagram</li>
        </ul>
      </li>
      <li><strong>Run diagram generation</strong> after Sections 9\u201314 are populated:<br/>
      <code>python confluence_update_diagrams.py</code><br/>
      This generates: Solution Architecture, Data Flow, Dataset Relationship, Context View, Logical View, Authentication Flow, and Network Segregation diagrams.</li>
      <li><strong>Complete Sections 15\u201316</strong> (LLD Summary + Cost Comparison) after HLD options are agreed at governance review.</li>
      <li><strong>Complete Sections 17\u201319</strong> (Implementation Handover, Cost Comparison, Roadmaps) before handing over to the delivery team.</li>
      <li><strong>Generate the implementation pack</strong> (Terraform scaffolds + delivery summary):<br/>
      <code>python confluence_generate_implementation_pack.py</code></li>
    </ol>
    <p>&#9888; <strong>Do not edit the Architecture Diagrams child page or the LLD page directly.</strong> They are fully generated from this page \u2014 any manual edits will be overwritten on the next run.</p>
      </ac:rich-text-body>
    </ac:structured-macro>"""


def _replace_intro_panels(body_html: str) -> str:
  """Always ensure tip (Fast-Fill) and info (How to Use) intro macros exist with current content."""

  _FAST_FILL_MACRO = (
    '<ac:structured-macro ac:name="tip">\n'
    '  <ac:parameter ac:name="title">&#9889; Fast-Fill Guidance &#8212; Which Sections to Complete First</ac:parameter>\n'
    '  <ac:rich-text-body>\n'
    + _FAST_FILL_BODY + '\n'
    '  </ac:rich-text-body>\n'
    '</ac:structured-macro>'
  )

  _HOW_TO_USE_MACRO = (
    '<ac:structured-macro ac:name="info">\n'
    '  <ac:parameter ac:name="title">&#9654; How to Use This Page &#8212; Step-by-Step</ac:parameter>\n'
    '  <ac:rich-text-body>\n'
    + _HOW_TO_USE_BODY + '\n'
    '  </ac:rich-text-body>\n'
    '</ac:structured-macro>'
  )

  def _upsert_macro(html: str, macro_name: str, full_macro: str, title: str, new_body: str) -> str:
    """Replace entire macro (including title) with current content, or insert if missing."""
    open_tag = f'<ac:structured-macro ac:name="{macro_name}"'
    # Prefer finding the specific macro by its title parameter to avoid replacing
    # an unrelated macro of the same type (e.g. multiple info macros on one page).
    title_param = f'<ac:parameter ac:name="title">{title}</ac:parameter>'
    t_idx = html.find(title_param)
    if t_idx != -1:
      candidate = html.rfind(open_tag, 0, t_idx)
      open_idx = candidate if candidate != -1 and (t_idx - candidate) < 500 else -1
    else:
      open_idx = -1
    if open_idx == -1:
      open_idx = html.find(open_tag)
    if open_idx == -1:
      # Macro missing — insert before Table of Contents or first h2
      print(f"  Note: '{macro_name}' intro macro not found — inserting it now.")
      for marker in ['<!-- TABLE OF CONTENTS', '<h2>\U0001f4d1', '<h2>&#128209;', '<h2 id="section1"']:
        if marker in html:
          return html.replace(marker, full_macro + '\n\n' + marker, 1)
      return full_macro + '\n\n' + html

    # Find the matching closing tag by counting nested structured-macros
    depth = 0
    i = open_idx
    close_idx = -1
    while i < len(html):
      next_open  = html.find('<ac:structured-macro', i)
      next_close = html.find('</ac:structured-macro>', i)
      if next_close == -1:
        break
      if next_open != -1 and next_open < next_close:
        depth += 1
        i = next_open + len('<ac:structured-macro')
      else:
        depth -= 1
        if depth == 0:
          close_idx = next_close + len('</ac:structured-macro>')
          break
        i = next_close + len('</ac:structured-macro>')

    if close_idx == -1:
      return html  # malformed — leave untouched

    replacement = (
      f'<ac:structured-macro ac:name="{macro_name}">\n'
      f'  <ac:parameter ac:name="title">{title}</ac:parameter>\n'
      f'  <ac:rich-text-body>\n'
      + new_body + '\n'
      '  </ac:rich-text-body>\n'
      '</ac:structured-macro>'
    )
    return html[:open_idx] + replacement + html[close_idx:]

  body_html = _upsert_macro(body_html, "tip",  _FAST_FILL_MACRO,
                             '&#9889; Fast-Fill Guidance &#8212; Which Sections to Complete First',
                             _FAST_FILL_BODY)
  body_html = _upsert_macro(body_html, "info", _HOW_TO_USE_MACRO,
                             '&#9654; How to Use This Page &#8212; Step-by-Step',
                             _HOW_TO_USE_BODY)
  return body_html




# ── Pattern Diagram Generation ─────────────────────────────────────────────

def _pd_box(root, cid, label, x, y, w=180, h=50,
            fill="#dae8fc", stroke="#6c8ebf"):
    style = (f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};"
             f"strokeColor={stroke};fontSize=10;fontStyle=1;")
    c = ET.SubElement(root, "mxCell", id=cid, value=label,
                      style=style, parent="1", vertex="1")
    ET.SubElement(c, "mxGeometry", x=str(x), y=str(y),
                  width=str(w), height=str(h), **{"as": "geometry"})


def _pd_band(root, cid, label, x, y, w, h,
             fill="#e8eaf6", stroke="#5c6bc0", font_color="#1a237e"):
    style = (f"rounded=0;whiteSpace=wrap;html=1;fillColor={fill};"
             f"strokeColor={stroke};fontSize=11;fontStyle=1;"
             f"verticalAlign=top;fontColor={font_color};")
    c = ET.SubElement(root, "mxCell", id=cid, value=label,
                      style=style, parent="1", vertex="1")
    ET.SubElement(c, "mxGeometry", x=str(x), y=str(y),
                  width=str(w), height=str(h), **{"as": "geometry"})


def _pd_arrow(root, cid, src, tgt, label=""):
    style = ("rounded=0;orthogonalLoop=1;jettySize=auto;"
             "exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
             "entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
             "endArrow=block;endFill=1;")
    c = ET.SubElement(root, "mxCell", id=cid, value=label,
                      style=style, parent="1", source=src, target=tgt, edge="1")
    ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})


def _pd_down_arrow(root, cid, src, tgt, label=""):
    style = ("rounded=0;orthogonalLoop=1;jettySize=auto;"
             "exitX=0.5;exitY=1;exitDx=0;exitDy=0;"
             "entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
             "endArrow=block;endFill=1;")
    c = ET.SubElement(root, "mxCell", id=cid, value=label,
                      style=style, parent="1", source=src, target=tgt, edge="1")
    ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})


def _pd_title(root, cid, label, y, w=940):
    style = ("text;html=1;align=center;verticalAlign=middle;"
             "fillColor=#003366;strokeColor=none;fontColor=#ffffff;"
             "fontStyle=1;fontSize=13;")
    c = ET.SubElement(root, "mxCell", id=cid, value=label,
                      style=style, parent="1", vertex="1")
    ET.SubElement(c, "mxGeometry", x="10", y=str(y),
                  width=str(w), height="36", **{"as": "geometry"})


def _new_mxfile(diagram_name):
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name=diagram_name)
    model = ET.SubElement(
        diagram, "mxGraphModel",
        dx="1422", dy="762", grid="1", gridSize="10",
        guides="1", tooltips="1", connect="1", arrows="1",
        fold="1", page="1", pageScale="1",
        pageWidth="1169", pageHeight="827",
        math="0", shadow="0",
    )
    root_el = ET.SubElement(model, "root")
    ET.SubElement(root_el, "mxCell", id="0")
    ET.SubElement(root_el, "mxCell", id="1", parent="0")
    return mxfile, root_el


def _xml_str(mxfile):
    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def _gen_security_pattern_drawio() -> str:
    """SEC-01: Zero Trust Security Baseline — 5 horizontal layers, top-down."""
    mxfile, root = _new_mxfile("SEC-01 Zero Trust Security Baseline")
    _pd_title(root, "title", "SEC-01: Zero Trust Security Baseline", 10)

    layers = [
        ("Identity & Access", "#e3f2fd", "#1565c0", [
            ("Entra ID /\nIAM Identity Center", "#bbdefb", "#1565c0"),
            ("MFA\nEnforced", "#bbdefb", "#1565c0"),
            ("RBAC /\nLeast Privilege", "#bbdefb", "#1565c0"),
            ("IAM Roles\n(Federated)", "#bbdefb", "#1565c0"),
        ]),
        ("Network Controls", "#fce4ec", "#880e4f", [
            ("WAF /\nAWS Shield", "#f8bbd0", "#880e4f"),
            ("VPC + SG\n+ NACL", "#f8bbd0", "#880e4f"),
            ("zScaler\nZero Trust", "#f8bbd0", "#880e4f"),
            ("Direct Connect\n(Private)", "#f8bbd0", "#880e4f"),
        ]),
        ("Secrets & Encryption", "#f3e5f5", "#4a148c", [
            ("KMS CMK\nEncryption", "#e1bee7", "#4a148c"),
            ("Secrets\nManager", "#e1bee7", "#4a148c"),
            ("Service Control\nPolicies (SCPs)", "#e1bee7", "#4a148c"),
            ("Certificate\nManager", "#e1bee7", "#4a148c"),
        ]),
        ("Monitoring & Audit", "#fff3e0", "#e65100", [
            ("CloudTrail\nAudit Logs", "#ffe0b2", "#e65100"),
            ("GuardDuty\nThreat Detection", "#ffe0b2", "#e65100"),
            ("Security Hub\nDashboard", "#ffe0b2", "#e65100"),
            ("CloudWatch\nAlarms", "#ffe0b2", "#e65100"),
        ]),
        ("Data Layer", "#e8f5e9", "#1b5e20", [
            ("S3 (SSE-KMS)\nEncrypted", "#c8e6c9", "#1b5e20"),
            ("RDS /Aurora\nEncrypted", "#c8e6c9", "#1b5e20"),
            ("DynamoDB\nEncrypted", "#c8e6c9", "#1b5e20"),
            ("Backup & DR\n(AWS Backup)", "#c8e6c9", "#1b5e20"),
        ]),
    ]

    band_h, box_w, box_h = 110, 195, 55
    gap_x, box_y_offset = 10, 35
    y_start = 60
    for li, (layer_name, band_fill, band_stroke, comps) in enumerate(layers):
        y = y_start + li * (band_h + 10)
        _pd_band(root, f"band{li}", layer_name, 10, y, 940, band_h,
                 fill=band_fill, stroke=band_stroke, font_color=band_stroke)
        for ci, (label, fill, stroke) in enumerate(comps):
            x = gap_x + 15 + ci * (box_w + 15)
            _pd_box(root, f"b{li}{ci}", label, x, y + box_y_offset,
                    w=box_w, h=box_h, fill=fill, stroke=stroke)

    return _xml_str(mxfile)


def _gen_network_pattern_drawio() -> str:
    """NET-01: Segmented VPC Network — 4 horizontal tiers with components."""
    mxfile, root = _new_mxfile("NET-01 Segmented VPC Network Pattern")
    _pd_title(root, "title", "NET-01: Segmented VPC Network Pattern", 10)

    tiers = [
        ("Internet / External", "#fff9c4", "#f9a825", [
            ("Internet\nUsers", "#fff176", "#f9a825"),
            ("Third-Party\nAPIs", "#fff176", "#f9a825"),
            ("On-Premises DC\n(Direct Connect)", "#fff176", "#f9a825"),
        ]),
        ("Public Subnets (AZ-a / AZ-b)", "#fce4ec", "#c62828", [
            ("CloudFront\n+ WAF", "#ef9a9a", "#c62828"),
            ("Application\nLoad Balancer", "#ef9a9a", "#c62828"),
            ("NAT Gateway\n(Outbound)", "#ef9a9a", "#c62828"),
            ("Transfer Family\n(SFTP Ingest)", "#ef9a9a", "#c62828"),
        ]),
        ("Private App Subnets (AZ-a / AZ-b)", "#e8f5e9", "#1b5e20", [
            ("API Gateway\n(Private)", "#a5d6a7", "#1b5e20"),
            ("ECS Fargate /\nLambda", "#a5d6a7", "#1b5e20"),
            ("EC2 /\nContainers", "#a5d6a7", "#1b5e20"),
            ("Step Functions\nOrchestrator", "#a5d6a7", "#1b5e20"),
        ]),
        ("Private Data Subnets (AZ-a / AZ-b)", "#e3f2fd", "#0d47a1", [
            ("RDS / Aurora\n(Multi-AZ)", "#90caf9", "#0d47a1"),
            ("ElastiCache\n(Redis)", "#90caf9", "#0d47a1"),
            ("S3 (via\nGateway EP)", "#90caf9", "#0d47a1"),
            ("DynamoDB\n(Interface EP)", "#90caf9", "#0d47a1"),
        ]),
    ]

    band_h, box_w, box_h = 110, 195, 55
    y_start = 60
    prev_band_id = None
    for ti, (tier_name, band_fill, band_stroke, comps) in enumerate(tiers):
        y = y_start + ti * (band_h + 10)
        band_id = f"tier{ti}"
        _pd_band(root, band_id, tier_name, 10, y, 940, band_h,
                 fill=band_fill, stroke=band_stroke, font_color=band_stroke)
        for ci, (label, fill, stroke) in enumerate(comps):
            x = 15 + ci * (box_w + 20)
            bid = f"t{ti}b{ci}"
            _pd_box(root, bid, label, x, y + 35, w=box_w, h=box_h, fill=fill, stroke=stroke)
            if ci == 0 and prev_band_id is not None:
                _pd_down_arrow(root, f"arrow{ti}", f"t{ti-1}b0", bid)
        prev_band_id = band_id

    return _xml_str(mxfile)


def _gen_governance_pattern_drawio() -> str:
    """GOV-01: Governance Controls Flow — policy to compliance pipeline."""
    mxfile, root = _new_mxfile("GOV-01 Governance Controls Pattern")
    _pd_title(root, "title", "GOV-01: Governance Controls Pattern", 10)

    # Main flow (horizontal, y=130)
    main_flow = [
        ("UKHSA\nPolicies",     "#bbdefb", "#1565c0", "m0"),
        ("Control\nOwners",     "#c8e6c9", "#1b5e20", "m1"),
        ("Evidence\nCollection","#ffe0b2", "#e65100", "m2"),
        ("Risk\nRegister",      "#f8bbd0", "#880e4f", "m3"),
        ("ARB\nReview",         "#e1bee7", "#4a148c", "m4"),
        ("Compliance\nReport",  "#b2dfdb", "#004d40", "m5"),
    ]
    box_w, box_h, gap = 130, 60, 20
    start_x = 20
    y_main = 130
    for i, (label, fill, stroke, cid) in enumerate(main_flow):
        x = start_x + i * (box_w + gap)
        _pd_box(root, cid, label, x, y_main, w=box_w, h=box_h, fill=fill, stroke=stroke)
        if i > 0:
            _pd_arrow(root, f"ma{i}", main_flow[i-1][3], cid)

    # Supporting boxes below each (y=260)
    support = [
        ("Enterprise\nGuide Rails",   "#e3f2fd", "#1565c0", "m0"),
        ("Delegated\nAdmin Model",     "#e8f5e9", "#1b5e20", "m1"),
        ("Audit Trail\n(CloudTrail)",  "#fff3e0", "#e65100", "m2"),
        ("Governance\nDomains",        "#fce4ec", "#880e4f", "m3"),
        ("Architecture\nDecisions",    "#f3e5f5", "#4a148c", "m4"),
        ("Quarterly\nCadence",         "#e0f2f1", "#004d40", "m5"),
    ]
    y_sup = 260
    for i, (label, fill, stroke, parent_id) in enumerate(support):
        x = start_x + i * (box_w + gap)
        sid = f"s{i}"
        _pd_box(root, sid, label, x, y_sup, w=box_w, h=box_h, fill=fill, stroke=stroke)
        _pd_down_arrow(root, f"sa{i}", parent_id, sid)

    # Bottom strip: mandatory note
    _pd_band(root, "note", "Mandatory: All controls mapped to risk register and reviewed quarterly at ARB",
             20, 380, 900, 36, fill="#fff9c4", stroke="#f9a825", font_color="#e65100")

    return _xml_str(mxfile)


def _gen_dpia_pattern_drawio() -> str:
    """DPIA-01: DPIA + DSA Pattern — 3-phase gate flow."""
    mxfile, root = _new_mxfile("DPIA-01 Privacy & Data Sharing Pattern")
    _pd_title(root, "title", "DPIA-01: Privacy & Data Sharing (DPIA + DSA) Pattern", 10)

    phases = [
        ("DESIGN GATE", "#e3f2fd", "#1565c0", [
            ("DPIA\nInitiated",         "#bbdefb", "#1565c0"),
            ("DSA\nIdentified",         "#bbdefb", "#1565c0"),
            ("Data Minimisation\nApplied", "#bbdefb", "#1565c0"),
            ("Lawful Basis\nDocumented", "#bbdefb", "#1565c0"),
        ]),
        ("BUILD GATE", "#fce4ec", "#880e4f", [
            ("DPIA\nApproved",          "#f8bbd0", "#880e4f"),
            ("DSA\nSigned",             "#f8bbd0", "#880e4f"),
            ("Retention Controls\nSet", "#f8bbd0", "#880e4f"),
            ("Masking /\nTokenisation", "#f8bbd0", "#880e4f"),
        ]),
        ("OPERATE", "#e8f5e9", "#1b5e20", [
            ("Annual DPIA\nReview",      "#c8e6c9", "#1b5e20"),
            ("Data Events\nAudited",     "#c8e6c9", "#1b5e20"),
            ("DPA Compliance\nConfirmed","#c8e6c9", "#1b5e20"),
            ("Subject Access\nManaged",  "#c8e6c9", "#1b5e20"),
        ]),
    ]

    phase_w, box_w, box_h = 300, 130, 55
    y_header, y_boxes = 60, 120
    for pi, (phase_name, band_fill, band_stroke, items) in enumerate(phases):
        px = 15 + pi * (phase_w + 10)
        _pd_band(root, f"ph{pi}", phase_name, px, y_header, phase_w, 40,
                 fill=band_fill, stroke=band_stroke, font_color=band_stroke)
        for ii, (label, fill, stroke) in enumerate(items):
            iy = y_boxes + ii * (box_h + 10)
            _pd_box(root, f"p{pi}i{ii}", label, px + 10, iy,
                    w=box_w, h=box_h, fill=fill, stroke=stroke)
        if pi > 0:
            prev_mid = f"p{pi-1}i0"
            curr_mid = f"p{pi}i0"
            _pd_arrow(root, f"phar{pi}", prev_mid, curr_mid, "Gate →")

    _pd_band(root, "note",
             "Mandatory: DPIA must be completed before data flows go live. DSA required for cross-organisation sharing.",
             15, 380, 920, 36, fill="#fff9c4", stroke="#f9a825", font_color="#e65100")

    return _xml_str(mxfile)


def _gen_edap_pattern_drawio() -> str:
    """EDAP-01: EDAP Integration Pipeline — source to analytics flow."""
    mxfile, root = _new_mxfile("EDAP-01 EDAP Integration Pattern")
    _pd_title(root, "title", "EDAP-01: EDAP Analytics Platform Integration Pattern", 10)

    stages = [
        ("Source\nSystems",  "#fff9c4", "#f9a825", [
            "SFTP Push\n(3rd Party)",
            "REST API\n(Pull/ECS)",
            "Stream\n(Kinesis)",
            "Azure Blob\n(DataSync)",
        ]),
        ("Ingestion\nLayer",  "#fce4ec", "#c62828", [
            "Transfer Family\n(SFTP Push)",
            "ECS Fargate\n(Pull Tasks)",
            "Kinesis Firehose\n(Streaming)",
            "S3 Staging /\nCleared",
        ]),
        ("Raw\nLayer",       "#e8f5e9", "#1b5e20", [
            "Step Functions\n(I2R Workflow)",
            "Glue ETL\n(Parquet/Snappy)",
            "RRD Tagging\n(Metadata)",
            "Glue Catalog\n+ Lake Formation",
        ]),
        ("Conform\nLayer",   "#e3f2fd", "#0d47a1", [
            "Step Functions\n(R2C Workflow)",
            "Glue Transform\n+ DataBrew",
            "Conform Tables\n(TBAC)",
            "Redshift Spectrum\n(External)",
        ]),
        ("DataMart /\nExport", "#f3e5f5", "#4a148c", [
            "Redshift RA3\n(DataMart)",
            "Athena\n(Ad-hoc Query)",
            "API Gateway\n(Export REST)",
            "Export Store\n(S3 Parquet)",
        ]),
        ("Analytics\nAccess", "#e0f2f1", "#004d40", [
            "Power BI\n(Gateway EC2)",
            "SageMaker\n(Notebooks)",
            "QuickSight\n(Enterprise)",
            "WorkSpaces\n(Data Scientists)",
        ]),
    ]

    stage_w, box_w, box_h, gap_y = 145, 125, 52, 8
    x_start = 10
    y_header, y_boxes = 58, 110
    prev_stage_first = None
    for si, (stage_name, band_fill, band_stroke, items) in enumerate(stages):
        sx = x_start + si * (stage_w + 8)
        _pd_band(root, f"stg{si}", stage_name, sx, y_header, stage_w, 40,
                 fill=band_fill, stroke=band_stroke, font_color=band_stroke)
        for ii, label in enumerate(items):
            iy = y_boxes + ii * (box_h + gap_y)
            bid = f"s{si}b{ii}"
            fill = band_fill
            _pd_box(root, bid, label, sx + 10, iy, w=box_w, h=box_h,
                    fill=fill, stroke=band_stroke)
        if prev_stage_first is not None:
            _pd_arrow(root, f"stgar{si}", prev_stage_first, f"s{si}b0")
        prev_stage_first = f"s{si}b0"

    _pd_band(root, "note",
             "EDAP Mandate: All new UKHSA analytical workloads must integrate with EDAP or justify non-EDAP pattern via ARB.",
             10, 380, 940, 36, fill="#fff9c4", stroke="#f9a825", font_color="#e65100")

    return _xml_str(mxfile)


_PATTERN_DIAGRAMS = [
    ("approved-pattern-security",   "Security Pattern (SEC-01)",            _gen_security_pattern_drawio),
    ("approved-pattern-network",    "Network Segmentation Pattern (NET-01)", _gen_network_pattern_drawio),
    ("approved-pattern-governance", "Governance Controls Pattern (GOV-01)",  _gen_governance_pattern_drawio),
    ("approved-pattern-dpia-dsa",   "DPIA + DSA Pattern (DPIA-01)",          _gen_dpia_pattern_drawio),
    ("approved-pattern-edap",       "EDAP Integration Pattern (EDAP-01)",    _gen_edap_pattern_drawio),
]

_PATTERN_DRAWIO_MACRO = (
    '<ac:structured-macro ac:name="drawio" ac:schema-version="1">'
    '<ac:parameter ac:name="border">true</ac:parameter>'
    '<ac:parameter ac:name="viewerToolbar">true</ac:parameter>'
    '<ac:parameter ac:name="simpleViewer">false</ac:parameter>'
    '<ac:parameter ac:name="width">100%</ac:parameter>'
    '<ac:parameter ac:name="height">560</ac:parameter>'
    '<ac:parameter ac:name="zoom">110</ac:parameter>'
    '<ac:parameter ac:name="editable">true</ac:parameter>'
    '<ac:parameter ac:name="diagramDisplayName">{display_name}</ac:parameter>'
    '<ac:parameter ac:name="diagramName">{filename}</ac:parameter>'
    '<ac:parameter ac:name="pageId">{page_id}</ac:parameter>'
    '</ac:structured-macro>'
)


def _replace_pattern_placeholder(html_body: str, diagram_key: str,
                                  filename: str, display_name: str,
                                  page_id: str) -> str:
    """Replace [[DIAGRAM:diagram_key]] (and wrapping <p> tags) with the draw.io macro."""
    macro = _PATTERN_DRAWIO_MACRO.format(
        display_name=display_name, filename=filename, page_id=page_id,
    )
    token_re = re.compile(
        r"\[\[\s*DIAGRAM\s*:\s*" + re.escape(diagram_key) + r"\s*\]\]",
        re.IGNORECASE,
    )
    wrapped_re = re.compile(
        r"<p[^>]*>\s*(?:<strong[^>]*>)?" + token_re.pattern + r"(?:</strong>)?\s*</p>",
        re.IGNORECASE,
    )
    new_html, n = wrapped_re.subn(macro, html_body)
    if n == 0:
        new_html, _ = token_re.subn(macro, html_body)
    return new_html


def _upsert_pattern_diagrams(session: requests.Session, base_url: str,
                              space_key: str, patterns_page_id: str,
                              page_html: str) -> str:
    """Generate pattern draw.io files, upload them, and replace placeholders in page_html."""
    updated_html = page_html
    for diagram_key, display_name, generator_fn in _PATTERN_DIAGRAMS:
        filename = f"{diagram_key}.drawio"
        print(f"  Generating pattern diagram: {filename} ...")
        try:
            xml_content = generator_fn()
            upload_attachment(session, base_url, patterns_page_id,
                              filename, xml_content.encode("utf-8"))
            updated_html = _replace_pattern_placeholder(
                updated_html, diagram_key, filename, display_name, patterns_page_id,
            )
            print(f"    Uploaded and placeholder replaced: {filename}")
        except Exception as exc:
            print(f"    Warning: could not generate/upload {filename}: {exc}")
    return updated_html


def main() -> None:
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    configured_title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "").strip()
    # Try the configured/default title first, then known page titles used by this template.
    title_candidates = list(dict.fromkeys([
        configured_title or "High-level Design (HLD) Solution Architecture Template",
        "High-level Design (HLD) Solution Architecture Template",
        "Architecture Diagrams",
    ]))

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    page = None
    last_error = None
    for title in title_candidates:
        try:
            print(f"Finding main page '{title}'...")
            page = find_page_by_title(session, base_url, space_key, title)
            break
        except ValueError as exc:
            last_error = exc

    if not page:
        raise ValueError(
            f"Main page not found in space '{space_key}'. Tried titles: {', '.join(title_candidates)}"
        ) from last_error

    current_body = page.get("body", {}).get("storage", {}).get("value", "")
    if current_body:
      save_synced_template(current_body)

    page_id = page["id"]

    workspace = os.path.dirname(__file__)
    plan_path = os.path.join(workspace, "QUESTIONNAIRE_PLAN.md")

    if not os.path.exists(plan_path):
        raise FileNotFoundError("Required QUESTIONNAIRE_PLAN.md file was not found in workspace root.")

    print("Uploading questionnaire plan...")
    with open(plan_path, "rb") as f:
        plan_attachment = upload_attachment(session, base_url, page_id, "QUESTIONNAIRE_PLAN.md", f.read())

    plan_link = attachment_link(base_url, plan_attachment)

    print("Updating main page with unified requirements and design template...")
    synced_template = load_synced_template()
    if synced_template:
      body_html = _update_questionnaire_plan_link(synced_template, plan_link)
      body_html = _replace_intro_panels(body_html)
      body_html = _ensure_secure_by_design_link(body_html)
      body_html = _ensure_secure_by_design_pattern_rows(body_html)
      body_html = _ensure_secure_by_design_coverage_matrix(body_html)
      body_html = _ensure_architecture_components_with_security_governance(body_html)
      body_html = _ensure_context_entities_populated(body_html)
      body_html = _ensure_secure_by_design_connections(body_html)
      body_html = _ensure_approved_patterns_link(body_html)
      body_html = _ensure_network_segmentation_section(body_html)
      body_html = _ensure_roadmaps_and_use_case_details(body_html)
    else:
      body_html = build_main_html(plan_link)
      body_html = _ensure_secure_by_design_link(body_html)
      body_html = _ensure_secure_by_design_pattern_rows(body_html)
      body_html = _ensure_secure_by_design_coverage_matrix(body_html)
      body_html = _ensure_architecture_components_with_security_governance(body_html)
      body_html = _ensure_context_entities_populated(body_html)
      body_html = _ensure_secure_by_design_connections(body_html)
      body_html = _ensure_approved_patterns_link(body_html)
      body_html = _ensure_network_segmentation_section(body_html)
      body_html = _ensure_roadmaps_and_use_case_details(body_html)

    result = update_page_body(session, base_url, page_id, page["version"]["number"], page["title"], body_html)

    patterns_page_title = os.getenv("CONFLUENCE_APPROVED_PATTERNS_PAGE_TITLE", "Architecture Patterns Reference").strip()
    if patterns_page_title:
      print(f"Upserting child page: {patterns_page_title}...")
      patterns_html = build_approved_patterns_page_html()

      # First pass: upsert to discover/create the page and get its ID.
      patterns_result = upsert_child_page(
        session,
        base_url,
        space_key,
        page_id,
        patterns_page_title,
        patterns_html,
      )
      patterns_page_id = str(patterns_result.get("id", ""))

      if patterns_page_id:
        print(f"  Patterns page ID: {patterns_page_id} — uploading diagrams...")
        patterns_html_with_diagrams = _upsert_pattern_diagrams(
          session, base_url, space_key, patterns_page_id, patterns_html,
        )

        # Second pass: re-fetch current version then update with draw.io macros.
        try:
          patterns_page_live = find_page_by_title(session, base_url, space_key, patterns_page_title)
          patterns_version = patterns_page_live["version"]["number"]
          patterns_title_live = patterns_page_live["title"]
        except ValueError:
          patterns_version = patterns_result.get("version", {}).get("number", 1)
          patterns_title_live = patterns_page_title
        update_page_body(
          session, base_url, patterns_page_id,
          patterns_version, patterns_title_live,
          patterns_html_with_diagrams,
        )
        print(f"  Patterns page updated with {len(_PATTERN_DIAGRAMS)} diagrams.")
      else:
        print("  Warning: could not determine patterns page ID — diagrams not uploaded.")

    # Re-sync after update to keep local template aligned with latest live page.
    updated_body = result.get("body", {}).get("storage", {}).get("value")
    if updated_body:
      save_synced_template(updated_body)

    links = result.get("_links", {})
    page_url = f"{links.get('base', base_url)}{links.get('webui', '')}"
    print(f"Done: {page_url}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
