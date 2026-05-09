"""
Fix the HLD template with working internal anchor links and proper external references.
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


def build_hld_with_working_links():
    """Build the HLD template with working internal anchor links."""
    html_body = """<h1>High Level Design (HLD) - Solution Architecture</h1>

<p><strong>Project Name:</strong> [Project Name]</p>
<p><strong>Reference Jira No.:</strong> [JIRA-XXXX]</p>
<p><strong>Version:</strong> 0.1</p>
<p><strong>Publish Date:</strong> [Date]</p>

<hr/>

<h2>Index</h2>
<ul>
<li><ac:link><ri:page ri:content-title="Solution Architecture" ri:space-key="CDA"/><ac:plain-text-link-body>1. Document Control</ac:plain-text-link-body></ac:link></li>
<li><ac:link><ri:page ri:content-title="Solution Architecture" ri:space-key="CDA"/><ac:anchor>engagement</ac:anchor><ac:plain-text-link-body>2. Engagement</ac:plain-text-link-body></ac:link></li>
<li><ac:link><ri:page ri:content-title="Solution Architecture" ri:space-key="CDA"/><ac:anchor>introduction</ac:anchor><ac:plain-text-link-body>3. Introduction</ac:plain-text-link-body></ac:link></li>
<li><ac:link><ri:page ri:content-title="Solution Architecture" ri:space-key="CDA"/><ac:anchor>business-context</ac:anchor><ac:plain-text-link-body>4. Business and Technology Context</ac:plain-text-link-body></ac:link></li>
<li><ac:link><ri:page ri:content-title="Solution Architecture" ri:space-key="CDA"/><ac:anchor>pain-points</ac:anchor><ac:plain-text-link-body>5. Pain Points</ac:plain-text-link-body></ac:link></li>
<li><ac:link><ri:page ri:content-title="Solution Architecture" ri:space-key="CDA"/><ac:anchor>functional-requirements</ac:anchor><ac:plain-text-link-body>6. Functional Requirements</ac:plain-text-link-body></ac:link></li>
<li><ac:link><ri:page ri:content-title="Solution Architecture" ri:space-key="CDA"/><ac:anchor>non-functional-requirements</ac:anchor><ac:plain-text-link-body>7. Non-Functional Requirements</ac:plain-text-link-body></ac:link></li>
<li><ac:link><ri:page ri:content-title="Solution Architecture" ri:space-key="CDA"/><ac:anchor>diagrams</ac:anchor><ac:plain-text-link-body>8. Architecture Diagrams &amp; References</ac:plain-text-link-body></ac:link></li>
<li><ac:link><ri:page ri:content-title="Solution Architecture" ri:space-key="CDA"/><ac:anchor>appendix</ac:anchor><ac:plain-text-link-body>9. Appendix</ac:plain-text-link-body></ac:link></li>
</ul>

<hr/>

<h2 ac:name="document-control">1. Document Control</h2>

<h3>Distribution List</h3>
<table>
<tbody>
<tr><th>Recipient</th><th>Role/Department</th><th>Purpose</th></tr>
<tr><td>[Name]</td><td>[Role]</td><td>Review &amp; Approval</td></tr>
<tr><td>[Name]</td><td>[Role]</td><td>Implementation</td></tr>
<tr><td>[Name]</td><td>[Role]</td><td>Operations</td></tr>
</tbody>
</table>

<h3>Reviewers</h3>
<table>
<tbody>
<tr><th>Reviewer Name</th><th>Reviewer Role</th><th>Sections to be Reviewed</th><th>Signoff Date</th></tr>
<tr><td>@Jamie A. Fraser</td><td>[Role]</td><td>[Sections]</td><td>[ ]</td></tr>
<tr><td>[Name]</td><td>[Role]</td><td>[Sections]</td><td>[ ]</td></tr>
<tr><td>[Name]</td><td>[Role]</td><td>[Sections]</td><td>[ ]</td></tr>
</tbody>
</table>

<h3>Revision History</h3>
<table>
<tbody>
<tr><th>Version</th><th>Date</th><th>Change Description</th><th>Author</th></tr>
<tr><td>0.1</td><td>[Date]</td><td>Initial version for review</td><td>@Jamie A. Fraser</td></tr>
<tr><td></td><td></td><td></td><td></td></tr>
<tr><td></td><td></td><td></td><td></td></tr>
</tbody>
</table>

<hr/>

<h2 ac:name="engagement">2. Engagement</h2>

<p><strong>Information Message:</strong> As the design moves along the lifecycle, the engagement of different areas will be required. The table below tracks engagement for each phase of the project as it transitions from <strong>Discovery → Beta → Production</strong>.</p>

