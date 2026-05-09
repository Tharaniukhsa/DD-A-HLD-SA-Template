"""
confluence_create_questionnaire.py
──────────────────────────────────

Creates a Data Solution Architecture Questionnaire page on Confluence.
Users fill in this questionnaire to specify:
  - Business context & data flow
  - Approved patterns (see UKHSA Cloud Strategy & Approved patterns.md file)
  - Components per layer (Ingestion, Processing, Storage, etc.)
  - Security & compliance requirements

Then run confluence_update_diagrams.py to auto-generate diagrams.
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
    if ca_bundle and not os.path.exists(ca_bundle):
        raise ValueError(f"CONFLUENCE_CA_BUNDLE path does not exist: {ca_bundle}")
    if os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").strip().lower() in {"1", "true", "yes"}:
        print("Warning: SSL verification is disabled.")
        return False
    return ca_bundle if ca_bundle else certifi.where()


def _tls():
    return get_tls_verify()


def find_page(session, base_url, space_key, title):
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


def update_page(session, base_url, page, body_html):
    page_id = page["id"]
    new_version = page["version"]["number"] + 1
    payload = {
        "version": {"number": new_version},
        "title": page["title"],
        "type": "page",
        "body": {"storage": {"value": body_html, "representation": "storage"}},
    }
    resp = _make_request(
        session, "PUT",
        f"{base_url}/rest/api/content/{page_id}",
        data=json.dumps(payload),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        verify=_tls(),
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to update page: {resp.status_code} {resp.text}")
    result = resp.json()
    links = result.get("_links", {})
    url = f"{links.get('base', base_url)}{links.get('webui', '')}"
    print(f"  Updated: {page['title']}\n    URL: {url}")
    return result


def create_page(session, base_url, space_key, title, body_html, parent_id):
    existing = find_page(session, base_url, space_key, title)
    if existing:
        print(f"  Page already exists — updating: {title}")
        return update_page(session, base_url, existing, body_html)

    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "ancestors": [{"id": parent_id}],
        "body": {"storage": {"value": body_html, "representation": "storage"}},
    }
    resp = _make_request(
        session, "POST",
        f"{base_url}/rest/api/content",
        data=json.dumps(payload),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        verify=_tls(),
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create page: {resp.status_code} {resp.text}")
    page = resp.json()
    links = page.get("_links", {})
    url = f"{links.get('base', base_url)}{links.get('webui', '')}"
    print(f"  Created: {title}\n    URL: {url}")
    return page


QUESTIONNAIRE_HTML = """
<p><strong>Solution Architecture Questionnaire for Data-Centric Systems</strong></p>

<p>This questionnaire captures all necessary information to auto-generate your Solution Architecture diagrams. Fill in each section, then run <code>confluence_update_diagrams.py</code> to generate diagrams automatically.</p>

<p><strong>Reference:</strong> Download UKHSA Cloud Strategy & Approved patterns.md from the main Solution Architecture page for detailed pattern descriptions and rationale.</p>

<hr />

<h2>1. Business Context</h2>

<p><em>Provide business context for your data solution.</em></p>

<table>
  <thead><tr><th>Field</th><th>Value / Answer</th></tr></thead>
  <tbody>
    <tr><td><strong>Solution Name</strong></td><td></td></tr>
    <tr><td><strong>LeanIX Business Capability ID</strong><br/><em>e.g., CAP-001</em></td><td></td></tr>
    <tr><td><strong>Business Capability Name</strong><br/><em>e.g., "Disease Surveillance", "Patient Records Management"</em></td><td></td></tr>
    <tr><td><strong>Business Outcome / Goal</strong><br/><em>What does this solution enable?</em></td><td></td></tr>
    <tr><td><strong>Data Domain</strong><br/><em>e.g., "Epidemiology", "Laboratory", "Hospital Operations"</em></td><td></td></tr>
    <tr><td><strong>Primary Stakeholders</strong><br/><em>Business Owner, Data Owner, Security Lead, etc.</em></td><td></td></tr>
    <tr><td><strong>Data Sensitivity Level</strong><br/><em>Public / Internal / Sensitive / Restricted (PII/PHI)</em></td><td></td></tr>
    <tr><td><strong>Data Retention Period</strong><br/><em>e.g., 7 years, 35 days, indefinite</em></td><td></td></tr>
  </tbody>
</table>

<hr />

<h2>2. Data Ingestion Layer</h2>

<p><em>How does data enter the system? Select the primary pattern(s) that apply.</em></p>

<h3>2.1 Select Ingestion Pattern(s)</h3>

