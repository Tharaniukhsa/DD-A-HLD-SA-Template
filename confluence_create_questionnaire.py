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

<p>This questionnaire captures all necessary information to auto-generate your Solution Architecture diagrams. Fill in each section, then run the sync script to generate diagrams automatically.</p>

<p><strong>Reference:</strong> See the <a href="https://ukhsa.atlassian.net/wiki/spaces/CDA/pages/520783944/Architecture+Patterns+Reference">Architecture Patterns Reference</a> page for full descriptions, rationale, and ADRs for every pattern.</p>

<h2>&#128196; Contents</h2>

<ac:structured-macro ac:name="toc">
  <ac:parameter ac:name="printable">true</ac:parameter>
  <ac:parameter ac:name="style">disc</ac:parameter>
  <ac:parameter ac:name="maxLevel">2</ac:parameter>
  <ac:parameter ac:name="minLevel">2</ac:parameter>
  <ac:parameter ac:name="type">list</ac:parameter>
</ac:structured-macro>

<hr />

<h2>&#9654; How to Use This Page</h2>

<ac:structured-macro ac:name="info">
<ac:rich-text-body>
<p><strong>Three steps to get your diagrams generated automatically:</strong></p>
<ol>
  <li><strong>Fill in Section 1</strong> (Business Context) — solution name, data domain, sensitivity level, and stakeholders.</li>
  <li><strong>Work through Sections 2–11</strong> and tick every pattern that applies to your workload:
    <ul>
      <li><strong>Sections 2–9</strong> — Data layer patterns (ingestion, processing, storage, integration, governance, security, monitoring, resilience)</li>
      <li><strong>Section 10</strong> — Infrastructure &amp; Platform patterns (INF-01 to INF-06)</li>
      <li><strong>Section 11</strong> — Target State Architecture patterns (TSA-NET and TSA-IDN)</li>
    </ul>
    For each ticked pattern, fill in the <em>Details</em> column. Use the <strong>Fast-Fill Guidance</strong> and <strong>Pattern Quick-Reference</strong> below if you are unsure which to pick.
  </li>
  <li><strong>Run the sync script</strong> from your local workspace:<br/>
  <code>python confluence_sync_questionnaire_to_main.py</code><br/>
  This reads your answers, merges them into the main HLD SA page, and auto-generates all HLD + LLD diagrams on Confluence.</li>
</ol>
<p>&#128276; <strong>You do not need to edit the main SA page or the LLD page directly.</strong> Everything flows from this questionnaire. INF-01 (Landing Zone) and INF-05 (Federated Identity) are always mandatory — they will be applied automatically even if not ticked.</p>
</ac:rich-text-body>
</ac:structured-macro>

<hr />

<h2>&#9889; Fast-Fill Guidance</h2>

<p><em>Use the table below to quickly identify which patterns to tick based on your project type. Find your scenario, then go to the relevant sections and tick those patterns.</em></p>