<h3>Engagement Log</h3>
<table>
<tbody>
<tr><th>Areas</th><th>Dates</th><th>Outcome/Commentary/Actions</th></tr>
<tr><td><strong>Enterprise Architecture</strong></td><td></td><td></td></tr>
<tr><td><strong>Cyber Security</strong></td><td></td><td></td></tr>
<tr><td><strong>Data Architecture</strong></td><td></td><td></td></tr>
<tr><td><strong>Data Governance</strong></td><td></td><td></td></tr>
<tr><td><strong>Records and Information Management</strong></td><td></td><td></td></tr>
<tr><td><strong>Data Release and Acquisition</strong></td><td></td><td></td></tr>
<tr><td><strong>Privacy</strong></td><td></td><td></td></tr>
<tr><td><strong>IT Service Management</strong></td><td></td><td></td></tr>
<tr><td><strong>HPC Platform and Infrastructure</strong></td><td></td><td></td></tr>
<tr><td><strong>DevOps and Development Leads</strong></td><td></td><td></td></tr>
<tr><td><strong>Technology QA / Testing Function</strong></td><td></td><td></td></tr>
<tr><td><strong>User Interface / User Experience</strong></td><td></td><td></td></tr>
<tr><td><strong>FinOps</strong></td><td></td><td></td></tr>
<tr><td><strong>M365 Function</strong></td><td></td><td></td></tr>
<tr><td><strong>Identity Function</strong></td><td></td><td></td></tr>
</tbody>
</table>

<hr/>

<h2 ac:name="introduction">3. Introduction</h2>

<h3>Executive Summary</h3>
<p>[Provide a high-level summary of the proposed solution, its business drivers, key benefits, and high-level technical approach]</p>

<h3>Purpose</h3>
<p>[Define the purpose of this HLD document and its intended audience]</p>

<h3>Scope</h3>
<p>[Define what is in scope and out of scope for this solution]</p>

<hr/>

<h2 ac:name="business-context">4. Business and Technology Context</h2>

<h3>Business Context</h3>
<p><strong>Business Goal:</strong> [Describe the business goal and desired outcome]</p>
<p><strong>Target Users:</strong> [Describe the target user groups]</p>
<p><strong>Expected Benefits:</strong> [List the expected benefits to the organization]</p>

<h3>Technology Context</h3>
<p><strong>Current Technology Landscape:</strong> [Describe current systems and technologies]</p>
<p><strong>Strategic Direction:</strong> [Describe how this solution aligns with the technology strategy]</p>
<p><strong>Compliance Requirements:</strong> [List key compliance requirements (GDPR, NHS DSPT, NIST, etc.)]</p>

<h3>Stakeholders</h3>
<table>
<tbody>
<tr><th>Stakeholder</th><th>Role</th><th>Interests/Concerns</th></tr>
<tr><td>[Name]</td><td>[Role]</td><td>[Interest]</td></tr>
<tr><td>[Name]</td><td>[Role]</td><td>[Interest]</td></tr>
</tbody>
</table>

<hr/>

<h2 ac:name="pain-points">5. Pain Points</h2>

<h3>Current Challenges</h3>
<table>
<tbody>
<tr><th>Pain Point</th><th>Business Impact</th><th>Severity</th><th>How This Solution Addresses It</th></tr>
<tr><td>[Issue 1]</td><td>[Impact]</td><td>High/Medium/Low</td><td>[Solution]</td></tr>
<tr><td>[Issue 2]</td><td>[Impact]</td><td>High/Medium/Low</td><td>[Solution]</td></tr>
<tr><td>[Issue 3]</td><td>[Impact]</td><td>High/Medium/Low</td><td>[Solution]</td></tr>
</tbody>
</table>

<hr/>

<h2 ac:name="functional-requirements">6. Functional Requirements</h2>

<h3>Core Capabilities</h3>
<table>
<tbody>
<tr><th>ID</th><th>Requirement</th><th>Description</th><th>Priority</th><th>Success Criteria</th></tr>
<tr><td>FR-001</td><td>[Capability Name]</td><td>[Description]</td><td>High/Medium/Low</td><td>[Acceptance Criteria]</td></tr>
<tr><td>FR-002</td><td>[Capability Name]</td><td>[Description]</td><td>High/Medium/Low</td><td>[Acceptance Criteria]</td></tr>
<tr><td>FR-003</td><td>[Capability Name]</td><td>[Description]</td><td>High/Medium/Low</td><td>[Acceptance Criteria]</td></tr>
</tbody>
</table>

<h3>User Workflows</h3>
<table>
<tbody>
<tr><th>Workflow ID</th><th>Workflow Name</th><th>User Type</th><th>Steps</th><th>Expected Outcome</th></tr>
<tr><td>UW-001</td><td>[Workflow]</td><td>[User Type]</td><td>[Step 1 → Step 2 → ...]</td><td>[Expected Result]</td></tr>
<tr><td>UW-002</td><td>[Workflow]</td><td>[User Type]</td><td>[Step 1 → Step 2 → ...]</td><td>[Expected Result]</td></tr>
</tbody>
</table>