<p><strong>Choose one or more:</strong></p>

<table>
  <thead><tr><th>Pattern</th><th>When to Use</th><th>Selected?</th><th>Details (if selected)</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Direct API Ingestion</strong><br/>(Pattern 1A)</td>
      <td>Real-time feeds, transactional data, live APIs</td>
      <td>☐ Yes</td>
      <td><em>API endpoint, authentication method, rate limits, SLA</em></td>
    </tr>
    <tr>
      <td><strong>Batch File Upload</strong><br/>(Pattern 1B)</td>
      <td>Large datasets, monthly reports, historical data</td>
      <td>☐ Yes</td>
      <td><em>File format, frequency, source system, volume</em></td>
    </tr>
    <tr>
      <td><strong>Database Replication</strong><br/>(Pattern 1C)</td>
      <td>Real-time sync from legacy systems, operational stores</td>
      <td>☐ Yes</td>
      <td><em>Source DB type, change capture method (CDC), latency requirement</em></td>
    </tr>
    <tr>
      <td><strong>Streaming Ingestion</strong><br/>(Pattern 1D)</td>
      <td>High-frequency data, sensors, continuous monitoring</td>
      <td>☐ Yes</td>
      <td><em>Data format, throughput (events/sec), latency requirement</em></td>
    </tr>
  </tbody>
</table>

<h3>2.2 Data Sources</h3>

<p><em>List all external data sources.</em></p>

<table>
  <thead><tr><th>No</th><th>Source Name</th><th>Ingestion Pattern</th><th>Data Type</th><th>Frequency</th><th>Expected Volume</th></tr></thead>
  <tbody>
    <tr><td>1</td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>2</td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>3</td><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

<hr />

<h2>3. Data Processing Layer</h2>

<p><em>How is data transformed and enriched? Select the primary pattern(s).</em></p>

<h3>3.1 Select Processing Pattern(s)</h3>

<table>
  <thead><tr><th>Pattern</th><th>When to Use</th><th>Selected?</th><th>Details (if selected)</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Batch ETL</strong><br/>(Pattern 2A)</td>
      <td>Large volumes, complex transformations, daily/weekly schedules</td>
      <td>☐ Yes</td>
      <td><em>Schedule (cron), transformation logic, SLA</em></td>
    </tr>
    <tr>
      <td><strong>Real-time Stream Processing</strong><br/>(Pattern 2B)</td>
      <td>Live analytics, anomaly detection, event-driven</td>
      <td>☐ Yes</td>
      <td><em>Latency requirement (ms), throughput, alert triggers</em></td>
    </tr>
    <tr>
      <td><strong>Scheduled Spark/Dask Jobs</strong><br/>(Pattern 2C)</td>
      <td>Machine learning, statistical analysis, data science</td>
      <td>☐ Yes</td>
      <td><em>Algorithm type, schedule, compute resources needed</em></td>
    </tr>
    <tr>
      <td><strong>Federated Query</strong><br/>(Pattern 2D)</td>
      <td>Multi-source analysis without data movement</td>
      <td>☐ Yes</td>
      <td><em>Query sources, join complexity, performance SLA</em></td>
    </tr>
  </tbody>
</table>

<h3>3.2 Transformation Components</h3>

<p><em>Describe major transformations and business rules.</em></p>

<table>
  <thead><tr><th>No</th><th>Component / Transformation Name</th><th>Pattern</th><th>Input Data</th><th>Output Data</th><th>Business Logic</th></tr></thead>
  <tbody>
    <tr><td>1</td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>2</td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>3</td><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

<hr />

<h2>4. Data Storage Layer</h2>

<p><em>Where does the processed data live? Choose the primary storage pattern.</em></p>

<h3>4.1 Primary Storage Choice</h3>

<table>
  <thead><tr><th>Storage Pattern</th><th>When to Use</th><th>Recommended AWS Service</th><th>Selected?</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Transactional Database (OLTP)</strong><br/>(Pattern 3A)</td>
      <td>Real-time operational data, high concurrency, ACID transactions</td>
      <td>Aurora PostgreSQL (preferred) or RDS</td>
      <td>☐ Yes</td>
    </tr>
    <tr>
      <td><strong>Data Warehouse (OLAP)</strong><br/>(Pattern 3B)</td>
      <td>Historical analysis, reporting, BI dashboards</td>
      <td>Redshift</td>
      <td>☐ Yes</td>
    </tr>
    <tr>
      <td><strong>Data Lake</strong><br/>(Pattern 3C)</td>
      <td>Raw/semi-structured data, exploratory analytics, data science</td>
      <td>S3 (Bronze/Silver/Gold zones) + Glue Catalog</td>
      <td>☐ Yes</td>
    </tr>
    <tr>
      <td><strong>Time-Series Database</strong><br/>(Pattern 3D)</td>
      <td>Metrics, sensor data, surveillance monitoring</td>
      <td>Amazon Timestream or DynamoDB with TTL</td>
      <td>☐ Yes</td>
    </tr>
    <tr>
      <td><strong>Document Store</strong><br/>(Pattern 3E)</td>
      <td>JSON documents, event logs, unstructured nested data</td>
      <td>DynamoDB or DocumentDB</td>
      <td>☐ Yes</td>
    </tr>
  </tbody>
