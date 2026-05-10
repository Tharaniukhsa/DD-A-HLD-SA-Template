import html
import json
import os
import sys
import re
from io import BytesIO

import certifi
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from requests_negotiate_sspi import HttpNegotiateAuth

load_dotenv()


def get_auth_methods():
    """Return tuple of (primary_auth, fallback_auth) to try Bearer first, then Basic."""
    api_token = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    
    primary = ("Bearer", api_token) if api_token else HttpNegotiateAuth()
    fallback = HTTPBasicAuth(user_email, api_token) if user_email and api_token else None
    return (primary, fallback)


def apply_auth(session: requests.Session, auth_result: tuple | object) -> None:
    """Apply authentication to a session. Handles Bearer tokens or standard auth."""
    if isinstance(auth_result, tuple) and auth_result[0] == "Bearer":
        session.headers.update({"Authorization": f"Bearer {auth_result[1]}"})
    else:
        session.auth = auth_result


def _make_request(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    """
    Make HTTP request with automatic auth fallback.
    Tries primary auth first (Bearer), then falls back to Basic if 403 received.
    """
    api_token = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    verify = kwargs.pop("verify", get_tls_verify())
    
    # Try Bearer auth first if we have a token
    if api_token:
        session_copy = requests.Session()
        session_copy.headers.update(session.headers)
        session_copy.headers.update({"Authorization": f"Bearer {api_token}"})
        try:
            resp = session_copy.request(method, url, verify=verify, **kwargs)
            if resp.status_code != 403:
                return resp
        except Exception:
            pass
    
    # Fallback to Basic auth if we have email + token
    if user_email and api_token:
        session_copy = requests.Session()
        session_copy.headers.update(session.headers)
        session_copy.auth = HTTPBasicAuth(user_email, api_token)
        resp = session_copy.request(method, url, verify=verify, **kwargs)
        return resp
    
    # Last resort: use session as-is
    return session.request(method, url, verify=verify, **kwargs)


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
    # Try Bearer auth first
    if api_token:
        temp_session = requests.Session()
        temp_session.headers.update({"Authorization": f"Bearer {api_token}", "X-Atlassian-Token": "no-check"})
        try:
            if existing:
                att_id = existing[0]["id"]
                resp = temp_session.post(f"{url}/{att_id}/data", files=_make_files_payload(), verify=verify, timeout=30)
            else:
                resp = temp_session.post(url, files=_make_files_payload(), verify=verify, timeout=30)
            if resp.status_code != 403:
                if resp.status_code not in (200, 201):
                    raise RuntimeError(f"Failed to upload attachment '{filename}': {resp.status_code} {resp.text}")
                return resp.json()
        except Exception:
            pass
    
    # Fallback to Basic auth
    if user_email and api_token:
        temp_session = requests.Session()
        temp_session.auth = HTTPBasicAuth(user_email, api_token)
        temp_session.headers.update({"X-Atlassian-Token": "no-check"})
        if existing:
            att_id = existing[0]["id"]
            resp = temp_session.post(f"{url}/{att_id}/data", files=_make_files_payload(), verify=verify, timeout=30)
        else:
            resp = temp_session.post(url, files=_make_files_payload(), verify=verify, timeout=30)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to upload attachment '{filename}': {resp.status_code} {resp.text}")
        return resp.json()
    
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
  <ac:parameter ac:name="title">Fast Fill Guidance</ac:parameter>
  <ac:rich-text-body>
    <ul>
      <li>Write short, decision-ready content first. One sentence or one bullet per cell is enough for the first workshop pass.</li>
      <li>For each section, capture the business problem, the architectural impact, and the decision or action needed.</li>
      <li>Where useful, use named options, systems, teams, and measures rather than generic wording.</li>
    </ul>
  </ac:rich-text-body>
</ac:structured-macro>

<ac:structured-macro ac:name="info">
  <ac:parameter ac:name="title">How to Use This Page</ac:parameter>
  <ac:rich-text-body>
    <ol>
      <li><strong>Discovery</strong> – fill in Sections 1–6 (Overview, Introduction, Background, Pain Points, Functional Requirements, Non-Functional Requirements) with the project team.</li>
      <li><strong>Design</strong> – complete Sections 7–13 (HLD options, pattern selection, components, connections, data flows, datasets, relationships).</li>
      <li><strong>Generate diagrams</strong> – run <code>confluence_update_diagrams.py</code> to auto-create all diagrams from the tables above.</li>
      <li><strong>Implementation pack</strong> – run <code>confluence_generate_implementation_pack.py</code> to output Terraform scaffolds and delivery summary.</li>
    </ol>
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

  <h3 id="section8a" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8a. Ingestion Patterns</h3>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected? (Y/N)</th><th>Notes / Justification</th></tr></thead>
  <tbody>
    <tr><td>1A</td><td>Batch File Ingestion</td><td></td><td></td></tr>
    <tr><td>1B</td><td>Real-Time Event Streaming</td><td></td><td></td></tr>
    <tr><td>1C</td><td>API / Web Service Pull</td><td></td><td></td></tr>
    <tr><td>1D</td><td>Database CDC (Change Data Capture)</td><td></td><td></td></tr>
  </tbody>
</table>

  <h3 id="section8b" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8b. Processing Patterns</h3>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected? (Y/N)</th><th>Notes / Justification</th></tr></thead>
  <tbody>
    <tr><td>2A</td><td>Batch ETL / ELT Pipeline</td><td></td><td></td></tr>
    <tr><td>2B</td><td>Stream Processing</td><td></td><td></td></tr>
    <tr><td>2C</td><td>Micro-Batch Processing</td><td></td><td></td></tr>
    <tr><td>2D</td><td>Serverless Function Processing</td><td></td><td></td></tr>
  </tbody>
</table>

  <h3 id="section8c" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8c. Storage Patterns</h3>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected? (Y/N)</th><th>Notes / Justification</th></tr></thead>
  <tbody>
    <tr><td>3A</td><td>Data Lake (Object Store)</td><td></td><td></td></tr>
    <tr><td>3B</td><td>Data Warehouse / Lakehouse</td><td></td><td></td></tr>
    <tr><td>3C</td><td>Relational Database</td><td></td><td></td></tr>
    <tr><td>3D</td><td>NoSQL / Document Store</td><td></td><td></td></tr>
    <tr><td>3E</td><td>In-Memory / Cache Store</td><td></td><td></td></tr>
  </tbody>
</table>

  <h3 id="section8d" style="color: #059669; margin-top: 20px; border-top: 2px solid #059669; padding-top: 10px;">8d. Governance, Security &amp; Operational Patterns</h3>
<table>
  <thead><tr><th>Pattern ID</th><th>Pattern Name</th><th>Layer</th><th>Selected? (Y/N)</th><th>Notes</th></tr></thead>
  <tbody>
    <tr><td>5A</td><td>Data Cataloguing</td><td>Governance</td><td></td><td></td></tr>
    <tr><td>5B</td><td>Data Lineage Tracking</td><td>Governance</td><td></td><td></td></tr>
    <tr><td>5C</td><td>Data Quality Framework</td><td>Governance</td><td></td><td></td></tr>
    <tr><td>6A</td><td>Encryption at Rest &amp; In Transit</td><td>Security</td><td></td><td></td></tr>
    <tr><td>6B</td><td>Role-Based Access Control (RBAC)</td><td>Security</td><td></td><td></td></tr>
    <tr><td>6C</td><td>Data Masking / Tokenisation</td><td>Security</td><td></td><td></td></tr>
    <tr><td>6D</td><td>Audit Logging</td><td>Security</td><td></td><td></td></tr>
    <tr><td>7A</td><td>Centralised Logging</td><td>Monitoring</td><td></td><td></td></tr>
    <tr><td>7B</td><td>Metrics &amp; Alerting</td><td>Monitoring</td><td></td><td></td></tr>
    <tr><td>7C</td><td>Distributed Tracing</td><td>Monitoring</td><td></td><td></td></tr>
    <tr><td>8A</td><td>Multi-Region / Multi-AZ</td><td>Resilience</td><td></td><td></td></tr>
    <tr><td>8B</td><td>Automated Backup &amp; Recovery</td><td>Resilience</td><td></td><td></td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 9: CONTEXT ENTITIES -->
<div style="background-color: #f0e8f8; border-left: 5px solid #7C3AED; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section9" style="color: #7C3AED; margin-top: 0;">9. Context Entities</h2>
<p><em>Define external actors, systems, and partners that interact with this solution. Drives the <strong>Context View diagram</strong>.</em></p>
<table>
  <thead><tr><th>Entity Name</th><th>Type (User / System / Partner / Service)</th><th>Interaction Description</th><th>Direction (In / Out / Both)</th></tr></thead>
  <tbody>
    <tr><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 10: ARCHITECTURE COMPONENTS -->
<div style="background-color: #f8f0e8; border-left: 5px solid #EA580C; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section10" style="color: #EA580C; margin-top: 0;">10. Architecture Components</h2>
<p><em>Drives the <strong>Solution Architecture</strong> and <strong>Logical View</strong> diagrams. Valid layers: <strong>Edge, Network, Platform, Application, Data</strong></em></p>
<table>
  <thead>
    <tr><th>No</th><th>Component Name</th><th>Layer</th><th>Technology / Service</th><th>Cloud (AWS/Azure/Both)</th><th>Description</th><th>Links to FR/NFR</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>2</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>3</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>4</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>5</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>6</td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
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
    <tr><td>D1</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>D2</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>D3</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>D4</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

  <h3 id="section13a" style="color: #D97706; margin-top: 20px; border-top: 2px solid #D97706; padding-top: 10px;">Dataset Relationships</h3>
<p><em>Define how datasets relate. Drives the ERD-style <strong>Dataset Relationship diagram</strong>.</em></p>
<table>
  <thead>
    <tr><th>From Dataset</th><th>To Dataset</th><th>Relationship Type (1:1 / 1:N / M:N)</th><th>Key Mapping (e.g. patient_id)</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

</div>
<!-- SECTION 14: AUTO-GENERATED DIAGRAMS -->
<div style="background-color: #e8f8f0; border-left: 5px solid #059669; padding: 15px; margin: 20px 0; border-radius: 4px;">
  <h2 id="section14" style="color: #059669; margin-top: 0;">14. Auto-Generated Diagrams</h2>
<p><em>All architectural diagrams are auto-generated from the tables above (Sections 10-13) and maintained on a separate page for clarity and editability.</em></p>

<p><strong>To generate or update diagrams:</strong> Run <code>confluence_update_diagrams.py</code> after completing the architecture tables.</p>

<p style="margin-top: 15px; font-size: 16px;"><strong><ac:link><ri:page ri:space-key="CDA" ri:content-title="Architecture Diagrams" /></ac:link></strong></p>

<h3>Diagram Types Generated</h3>
<ul>
  <li><strong>Context View</strong> – System boundary and external entities</li>
  <li><strong>Logical View</strong> – Services by responsibility and interaction</li>
  <li><strong>Solution Architecture</strong> – Layer-based component view (Edge, Network, Platform, Application, Data)</li>
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


def main() -> None:
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    configured_title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "").strip()
    # Try the configured/default title first, then known page titles used by this template.
    title_candidates = [
        configured_title or "Solution Architecture",
        "High-level Design (HLD) Solution Architecture Template",
        "Architecture Diagrams",
    ]

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
    else:
      body_html = build_main_html(plan_link)

    result = update_page_body(session, base_url, page_id, page["version"]["number"], page["title"], body_html)

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