<hr/>

<h2 ac:name="non-functional-requirements">7. Non-Functional Requirements</h2>

<h3>Performance</h3>
<table>
<tbody>
<tr><th>Metric</th><th>Target</th><th>Acceptance Criteria</th></tr>
<tr><td>API Response Time (P95)</td><td>[ms]</td><td>&lt; [ms]</td></tr>
<tr><td>Portal Load Time</td><td>[seconds]</td><td>&lt; [seconds]</td></tr>
<tr><td>Concurrent Users</td><td>[Number]</td><td>Support [Number] users</td></tr>
<tr><td>Throughput</td><td>[TPS]</td><td>[Number] requests/sec</td></tr>
</tbody>
</table>

<h3>Availability &amp; Reliability</h3>
<table>
<tbody>
<tr><th>Requirement</th><th>Target</th><th>Implementation Strategy</th></tr>
<tr><td>System Availability (SLA)</td><td>99.X%</td><td>Multi-region failover, load balancing</td></tr>
<tr><td>RTO (Recovery Time Objective)</td><td>[minutes/hours]</td><td>Automated failover mechanism</td></tr>
<tr><td>RPO (Recovery Point Objective)</td><td>[minutes/hours]</td><td>Continuous replication / [interval] backups</td></tr>
<tr><td>Data Backup</td><td>Daily</td><td>Automated backup to secondary region</td></tr>
</tbody>
</table>

<h3>Security &amp; Compliance</h3>
<table>
<tbody>
<tr><th>Requirement</th><th>Standard/Framework</th><th>Implementation</th></tr>
<tr><td>Authentication</td><td>MFA</td><td>Entra ID / OAuth 2.0 with MFA</td></tr>
<tr><td>Authorization</td><td>RBAC</td><td>Role-Based Access Control</td></tr>
<tr><td>Encryption at Rest</td><td>AES-256</td><td>Database &amp; Storage encryption</td></tr>
<tr><td>Encryption in Transit</td><td>TLS 1.3</td><td>HTTPS/TLS for all communications</td></tr>
<tr><td>Audit Logging</td><td>Compliance</td><td>Centralized logging &amp; 7-year retention</td></tr>
<tr><td>Data Classification</td><td>GDPR/NHS DSPT</td><td>Data governance &amp; handling framework</td></tr>
<tr><td>Vulnerability Management</td><td>NIST CSF</td><td>Regular scanning &amp; patching</td></tr>
</tbody>
</table>

<h3>Scalability</h3>
<table>
<tbody>
<tr><th>Dimension</th><th>Current</th><th>Target (2 Years)</th><th>Scaling Strategy</th></tr>
<tr><td>Users</td><td>[Number]</td><td>[Number]</td><td>Horizontal scaling, auto-scaling groups</td></tr>
<tr><td>Data Volume</td><td>[GB/TB]</td><td>[GB/TB]</td><td>Partitioning, sharding, archival</td></tr>
<tr><td>Transactions/sec</td><td>[TPS]</td><td>[TPS]</td><td>Database optimization, read replicas</td></tr>
</tbody>
</table>

<h3>Maintainability &amp; Operations</h3>
<table>
<tbody>
<tr><th>Requirement</th><th>Target</th><th>Implementation</th></tr>
<tr><td>Deployment Frequency</td><td>[Per week/month]</td><td>CI/CD pipeline with automated testing</td></tr>
<tr><td>Mean Time to Recovery (MTTR)</td><td>[minutes]</td><td>Automated alerts &amp; runbooks</td></tr>
<tr><td>Monitoring Coverage</td><td>&gt;95%</td><td>Application &amp; infrastructure monitoring</td></tr>
<tr><td>Documentation</td><td>Current</td><td>Wiki, Runbooks, API Documentation</td></tr>
</tbody>
</table>

<hr/>

<h2 ac:name="diagrams">8. Architecture Diagrams &amp; References</h2>

<p><strong>Note:</strong> Detailed architecture diagrams and specifications are maintained in separate documentation:</p>

<h3>High-Level Architecture Views</h3>
<ul>
<li><strong>Context Diagram:</strong> System boundary and external interactions - Auto-generated</li>
<li><strong>Data Flow Diagram:</strong> User workflows and data movements - Auto-generated</li>
<li><strong>Relationship Diagram:</strong> Component and data dependencies - Auto-generated</li>
</ul>