<table>
  <thead>
    <tr>
      <th>Project Type / Scenario</th>
      <th>Mandatory Patterns (always tick)</th>
      <th>Likely Additional Patterns</th>
      <th>Skip / Not Applicable</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>New analytics / data pipeline on AWS</strong><br/><em>e.g., disease surveillance feed, lab data ingestion</em></td>
      <td>INF-01, INF-05, 3C (Data Lake), 6A, 6B, 6C, 7A, 7B, 8A (Backup)</td>
      <td>1B or 1C or 1D (pick ingestion type), 2A (Batch ETL), 4B (orchestration), 5A (catalogue), 5C (lineage)</td>
      <td>TSA-NET-02 — only if public-facing API or portal; 3B — only if BI warehouse needed</td>
    </tr>
    <tr>
      <td><strong>Public-facing API or web application</strong><br/><em>e.g., data portal, UKHSA public dashboard</em></td>
      <td>INF-01, INF-04, INF-05, TSA-NET-02 (ALB + WAF), 6A, 6B, 6C, 7A, 7B, 8A, 8B</td>
      <td>1A (API ingestion), TSA-NET-01 (Transit Gateway if multi-VPC), TSA-IDN-02 (PIM for admin access)</td>
      <td>1D — only if real-time streaming also required; 3D — only if time-series metrics needed</td>
    </tr>
    <tr>
      <td><strong>Hybrid workload (on-prem + cloud)</strong><br/><em>e.g., migrating legacy system to HALO LZ</em></td>
      <td>INF-01, INF-02 (Direct Connect / VPN), INF-04 (Split DNS), INF-05, 6A, 6B, 6C, 7A, 8A</td>
      <td>1C (DB replication via DMS), TSA-NET-01 (Transit Gateway routing), 4C (data sync/replication)</td>
      <td>TSA-NET-02 — only if there is a public-facing endpoint; 1A — only if a new API is being added</td>
    </tr>
    <tr>
      <td><strong>ML / data science platform</strong><br/><em>e.g., SageMaker training, EMR Spark jobs</em></td>
      <td>INF-01, INF-05, 3C (Data Lake), 2C (Spark/ML jobs), 5A (catalogue), 6A, 6B, 6C, 6D (if PII), 7A, 8A</td>
      <td>2D (federated query via Athena), 1B or 1C (data source), INF-06 (EDAP if analytics platform), 5C (lineage for model inputs)</td>
      <td>TSA-NET-02 — only if model serving endpoint is public; 3B — only if BI / reporting output also required</td>
    </tr>
    <tr>
      <td><strong>Real-time / streaming system</strong><br/><em>e.g., IoT sensors, live monitoring, alerting</em></td>
      <td>INF-01, INF-05, 1D (streaming ingestion), 2B (real-time processing), 3D (time-series DB), 6A, 6B, 6C, 7A, 7B, 8A</td>
      <td>4A (event-driven pipelines via EventBridge/SQS), TSA-NET-01 (if multi-VPC routing), INF-04 (split DNS)</td>
      <td>1B (batch file upload — not needed for real-time); 3B (warehouse — only add if historical reporting also needed)</td>
    </tr>
    <tr>
      <td><strong>Identity / access management change</strong><br/><em>e.g., new SCIM group, PIM role, JML process</em></td>
      <td>INF-05 (Entra ID as IdP), TSA-IDN-01 (Passwordless auth), TSA-IDN-02 (PIM / JIT elevation), 6A, 6B, 7A (audit logging)</td>
      <td>TSA-NET-01 (if network segmentation is also changing), INF-06 (if platform access roles are changing), 5A (if data access catalogue entries affected)</td>
      <td>Data layer patterns (1A–4C, 5A–8C) — unless data access permissions are also changing</td>
    </tr>
  </tbody>
</table>

<hr />

<h2>&#128270; Pattern Quick-Reference</h2>

<p><em>Not sure what a pattern does? Use this at-a-glance summary before filling in the sections below.</em></p>

