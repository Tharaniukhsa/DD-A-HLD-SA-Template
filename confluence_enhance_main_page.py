import html
import json
import os
import sys
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
    result = data["results"][0] if "results" in data else data
    print(f"  Uploaded attachment: {filename}")
    return result


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

  def _panel(macro: str, title: str, body: str) -> str:
    return (
      f'<ac:structured-macro ac:name="{macro}">'
      f'<ac:parameter ac:name="title">{title}</ac:parameter>'
      f"<ac:rich-text-body>{body}</ac:rich-text-body>"
      "</ac:structured-macro>"
    )

  def _pattern_card(tag: str, name: str, plain_english: str, use_when: str,
                    services: list[str], security_note: str, example: str) -> str:
    svc_pills = "".join(f"<code>{s}</code>&nbsp; " for s in services)
    return (
      f"<h3>{tag}: {name}</h3>"
      f'<ac:structured-macro ac:name="info">'
      f'<ac:parameter ac:name="title">What is this?</ac:parameter>'
      f"<ac:rich-text-body><p>{plain_english}</p></ac:rich-text-body>"
      "</ac:structured-macro>"
      "<table><colgroup>"
      '<col style="width:20%;" /><col style="width:80%;" />'
      "</colgroup><tbody>"
      f"<tr><th>Use when</th><td>{use_when}</td></tr>"
      f"<tr><th>AWS services</th><td>{svc_pills}</td></tr>"
      f"<tr><th>Security note</th><td>{security_note}</td></tr>"
      f"<tr><th>Real-world example</th><td><em>{example}</em></td></tr>"
      "</tbody></table><p><br /></p>"
    )

  # ── intro ──────────────────────────────────────────────────────────────────
  intro = (
    "<h1>UKHSA Cloud Strategy & Approved Patterns</h1>"
    "<p>This page describes the building blocks your solution can be made from. "
    "Each <strong>pattern</strong> is a proven, approved way of solving a common "
    "data problem at UKHSA. Think of them like LEGO bricks — you pick the right "
    "bricks for your project and snap them together.</p>"
    + _panel("warning", "Who is this page for?",
             "<p>This page is written for <strong>everyone</strong> — not just technical staff. "
             "You do not need to understand AWS to read it. "
             "Use it when you are choosing patterns in Section&nbsp;8 of the Solution Architecture page.</p>")
  )

  # ── layer 1: ingestion ─────────────────────────────────────────────────────
  s1 = (
    "<h2>Layer 1 — Getting Data In (Ingestion)</h2>"
    "<p>Before anything else can happen, data must arrive in the system. "
    "These patterns describe the four approved ways data can be brought in.</p>"
    + _pattern_card(
      "1A", "Direct API Ingestion",
      "Think of this like a tap that is always on. External systems send data directly "
      "to UKHSA in real time — the moment something happens, the data flows in. "
      "AWS API Gateway acts as the front door; SQS is a queue that holds messages "
      "while they wait to be processed, so nothing is lost even if processing is slow.",
      "You need data <strong>immediately</strong> as it is created — e.g. live case notifications, real-time feeds.",
      ["API Gateway", "SQS", "EventBridge", "Lambda"],
      "All connections are authenticated (OAuth 2.0 / mTLS). Access is locked down to approved IP addresses.",
      "NHS hospital systems sending daily admission updates",
    )
    + _pattern_card(
      "1B", "Batch File Upload",
      "Think of this like a filing cabinet delivery. Someone sends a big file "
      "(e.g. a monthly spreadsheet or CSV) and it lands in a secure S3 'inbox'. "
      "AWS Glue then catalogues it — recording what the file contains — so it can "
      "be found and processed later.",
      "Data arrives in <strong>bulk at scheduled times</strong> — e.g. monthly reports, historical exports.",
      ["S3", "AWS Glue", "DataSync", "Transfer Family (SFTP)"],
      "Files are encrypted the moment they land. Bucket policies prevent unauthorised access. Versioning keeps a history of every file.",
      "Monthly epidemiological reports from regional health authorities",
    )
    + _pattern_card(
      "1C", "Database Replication",
      "Think of this like a live carbon copy. A database somewhere else (e.g. a legacy "
      "UKHSA operational system) continuously mirrors its changes into the AWS environment. "
      "AWS DMS (Database Migration Service) handles the mirroring automatically.",
      "You need to keep an <strong>existing database in sync</strong> — e.g. legacy operational system read replicas.",
      ["DMS", "RDS", "Aurora", "S3"],
      "Connections run over private, encrypted network paths. Every change is logged for audit.",
      "Real-time sync from UKHSA operational databases",
    )
    + _pattern_card(
      "1D", "Streaming Ingestion",
      "Think of this like a live news ticker. Data arrives in a continuous, "
      "high-speed stream — thousands of tiny messages per second. "
      "Amazon Kinesis is a motorway for data; MSK (Kafka) is used when "
      "the routing rules become complex.",
      "You have <strong>very high frequency, continuous data</strong> — e.g. sensor readings, live surveillance.",
      ["Kinesis Data Streams", "MSK (Kafka)", "Lambda", "Timestream"],
      "Each consumer application has its own IAM role (identity), so one system cannot read another's data.",
      "Real-time disease surveillance data from testing labs",
    )
  )

  # ── layer 2: processing ────────────────────────────────────────────────────
  s2 = (
    "<h2>Layer 2 — Cleaning &amp; Transforming Data (Processing)</h2>"
    "<p>Raw data is rarely ready to use. These patterns describe approved ways "
    "to clean, enrich, and reshape data before it is stored or analysed.</p>"
    + _pattern_card(
      "2A", "Batch ETL",
      "ETL stands for Extract, Transform, Load. Think of it like a night-shift "
      "factory: a big job runs on a schedule (daily, weekly), picks up all the "
      "raw data, cleans and reshapes it, then loads it into the destination. "
      "AWS Glue is the factory; Step Functions is the foreman that keeps everything in order.",
      "You have <strong>large volumes to process on a schedule</strong> — e.g. nightly data normalisation.",
      ["AWS Glue", "Step Functions", "DataBrew", "Glue DataCatalog"],
      "Each Glue job runs under its own identity (IAM role) with only the permissions it needs.",
      "Daily deduplication, validation, and normalisation of lab results",
    )
    + _pattern_card(
      "2B", "Real-time Stream Processing",
      "Think of this like a live analyst watching a dashboard and flagging anomalies "
      "instantly. Data is processed the moment it arrives — no waiting for a batch job. "
      "Kinesis Data Analytics can run SQL queries on a live stream; Lambda handles "
      "simple one-step transformations.",
      "You need <strong>instant decisions or alerts</strong> based on incoming data.",
      ["Kinesis Data Analytics", "Lambda", "EMR"],
      "Runs in an isolated VPC. All traffic is encrypted. Alerts fire to monitored channels.",
      "Real-time epidemiological alert when a threshold is breached",
    )
    + _pattern_card(
      "2C", "Scheduled Spark / ML Jobs",
      "Think of this like a data science lab that opens once a week. Complex statistical "
      "or machine-learning jobs run on a schedule using EMR (a managed Spark cluster) "
      "or SageMaker. When the job finishes the cluster shuts itself down — no wasted cost.",
      "You need <strong>heavy-duty analytics, ML models, or statistical analysis</strong> on large datasets.",
      ["EMR", "SageMaker", "Step Functions", "S3"],
      "Clusters auto-terminate after use. Data is encrypted with KMS keys. Spark security enabled.",
      "Monthly predictive disease modelling",
    )
    + _pattern_card(
      "2D", "Federated Query",
      "Think of this like asking a question that simultaneously searches several filing "
      "cabinets without moving anything. Athena lets you query data sitting in S3, "
      "RDS, and DynamoDB all at once — without copying it first.",
      "You need to <strong>query across multiple data stores</strong> without consolidating the data.",
      ["Athena", "Redshift Spectrum", "Glue Catalog"],
      "Column-level encryption. Query results are encrypted. Runs via VPC endpoints.",
      "Cross-dataset epidemiological query without data movement",
    )
  )

  # ── layer 3: storage ───────────────────────────────────────────────────────
  s3 = (
    "<h2>Layer 3 — Storing Data (Storage)</h2>"
    "<p>Different problems need different storage types — like choosing between "
    "a notebook, a filing cabinet, and a warehouse. Here are the five approved options.</p>"
    + _pattern_card(
      "3A", "Transactional Database (OLTP)",
      "This is your operational day-to-day database — like the till system in a shop. "
      "It handles lots of small read/write operations simultaneously and guarantees "
      "accuracy (ACID compliance). Aurora PostgreSQL is the preferred choice.",
      "You need a database for <strong>live, operational data</strong> with many simultaneous users.",
      ["Aurora PostgreSQL", "RDS PostgreSQL", "DynamoDB"],
      "Encrypted at rest (KMS) and in transit (SSL). IAM authentication. Daily automated backups, 35-day retention.",
      "Patient records, lab results, real-time case dashboards",
    )
    + _pattern_card(
      "3B", "Data Warehouse (OLAP)",
      "Think of this like a very large spreadsheet optimised for complex questions "
      "across years of history. Redshift can hold petabytes of data and answer "
      "questions like 'What was the infection trend over the last 5 years?' very fast.",
      "You need <strong>historical reporting and business intelligence</strong> at scale.",
      ["Redshift", "Redshift Spectrum", "QuickSight"],
      "Column-level security. Encrypted with KMS. SAML authentication (Entra ID). Query monitoring.",
      "Annual disease surveillance reports, multi-year trend analysis",
    )
    + _pattern_card(
      "3C", "Data Lake (S3 Bronze / Silver / Gold)",
      "Think of this like a three-floor archive. Raw, untouched data lands on the "
      "ground floor (Bronze). It gets cleaned and moves to the first floor (Silver). "
      "Fully validated, business-ready data lives on the top floor (Gold). "
      "You only promote data upwards when it meets quality standards.",
      "You have <strong>mixed / unstructured data</strong> or need a flexible exploratory store.",
      ["S3", "Glue Catalog", "Lake Formation", "Athena"],
      "Bucket policies. Object-level encryption. Tag-based access control. Lifecycle policies.",
      "Genomic data, unstructured epidemiological documents",
    )
    + _pattern_card(
      "3D", "Time-Series Database",
      "Think of this like a graph that records a reading every second. "
      "Timestream is purpose-built for metrics that change over time — "
      "it stores and queries time-stamped data far more efficiently than a normal database.",
      "You have <strong>sensor readings, metrics, or surveillance data</strong> captured over time.",
      ["Timestream", "DynamoDB with TTL"],
      "Encryption, VPC endpoints, IAM. Configurable archival to S3 after a set period.",
      "Real-time infection rate monitoring, lab capacity tracking",
    )
    + _pattern_card(
      "3E", "Document Store",
      "Think of this like a folder of JSON documents rather than a structured spreadsheet. "
      "DynamoDB is serverless and scales automatically; DocumentDB is used when the "
      "queries are complex. OpenSearch adds full-text search on top.",
      "You have <strong>nested, variable-structure data</strong> — e.g. incident reports, investigation records.",
      ["DynamoDB", "DocumentDB", "OpenSearch"],
      "Encryption. Point-in-time recovery. IAM fine-grained access control.",
      "Epidemiological investigation records, incident reports",
    )
  )

  # ── layer 4: integration ───────────────────────────────────────────────────
  s4 = (
    "<h2>Layer 4 — Moving Data Between Systems (Integration)</h2>"
    "<p>Getting data from one place to another reliably — these patterns keep systems "
    "loosely coupled so one failure does not bring everything down.</p>"
    + _pattern_card(
      "4A", "Event-Driven Pipelines",
      "Think of this like an office announcement board. When something happens "
      "(e.g. a new file arrives), EventBridge shouts about it. Any downstream "
      "system that cares can listen and react — without the sender needing to "
      "know who is listening. Systems stay independent of each other.",
      "You want systems to react to events <strong>without tight coupling</strong> between them.",
      ["EventBridge", "SQS", "SNS", "Lambda"],
      "IAM policies per consumer. Encryption in transit.",
      "Trigger downstream processing when new surveillance data arrives",
    )
    + _pattern_card(
      "4B", "ETL Orchestration (Step Functions / Airflow)",
      "Think of this like a workflow manager with a checklist. Step Functions "
      "coordinates multi-step data pipelines — it knows which job to run next, "
      "handles retries if something fails, and keeps a visual audit trail.",
      "You have a <strong>complex multi-step pipeline</strong> with dependencies between jobs.",
      ["Step Functions", "MWAA (Airflow)", "EventBridge"],
      "IAM role per workflow. Cross-account execution policies.",
      "Daily pipeline: ingest → transform → validate → publish",
    )
    + _pattern_card(
      "4C", "Data Replication &amp; Sync",
      "Think of this like keeping two whiteboards identical in two rooms. "
      "S3 Cross-Region Replication, RDS Read Replicas, and DataSync ensure "
      "a copy of data exists in a second location for resilience or compliance.",
      "You need <strong>high availability or data residency compliance</strong> across regions.",
      ["S3 replication", "RDS Read Replicas", "DataSync"],
      "Encryption in transit. Cross-account roles. Audit logging.",
      "Replicate processed data to secondary region for resilience",
    )
  )

  # ── layer 5: governance ────────────────────────────────────────────────────
  s5 = (
    "<h2>Layer 5 — Knowing What You Have (Governance &amp; Cataloguing)</h2>"
    "<p>These patterns answer the question: <em>What data do we hold, where is it, "
    "who owns it, and is it good quality?</em></p>"
    + _pattern_card(
      "5A", "Centralised Data Catalogue",
      "Think of this like a library catalogue for all UKHSA datasets. "
      "AWS Glue Catalog records the name, owner, schema, sensitivity level, and "
      "lineage of every dataset. Lake Formation sits on top to enforce who can "
      "see what — down to individual columns.",
      "You need to <strong>discover, document, and govern</strong> datasets across the organisation.",
      ["Glue Catalog", "Lake Formation"],
      "Tag-based access control. Sensitivity levels enforced at query time.",
      "Centralised register of all epidemiological datasets",
    )
    + _pattern_card(
      "5B", "Data Quality &amp; Validation",
      "Think of this like a quality-control inspector on a production line. "
      "Before data moves to the next stage it must pass checks: "
      "Are there nulls? Are values in the expected range? Are there duplicates? "
      "Glue DataBrew provides a visual rule builder — no coding required.",
      "You need to <strong>prevent bad data from spreading</strong> downstream.",
      ["Glue DataBrew", "Glue quality checks", "EventBridge (failure alerts)"],
      "Validation failures trigger alerts. Rules are versioned and auditable.",
      "Validate lab results are within expected clinical ranges before storing",
    )
    + _pattern_card(
      "5C", "Data Lineage &amp; Audit Trail",
      "Think of this like a passport stamp for every piece of data — you can "
      "trace exactly where it came from, every transformation it went through, "
      "and who accessed it. This is essential for GDPR compliance and incident investigation.",
      "You need to <strong>prove data provenance</strong> or meet compliance audit requirements.",
      ["Lake Formation lineage", "Glue Catalog", "CloudTrail", "S3 access logs"],
      "Immutable audit logs in CloudTrail. Access logs retained per policy.",
      "Audit trail for sensitive epidemiological data — who accessed it and when",
    )
  )

  # ── layer 6: security ──────────────────────────────────────────────────────
  s6 = (
    "<h2>Layer 6 — Keeping Data Safe (Security &amp; Compliance)</h2>"
    "<p>These patterns are <strong>mandatory for all solutions</strong>. They are not optional extras.</p>"
    + _pattern_card(
      "6A", "Access Control (IAM + Entra ID)",
      "Think of this like a building with key-card access. Every person and every "
      "system gets only the keys they need — nothing more. UKHSA uses Entra ID (Azure AD) "
      "as the identity provider, linked to AWS IAM. Temporary credentials (STS) "
      "mean keys expire automatically — no permanent passwords.",
      "<strong>Always required.</strong> Governs who can access which data.",
      ["IAM", "Entra ID / Azure AD", "Lake Formation (column security)", "S3 Object Lock"],
      "Role-based access. MFA enforced. Attribute-based control (department, sensitivity level). Temporary credentials only.",
      "Data analysts can query public datasets but cannot see sensitive patient-level data",
    )
    + _pattern_card(
      "6B", "Encryption &amp; Key Management",
      "Think of this like a combination lock that only you know. "
      "All UKHSA data must be encrypted at rest (when stored) and in transit (when moving). "
      "AWS KMS manages the encryption keys — UKHSA holds customer-managed keys, "
      "meaning AWS cannot read the data without UKHSA's permission.",
      "<strong>Always required.</strong> Mandatory for sensitive and restricted data.",
      ["KMS (customer-managed keys)", "Secrets Manager", "ACM (certificates)"],
      "AES-256 at rest. TLS 1.2+ in transit. Keys are backed up cross-region.",
      "All S3 buckets encrypted with UKHSA-owned KMS keys",
    )
    + _pattern_card(
      "6C", "Network Security &amp; Isolation",
      "Think of this like putting the data centre in a locked room inside a locked building. "
      "All data processing runs inside a private VPC (Virtual Private Cloud) with no "
      "direct internet access. Traffic to AWS services goes through private endpoints "
      "so it never touches the public internet.",
      "<strong>Always required.</strong> No processing in public subnets.",
      ["VPC", "Security Groups", "VPC Endpoints", "PrivateLink", "WAF"],
      "Private subnets only. No internet access (NAT gateway for outbound only). Logs to isolated CloudWatch.",
      "Data processing pipeline running in fully isolated VPC",
    )
    + _pattern_card(
      "6D", "Data Masking &amp; Anonymisation",
      "Think of this like redacting a document before sharing it. "
      "Before data is shared with researchers or external teams, "
      "personal identifiers are removed, generalised (e.g. age bands instead of DOB), "
      "or replaced with tokens. This satisfies GDPR and DPIA requirements.",
      "Required whenever <strong>PII or sensitive data</strong> is shared outside the originating system.",
      ["Glue DataBrew", "Lambda (custom masking)", "RDS dynamic masking", "Redshift row-level security"],
      "Pseudonymisation, generalisation, aggregation, or redaction applied before data leaves secure boundary.",
      "Remove patient names and NHS numbers before sharing data with research teams",
    )
  )

  # ── layer 7: monitoring ────────────────────────────────────────────────────
  s7 = (
    "<h2>Layer 7 — Watching What Happens (Monitoring &amp; Observability)</h2>"
    "<p>You cannot fix what you cannot see. These patterns ensure the system is "
    "observable and problems are caught early.</p>"
    + _pattern_card(
      "7A", "Centralised Logging",
      "Think of this like a CCTV recording of everything the system does. "
      "CloudWatch Logs collects logs from every component in one place. "
      "CloudTrail records every API call — who did what, when, from where. "
      "This is the foundation for debugging, compliance auditing, and incident response.",
      "<strong>Always required.</strong> Needed for debugging and compliance.",
      ["CloudWatch Logs", "CloudTrail", "VPC Flow Logs", "S3 access logs"],
      "Logs are immutable. Retention periods set per policy. Access to logs is restricted.",
      "Track each data load: rows in, rows out, duration, error count",
    )
    + _pattern_card(
      "7B", "Data Quality Monitoring",
      "Think of this like a smoke detector for your data. "
      "Automated checks run continuously — if data stops arriving on time, "
      "or the number of records drops unexpectedly, an alert fires to the team. "
      "CloudWatch custom metrics track freshness, completeness, and accuracy.",
      "Required whenever <strong>data freshness or quality SLAs</strong> must be met.",
      ["CloudWatch (custom metrics)", "EventBridge", "SNS", "Lambda"],
      "Alert thresholds defined and documented. On-call routing configured.",
      "Alert if daily lab data has not arrived by 10:00 AM",
    )
    + _pattern_card(
      "7C", "Performance &amp; Cost Monitoring",
      "Think of this like a fuel gauge on your car. "
      "Cost Explorer tracks how much each part of the solution is spending. "
      "Compute Optimizer recommends cheaper instance sizes. "
      "CloudWatch tracks query times and resource utilisation.",
      "Required for <strong>cost governance and performance optimisation</strong>.",
      ["CloudWatch", "Cost Explorer", "Compute Optimizer", "Trusted Advisor"],
      "Cost budgets set with alerts. Unused resources flagged weekly.",
      "Track cost per epidemiological query; identify and optimise expensive jobs",
    )
  )

  # ── layer 8: resilience ────────────────────────────────────────────────────
  s8 = (
    "<h2>Layer 8 — Surviving Failure (Resilience &amp; Disaster Recovery)</h2>"
    "<p>Things go wrong. These patterns ensure data is not lost and services recover quickly.</p>"
    + _panel("info", "RPO and RTO — what do these mean?",
             "<p><strong>RPO (Recovery Point Objective)</strong> — How much data can we afford to lose? "
             "An RPO of 1 hour means in the worst case you lose 1 hour of data.</p>"
             "<p><strong>RTO (Recovery Time Objective)</strong> — How quickly must the service be back up? "
             "An RTO of 4 hours means the service must be restored within 4 hours of a failure.</p>")
    + _pattern_card(
      "8A", "Backup Strategy",
      "Think of this like taking a daily photograph of your data. "
      "AWS Backup coordinates automated daily backups of RDS databases, S3 buckets, "
      "and EC2 volumes — all in one place. Backups are copied to a second region "
      "so a regional outage does not cause data loss.",
      "Required for <strong>all production data</strong>. Criticality level determines retention.",
      ["RDS automated backups", "S3 Cross-Region Replication", "AWS Backup", "Snapshots"],
      "Backup jobs monitored. Restore tested quarterly. Cross-region copies encrypted.",
      "Daily backup of epidemiological database, replicated to Ireland (eu-west-1)",
    )
    + _pattern_card(
      "8B", "Multi-AZ / Multi-Region Deployment",
      "Think of this like having two offices — if one floods, the other keeps running. "
      "Multi-AZ means the database has a hot standby in a different data centre within "
      "the same region. Multi-Region means a full copy in a second UK-approved region.",
      "Required for <strong>critical services</strong> where downtime is unacceptable.",
      ["Multi-AZ RDS", "S3 Cross-Region Replication", "Route 53 failover", "Global Accelerator"],
      "Primary: eu-west-2 (London). Secondary: eu-west-1 (Ireland). Data residency maintained within UK/EEA.",
      "Main database in London with automatic failover to Ireland read replica",
    )
  )

  # ── ADRs ───────────────────────────────────────────────────────────────────
  adrs = (
    "<h2>Architecture Decision Records (ADRs)</h2>"
    "<p>These are firm decisions that apply to <strong>all</strong> UKHSA data solutions. "
    "You do not need to re-justify these — they are already decided.</p>"
    "<table><thead><tr><th>ADR</th><th>Decision</th><th>Why</th></tr></thead><tbody>"
    "<tr><td>ADR-001</td><td>Use PostgreSQL (not MySQL) for new OLTP systems</td><td>Better JSON support, window functions, standards compliance</td></tr>"
    "<tr><td>ADR-002</td><td>Use S3 + Glue instead of HDFS for data lakes</td><td>Serverless — no cluster to manage, lower cost, simpler</td></tr>"
    "<tr><td>ADR-003</td><td>Prefer Redshift Spectrum over Athena for queries on datasets &gt;100 GB</td><td>Significantly better performance at large scale</td></tr>"
    "<tr><td>ADR-004</td><td>Use EventBridge over SNS/SQS for event orchestration</td><td>Built-in schema validation, event routing without code, better observability</td></tr>"
    "<tr><td>ADR-005</td><td>All data in transit must use TLS 1.2 or higher</td><td>Mandatory per UKHSA security standards</td></tr>"
    "<tr><td>ADR-006</td><td>Customer-managed KMS keys required for sensitive data</td><td>GDPR and Data Protection Act compliance — UKHSA must hold its own keys</td></tr>"
    "<tr><td>ADR-007</td><td>All data lakes must use the Bronze / Silver / Gold three-zone model</td><td>Enforces data quality gates, traceability, and governance</td></tr>"
    "</tbody></table>"
  )

  # ── quick-pick cheat sheet ─────────────────────────────────────────────────
  cheat = (
    "<h2>Quick-Pick Cheat Sheet</h2>"
    "<p>Not sure which pattern to pick? Use this table as a starting point.</p>"
    "<table><thead><tr>"
    "<th>If you need to…</th><th>Start with this pattern</th>"
    "</tr></thead><tbody>"
    "<tr><td>Receive data from an external API in real time</td><td>1A — Direct API Ingestion</td></tr>"
    "<tr><td>Accept a large file upload from a partner</td><td>1B — Batch File Upload</td></tr>"
    "<tr><td>Mirror a legacy database into AWS</td><td>1C — Database Replication</td></tr>"
    "<tr><td>Ingest thousands of sensor readings per second</td><td>1D — Streaming Ingestion</td></tr>"
    "<tr><td>Run nightly data cleaning and transformation</td><td>2A — Batch ETL</td></tr>"
    "<tr><td>Detect anomalies the moment data arrives</td><td>2B — Real-time Stream Processing</td></tr>"
    "<tr><td>Train a machine learning model</td><td>2C — Scheduled Spark / ML Jobs</td></tr>"
    "<tr><td>Query several databases without moving data</td><td>2D — Federated Query</td></tr>"
    "<tr><td>Store operational, live-query data</td><td>3A — Transactional Database</td></tr>"
    "<tr><td>Run complex reports across years of history</td><td>3B — Data Warehouse</td></tr>"
    "<tr><td>Store raw and mixed-format data flexibly</td><td>3C — Data Lake (Bronze/Silver/Gold)</td></tr>"
    "<tr><td>Store time-stamped metrics or sensor data</td><td>3D — Time-Series Database</td></tr>"
    "<tr><td>Store JSON documents or event logs</td><td>3E — Document Store</td></tr>"
    "<tr><td>Trigger downstream systems when data arrives</td><td>4A — Event-Driven Pipelines</td></tr>"
    "<tr><td>Coordinate a multi-step data pipeline</td><td>4B — ETL Orchestration</td></tr>"
    "<tr><td>Keep two regions in sync for resilience</td><td>4C — Data Replication &amp; Sync</td></tr>"
    "</tbody></table>"
  )

  return (
    intro + s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8 + adrs + cheat
    + f'<p><br /><em>Source file: <a href="{source_download_link}">UKHSA Cloud Strategy & Approved patterns.md</a></em></p>'
  )


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
<div style="background-color: #f0f4f8; border: 2px solid #003366; border-radius: 8px; padding: 20px; margin: 20px 0;">
  <h2 style="color: #003366; margin-top: 0;">📑 Table of Contents</h2>
  <div style="column-count: 2; column-gap: 30px;">
    <strong style="color: #0052CC;">Discovery Phase:</strong>
    <ul style="margin-top: 5px;">
      <li><a href="#section1">1. Solution Overview</a></li>
      <li><a href="#section2">2. Introduction</a></li>
      <li><a href="#section3">3. Background</a></li>
      <li><a href="#section4">4. Pain Points / Problem Statement</a></li>
      <li><a href="#section5">5. Functional Requirements</a></li>
      <li><a href="#section6">6. Non-Functional Requirements</a></li>
    </ul>
    <strong style="color: #0052CC;">Design Phase:</strong>
    <ul style="margin-top: 5px;">
      <li><a href="#section7">7. Architecture Decision – HLD Options</a></li>
      <li><a href="#section8">8. Pattern Selection</a></li>
      <li><a href="#section9">9. Context Entities</a></li>
      <li><a href="#section10">10. Architecture Components</a></li>
      <li><a href="#section11">11. Architecture Connections</a></li>
      <li><a href="#section12">12. Data Flow Entries</a></li>
      <li><a href="#section13">13. Dataset Inventory</a></li>
    </ul>
    <strong style="color: #0052CC;">Delivery Phase:</strong>
    <ul style="margin-top: 5px;">
      <li><a href="#section14">14. Auto-Generated Diagrams</a></li>
      <li><a href="#section15">15. Low-Level Design (LLD) Summary</a></li>
      <li><a href="#section16">16. Solution Option Cost Comparison</a></li>
      <li><a href="#section17">17. Implementation Handover</a></li>
    </ul>
  </div>
</div>

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
<p><em>Run <code>confluence_update_diagrams.py</code> after completing the tables above. All diagrams are editable in draw.io.</em></p>

<h3>14.1 Context View</h3>
<p><strong>[[DIAGRAM:context-view]]</strong></p>

<h3>14.2 Logical View</h3>
<p><strong>[[DIAGRAM:logical-view]]</strong></p>

<h3>14.3 Solution Architecture</h3>
<p><strong>[[DIAGRAM:solution-architecture]]</strong></p>

<h3>14.4 Data Flow Diagram</h3>
<p><strong>[[DIAGRAM:data-flow]]</strong></p>

<h3>14.5 Dataset Relationship Diagram</h3>
<p><strong>[[DIAGRAM:data-relationship]]</strong></p>

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


def main() -> None:
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "Solution Architecture")

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    print(f"Finding main page '{title}'...")
    page = find_page_by_title(session, base_url, space_key, title)
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
    body_html = build_main_html(plan_link)
    result = update_page_body(session, base_url, page_id, page["version"]["number"], page["title"], body_html)

    links = result.get("_links", {})
    page_url = f"{links.get('base', base_url)}{links.get('webui', '')}"
    print(f"Done: {page_url}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
