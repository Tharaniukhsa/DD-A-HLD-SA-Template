"""
confluence_update_diagrams.py
─────────────────────────────
Reads the "Architecture Components", "Architecture Connections", and
"Data Flow Entries" tables from your Solution Architecture Confluence page,
generates Draw.io diagrams, uploads them as page attachments, and embeds
them back into the page via the draw.io Confluence macro.

Prerequisites
─────────────
• The draw.io (diagrams.net) app must be installed in your Confluence Cloud
  instance (most enterprise instances already have it).
• Fill in the Architecture Components, Connections, and Data Flow Entries
  tables on the Confluence page first.
• Optionally set CONFLUENCE_ARCHITECTURE_PAGE_ID in .env to skip the
  title search and point directly at the page.

Workflow
────────
  1. Run confluence_create_architecture_pages.py  →  creates the template page
  2. Fill in the tables on Confluence
  3. Run this script  →  diagrams appear in the page automatically
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from io import BytesIO

from bs4 import BeautifulSoup
import certifi
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from requests_negotiate_sspi import HttpNegotiateAuth

# Import EDAP knowledge base for automatic EDAP-integration diagram enrichment
try:
    from edap_knowledge_base import (
        detect_edap_patterns,
        inject_edap_into_components,
        inject_edap_into_connections,
        inject_edap_into_dataflows,
        inject_edap_into_context_entities,
        build_edap_integration_summary,
    )
    EDAP_KB_AVAILABLE = True
except ImportError:
    EDAP_KB_AVAILABLE = False

# Import UKHSA Patterns knowledge base (all UKHSA-approved patterns: INF, data, TSA)
try:
    from ukhsa_patterns_knowledge_base import (
        detect_ukhsa_patterns,
        inject_ukhsa_into_components,
        inject_ukhsa_into_connections,
        inject_ukhsa_into_dataflows,
        inject_ukhsa_into_context_entities,
        build_ukhsa_pattern_summary,
        get_mandatory_controls_for_patterns,
    )
    UKHSA_KB_AVAILABLE = True
except ImportError:
    UKHSA_KB_AVAILABLE = False

# Import AWS architecture diagram generator with real icons
try:
    from aws_architecture_diagram_generator import (
        generate_aws_architecture_with_real_icons,
        generate_detailed_network_diagram,
        generate_authentication_flow_diagram,
        generate_network_segregation_diagram,
    )
    AWS_DIAGRAMS_AVAILABLE = True
except ImportError:
    AWS_DIAGRAMS_AVAILABLE = False

load_dotenv()


# ── Auth & TLS ─────────────────────────────────────────────────────────────

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
    base_headers = dict(kwargs.pop("headers", {}) or {})

    def _request_with_retry(req_headers: dict, req_auth=None) -> requests.Response:
        """Retry once with Connection: close on transient SSL EOF errors."""
        try:
            return session.request(method, url, verify=verify, headers=req_headers, auth=req_auth, **kwargs)
        except requests.exceptions.SSLError as exc:
            if "UNEXPECTED_EOF_WHILE_READING" not in str(exc):
                raise
            retry_headers = dict(req_headers)
            retry_headers["Connection"] = "close"
            return session.request(method, url, verify=verify, headers=retry_headers, auth=req_auth, **kwargs)

    # Try Bearer auth first if we have a token.
    if api_token:
        bearer_headers = dict(base_headers)
        bearer_headers["Authorization"] = f"Bearer {api_token}"
        try:
            resp = _request_with_retry(bearer_headers, req_auth=None)
            if resp.status_code != 403:
                return resp
        except requests.RequestException:
            pass

    # Fallback to Basic auth if we have email + token.
    if user_email and api_token:
        return _request_with_retry(base_headers, req_auth=HTTPBasicAuth(user_email, api_token))

    # Last resort: use session as-is.
    return _request_with_retry(base_headers, req_auth=None)


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


def _json_headers() -> dict:
    return {"Accept": "application/json", "Content-Type": "application/json"}


def _accept_headers() -> dict:
    return {"Accept": "application/json"}


def find_page_by_title(session: requests.Session, base_url: str,
                        space_key: str, title: str) -> dict:
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


def get_page_by_id(session: requests.Session, base_url: str, page_id: str) -> dict:
    resp = _make_request(
        session, "GET",
        f"{base_url}/rest/api/content/{page_id}",
        params={"expand": "body.storage,version"},
        headers=_accept_headers(),
        verify=get_tls_verify(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def upload_attachment(session: requests.Session, base_url: str,
                      page_id: str, filename: str, xml_content: str) -> None:
    """Upload a .drawio file as a page attachment, replacing it if it already exists."""
    url = f"{base_url}/rest/api/content/{page_id}/child/attachment"
    file_bytes = xml_content.encode("utf-8")

    # Check for existing attachment to update instead of duplicate
    check = _make_request(
        session, "GET",
        url,
        params={"filename": filename},
        headers=_accept_headers(),
        verify=get_tls_verify(),
        timeout=30,
    )
    existing = check.json().get("results", []) if check.status_code == 200 else []

    def _make_files_payload():
        return {"file": (filename, BytesIO(file_bytes), "application/octet-stream")}
    
    # Use direct session for file uploads (auth fallback handled via headers)
    api_token = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    verify = get_tls_verify()
    
    upload_url = f"{url}/{existing[0]['id']}/data" if existing else url
    original_content_type = session.headers.pop("Content-Type", None)

    def _post_upload(req_headers: dict, req_auth=None) -> requests.Response:
        try:
            return session.post(
                upload_url,
                files=_make_files_payload(),
                headers=req_headers,
                auth=req_auth,
                verify=verify,
                timeout=30,
            )
        except requests.exceptions.SSLError as exc:
            if "UNEXPECTED_EOF_WHILE_READING" not in str(exc):
                raise
            retry_headers = dict(req_headers)
            retry_headers["Connection"] = "close"
            return session.post(
                upload_url,
                files=_make_files_payload(),
                headers=retry_headers,
                auth=req_auth,
                verify=verify,
                timeout=30,
            )

    try:
        # Try Bearer auth first.
        if api_token:
            bearer_headers = {"Authorization": f"Bearer {api_token}", "X-Atlassian-Token": "no-check"}
            try:
                resp = _post_upload(bearer_headers, req_auth=None)
                if resp.status_code != 403:
                    if resp.status_code not in (200, 201):
                        raise RuntimeError(f"Failed to upload {filename}: {resp.status_code} {resp.text}")
                    print(f"  Uploaded: {filename}")
                    return
            except requests.RequestException:
                pass

        # Fallback to Basic auth.
        if user_email and api_token:
            resp = _post_upload({"X-Atlassian-Token": "no-check"}, req_auth=HTTPBasicAuth(user_email, api_token))
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Failed to upload {filename}: {resp.status_code} {resp.text}")
            print(f"  Uploaded: {filename}")
            return
    finally:
        if original_content_type is not None:
            session.headers["Content-Type"] = original_content_type
    
    raise RuntimeError(f"Failed to upload {filename}: No valid authentication")


def save_local_drawio(filename: str, xml_content: str) -> None:
    """Save editable .drawio sources locally for offline edits/versioning."""
    output_dir = os.path.join("output", "generated")
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"  Local editable source: {file_path}")


def load_local_drawio(filename: str) -> str | None:
    """Load previously generated .drawio source if available."""
    file_path = os.path.join("output", "generated", filename)
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def _diagrams_synced_path() -> str:
    """Path to the synced Architecture Diagrams page template."""
    return "architecture_diagrams_page.synced.html"


def save_diagrams_synced_template(body_html: str) -> None:
    """Save the current Architecture Diagrams page body for future reuse.
    
    This preserves manual edits from Confluence by caching the page structure,
    so we can update only the diagram macros without overwriting user changes.
    """
    synced_path = _diagrams_synced_path()
    with open(synced_path, "w", encoding="utf-8") as f:
        f.write(body_html)
    print(f"  Synced template saved: {synced_path}")


def load_diagrams_synced_template() -> str | None:
    """Load the synced Architecture Diagrams page template if available.
    
    Returns cached page structure from previous run to preserve manual edits.
    """
    synced_path = _diagrams_synced_path()
    if not os.path.exists(synced_path):
        return None
    with open(synced_path, "r", encoding="utf-8") as f:
        return f.read()


def build_default_diagrams_template() -> str:
    """Return a clean, canonical Architecture Diagrams page template."""
    return """<h1>Architecture Diagrams</h1>

<p><em>Auto-generated diagrams from the Solution Architecture design tables. All diagrams are editable in draw.io.</em></p>

<hr/>

<h2>How to Generate Diagrams</h2>
<ol>
<li>Complete the architecture tables in the main <strong>Solution Architecture</strong> page (Sections 10-13b)</li>
<li>Run the diagram generation script: <code>./.venv/Scripts/python.exe ./confluence_update_diagrams.py</code></li>
<li>All diagrams will be auto-generated and embedded below</li>
</ol>

<hr/>

<h2>1. Context View Diagram</h2>
<p><strong>[[DIAGRAM:context-view]]</strong></p>

<h2>2. Logical View Diagram</h2>
<p><strong>[[DIAGRAM:logical-view]]</strong></p>

<h2>3. High-level Architecture Diagram</h2>
<p><strong>[[DIAGRAM:solution-architecture]]</strong></p>

<h2>4. Data Flow Diagram (DFD)</h2>
<p><strong>[[DIAGRAM:data-flow]]</strong></p>

<h2>5. Dataset Relationship Diagram (ERD)</h2>
<p><strong>[[DIAGRAM:data-relationship]]</strong></p>

<h2>6. Authentication Flow Diagram</h2>
<p><strong>[[DIAGRAM:authentication-flow]]</strong></p>

<h2>7. Network Segregation Diagram</h2>
<p><strong>[[DIAGRAM:network-segregation]]</strong></p>

<hr/>

