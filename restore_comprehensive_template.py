"""
Restore comprehensive Solution Architecture template to Confluence page.
This includes Introduction, Pain Points, Functional/Non-Functional Requirements,
and all architectural layers.
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
    if ca_bundle:
        if not os.path.exists(ca_bundle):
            raise ValueError(f"CONFLUENCE_CA_BUNDLE path does not exist: {ca_bundle}")
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


def build_comprehensive_template():
    """Build the comprehensive Solution Architecture template."""
    html_body = """<h1>Solution Architecture</h1>

<h2>1. Introduction</h2>
<p>This page documents the complete solution architecture covering all layers from user interface through data persistence. 
It includes business context, requirements, component design, and deployment considerations.</p>
<p><strong>Purpose:</strong> Provide a comprehensive view of the system design for stakeholders, developers, and operations teams.</p>
<p><strong>Last Updated:</strong> [Date]</p>
<p><strong>Status:</strong> [Draft/Review/Approved]</p>

<hr/>

<h2>2. Business Context</h2>

<h3>2.1 Overview</h3>
<p>Provide a brief overview of the business problem and solution being designed.</p>
<table>
<tbody>
<tr><th>Aspect</th><th>Description</th></tr>
<tr><td>Business Goal</td><td>[Enter business goal]</td></tr>
<tr><td>Target Users</td><td>[Enter target users]</td></tr>
<tr><td>Expected Outcome</td><td>[Enter expected outcome]</td></tr>
<tr><td>Success Criteria</td><td>[Enter success criteria]</td></tr>
</tbody>
</table>

<h3>2.2 Stakeholders</h3>
<table>
<tbody>
<tr><th>Stakeholder</th><th>Role</th><th>Interest</th></tr>
<tr><td>[Name]</td><td>[Role]</td><td>[Interest/Concern]</td></tr>
</tbody>
</table>

<hr/>

<h2>3. Problem Statement & Pain Points</h2>

<h3>Current Challenges</h3>
<ul>
<li><strong>Pain Point 1:</strong> [Describe current challenge]</li>
<li><strong>Pain Point 2:</strong> [Describe current challenge]</li>
<li><strong>Pain Point 3:</strong> [Describe current challenge]</li>
<li><strong>Pain Point 4:</strong> [Describe current challenge]</li>
</ul>

<h3>Business Impact</h3>
<p>Explain how these pain points impact the business, including cost, efficiency, and risk implications.</p>

<h3>Proposed Solution</h3>
<p>Explain how the proposed architecture addresses these pain points and delivers business value.</p>

<hr/>

<h2>4. Functional Requirements</h2>

<h3>Core Capabilities</h3>
<table>
<tbody>
<tr><th>ID</th><th>Requirement</th><th>Description</th><th>Priority</th><th>Layer(s)</th></tr>
<tr><td>FR-001</td><td>[Capability Name]</td><td>[Description]</td><td>High/Medium/Low</td><td>[Edge/Network/Platform/Application/Data]</td></tr>
<tr><td>FR-002</td><td>[Capability Name]</td><td>[Description]</td><td>High/Medium/Low</td><td>[Layer(s)]</td></tr>
<tr><td>FR-003</td><td>[Capability Name]</td><td>[Description]</td><td>High/Medium/Low</td><td>[Layer(s)]</td></tr>
</tbody>
</table>

<h3>User Workflows</h3>
<table>
<tbody>
<tr><th>Workflow</th><th>Steps</th><th>Expected Outcome</th></tr>
<tr><td>[Workflow Name]</td><td>[Step 1 → Step 2 → ...]</td><td>[Expected Result]</td></tr>
</tbody>
</table>

<hr/>

<h2>5. Non-Functional Requirements</h2>

<h3>Performance</h3>
<table>
<tbody>
<tr><th>Metric</th><th>Target</th><th>Acceptance Criteria</th></tr>
<tr><td>Response Time (API)</td><td>[ms]</td><td>P95 &lt; [ms]</td></tr>
<tr><td>Throughput</td><td>[requests/sec]</td><td>[Target]</td></tr>
<tr><td>Data Load Time</td><td>[seconds]</td><td>Initial load &lt; [seconds]</td></tr>
</tbody>
</table>