<h3>Detailed Documentation &amp; References</h3>
<ul>
<li><strong>Cloud Strategy &amp; Approved Patterns:</strong> Strategic reference document with approved design patterns across 8 layers - Attached to this page</li>
<li><strong>LLD (Low Level Design):</strong> Detailed component specifications, connections, data flows, and technology stack [LINK TO BE CREATED]</li>
<li><strong>Deployment Architecture:</strong> Infrastructure specifications, Terraform code, and cloud configuration [LINK TO BE CREATED]</li>
<li><strong>Auto-Generated Diagrams:</strong> All diagrams are generated from the detailed component tables and can be edited using draw.io [LINK TO DIAGRAMS]</li>
</ul>

<h3>Files to Reference</h3>
<ul>
<li><strong>UKHSA Cloud Strategy &amp; Approved patterns.md</strong> - Strategic design patterns and cloud approach</li>
<li><strong>output/generated/solution-architecture.drawio</strong> - Main architecture diagram (editable)</li>
<li><strong>output/generated/data-flow-diagram.drawio</strong> - Data flow visualization (editable)</li>
<li><strong>output/generated/data-relationship-diagram.drawio</strong> - Entity relationships (editable)</li>
</ul>

<hr/>

<h2 ac:name="appendix">9. Appendix</h2>

<h3>A. Assumptions</h3>
<ul>
<li>[Assumption 1]</li>
<li>[Assumption 2]</li>
<li>[Assumption 3]</li>
</ul>

<h3>B. Constraints</h3>
<ul>
<li>[Constraint 1]</li>
<li>[Constraint 2]</li>
<li>[Constraint 3]</li>
</ul>

<h3>C. Risks &amp; Mitigation</h3>
<table>
<tbody>
<tr><th>Risk ID</th><th>Risk Description</th><th>Impact</th><th>Probability</th><th>Mitigation Strategy</th></tr>
<tr><td>R-001</td><td>[Risk Description]</td><td>High/Medium/Low</td><td>High/Medium/Low</td><td>[Mitigation]</td></tr>
<tr><td>R-002</td><td>[Risk Description]</td><td>High/Medium/Low</td><td>High/Medium/Low</td><td>[Mitigation]</td></tr>
</tbody>
</table>

<h3>D. Dependencies &amp; Critical Success Factors</h3>
<table>
<tbody>
<tr><th>Dependency/CSF</th><th>Type</th><th>Description</th><th>Owner</th></tr>
<tr><td>[Item]</td><td>Dependency/CSF</td><td>[Description]</td><td>[Owner]</td></tr>
</tbody>
</table>

<h3>E. Approval &amp; Sign-Off</h3>
<table>
<tbody>
<tr><th>Role</th><th>Name</th><th>Department</th><th>Date</th><th>Status</th></tr>
<tr><td>Solution Architect</td><td>[Name]</td><td>Enterprise Architecture</td><td></td><td>[ ] Approved</td></tr>
<tr><td>Security Lead</td><td>[Name]</td><td>Cyber Security</td><td></td><td>[ ] Approved</td></tr>
<tr><td>Data Architect</td><td>[Name]</td><td>Data Architecture</td><td></td><td>[ ] Approved</td></tr>
<tr><td>Product Owner</td><td>[Name]</td><td>Business</td><td></td><td>[ ] Approved</td></tr>
</tbody>
</table>

<hr/>

<p><strong>Version:</strong> 0.1</p>
<p><strong>Last Revised:</strong> [Date]</p>
<p><strong>Status:</strong> Draft / In Review / Approved</p>
<p><em>This is a High-Level Design (HLD) document. For detailed Low-Level Design (LLD) specifications, component details, and auto-generated diagrams, refer to the linked pages above.</em></p>
"""
    return html_body


def main():
    print("=" * 70)
    print("FIX HLD TEMPLATE LINKS")
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
        
        print("Building HLD template with working anchor links...")
        html_body = build_hld_with_working_links()
        
        print("Updating Confluence page with fixed links...")
        result = update_page_body(session, base_url, page_id, version, page_title, html_body)
        
        print("✓ HLD template links fixed successfully!")
        print()
        print("=" * 70)
        print("LINKS FIXED")
        print("=" * 70)
        print()
        print("Fixed Issues:")
        print("  ✓ Index links now use Confluence anchor macros for proper navigation")
        print("  ✓ Internal section anchors properly configured")
        print("  ✓ External references updated with clear instructions")
        print("  ✓ File references added (Cloud Strategy, diagrams, etc.)")
        print()
        print("How to use the page:")
        print("  1. Click any link in the Index to jump to that section")
        print("  2. Fill in placeholder text [Like This]")
        print("  3. Create child pages for LLD and Deployment Architecture")
        print("  4. Attach files (diagrams, strategy documents)")
        print()
        print(f"View HLD page: {base_url}/spaces/{space_key}/pages/{page_id}/{page_title.replace(' ', '+')}")
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