</table>

<h3>4.2 Storage Details</h3>

<table>
  <thead><tr><th>Field</th><th>Value / Answer</th></tr></thead>
  <tbody>
    <tr><td><strong>Storage Pattern Selected</strong></td><td></td></tr>
    <tr><td><strong>Expected Data Volume</strong><br/><em>e.g., 100 GB, 1 TB, 10 TB</em></td><td></td></tr>
    <tr><td><strong>Growth Rate</strong><br/><em>e.g., 10 GB/month, 100 GB/year</em></td><td></td></tr>
    <tr><td><strong>Query Frequency</strong><br/><em>Real-time, hourly, daily, weekly</em></td><td></td></tr>
    <tr><td><strong>Read Concurrency</strong><br/><em>e.g., 10 concurrent queries, 1000 concurrent reads</em></td><td></td></tr>
    <tr><td><strong>Backup & Recovery Requirements</strong><br/><em>RPO (Recovery Point Objective), RTO (Recovery Time Objective)</em></td><td></td></tr>
  </tbody>
</table>

<hr />

<h2>5. Data Governance & Cataloging</h2>

<p><em>How is data managed, discovered, and governed?</em></p>

<h3>5.1 Governance Patterns</h3>

<table>
  <thead><tr><th>Pattern</th><th>Description</th><th>Required?</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Data Catalog</strong><br/>(Pattern 5A)</td>
      <td>Centralized metadata, discovery, lineage (AWS Glue Catalog + Lake Formation)</td>
      <td>☐ Yes</td>
    </tr>
    <tr>
      <td><strong>Data Quality & Validation</strong><br/>(Pattern 5B)</td>
      <td>Quality rules, schema validation, anomaly detection (Glue DataBrew)</td>
      <td>☐ Yes</td>
    </tr>
    <tr>
      <td><strong>Data Lineage & Audit Trail</strong><br/>(Pattern 5C)</td>
      <td>Track data provenance, transformations, access logs (Lake Formation + CloudTrail)</td>
      <td>☐ Yes</td>
    </tr>
  </tbody>
</table>

<h3>5.2 Data Quality Rules</h3>

<p><em>List key quality checks that must pass before data is published.</em></p>

<table>
  <thead><tr><th>No</th><th>Quality Check</th><th>Rule / Condition</th><th>Action if Failed</th></tr></thead>
  <tbody>
    <tr><td>1</td><td><em>e.g., Schema Validation</em></td><td><em>All required columns present</em></td><td><em>Reject load, alert owner</em></td></tr>
    <tr><td>2</td><td></td><td></td><td></td></tr>
    <tr><td>3</td><td></td><td></td><td></td></tr>
  </tbody>
</table>

<hr />

<h2>6. Security & Compliance</h2>

<p><em>All security patterns are mandatory. Specify details per pattern.</em></p>

<h3>6.1 Access Control (Pattern 6A)</h3>

<table>
  <thead><tr><th>Field</th><th>Value / Answer</th></tr></thead>
  <tbody>
    <tr><td><strong>Authentication Method</strong><br/><em>OAuth 2.0, Entra ID SAML, mTLS, API Key</em></td><td></td></tr>
    <tr><td><strong>Authorization Model</strong><br/><em>Role-Based Access Control (RBAC), Attribute-Based (ABAC)</em></td><td></td></tr>
    <tr><td><strong>User Roles & Permissions</strong><br/><em>List roles (e.g., Data Analyst, Data Engineer) and their access levels</em></td><td></td></tr>
    <tr><td><strong>MFA Required?</strong><br/><em>Yes / No</em></td><td></td></tr>
  </tbody>
</table>

<h3>6.2 Encryption & Key Management (Pattern 6B)</h3>

