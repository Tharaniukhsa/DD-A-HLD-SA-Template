"""
Creates the Solution Architecture template page and its child pages on Confluence.
Reads all config from .env — no manual environment variables required.

Pages created:
  1. Solution Architecture          (child of CONFLUENCE_PARENT_PAGE_ID)
  2. Low Level Design (LLD)         (child of the page above)
  3. Architectural Decision Records (child of the page above)
"""

import json
import os
import sys

import certifi
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from requests_negotiate_sspi import HttpNegotiateAuth

load_dotenv()

# ---------------------------------------------------------------------------
# Auth & TLS
# ---------------------------------------------------------------------------

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
    verify = kwargs.pop("verify", True)
    
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


# ---------------------------------------------------------------------------
# Confluence REST helpers
# ---------------------------------------------------------------------------

def _tls() -> bool | str:
    return get_tls_verify()


def find_existing_page(session: requests.Session, base_url: str,
                        space_key: str, title: str) -> dict | None:
    """Return the existing page dict (with version info) if found, else None."""
    resp = _make_request(
        session, "GET",
        f"{base_url}/rest/api/content",
        params={"spaceKey": space_key, "title": title, "expand": "version,ancestors"},
        headers={"Accept": "application/json"},
        verify=_tls(),
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0] if results else None


def update_page(session: requests.Session, base_url: str, page: dict,
                body_html: str) -> dict:
    """Increment version and overwrite the page body."""
    page_id = page["id"]
    new_version = page["version"]["number"] + 1
    payload = {
        "version": {"number": new_version},
        "title": page["title"],
        "type": "page",
        "body": {
            "storage": {
                "value": body_html,
                "representation": "storage",
            }
        },
    }
    response = _make_request(
        session, "PUT",
        f"{base_url}/rest/api/content/{page_id}",
        data=json.dumps(payload),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        verify=_tls(),
        timeout=30,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to update page '{page['title']}'. "
            f"Status: {response.status_code}. Response: {response.text}"
        )
    result = response.json()
    links = result.get("_links", {})
    url = f"{links.get('base', base_url)}{links.get('webui', '')}"
    print(f"  Updated: {page['title']}\n    URL: {url}")
    return result


def create_page(session: requests.Session, base_url: str, space_key: str,
                title: str, body_html: str, parent_id: str) -> dict:
    """Create a new page, or update it in-place if it already exists."""
    existing = find_existing_page(session, base_url, space_key, title)
    if existing:
        print(f"  Page already exists — updating: {title}")
        return update_page(session, base_url, existing, body_html)

    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "ancestors": [{"id": parent_id}],
        "body": {
            "storage": {
                "value": body_html,
                "representation": "storage",
            }
        },
    }
    response = _make_request(
        session, "POST",
        f"{base_url}/rest/api/content",
        data=json.dumps(payload),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        verify=_tls(),
        timeout=30,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create page '{title}'. "
            f"Status: {response.status_code}. Response: {response.text}"
        )
    page = response.json()
    links = page.get("_links", {})
    url = f"{links.get('base', base_url)}{links.get('webui', '')}"
    print(f"  Created: {title}\n    URL: {url}")
    return page


# ---------------------------------------------------------------------------
# HTML Templates
# ---------------------------------------------------------------------------