<table>
  <thead><tr><th>Pattern ID</th><th>Name</th><th>One-Line Summary</th><th>Key AWS / Azure Service</th></tr></thead>
  <tbody>
    <tr><td>INF-01</td><td>Strategic Landing Zone</td><td>All workloads must go to AWS HALO or Azure PHECloud LZ</td><td>Control Tower, AWS Organizations</td></tr>
    <tr><td>INF-02</td><td>Hybrid Connectivity</td><td>On-prem ↔ cloud via Direct Connect / ExpressRoute only</td><td>AWS Direct Connect, Transit Gateway</td></tr>
    <tr><td>INF-03</td><td>Zero Trust Network Architecture</td><td>Replace implicit network trust with identity-verified, context-aware access (ZPA / ZIA)</td><td>zScaler ZPA/ZIA, AWS Verified Access</td></tr>
    <tr><td>INF-04</td><td>Split-Horizon DNS</td><td>Consistent internal + external DNS via Route 53</td><td>Route 53 Resolver, Private Hosted Zones</td></tr>
    <tr><td>INF-05</td><td>Federated Identity</td><td>Entra ID is the only IdP — no local IAM users permitted</td><td>Microsoft Entra ID, IAM Identity Center</td></tr>
    <tr><td>INF-06</td><td>Approved Platforms</td><td>Use EDAP, Azure APIM, Sentinel, or AVD — no bespoke equivalents</td><td>EDAP, Azure APIM, Sentinel</td></tr>
    <tr><td>TSA-NET-01</td><td>Zero-Trust Network Access (ZTNA)</td><td>Replace implicit network trust with identity-verified, device-checked, context-aware access</td><td>AWS Transit Gateway, Azure Virtual WAN, Zscaler</td></tr>
    <tr><td>TSA-NET-02</td><td>Centralised Ingress (ALB + WAF)</td><td>All public-facing workloads must use a single WAF-protected ALB ingress point</td><td>ALB, AWS WAF, Route 53</td></tr>
    <tr><td>TSA-IDN-01</td><td>Passwordless Authentication</td><td>FIDO2 / Windows Hello / Certificate-based auth for all users — no passwords</td><td>Microsoft Entra ID, FIDO2, AWS IAM Identity Center</td></tr>
    <tr><td>TSA-IDN-02</td><td>Privileged Identity Management (PIM)</td><td>Elevated access is time-bound, approval-gated, and audited via Entra PIM</td><td>Entra ID PIM, CloudTrail, AWS IAM Access Analyzer</td></tr>
    <tr><td>1A</td><td>Direct API Ingestion</td><td>Real-time REST/webhook feeds into the platform</td><td>API Gateway, SQS, EventBridge</td></tr>
    <tr><td>1B</td><td>Batch File Upload</td><td>Scheduled bulk file transfers (CSV, JSON, Parquet)</td><td>S3, Glue, AWS Transfer Family (SFTP)</td></tr>
    <tr><td>1C</td><td>Database Replication</td><td>Continuous CDC sync from source DB to cloud</td><td>AWS DMS, Aurora PostgreSQL</td></tr>
    <tr><td>1D</td><td>Streaming Ingestion</td><td>High-velocity event/sensor streams</td><td>Kinesis, MSK (Kafka)</td></tr>
    <tr><td>2A</td><td>Batch ETL</td><td>Scheduled large-volume transformation jobs</td><td>Glue, Step Functions</td></tr>
    <tr><td>2B</td><td>Real-Time Stream Processing</td><td>Live anomaly detection and event-driven transforms</td><td>Kinesis Data Analytics, Lambda</td></tr>
    <tr><td>2C</td><td>Spark / ML Jobs</td><td>Transient EMR or SageMaker training runs</td><td>Amazon EMR, SageMaker</td></tr>
    <tr><td>2D</td><td>Federated Query</td><td>Query data where it sits — no copy needed</td><td>Athena, Redshift Spectrum</td></tr>
    <tr><td>3A</td><td>Transactional DB (OLTP)</td><td>ACID-compliant relational database for operational data</td><td>Aurora PostgreSQL, RDS</td></tr>
    <tr><td>3B</td><td>Data Warehouse (OLAP)</td><td>Historical analytics and BI reporting</td><td>Redshift, QuickSight</td></tr>
    <tr><td>3C</td><td>Data Lake (Bronze/Silver/Gold)</td><td>Centralised raw → conformed → curated S3 storage</td><td>S3, Glue Catalog, Lake Formation</td></tr>
    <tr><td>3D</td><td>Time-Series DB</td><td>Per-second/minute metrics and surveillance data</td><td>Amazon Timestream</td></tr>
    <tr><td>3E</td><td>Document Store</td><td>JSON / nested / schema-flexible data</td><td>DynamoDB, DocumentDB, OpenSearch</td></tr>
    <tr><td>4A</td><td>Event-Driven Pipelines</td><td>Services communicate via events — no direct coupling</td><td>EventBridge, SQS, SNS, Lambda</td></tr>
    <tr><td>4B</td><td>ETL Orchestration</td><td>Multi-step workflows with retries and branching</td><td>Step Functions, Apache Airflow (MWAA)</td></tr>
    <tr><td>4C</td><td>Data Replication &amp; Sync</td><td>Cross-region / cross-AZ copies for HA and DR</td><td>S3 CRR, RDS Read Replicas</td></tr>
    <tr><td>5A</td><td>Data Catalogue</td><td>Centralised metadata and discoverability</td><td>Glue Data Catalog, Lake Formation</td></tr>
    <tr><td>5B</td><td>Data Quality</td><td>Automated quality gates before data is promoted</td><td>Glue DataBrew, EventBridge</td></tr>
    <tr><td>5C</td><td>Data Lineage &amp; Audit</td><td>Full provenance trail for compliance and root-cause</td><td>CloudTrail, Lake Formation, OpenLineage</td></tr>
    <tr><td>6A</td><td>Access Control</td><td>&#9888; MANDATORY — IAM + Lake Formation TBAC on all data</td><td>IAM, Lake Formation, S3 Object Lock</td></tr>
    <tr><td>6B</td><td>Encryption &amp; Key Mgmt</td><td>&#9888; MANDATORY — KMS CMK at rest, TLS 1.2+ in transit</td><td>KMS, Secrets Manager, ACM</td></tr>
    <tr><td>6C</td><td>Network Security</td><td>&#9888; MANDATORY — VPC private subnets, WAF, VPC Endpoints</td><td>VPC, Security Groups, WAF, PrivateLink</td></tr>
    <tr><td>6D</td><td>Data Masking</td><td>Required if handling PII / PHI — de-identify before non-prod</td><td>Glue DataBrew, Lambda</td></tr>
    <tr><td>7A</td><td>Centralised Logging</td><td>&#9888; MANDATORY — CloudWatch + CloudTrail → Sentinel</td><td>CloudWatch Logs, X-Ray, CloudTrail</td></tr>
    <tr><td>7B</td><td>Performance Alerting</td><td>&#9888; MANDATORY — alarms on latency, errors, capacity</td><td>CloudWatch Alarms, SNS</td></tr>
    <tr><td>7C</td><td>Cost Tracking</td><td>FinOps — tagged resources, budget alerts, rightsizing</td><td>Cost Explorer, Budgets, Compute Optimizer</td></tr>
    <tr><td>8A</td><td>Backup &amp; PITR</td><td>&#9888; MANDATORY — centralised AWS Backup + S3 versioning</td><td>AWS Backup, RDS snapshots, S3 versioning</td></tr>
    <tr><td>8B</td><td>Multi-Region DR</td><td>Required if RTO &lt; 4h or RPO &lt; 1h — Route 53 failover</td><td>Route 53, S3 CRR, RDS cross-region replica</td></tr>
  </tbody>