<table>
  <thead><tr><th>Field</th><th>Value / Answer</th></tr></thead>
  <tbody>
    <tr><td><strong>Encryption at Rest</strong><br/><em>AWS KMS (customer-managed keys recommended)</em></td><td>☐ Yes</td></tr>
    <tr><td><strong>Encryption in Transit</strong><br/><em>TLS 1.2+ required</em></td><td>☐ Yes</td></tr>
    <tr><td><strong>Key Rotation Policy</strong><br/><em>e.g., annual, every 90 days</em></td><td></td></tr>
  </tbody>
</table>

<h3>6.3 Network Security & Isolation (Pattern 6C)</h3>

<table>
  <thead><tr><th>Field</th><th>Value / Answer</th></tr></thead>
  <tbody>
    <tr><td><strong>Network Architecture</strong><br/><em>VPC with private subnets, VPC endpoints, no internet access</em></td><td>☐ Confirmed</td></tr>
    <tr><td><strong>Data Processing Location</strong><br/><em>Private subnets only, no public IPs</em></td><td>☐ Confirmed</td></tr>
    <tr><td><strong>Egress Control</strong><br/><em>VPC endpoints to AWS services, NAT for outbound</em></td><td>☐ Confirmed</td></tr>
  </tbody>
</table>

<h3>6.4 Data Masking & Anonymization (Pattern 6D) — If Handling PII/PHI</h3>

<table>
  <thead><tr><th>Field</th><th>Value / Answer</th></tr></thead>
  <tbody>
    <tr><td><strong>Is this solution handling PII/PHI?</strong><br/><em>Yes / No</em></td><td></td></tr>
    <tr><td><strong>Masking Techniques Required</strong><br/><em>Pseudonymization, Generalization, Redaction, Aggregation</em></td><td></td></tr>
    <tr><td><strong>GDPR / DPIA Required?</strong><br/><em>Yes / No</em></td><td></td></tr>
  </tbody>
</table>

<hr />

<h2>7. Monitoring & Observability</h2>

<p><em>All monitoring patterns are mandatory.</em></p>

<h3>7.1 Centralized Logging (Pattern 7A)</h3>

<table>
  <thead><tr><th>Field</th><th>Value / Answer</th></tr></thead>
  <tbody>
    <tr><td><strong>Log Aggregation Service</strong></td><td>CloudWatch Logs (recommended)</td></tr>
    <tr><td><strong>Log Retention Period</strong><br/><em>e.g., 30 days, 1 year</em></td><td></td></tr>
    <tr><td><strong>Key Events to Log</strong><br/><em>Job start/completion, row counts, errors, access events</em></td><td></td></tr>
  </tbody>
</table>

<h3>7.2 Data Quality Monitoring (Pattern 7B)</h3>

<table>
  <thead><tr><th>Metric</th><th>Alert Threshold</th><th>Notification</th></tr></thead>
  <tbody>
    <tr><td><strong>Data Freshness</strong><br/><em>How recent is latest data?</em></td><td><em>e.g., alert if no data in 4 hours</em></td><td>SNS / Email</td></tr>
    <tr><td><strong>Completeness</strong><br/><em>% null values</em></td><td><em>e.g., alert if > 5% nulls</em></td><td>SNS / Email</td></tr>
    <tr><td><strong>Volume Anomalies</strong><br/><em>Unexpected row counts</em></td><td><em>e.g., alert if 50% variance</em></td><td>SNS / Email</td></tr>
  </tbody>
</table>

<h3>7.3 Performance & Cost Monitoring (Pattern 7C)</h3>

<table>
  <thead><tr><th>Metric</th><th>Target / Baseline</th></tr></thead>
  <tbody>
    <tr><td><strong>Query Execution Time</strong></td><td><em>e.g., < 30 seconds</em></td></tr>
    <tr><td><strong>Monthly Compute Cost</strong></td><td><em>e.g., $ budget threshold</em></td></tr>
    <tr><td><strong>Storage Utilization</strong></td><td><em>e.g., alert if > 80% capacity</em></td></tr>
  </tbody>
</table>

<hr />

<h2>8. Resilience & Disaster Recovery</h2>

<p><em>Define backup and recovery strategy based on data criticality.</em></p>

<h3>8.1 Backup Strategy (Pattern 8A)</h3>

<table>
  <thead><tr><th>Field</th><th>Value / Answer</th></tr></thead>
  <tbody>
    <tr><td><strong>Data Criticality Level</strong><br/><em>Critical / Important / Standard</em></td><td></td></tr>
    <tr><td><strong>RPO (Recovery Point Objective)</strong><br/><em>Max acceptable data loss</em></td><td></td></tr>
    <tr><td><strong>RTO (Recovery Time Objective)</strong><br/><em>Max acceptable downtime</em></td><td></td></tr>
    <tr><td><strong>Backup Frequency</strong><br/><em>Hourly, daily, weekly</em></td><td></td></tr>
    <tr><td><strong>Backup Retention</strong><br/><em>e.g., 35 days, 1 year</em></td><td></td></tr>
  </tbody>