<h2>Local Diagram Files</h2>
<p><strong>Location:</strong> <code>output/generated/</code></p>
"""


def is_valid_diagrams_template(html: str) -> bool:
    """Validate that required diagram placeholders still exist in the template."""
    required_tokens = [
        "[[DIAGRAM:context-view]]",
        "[[DIAGRAM:logical-view]]",
        "[[DIAGRAM:solution-architecture]]",
        "[[DIAGRAM:data-flow]]",
        "[[DIAGRAM:data-relationship]]",
        "[[DIAGRAM:authentication-flow]]",
        "[[DIAGRAM:network-segregation]]",
    ]
    return all(token in html for token in required_tokens)


def update_page_body(session: requests.Session, base_url: str, page_id: str,
                     version_number: int, title: str, body_html: str) -> None:
    payload = {
        "version": {"number": version_number + 1},
        "title": title,
        "type": "page",
        "body": {
            "storage": {
                "value": body_html,
                "representation": "storage",
            }
        },
    }
    r = _make_request(
        session, "PUT",
        f"{base_url}/rest/api/content/{page_id}",
        data=json.dumps(payload),
        headers=_json_headers(),
        verify=get_tls_verify(),
        timeout=30,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Failed to update page: {r.status_code} {r.text}")
    page = r.json()
    links = page.get("_links", {})
    url = f"{links.get('base', base_url)}{links.get('webui', '')}"
    print(f"  Page updated: {url}")


# ── Table Parsing ──────────────────────────────────────────────────────────

def _table_rows(table) -> list[list[str]]:
    """Return all non-header rows as lists of stripped cell text."""
    rows = []
    for i, tr in enumerate(table.find_all("tr")):
        if i == 0:
            continue  # skip header
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if any(cells):
            rows.append(cells)
    return rows


def _find_table_after_heading(soup, heading_text: str):
    """Return the <table> that follows the first heading containing heading_text."""
    for tag in soup.find_all(["h2", "h3", "h4", "h5"]):
        if heading_text.lower() in tag.get_text(strip=True).lower():
            sibling = tag.find_next_sibling()
            while sibling and sibling.name in ("p", "ul", "ol"):
                sibling = sibling.find_next_sibling()
            if sibling and sibling.name == "table":
                return sibling
    return None


def parse_components(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_after_heading(soup, "Architecture Components")
    if not table:
        return []
    components = []
    for row in _table_rows(table):
        name = row[1] if len(row) > 1 else ""
        if not name:
            continue
        components.append({
            "no":          row[0] if len(row) > 0 else "",
            "name":        name,
            "layer":       row[2] if len(row) > 2 else "Application",
            "technology":  row[3] if len(row) > 3 else "",
            "direction":   row[4] if len(row) > 4 else "",
            "description": row[5] if len(row) > 5 else (row[4] if len(row) > 4 else ""),
        })
    return components


def parse_connections(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_after_heading(soup, "Architecture Connections")
    if not table:
        return []
    connections = []
    for row in _table_rows(table):
        frm = row[0] if len(row) > 0 else ""
        to  = row[1] if len(row) > 1 else ""
        if not frm or not to:
            continue
        connections.append({
            "from":  frm,
            "to":    to,
            "label": row[2] if len(row) > 2 else "",
        })
    return connections


def parse_dataflows(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_after_heading(soup, "Data Flow Entries")
    if not table:
        return []
    flows = []
    for row in _table_rows(table):
        source = row[1] if len(row) > 1 else ""
        dest   = row[2] if len(row) > 2 else ""
        if not source or not dest:
            continue
        flows.append({
            "id":       row[0] if len(row) > 0 else "",
            "source":   source,
            "destination": dest,
            "data":     row[3] if len(row) > 3 else "",
            "protocol": row[4] if len(row) > 4 else "",
        })
    return flows


def parse_dataset_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_after_heading(soup, "Dataset Inventory")
    if not table:
        return []
    datasets = []
    for row in _table_rows(table):
        name = row[1] if len(row) > 1 else ""
        if not name:
            continue
        datasets.append(
            {
                "id": row[0] if len(row) > 0 else "",
                "name": name,
                "type": row[2] if len(row) > 2 else "",
                "source_system": row[3] if len(row) > 3 else "",
                "primary_key": row[4] if len(row) > 4 else "",
                "sensitivity": row[5] if len(row) > 5 else "",
                "volume_estimate": row[6] if len(row) > 6 else "",
                "retention": row[7] if len(row) > 7 else "",
            }
        )
    return datasets


def parse_dataset_relationships(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_after_heading(soup, "Dataset Relationships")
    if not table:
        return []
    relationships = []
    for row in _table_rows(table):
        source = row[0] if len(row) > 0 else ""
        target = row[1] if len(row) > 1 else ""
        if not source or not target:
            continue
        relationships.append(
            {
                "source": source,
                "target": target,
                "relation": row[2] if len(row) > 2 else "",
                "mapping": row[3] if len(row) > 3 else "",
            }
        )
    return relationships


def parse_context_entities(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_after_heading(soup, "Context Entities")
    if not table:
        return []
    entities = []
    for row in _table_rows(table):
        name = row[0] if len(row) > 0 else ""
        if not name:
            continue
        entities.append(
            {
                "name": name,
                "type": row[1] if len(row) > 1 else "",
                "interaction": row[2] if len(row) > 2 else "",
                "direction": row[3] if len(row) > 3 else "",
            }
        )
    return entities


def parse_network_segmentation(html: str) -> dict:
    """Parse key network segmentation parameters from the main page table."""
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_after_heading(soup, "Network Segmentation Inputs")
    if not table:
        return {}

    key_map = {
        "vpc cidr": "vpc_cidr",
        "public subnet cidr": "public_subnet_cidr",
        "private subnet cidr": "private_subnet_cidr",
        "data subnet cidr": "data_subnet_cidr",
        "on prem cidr": "on_prem_cidr",
        "on-prem cidr": "on_prem_cidr",
        "connectivity type": "connectivity_type",
        "public ingress path": "public_ingress",
        "private ingress path": "private_ingress",
        "public sg rules": "sg_public_rule",
        "private sg rules": "sg_private_rule",
        "data sg rules": "sg_data_rule",
        "public route": "route_public",
        "private route": "route_private",
    }

    parsed = {}
    for row in _table_rows(table):
        param = (row[0] if len(row) > 0 else "").strip().lower()
        value = (row[1] if len(row) > 1 else "").strip()
        if not param or not value:
            continue
        mapped = key_map.get(param)
        if mapped:
            parsed[mapped] = value
    return parsed


def derive_auth_flow_rules(
    components: list[dict],
    connections: list[dict],
    dataflows: list[dict],
    context_entities: list[dict],
) -> dict:
    """
    Template-level rules for authentication diagram generation.

    This keeps diagram behavior declarative for future projects:
    rules are inferred from project input tables, then passed into the
    generator so the output adapts to each solution context.
    """
    def _flatten_text(records: list[dict], keys: tuple[str, ...]) -> str:
        return " ".join(" ".join(str(rec.get(k, "")) for k in keys) for rec in records)

    corpus = " ".join([
        _flatten_text(components, ("name", "technology", "description")),
        _flatten_text(connections, ("from", "to", "label")),
        _flatten_text(dataflows, ("source", "target", "label", "protocol")),
        _flatten_text(context_entities, ("name", "interaction", "type")),
    ]).lower()

    has_mfa = any(k in corpus for k in ["mfa", "multi-factor", "entra", "sso", "oidc", "oauth"])
    has_token_refresh = any(k in corpus for k in ["token", "jwt", "refresh", "federated", "bearer"])
    has_validation_or_reauth = any(k in corpus for k in ["validate", "validation", "401", "unauthorized", "reauth", "retry", "expired"])

    return {
        "flow_mode": "sequence",
        "include_mfa_challenge": has_mfa,
        "include_token_refresh": has_token_refresh,
        # Keep retry loop enabled by default for secure-by-design templates.
        "include_reauth_on_validation_failure": True if not has_validation_or_reauth else has_validation_or_reauth,
    }


def build_inherited_diagram_context(
    components: list[dict],
    connections: list[dict],
    dataflows: list[dict],
    context_entities: list[dict],
) -> dict:
    """Ensure all architecture diagrams inherit a complete set of required nodes from source inputs."""

    def _infer_layer(name: str) -> str:
        txt = (name or "").lower()
        if any(k in txt for k in ["internet", "user", "client", "on-prem", "external", "edge"]):
            return "Edge"
        if any(k in txt for k in ["gateway", "waf", "load balancer", "network", "subnet", "dns"]):
            return "Network"
        if any(k in txt for k in ["k8s", "eks", "platform", "runtime", "queue", "processing"]):
            return "Platform"
        if any(k in txt for k in ["database", "warehouse", "store", "bucket", "data", "rds", "s3"]):
            return "Data"
        return "Application"

    component_map: dict[str, dict] = {}
    for comp in components:
        name = (comp.get("name") or "").strip()
        if name:
            component_map[name.lower()] = dict(comp)

    for ent in context_entities:
        name = (ent.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key not in component_map:
            component_map[key] = {
                "no": "",
                "name": name,
                "layer": _infer_layer(name),
                "technology": ent.get("type", "External Entity"),
                "direction": ent.get("direction", "Both"),
                "description": ent.get("interaction", "Inherited from Context Entities"),
            }

    for conn in connections:
        for endpoint in [conn.get("from", ""), conn.get("to", "")]:
            name = (endpoint or "").strip()
            if not name:
                continue
            key = name.lower()
            if key not in component_map:
                component_map[key] = {
                    "no": "",
                    "name": name,
                    "layer": _infer_layer(name),
                    "technology": "Inherited from Architecture Connections",
                    "direction": "",
                    "description": "Auto-added to preserve complete connection paths",
                }

    for flow in dataflows:
        for endpoint in [flow.get("source", ""), flow.get("destination", "")]:
            name = (endpoint or "").strip()
            if not name:
                continue
            key = name.lower()
            if key not in component_map:
                component_map[key] = {
                    "no": "",
                    "name": name,
                    "layer": _infer_layer(name),
                    "technology": "Inherited from Data Flow Entries",
                    "direction": "",
                    "description": "Auto-added to preserve complete data flow paths",
                }

    return {
        "components": list(component_map.values()),
        "connections": connections,
        "dataflows": dataflows,
        "context_entities": context_entities,
    }


# ── Draw.io XML Generation ─────────────────────────────────────────────────

LAYER_ORDER  = ["Edge", "Network", "Platform", "Application", "Data"]
LAYER_COLORS = {
    "edge":        "#dae8fc",
    "network":     "#d5e8d4",
    "platform":    "#fff2cc",
    "application": "#f8cecc",
    "data":        "#e1d5e7",
}
BOX_W, BOX_H   = 160, 50
GAP_X, GAP_Y   = 40,  30
LABEL_W        = 120
X_START        = LABEL_W + GAP_X


def _normalise_layer(layer: str) -> str:
    lc = layer.strip().lower()
    for known in LAYER_ORDER:
        if known.lower() in lc or lc in known.lower():
            return known
    return "Application"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def generate_architecture_drawio(components: list[dict], connections: list[dict]) -> str:
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="Solution Architecture")
    ET.SubElement(diagram, "mxGraphModel",
                  dx="1422", dy="762", grid="1", gridSize="10", guides="1",
                  tooltips="1", connect="1", arrows="1", fold="1",
                  page="0", pageScale="1", pageWidth="1169", pageHeight="827",
                  math="0", shadow="0")
    root = ET.SubElement(diagram.find("mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    # Bucket components by layer
    layer_map: dict[str, list[dict]] = {l: [] for l in LAYER_ORDER}
    for comp in components:
        layer_map[_normalise_layer(comp["layer"])].append(comp)

    # Calculate Y per occupied layer
    y_cursor = 20
    layer_y: dict[str, int] = {}
    for layer in LAYER_ORDER:
        layer_y[layer] = y_cursor
        if layer_map[layer]:
            y_cursor += BOX_H + GAP_Y

    # Layer label boxes
    for layer in LAYER_ORDER:
        if not layer_map[layer]:
            continue
        color = LAYER_COLORS.get(layer.lower(), "#f5f5f5")
        lbl = ET.SubElement(root, "mxCell",
            id=f"lbl-{layer.lower()}",
            value=layer,
            style=(f"rounded=1;whiteSpace=wrap;align=center;"
                   f"fillColor={color};fontStyle=1;fontSize=11;"
                   "strokeColor=#999999;"),
            parent="1", vertex="1",
        )
        ET.SubElement(lbl, "mxGeometry",
            x="10", y=str(layer_y[layer]),
            width=str(LABEL_W - 20), height=str(BOX_H),
            **{"as": "geometry"})

    # Component boxes  — name (lower) → cell id
    comp_cell: dict[str, str] = {}
    for layer in LAYER_ORDER:
        for i, comp in enumerate(layer_map[layer]):
            cell_id = f"c-{_slug(comp['name'])}"
            comp_cell[comp["name"].lower()] = cell_id
            color = LAYER_COLORS.get(layer.lower(), "#ffffff")
            tech_line = f"\n({comp['technology']})" if comp["technology"] else ""
            cell = ET.SubElement(root, "mxCell",
                id=cell_id,
                value=f"{comp['name']}{tech_line}",
                style=(f"rounded=1;whiteSpace=wrap;align=center;"
                       f"fillColor={color};strokeColor=#666666;fontSize=11;"),
                parent="1", vertex="1",
            )
            ET.SubElement(cell, "mxGeometry",
                x=str(X_START + i * (BOX_W + GAP_X)),
                y=str(layer_y[layer]),
                width=str(BOX_W), height=str(BOX_H),
                **{"as": "geometry"})

    # Connections
    for i, conn in enumerate(connections):
        src = comp_cell.get(conn["from"].lower())
        tgt = comp_cell.get(conn["to"].lower())
        if not src or not tgt:
            print(f"  Warning: skipping connection '{conn['from']} → {conn['to']}' "
                  f"(component name not found in Components table).")
            continue
        edge = ET.SubElement(root, "mxCell",
            id=f"e-{i}",
            value=conn["label"],
            style=("edgeStyle=orthogonalEdgeStyle;rounded=0;"
                   "orthogonalLoop=1;jettySize=auto;"
                   "exitX=0.5;exitY=1;exitDx=0;exitDy=0;"
                   "entryX=0.5;entryY=0;entryDx=0;entryDy=0;fontSize=10;"),
            parent="1", source=src, target=tgt, edge="1",
        )
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_c4_logical_view_drawio(
    solution_name: str,
    components: list[dict],
    connections: list[dict],
    context_entities: list[dict],
) -> str:
    """Generate a C4 Level 2 (Container) logical view diagram."""
    display_solution_name = (solution_name or "").strip()
    if not display_solution_name or "template" in display_solution_name.lower():
        display_solution_name = "Target Data Solution"

    # Level 2 containers should focus on core runtime containers, not control-plane utilities.
    allowed_layers = {"edge", "network", "platform", "application", "data"}
    exclude_keywords = {
        "identity",
        "access management",
        "iam",
        "encryption",
        "secret",
        "threat",
        "vulnerability",
        "audit",
        "policy",
        "lineage",
        "cost",
        "privacy",
        "compliance",
        "secure ci/cd",
    }

    containers = []
    for comp in components:
        raw_layer = (comp.get("layer") or "").strip().lower()
        name_lc = (comp.get("name") or "").strip().lower()
        if raw_layer not in allowed_layers:
            continue
        if any(keyword in name_lc for keyword in exclude_keywords):
            continue
        containers.append(comp)

    if not containers:
        containers = [
            c for c in components
            if any(k in (c.get("name") or "").lower() for k in [
                "business app",
                "sftp",
                "transfer endpoint",
                "landing bucket",
                "validation processor",
                "processing queue",
                "curated database",
                "monitoring",
            ])
        ]

    # Keep container count readable.
    containers = containers[:9]

    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="C4 Container Diagram")
    ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="1422",
        dy="762",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="0",
        pageScale="1",
        pageWidth="2200",
        pageHeight="1000",
        math="0",
        shadow="0",
    )
    root = ET.SubElement(diagram.find("mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    title = ET.SubElement(
        root,
        "mxCell",
        id="c4-l2-title",
        value="C4 Container Diagram (Level 2) - Logical View",
        style="fontSize=16;fontStyle=1;align=center;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(title, "mxGeometry", x="250", y="20", width="1300", height="40", **{"as": "geometry"})

    boundary = ET.SubElement(
        root,
        "mxCell",
        id="c4-boundary",
        value="",
        style="rounded=0;whiteSpace=wrap;fontSize=14;dashed=1;dashPattern=1 4;strokeColor=#1a1a1a;strokeWidth=2;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(boundary, "mxGeometry", x="300", y="100", width="1000", height="640", **{"as": "geometry"})

    boundary_label = ET.SubElement(
        root,
        "mxCell",
        id="c4-boundary-label",
        value=display_solution_name,
        style="fontSize=12;fontStyle=1;align=left;fillColor=none;strokeColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(boundary_label, "mxGeometry", x="312", y="110", width="500", height="24", **{"as": "geometry"})

    container_ids: dict[str, str] = {}
    start_x, start_y = 340, 170
    box_w, box_h = 240, 105
    x_gap, y_gap = 35, 35
    cols = 3

    for i, comp in enumerate(containers):
        row = i // cols
        col = i % cols
        x = start_x + col * (box_w + x_gap)
        y = start_y + row * (box_h + y_gap)

        name = comp.get("name", "Container")
        cid = f"c4-container-{_slug(name)}-{i}"
        container_ids[name.lower()] = cid

        layer = _normalise_layer(comp.get("layer", ""))
        fill = LAYER_COLORS.get(layer.lower(), "#f5f5f5")
        tech = comp.get("technology") or comp.get("layer") or "Container"
        label = f"{name}\n[{tech}]"

        node = ET.SubElement(
            root,
            "mxCell",
            id=cid,
            value=label,
            style=f"rounded=1;whiteSpace=wrap;align=center;verticalAlign=middle;fillColor={fill};strokeColor=#4b5563;fontSize=11;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(node, "mxGeometry", x=str(x), y=str(y), width=str(box_w), height=str(box_h), **{"as": "geometry"})

    # Container relationships from architecture connections with flow numbering.
    # Color meaning: Blue = outbound (A→B only), Green = bidirectional (A↔B both exist).
    # Pre-build a set of all (from, to) pairs so we can detect bidirectional pairs.
    _all_pairs: set[tuple] = set()
    for _c in connections:
        _f = (_c.get("from") or "").lower()
        _t = (_c.get("to") or "").lower()
        if _f and _t:
            _all_pairs.add((_f, _t))

    _pair_count: dict[tuple, int] = {}

    # Vertical exit/entry fractions — each slot routes to a different face position.
    _offset_slots = [
        ("0.5", "0.5"),
        ("0.25", "0.25"),
        ("0.75", "0.75"),
        ("0.1",  "0.5"),
        ("0.9",  "0.5"),
        ("0.5",  "0.1"),
        ("0.5",  "0.9"),
    ]

    edge_idx = 0
    flow_explanations = []  # Track flows for right-side panel

    for conn in connections:
        src = container_ids.get((conn.get("from") or "").lower())
        tgt = container_ids.get((conn.get("to") or "").lower())
        if not src or not tgt:
            continue

        flow_num = edge_idx + 1
        label = conn.get("label", "")

        from_lc = (conn.get("from") or "").lower()
        to_lc   = (conn.get("to") or "").lower()

        # Determine direction: bidirectional if the reverse pair also exists.
        is_bidir = (to_lc, from_lc) in _all_pairs
        if is_bidir:
            direction_str = "Bi-directional"
            color = "#059669"  # green
            start_arrow = "classic"
        else:
            direction_str = "Outbound"
            color = "#2563EB"  # blue
            start_arrow = "none"

        flow_explanations.append({
            "num": flow_num,
            "from": conn.get("from", ""),
            "to": conn.get("to", ""),
            "label": label,
            "direction": direction_str,
        })

        # Pick exit/entry slot so parallel arrows fan out instead of stacking.
        pair_key = (src, tgt)
        slot_idx = _pair_count.get(pair_key, 0)
        _pair_count[pair_key] = slot_idx + 1
        ex_y, en_y = _offset_slots[slot_idx % len(_offset_slots)]
        routing_hint = f"exitX=1;exitY={ex_y};exitDx=0;exitDy=0;entryX=0;entryY={en_y};entryDx=0;entryDy=0;"

        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
            "jettySize=auto;fontSize=13;fontStyle=1;"
            "fontColor=#1e1e1e;labelBackgroundColor=#ffffff;labelBorderColor=none;"
            f"strokeColor={color};strokeWidth=2;"
            f"endArrow=classic;startArrow={start_arrow};"
            + routing_hint
        )

        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"c4-container-edge-{edge_idx}",
            value=str(flow_num),
            style=style,
            parent="1",
            source=src,
            target=tgt,
            edge="1",
        )
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
        edge_idx += 1

    # External actors/systems from context entities.
    externals = (context_entities or [])[:6]
    external_ids: dict[str, str] = {}
    for i, ent in enumerate(externals):
        name = (ent.get("name") or "External Entity").strip()
        direction = (ent.get("direction") or "both").strip().lower()
        ent_type = (ent.get("type") or "System").strip()

        is_right = direction == "in"
        ex_x = 40 if not is_right else 1290
        ex_y = 170 + i * 95

        eid = f"c4-external-{_slug(name)}-{i}"
        external_ids[name.lower()] = eid
        box = ET.SubElement(
            root,
            "mxCell",
            id=eid,
            value=f"{name}\n[{ent_type}]",
            style="rounded=1;whiteSpace=wrap;align=center;verticalAlign=middle;fillColor=#ffffff;strokeColor=#6b7280;fontSize=10;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(box, "mxGeometry", x=str(ex_x), y=str(ex_y), width="240", height="70", **{"as": "geometry"})

    preferred_targets = {
        "on-prem business app": "on-prem sftp server",
        "on-prem sftp server": "aws transfer endpoint",
        "on-prem identity service": "aws transfer endpoint",
        "ukhsa intra identity (azure entra id)": "aws transfer endpoint",
        "data analyst team": "curated database",
        "security operations": "monitoring and alerts",
    }

    if containers:
        default_target = containers[0].get("name", "").lower()
    else:
        default_target = ""

    for ent in externals:
        name = (ent.get("name") or "").strip().lower()
        direction = (ent.get("direction") or "both").strip().lower()
        src_external = external_ids.get(name)
        target_name = preferred_targets.get(name, default_target)
        target_container = container_ids.get(target_name)
        if not src_external or not target_container:
            continue

        if direction == "in":
            source, target = target_container, src_external
            # Blue = outbound (one-way, data going in to external)
            edge_style = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;fontSize=9;strokeColor=#2563EB;strokeWidth=2;startArrow=none;endArrow=classic;"
        elif direction == "out":
            source, target = src_external, target_container
            # Blue = outbound (one-way, data coming out from external)
            edge_style = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;fontSize=9;strokeColor=#2563EB;strokeWidth=2;startArrow=none;endArrow=classic;"
        else:
            source, target = src_external, target_container
            # Green = bi-directional
            edge_style = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;fontSize=9;strokeColor=#059669;strokeWidth=2;startArrow=classic;endArrow=classic;"

        ext_edge = ET.SubElement(
            root,
            "mxCell",
            id=f"c4-external-edge-{edge_idx}",
            value=ent.get("interaction", ""),
            style=edge_style,
            parent="1",
            source=source,
            target=target,
            edge="1",
        )
        ET.SubElement(ext_edge, "mxGeometry", relative="1", **{"as": "geometry"})
        edge_idx += 1

    # Right-side explanation panel for flow details
    panel_x = 1850
    panel_width = 280
    panel_y = 100
    panel_height = 640
    
    explanation_panel = ET.SubElement(
        root,
        "mxCell",
        id="flow-explanation-panel",
        value="",
        style="rounded=1;fillColor=#F8FAFC;strokeColor=#9AA5B1;strokeWidth=1.5;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(explanation_panel, "mxGeometry", x=str(panel_x), y=str(panel_y), width=str(panel_width), height=str(panel_height), **{"as": "geometry"})
    
    # Panel title
    panel_title = ET.SubElement(
        root,
        "mxCell",
        id="flow-explanation-title",
        value="Data Flows",
        style="fontSize=12;fontStyle=1;fillColor=none;strokeColor=none;align=center;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(panel_title, "mxGeometry", x=str(panel_x + 10), y=str(panel_y + 10), width=str(panel_width - 20), height="25", **{"as": "geometry"})
    
    # Flow descriptions
    flow_y = panel_y + 45
    for flow_info in flow_explanations[:8]:  # Limit to 8 flows for space
        direction = flow_info.get("direction", "Outbound")
        dir_symbol = "↔" if direction == "Bi-directional" else "→"
        flow_text = f"Step {flow_info['num']}: {flow_info['from'].split('(')[0].strip()} {dir_symbol} {flow_info['to'].split('(')[0].strip()} ({direction})"
        if flow_info.get("label"):
            flow_text += f"\n{flow_info['label']}"

        flow_description = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-desc-{flow_info['num']}",
            value=flow_text,
            style="fontSize=9;align=left;verticalAlign=top;fillColor=none;strokeColor=none;whiteSpace=wrap;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(flow_description, "mxGeometry", x=str(panel_x + 8), y=str(flow_y), width=str(panel_width - 16), height="65", **{"as": "geometry"})
        flow_y += 72
    legend_title = ET.SubElement(
        root,
        "mxCell",
        id="c4-legend-title",
        value="Legend:",
        style="fontSize=10;fontStyle=1;align=left;fillColor=none;strokeColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(legend_title, "mxGeometry", x="320", y="760", width="80", height="20", **{"as": "geometry"})

    c4_legend_items = [
        ("Edge/Network", "#dae8fc", "410"),
        ("Platform", "#d5e8d4", "560"),
        ("Application", "#f8cecc", "690"),
        ("Data", "#e1d5e7", "840"),
        ("Internal", "#ffffff", "950"),
    ]

    for idx, (label, fill, lx) in enumerate(c4_legend_items):
        legend_box = ET.SubElement(
            root,
            "mxCell",
            id=f"c4-legend-box-{idx}",
            value="",
            style=f"rounded=0;whiteSpace=wrap;fillColor={fill};strokeColor=#6b7280;strokeWidth=1;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(legend_box, "mxGeometry", x=lx, y="760", width="18", height="18", **{"as": "geometry"})

        legend_text = ET.SubElement(
            root,
            "mxCell",
            id=f"c4-legend-text-{idx}",
            value=label,
            style="fontSize=9;align=left;fillColor=none;strokeColor=none;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(legend_text, "mxGeometry", x=str(int(lx) + 22), y="759", width="110", height="20", **{"as": "geometry"})

    c4_arrow_legend = ET.SubElement(
        root,
        "mxCell",
        id="c4-legend-arrows",
        value="Arrow colours:  Blue (→) = Outbound (one-way)     Green (↔) = Bi-directional",
        style="fontSize=9;align=left;fillColor=none;strokeColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(c4_arrow_legend, "mxGeometry", x="320", y="785", width="700", height="20", **{"as": "geometry"})

    # Small colored line swatches to reinforce the arrow legend visually.
    for swatch_id, swatch_color, swatch_x in [
        ("c4-legend-swatch-blue",  "#2563EB", "321"),
        ("c4-legend-swatch-green", "#059669", "600"),
    ]:
        swatch = ET.SubElement(
            root, "mxCell", id=swatch_id, value="",
            style=f"endArrow=classic;startArrow=none;strokeColor={swatch_color};strokeWidth=2;",
            parent="1", source="", target="", edge="1",
        )
        geom = ET.SubElement(swatch, "mxGeometry", relative="1", **{"as": "geometry"})
        pts = ET.SubElement(geom, "Array", **{"as": "points"})
        ET.SubElement(swatch, "mxPoint", x=swatch_x, y="793", **{"as": "sourcePoint"})
        ET.SubElement(swatch, "mxPoint", x=str(int(swatch_x) + 30), y="793", **{"as": "targetPoint"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_dfd_drawio(dataflows: list[dict]) -> str:
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="Data Flow Diagram (Level 2)")
    ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="1422",
        dy="762",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="0",
        pageScale="1",
        pageWidth="1700",
        pageHeight="1000",
        math="0",
        shadow="0",
    )
    root = ET.SubElement(diagram.find("mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    title = ET.SubElement(
        root,
        "mxCell",
        id="dfd-l2-title",
        value="Data Flow Diagram (Level 2)",
        style="fontSize=16;fontStyle=1;align=center;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(title, "mxGeometry", x="220", y="20", width="980", height="36", **{"as": "geometry"})

    def _is_datastore(name: str) -> bool:
        n = name.lower()
        return any(k in n for k in ["bucket", "database", "db", "queue", "store", "warehouse", "lake", "table"])

    def _is_external(name: str) -> bool:
        n = name.lower()
        return any(k in n for k in ["on-prem", "on prem", "team", "user", "operations", "external", "partner", "source"])

    # Build node stats from all flows to support layout and direction labels.
    node_stats: dict[str, dict[str, int]] = {}
    for flow in dataflows:
        src = (flow.get("source") or "").strip()
        dst = (flow.get("destination") or "").strip()
        if not src or not dst:
            continue
        src_key = src.lower()
        dst_key = dst.lower()
        if src_key not in node_stats:
            node_stats[src_key] = {"name": src, "in": 0, "out": 0}
        if dst_key not in node_stats:
            node_stats[dst_key] = {"name": dst, "in": 0, "out": 0}
        node_stats[src_key]["out"] += 1
        node_stats[dst_key]["in"] += 1

    externals, processes, stores = [], [], []
    for key, st in node_stats.items():
        name = st["name"]
        if _is_datastore(name):
            stores.append(name)
        elif _is_external(name):
            externals.append(name)
        else:
            processes.append(name)

    externals.sort()
    processes.sort()
    stores.sort()

    # Draw a central level-2 process boundary.
    l2_boundary = ET.SubElement(
        root,
        "mxCell",
        id="dfd-l2-boundary",
        value="Level 2 Process Decomposition",
        style="rounded=0;whiteSpace=wrap;dashed=1;dashPattern=1 4;strokeColor=#6B7280;strokeWidth=2;fillColor=none;fontSize=12;fontStyle=1;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(l2_boundary, "mxGeometry", x="320", y="90", width="700", height="720", **{"as": "geometry"})

    node_cells: dict[str, str] = {}

    def _add_node(node_id: str, name: str, x: int, y: int, w: int, h: int, style: str) -> None:
        cell = ET.SubElement(
            root,
            "mxCell",
            id=node_id,
            value=name,
            style=style,
            parent="1",
            vertex="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as": "geometry"})

    # External entities (left lane)
    ex_y = 130
    for i, name in enumerate(externals):
        nid = f"dfd-ext-{_slug(name)}-{i}"
        node_cells[name.lower()] = nid
        _add_node(
            nid,
            name,
            40,
            ex_y,
            220,
            64,
            "rounded=0;whiteSpace=wrap;align=center;verticalAlign=middle;fillColor=#F3F4F6;strokeColor=#4B5563;fontSize=10;fontStyle=1;",
        )
        ex_y += 95

    # Processes (middle lane, two columns)
    pr_start_x = 380
    pr_y = 140
    pr_col_gap = 330
    pr_row_gap = 115
    for i, name in enumerate(processes):
        nid = f"dfd-proc-{_slug(name)}-{i}"
        node_cells[name.lower()] = nid
        col = i % 2
        row = i // 2
        _add_node(
            nid,
            name,
            pr_start_x + col * pr_col_gap,
            pr_y + row * pr_row_gap,
            280,
            70,
            "ellipse;whiteSpace=wrap;align=center;verticalAlign=middle;fillColor=#DBEAFE;strokeColor=#1D4ED8;fontSize=10;fontStyle=1;",
        )

    # Data stores (right lane)
    ds_y = 130
    for i, name in enumerate(stores):
        nid = f"dfd-store-{_slug(name)}-{i}"
        node_cells[name.lower()] = nid
        _add_node(
            nid,
            name,
            1080,
            ds_y,
            240,
            64,
            "shape=partialRectangle;whiteSpace=wrap;align=center;verticalAlign=middle;fillColor=#FEF3C7;strokeColor=#B45309;fontSize=10;fontStyle=1;top=0;left=0;right=0;bottom=1;",
        )
        ds_y += 95

    # Build a reverse pair set to classify directional semantics.
    pair_set: set[tuple[str, str]] = set()
    for flow in dataflows:
        s = (flow.get("source") or "").strip().lower()
        d = (flow.get("destination") or "").strip().lower()
        if s and d:
            pair_set.add((s, d))

    flow_details = []
    edge_counts: dict[tuple[str, str], int] = {}
    offset_slots = ["0.25", "0.45", "0.65", "0.85"]

    for i, flow in enumerate(dataflows):
        src_name = (flow.get("source") or "").strip()
        dst_name = (flow.get("destination") or "").strip()
        if not src_name or not dst_name:
            continue
        src_id = node_cells.get(src_name.lower())
        dst_id = node_cells.get(dst_name.lower())
        if not src_id or not dst_id:
            continue

        flow_id = (flow.get("id") or str(i + 1)).strip() or str(i + 1)
        data_label = (flow.get("data") or "").strip()
        protocol = (flow.get("protocol") or "").strip()

        bidir = (dst_name.lower(), src_name.lower()) in pair_set
        direction = "Bi-directional" if bidir else "One-way"
        stroke = "#059669" if bidir else "#2563EB"
        start_arrow = "classic" if bidir else "none"
        symbol = "<->" if bidir else "->"

        pair_key = (src_id, dst_id)
        pidx = edge_counts.get(pair_key, 0)
        edge_counts[pair_key] = pidx + 1
        exit_y = offset_slots[pidx % len(offset_slots)]
        entry_y = offset_slots[(pidx + 1) % len(offset_slots)]

        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"df-l2-e-{i}",
            value=flow_id,
            style=(
                f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;"
                f"exitX=1;exitY={exit_y};entryX=0;entryY={entry_y};"
                f"fontSize=11;fontStyle=1;fontColor=#111827;labelBackgroundColor=#FFFFFF;"
                f"strokeColor={stroke};strokeWidth=2;startArrow={start_arrow};endArrow=classic;"
            ),
            parent="1",
            source=src_id,
            target=dst_id,
            edge="1",
        )
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})

        detail_text = data_label if data_label else "Data"
        if protocol:
            detail_text += f" [{protocol}]"
        flow_details.append(f"{flow_id}. {src_name} {symbol} {dst_name} ({direction})\\n{detail_text}")

    # Right-side L2 flow details panel.
    panel_x = 1360
    panel_y = 100
    panel_w = 300
    panel_h = 740

    panel = ET.SubElement(
        root,
        "mxCell",
        id="dfd-l2-panel",
        value="",
        style="rounded=1;fillColor=#F8FAFC;strokeColor=#9AA5B1;strokeWidth=1.5;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(panel, "mxGeometry", x=str(panel_x), y=str(panel_y), width=str(panel_w), height=str(panel_h), **{"as": "geometry"})

    panel_title = ET.SubElement(
        root,
        "mxCell",
        id="dfd-l2-panel-title",
        value="L2 Data Flows",
        style="fontSize=12;fontStyle=1;align=center;fillColor=none;strokeColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(panel_title, "mxGeometry", x=str(panel_x + 10), y=str(panel_y + 8), width=str(panel_w - 20), height="24", **{"as": "geometry"})

    fy = panel_y + 38
    for idx, text in enumerate(flow_details[:10]):
        flow_cell = ET.SubElement(
            root,
            "mxCell",
            id=f"dfd-l2-flow-{idx}",
            value=text,
            style="fontSize=9;align=left;verticalAlign=top;whiteSpace=wrap;fillColor=none;strokeColor=none;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(flow_cell, "mxGeometry", x=str(panel_x + 8), y=str(fy), width=str(panel_w - 16), height="66", **{"as": "geometry"})
        fy += 70

    direction_key = ET.SubElement(
        root,
        "mxCell",
        id="dfd-l2-key",
        value="Direction key: Blue = One-way, Green = Bi-directional",
        style="fontSize=9;fontStyle=1;align=left;fillColor=none;strokeColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(direction_key, "mxGeometry", x=str(panel_x + 8), y=str(panel_y + panel_h - 24), width=str(panel_w - 16), height="18", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_dataset_relationship_drawio(datasets: list[dict], relationships: list[dict]) -> str:
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="Entity Relationship Diagram (ERD)")
    ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="1422",
        dy="762",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="0",
        pageScale="1",
        pageWidth="1900",
        pageHeight="1000",
        math="0",
        shadow="0",
    )
    root = ET.SubElement(diagram.find("mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    title = ET.SubElement(
        root,
        "mxCell",
        id="erd-title",
        value="Entity Relationship Diagram (ERD) - All Entities & Relationships",
        style="fontSize=16;fontStyle=1;align=center;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(title, "mxGeometry", x="240", y="20", width="1100", height="36", **{"as": "geometry"})

    BOX_W, BOX_H = 240, 120
    X_GAP, Y_GAP = 30, 30
    X_START, Y_START = 40, 90
    COLUMNS = 3

    dataset_cells: dict[str, str] = {}
    dataset_meta: dict[str, dict] = {}

    def _safe(v: str) -> str:
        return (v or "N/A").strip() or "N/A"

    # Render all entities on the left side
    for i, ds in enumerate(datasets):
        row = i // COLUMNS
        col = i % COLUMNS
        x = X_START + col * (BOX_W + X_GAP)
        y = Y_START + row * (BOX_H + Y_GAP)
        cell_id = f"ds-{_slug(ds['name'])}-{i}"
        ds_name = _safe(ds.get("name", "Dataset"))
        ds_id = _safe(ds.get("id", ""))
        ds_pk = _safe(ds.get("primary_key", ""))
        dataset_cells[ds_name.lower()] = cell_id
        if ds_id != "N/A":
            dataset_cells[ds_id.lower()] = cell_id
        dataset_meta[ds_name.lower()] = {"name": ds_name, "pk": ds_pk}
        if ds_id != "N/A":
            dataset_meta[ds_id.lower()] = {"name": ds_name, "pk": ds_pk}

        name = ds_name
        pk = ds_pk
        dtype = _safe(ds.get("type", ""))
        sensitivity = _safe(ds.get("sensitivity", ""))
        retention = _safe(ds.get("retention", ""))
        label = (
            f"<b>{name}</b><br/>"
            f"PK: {pk}<br/>"
            f"Type: {dtype}<br/>"
            f"Sensitivity: {sensitivity}<br/>"
            f"Retention: {retention}"
        )
        cell = ET.SubElement(
            root,
            "mxCell",
            id=cell_id,
            value=label,
            style=(
                "rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;"
                "fillColor=#FFF7E6;strokeColor=#B45309;strokeWidth=1.6;fontSize=9;spacing=6;"
            ),
            parent="1",
            vertex="1",
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            x=str(x),
            y=str(y),
            width=str(BOX_W),
            height=str(BOX_H),
            **{"as": "geometry"},
        )

    def _cardinality_label(rel: str, mapping: str) -> str:
        text = f"{(rel or '').lower()} {(mapping or '').lower()}"
        compact = text.replace(" ", "").upper()
        if "1:1" in compact:
            return "1:1"
        if "1:N" in compact or "1:M" in compact:
            return "1:N"
        if "M:N" in compact or "N:M" in compact:
            return "N:N"
        if "many" in text and "one" in text:
            return "1:N"
        if "many" in text:
            return "N:N"
        if "one" in text:
            return "1:1"
        return "Rel"

    def _extract_pk_fk(mapping: str, src_pk: str, tgt_pk: str) -> tuple[str, str]:
        m = (mapping or "").strip()
        if not m:
            return (src_pk, tgt_pk)

        # Support common arrow notations: ->, , <->, 
        normalized = (
            m.replace("↔", "<->")
            .replace("→", "->")
            .replace("←", "<-")
        )

        if "<->" in normalized:
            parts = [p.strip() for p in normalized.split("<->", 1)]
        elif "->" in normalized:
            parts = [p.strip() for p in normalized.split("->", 1)]
        elif "<-" in normalized:
            parts = [p.strip() for p in normalized.split("<-", 1)]
            parts = [parts[1], parts[0]] if len(parts) == 2 else parts
        else:
            parts = [p.strip() for p in re.split(r"\s+", normalized) if p.strip()]

        if len(parts) >= 2:
            return (parts[0] or src_pk, parts[1] or tgt_pk)
        if len(parts) == 1:
            return (parts[0] or src_pk, parts[0] or tgt_pk)
        return (src_pk, tgt_pk)

    # Collect all relationships
    valid_relationships = []
    for i, rel in enumerate(relationships):
        src_key = (rel.get("source") or "").strip().lower()
        tgt_key = (rel.get("target") or "").strip().lower()
        src = dataset_cells.get(src_key)
        tgt = dataset_cells.get(tgt_key)
        if not src or not tgt:
            print(
                f"  Warning: skipping dataset relationship '{rel['source']} -> {rel['target']}' "
                "(dataset not found in Dataset Inventory)."
            )
            continue
        src_meta = dataset_meta.get(src_key, {"name": rel["source"], "pk": "N/A"})
        tgt_meta = dataset_meta.get(tgt_key, {"name": rel["target"], "pk": "N/A"})
        pk_key, fk_key = _extract_pk_fk(rel.get("mapping", ""), src_meta["pk"], tgt_meta["pk"])
        valid_relationships.append({
            "id": i,
            "source": src_meta["name"],
            "target": tgt_meta["name"],
            "relation": rel.get("relation", ""),
            "mapping": rel.get("mapping", ""),
            "pk_key": pk_key,
            "fk_key": fk_key,
            "src_cell": src,
            "tgt_cell": tgt,
        })

    # Create edges for relationships
    for rel in valid_relationships:
        edge_label = _cardinality_label(rel["relation"], rel["mapping"])
        edge_label = f"{edge_label}\\nPK: {rel['pk_key']} -> FK: {rel['fk_key']}"
        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"ds-edge-{rel['id']}",
            value=edge_label,
            style=(
                "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=20;"
                "fontSize=9;fontStyle=1;strokeColor=#2563EB;strokeWidth=2.5;"
                "startArrow=none;endArrow=block;endFill=1;"
                "labelBackgroundColor=#FFFFFF;labelBorderColor=#CBD5E1;"
            ),
            parent="1",
            source=rel["src_cell"],
            target=rel["tgt_cell"],
            edge="1",
        )
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})

    # Right-side Relationships Panel
    panel_x = 1050
    panel_y = 90
    panel_w = 820
    panel_h = 800

    panel = ET.SubElement(
        root,
        "mxCell",
        id="erd-relationships-panel",
        value="",
        style="rounded=1;fillColor=#F8FAFC;strokeColor=#9AA5B1;strokeWidth=1.5;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(panel, "mxGeometry", x=str(panel_x), y=str(panel_y), width=str(panel_w), height=str(panel_h), **{"as": "geometry"})

    # Panel Title
    panel_title = ET.SubElement(
        root,
        "mxCell",
        id="erd-relationships-title",
        value="Entity Relationships & Connections",
        style="fontSize=13;fontStyle=1;align=left;fillColor=none;strokeColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(panel_title, "mxGeometry", x=str(panel_x + 12), y=str(panel_y + 10), width=str(panel_w - 24), height="22", **{"as": "geometry"})

    # Header row for relationship details
    header_y = panel_y + 40
    header_style = "fontSize=9;fontStyle=1;align=left;verticalAlign=middle;fillColor=#E2E8F0;strokeColor=#CBD5E1;strokeWidth=1;padding=4;"
    
    headers = [
        ("ID", panel_x + 12, 30),
        ("Source Entity", panel_x + 44, 150),
        ("Type", panel_x + 198, 55),
        ("Target Entity", panel_x + 257, 150),
        ("PK -> FK Relationship", panel_x + 411, 445),
    ]
    
    for header_text, header_x, header_w in headers:
        header = ET.SubElement(
            root,
            "mxCell",
            id=f"erd-header-{header_text.replace(' ', '-')}",
            value=header_text,
            style=header_style,
            parent="1",
            vertex="1",
        )
        ET.SubElement(header, "mxGeometry", x=str(header_x), y=str(header_y), width=str(header_w), height="18", **{"as": "geometry"})

    # Relationship rows
    row_y = header_y + 24
    for idx, rel in enumerate(valid_relationships[:15]):  # Limit to 15 rows
        rel_id = str(idx + 1)
        rel_type = _cardinality_label(rel["relation"], rel["mapping"])
        key_relationship = f"PK: {rel['pk_key']} -> FK: {rel['fk_key']}"
        if rel["mapping"]:
            key_relationship = f"{key_relationship} ({rel['mapping']})"
        
        row_height = 24
        row_style = "fontSize=8;align=left;verticalAlign=middle;fillColor=none;strokeColor=#E2E8F0;strokeWidth=0.5;padding=2;"
        
        # ID column
        id_cell = ET.SubElement(
            root,
            "mxCell",
            id=f"erd-rel-id-{idx}",
            value=rel_id,
            style=row_style,
            parent="1",
            vertex="1",
        )
        ET.SubElement(id_cell, "mxGeometry", x=str(panel_x + 12), y=str(row_y), width="30", height=str(row_height), **{"as": "geometry"})
        
        # Source Entity column
        src_cell = ET.SubElement(
            root,
            "mxCell",
            id=f"erd-rel-src-{idx}",
            value=rel["source"],
            style=row_style,
            parent="1",
            vertex="1",
        )
        ET.SubElement(src_cell, "mxGeometry", x=str(panel_x + 44), y=str(row_y), width="150", height=str(row_height), **{"as": "geometry"})
        
        # Relationship Type column
        type_cell = ET.SubElement(
            root,
            "mxCell",
            id=f"erd-rel-type-{idx}",
            value=rel_type,
            style=row_style + "fontStyle=1;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(type_cell, "mxGeometry", x=str(panel_x + 198), y=str(row_y), width="55", height=str(row_height), **{"as": "geometry"})
        
        # Target Entity column
        tgt_cell = ET.SubElement(
            root,
            "mxCell",
            id=f"erd-rel-tgt-{idx}",
            value=rel["target"],
            style=row_style,
            parent="1",
            vertex="1",
        )
        ET.SubElement(tgt_cell, "mxGeometry", x=str(panel_x + 257), y=str(row_y), width="150", height=str(row_height), **{"as": "geometry"})
        
        # Mapping Details column
        map_cell = ET.SubElement(
            root,
            "mxCell",
            id=f"erd-rel-map-{idx}",
            value=key_relationship,
            style=row_style,
            parent="1",
            vertex="1",
        )
        ET.SubElement(map_cell, "mxGeometry", x=str(panel_x + 411), y=str(row_y), width="445", height=str(row_height), **{"as": "geometry"})
        
        row_y += row_height

    # Legend section
    legend_y = row_y + 20
    legend_label = ET.SubElement(
        root,
        "mxCell",
        id="erd-legend-title",
        value="Cardinality Legend:",
        style="fontSize=9;fontStyle=1;align=left;fillColor=none;strokeColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(legend_label, "mxGeometry", x=str(panel_x + 12), y=str(legend_y), width=str(panel_w - 24), height="16", **{"as": "geometry"})

    legend_items = [
        "1:1 = One-to-One relationship",
        "1:N = One-to-Many relationship",
        "N:N = Many-to-Many relationship",
        "PK = Primary Key, FK = Secondary/Foreign Key",
        "Blue arrows indicate relationship direction (source → target)",
    ]
    
    legend_item_y = legend_y + 18
    for legend_text in legend_items:
        legend_item = ET.SubElement(
            root,
            "mxCell",
            id=f"erd-legend-{legend_text[:20].replace(' ', '-')}",
            value=legend_text,
            style="fontSize=8;align=left;verticalAlign=top;whiteSpace=wrap;fillColor=none;strokeColor=none;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(legend_item, "mxGeometry", x=str(panel_x + 20), y=str(legend_item_y), width=str(panel_w - 40), height="16", **{"as": "geometry"})
        legend_item_y += 18

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_context_view_drawio(solution_name: str, entities: list[dict]) -> str:
    """
    Generate a C4 System Context Diagram (Level 1).
    Shows the system boundary, external systems/users, and data flows.
    Emphasizes on-prem to cloud data flow path via SFTP server bridge.
    """
    display_solution_name = (solution_name or "").strip()
    if not display_solution_name or "template" in display_solution_name.lower():
        display_solution_name = "Target Data Solution"

    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="C4 System Context")
    ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="1422",
        dy="762",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="0",
        pageScale="1",
        pageWidth="2200",
        pageHeight="1000",
        math="0",
        shadow="0",
    )
    root = ET.SubElement(diagram.find("mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    # Add title
    title = ET.SubElement(
        root,
        "mxCell",
        id="title",
        value="C4 System Context Diagram (Level 1) - On-Prem SFTP to Cloud",
        style="fontSize=16;fontStyle=1;align=center;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(title, "mxGeometry", x="300", y="20", width="1000", height="40", **{"as": "geometry"})

    # Add system boundary (large rectangle)
    system_boundary_id = "system-boundary"
    system_boundary = ET.SubElement(
        root,
        "mxCell",
        id=system_boundary_id,
        value="",
        style="rounded=0;whiteSpace=wrap;fontSize=14;dashed=1;dashPattern=1 4;strokeColor=#1a1a1a;strokeWidth=2;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(system_boundary, "mxGeometry", x="450", y="100", width="650", height="600", **{"as": "geometry"})

    # Add system label inside boundary
    system_label = ET.SubElement(
        root,
        "mxCell",
        id="system-label",
        value=display_solution_name,
        style="fontSize=12;fontStyle=1;align=left;fillColor=none;strokeColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(system_label, "mxGeometry", x="460", y="110", width="400", height="20", **{"as": "geometry"})

    # Central system container
    center_id = "solution-core"
    center = ET.SubElement(
        root,
        "mxCell",
        id=center_id,
        value=display_solution_name,
        style="rounded=1;whiteSpace=wrap;align=center;fillColor=#4da6ff;strokeColor=#003d99;fontSize=12;fontStyle=1;fontColor=#ffffff;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(center, "mxGeometry", x="575", y="340", width="200", height="100", **{"as": "geometry"})

    # Color mapping for entity types
    color_map = {
        "user": "fillColor=#fff4e6;strokeColor=#ff7700;",
        "system": "fillColor=#f0f0f0;strokeColor=#666666;",
        "service": "fillColor=#e6f3ff;strokeColor=#0066cc;",
        "": "fillColor=#f0f0f0;strokeColor=#666666;",
    }
    
    # Default color
    default_color = "fillColor=#f0f0f0;strokeColor=#666666;"

    # Position entities strategically to show data flow path
    # Left side (on-prem + identity): Business App → SFTP Server + UKHSA identity integration
    # Right side (consumers): Data Analyst Team, Security Operations
    positions = [
        (100, 150),    # On-Prem Business App (top-left)
        (100, 350),    # On-Prem SFTP Server (middle-left - bridge)
        (100, 550),    # UKHSA Intra Identity (bottom-left)
        (1150, 250),   # Data Analyst Team (top-right)
        (1150, 450),   # Security Operations (bottom-right)
    ]

    entity_node_ids = {}
    flow_explanations = []
    edge_idx = 1
    for i, ent in enumerate(entities):
        ent_id = f"ctx-{_slug(ent['name'])}-{i}"
        ent_name = (ent.get("name") or "").strip()
        ent_type = (ent.get("type") or "").lower()
        entity_node_ids[ent_name.lower()] = ent_id
        
        # Get color based on type
        color = color_map.get(ent_type, default_color)
        
        # Format entity label with type and direction
        direction = (ent.get("direction") or "").strip()
        if direction.lower() == "in":
            direction_symbol = "←"
        elif direction.lower() == "out":
            direction_symbol = "→"
        elif direction.lower() == "both":
            direction_symbol = "↔"
        else:
            direction_symbol = ""
        
        label = f"{ent['name']}"
        if ent_type:
            label += f"\n[{ent_type.capitalize()}]"
        if direction_symbol:
            label += f"\n{direction_symbol}"
        
        x, y = positions[i] if i < len(positions) else (200, 200 + i * 80)
        node = ET.SubElement(
            root,
            "mxCell",
            id=ent_id,
            value=label,
            style=f"rounded=1;whiteSpace=wrap;align=center;{color}fontSize=10;verticalAlign=middle;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(node, "mxGeometry", x=str(x), y=str(y), width="140", height="80", **{"as": "geometry"})

        # Add data flow edge with label
        interaction_text = ent.get("interaction", "")
        if direction.lower() == "in":
            source = center_id
            target = ent_id
        elif direction.lower() == "out":
            source = ent_id
            target = center_id
        else:  # both or default
            source = ent_id
            target = center_id

        # Keep a dedicated orange bridge for the business app path, but retain
        # normal black connectivity for SFTP and all other entities.
        skip_direct_edge = ent_name.lower() in {"on-prem business app"}
        if skip_direct_edge:
            continue

        flow_num = edge_idx
        flow_explanations.append(
            {
                "num": flow_num,
                "from": ent_name or "External Entity",
                "to": display_solution_name if direction.lower() != "in" else ent_name or "External Entity",
                "label": interaction_text,
            }
        )

        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"ctx-edge-{i}",
            value=str(flow_num),
            style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;fontSize=16;fontStyle=1;fontColor=#111827;labelBackgroundColor=#ffffff;strokeWidth=2;strokeColor=#111827;startArrow=classic;endArrow=classic;",
            parent="1",
            source=source,
            target=target,
            edge="1",
        )
        # Route the normal SFTP line to the lower side of the core so it does
        # not merge visually with the orange bridge line.
        if ent_name.lower() == "on-prem sftp server":
            edge.set("style", edge.get("style") + "exitX=1;exitY=0.7;entryX=0;entryY=0.8;")
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
        edge_idx += 1

    # Explicit bridge flows to make the on-prem ingestion path visually unambiguous.
    business_id = entity_node_ids.get("on-prem business app")
    sftp_id = entity_node_ids.get("on-prem sftp server")
    if business_id and sftp_id:
        flow_explanations.append(
            {
                "num": edge_idx,
                "from": "On-Prem Business App",
                "to": "On-Prem SFTP Server",
                "label": "Daily SFTP export",
            }
        )
        bridge_edge_1 = ET.SubElement(
            root,
            "mxCell",
            id="ctx-bridge-business-to-sftp",
            value=str(edge_idx),
            style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;fontSize=16;fontStyle=1;fontColor=#111827;labelBackgroundColor=#ffffff;strokeWidth=2;strokeColor=#ea580c;endArrow=classic;",
            parent="1",
            source=business_id,
            target=sftp_id,
            edge="1",
        )
        ET.SubElement(bridge_edge_1, "mxGeometry", relative="1", **{"as": "geometry"})
        edge_idx += 1

        flow_explanations.append(
            {
                "num": edge_idx,
                "from": "On-Prem SFTP Server",
                "to": display_solution_name,
                "label": "SFTP relay to cloud endpoint",
            }
        )
        bridge_edge_2 = ET.SubElement(
            root,
            "mxCell",
            id="ctx-bridge-sftp-to-cloud",
            value=str(edge_idx),
            style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;fontSize=16;fontStyle=1;fontColor=#111827;labelBackgroundColor=#ffffff;strokeWidth=2;strokeColor=#ea580c;endArrow=classic;exitX=1;exitY=0.45;entryX=0;entryY=0.2;",
            parent="1",
            source=sftp_id,
            target=center_id,
            edge="1",
        )
        ET.SubElement(bridge_edge_2, "mxGeometry", relative="1", **{"as": "geometry"})
        edge_idx += 1

    # Add data flow path annotation for on-prem bridge
    annotation = ET.SubElement(
        root,
        "mxCell",
        id="data-flow-path",
        value="On-Prem Data Path:\nBusiness App → SFTP Server → Cloud",
        style="fontSize=9;align=center;fillColor=#fff9c4;strokeColor=#f9a825;rounded=1;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(annotation, "mxGeometry", x="50", y="280", width="200", height="60", **{"as": "geometry"})

    # Right-side panel for numbered flow steps.
    panel_x = 1800
    panel_y = 120
    panel_width = 340
    panel_height = 560

    explanation_panel = ET.SubElement(
        root,
        "mxCell",
        id="ctx-flow-explanation-panel",
        value="",
        style="rounded=1;fillColor=#F8FAFC;strokeColor=#9AA5B1;strokeWidth=1.5;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(
        explanation_panel,
        "mxGeometry",
        x=str(panel_x),
        y=str(panel_y),
        width=str(panel_width),
        height=str(panel_height),
        **{"as": "geometry"},
    )

    panel_title = ET.SubElement(
        root,
        "mxCell",
        id="ctx-flow-explanation-title",
        value="Data Flow Steps",
        style="fontSize=12;fontStyle=1;fillColor=none;strokeColor=none;align=center;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(
        panel_title,
        "mxGeometry",
        x=str(panel_x + 10),
        y=str(panel_y + 10),
        width=str(panel_width - 20),
        height="24",
        **{"as": "geometry"},
    )

    flow_y = panel_y + 42
    for flow_info in flow_explanations[:8]:
        flow_text = f"Flow {flow_info['num']}: {flow_info['from']} -> {flow_info['to']}"
        if flow_info["label"]:
            flow_text += f"\n{flow_info['label']}"

        flow_description = ET.SubElement(
            root,
            "mxCell",
            id=f"ctx-flow-desc-{flow_info['num']}",
            value=flow_text,
            style="fontSize=9;align=left;verticalAlign=top;fillColor=none;strokeColor=none;whiteSpace=wrap;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(
            flow_description,
            "mxGeometry",
            x=str(panel_x + 8),
            y=str(flow_y),
            width=str(panel_width - 16),
            height="60",
            **{"as": "geometry"},
        )
        flow_y += 66

    # Add legend
    legend_y = 750
    legend = ET.SubElement(
        root,
        "mxCell",
        id="legend",
        value="Legend:",
        style="fontSize=10;fontStyle=1;align=left;fillColor=none;strokeColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(legend, "mxGeometry", x="300", y=str(legend_y), width="100", height="20", **{"as": "geometry"})

    legend_items = [
        ("User", "#fff4e6", "#ff7700", "220", str(legend_y + 25)),
        ("Internal On-Prem System", "#f0f0f0", "#666666", "390", str(legend_y + 25)),
        ("Service", "#e6f3ff", "#0066cc", "620", str(legend_y + 25)),
        ("Target System", "#4da6ff", "#003d99", "800", str(legend_y + 25)),
    ]

    for label, fill, stroke, lx, ly in legend_items:
        box = ET.SubElement(
            root,
            "mxCell",
            id=f"legend-{label}",
            value="",
            style=f"rounded=0;whiteSpace=wrap;fillColor={fill};strokeColor={stroke};strokeWidth=1;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(box, "mxGeometry", x=lx, y=ly, width="20", height="20", **{"as": "geometry"})

        text = ET.SubElement(
            root,
            "mxCell",
            id=f"legend-{label}-text",
            value=label,
            style="fontSize=9;align=left;fillColor=none;strokeColor=none;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(text, "mxGeometry", x=str(int(lx) + 25), y=ly, width="100", height="20", **{"as": "geometry"})

    arrow_legend = ET.SubElement(
        root,
        "mxCell",
        id="legend-arrow-text",
        value="Arrow semantics: Source → Target (Out), Target → External (In), ↔ Bi-directional (Both)",
        style="fontSize=9;align=left;fillColor=none;strokeColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(arrow_legend, "mxGeometry", x="220", y=str(legend_y + 58), width="760", height="20", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


# ── Placeholder Replacement ────────────────────────────────────────────────

_DRAWIO_MACRO = (
    '<ac:structured-macro ac:name="drawio" ac:schema-version="1">'
    '<ac:parameter ac:name="border">true</ac:parameter>'
    '<ac:parameter ac:name="viewerToolbar">true</ac:parameter>'
    '<ac:parameter ac:name="simpleViewer">false</ac:parameter>'
    '<ac:parameter ac:name="width">100%</ac:parameter>'
    '<ac:parameter ac:name="height">1280</ac:parameter>'
    '<ac:parameter ac:name="zoom">125</ac:parameter>'
    '<ac:parameter ac:name="editable">true</ac:parameter>'
    '<ac:parameter ac:name="diagramDisplayName">{display_name}</ac:parameter>'
    '<ac:parameter ac:name="diagramName">{filename}</ac:parameter>'
    '<ac:parameter ac:name="pageId">{page_id}</ac:parameter>'
    "</ac:structured-macro>"
)


def replace_placeholder(html: str, diagram_key: str,
                         filename: str, display_name: str, page_id: str) -> str:
    macro = _DRAWIO_MACRO.format(
        display_name=display_name, filename=filename, page_id=page_id
    )

    # Tolerant placeholder token matcher:
    # [[DIAGRAM:context-view]], [[ DIAGRAM : context-view ]], mixed case, etc.
    token_pattern = re.compile(
        r"\[\[\s*diagram\s*:\s*" + re.escape(diagram_key) + r"\s*\]\]",
        re.IGNORECASE,
    )

    # First, replace wrapped paragraph variants if present.
    wrapped_pattern = re.compile(
        r"<p[^>]*>\s*(?:<strong[^>]*>\s*)?"
        + token_pattern.pattern
        + r"(?:\s*</strong>)?\s*</p>",
        re.IGNORECASE,
    )
    new_html, wrapped_count = wrapped_pattern.subn(macro, html)

    # Then, replace any remaining plain token occurrences anywhere in storage HTML.
    new_html, token_count = token_pattern.subn(macro, new_html)

    if wrapped_count > 0 or token_count > 0:
        return new_html

    # Fallback 1: update an existing draw.io macro that already points to this filename.
    existing_macro_pattern = re.compile(
        r'<ac:structured-macro[^>]*ac:name="drawio"[^>]*>.*?'
        r'<ac:parameter\s+ac:name="diagramName">\s*'
        + re.escape(filename)
        + r'\s*</ac:parameter>.*?</ac:structured-macro>',
        re.IGNORECASE | re.DOTALL,
    )
    new_html, existing_count = existing_macro_pattern.subn(macro, new_html, count=1)
    if existing_count > 0:
        return new_html

    # Fallback 2: insert macro under matching section heading (flexible heading matching).
    # Try exact display name match first
    heading_pattern = re.compile(
        r'(<h[23][^>]*>[^<]*' + re.escape(display_name) + r'[^<]*</h[23]>)',
        re.IGNORECASE,
    )
    if heading_pattern.search(new_html):
        new_html = heading_pattern.sub(r'\1\n<p>' + macro + r'</p>', new_html, count=1)
        return new_html

    # Fallback 3: Try fuzzy heading match (match diagram name keywords in heading)
    diagram_words = diagram_key.replace('-', ' ').split()
    if diagram_words:
        first_word = diagram_words[0]
        fuzzy_pattern = re.compile(
            r'(<h[23][^>]*>[^<]*' + re.escape(first_word.title()) + r'[^<]*</h[23]>)',
            re.IGNORECASE,
        )
        if fuzzy_pattern.search(new_html):
            new_html = fuzzy_pattern.sub(r'\1\n<p>' + macro + r'</p>', new_html, count=1)
            return new_html

    # Fallback 4: If no heading found, add macro before "Local Diagram Files" or at the end
    insert_before_pattern = re.compile(r'(<h2[^>]*>Local Diagram Files</h2>)', re.IGNORECASE)
    if insert_before_pattern.search(new_html):
        new_html = insert_before_pattern.sub(r'<p>' + macro + r'</p>\n\1', new_html, count=1)
        return new_html

    print(f"  Warning: could not place diagram macro for '{diagram_key}' - will attempt to update on next run.")
    return new_html


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    base_url  = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    source_page_id = os.getenv("CONFLUENCE_SOURCE_PAGE_ID") or os.getenv("CONFLUENCE_ARCHITECTURE_PAGE_ID")
    source_title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "High-level Design (HLD) Solution Architecture Template")
    target_page_id = os.getenv("CONFLUENCE_TARGET_PAGE_ID")
    target_title = os.getenv("CONFLUENCE_TARGET_PAGE_TITLE", "Architecture Diagrams")

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    # ── Find source page for table parsing
    if source_page_id:
        source_page = get_page_by_id(session, base_url, source_page_id)
    else:
        print(f"Searching for source page '{source_title}' in space '{space_key}'...")
        source_page = find_page_by_title(session, base_url, space_key, source_title)

    # ── Find target page for diagram embedding
    if target_page_id:
        target_page = get_page_by_id(session, base_url, target_page_id)
    else:
        print(f"Searching for target page '{target_title}' in space '{space_key}'...")
        target_page = find_page_by_title(session, base_url, space_key, target_title)

    source_page_id = source_page["id"]
    source_body_html = source_page["body"]["storage"]["value"]
    target_page_id = target_page["id"]
    version_number = target_page["version"]["number"]
    target_page_title = target_page["title"]
    target_body_html = target_page["body"]["storage"]["value"]

    # ── Load synced template to preserve manual edits (if available)
    synced_html = load_diagrams_synced_template()
    if synced_html and is_valid_diagrams_template(synced_html):
        print("\n  Using synced Architecture Diagrams template (preserves your manual edits)")
        target_body_html = synced_html
    else:
        print("\n  Synced template missing or malformed; rebuilding a clean diagrams layout")
        target_body_html = build_default_diagrams_template()

    print(f"\nSource: '{source_page['title']}'  (ID: {source_page_id})")
    print(f"Target: '{target_page_title}'  (ID: {target_page_id}, version: {version_number})")

    # ── Parse tables
    components  = parse_components(source_body_html)
    connections = parse_connections(source_body_html)
    dataflows   = parse_dataflows(source_body_html)
    datasets = parse_dataset_inventory(source_body_html)
    dataset_relationships = parse_dataset_relationships(source_body_html)
    context_entities = parse_context_entities(source_body_html)
    network_segmentation = parse_network_segmentation(source_body_html)
    inherited_context = build_inherited_diagram_context(components, connections, dataflows, context_entities)
    components = inherited_context["components"]
    connections = inherited_context["connections"]
    dataflows = inherited_context["dataflows"]
    context_entities = inherited_context["context_entities"]

    # ── EDAP pattern detection and automatic diagram enrichment
    # Parse optional explicit pattern IDs from env (comma-separated, e.g. "EDAP-INT-01,EDAP-INT-03")
    explicit_edap = [p.strip() for p in os.getenv("EDAP_PATTERN_IDS", "").split(",") if p.strip()]
    if EDAP_KB_AVAILABLE:
        edap_patterns = detect_edap_patterns(components, connections, dataflows, context_entities, explicit_edap or None)
        if edap_patterns:
            print(f"\n  {build_edap_integration_summary(edap_patterns)}")
            components        = inject_edap_into_components(components, edap_patterns)
            connections       = inject_edap_into_connections(connections, edap_patterns)
            dataflows         = inject_edap_into_dataflows(dataflows, edap_patterns)
            context_entities  = inject_edap_into_context_entities(context_entities, edap_patterns)
        else:
            print("\n  No EDAP integration patterns detected — diagrams will reflect project data only.")
            print("  Tip: set EDAP_PATTERN_IDS=EDAP-INT-01,EDAP-INT-03 in .env to force specific patterns.")
    else:
        edap_patterns = []

    # ── UKHSA patterns detection and automatic diagram enrichment
    # Supports explicit override via UKHSA_PATTERN_IDS env var (comma-separated IDs e.g. "1A,3C,TSA-NET-01")
    explicit_ukhsa = [p.strip() for p in os.getenv("UKHSA_PATTERN_IDS", "").split(",") if p.strip()]
    if UKHSA_KB_AVAILABLE:
        ukhsa_patterns = detect_ukhsa_patterns(components, connections, dataflows, context_entities, explicit_ukhsa or None)
        if ukhsa_patterns:
            print(f"\n  {build_ukhsa_pattern_summary(ukhsa_patterns)}")
            components        = inject_ukhsa_into_components(components, ukhsa_patterns)
            connections       = inject_ukhsa_into_connections(connections, ukhsa_patterns)
            dataflows         = inject_ukhsa_into_dataflows(dataflows, ukhsa_patterns)
            context_entities  = inject_ukhsa_into_context_entities(context_entities, ukhsa_patterns)
        else:
            print("\n  No UKHSA patterns detected — diagrams will reflect project data only.")
            print("  Tip: set UKHSA_PATTERN_IDS=1A,3C,UKHSA-INF-01 in .env to force specific patterns.")
    else:
        ukhsa_patterns = []

    auth_flow_rules = derive_auth_flow_rules(components, connections, dataflows, context_entities)

    # Debug: print context entities
    if context_entities:
        print(f"  Context Entities Found ({len(context_entities)}):")
        for i, entity in enumerate(context_entities):
            print(f"    [{i}] {entity['name']} ({entity['type']}) - {entity['direction']}")

    print(f"  Components: {len(components)} | "
          f"Connections: {len(connections)} | "
          f"Data flows:  {len(dataflows)} | "
          f"Datasets: {len(datasets)} | "
          f"Dataset relationships: {len(dataset_relationships)} | "
          f"Context entities: {len(context_entities)} | "
          f"Network segmentation params: {len(network_segmentation)}")
    print(
        "  Auth rules: "
        f"sequence={auth_flow_rules['flow_mode']} | "
        f"mfa={auth_flow_rules['include_mfa_challenge']} | "
        f"token_refresh={auth_flow_rules['include_token_refresh']} | "
        f"reauth_loop={auth_flow_rules['include_reauth_on_validation_failure']}"
    )

    if not components and not dataflows and not datasets:
        print(
            "\nNo data found in source tables. Falling back to previously generated local draw.io files if available."
        )

    updated_html = target_body_html

    # ── High-level Architecture diagram (with AWS icons if available)
    if components:
        print("\nGenerating High-level Architecture Diagram...")
        if AWS_DIAGRAMS_AVAILABLE:
            arch_xml = generate_aws_architecture_with_real_icons(components, connections)
            print("  ✓ Using AWS-enhanced architecture diagram with service icons")
        else:
            arch_xml = generate_architecture_drawio(components, connections)
            print("  ⚠ Enhanced diagrams not available, using basic diagram")
        save_local_drawio("solution-architecture.drawio", arch_xml)
        upload_attachment(session, base_url, target_page_id,
                          "solution-architecture.drawio", arch_xml)
        updated_html = replace_placeholder(
            updated_html, "solution-architecture",
            "solution-architecture.drawio", "High-level Architecture Diagram", target_page_id,
        )
    else:
        arch_xml = load_local_drawio("solution-architecture.drawio")
        if arch_xml:
            print("\nReusing existing local High-level Architecture Diagram...")
            upload_attachment(session, base_url, target_page_id,
                              "solution-architecture.drawio", arch_xml)
            updated_html = replace_placeholder(
                updated_html, "solution-architecture",
                "solution-architecture.drawio", "High-level Architecture Diagram", target_page_id,
            )

    # ── Data Flow Diagram
    if dataflows:
        print("\nGenerating Data Flow Diagram...")
        dfd_xml = generate_dfd_drawio(dataflows)
        save_local_drawio("data-flow-diagram.drawio", dfd_xml)
        upload_attachment(session, base_url, target_page_id,
                          "data-flow-diagram.drawio", dfd_xml)
        updated_html = replace_placeholder(
            updated_html, "data-flow",
            "data-flow-diagram.drawio", "Data Flow Diagram", target_page_id,
        )
    else:
        dfd_xml = load_local_drawio("data-flow-diagram.drawio")
        if dfd_xml:
            print("\nReusing existing local Data Flow Diagram...")
            upload_attachment(session, base_url, target_page_id,
                              "data-flow-diagram.drawio", dfd_xml)
            updated_html = replace_placeholder(
                updated_html, "data-flow",
                "data-flow-diagram.drawio", "Data Flow Diagram", target_page_id,
            )

    # ── Dataset Relationship Diagram
    if datasets:
        print("\nGenerating Dataset Relationship Diagram...")
        ds_xml = generate_dataset_relationship_drawio(datasets, dataset_relationships)
        save_local_drawio("data-relationship-diagram.drawio", ds_xml)
        upload_attachment(session, base_url, target_page_id, "data-relationship-diagram.drawio", ds_xml)
        updated_html = replace_placeholder(
            updated_html,
            "data-relationship",
            "data-relationship-diagram.drawio",
            "Dataset Relationship Diagram",
            target_page_id,
        )
    else:
        ds_xml = load_local_drawio("data-relationship-diagram.drawio")
        if ds_xml:
            print("\nReusing existing local Dataset Relationship Diagram...")
            upload_attachment(session, base_url, target_page_id, "data-relationship-diagram.drawio", ds_xml)
            updated_html = replace_placeholder(
                updated_html,
                "data-relationship",
                "data-relationship-diagram.drawio",
                "Dataset Relationship Diagram",
                target_page_id,
            )

    # Ensure required Context Entities are present for HLD on-prem data path.
    required_context_entities = [
        {"name": "On-Prem Business App", "type": "System", "interaction": "Produces daily surveillance files via SFTP export", "direction": "Out"},
        {"name": "On-Prem SFTP Server", "type": "System", "interaction": "Stages and relays files for secure cloud transfer", "direction": "Both"},
        {"name": "UKHSA Intra Identity (Azure Entra ID)", "type": "Service", "interaction": "Provides SSO and MFA authentication for transfer users and support access", "direction": "Both"},
        {"name": "Data Analyst Team", "type": "User", "interaction": "Consumes validated data outputs", "direction": "In"},
        {"name": "Security Operations", "type": "Service", "interaction": "Reviews logs and alerts", "direction": "In"},
    ]
    required_names = {ent["name"] for ent in required_context_entities}
    parsed_names = {ent.get("name", "") for ent in context_entities}
    if not required_names.issubset(parsed_names):
        missing = sorted(required_names - parsed_names)
        print(f"  Context entities fallback applied (missing from source parse: {', '.join(missing)})")
        context_entities = required_context_entities

    # ── Context View Diagram
    if context_entities:
        print("\nGenerating Context View Diagram...")
        context_xml = generate_context_view_drawio(source_page["title"], context_entities)
        save_local_drawio("context-view-diagram.drawio", context_xml)
        upload_attachment(session, base_url, target_page_id, "context-view-diagram.drawio", context_xml)
        updated_html = replace_placeholder(
            updated_html,
            "context-view",
            "context-view-diagram.drawio",
            "Context View Diagram",
            target_page_id,
        )
    else:
        context_xml = load_local_drawio("context-view-diagram.drawio")
        if context_xml:
            print("\nReusing existing local Context View Diagram...")
            upload_attachment(session, base_url, target_page_id, "context-view-diagram.drawio", context_xml)
            updated_html = replace_placeholder(
                updated_html,
                "context-view",
                "context-view-diagram.drawio",
                "Context View Diagram",
                target_page_id,
            )

    # ── Logical View (C4 Level 2 - Container Diagram)
    if components:
        print("\nGenerating Logical View Diagram (C4 Level 2 - Container)...")
        logical_xml = generate_c4_logical_view_drawio(source_page["title"], components, connections, context_entities)
        save_local_drawio("logical-view-diagram.drawio", logical_xml)
        upload_attachment(session, base_url, target_page_id, "logical-view-diagram.drawio", logical_xml)
        updated_html = replace_placeholder(
            updated_html,
            "logical-view",
            "logical-view-diagram.drawio",
            "Logical View Diagram",
            target_page_id,
        )
    else:
        logical_xml = load_local_drawio("logical-view-diagram.drawio")
        if logical_xml:
            print("\nReusing existing local Logical View Diagram...")
            upload_attachment(session, base_url, target_page_id, "logical-view-diagram.drawio", logical_xml)
            updated_html = replace_placeholder(
                updated_html,
                "logical-view",
                "logical-view-diagram.drawio",
                "Logical View Diagram",
                target_page_id,
            )

    # ── ENHANCED DIAGRAMS: Authentication Flow, Network Segregation, AWS Architecture Details
    if AWS_DIAGRAMS_AVAILABLE:
        print("\n" + "="*70)
        print("ENHANCED DIAGRAMS: Authentication Flows & Network Architecture")
        print("="*70)
        
        # Authentication Flow Diagram
        print("\nGenerating Authentication Flow Diagram...")
        print("  Showing: User → WebApp → API → Azure Network → Azure Entra ID → Service → Database")
        print("  Steps: SSO/MFA federated token exchange and secure data access")
        auth_xml = generate_authentication_flow_diagram(auth_flow_rules)
        save_local_drawio("authentication-flow-diagram.drawio", auth_xml)
        upload_attachment(session, base_url, target_page_id,
                          "authentication-flow-diagram.drawio", auth_xml)
        updated_html = replace_placeholder(
            updated_html, "authentication-flow",
            "authentication-flow-diagram.drawio", "Authentication Flow", target_page_id,
        )
        
        # Network Segregation Diagram
        print("\nGenerating Network Segregation Diagram...")
        print("  Showing: VPC → Subnets → Security Groups → Service routing")
        print("  Segments: Internet → IGW → Public/Private/Data subnets with SGs")
        if network_segmentation:
            print(f"  Using main-page network segmentation inputs ({len(network_segmentation)} values)")
        else:
            print("  Using default segmentation values (add 'Network Segmentation Inputs' table on main page)")
        net_xml = generate_network_segregation_diagram(network_segmentation)
        save_local_drawio("network-segregation-diagram.drawio", net_xml)
        upload_attachment(session, base_url, target_page_id,
                          "network-segregation-diagram.drawio", net_xml)
        updated_html = replace_placeholder(
            updated_html, "network-segregation",
            "network-segregation-diagram.drawio", "Network Segregation", target_page_id,
        )
        print("\nEnhanced diagrams generated successfully!")

    # ── Write the page back
    print("\nUpdating Confluence page with embedded diagrams...")
    update_page_body(session, base_url, target_page_id, version_number, target_page_title, updated_html)
    
    # ── Save synced template to preserve manual edits on future runs
    save_diagrams_synced_template(updated_html)
    
    print("\nDone! Diagrams are embedded on the target page and remain editable via draw.io on Confluence and from local .drawio files in output/generated.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