</table>

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

<h2>10. Infrastructure &amp; Platform Patterns</h2>

<p><em>Select the UKHSA-approved infrastructure patterns that apply to this workload. These control landing zone placement, connectivity, identity, DNS, and platform choices.</em></p>

<table>
  <thead><tr><th>Pattern</th><th>When to Use</th><th>Selected?</th><th>Details (if selected)</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Strategic Landing Zone Placement</strong><br/>(UKHSA-INF-01)</td>
      <td>All new workloads — must deploy to AWS HALO or Azure PHECloud LZ</td>
      <td>&#9744; Yes (mandatory)</td>
      <td><em>Target LZ: AWS HALO / Azure PHECloud / Other (specify)</em></td>
    </tr>
    <tr>
      <td><strong>Hybrid Cloud Connectivity</strong><br/>(UKHSA-INF-02)</td>
      <td>Any workload needing on-premises connectivity (Direct Connect / ExpressRoute)</td>
      <td>&#9744; Yes</td>
      <td><em>On-prem systems accessed, estimated bandwidth</em></td>
    </tr>
    <tr>
      <td><strong>Zero Trust End-User Access (zScaler)</strong><br/>(UKHSA-INF-03)</td>
      <td>Any workload accessed by end users from internet or corporate devices</td>
      <td>&#9744; Yes</td>
      <td><em>User population, ZPA or ZIA required</em></td>
    </tr>
    <tr>
      <td><strong>Split-Horizon DNS</strong><br/>(UKHSA-INF-04)</td>
      <td>Any workload with a domain name — internal and external resolution required</td>
      <td>&#9744; Yes</td>
      <td><em>Desired hostname (e.g. api.myservice.aws.ukhsa.gov.uk)</em></td>
    </tr>
    <tr>
      <td><strong>Federated Identity (Entra ID)</strong><br/>(UKHSA-INF-05)</td>
      <td>All workloads requiring user authentication — no local IAM users permitted</td>
      <td>&#9744; Yes (mandatory)</td>
      <td><em>User roles required, JIT/PIM needed?, SCIM provisioning groups</em></td>
    </tr>
    <tr>
      <td><strong>Approved Platform Portfolio</strong><br/>(UKHSA-INF-06)</td>
      <td>Workload uses EDAP, Azure APIM, Sentinel, AVD, or other shared platforms</td>
      <td>&#9744; Yes</td>
      <td><em>Platform(s) used: EDAP / Azure APIM / Sentinel / AVD / Other</em></td>
    </tr>
  </tbody>