MAIN_PAGE_HTML = """
<table>
  <tbody>
    <tr><th>Version</th><td>3.0 Alpha / Private Beta / Public Beta / Live / Decommission</td></tr>
    <tr><th>Publish date</th><td>Jun 23, 2025</td></tr>
  </tbody>
</table>

<h2>Index</h2>
<p>Reference points for further refinement of the HLD are as follows:</p>
<h3>Beta Stage</h3>
<ul>
  <li>All sections in Discovery and Alpha Stages</li>
  <li>5. System Overview and Architecture (more detailed)
    <ul>
      <li>5.1 Enterprise Architecture</li>
      <li>5.2 Solution Architecture
        <ul>
          <li>5.2.4 Module Decomposition</li>
          <li>5.2.5 Data Flow Diagram (DFD)</li>
          <li>5.2.6 Functional Architecture</li>
          <li>5.2.7 Non-functional Architecture (more robust requirement)</li>
        </ul>
      </li>
      <li>5.3 Cloud Platform / Microsoft 365 Platforms</li>
      <li>5.4 Integration Architecture</li>
      <li>5.5 FinOps / CCOE</li>
      <li>5.6 DevOps / SDLC</li>
      <li>5.7 QAT (QA and Testing)</li>
      <li>5.8 Service Management</li>
      <li>5.9 Data Design and Architecture</li>
      <li>5.11 Cyber Product Assurance / Cyber Risk Assurance / Cyber Architecture (in-depth)</li>
      <li>5.12 Identity Management
        <ul><li>5.12.1 Identity Management (role-based access, authentication strategies)</li></ul>
      </li>
      <li>5.13 Technology Stack</li>
    </ul>
  </li>
</ul>
<h3>Live Stage</h3>
<ul>
  <li>All sections in Discovery, Alpha and Beta Stages</li>
  <li>5.10 Enterprise Networking (final network diagrams, VPNs, firewalls, load balancers)</li>
  <li>5.11 Cyber Product Assurance / Cyber Risk Assurance / Cyber Architecture (ongoing)</li>
  <li>5.12 Identity Management / Information Governance and Data Protection
    <ul><li>5.12.2 Information Governance and Protection (record management, GDPR…)</li></ul>
  </li>
</ul>

<h2>Engagement Log</h2>
<p>This will be updated for each phase of the project as it transitions from Discovery &rarr; Beta.</p>
<table>
  <thead>
    <tr><th>Areas</th><th>Dates</th><th>Outcome / Commentary / Actions</th></tr>
  </thead>
  <tbody>
    <tr><td>Enterprise Architecture</td><td></td><td></td></tr>
    <tr><td>Cyber Security</td><td></td><td></td></tr>
    <tr><td>Data Architecture</td><td></td><td></td></tr>
    <tr><td>Data Governance</td><td></td><td></td></tr>
    <tr><td>Records and Information Management</td><td></td><td></td></tr>
    <tr><td>Data Release and Acquisition</td><td></td><td></td></tr>
    <tr><td>Privacy</td><td></td><td></td></tr>
    <tr><td>IT Service Management</td><td></td><td></td></tr>
    <tr><td>HPC Platform and Infrastructure</td><td></td><td></td></tr>
    <tr><td>DevOps and Development Leads</td><td></td><td></td></tr>
    <tr><td>Technology QA / Testing Function</td><td></td><td></td></tr>
    <tr><td>User Interface / User Experience</td><td></td><td></td></tr>
    <tr><td>FinOps</td><td></td><td></td></tr>
    <tr><td>M365 Function</td><td></td><td></td></tr>
    <tr><td>Identity Function</td><td></td><td></td></tr>
  </tbody>
</table>

<h2>Introduction</h2>
<h3>Executive Summary</h3>
<p>Provide a brief overview of the project, including its purpose, high-level goals, and the scope of this document. The section should introduce the audience to the system being designed without going into detailed technical specifics.</p>

<h3>Business and Technology Context</h3>
<ul>
  <li>Describe the business objectives that the system aims to achieve and provide an overview of the technology landscape. Explain how the project aligns with broader business goals and identify key stakeholders and their roles.</li>
  <li>Business Context</li>
  <li>Technology Context</li>
</ul>

<h3>Assumptions and Constraints</h3>
<p>Insert key assumptions that the design is based on. Also list any constraints that could impact the design, such as technical limitations, budgetary restrictions, or regulatory requirements.</p>
<h4>Assumptions</h4>
<p>The design of this project is based on the following key assumptions:</p>
<table>
  <thead><tr><th>Category</th><th>Details</th></tr></thead>
  <tbody>
    <tr><td>Operational &amp; User Assumptions</td><td></td></tr>
    <tr><td>Scope &amp; Delivery Assumptions</td><td></td></tr>
    <tr><td>Infrastructure &amp; Architecture Assumptions</td><td></td></tr>
    <tr><td>Data &amp; Processing Assumptions</td><td></td></tr>
  </tbody>
</table>
<h4>Constraints</h4>
<p>The solution is subject to the following constraints that shape the design:</p>
<table>
  <thead><tr><th>Category</th><th>Details</th></tr></thead>
  <tbody>
    <tr><td>Technical Constraints</td><td></td></tr>
    <tr><td>Security &amp; Governance Constraints</td><td></td></tr>
    <tr><td>Product &amp; Delivery Constraints</td><td></td></tr>
    <tr><td>Budgetary &amp; Resourcing Constraints</td><td></td></tr>
    <tr><td>Regulatory &amp; Compliance Constraints</td><td></td></tr>
  </tbody>
</table>

<h3>Deviations / Dispensations</h3>
<p>Specify any deviation from strategy and reference any associated ADRs involved. Detail how the deviation will be remediated and whether the technical debt will be addressed in the current project, or elsewhere.</p>
<table>
  <thead><tr><th>Deviation</th><th>Description</th><th>Rationale</th><th>Remediation / Technical Debt Plan</th></tr></thead>
  <tbody><tr><td></td><td></td><td></td><td></td></tr></tbody>
</table>

<h3>Key Architectural Decisions</h3>
<p>Architectural decision records can be raised at TACB to resolve a particular design issue. Please find a project-level ADR record in the page-tree below.</p>

<h2>Business Architecture</h2>
<h3>Business Architecture Overview</h3>
<p>Provide a high-level description of the business architecture. This section should explain the relationship between business processes, organisational structure, and the system being developed.</p>

<h3>Business Capability Model</h3>
<p>Outline the key business capabilities that the system will support or enable. Provide diagrams (using LeanIX) and LeanIX Fact Sheet URLs for Business Capabilities, participating applications, active or planned initiatives, etc. Describe how these capabilities align with the business strategy and how they will be enhanced or fulfilled by the new system. Please refer to the Business Capability Model - Architecture and Standards for the UKHSA business capabilities, Level 1 and Level 2.</p>

<h3>Business Processes and Workflow</h3>
<p>Provide an overview of the major business processes affected by the system. Describe the workflow changes or improvements that the system will introduce. Include high-level process diagrams if necessary.</p>

<h2>System Overview and Architecture</h2>
<p>In the following sections, please use the content as appropriate. If certain sections are not applicable, do not delete them; instead, indicate this by marking them as &ldquo;N/A&rdquo;.</p>

<h3>Strategic Platform Choices</h3>
<p>Insert description on strategic platform choice to show how it aligns with the organisation&rsquo;s long-term technology strategy and meets the initial project requirements, providing the necessary capabilities, performance, and flexibility to support both current needs and anticipated future enhancements. Insert links to project requirements.</p>
<ul>
  <li>As per UKHSA&rsquo;s Technology Code of Practice (TCOP) guidance, and aligned to the UK Government&rsquo;s general &lsquo;cloud-first&rsquo; policy, we are hosting the solution within UKHSA&rsquo;s Amazon Web Services (AWS) ecosystem. All services will be deployed within the eu-west-2 region in dedicated AWS accounts, vended as per the UCP/DXC ServiceNow process.</li>
  <li>All source code for the application will be hosted on UKHSA&rsquo;s Internal GitHub Organisation, with GitHub Actions used to deploy the various resources (i.e. Infrastructure-as-Code and Container deployment).</li>
</ul>
<table>
  <thead><tr><th>Gate</th><th>Type of Evidence Required</th></tr></thead>
  <tbody>
    <tr><td>Gate 1: Discovery to Alpha</td><td>Platform choices align with technology strategy and initial project requirements.</td></tr>
    <tr><td>Gate 2: Alpha to Beta Private</td><td>Platforms re-evaluated based on feedback and evolving needs.</td></tr>
    <tr><td>Gate 3: Private Beta to Public Beta</td><td>Platforms handle increased loads and meet user needs.</td></tr>
    <tr><td>Gate 4: Public Beta to Live</td><td>Platforms evaluated for full-scale deployment demands.</td></tr>
    <tr><td>Gate 5: Live to Decommission</td><td>Platforms reviewed for long-term sustainability and decommissioning plans.</td></tr>
  </tbody>
</table>

<h3>Enterprise Architecture</h3>
<p>Insert technology strategy and enterprise architecture standards and principles that this solution will align to and adhere to.</p>
<table>
  <thead><tr><th>EA Principle</th><th>How the Solution Aligns</th></tr></thead>
  <tbody>
    <tr><td>Prioritise cloud technologies</td><td>The system is fully deployed within UKHSA&rsquo;s AWS environment, using cloud native services such as CloudFront, S3, API Gateway, Fargate and Bedrock to ensure scalability and adherence to cloud first strategy.</td></tr>
    <tr><td>Adopt a product centric approach</td><td>LENS is delivered as an MVP with clear product boundaries, iterative development, and a roadmap shaped by user research, Alpha/Beta feedback, and continuous improvement cycles.</td></tr>
    <tr><td>Leverage core platforms and drive convergence</td><td>The design uses UKHSA&rsquo;s core identity platform (Entra ID), standard cloud patterns, and AWS-native services. It avoids bespoke integrations, supporting long-term convergence on approved enterprise platforms.</td></tr>
    <tr><td>Enable data sharing and exploitation</td><td>Structured workspaces, standardised metadata extraction, and vector based semantic search improve the organisation&rsquo;s ability to interrogate, reuse, and draw insights from scientific literature.</td></tr>
    <tr><td>Embrace innovation</td><td>The tool provides a safe exemplar for integrating LLMs, embeddings, and automated text extraction using AWS Bedrock and Docling.</td></tr>
    <tr><td>Build an enduring DDaT capability</td><td>By adopting modern engineering patterns (containerised services, CDK-based IaC, standardised identity and security controls), the solution strengthens reusable technical capabilities across the DDaT function.</td></tr>
    <tr><td>Strive for operational excellence</td><td>Although MVP focused, the architecture incorporates secure defaults, private networking, token validation, and observability pathways, creating a foundation for scaling to production grade operations.</td></tr>
  </tbody>
</table>
<table>
  <thead><tr><th>Gate</th><th>Type of Evidence Required</th></tr></thead>
  <tbody>
    <tr><td>Gate 1: Discovery to Alpha</td><td>Project aligns with enterprise technology strategy and architectural principles.</td></tr>
    <tr><td>Gate 2: Alpha to Beta Private</td><td>Technology choices validated for scalability and enterprise system integration.</td></tr>
    <tr><td>Gate 3: Private Beta to Public Beta</td><td>Architectural adherence maintained, accommodating user feedback and technology changes.</td></tr>
    <tr><td>Gate 4: Public Beta to Live</td><td>Architecture confirmed to align with long-term strategic goals and standards.</td></tr>
    <tr><td>Gate 5: Live to Decommission</td><td>Architectural strategy for system decommissioning approved, ensuring legacy integration and data retention compliance.</td></tr>
  </tbody>
</table>

<h3>Solution Architecture</h3>
<h4>System Architecture Overview</h4>
<p>Insert an overall description of the system, including its key components and the technologies used. This section should give the reader a high-level understanding of what the system is and how it is structured.</p>

<h4>Architecture Components</h4>
<p>Fill in the table below. Valid layers: <strong>Edge, Network, Platform, Application, Data</strong>. Once complete, run <code>confluence_update_diagrams.py</code> to auto-generate the diagram.</p>
<table>
  <thead><tr><th>No</th><th>Component Name</th><th>Layer</th><th>Technology</th><th>Description</th></tr></thead>
  <tbody>
    <tr><td>1</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>2</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>3</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>4</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>5</td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

<h4>Architecture Connections</h4>
<p>Define how components connect. Component names must match the Architecture Components table above.</p>
<table>
  <thead><tr><th>From Component</th><th>To Component</th><th>Connection Label</th></tr></thead>
  <tbody>
    <tr><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td></tr>
  </tbody>
</table>

<h4>Generated Solution Architecture Diagram</h4>
<p><strong>[[DIAGRAM:solution-architecture]]</strong></p>

<h4>Context Diagram</h4>
<p>Insert a diagram that illustrates how the system interacts with external systems, users, and other stakeholders. The diagram should highlight the system boundaries and key interfaces.</p>

<h4>Use Case Diagrams</h4>
<p>Insert high-level use case diagrams that identify the primary actors and their interactions with the system. These diagrams should help in understanding the system&rsquo;s functionality from the user&rsquo;s perspective.</p>

<h4>Module Decomposition</h4>
<p>Break down the system into major modules or components. Describe the responsibilities of each module and how they interact with each other. This section should provide a clear view of the system&rsquo;s internal structure.</p>
<table>
  <thead><tr><th>Type</th><th>Description</th></tr></thead>
  <tbody><tr><td></td><td></td></tr></tbody>
</table>
<table>
  <thead><tr><th>No</th><th>Component Name</th><th>Component Type</th><th>Technology</th><th>Security Focused Component Description</th></tr></thead>
  <tbody><tr><td></td><td></td><td></td><td></td><td></td></tr></tbody>
</table>

<h4>Data Flow Diagram (DFD)</h4>
<p>Insert a high-level flow of data between different components of the system. Identify key data sources, destinations, and major data stores. This section should help in understanding how data moves through the system.</p>
<p>The diagram below shows how data generally traverses the end-to-end system in a use-case agnostic way. Specific flows will be detailed in the LLD.</p>

<h4>Data Flow Entries</h4>
<p>Fill in each data flow. Once complete, run <code>confluence_update_diagrams.py</code> to auto-generate the diagram.</p>
<table>
  <thead><tr><th>Flow ID</th><th>Source</th><th>Destination</th><th>Data Description</th><th>Protocol</th></tr></thead>
  <tbody>
    <tr><td>F1</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>F2</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>F3</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>F4</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>F5</td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

<h4>Generated Data Flow Diagram</h4>
<p><strong>[[DIAGRAM:data-flow]]</strong></p>

<h4>Functional Architecture</h4>
<p>Insert the high-level functional requirements and describe the functional components of the system. Explain how these components interact to deliver the required functionality.</p>
<p>Functional components described in the Module Decomposition section above.</p>

<h4>Non-functional Architecture</h4>
<p>Insert the non-functional requirements, such as performance, scalability, and security. Describe the architectural considerations that address these requirements and how they impact the overall design.</p>
<table>
  <thead><tr><th>NFR Category</th><th>Approach / Considerations</th></tr></thead>
  <tbody>
    <tr><td>Performance</td><td></td></tr>
    <tr><td>Scalability</td><td></td></tr>
    <tr><td>Availability</td><td></td></tr>
    <tr><td>Reliability / Resilience</td><td></td></tr>
    <tr><td>Security</td><td></td></tr>
    <tr><td>Data Protection &amp; Privacy</td><td></td></tr>
    <tr><td>Operability</td><td></td></tr>
    <tr><td>Maintainability</td><td></td></tr>
    <tr><td>Cost Efficiency</td><td></td></tr>
  </tbody>
</table>

<h3>Cloud Platform / Microsoft 365 Platforms</h3>
<p>Provide an overview of alignment to the cloud platform strategy, leveraging the chosen cloud provider&rsquo;s services to ensure scalability, reliability, and alignment with enterprise architecture standards. Where appropriate, indicate how the solution leverages Microsoft 365 and utilises features such as SharePoint, OneDrive, etc.</p>

<h3>Integration Architecture</h3>
<p>Provide an overview of the integration points within the system. Describe the key interfaces and protocols used for data exchange and explain how different components will be integrated.</p>
<table>
  <thead><tr><th>Integration Point</th><th>Description</th><th>Interface / Protocol</th><th>Notes / Purpose</th></tr></thead>
  <tbody>
    <tr><td>Frontend &rarr; API Gateway</td><td></td><td></td><td></td></tr>
    <tr><td>Frontend &rarr; S3 (Raw Files)</td><td></td><td></td><td></td></tr>
    <tr><td>Frontend &rarr; Entra ID</td><td></td><td></td><td></td></tr>
    <tr><td>API Gateway &rarr; Backend Services</td><td></td><td></td><td></td></tr>
    <tr><td>Backend &harr; Workspace DB (Aurora)</td><td></td><td></td><td></td></tr>
    <tr><td>Backend &harr; Document DB (Aurora)</td><td></td><td></td><td></td></tr>
    <tr><td>Backend &harr; S3 Raw Documents</td><td></td><td></td><td></td></tr>
    <tr><td>Backend &harr; S3 Document Chunks</td><td></td><td></td><td></td></tr>
    <tr><td>Backend &harr; S3 Vectors (Embeddings)</td><td></td><td></td><td></td></tr>
    <tr><td>Embeddings / Search &rarr; Bedrock</td><td></td><td></td><td></td></tr>
  </tbody>
</table>

<h3>FinOps / CCOE</h3>
<p>Provide an overview on the adherence to FinOps practices, ensuring optimised cloud financial management by providing cost visibility, enabling resource optimisation, and fostering collaboration across teams. Also provide a section to show alignment with Cloud Centre of Excellence (CCoE) guidelines.</p>
<table>
  <thead><tr><th>FinOps Area</th><th>Approach (MVP-Focused, Concise)</th></tr></thead>
  <tbody>
    <tr><td>Cost Visibility</td><td></td></tr>
    <tr><td>Cost Allocation &amp; Ownership</td><td></td></tr>
    <tr><td>Usage Optimisation</td><td></td></tr>
    <tr><td>Scalability &amp; Efficiency</td><td></td></tr>
    <tr><td>Data Storage Management</td><td></td></tr>
    <tr><td>Model Usage Efficiency</td><td></td></tr>
    <tr><td>Future Maturity</td><td></td></tr>
  </tbody>
</table>

<h3>DevOps / SDLC</h3>
<p>Provide an overview of the DevOps practices, including integration of CI/CD pipelines, automated testing, and infrastructure as code (IaC) to streamline the development, reduce time-to-market, and maintain consistency across environments. Outline how the solution follows established SDLC phases, ensuring alignment with best practices and compliance standards throughout the software lifecycle.</p>

<h3>QAT (QA and Testing)</h3>
<p>Describe the high-level testing strategy, outlining how the solution follows the QA and testing standards, ensuring that all components are rigorously validated for functionality, performance, security and compliance.</p>
<table>
  <thead><tr><th>Testing Area</th><th>Approach</th><th>Purpose / Assurance</th></tr></thead>
  <tbody>
    <tr><td>Functional Testing</td><td>Component level and API level tests for each backend service; frontend workflow testing for all primary user journeys.</td><td>Ensures core functionality behaves as expected and validates end to end flows such as upload &rarr; extract &rarr; embed &rarr; search.</td></tr>
    <tr><td>Integration &amp; End to End Testing</td><td>Full-path testing across frontend, API Gateway, backend services, S3, Bedrock, Aurora and DynamoDB.</td><td>Confirms interoperability of all components and validates correct handling of orchestration and failure scenarios.</td></tr>
    <tr><td>Performance Testing</td><td>Light performance checks on document upload, extraction pipeline, and semantic search. Cloud-native autoscaling relied upon for elasticity.</td><td>Ensures acceptable latency for internal users and demonstrates that the MVP can handle expected non-critical workloads.</td></tr>
    <tr><td>Security Testing</td><td>Validate token handling, JWT authorisation, role-based access control and secure-by-default service configurations. Includes static analysis and dependency scanning.</td><td>Confirms compliance with UKHSA security expectations and validates that identity, access and data flows are secure.</td></tr>
    <tr><td>Compliance &amp; Data Protection</td><td>Verification that only non-sensitive public scientific literature is processed; audit and logging checks aligned to governance needs.</td><td>Ensures alignment with data protection and IG standards, minimising risk around handling and retention.</td></tr>
    <tr><td>Operability Testing</td><td>Logging, error handling, and basic monitoring validated in Test/Pre-Prod environments.</td><td>Confirms operational visibility, stability and readiness for Private Beta.</td></tr>
    <tr><td>Maintainability Testing</td><td>CI pipeline runs automated tests (unit, component, smoke) and validates CDK-based infrastructure deployments.</td><td>Ensures consistency across environments and reduces risk of configuration drift.</td></tr>
    <tr><td>User Acceptance Testing (UAT)</td><td>Carried out by Evidence Reviewers using realistic scenarios and datasets.</td><td>Ensures usability, workflow alignment and functional suitability for Private Beta.</td></tr>
  </tbody>
</table>

<h3>Service Management</h3>
<p>Describe how the solution conforms to the IT service management (ITSM) framework, ensuring that all aspects of service delivery, support and operations are aligned with best practices such as ITIL. Also outline any integration of existing ITSM tools and processes to facilitate efficient incident management, change management, service request fulfilment, ensuring minimal disruption to business operations.</p>
<table>
  <thead><tr><th>Area</th><th>Summary (MVP Appropriate, Concise)</th></tr></thead>
  <tbody>
    <tr><td>Service Onboarding</td><td></td></tr>
    <tr><td>Support Model</td><td></td></tr>
    <tr><td>Incident Management</td><td></td></tr>
    <tr><td>Change &amp; Release Management</td><td></td></tr>
    <tr><td>Monitoring &amp; Alerting</td><td></td></tr>
    <tr><td>Access &amp; Request Fulfilment</td><td></td></tr>
    <tr><td>Operational Governance</td><td></td></tr>
  </tbody>
</table>

<h3>Data Design and Architecture</h3>
<p>Describe the high-level data architecture, including the data models, key data entities and relationships. Discuss how data will be stored, accessed, and managed across the system.</p>
<p><em>Insert Entity Relationship Diagram (ERD) here.</em></p>

<h3>Enterprise Networking</h3>
<p>Outline how the solution adheres to the enterprise networking standards, ensuring secure, reliable, and efficient connectivity across all network environments. The solution should follow best practices for network segmentation, traffic management, and redundancy to optimise performance and ensure high availability.</p>

<h3>Cyber Product Assurance / Cyber Risk Assurance / Cyber Architecture</h3>
<p>Outline the security requirements for the system, including confidentiality, integrity, availability, and privacy considerations. Provide a high-level overview of the security architecture, detailing how security is integrated into the system&rsquo;s design.</p>
<table>
  <thead><tr><th>Area</th><th>Requirement</th><th>How It Is Addressed</th></tr></thead>
  <tbody>
    <tr><td>Confidentiality</td><td></td><td></td></tr>
    <tr><td>Integrity</td><td></td><td></td></tr>
    <tr><td>Availability</td><td></td><td></td></tr>
    <tr><td>Privacy</td><td></td><td></td></tr>
    <tr><td>Security Governance</td><td></td><td></td></tr>
  </tbody>
</table>
<ul>
  <li>Identity &amp; Access Management</li>
  <li>Network &amp; Boundary Security</li>
  <li>Data Security</li>
  <li>Application Security</li>
  <li>Cyber Product Assurance</li>
  <li>Cyber Risk Assurance</li>
  <li>Cyber Architecture</li>
</ul>

<h3>Identity Management / Information Governance and Data Protection</h3>
<p>Insert a section to indicate how the solution will adhere to the identity management guidance, ensuring robust authentication, authorisation, and user lifecycle management. Also add a description on the compliance to data protection and impact analysis policies.</p>
<table>
  <thead><tr><th>Control Area</th><th>Implementation</th></tr></thead>
  <tbody>
    <tr><td>Authentication</td><td>Entra ID OIDC flows; MSAL token acquisition; no local accounts.</td></tr>
    <tr><td>Authorisation</td><td>RBAC using Entra ID groups/app roles; enforced at API Gateway and backend services.</td></tr>
    <tr><td>Access Assurance</td><td>Centralised identity governance, MFA, Conditional Access, and password policies inherited from UKHSA.</td></tr>
    <tr><td>Data Minimisation</td><td>Only Entra object IDs stored for workspace membership; no personal profile data or credentials stored.</td></tr>
    <tr><td>Lifecycle Management</td><td>Access updated automatically through JML processes in Entra ID; token expiry and revocation follow OAuth2 standards.</td></tr>
    <tr><td>Audit &amp; Logging</td><td>Identity events captured through API Gateway logs, backend request tracing, and standard Azure/Entra audit logs.</td></tr>
  </tbody>
</table>
<h4>Identity Management Gates</h4>
<table>
  <thead><tr><th>Gate</th><th>Type of Evidence Required</th></tr></thead>
  <tbody>
    <tr><td>Gate 1: Discovery to Alpha</td><td>Identity management and access control strategies designed, aligning with project needs.</td></tr>
    <tr><td>Gate 2: Alpha to Beta Private</td><td>Implemented identity solutions tested and compliant in controlled environments.</td></tr>
    <tr><td>Gate 3: Private Beta to Public Beta</td><td>Identity solutions scaled, ensuring robust access management.</td></tr>
    <tr><td>Gate 4: Public Beta to Live</td><td>Identity management finalised for full-scale deployment.</td></tr>
    <tr><td>Gate 5: Live to Decommission</td><td>Identity and access management during decommissioning effectively managed.</td></tr>
  </tbody>
</table>
<h4>Information Governance and Protection Gates</h4>
<table>
  <thead><tr><th>Gate</th><th>Type of Evidence Required</th></tr></thead>
  <tbody>
    <tr><td>Gate 1: Discovery to Alpha</td><td>Information governance and protection policies established and aligned with compliance requirements.</td></tr>
    <tr><td>Gate 2: Alpha to Beta Private</td><td>Data protection measures integrated and effective.</td></tr>
    <tr><td>Gate 3: Private Beta to Public Beta</td><td>Ongoing monitoring and adjustments to data governance compliant.</td></tr>
    <tr><td>Gate 4: Public Beta to Live</td><td>Full compliance with data protection regulations confirmed.</td></tr>
    <tr><td>Gate 5: Live to Decommission</td><td>Data safeguarding during decommissioning process ensured.</td></tr>
  </tbody>
</table>

<h3>Technology Stack</h3>
<p>Insert a section to list the technologies that will be used in the system, including programming languages, frameworks, databases, and other tools. Explain the rationale behind these choices.</p>
<table>
  <thead><tr><th>Category</th><th>Technology / Service</th><th>Description &amp; Rationale</th></tr></thead>
  <tbody><tr><td></td><td></td><td></td></tr></tbody>
</table>
"""


