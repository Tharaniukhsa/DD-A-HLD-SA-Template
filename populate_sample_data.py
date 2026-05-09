"""
Populate the Solution Architecture Confluence page with sample architecture data.
This script adds sample tables (Components, Connections, Data Flows, etc.) to the
Confluence page so that confluence_update_diagrams.py can generate diagrams.
"""

import html
import json
import os
import sys
from io import BytesIO

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


def build_html_table(headers, rows):
    """Build an HTML table from headers and row data."""
    html_table = "<table><tbody>\n"
    
    # Header row
    html_table += "<tr>"
    for header in headers:
        html_table += f"<th>{header}</th>"
    html_table += "</tr>\n"
    
    # Data rows
    for row in rows:
        html_table += "<tr>"
        for cell in row:
            html_table += f"<td>{cell}</td>"
        html_table += "</tr>\n"
    
    html_table += "</tbody></table>"
    return html_table


def build_sample_page():
    """Build the complete page HTML with sample data tables."""
    
    # Architecture Components
    components_headers = ["No", "Name", "Layer", "Technology", "Description"]
    components_rows = [
        ["1", "Healthcare Portal", "Edge", "React.js, TypeScript", "Web-based portal for healthcare professionals"],
        ["2", "Mobile Health App", "Edge", "React Native", "Mobile application for on-the-go access (iOS/Android)"],
        ["3", "AWS CloudFront CDN", "Edge", "CloudFront", "Global content delivery network for portal assets"],
        ["4", "API Gateway", "Network", "API Gateway", "Central API endpoint for frontend-backend communication"],
        ["5", "Web Application Firewall", "Network", "AWS WAF", "Protects against common web exploits"],
        ["6", "Network Load Balancer", "Network", "NLB", "Distributes traffic across application instances"],
        ["7", "Identity Service", "Platform", "Entra ID (Azure AD)", "Single sign-on and multi-factor authentication"],
        ["8", "Encryption Service", "Platform", "AWS KMS", "Manages encryption keys for data"],
        ["9", "Audit Logging Service", "Platform", "CloudWatch Logs", "Centralized logging for compliance"],
        ["10", "Records API Service", "Application", "Python FastAPI", "Microservice for record management"],
        ["11", "Search Service", "Application", "Elasticsearch", "Full-text search engine for records"],
        ["12", "Notification Service", "Application", "SNS + Lambda", "Alerts and notifications service"],
        ["13", "Patient Records Database", "Data", "RDS Aurora (PostgreSQL)", "Primary relational database"],
        ["14", "Data Lake", "Data", "S3 + Glue", "Long-term storage for historical data"],
        ["15", "Search Index", "Data", "Elasticsearch Index", "Indexed data for fast search"],
    ]
    
    # Architecture Connections
    connections_headers = ["From", "To", "Label"]
    connections_rows = [
        ["Healthcare Portal", "CloudFront CDN", "Static Assets (CSS/JS/Images)"],
        ["Healthcare Portal", "API Gateway", "REST API Calls (HTTPS)"],
        ["Mobile Health App", "API Gateway", "REST API Calls (HTTPS)"],
        ["API Gateway", "Web Application Firewall", "Request Routing"],
        ["Web Application Firewall", "Network Load Balancer", "Filtered Traffic"],
        ["Network Load Balancer", "Records API Service", "HTTP Internal"],
        ["Network Load Balancer", "Search Service", "HTTP Internal"],
        ["Records API Service", "Identity Service", "User Authentication"],
        ["Records API Service", "Encryption Service", "Encrypt/Decrypt Data"],
        ["Records API Service", "Patient Records Database", "Read/Write Records"],
        ["Records API Service", "Audit Logging Service", "Log Operations"],
        ["Records API Service", "Notification Service", "Trigger Alerts"],
        ["Search Service", "Search Index", "Query Index Data"],
        ["Notification Service", "Healthcare Portal", "Push Notifications"],
        ["Patient Records Database", "Data Lake", "Nightly ETL"],
        ["Data Lake", "Search Index", "Analytics Feed"],
    ]
    
    # Data Flow Entries
    dataflows_headers = ["ID", "Source", "Destination", "Data", "Protocol"]
    dataflows_rows = [
        ["DF-001", "Healthcare Professional", "Healthcare Portal", "Login Request", "HTTPS"],
        ["DF-002", "Healthcare Portal", "Identity Service", "User Credentials", "HTTPS"],
        ["DF-003", "Identity Service", "Healthcare Portal", "JWT Token", "HTTPS"],
        ["DF-004", "Healthcare Portal", "Records API Service", "Patient Record Query", "REST/JSON"],
        ["DF-005", "Records API Service", "Patient Records Database", "SQL Query", "TLS"],
        ["DF-006", "Patient Records Database", "Records API Service", "Patient Record Data", "TLS"],
        ["DF-007", "Records API Service", "Encryption Service", "Plaintext Data", "HTTPS"],
        ["DF-008", "Encryption Service", "Records API Service", "Encrypted Data", "HTTPS"],
        ["DF-009", "Records API Service", "Audit Logging Service", "Audit Event", "HTTPS"],
        ["DF-010", "Healthcare Portal", "Search Service", "Search Query", "REST/JSON"],
        ["DF-011", "Search Service", "Search Index", "Elasticsearch Query", "HTTP"],
        ["DF-012", "Search Index", "Search Service", "Search Results", "HTTP"],
        ["DF-013", "Records API Service", "Notification Service", "Alert Message", "SNS"],
        ["DF-014", "Notification Service", "Healthcare Portal", "Push Notification", "WebSocket"],
        ["DF-015", "Data Lake", "Analytics Tools", "Analytics Data", "S3/Parquet"],
    ]
    
    # Dataset Inventory
    datasets_headers = ["ID", "Name", "Type", "Primary Key", "Sensitivity", "Retention"]
    datasets_rows = [
        ["DS-001", "Patient Demographics", "Relational", "patient_id", "High", "7 Years"],
        ["DS-002", "Medical History", "Relational", "record_id", "High", "10 Years"],
        ["DS-003", "Prescriptions", "Relational", "prescription_id", "High", "5 Years"],
        ["DS-004", "Lab Results", "Relational", "result_id", "High", "7 Years"],
        ["DS-005", "Appointments", "Relational", "appointment_id", "Medium", "3 Years"],
        ["DS-006", "Audit Trail", "Relational", "audit_id", "Medium", "5 Years"],
        ["DS-007", "User Activity Logs", "Unstructured", "log_id", "Medium", "1 Year"],
        ["DS-008", "Historical Analytics", "Parquet", "record_id", "Low", "10 Years"],
    ]
    
    # Dataset Relationships
    relationships_headers = ["Source", "Target", "Relation", "Mapping"]
    relationships_rows = [
        ["Patient Demographics", "Medical History", "1:N", "patient_id -> patient_id"],
        ["Patient Demographics", "Prescriptions", "1:N", "patient_id -> patient_id"],
        ["Patient Demographics", "Appointments", "1:N", "patient_id -> patient_id"],
        ["Medical History", "Lab Results", "1:N", "record_id -> related_record_id"],
        ["Prescriptions", "Lab Results", "N:M", "prescription_id <-> lab_test_id"],
        ["Patient Demographics", "Historical Analytics", "1:N", "patient_id -> patient_id"],
    ]
    
    # Context Entities
    entities_headers = ["Name", "Type", "Interaction"]
    entities_rows = [
        ["Healthcare Professional", "User", "Portal Access, Record Management"],
        ["Patient", "Person", "Records Stored, Notifications Received"],
        ["NHS Systems", "External System", "Data Exchange, Clinical Integration"],
        ["Compliance Auditor", "User", "Audit Trail Review, Compliance Reports"],
        ["Data Analyst", "User", "Analytics Dashboard Access"],
        ["System Administrator", "User", "System Configuration, User Management"],
    ]
    
    html_body = """<h1>Solution Architecture</h1>
<p><strong>Project:</strong> Digital Health Records Management System</p>
<p><strong>Status:</strong> Design Phase</p>
<p><strong>Last Updated:</strong> """ + str(__import__('datetime').date.today()) + """</p>
<hr/>

<h2>Architecture Overview</h2>
<p>A comprehensive solution for managing patient health records across the UK Health Security Agency. 
This system enables authorized healthcare professionals to securely access, update, and manage patient records 
while maintaining compliance with NHS Data Security and Protection Toolkit (DSPT).</p>

<h3>Key Objectives</h3>
<ul>
<li>Provide secure, real-time access to patient health records</li>
<li>Maintain compliance with NHS data security standards</li>
<li>Enable healthcare professionals to access records on mobile devices</li>
<li>Support comprehensive audit logging for compliance</li>
<li>Ensure end-to-end encryption of patient data</li>
</ul>

<hr/>

<h2>Architecture Components</h2>
"""
    
    html_body += build_html_table(components_headers, components_rows)
    
    html_body += """
<hr/>

<h2>Architecture Connections</h2>
"""
    
    html_body += build_html_table(connections_headers, connections_rows)
    
    html_body += """
<hr/>

<h2>Data Flow Entries</h2>
"""
    
    html_body += build_html_table(dataflows_headers, dataflows_rows)
    
    html_body += """
<hr/>

<h2>Dataset Inventory</h2>
"""
    
    html_body += build_html_table(datasets_headers, datasets_rows)
    
    html_body += """
<hr/>

<h2>Dataset Relationships</h2>
"""
    
    html_body += build_html_table(relationships_headers, relationships_rows)
    
    html_body += """
<hr/>

<h2>Context Entities</h2>
"""
    
    html_body += build_html_table(entities_headers, entities_rows)
    
    html_body += """
<hr/>

<h2>Security & Compliance</h2>

<h3>Security Requirements</h3>
<ul>
<li><strong>Authentication:</strong> Multi-factor authentication (MFA) via Entra ID</li>
<li><strong>Encryption:</strong> AES-256 encryption at rest, TLS 1.3 in transit</li>
<li><strong>Access Control:</strong> Role-based access control (RBAC) with principle of least privilege</li>
<li><strong>Audit Logging:</strong> All access attempts and data modifications logged</li>
<li><strong>Network Security:</strong> WAF, DDoS protection, network segmentation</li>
</ul>

<h3>Compliance Standards</h3>
<ul>
<li>NHS Data Security and Protection Toolkit (DSPT)</li>
<li>GDPR and UK Data Protection Act 2018</li>
<li>NHS Information Governance Toolkit (IGT)</li>
<li>NIST Cybersecurity Framework</li>
</ul>

<p><em>Note: Diagrams will be auto-generated and embedded below after running the diagram generation script.</em></p>
"""
    
    return html_body


def main():
    print("=" * 70)
    print("POPULATE CONFLUENCE PAGE WITH SAMPLE ARCHITECTURE DATA")
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
        
        print("Building HTML with sample tables...")
        html_body = build_sample_page()
        
        print("Updating Confluence page...")
        result = update_page_body(session, base_url, page_id, version, page_title, html_body)
        
        print("✓ Page updated successfully!")
        print()
        print("=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print("1. Run: confluence_update_diagrams.py")
        print("   This will generate diagrams from the tables above")
        print()
        print(f"2. View results in Confluence:")
        print(f"   {base_url}/spaces/{space_key}/pages/{page_id}/{page_title.replace(' ', '+')}")
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