</table>

<hr />

<h2>11. Target State Architecture Patterns</h2>

<p><em>Select Target State patterns relevant to the networking and identity design of this workload.</em></p>

<h3>11.1 Networking</h3>

<table>
  <thead><tr><th>Pattern</th><th>When to Use</th><th>Selected?</th><th>Details (if selected)</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Hub-and-Spoke (Transit Gateway / Virtual WAN)</strong><br/>(TSA-NET-01)</td>
      <td>Multi-VPC or multi-account workloads needing centralised routing</td>
      <td>&#9744; Yes</td>
      <td><em>Number of spoke VPCs, cross-account routing required?</em></td>
    </tr>
    <tr>
      <td><strong>Centralised Ingress (ALB + WAF)</strong><br/>(TSA-NET-02)</td>
      <td>Any public-facing application or API endpoint</td>
      <td>&#9744; Yes</td>
      <td><em>Public hostname, expected TPS, WAF rule sets needed</em></td>
    </tr>
  </tbody>
</table>

<h3>11.2 Identity</h3>

<table>
  <thead><tr><th>Pattern</th><th>When to Use</th><th>Selected?</th><th>Details (if selected)</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>JIT / PIM Privileged Access</strong><br/>(TSA-IDN-01)</td>
      <td>Any workload requiring elevated/admin access to cloud resources</td>
      <td>&#9744; Yes</td>
      <td><em>Roles needing JIT, approval workflow, max session duration</em></td>
    </tr>
    <tr>
      <td><strong>Identity Lifecycle Management (JML)</strong><br/>(TSA-IDN-02)</td>
      <td>Workloads where Joiner/Mover/Leaver process must auto-provision/deprovision access</td>
      <td>&#9744; Yes</td>
      <td><em>HR system integration, SCIM groups, deprovisioning SLA</em></td>
    </tr>
  </tbody>
</table>

<hr />

<h2>12. Auto-Generated Diagrams (Placeholder)</h2>

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
  <thead><tr><th>Layer</th><th>Pattern(s) Selected</th><th>AWS / Azure Service(s)</th></tr></thead>
  <tbody>
    <tr><td>Infrastructure — Landing Zone</td><td>UKHSA-INF-01</td><td></td></tr>
    <tr><td>Infrastructure — Connectivity</td><td></td><td></td></tr>
    <tr><td>Infrastructure — Zero Trust Access</td><td></td><td></td></tr>
    <tr><td>Infrastructure — DNS</td><td></td><td></td></tr>
    <tr><td>Infrastructure — Identity</td><td>UKHSA-INF-05</td><td></td></tr>
    <tr><td>Infrastructure — Platform</td><td></td><td></td></tr>
    <tr><td>Networking (TSA)</td><td></td><td></td></tr>
    <tr><td>Identity (TSA)</td><td></td><td></td></tr>
    <tr><td>Ingestion</td><td></td><td></td></tr>
    <tr><td>Processing</td><td></td><td></td></tr>
    <tr><td>Storage</td><td></td><td></td></tr>
    <tr><td>Governance</td><td></td><td></td></tr>
    <tr><td>Security (mandatory)</td><td>6A, 6B, 6C</td><td>IAM, KMS, VPC, WAF</td></tr>
    <tr><td>Monitoring</td><td></td><td></td></tr>
    <tr><td>Resilience</td><td></td><td></td></tr>
  </tbody>
</table>

<hr />

<h2>13. Related Documents</h2>

<ul>
  <li><a href="#">High-level Design (HLD) Solution Architecture Template</a> (main page)</li>
  <li>UKHSA Cloud Strategy & Approved patterns.md (pattern reference - download from the HLD page)</li>
  <li><a href="#">Low Level Design (LLD)</a> (for detailed component specs)</li>
  <li><a href="#">Architectural Decision Records</a> (ADRs for decisions)</li>
</ul>
"""


def main():
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    main_page_title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "High-level Design (HLD) Solution Architecture Template")

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