<h3>Availability & Reliability</h3>
<table>
<tbody>
<tr><th>Requirement</th><th>Target</th><th>Implementation</th></tr>
<tr><td>Availability</td><td>99.X%</td><td>Multi-region redundancy, failover</td></tr>
<tr><td>RTO (Recovery Time Objective)</td><td>[minutes/hours]</td><td>[Strategy]</td></tr>
<tr><td>RPO (Recovery Point Objective)</td><td>[minutes/hours]</td><td>Backup frequency</td></tr>
<tr><td>Data Backup</td><td>Daily</td><td>Automated backup to secondary region</td></tr>
</tbody>
</table>

<h3>Security & Compliance</h3>
<table>
<tbody>
<tr><th>Requirement</th><th>Standard/Framework</th><th>Implementation</th></tr>
<tr><td>Authentication</td><td>MFA</td><td>Entra ID / SSO</td></tr>
<tr><td>Encryption at Rest</td><td>AES-256</td><td>Database &amp; Storage encryption</td></tr>
<tr><td>Encryption in Transit</td><td>TLS 1.3</td><td>HTTPS/TLS for all communications</td></tr>
<tr><td>Audit Logging</td><td>Compliance Audit</td><td>Centralized logging &amp; monitoring</td></tr>
<tr><td>Data Classification</td><td>GDPR/NHS DSPT</td><td>Data governance framework</td></tr>
</tbody>
</table>

<h3>Scalability</h3>
<table>
<tbody>
<tr><th>Dimension</th><th>Current</th><th>Target</th><th>Strategy</th></tr>
<tr><td>Users</td><td>[Number]</td><td>[Number]</td><td>Horizontal scaling, load balancing</td></tr>
<tr><td>Data Volume</td><td>[GB/TB]</td><td>[GB/TB]</td><td>Partitioning, sharding, archiving</td></tr>
<tr><td>Transactions/sec</td><td>[TPS]</td><td>[TPS]</td><td>Database optimization, caching</td></tr>
</tbody>
</table>

<h3>Maintainability & Operations</h3>
<table>
<tbody>
<tr><th>Requirement</th><th>Target</th><th>Implementation</th></tr>
<tr><td>Deployment Frequency</td><td>[Per week/month]</td><td>CI/CD pipeline</td></tr>
<tr><td>Time to Fix Critical Issue</td><td>[minutes/hours]</td><td>On-call support, runbooks</td></tr>
<tr><td>Monitoring Coverage</td><td>&gt;95%</td><td>Application &amp; infrastructure monitoring</td></tr>
<tr><td>Documentation</td><td>Current</td><td>Automated documentation generation</td></tr>
</tbody>
</table>

<hr/>

<h2>6. Architecture Layers</h2>

<h3>6.1 Edge Layer</h3>
<p><strong>Purpose:</strong> User-facing applications and content delivery</p>
<ul>
<li>Web browsers and mobile applications</li>
<li>Content delivery networks (CDN)</li>
<li>API consumers and integrations</li>
</ul>

<h3>6.2 Network Layer</h3>
<p><strong>Purpose:</strong> Network routing, security, and load distribution</p>
<ul>
<li>API Gateways</li>
<li>Web Application Firewalls (WAF)</li>
<li>Load Balancers</li>
<li>Network segmentation and access control</li>
</ul>

<h3>6.3 Platform Layer</h3>
<p><strong>Purpose:</strong> Cross-cutting concerns and shared services</p>
<ul>
<li>Identity and Access Management (IAM)</li>
<li>Encryption and Key Management</li>
<li>Logging and Monitoring</li>
<li>Message Queuing and Event Distribution</li>
</ul>

<h3>6.4 Application Layer</h3>
<p><strong>Purpose:</strong> Business logic and service orchestration</p>
<ul>
<li>Business Service APIs</li>
<li>Data Processing Services</li>
<li>Integration Middleware</li>
<li>Caching Services</li>
</ul>