LLD_PAGE_HTML = """
<p>This Low Level Design (LLD) document provides the detailed technical specification for each component described in the Solution Architecture. It is intended for engineers and technical leads implementing the system.</p>

<h2>Document Information</h2>
<table>
  <thead><tr><th>Field</th><th>Detail</th></tr></thead>
  <tbody>
    <tr><td>Related HLD</td><td><em>Link to Solution Architecture page</em></td></tr>
    <tr><td>Status</td><td>Draft</td></tr>
    <tr><td>Owner</td><td></td></tr>
    <tr><td>Last Updated</td><td></td></tr>
  </tbody>
</table>

<h2>Component Detail</h2>
<p>For each component identified in the Solution Architecture Module Decomposition, provide the following detail:</p>
<table>
  <thead><tr><th>Component</th><th>Responsibility</th><th>Technology</th><th>Key Interfaces</th><th>Configuration / Notes</th></tr></thead>
  <tbody><tr><td></td><td></td><td></td><td></td><td></td></tr></tbody>
</table>

<h2>Detailed Data Flow</h2>
<p>Describe each use-case-specific data flow. Reference the high-level DFD from the HLD and expand per scenario.</p>
<table>
  <thead><tr><th>Flow ID</th><th>Scenario / Use Case</th><th>Steps</th><th>Data In</th><th>Data Out</th><th>Error Handling</th></tr></thead>
  <tbody><tr><td></td><td></td><td></td><td></td><td></td><td></td></tr></tbody>
</table>

<h2>API Specifications</h2>
<p>List all internal and external API endpoints, their methods, request/response schemas, and authentication requirements.</p>
<table>
  <thead><tr><th>Endpoint</th><th>Method</th><th>Description</th><th>Auth Required</th><th>Request Schema</th><th>Response Schema</th></tr></thead>
  <tbody><tr><td></td><td></td><td></td><td></td><td></td><td></td></tr></tbody>
</table>

<h2>Database / Data Store Design</h2>
<p>Describe the schema, indexing strategy, and partitioning approach for each data store.</p>
<table>
  <thead><tr><th>Data Store</th><th>Type</th><th>Schema / Key Structure</th><th>Indexing</th><th>Retention Policy</th></tr></thead>
  <tbody><tr><td></td><td></td><td></td><td></td><td></td></tr></tbody>
</table>

<h2>Infrastructure as Code (IaC) Overview</h2>
<p>Describe the IaC approach (e.g. AWS CDK), the stacks defined, and the deployment order.</p>
<table>
  <thead><tr><th>Stack Name</th><th>Description</th><th>Key Resources</th><th>Deployment Order</th></tr></thead>
  <tbody><tr><td></td><td></td><td></td><td></td></tr></tbody>
</table>

<h2>Security Controls Detail</h2>
<p>Expand on the security controls summarised in the HLD, providing implementation-level detail for each control.</p>
<table>
  <thead><tr><th>Control</th><th>Implementation Detail</th><th>Owner</th><th>Status</th></tr></thead>
  <tbody><tr><td></td><td></td><td></td><td></td></tr></tbody>
</table>

<h2>Deployment Architecture</h2>
<p>Describe the environment topology (dev / test / staging / prod), the CI/CD pipeline stages, and promotion criteria.</p>
<table>
  <thead><tr><th>Environment</th><th>Purpose</th><th>Account / Region</th><th>Promotion Criteria</th></tr></thead>
  <tbody>
    <tr><td>Development</td><td></td><td></td><td></td></tr>
    <tr><td>Test / QA</td><td></td><td></td><td></td></tr>
    <tr><td>Staging / Pre-Prod</td><td></td><td></td><td></td></tr>
    <tr><td>Production</td><td></td><td></td><td></td></tr>
  </tbody>
</table>

<h2>Open Items and Risks</h2>
<table>
  <thead><tr><th>ID</th><th>Description</th><th>Owner</th><th>Target Date</th><th>Status</th></tr></thead>
  <tbody><tr><td></td><td></td><td></td><td></td><td></td></tr></tbody>
</table>
"""


