"""
Restore Solution Architecture page with comprehensive Requirements & Design Pack template.
Single source of truth for discovery → design → implementation.
Tables drive automated diagram generation and Terraform delivery.
"""

import json
import os
import sys

import certifi
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth

load_dotenv()


def get_tls_verify():
    ca_bundle = (os.getenv("CONFLUENCE_CA_BUNDLE") or "").strip()
    if ca_bundle and os.path.exists(ca_bundle):
        return ca_bundle
    if os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").strip().lower() in {"1", "true", "yes"}:
        return False
    return certifi.where()


def _make_request(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    api_token = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    verify = kwargs.pop("verify", get_tls_verify())
    
    if api_token:
        session_copy = requests.Session()
        session_copy.headers.update(kwargs.get("headers", {}))
        session_copy.headers.update({"Authorization": f"Bearer {api_token}"})
        try:
            resp = session_copy.request(method, url, verify=verify, **kwargs)
            if resp.status_code != 403:
                return resp
        except Exception:
            pass
    
    if user_email and api_token:
        session_copy = requests.Session()
        session_copy.headers.update(kwargs.get("headers", {}))
        session_copy.auth = HTTPBasicAuth(user_email, api_token)
        resp = session_copy.request(method, url, verify=verify, **kwargs)
        return resp
    
    return session.request(method, url, verify=verify, **kwargs)


def _accept_headers():
    return {"Accept": "application/json"}


def _json_headers():
    return {"Accept": "application/json", "Content-Type": "application/json"}


def find_page_by_title(session: requests.Session, base_url: str, space_key: str, title: str):
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


def update_page_body(session: requests.Session, base_url: str, page_id: str, version_number: int, title: str, body_html: str):
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


def build_requirements_design_pack():
    """Build the comprehensive Requirements & Design Pack template."""
    html = """<h1>Solution Architecture – Requirements &amp; Design Pack</h1>

<p><em>Single source of truth: complete this page during discovery workshops. The tables below drive automated diagram generation and Terraform delivery output.</em></p>

<hr/>

<h2>Fast Fill Guidance</h2>
<ul>
<li><strong>Write short, decision-ready content first.</strong> One sentence or one bullet per cell is enough for the first workshop pass.</li>
<li><strong>For each section,</strong> capture the business problem, the architectural impact, and the decision or action needed.</li>
<li><strong>Use named options, systems, teams, and measures</strong> rather than generic wording.</li>
</ul>

<h2>How to Use This Page</h2>
<ol>
<li><strong>Discovery –</strong> Fill in Sections 1–6 (Overview, Introduction, Background, Pain Points, Functional Requirements, Non-Functional Requirements) with the project team.</li>
<li><strong>Design –</strong> Complete Sections 7–13 (HLD options, pattern selection, components, connections, data flows, datasets, relationships).</li>
<li><strong>Generate diagrams –</strong> Run <code>confluence_update_diagrams.py</code> to auto-create all diagrams from the tables above.</li>
<li><strong>Implementation pack –</strong> Run <code>confluence_generate_implementation_pack.py</code> to output Terraform scaffolds and delivery summary.</li>
</ol>

<hr/>

<h2>1. Solution Overview</h2>
<p><em>Use this section as the front sheet for governance review. Keep each value concise and decision-oriented.</em></p>

<table>
<tbody>
<tr><th>Field</th><th>Value</th></tr>
<tr><td><strong>Solution Name</strong></td><td>e.g. National Surveillance Data Exchange</td></tr>
<tr><td><strong>Version</strong></td><td>0.1 – DRAFT</td></tr>
<tr><td><strong>Date</strong></td><td>e.g. 08 May 2026</td></tr>
<tr><td><strong>Solution Architect</strong></td><td>Named accountable architect</td></tr>
<tr><td><strong>Business Owner</strong></td><td>Named senior business owner</td></tr>
<tr><td><strong>Primary Stakeholders</strong></td><td>Key delivery, operational, and business stakeholders</td></tr>
<tr><td><strong>LeanIX Business Capability ID</strong></td><td>Capability reference or "TBC"</td></tr>
<tr><td><strong>Data Sensitivity Classification</strong></td><td>e.g. Official / Official-Sensitive / Personal Data</td></tr>
<tr><td><strong>Target Cloud Platform</strong></td><td>AWS / Azure / Hybrid</td></tr>
<tr><td><strong>Programme / Project Name</strong></td><td>Formal programme, portfolio, or project name</td></tr>
</tbody>
</table>

<hr/>

<h2>2. Introduction</h2>
<p><em>Describe what this solution is, why it is needed, and how it fits into the wider UKHSA operating and data landscape.</em></p>

<table>
<tbody>
<tr><th>Field</th><th>Detail</th></tr>
<tr><td><strong>Solution Description</strong></td><td>What the service does in plain English</td></tr>
<tr><td><strong>Business Capability Supported</strong></td><td>Which capability, service line, or mission outcome this supports</td></tr>
<tr><td><strong>Key Users / Data Consumers</strong></td><td>Who uses the outputs and what decisions or services they support</td></tr>
<tr><td><strong>Strategic Alignment</strong></td><td>Policies, strategies, or transformation drivers this aligns to (e.g. Data Strategy, Cloud First)</td></tr>
<tr><td><strong>Expected Business Outcomes</strong></td><td>2-4 measurable outcomes, e.g. reduced manual effort, faster reporting, improved quality</td></tr>
<tr><td><strong>Out of Scope</strong></td><td>Explicit exclusions to avoid ambiguity during design</td></tr>
</tbody>
</table>

<hr/>

<h2>3. Background</h2>
<p><em>Summarise why the work started, what exists today, and what the target end-state needs to achieve.</em></p>

<table>
<tbody>
<tr><th>Field</th><th>Detail</th></tr>
<tr><td><strong>Trigger / Business Driver</strong></td><td>What event, issue, or mandate has triggered the need for change</td></tr>
<tr><td><strong>Current State (As-Is)</strong></td><td>One-paragraph summary of today's process, systems, and known issues</td></tr>
<tr><td><strong>Desired Future State (To-Be)</strong></td><td>What better looks like from a business and architecture point of view</td></tr>
<tr><td><strong>Related Projects / Programmes</strong></td><td>List connected initiatives, platforms, or dependencies</td></tr>
<tr><td><strong>Key Dependencies</strong></td><td>Teams, suppliers, services, or approvals required</td></tr>
<tr><td><strong>Constraints</strong></td><td>Hard constraints (technical, policy, budget) the design must work within</td></tr>
<tr><td><strong>Assumptions</strong></td><td>Assumptions currently driving scope or solution choices</td></tr>
<tr><td><strong>Risks</strong></td><td>Initial delivery, operational, security, or data risks</td></tr>
</tbody>
</table>

<h3>3a. As-Is Architecture Snapshot</h3>
<p><em>Capture the current-state architecture in a structured, easy-to-fill format before defining the target solution.</em></p>

<table>
<tbody>
<tr><th>Current-State Area</th><th>Detail</th></tr>
<tr><td><strong>Business Process / User Journey</strong></td><td>What happens today from data capture to data use</td></tr>
<tr><td><strong>Current Users / Teams</strong></td><td>Which teams operate, support, or depend on the current service</td></tr>
<tr><td><strong>Current Source Systems</strong></td><td>Named upstream source systems and data providers</td></tr>
<tr><td><strong>Current Applications / Platforms</strong></td><td>Key applications, tools, or platforms in use today</td></tr>
<tr><td><strong>Current Data Stores</strong></td><td>Databases, file shares, data lakes, warehouses, spreadsheets, etc.</td></tr>
<tr><td><strong>Current Integrations / Interfaces</strong></td><td>APIs, SFTP, batch files, email, manual extract, CDC, messaging, etc.</td></tr>
<tr><td><strong>Current Hosting / Environment</strong></td><td>On-prem, cloud tenant, managed service, local desktop, shared drive, etc.</td></tr>
<tr><td><strong>Current Identity / Access Model</strong></td><td>How users and systems authenticate and are authorised today</td></tr>
<tr><td><strong>Current Monitoring / Support Model</strong></td><td>Who supports it and what monitoring or alerting exists</td></tr>
<tr><td><strong>Known As-Is Issues / Technical Debt</strong></td><td>Failures, manual workarounds, unsupported tech, resilience gaps, data quality issues</td></tr>
</tbody>
</table>

<h3>3b. As-Is Architecture Detail</h3>
<p><em>Use this table for a fillable current-state architecture inventory.</em></p>

<table>
<tbody>
<tr><th>Current Component / System</th><th>Type</th><th>Purpose</th><th>Key Interfaces</th><th>Pain Points / Constraints</th></tr>
<tr><td>e.g. LIMS</td><td>Source system</td><td>Captures laboratory events</td><td>CSV batch to shared drive</td><td>Manual handling, delayed updates</td></tr>
<tr><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td></td><td></td><td></td><td></td><td></td></tr>
</tbody>
</table>

<hr/>

<h2>4. Pain Points / Problem Statement</h2>
<p><em>Capture specific problems this solution must address. Each pain point should map to at least one requirement below.</em></p>

<table>
<tbody>
<tr><th>ID</th><th>Pain Point</th><th>Impacted Team / Process</th><th>Business Impact</th><th>Priority</th><th>Linked Requirement</th></tr>
<tr><td>PP1</td><td></td><td></td><td></td><td>High</td><td></td></tr>
<tr><td>PP2</td><td></td><td></td><td></td><td>High</td><td></td></tr>
<tr><td>PP3</td><td></td><td></td><td></td><td>Medium</td><td></td></tr>
<tr><td>PP4</td><td></td><td></td><td></td><td>Medium</td><td></td></tr>
<tr><td>PP5</td><td></td><td></td><td></td><td>Low</td><td></td></tr>
</tbody>
</table>

<hr/>

<h2>5. Functional Requirements</h2>
<p><em>What the system must do. Use MoSCoW prioritisation: Must Have / Should Have / Could Have / Won't Have.</em></p>

<table>
<tbody>
<tr><th>ID</th><th>Requirement</th><th>Acceptance Criteria</th><th>Priority</th><th>Linked Pain Point</th><th>Owner</th><th>Status</th></tr>
<tr><td>FR1</td><td></td><td></td><td>Must Have</td><td></td><td></td><td>Draft</td></tr>
<tr><td>FR2</td><td></td><td></td><td>Must Have</td><td></td><td></td><td>Draft</td></tr>
<tr><td>FR3</td><td></td><td></td><td>Must Have</td><td></td><td></td><td>Draft</td></tr>
<tr><td>FR4</td><td></td><td></td><td>Should Have</td><td></td><td></td><td>Draft</td></tr>
<tr><td>FR5</td><td></td><td></td><td>Should Have</td><td></td><td></td><td>Draft</td></tr>
<tr><td>FR6</td><td></td><td></td><td>Could Have</td><td></td><td></td><td>Draft</td></tr>
</tbody>
</table>

<hr/>

<h2>6. Non-Functional Requirements</h2>
<p><em>Quality attributes, service levels, and constraints. These drive pattern selection and NFR controls in the LLD.</em></p>

<table>
<tbody>
<tr><th>ID</th><th>NFR Category</th><th>Requirement</th><th>Target / SLA</th><th>Measurement Method</th><th>Priority</th><th>Status</th></tr>
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

<hr/>

<h2>7. Architecture Decision – HLD Options</h2>
<p><em>Use this section to compare the shortlisted solution options and make an explicit architecture decision.</em></p>

<table>
<tbody>
<tr><th>Option</th><th>Summary</th><th>Key Services / Patterns</th><th>Pros</th><th>Cons</th><th>Addresses Pain Points</th><th>Decision Status</th></tr>
<tr><td>Option A</td><td>Short name and one-line description</td><td>Named services, platforms, and pattern IDs</td><td>Main strengths</td><td>Main drawbacks</td><td>PP1, PP2, etc.</td><td>Candidate</td></tr>
<tr><td>Option B</td><td></td><td></td><td></td><td></td><td></td><td>Candidate</td></tr>
<tr><td>Option C</td><td></td><td></td><td></td><td></td><td></td><td>Candidate</td></tr>
</tbody>
</table>

<h3>7a. Option Evaluation Criteria</h3>

<table>
<tbody>
<tr><th>Criterion</th><th>How to Assess</th><th>Relative Weight</th></tr>
<tr><td><strong>Strategic Fit</strong></td><td>Alignment to business outcomes, operating model, and target state</td><td>High</td></tr>
<tr><td><strong>Technical Fit</strong></td><td>Ability to satisfy FRs, NFRs, and integration constraints</td><td>High</td></tr>
<tr><td><strong>Delivery Complexity</strong></td><td>Implementation effort, dependencies, and migration impact</td><td>Medium</td></tr>
<tr><td><strong>Operational Complexity</strong></td><td>Supportability, monitoring, resilience, and skills needed</td><td>Medium</td></tr>
<tr><td><strong>Cost</strong></td><td>Build cost and ongoing run cost over the expected lifecycle</td><td>Medium</td></tr>
<tr><td><strong>Risk</strong></td><td>Security, compliance, data, and supplier risk exposure</td><td>High</td></tr>
</tbody>
</table>

<hr/>

<h2>8. Pattern Selection</h2>
<p><em>Select the approved UKHSA patterns for the chosen HLD option. See the <code>UKHSA Cloud Strategy &amp; Approved patterns.md</code> file for pattern reference.</em></p>

<h3>8a. Ingestion Patterns</h3>

<table>
<tbody>
<tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected?</th><th>Notes / Justification</th></tr>
<tr><td>1A</td><td>Batch File Ingestion</td><td>Y/N</td><td></td></tr>
<tr><td>1B</td><td>Real-Time Event Streaming</td><td>Y/N</td><td></td></tr>
<tr><td>1C</td><td>API / Web Service Pull</td><td>Y/N</td><td></td></tr>
<tr><td>1D</td><td>Database CDC (Change Data Capture)</td><td>Y/N</td><td></td></tr>
</tbody>
</table>

<h3>8b. Processing Patterns</h3>

<table>
<tbody>
<tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected?</th><th>Notes / Justification</th></tr>
<tr><td>2A</td><td>Batch ETL / ELT Pipeline</td><td>Y/N</td><td></td></tr>
<tr><td>2B</td><td>Stream Processing</td><td>Y/N</td><td></td></tr>
<tr><td>2C</td><td>Micro-Batch Processing</td><td>Y/N</td><td></td></tr>
<tr><td>2D</td><td>Serverless Function Processing</td><td>Y/N</td><td></td></tr>
</tbody>
</table>

<h3>8c. Storage Patterns</h3>

<table>
<tbody>
<tr><th>Pattern ID</th><th>Pattern Name</th><th>Selected?</th><th>Notes / Justification</th></tr>
<tr><td>3A</td><td>Data Lake (Object Store)</td><td>Y/N</td><td></td></tr>
<tr><td>3B</td><td>Data Warehouse / Lakehouse</td><td>Y/N</td><td></td></tr>
<tr><td>3C</td><td>Relational Database</td><td>Y/N</td><td></td></tr>
<tr><td>3D</td><td>NoSQL / Document Store</td><td>Y/N</td><td></td></tr>
<tr><td>3E</td><td>In-Memory / Cache Store</td><td>Y/N</td><td></td></tr>
</tbody>
</table>

<h3>8d. Governance, Security &amp; Operational Patterns</h3>

<table>
<tbody>
<tr><th>Pattern ID</th><th>Pattern Name</th><th>Layer</th><th>Selected?</th><th>Notes</th></tr>
<tr><td>5A</td><td>Data Cataloguing</td><td>Governance</td><td>Y/N</td><td></td></tr>
<tr><td>5B</td><td>Data Lineage Tracking</td><td>Governance</td><td>Y/N</td><td></td></tr>
<tr><td>5C</td><td>Data Quality Framework</td><td>Governance</td><td>Y/N</td><td></td></tr>
<tr><td>6A</td><td>Encryption at Rest &amp; In Transit</td><td>Security</td><td>Y/N</td><td></td></tr>
<tr><td>6B</td><td>Role-Based Access Control (RBAC)</td><td>Security</td><td>Y/N</td><td></td></tr>
<tr><td>6C</td><td>Data Masking / Tokenisation</td><td>Security</td><td>Y/N</td><td></td></tr>
<tr><td>6D</td><td>Audit Logging</td><td>Security</td><td>Y/N</td><td></td></tr>
<tr><td>7A</td><td>Centralised Logging</td><td>Monitoring</td><td>Y/N</td><td></td></tr>
<tr><td>7B</td><td>Metrics &amp; Alerting</td><td>Monitoring</td><td>Y/N</td><td></td></tr>
<tr><td>7C</td><td>Distributed Tracing</td><td>Monitoring</td><td>Y/N</td><td></td></tr>
<tr><td>8A</td><td>Multi-Region / Multi-AZ</td><td>Resilience</td><td>Y/N</td><td></td></tr>
<tr><td>8B</td><td>Automated Backup &amp; Recovery</td><td>Resilience</td><td>Y/N</td><td></td></tr>
</tbody>
</table>

<hr/>

<h2>9. Context Entities</h2>
<p><em>Define external actors, systems, and partners that interact with this solution. Drives the Context View diagram.</em></p>

<table>
<tbody>
<tr><th>Entity Name</th><th>Type</th><th>Interaction Description</th><th>Direction</th></tr>
<tr><td></td><td>User / System / Partner / Service</td><td></td><td>In / Out / Both</td></tr>
<tr><td></td><td></td><td></td><td></td></tr>
<tr><td></td><td></td><td></td><td></td></tr>
</tbody>
</table>

<hr/>

<h2>10. Architecture Components</h2>
<p><em>Drives the Solution Architecture and Logical View diagrams. Valid layers: Edge, Network, Platform, Application, Data</em></p>

<table>
<tbody>
<tr><th>No</th><th>Component Name</th><th>Layer</th><th>Technology / Service</th><th>Cloud</th><th>Description</th><th>Links to FR/NFR</th></tr>
<tr><td>1</td><td></td><td></td><td></td><td>AWS/Azure/Both</td><td></td><td></td></tr>
<tr><td>2</td><td></td><td></td><td></td><td>AWS/Azure/Both</td><td></td><td></td></tr>
<tr><td>3</td><td></td><td></td><td></td><td>AWS/Azure/Both</td><td></td><td></td></tr>
<tr><td>4</td><td></td><td></td><td></td><td>AWS/Azure/Both</td><td></td><td></td></tr>
<tr><td>5</td><td></td><td></td><td></td><td>AWS/Azure/Both</td><td></td><td></td></tr>
<tr><td>6</td><td></td><td></td><td></td><td>AWS/Azure/Both</td><td></td><td></td></tr>
</tbody>
</table>

<hr/>

<h2>11. Architecture Connections</h2>
<p><em>Define how components communicate. Drives connection arrows on the Solution Architecture diagram.</em></p>

<table>
<tbody>
<tr><th>From Component</th><th>To Component</th><th>Connection Label / Protocol</th><th>Port / Auth</th><th>Notes</th></tr>
<tr><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td></td><td></td><td></td><td></td><td></td></tr>
</tbody>
</table>

<hr/>

<h2>12. Data Flow Entries</h2>
<p><em>Drives the Data Flow Diagram (DFD). Capture each distinct data movement between components or external entities.</em></p>

<table>
<tbody>
<tr><th>Flow ID</th><th>Source</th><th>Destination</th><th>Data Description</th><th>Format</th><th>Protocol / Method</th><th>Frequency</th><th>Sensitivity</th></tr>
<tr><td>F1</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>F2</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>F3</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>F4</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
</tbody>
</table>

<hr/>

<h2>13. Dataset Inventory</h2>
<p><em>Drives the Dataset Relationship diagram.</em></p>

<table>
<tbody>
<tr><th>ID</th><th>Dataset Name</th><th>Type</th><th>Source System</th><th>Primary Key</th><th>Sensitivity</th><th>Volume Estimate</th><th>Retention Period</th></tr>
<tr><td>D1</td><td></td><td>Structured/Semi/Unstructured</td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>D2</td><td></td><td>Structured/Semi/Unstructured</td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>D3</td><td></td><td>Structured/Semi/Unstructured</td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>D4</td><td></td><td>Structured/Semi/Unstructured</td><td></td><td></td><td></td><td></td><td></td></tr>
</tbody>
</table>

<h3>Dataset Relationships</h3>
<p><em>Define how datasets relate. Drives the ERD-style Dataset Relationship diagram.</em></p>

<table>
<tbody>
<tr><th>From Dataset</th><th>To Dataset</th><th>Relationship Type</th><th>Key Mapping</th><th>Notes</th></tr>
<tr><td></td><td></td><td>1:1 / 1:N / M:N</td><td>e.g. patient_id</td><td></td></tr>
<tr><td></td><td></td><td>1:1 / 1:N / M:N</td><td>e.g. patient_id</td><td></td></tr>
<tr><td></td><td></td><td>1:1 / 1:N / M:N</td><td>e.g. patient_id</td><td></td></tr>
</tbody>
</table>

<hr/>

<h2>14. Auto-Generated Diagrams</h2>
<p><em>Run <code>confluence_update_diagrams.py</code> after completing the tables above. All diagrams are editable in draw.io.</em></p>

<p><strong>14.1 Context View</strong></p>
<p><em>[Diagram will be embedded here after running confluence_update_diagrams.py]</em></p>

<p><strong>14.2 Logical View</strong></p>
<p><em>[Diagram will be embedded here after running confluence_update_diagrams.py]</em></p>

<p><strong>14.3 Solution Architecture</strong></p>
<p><em>[Diagram will be embedded here after running confluence_update_diagrams.py]</em></p>

<p><strong>14.4 Data Flow Diagram</strong></p>
<p><em>[Diagram will be embedded here after running confluence_update_diagrams.py]</em></p>

<p><strong>14.5 Dataset Relationship Diagram</strong></p>
<p><em>[Diagram will be embedded here after running confluence_update_diagrams.py]</em></p>

<hr/>

<h2>15. Low-Level Design (LLD) Summary</h2>
<p><em>Final design decisions agreed after HLD review. Updated before handover to engineering.</em></p>

<table>
<tbody>
<tr><th>LLD Area</th><th>Implementation Detail</th><th>Decision Owner</th><th>Status</th></tr>
<tr><td><strong>Component Specifications</strong></td><td></td><td></td><td>Draft</td></tr>
<tr><td><strong>API Contracts / Interfaces</strong></td><td></td><td></td><td>Draft</td></tr>
<tr><td><strong>Schema / Data Model</strong></td><td></td><td></td><td>Draft</td></tr>
<tr><td><strong>IAM / RBAC Design</strong></td><td></td><td></td><td>Draft</td></tr>
<tr><td><strong>NFR Controls Implementation</strong></td><td></td><td></td><td>Draft</td></tr>
<tr><td><strong>Monitoring &amp; Alerting Setup</strong></td><td></td><td></td><td>Draft</td></tr>
<tr><td><strong>DR / Backup Configuration</strong></td><td></td><td></td><td>Draft</td></tr>
</tbody>
</table>

<hr/>

<h2>16. Solution Option Cost Comparison</h2>
<p><em>Compare the shortlisted solution options from Section 7, including indicative build and run costs. Capture assumptions clearly so reviewers can understand what is included or excluded.</em></p>

<table>
<tbody>
<tr><th>Cost Area</th><th>Option A (£ / month)</th><th>Option B (£ / month)</th><th>Option C (£ / month)</th><th>Notes / Assumptions</th></tr>
<tr><td><strong>Storage</strong></td><td></td><td></td><td></td><td>Volumes, retention, replication assumptions</td></tr>
<tr><td><strong>Compute / Processing</strong></td><td></td><td></td><td></td><td>Batch frequency, peak load, scaling assumptions</td></tr>
<tr><td><strong>Data Transfer / Networking</strong></td><td></td><td></td><td></td><td>Ingress, egress, private connectivity, cross-region traffic</td></tr>
<tr><td><strong>Monitoring / Logging</strong></td><td></td><td></td><td></td><td>Expected log retention and alerting coverage</td></tr>
<tr><td><strong>Security / IAM</strong></td><td></td><td></td><td></td><td>KMS, secrets, PAM, identity integration, audit needs</td></tr>
<tr><td><strong>Managed Services / Licensing</strong></td><td></td><td></td><td></td><td>Third-party tooling, enterprise licences, support plans</td></tr>
<tr><td><strong>Total Indicative Run Cost</strong></td><td></td><td></td><td></td><td>Document whether VAT, contingency, and support are included</td></tr>
</tbody>
</table>

<h3>16a. Option-Level Comparison Summary</h3>

<table>
<tbody>
<tr><th>Option</th><th>Delivery Cost (£ one-off)</th><th>Key Benefits</th><th>Key Risks / Trade-offs</th><th>Preferred?</th></tr>
<tr><td>Option A</td><td></td><td>Why this option is attractive</td><td>Main trade-offs, dependencies, or uncertainties</td><td>Y/N</td></tr>
<tr><td>Option B</td><td></td><td></td><td></td><td>Y/N</td></tr>
<tr><td>Option C</td><td></td><td></td><td></td><td>Y/N</td></tr>
</tbody>
</table>

<hr/>

<h2>17. Implementation Handover</h2>
<p><em>After architecture sign-off, generate the implementation pack for the engineering delivery team.</em></p>

<table>
<tbody>
<tr><th>Deliverable</th><th>Output Location</th><th>Generated By</th><th>Status</th></tr>
<tr><td><strong>Terraform (AWS)</strong></td><td>output/terraform/aws/main.tf</td><td>confluence_generate_implementation_pack.py</td><td>Pending</td></tr>
<tr><td><strong>Terraform (Azure)</strong></td><td>output/terraform/azure/main.tf</td><td>confluence_generate_implementation_pack.py</td><td>Pending</td></tr>
<tr><td><strong>Implementation Summary JSON</strong></td><td>output/implementation/summary.json</td><td>confluence_generate_implementation_pack.py</td><td>Pending</td></tr>
<tr><td><strong>draw.io Diagrams (local)</strong></td><td>output/generated/*.drawio</td><td>confluence_update_diagrams.py</td><td>Pending</td></tr>
</tbody>
</table>

<hr/>

<h2>Reference Documents</h2>
<ul>
<li><strong>UKHSA Cloud Strategy &amp; Approved patterns.md</strong> – UKHSA-approved patterns and cloud strategy reference (local file)</li>
<li><strong>QUESTIONNAIRE_PLAN.md</strong> – Questionnaire planning notes</li>
</ul>

<hr/>

<p><em><strong>Status:</strong> Requirements Discovery Phase</em></p>
<p><em><strong>Last Revised:</strong> [Date]</em></p>
<p><em><strong>Version:</strong> 1.0</em></p>
"""
    return html


def main():
    print("=" * 80)
    print("RESTORE SOLUTION ARCHITECTURE: REQUIREMENTS & DESIGN PACK")
    print("=" * 80)
    print()
    
    base_url = "https://ukhsa.atlassian.net/wiki"
    space_key = "CDA"
    page_title = "Solution Architecture"
    
    try:
        session = requests.Session()
        session.headers.update(_accept_headers())
        
        print("Finding Confluence page...")
        page = find_page_by_title(session, base_url, space_key, page_title)
        page_id = page["id"]
        version = page["version"]["number"]
        
        print(f"  ✓ Found: {page_title} (ID: {page_id}, version: {version})")
        print()
        
        print("Building comprehensive Requirements & Design Pack template...")
        html_body = build_requirements_design_pack()
        
        print("Updating Confluence page (this may take a moment)...")
        result = update_page_body(session, base_url, page_id, version, page_title, html_body)
        
        print("✓ Page updated successfully!")
        print()
        print("=" * 80)
        print("REQUIREMENTS & DESIGN PACK RESTORED")
        print("=" * 80)
        print()
        print("Document Structure (17 Sections):")
        print("  ✓ 1. Solution Overview – Governance front sheet")
        print("  ✓ 2. Introduction – Solution description and alignment")
        print("  ✓ 3. Background – Current state, triggers, dependencies")
        print("  ✓ 4. Pain Points – Problems to address (traceability)")
        print("  ✓ 5. Functional Requirements – What system must do (MoSCoW)")
        print("  ✓ 6. Non-Functional Requirements – Quality attributes & SLAs")
        print("  ✓ 7. Architecture Decision – HLD options comparison")
        print("  ✓ 8. Pattern Selection – UKHSA approved patterns (5 categories)")
        print("  ✓ 9. Context Entities – External actors & systems")
        print("  ✓ 10. Architecture Components – Drives auto-generated diagrams")
        print("  ✓ 11. Architecture Connections – Service dependencies")
        print("  ✓ 12. Data Flow Entries – Data movements (DFD)")
        print("  ✓ 13. Dataset Inventory – Data entities & relationships")
        print("  ✓ 14. Auto-Generated Diagrams – Context, Logical, Architecture, DFD, ERD")
        print("  ✓ 15. LLD Summary – Final design decisions")
        print("  ✓ 16. Cost Comparison – Option analysis & breakdown")
        print("  ✓ 17. Implementation Handover – Terraform & delivery pack")
        print()
        print("Workflow:")
        print("  DISCOVERY: Fill Sections 1-6 with project team")
        print("  DESIGN: Complete Sections 7-13 with architectural decisions")
        print("  GENERATE: Run confluence_update_diagrams.py → auto-generates diagrams")
        print("  DELIVER: Run confluence_generate_implementation_pack.py → Terraform scaffolds")
        print()
        print(f"View page: {base_url}/spaces/{space_key}/pages/{page_id}/{page_title.replace(' ', '+')}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