<h3>6.5 Data Layer</h3>
<p><strong>Purpose:</strong> Data persistence and analytics</p>
<ul>
<li>Relational Databases</li>
<li>NoSQL Datastores</li>
<li>Data Lakes and Warehouses</li>
<li>Search Indexes</li>
<li>Message Queues and Event Logs</li>
</ul>

<hr/>

<h2>7. Architecture Components</h2>
<p><em>Define all system components. Fill in the table below with components for each layer.</em></p>
<table>
<tbody>
<tr>
<th>No</th>
<th>Name</th>
<th>Layer</th>
<th>Technology</th>
<th>Description</th>
</tr>
</tbody>
</table>

<hr/>

<h2>8. Architecture Connections</h2>
<p><em>Define how components interact. Specify dependencies and communication patterns.</em></p>
<table>
<tbody>
<tr>
<th>From</th>
<th>To</th>
<th>Label</th>
</tr>
</tbody>
</table>

<hr/>

<h2>9. Data Flow Entries</h2>
<p><em>Document user interactions and data movements through the system.</em></p>
<table>
<tbody>
<tr>
<th>ID</th>
<th>Source</th>
<th>Destination</th>
<th>Data</th>
<th>Protocol</th>
</tr>
</tbody>
</table>

<hr/>

<h2>10. Dataset Inventory</h2>
<p><em>Document all datasets, their types, sensitivity levels, and retention policies.</em></p>
<table>
<tbody>
<tr>
<th>ID</th>
<th>Name</th>
<th>Type</th>
<th>Primary Key</th>
<th>Sensitivity</th>
<th>Retention</th>
</tr>
</tbody>
</table>

<hr/>

<h2>11. Dataset Relationships</h2>
<p><em>Define relationships and dependencies between datasets.</em></p>
<table>
<tbody>
<tr>
<th>Source</th>
<th>Target</th>
<th>Relation</th>
<th>Mapping</th>
</tr>
</tbody>
</table>

<hr/>

<h2>12. Context Entities</h2>
<p><em>Define external systems, users, and stakeholders that interact with the architecture.</em></p>
<table>
<tbody>
<tr>
<th>Name</th>
<th>Type</th>
<th>Interaction</th>
</tr>
</tbody>
</table>

<hr/>

<h2>13. Security & Compliance Design</h2>

<h3>13.1 Authentication & Authorization</h3>
<p>Describe authentication mechanisms (MFA, SSO, OAuth), authorization models (RBAC, ABAC), and access control strategies.</p>

<h3>13.2 Data Protection</h3>
<p>Document encryption strategies, key management, and data masking approaches.</p>

<h3>13.3 Network Security</h3>
<p>Describe firewalls, DDoS protection, network segmentation, and VPN requirements.</p>

<h3>13.4 Audit & Monitoring</h3>
<p>Document audit logging, monitoring strategies, alerting mechanisms, and compliance reporting.</p>

<h3>13.5 Compliance Mapping</h3>
<table>
<tbody>
<tr><th>Regulation/Standard</th><th>Requirement</th><th>Implementation</th></tr>
<tr><td>GDPR</td><td>[Requirement]</td><td>[How addressed]</td></tr>
<tr><td>NHS DSPT</td><td>[Requirement]</td><td>[How addressed]</td></tr>
<tr><td>NIST CSF</td><td>[Requirement]</td><td>[How addressed]</td></tr>
</tbody>
</table>

<hr/>

<h2>14. Deployment Architecture</h2>

<h3>14.1 Infrastructure</h3>
<p>Describe cloud platform (AWS/Azure), regions, availability zones, and deployment strategy.</p>

<h3>14.2 Deployment Pattern</h3>
<p>Blue-Green, Canary, Rolling, or other deployment strategies.</p>

<h3>14.3 Infrastructure as Code</h3>
<p>Document Terraform, CloudFormation, or other IaC tools used for infrastructure provisioning.</p>

<hr/>