ADR_PAGE_HTML = """
<p>This page is the project-level log of all Architectural Decision Records (ADRs). Each ADR documents a significant architectural decision, its context, the options considered, the decision made, and the consequences.</p>
<p>Individual ADR pages are linked in the table below and maintained as child pages of this page.</p>

<h2>ADR Log</h2>
<table>
  <thead>
    <tr>
      <th>ADR ID</th>
      <th>Title</th>
      <th>Status</th>
      <th>Date</th>
      <th>Decision Summary</th>
      <th>Link</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>ADR-001</td><td></td><td>Proposed / Accepted / Superseded</td><td></td><td></td><td></td></tr>
  </tbody>
</table>

<h2>ADR Template</h2>
<p>Use the following structure when creating a new ADR child page under this page.</p>

<h3>Context</h3>
<p>Describe the situation and forces at play that led to this decision. Include the problem statement and any constraints.</p>

<h3>Decision Drivers</h3>
<ul>
  <li>Driver 1</li>
  <li>Driver 2</li>
</ul>

<h3>Options Considered</h3>
<table>
  <thead><tr><th>Option</th><th>Pros</th><th>Cons</th></tr></thead>
  <tbody>
    <tr><td>Option A</td><td></td><td></td></tr>
    <tr><td>Option B</td><td></td><td></td></tr>
  </tbody>
</table>

<h3>Decision</h3>
<p>State the decision made and why it was chosen over the alternatives.</p>

<h3>Consequences</h3>
<p>Describe the resulting context after applying the decision. Include positive and negative consequences and any technical debt introduced.</p>

<h3>Related ADRs / Links</h3>
<ul><li></li></ul>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    parent_page_id = os.getenv("CONFLUENCE_PARENT_PAGE_ID", "173314084")
    main_page_title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "Solution Architecture")

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    print(f"\nCreating pages under space '{space_key}', parent ID {parent_page_id}...\n")

    # 1. Main Solution Architecture page
    main_page = create_page(
        session, base_url, space_key,
        main_page_title, MAIN_PAGE_HTML,
        parent_page_id,
    )
    main_id = main_page["id"]

    # 2. Low Level Design — child of main page
    create_page(
        session, base_url, space_key,
        "Low Level Design (LLD)", LLD_PAGE_HTML,
        main_id,
    )

    # 3. Architectural Decision Records — child of main page
    create_page(
        session, base_url, space_key,
        "Architectural Decision Records", ADR_PAGE_HTML,
        main_id,
    )

    print("\nAll pages created successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