</table>

<h3>8.2 Multi-AZ / Multi-Region (Pattern 8B)</h3>

<table>
  <thead><tr><th>Field</th><th>Value / Answer</th></tr></thead>
  <tbody>
    <tr><td><strong>Primary Region</strong></td><td>eu-west-2 (London)</td></tr>
    <tr><td><strong>Secondary Region Required?</strong><br/><em>Yes / No — for compliance or resilience</em></td><td></td></tr>
    <tr><td><strong>Secondary Region</strong><br/><em>e.g., eu-west-1 (Ireland)</em></td><td></td></tr>
    <tr><td><strong>Replication Strategy</strong><br/><em>Cross-region, cross-AZ, or both</em></td><td></td></tr>
  </tbody>
</table>

<hr />

<h2>9. Data Flows Summary</h2>

<p><em>Map high-level data movement through the system. (More detail will be in the auto-generated diagram.)</em></p>

<table>
  <thead><tr><th>Flow ID</th><th>From (Source)</th><th>To (Destination)</th><th>Data Type</th><th>Frequency</th><th>Volume</th></tr></thead>
  <tbody>
    <tr><td>F1</td><td><em>e.g., Lab API</em></td><td><em>e.g., S3 Raw Data</em></td><td><em>e.g., JSON records</em></td><td><em>Real-time</em></td><td><em>100 msg/sec</em></td></tr>
    <tr><td>F2</td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>F3</td><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>

<hr />

<h2>10. Auto-Generated Diagrams (Placeholder)</h2>

<p><em>After filling in the questionnaire above, run:</em></p>

<pre>confluence_sync_questionnaire_to_main.py</pre>

<p><em>This will copy relevant questionnaire content into the main Solution Architecture page and then regenerate diagrams automatically.</em></p>

<p><em>The following diagrams will automatically appear here:</em></p>

<h3>Solution Architecture Diagram</h3>
<p><strong>[[DIAGRAM:solution-architecture]]</strong></p>

<h3>Data Flow Diagram</h3>
<p><strong>[[DIAGRAM:data-flow]]</strong></p>

<h3>Approved Patterns Used</h3>
<p><em>Auto-generated summary of which patterns were selected for this solution.</em></p>
<table>
  <thead><tr><th>Layer</th><th>Pattern(s) Selected</th><th>AWS Service(s)</th></tr></thead>
  <tbody>
    <tr><td>Ingestion</td><td></td><td></td></tr>
    <tr><td>Processing</td><td></td><td></td></tr>
    <tr><td>Storage</td><td></td><td></td></tr>
    <tr><td>Governance</td><td></td><td></td></tr>
    <tr><td>Security</td><td></td><td></td></tr>
    <tr><td>Monitoring</td><td></td><td></td></tr>
    <tr><td>Resilience</td><td></td><td></td></tr>
  </tbody>
</table>

<hr />

<h2>11. Related Documents</h2>

<ul>
  <li><a href="#">Solution Architecture HLD</a> (main page)</li>
  <li>UKHSA Cloud Strategy & Approved patterns.md (pattern reference - download from Solution Architecture page)</li>
  <li><a href="#">Low Level Design (LLD)</a> (for detailed component specs)</li>
  <li><a href="#">Architectural Decision Records</a> (ADRs for decisions)</li>
</ul>
"""


def main():
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    main_page_title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "Solution Architecture")

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    print(f"\nFinding '{main_page_title}' in space '{space_key}'...")
    main_page = find_page(session, base_url, space_key, main_page_title)
    if not main_page:
        raise ValueError(f"Main page '{main_page_title}' not found. Run confluence_create_architecture_pages.py first.")

    main_id = main_page["id"]
    print(f"Found: ID {main_id}\n")

    print("Creating questionnaire page...\n")
    questionnaire = create_page(
        session, base_url, space_key,
        "Data Solution Architecture Questionnaire",
        QUESTIONNAIRE_HTML,
        main_id,
    )

    print("\nQuestionnaire page ready!")
    print("\nNext steps:")
    print("  1. Fill in the questionnaire with your data solution details")
    print("  2. Run: & \".\\venv\\Scripts\\python.exe\" \".\\confluence_update_diagrams.py\"")
    print("  3. Diagrams will auto-generate on the page")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