<h2>15. Generated Diagrams</h2>
<p><em>Auto-generated visual representations of the architecture (generated by confluence_update_diagrams.py)</em></p>
<ul>
<li>Solution Architecture Diagram</li>
<li>Data Flow Diagram</li>
<li>Dataset Relationship Diagram</li>
<li>Context View Diagram</li>
<li>Logical View Diagram</li>
</ul>

<hr/>

<h2>16. Assumptions & Constraints</h2>

<h3>Assumptions</h3>
<ul>
<li>[Assumption 1]</li>
<li>[Assumption 2]</li>
</ul>

<h3>Constraints</h3>
<ul>
<li>[Constraint 1]</li>
<li>[Constraint 2]</li>
</ul>

<hr/>

<h2>17. Risks & Mitigation</h2>

<table>
<tbody>
<tr><th>Risk</th><th>Impact</th><th>Probability</th><th>Mitigation</th></tr>
<tr><td>[Risk Description]</td><td>High/Medium/Low</td><td>High/Medium/Low</td><td>[Mitigation Strategy]</td></tr>
</tbody>
</table>

<hr/>

<h2>18. Approval & Sign-Off</h2>

<table>
<tbody>
<tr><th>Role</th><th>Name</th><th>Date</th><th>Status</th></tr>
<tr><td>Architect</td><td>[Name]</td><td>[Date]</td><td>[ ]</td></tr>
<tr><td>Security Lead</td><td>[Name]</td><td>[Date]</td><td>[ ]</td></tr>
<tr><td>Product Owner</td><td>[Name]</td><td>[Date]</td><td>[ ]</td></tr>
</tbody>
</table>

<hr/>

<h2>19. Related Documents</h2>
<ul>
<li><a href="#">UKHSA Cloud Strategy &amp; Approved patterns.md</a></li>
<li><a href="#">Deployment Guide</a></li>
<li><a href="#">Security Design Document</a></li>
<li><a href="#">Operational Runbooks</a></li>
</ul>

<p><em>Last Revised: [Date]</em></p>
<p><em>Version: 1.0</em></p>
"""
    return html_body


def main():
    print("=" * 70)
    print("RESTORE COMPREHENSIVE SOLUTION ARCHITECTURE TEMPLATE")
    print("=" * 70)
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
        
        print(f"  Found: {page_title} (ID: {page_id}, version: {version})")
        print()
        
        print("Building comprehensive template...")
        print("  Sections included:")
        print("    • Introduction")
        print("    • Business Context & Stakeholders")
        print("    • Problem Statement & Pain Points")
        print("    • Functional Requirements")
        print("    • Non-Functional Requirements (Performance, Availability, Security, Scalability)")
        print("    • Architecture Layers (Edge, Network, Platform, Application, Data)")
        print("    • Components Table")
        print("    • Connections Table")
        print("    • Data Flow Entries Table")
        print("    • Dataset Inventory")
        print("    • Dataset Relationships")
        print("    • Context Entities")
        print("    • Security & Compliance Design")
        print("    • Deployment Architecture")
        print("    • Assumptions & Constraints")
        print("    • Risks & Mitigation")
        print("    • Approval & Sign-Off")
        print()
        
        html_body = build_comprehensive_template()
        
        print("Updating Confluence page with comprehensive template...")
        result = update_page_body(session, base_url, page_id, version, page_title, html_body)
        
        print("✓ Page restored to comprehensive template!")
        print()
        print("=" * 70)
        print("RESTORE COMPLETE")
        print("=" * 70)
        print()
        print("The Solution Architecture page now includes:")
        print("  ✓ Full introduction and business context")
        print("  ✓ Pain points and problem statement")
        print("  ✓ Functional requirements with traceability")
        print("  ✓ Non-functional requirements (Performance, Availability, Security, Scalability)")
        print("  ✓ All 5 architectural layers defined")
        print("  ✓ Tables for components, connections, data flows, datasets")
        print("  ✓ Security & Compliance design section")
        print("  ✓ Deployment architecture documentation")
        print()
        print(f"View page: {base_url}/spaces/{space_key}/pages/{page_id}/{page_title.replace(' ', '+')}")
        print()
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
