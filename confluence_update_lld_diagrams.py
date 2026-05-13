"""
confluence_update_lld_diagrams.py
--------------------------------
Creates or updates the Low Level Design (LLD) page with detailed diagram sections,
then generates and embeds detailed draw.io diagrams covering:
- Full component and service architecture
- Network and service-to-service connections
- Security access connections (authn/authz/encryption)
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
from aws_architecture_diagram_generator import get_icon_url, _to_drawio_image_uri

# Import EDAP knowledge base for automatic EDAP-integration LLD diagram enrichment
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

load_dotenv()

LLD_HEADING_TEXT = "Low-Level Design (LLD) Solution Architecture Template"


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


def _make_request(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    api_token = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    verify = kwargs.pop("verify", get_tls_verify())
    base_headers = dict(kwargs.pop("headers", {}) or {})

    def _request_with_retry(req_headers: dict, req_auth=None) -> requests.Response:
        try:
            return session.request(method, url, verify=verify, headers=req_headers, auth=req_auth, **kwargs)
        except requests.exceptions.SSLError as exc:
            if "UNEXPECTED_EOF_WHILE_READING" not in str(exc):
                raise
            retry_headers = dict(req_headers)
            retry_headers["Connection"] = "close"
            return session.request(method, url, verify=verify, headers=retry_headers, auth=req_auth, **kwargs)

    if api_token:
        bearer_headers = dict(base_headers)
        bearer_headers["Authorization"] = f"Bearer {api_token}"
        try:
            resp = _request_with_retry(bearer_headers, req_auth=None)
            if resp.status_code != 403:
                return resp
        except requests.RequestException:
            pass

    if user_email and api_token:
        return _request_with_retry(base_headers, req_auth=HTTPBasicAuth(user_email, api_token))

    return _request_with_retry(base_headers, req_auth=None)


def _accept_headers() -> dict:
    return {"Accept": "application/json"}


def _json_headers() -> dict:
    return {"Accept": "application/json", "Content-Type": "application/json"}


def find_page_by_title(session: requests.Session, base_url: str, space_key: str, title: str) -> dict:
    resp = _make_request(
        session,
        "GET",
        f"{base_url}/rest/api/content",
        params={"spaceKey": space_key, "title": title, "expand": "body.storage,version"},
        headers=_accept_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        raise ValueError(f"Page not found: '{title}' in space '{space_key}'")
    return results[0]


def get_page_by_id(session: requests.Session, base_url: str, page_id: str) -> dict:
    resp = _make_request(
        session,
        "GET",
        f"{base_url}/rest/api/content/{page_id}",
        params={"expand": "body.storage,version"},
        headers=_accept_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def create_child_page(session: requests.Session, base_url: str, space_key: str, parent_page_id: str, title: str, body_html: str) -> dict:
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "ancestors": [{"id": parent_page_id}],
        "body": {"storage": {"value": body_html, "representation": "storage"}},
    }
    resp = _make_request(
        session,
        "POST",
        f"{base_url}/rest/api/content",
        data=json.dumps(payload),
        headers=_json_headers(),
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create page: {resp.status_code} {resp.text}")
    return resp.json()


def update_page_body(session: requests.Session, base_url: str, page_id: str, version_number: int, title: str, body_html: str, minor_edit: bool = False) -> dict:
    payload = {
        "version": {"number": version_number + 1, "minorEdit": minor_edit},
        "title": title,
        "type": "page",
        "body": {"storage": {"value": body_html, "representation": "storage"}},
    }
    resp = _make_request(
        session,
        "PUT",
        f"{base_url}/rest/api/content/{page_id}",
        data=json.dumps(payload),
        headers=_json_headers(),
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to update page: {resp.status_code} {resp.text}")
    return resp.json()


def upload_attachment(session: requests.Session, base_url: str, page_id: str, filename: str, xml_content: str) -> None:
    url = f"{base_url}/rest/api/content/{page_id}/child/attachment"
    file_bytes = xml_content.encode("utf-8")

    check = _make_request(
        session,
        "GET",
        url,
        params={"filename": filename},
        headers=_accept_headers(),
        timeout=30,
    )
    existing = check.json().get("results", []) if check.status_code == 200 else []

    def _make_files_payload():
        return {"file": (filename, BytesIO(file_bytes), "application/octet-stream")}

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
    out_dir = os.path.join("output", "generated")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, filename)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"  Local editable source: {out_file}")


def _find_table_after_heading(soup: BeautifulSoup, heading_text: str):
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if heading_text.lower() in tag.get_text(strip=True).lower():
            sibling = tag.find_next_sibling()
            while sibling and sibling.name in ("p", "ul", "ol", "div"):
                sibling = sibling.find_next_sibling()
            if sibling and sibling.name == "table":
                return sibling
    return None


def _table_rows(table) -> list[list[str]]:
    rows: list[list[str]] = []
    for i, tr in enumerate(table.find_all("tr")):
        if i == 0:
            continue
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if any(cells):
            rows.append(cells)
    return rows


def parse_lld_components(body_html: str) -> list[dict]:
    soup = BeautifulSoup(body_html, "html.parser")
    table = _find_table_after_heading(soup, "Detailed Component Architecture")
    if not table:
        return []
    items = []
    for row in _table_rows(table):
        name = row[0] if len(row) > 0 else ""
        if not name:
            continue
        items.append(
            {
                "name": name,
                "layer": row[1] if len(row) > 1 else "Application",
                "service": row[2] if len(row) > 2 else "",
                "network_zone": row[3] if len(row) > 3 else "",
                "purpose": row[4] if len(row) > 4 else "",
            }
        )
    return items


def parse_lld_connections(body_html: str) -> list[dict]:
    soup = BeautifulSoup(body_html, "html.parser")
    table = _find_table_after_heading(soup, "Detailed Network and Service Connections")
    if not table:
        return []
    items = []
    for row in _table_rows(table):
        source = row[0] if len(row) > 0 else ""
        target = row[1] if len(row) > 1 else ""
        if not source or not target:
            continue
        items.append(
            {
                "source": source,
                "target": target,
                "protocol": row[2] if len(row) > 2 else "",
                "port": row[3] if len(row) > 3 else "",
                "network_path": row[4] if len(row) > 4 else "",
                "auth": row[5] if len(row) > 5 else "",
            }
        )
    return items


def parse_lld_security_access(body_html: str) -> list[dict]:
    soup = BeautifulSoup(body_html, "html.parser")
    table = _find_table_after_heading(soup, "Security Access Connections")
    if not table:
        return []
    items = []
    for row in _table_rows(table):
        actor = row[0] if len(row) > 0 else ""
        target = row[1] if len(row) > 1 else ""
        if not actor or not target:
            continue
        items.append(
            {
                "actor": actor,
                "target": target,
                "access_type": row[2] if len(row) > 2 else "",
                "authn": row[3] if len(row) > 3 else "",
                "authz": row[4] if len(row) > 4 else "",
                "secret": row[5] if len(row) > 5 else "",
                "encryption": row[6] if len(row) > 6 else "",
            }
        )
    return items


def parse_main_components_and_connections(body_html: str) -> tuple[list[dict], list[dict]]:
    soup = BeautifulSoup(body_html, "html.parser")

    comp_table = _find_table_after_heading(soup, "Architecture Components")
    conn_table = _find_table_after_heading(soup, "Architecture Connections")

    components: list[dict] = []
    connections: list[dict] = []

    if comp_table:
        for row in _table_rows(comp_table):
            name = row[1] if len(row) > 1 else ""
            if not name:
                continue
            components.append(
                {
                    "name": name,
                    "layer": row[2] if len(row) > 2 else "Application",
                    "service": row[3] if len(row) > 3 else "",
                    "network_zone": "",
                    "purpose": row[5] if len(row) > 5 else "",
                }
            )

    if conn_table:
        for row in _table_rows(conn_table):
            source = row[0] if len(row) > 0 else ""
            target = row[1] if len(row) > 1 else ""
            if not source or not target:
                continue
            connections.append(
                {
                    "source": source,
                    "target": target,
                    "protocol": row[2] if len(row) > 2 else "",
                    "port": row[3] if len(row) > 3 else "",
                    "network_path": "",
                    "auth": row[3] if len(row) > 3 else "",
                }
            )

    return components, connections


def parse_main_dataflows(body_html: str) -> list[dict]:
    soup = BeautifulSoup(body_html, "html.parser")
    flow_table = _find_table_after_heading(soup, "Data Flow Entries")
    flows: list[dict] = []
    if not flow_table:
        return flows

    for row in _table_rows(flow_table):
        source = row[1] if len(row) > 1 else ""
        target = row[2] if len(row) > 2 else ""
        if not source or not target:
            continue
        flows.append(
            {
                "id": row[0] if len(row) > 0 else "",
                "source": source,
                "target": target,
                "data": row[3] if len(row) > 3 else "",
                "format": row[4] if len(row) > 4 else "",
                "protocol": row[5] if len(row) > 5 else "",
                "frequency": row[6] if len(row) > 6 else "",
                "sensitivity": row[7] if len(row) > 7 else "",
            }
        )
    return flows


def parse_main_context_entities(body_html: str) -> list[dict]:
    soup = BeautifulSoup(body_html, "html.parser")
    table = _find_table_after_heading(soup, "Context Entities")
    if not table:
        return []

    entities: list[dict] = []
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


def parse_main_network_segmentation(body_html: str) -> dict:
    soup = BeautifulSoup(body_html, "html.parser")
    table = _find_table_after_heading(soup, "Network Segmentation Inputs")
    if not table:
        return {}

    key_map = {
        "public subnet cidr": "public_subnet_cidr",
        "private subnet cidr": "private_subnet_cidr",
        "data subnet cidr": "data_subnet_cidr",
        "public ingress path": "public_ingress",
        "private ingress path": "private_ingress",
        "public route": "route_public",
        "private route": "route_private",
    }

    parsed: dict[str, str] = {}
    for row in _table_rows(table):
        param = (row[0] if len(row) > 0 else "").strip().lower()
        value = (row[1] if len(row) > 1 else "").strip()
        mapped = key_map.get(param)
        if mapped and value:
            parsed[mapped] = value
    return parsed


def _normalise_lld_layer(layer: str) -> str:
    lc = (layer or "").strip().lower()
    if "edge" in lc:
        return "Edge"
    if "network" in lc:
        return "Network"
    if "platform" in lc:
        return "Platform"
    if "data" in lc:
        return "Data"
    if "security" in lc:
        return "Security"
    return "Application"


def _infer_network_zone(component: dict, segmentation: dict) -> str:
    text = " ".join(
        [
            component.get("name", "") or "",
            component.get("service", "") or "",
            component.get("purpose", "") or "",
            component.get("layer", "") or "",
        ]
    ).lower()

    if any(k in text for k in ["on-prem", "on prem", "onprem", "sftp", "external", "internet", "user"]):
        return "External / On-Prem"
    if any(k in text for k in ["api gateway", "gateway", "waf", "alb", "public", "ingress"]):
        return f"Public Subnet ({segmentation.get('public_subnet_cidr', 'CIDR TBC')})"
    if any(k in text for k in ["database", "rds", "data", "warehouse", "bucket", "storage"]):
        return f"Data Subnet ({segmentation.get('data_subnet_cidr', 'CIDR TBC')})"
    return f"Private Subnet ({segmentation.get('private_subnet_cidr', 'CIDR TBC')})"


def _parse_connection_label_fields(label: str, segmentation: dict) -> tuple[str, str, str, str]:
    txt = (label or "").strip()
    lower = txt.lower()

    protocol = ""
    port = ""
    auth = ""
    network_path = ""

    if any(k in lower for k in ["https", "tls"]):
        protocol = "HTTPS/TLS"
        port = "443"
    elif "sftp" in lower:
        protocol = "SFTP"
        port = "22"
    elif "sql" in lower:
        protocol = "SQL/TLS"
        port = "3306"

    if any(k in lower for k in ["mfa", "entra", "oidc", "oauth", "token", "sso"]):
        auth = "OIDC/OAuth2 + MFA"
    elif any(k in lower for k in ["mtls", "mutual tls"]):
        auth = "mTLS"
    elif any(k in lower for k in ["managed identity", "iam", "role"]):
        auth = "Managed Identity"

    if any(k in lower for k in ["internet", "public", "ingress"]):
        network_path = segmentation.get("public_ingress", "Internet/Public Path")
    elif any(k in lower for k in ["private", "internal", "vpc", "vnet"]):
        network_path = segmentation.get("private_ingress", "Private Network Path")
    elif any(k in lower for k in ["sftp", "site-to-site", "vpn", "direct connect"]):
        network_path = "Private Connectivity / VPN"

    return protocol, port, network_path, auth


def build_inherited_design_context(main_html: str) -> dict:
    main_components, main_connections = parse_main_components_and_connections(main_html)
    main_dataflows = parse_main_dataflows(main_html)
    context_entities = parse_main_context_entities(main_html)
    segmentation = parse_main_network_segmentation(main_html)

    component_map: dict[str, dict] = {}
    for comp in main_components:
        name = (comp.get("name") or "").strip()
        if not name:
            continue
        layer = _normalise_lld_layer(comp.get("layer", "Application"))
        enriched = {
            "name": name,
            "layer": layer,
            "service": comp.get("service", ""),
            "purpose": comp.get("purpose", ""),
            "network_zone": _infer_network_zone({**comp, "layer": layer}, segmentation),
        }
        component_map[name.lower()] = enriched

    for entity in context_entities:
        ename = (entity.get("name") or "").strip()
        if not ename:
            continue
        key = ename.lower()
        if key in component_map:
            continue
        component_map[key] = {
            "name": ename,
            "layer": "Edge",
            "service": entity.get("type", "External Entity"),
            "purpose": entity.get("interaction", ""),
            "network_zone": "External / On-Prem",
        }

    inherited_connections: list[dict] = []
    for conn in main_connections:
        src = (conn.get("source") or conn.get("from") or "").strip()
        tgt = (conn.get("target") or conn.get("to") or "").strip()
        if not src or not tgt:
            continue
        label = conn.get("label", "")
        protocol, port, net_path, auth = _parse_connection_label_fields(label, segmentation)
        inherited_connections.append(
            {
                "source": src,
                "target": tgt,
                "protocol": conn.get("protocol", "") or protocol,
                "port": conn.get("port", "") or port,
                "network_path": conn.get("network_path", "") or net_path,
                "auth": conn.get("auth", "") or auth,
            }
        )

    for flow in main_dataflows:
        src = (flow.get("source") or "").strip()
        tgt = (flow.get("target") or "").strip()
        if not src or not tgt:
            continue
        if any(c["source"].lower() == src.lower() and c["target"].lower() == tgt.lower() for c in inherited_connections):
            continue
        inherited_connections.append(
            {
                "source": src,
                "target": tgt,
                "protocol": flow.get("protocol", ""),
                "port": "",
                "network_path": "Inferred from Data Flow Entries",
                "auth": "",
            }
        )

    for conn in inherited_connections:
        for endpoint in [conn.get("source", ""), conn.get("target", "")]:
            k = endpoint.lower().strip()
            if endpoint and k not in component_map:
                component_map[k] = {
                    "name": endpoint,
                    "layer": "Application",
                    "service": "Inherited from connection",
                    "purpose": "Added to preserve end-to-end path",
                    "network_zone": _infer_network_zone({"name": endpoint, "layer": "Application"}, segmentation),
                }

    inherited_security = derive_security_rows_from_connections(inherited_connections)

    return {
        "components": list(component_map.values()),
        "connections": inherited_connections,
        "security_rows": inherited_security,
        "segmentation": segmentation,
        "context_entities": context_entities,
        "dataflows": main_dataflows,
    }


def _replace_table_rows(soup: BeautifulSoup, table, rows: list[list[str]]) -> int:
    if not table:
        return 0

    body = table.find("tbody")
    if body is None:
        body = soup.new_tag("tbody")
        table.append(body)

    for tr in body.find_all("tr"):
        tr.decompose()

    for row in rows:
        tr = soup.new_tag("tr")
        for value in row:
            td = soup.new_tag("td")
            td.string = value
            tr.append(td)
        body.append(tr)

    return len(rows)


def apply_lld_color_theme(body_html: str) -> str:
    soup = BeautifulSoup(body_html, "html.parser")

    h1 = soup.find("h1")
    if h1:
        h1.string = LLD_HEADING_TEXT
        h1["style"] = "color: #003366; border-bottom: 4px solid #003366; padding-bottom: 10px;"
    else:
        new_h1 = soup.new_tag("h1")
        new_h1.string = LLD_HEADING_TEXT
        new_h1["style"] = "color: #003366; border-bottom: 4px solid #003366; padding-bottom: 10px;"
        if soup.body:
            soup.body.insert(0, new_h1)
        else:
            soup.insert(0, new_h1)

    h2_palette = ["#0052CC", "#6B46C1", "#D97706", "#DC2626", "#16A34A", "#9333EA", "#0891B2", "#B91C1C"]
    h3_palette = ["#2563EB", "#7C3AED", "#B45309", "#BE123C", "#059669", "#7E22CE", "#0369A1", "#991B1B"]

    for idx, tag in enumerate(soup.find_all("h2")):
        color = h2_palette[idx % len(h2_palette)]
        tag["style"] = f"color: {color}; border-left: 5px solid {color}; padding-left: 10px;"

    for idx, tag in enumerate(soup.find_all("h3")):
        color = h3_palette[idx % len(h3_palette)]
        tag["style"] = f"color: {color}; border-bottom: 2px solid {color}; padding-bottom: 4px;"

    return str(soup)


def sync_main_to_lld_tables(lld_html: str, main_html: str) -> tuple[str, dict]:
    inherited = build_inherited_design_context(main_html)
    main_components = inherited["components"]
    main_connections = inherited["connections"]
    main_dataflows = inherited["dataflows"]
    derived_security = inherited["security_rows"]

    lld_soup = BeautifulSoup(lld_html, "html.parser")

    comp_rows = [
        [
            c.get("name", ""),
            c.get("layer", ""),
            c.get("service", ""),
            c.get("network_zone", "TBC"),
            c.get("purpose", ""),
        ]
        for c in main_components
    ]
    conn_rows = [
        [
            c.get("source", ""),
            c.get("target", ""),
            c.get("protocol", ""),
            c.get("port", ""),
            c.get("network_path", "TBC"),
            c.get("auth", ""),
        ]
        for c in main_connections
    ]
    security_rows = [
        [
            s.get("actor", ""),
            s.get("target", ""),
            s.get("access_type", ""),
            s.get("authn", ""),
            s.get("authz", ""),
            s.get("secret", ""),
            s.get("encryption", ""),
        ]
        for s in derived_security
    ]
    dataflow_rows = [
        [
            f.get("id", ""),
            f"{f.get('source', '')} -> {f.get('target', '')}",
            f"Protocol: {f.get('protocol', '')}; Frequency: {f.get('frequency', '')}",
            f.get("data", ""),
            f.get("data", ""),
            "Retry, dead-letter, and alerting as per runbook",
        ]
        for f in main_dataflows
    ]

    summary = {
        "components_synced": _replace_table_rows(
            lld_soup,
            _find_table_after_heading(lld_soup, "Detailed Component Architecture"),
            comp_rows,
        ),
        "connections_synced": _replace_table_rows(
            lld_soup,
            _find_table_after_heading(lld_soup, "Detailed Network and Service Connections"),
            conn_rows,
        ),
        "security_synced": _replace_table_rows(
            lld_soup,
            _find_table_after_heading(lld_soup, "Security Access Connections"),
            security_rows,
        ),
        "dataflows_synced": _replace_table_rows(
            lld_soup,
            _find_table_after_heading(lld_soup, "Detailed Data Flow"),
            dataflow_rows,
        ),
        "inherited_context_entities": len(inherited["context_entities"]),
        "inherited_network_segmentation": len(inherited["segmentation"]),
    }

    themed_html = apply_lld_color_theme(str(lld_soup))
    return themed_html, summary


def derive_security_rows_from_connections(connections: list[dict]) -> list[dict]:
    derived: list[dict] = []
    for conn in connections:
        auth = (conn.get("auth") or "").strip()
        if not auth:
            continue
        derived.append(
            {
                "actor": conn.get("source", ""),
                "target": conn.get("target", ""),
                "access_type": "Data Plane",
                "authn": auth,
                "authz": "RBAC",
                "secret": "Managed Secret Store",
                "encryption": "TLS 1.2+",
            }
        )
    return derived


def default_components_template() -> list[dict]:
    return [
        {
            "name": "Internet / User",
            "layer": "Edge",
            "service": "Client",
            "network_zone": "Public",
            "purpose": "User entry point",
        },
        {
            "name": "API Gateway",
            "layer": "Network",
            "service": "Gateway / WAF",
            "network_zone": "DMZ",
            "purpose": "Ingress control",
        },
        {
            "name": "Application Service",
            "layer": "Application",
            "service": "App Runtime",
            "network_zone": "Private Subnet",
            "purpose": "Business logic",
        },
        {
            "name": "Primary Data Store",
            "layer": "Data",
            "service": "Managed Database",
            "network_zone": "Private Data Subnet",
            "purpose": "Persistent storage",
        },
    ]


def default_connections_template() -> list[dict]:
    return [
        {
            "source": "Internet / User",
            "target": "API Gateway",
            "protocol": "HTTPS",
            "port": "443",
            "network_path": "Public Internet",
            "auth": "OIDC + MFA",
        },
        {
            "source": "API Gateway",
            "target": "Application Service",
            "protocol": "HTTPS",
            "port": "443",
            "network_path": "Private Link / VNet",
            "auth": "mTLS",
        },
        {
            "source": "Application Service",
            "target": "Primary Data Store",
            "protocol": "TCP",
            "port": "1433",
            "network_path": "Private Subnet",
            "auth": "Managed Identity",
        },
    ]


def default_security_template() -> list[dict]:
    return [
        {
            "actor": "Platform Operator",
            "target": "API Gateway",
            "access_type": "Control Plane",
            "authn": "Entra ID + MFA",
            "authz": "RBAC",
            "secret": "Key Vault",
            "encryption": "TLS 1.2+",
        },
        {
            "actor": "Application Service",
            "target": "Primary Data Store",
            "access_type": "Data Plane",
            "authn": "Managed Identity",
            "authz": "Least Privilege Role",
            "secret": "Key Vault",
            "encryption": "TLS 1.2+",
        },
    ]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


AWS4_RES_ICON_HINTS = [
    (("direct connect", "directconnect", "private connectivity", "private link"), ("direct_connect", "#4D72B8")),
    (("site-to-site vpn", "site to site vpn", "vpn"), ("vpn", "#4D72B8")),
    (("api gateway",), ("api_gateway", "#DD344C")),
    (("waf",), ("waf", "#C925D1")),
    (("cognito", "oidc", "oauth", "authentication"), ("cognito", "#C925D1")),
    (("ecs", "container", "app runtime", "application runtime", "application service"), ("ecs", "#ED7100")),
    (("fargate",), ("fargate", "#ED7100")),
    (("lambda",), ("lambda", "#ED7100")),
    (("ec2", "server", "instance"), ("ec2", "#ED7100")),
    (("rds", "managed database", "database", "sql", "postgres", "mysql"), ("rds", "#4D72B8")),
    (("dynamodb",), ("dynamodb", "#4D72B8")),
    (("elasticache", "redis", "cache"), ("elasticache", "#4D72B8")),
    (("s3", "bucket", "storage"), ("bucket", "#7AA116")),
    (("cloudfront", "cdn", "client"), ("cloudfront", "#8C4FFF")),
    (("internet gateway",), ("internet_gateway", "#4D72B8")),
    (("internet", "user", "external"), ("internet", "#879196")),
    (("nat gateway",), ("nat_gateway", "#4D72B8")),
    (("route 53", "route53", "dns"), ("route_53", "#4D72B8")),
    (("cloudwatch",), ("cloudwatch_2", "#E7157B")),
    (("iam", "identity"), ("iam", "#C925D1")),
]


def _resolve_native_aws4_icon(component: dict) -> tuple[str, str] | None:
    text = " ".join(
        [
            component.get("name", "") or "",
            component.get("service", "") or "",
            component.get("purpose", "") or "",
            component.get("layer", "") or "",
            component.get("network_zone", "") or "",
        ]
    ).lower()
    if any(token in text for token in ["on-prem", "on prem", "onprem", "corporate data center", "sftp"]):
        return None

    for keywords, resolved in AWS4_RES_ICON_HINTS:
        if any(keyword in text for keyword in keywords):
            return resolved
    return None


def _mxfile(name: str):
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name=name)
    model = ET.SubElement(
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
        pageWidth="3050",
        pageHeight="1600",
        math="0",
        shadow="0",
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    return mxfile, root


def generate_lld_detailed_architecture_drawio(components: list[dict], connections: list[dict]) -> str:
    mxfile, root = _mxfile("LLD Detailed Architecture")
    layer_order = ["Edge", "Network", "Platform", "Application", "Data", "Security"]

    def _split_text(value: str, width: int = 24) -> str:
        words = re.sub(r"\s+", " ", value or "").strip().split(" ")
        if not words:
            return ""
        lines: list[str] = []
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if len(candidate) <= width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return "<br/>".join(lines)

    def _label_value(comp: dict, compact: bool = False) -> str:
        """Generate compact label: just component name, readable font."""
        name = (comp.get("name") or "").strip()
        if name:
            return f"<b>{_split_text(name, 22)}</b>"
        return "Component"

    title = ET.SubElement(
        root,
        "mxCell",
        id="lld-title",
        value="Low-Level Service Design (Left-to-Right Segregated Flow)",
        style="text;fontSize=16;fontStyle=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(title, "mxGeometry", x="20", y="20", width="1400", height="30", **{"as": "geometry"})

    boundary_title = ET.SubElement(
        root,
        "mxCell",
        id="lld-boundary-title",
        value="Solution Boundary",
        style="text;fontSize=11;fontStyle=1;align=left;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(boundary_title, "mxGeometry", x="24", y="60", width="180", height="20", **{"as": "geometry"})

    # ── AWS service classification ─────────────────────────────────────────
    _AWS_GLOBAL = {
        "cloudfront", "route53", "route 53", "iam", "sts", "waf",
    }
    _AWS_MANAGED = {
        "cloudwatch", "logs", "secrets manager", "secret", "kms",
        "dynamodb", "sns", "sqs", "audit", "compliance", "monitoring",
        "s3", "bucket",
    }

    def _is_global_scope_item(comp: dict) -> bool:
        joined = " ".join([
            (comp.get("name") or ""), (comp.get("service") or ""),
            (comp.get("purpose") or ""),
        ]).lower()
        return any(k in joined for k in _AWS_GLOBAL) or any(
            k in joined for k in ["global service", "control plane", "audit logging", "audit logs", "compliance monitoring"]
        )

    def _resolve_zone(comp: dict) -> str:
        zone = (comp.get("network_zone") or "").lower()
        layer = (comp.get("layer") or "application").lower()
        name = (comp.get("name") or "").lower()
        service = (comp.get("service") or "").lower()
        joined = f"{zone} {layer} {name} {service}"
        if any(k in joined for k in _AWS_GLOBAL | _AWS_MANAGED):
            return "managed"
        if any(k in joined for k in ["entra id", "azure identity", "azure ad", "ukhsa intra identity", "entra", "azure identity (entra id)"]):
            return "azureid"
        if any(k in joined for k in ["on-prem", "on prem", "onprem", "business app", "sftp", "corporate data center"]):
            return "internet"
        if any(k in joined for k in ["cloudfront", "route53", "route 53", "global accelerator"]):
            return "public"
        if "cognito" in joined:
            return "private"
        if any(k in joined for k in ["api gateway", "gateway", "alb", "nlb", "internet gateway", "nat gateway", "public"]):
            return "public"
        if any(k in joined for k in ["database", "rds", "data store", "warehouse", "raw landing"]):
            return "data"
        if any(k in joined for k in ["app", "application", "service", "ecs", "ec2", "lambda", "private", "platform", "security"]):
            return "private"
        if any(k in joined for k in ["internet", "external", "edge", "user", "client"]):
            return "internet"
        if "public" in joined or "gateway" in joined:
            return "public"
        if layer in {"platform", "application", "security"}:
            return "private"
        if layer == "network":
            return "public"
        if layer == "data":
            return "data"
        return "private"

    global_scope_items: list[str] = []

    # ── Dynamic layout engine ──────────────────────────────────────────────
    import math as _math

    CARD_W = 170      # component card width
    CARD_H = 170      # component card height
    CARD_GAP_X = 22   # horizontal gap between cards
    CARD_GAP_Y = 22   # vertical gap between cards
    ZONE_PAD_X = 18   # left/right padding inside zone
    ZONE_PAD_TOP = 56 # top padding inside zone (title area)
    ZONE_PAD_BOT = 18 # bottom padding inside zone
    ZONE_GAP = 24           # gap between adjacent zones
    DATA_MANAGED_GAP = 80   # wider gap between data and managed zones to fit VPC endpoint icon
    AZURE_AWS_GAP = 90      # wider gap between azureid and public zones to fit Direct Connect icon
    ZONE_Y = 170            # y-coordinate where zones start

    # Max columns per zone
    MAX_COLS_MAP = {
        "internet": 1, "azureid": 1, "public": 1,
        "private": 2, "data": 1, "managed": 2,
    }

    # ── Pre-pass: classify components into zones ────────────────────────────
    zone_comp_lists: dict[str, list] = {k: [] for k in ["internet", "azureid", "public", "private", "data", "managed"]}
    ordered_components2: list[dict] = []
    for layer in layer_order:
        for comp in components:
            if (comp.get("layer") or "Application").strip().lower() in layer.lower() or layer.lower() in (comp.get("layer") or "Application").strip().lower():
                if comp not in ordered_components2:
                    ordered_components2.append(comp)
    for comp in components:
        if comp not in ordered_components2:
            ordered_components2.append(comp)

    for comp in ordered_components2:
        zk = _resolve_zone(comp)
        zone_comp_lists[zk].append(comp)
        if _is_global_scope_item(comp):
            global_scope_items.append((comp.get("name") or "Component").strip())

    # ── Calculate zone dimensions ────────────────────────────────────────────
    def _calc_zone_dims(n: int, max_cols: int):
        n = max(n, 1)
        cols = min(max_cols, n)
        rows = _math.ceil(n / cols)
        w = ZONE_PAD_X * 2 + cols * CARD_W + max(0, cols - 1) * CARD_GAP_X
        h = ZONE_PAD_TOP + rows * CARD_H + max(0, rows - 1) * CARD_GAP_Y + ZONE_PAD_BOT
        return cols, rows, max(w, CARD_W + ZONE_PAD_X * 2), max(h, CARD_H + ZONE_PAD_TOP + ZONE_PAD_BOT)

    zone_order = ["internet", "azureid", "public", "private", "data", "managed"]
    zone_layout: dict[str, dict] = {}
    x_cursor = 20
    for zk in zone_order:
        cols, rows, w, h = _calc_zone_dims(len(zone_comp_lists[zk]), MAX_COLS_MAP[zk])
        zone_layout[zk] = {"x": x_cursor, "y": ZONE_Y, "w": w, "h": h, "cols": cols}
        if zk == "data":
            gap = DATA_MANAGED_GAP
        elif zk == "azureid":
            gap = AZURE_AWS_GAP
        else:
            gap = ZONE_GAP
        x_cursor += w + gap

    # Total zone area width (used for boundary boxes)
    zones_right_x = x_cursor - ZONE_GAP
    max_zone_h = max(d["h"] for d in zone_layout.values())
    PANEL_X = zones_right_x + 30  # right-side panels start here (clear of all zones)

    # ── Outer solution boundary ─────────────────────────────────────────────
    boundary_total_w = PANEL_X + 430  # includes all right-side panels
    boundary_total_h = ZONE_Y + max_zone_h + 60
    ET.SubElement(
        root, "mxCell", id="lld-sol-boundary", value="",
        style="rounded=1;dashed=1;strokeWidth=2;strokeColor=#7C8795;fillColor=none;",
        parent="1", vertex="1",
    ).append(ET.fromstring(f'<mxGeometry x="12" y="58" width="{boundary_total_w}" height="{boundary_total_h}" as="geometry"/>'))

    # ── AWS Cloud boundary (wraps public → managed; azureid is outside in Azure Cloud) ──
    az = zone_layout["azureid"]
    pb = zone_layout["public"]
    mg = zone_layout["managed"]
    aws_left  = pb["x"] - 14
    aws_top   = 90
    aws_right = mg["x"] + mg["w"] + 14
    aws_w     = aws_right - aws_left
    aws_h     = ZONE_Y + max_zone_h + 40
    aws_cloud = ET.SubElement(
        root, "mxCell", id="lld-aws-cloud", value="",
        style="rounded=1;strokeWidth=2;strokeColor=#5B6777;fillColor=#F8FAFC;",
        parent="1", vertex="1",
    )
    ET.SubElement(aws_cloud, "mxGeometry", x=str(aws_left), y=str(aws_top), width=str(aws_w), height=str(aws_h), **{"as": "geometry"})
    aws_title = ET.SubElement(
        root, "mxCell", id="lld-aws-cloud-title", value="AWS Cloud",
        style="text;fontSize=12;fontStyle=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1", vertex="1",
    )
    ET.SubElement(aws_title, "mxGeometry", x=str(aws_left + 12), y=str(aws_top + 6), width="160", height="20", **{"as": "geometry"})

    # ── VPC boundary (wraps public → data; azure identity is outside) ─────
    dt = zone_layout["data"]
    vpc_left  = pb["x"] - 10
    vpc_top   = ZONE_Y - 16
    vpc_right = dt["x"] + dt["w"] + 10
    vpc_w     = vpc_right - vpc_left
    vpc_h     = max_zone_h + 32
    vpc = ET.SubElement(
        root, "mxCell", id="lld-vpc-boundary", value="",
        style="rounded=1;strokeWidth=2;strokeColor=#2E7D32;fillColor=#F3FBF5;dashed=1;",
        parent="1", vertex="1",
    )
    ET.SubElement(vpc, "mxGeometry", x=str(vpc_left), y=str(vpc_top), width=str(vpc_w), height=str(vpc_h), **{"as": "geometry"})
    vpc_title = ET.SubElement(
        root, "mxCell", id="lld-vpc-title", value="VPC Boundary",
        style="text;fontSize=11;fontStyle=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1", vertex="1",
    )
    ET.SubElement(vpc_title, "mxGeometry", x=str(vpc_left + 10), y=str(vpc_top + 6), width="160", height="20", **{"as": "geometry"})

    # ── Azure Cloud boundary (wraps azureid zone) ───────────────────────────
    azure_pad = 12
    azure_cloud = ET.SubElement(
        root, "mxCell", id="lld-azure-cloud", value="",
        style="rounded=1;strokeWidth=2;strokeColor=#0078D4;fillColor=#EBF5FB;dashed=0;",
        parent="1", vertex="1",
    )
    ET.SubElement(azure_cloud, "mxGeometry",
        x=str(az["x"] - azure_pad), y=str(aws_top),
        width=str(az["w"] + azure_pad * 2), height=str(aws_h),
        **{"as": "geometry"})
    azure_cloud_title = ET.SubElement(
        root, "mxCell", id="lld-azure-cloud-title", value="Azure Cloud (Microsoft Entra ID)",
        style="text;fontSize=11;fontStyle=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;fontColor=#0078D4;",
        parent="1", vertex="1",
    )
    ET.SubElement(azure_cloud_title, "mxGeometry",
        x=str(az["x"] - azure_pad + 8), y=str(aws_top + 6),
        width="260", height="20",
        **{"as": "geometry"})

    # ── AWS Direct Connect icon — in the gap between Azure Cloud and AWS Cloud ──
    dc_cx = az["x"] + az["w"] + AZURE_AWS_GAP // 2  # centre of gap
    dc_cy = ZONE_Y + max_zone_h // 2
    dc_icon = ET.SubElement(
        root, "mxCell", id="lld-direct-connect-icon",
        value="AWS Direct Connect",
        style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.direct_connect;fillColor=#4D72B8;strokeColor=#ffffff;fontSize=8;fontStyle=1;fontColor=#1E3A5F;html=1;align=center;verticalLabelPosition=bottom;labelPosition=center;verticalAlign=top;",
        parent="1", vertex="1",
    )
    ET.SubElement(dc_icon, "mxGeometry",
        x=str(dc_cx - 24), y=str(dc_cy - 24),
        width="48", height="48",
        **{"as": "geometry"})
    # Arrow: azureid zone → Direct Connect icon
    dc_arrow1 = ET.SubElement(
        root, "mxCell", id="lld-direct-connect-arrow1", value="",
        style="edgeStyle=orthogonalEdgeStyle;strokeColor=#0078D4;strokeWidth=2;endArrow=block;endFill=1;startArrow=block;startFill=1;dashed=0;",
        parent="1", source="lld-zone-azureid", target="lld-direct-connect-icon", edge="1",
    )
    ET.SubElement(dc_arrow1, "mxGeometry", relative="1", **{"as": "geometry"})
    # Arrow: Direct Connect icon → AWS public subnet zone
    dc_arrow2 = ET.SubElement(
        root, "mxCell", id="lld-direct-connect-arrow2", value="",
        style="edgeStyle=orthogonalEdgeStyle;strokeColor=#4D72B8;strokeWidth=2;endArrow=block;endFill=1;startArrow=block;startFill=1;dashed=0;",
        parent="1", source="lld-direct-connect-icon", target="lld-zone-public", edge="1",
    )
    ET.SubElement(dc_arrow2, "mxGeometry", relative="1", **{"as": "geometry"})

    # ── Managed Services zone box ──────────────────────────────────────────
    mgl = zone_layout["managed"]
    managed_svc_box = ET.SubElement(
        root, "mxCell", id="lld-managed-services", value="",
        style="rounded=1;strokeWidth=2;strokeColor=#E65100;fillColor=#FFF3E0;dashed=0;",
        parent="1", vertex="1",
    )
    ET.SubElement(managed_svc_box, "mxGeometry", x=str(mgl["x"]), y=str(mgl["y"]), width=str(mgl["w"]), height=str(mgl["h"]), **{"as": "geometry"})
    managed_svc_title = ET.SubElement(
        root, "mxCell", id="lld-managed-services-title",
        value="<b>AWS Managed Services</b><br/><font color='#E65100' style='font-size:8px;'>Accessed via VPC Endpoints</font>",
        style="text;html=1;fontSize=9;fontStyle=1;align=center;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1", vertex="1",
    )
    ET.SubElement(managed_svc_title, "mxGeometry", x=str(mgl["x"] + 4), y=str(mgl["y"] + 4), width=str(mgl["w"] - 8), height="40", **{"as": "geometry"})

    # VPC Endpoint icon node - centered in the gap between data and managed zones
    vpc_ep_cx = dt["x"] + dt["w"] + DATA_MANAGED_GAP // 2  # horizontal center of gap
    vpc_ep_cy = ZONE_Y + max_zone_h // 2                    # vertical center
    vpc_ep_icon = ET.SubElement(
        root, "mxCell", id="lld-vpc-endpoint-icon",
        value="VPC Endpoint",
        style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.vpc_endpoints;fillColor=#8C4FFF;strokeColor=#ffffff;fontSize=8;fontStyle=1;fontColor=#6B21A8;html=1;align=center;verticalAlign=bottom;verticalLabelPosition=bottom;labelPosition=center;",
        parent="1", vertex="1",
    )
    ET.SubElement(vpc_ep_icon, "mxGeometry", x=str(vpc_ep_cx - 24), y=str(vpc_ep_cy - 24), width="48", height="48", **{"as": "geometry"})
    # Arrow: VPC boundary right edge → VPC endpoint icon
    vpc_ep_a1 = ET.SubElement(
        root, "mxCell", id="lld-vpc-endpoint-arrow",
        value="",
        style="edgeStyle=orthogonalEdgeStyle;dashed=1;dashPattern=6 3;strokeColor=#E65100;strokeWidth=2;endArrow=block;endFill=0;",
        parent="1", source="lld-zone-data", target="lld-vpc-endpoint-icon", edge="1",
    )
    ET.SubElement(vpc_ep_a1, "mxGeometry", relative="1", **{"as": "geometry"})
    # Arrow: VPC endpoint icon → Managed services zone
    vpc_ep_a2 = ET.SubElement(
        root, "mxCell", id="lld-vpc-endpoint-arrow2",
        value="",
        style="edgeStyle=orthogonalEdgeStyle;dashed=1;dashPattern=6 3;strokeColor=#E65100;strokeWidth=2;endArrow=block;endFill=0;",
        parent="1", source="lld-vpc-endpoint-icon", target="lld-managed-services", edge="1",
    )
    ET.SubElement(vpc_ep_a2, "mxGeometry", relative="1", **{"as": "geometry"})

    # ── Zone colour bands ────────────────────────────────────────────────────
    ZONE_STYLES = {
        "internet": {"title": "External / On-Prem",      "fill": "#E3F2FD", "stroke": "#1565C0"},
        "azureid":  {"title": "Azure Identity\n(Entra ID)", "fill": "#E1F5FE", "stroke": "#01579B"},
        "public":   {"title": "Public Subnet\n(Ingress)",   "fill": "#FFF8E1", "stroke": "#F57F17"},
        "private":  {"title": "Private Subnet\n(App Layer)","fill": "#E8F5E9", "stroke": "#1B5E20"},
        "data":     {"title": "Data Subnet\n(Storage)",     "fill": "#F3E5F5", "stroke": "#4A148C"},
        "managed":  {"title": "",                            "fill": "#FFF3E0", "stroke": "#E65100"},
    }
    for zk in ["internet", "azureid", "public", "private", "data"]:
        zd = zone_layout[zk]
        zs = ZONE_STYLES[zk]
        box = ET.SubElement(
            root, "mxCell", id=f"lld-zone-{zk}", value="",
            style=f"rounded=0;fillColor={zs['fill']};strokeColor={zs['stroke']};strokeWidth=2.5;",
            parent="1", vertex="1",
        )
        ET.SubElement(box, "mxGeometry", x=str(zd["x"]), y=str(zd["y"]), width=str(zd["w"]), height=str(zd["h"]), **{"as": "geometry"})
        lbl = ET.SubElement(
            root, "mxCell", id=f"lld-zone-{zk}-title", value=zs["title"],
            style=f"text;fontSize=11;fontStyle=1;align=center;verticalAlign=middle;strokeColor=none;fillColor=none;backgroundColor={zs['fill']};",
            parent="1", vertex="1",
        )
        ET.SubElement(lbl, "mxGeometry", x=str(zd["x"] + 4), y=str(zd["y"] + 6), width=str(zd["w"] - 8), height="30", **{"as": "geometry"})

    # ── Component placement ──────────────────────────────────────────────────
    card_w = CARD_W
    card_h = CARD_H
    id_map: dict[str, str] = {}
    comp_zone_map: dict[str, str] = {}
    node_pos: dict[str, tuple[int, int]] = {}

    for zk in zone_order:
        zd = zone_layout[zk]
        cols = zd["cols"]
        comps = zone_comp_lists[zk]
        for idx, comp in enumerate(comps):
            comp_name = (comp.get("name") or "Component").strip()
            cid = f"cmp-{_slug(comp_name)}"
            id_map[comp_name.lower()] = cid
            comp_zone_map[comp_name.lower()] = zk

            col = idx % cols
            row = idx // cols
            x = zd["x"] + ZONE_PAD_X + col * (CARD_W + CARD_GAP_X)
            y = zd["y"] + ZONE_PAD_TOP + row * (CARD_H + CARD_GAP_Y)
            node_pos[comp_name.lower()] = (x + CARD_W // 2, y + CARD_H // 2)

            # Card background
            card = ET.SubElement(
                root, "mxCell", id=cid, value="",
                style=f"rounded=1;fillColor=#FFFFFF;strokeColor={ZONE_STYLES[zk]['stroke']};strokeWidth=2;shadow=1;",
                parent="1", vertex="1",
            )
            ET.SubElement(card, "mxGeometry", x=str(x), y=str(y), width=str(CARD_W), height=str(CARD_H), **{"as": "geometry"})

            # Icon area (top 60% of card)
            icon_h = int(CARD_H * 0.58)
            icon_panel = ET.SubElement(
                root, "mxCell", id=f"{cid}-icon-panel", value="",
                style=f"rounded=0;fillColor={ZONE_STYLES[zk]['fill']};strokeColor=none;",
                parent="1", vertex="1",
            )
            ET.SubElement(icon_panel, "mxGeometry", x=str(x + 1), y=str(y + 1), width=str(CARD_W - 2), height=str(icon_h - 1), **{"as": "geometry"})

            # AWS icon centred in icon area
            icon_sz = 48
            icon_x = x + (CARD_W - icon_sz) // 2
            icon_y = y + (icon_h - icon_sz) // 2

            native_icon = _resolve_native_aws4_icon(comp)
            icon_hint = " ".join([comp_name, (comp.get("service") or ""), (comp.get("purpose") or ""), (comp.get("layer") or "")]).strip()
            icon_url = None if native_icon else get_icon_url(icon_hint)

            if native_icon:
                res_icon, fill_color = native_icon
                icon_cell = ET.SubElement(
                    root, "mxCell", id=f"{cid}-icon", value="",
                    style=(f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res_icon};"
                           f"fillColor={fill_color};strokeColor=#FFFFFF;gradientColor=none;dashed=0;aspect=fixed;outlineConnect=0;"),
                    parent="1", vertex="1",
                )
                ET.SubElement(icon_cell, "mxGeometry", x=str(icon_x), y=str(icon_y), width=str(icon_sz), height=str(icon_sz), **{"as": "geometry"})
            elif icon_url:
                icon_cell = ET.SubElement(
                    root, "mxCell", id=f"{cid}-icon", value="",
                    style=f"shape=image;image={_to_drawio_image_uri(icon_url)};imageAspect=1;aspect=fixed;strokeColor=none;fillColor=none;",
                    parent="1", vertex="1",
                )
                ET.SubElement(icon_cell, "mxGeometry", x=str(icon_x), y=str(icon_y), width=str(icon_sz), height=str(icon_sz), **{"as": "geometry"})

            # Name label strip (bottom 42% of card, white background)
            name_y = y + icon_h
            name_h = CARD_H - icon_h
            name_bg = ET.SubElement(
                root, "mxCell", id=f"{cid}-name-bg", value="",
                style="rounded=0;fillColor=#FFFFFF;strokeColor=none;",
                parent="1", vertex="1",
            )
            ET.SubElement(name_bg, "mxGeometry", x=str(x + 1), y=str(name_y), width=str(CARD_W - 2), height=str(name_h - 1), **{"as": "geometry"})
            name_label = ET.SubElement(
                root, "mxCell", id=f"{cid}-text",
                value=_label_value(comp, compact=True),
                style="text;html=1;whiteSpace=wrap;align=center;verticalAlign=middle;fontSize=10;fontStyle=1;strokeColor=none;fillColor=none;",
                parent="1", vertex="1",
            )
            ET.SubElement(name_label, "mxGeometry", x=str(x + 4), y=str(name_y + 2), width=str(CARD_W - 8), height=str(name_h - 4), **{"as": "geometry"})

    # ── Re-use zone_bounds for boundary-clamping reference ───────────────────
    zone_bounds = {
        zk: (zd["x"], zd["w"], zd["y"], zd["h"])
        for zk, zd in zone_layout.items()
    }

    # ── Legacy aliases used by downstream code ───────────────────────────────
    zone_x = {zk: (zd["x"], zd["w"]) for zk, zd in zone_layout.items()}
    zone_next_y = {zk: zd["y"] + zd["h"] + ZONE_GAP for zk, zd in zone_layout.items()}

    aws_left, aws_top, aws_w, aws_h = aws_left, aws_top, aws_w, aws_h  # already defined above

    flow_lines: list[str] = []
    flow_index_lines: list[str] = []
    observed_auth: list[str] = []
    zone_label = {
        "internet": "On-Prem",
        "azureid": "Azure Identity",
        "public": "Public Subnet",
        "private": "Private Subnet",
        "data": "Data Subnet",
    }

    def _fuzzy_lookup(name: str) -> str | None:
        """Try exact, then partial/substring match in id_map."""
        key = name.lower().strip()
        if key in id_map:
            return id_map[key]
        # try partial match: name contains a known key or vice versa
        for k, v in id_map.items():
            if key in k or k in key:
                return v
        return None

    def _ensure_virtual_node(name: str, virtual_nodes: dict) -> str:
        """Create a placeholder card for components referenced in connections but not in the component table."""
        key = name.lower().strip()
        if key in id_map:
            return id_map[key]
        if key in virtual_nodes:
            return virtual_nodes[key]
        # Determine zone from name
        joined = key
        if any(k in joined for k in ["user", "end user", "browser", "client", "operator", "admin"]):
            v_zone = "internet"
        elif any(k in joined for k in ["entra", "azure ad", "identity", "azure identity"]):
            v_zone = "azureid"
        else:
            v_zone = "internet"
        vx, _ = zone_x[v_zone]
        vy = zone_next_y[v_zone]
        vcid = f"vnode-{_slug(name)}"
        virtual_nodes[key] = vcid
        id_map[key] = vcid
        comp_zone_map[key] = v_zone
        node_pos[key] = (vx, vy)
        zone_next_y[v_zone] += card_h + 30
        vcard = ET.SubElement(
            root, "mxCell", id=vcid, value="",
            style="rounded=1;fillColor=#F0F4FF;strokeColor=#1565C0;strokeWidth=1.8;shadow=1;dashed=1;",
            parent="1", vertex="1",
        )
        ET.SubElement(vcard, "mxGeometry", x=str(vx), y=str(vy), width=str(card_w), height=str(card_h), **{"as": "geometry"})
        vlabel = ET.SubElement(
            root, "mxCell", id=f"{vcid}-text",
            value=f"<b>{name}</b>",
            style="text;html=1;whiteSpace=wrap;align=center;verticalAlign=middle;fontSize=8;fontStyle=1;strokeColor=none;fillColor=none;",
            parent="1", vertex="1",
        )
        ET.SubElement(vlabel, "mxGeometry", x=str(vx + 4), y=str(vy + card_h // 3), width=str(card_w - 8), height=str(card_h // 2), **{"as": "geometry"})
        return vcid

    _virtual_nodes: dict[str, str] = {}

    flow_entries: list[dict] = []
    for original_index, conn in enumerate(connections, start=1):
        src_name = (conn.get("source") or "").strip()
        tgt_name = (conn.get("target") or "").strip()
        if not src_name or not tgt_name:
            continue
        src_key = src_name.lower()
        tgt_key = tgt_name.lower()
        src = _fuzzy_lookup(src_name) or _ensure_virtual_node(src_name, _virtual_nodes)
        tgt = _fuzzy_lookup(tgt_name) or _ensure_virtual_node(tgt_name, _virtual_nodes)
        if not src or not tgt:
            continue

        src_xy = node_pos.get(src_key, (9999, 9999))
        tgt_xy = node_pos.get(tgt_key, (9999, 9999))
        flow_entries.append(
            {
                "conn": conn,
                "src": src,
                "tgt": tgt,
                "src_name": src_name,
                "tgt_name": tgt_name,
                "src_key": src_key,
                "tgt_key": tgt_key,
                "sort_key": (src_xy[0], src_xy[1], tgt_xy[0], tgt_xy[1], original_index),
            }
        )

    flow_entries.sort(key=lambda e: e["sort_key"])

    def _is_bi_directional(conn: dict) -> bool:
        signal = " ".join(
            [
                (conn.get("protocol") or ""),
                (conn.get("network_path") or ""),
                (conn.get("auth") or ""),
            ]
        ).lower()
        return any(
            k in signal
            for k in [
                "bi-directional",
                "bidirectional",
                "two-way",
                "two way",
                "request/response",
                "request-response",
                "mutual",
            ]
        )

    for i, entry in enumerate(flow_entries, start=1):
        conn = entry["conn"]
        src = entry["src"]
        tgt = entry["tgt"]
        src_name = entry["src_name"]
        tgt_name = entry["tgt_name"]
        src_key = entry["src_key"]
        tgt_key = entry["tgt_key"]

        route_parts = [x for x in [conn.get("protocol", ""), conn.get("port", ""), conn.get("network_path", "")] if x]
        route = " | ".join(route_parts)
        auth = (conn.get("auth") or "").strip()
        src_zone = zone_label.get(comp_zone_map.get(src_key, "private"), "Private Subnet")
        tgt_zone = zone_label.get(comp_zone_map.get(tgt_key, "private"), "Private Subnet")
        if auth and auth not in observed_auth:
            observed_auth.append(auth)

        is_bidir = _is_bi_directional(conn)
        dir_symbol = "<->" if is_bidir else "->"

        detail = f"<b>STEP {i}</b>: {src_name} {dir_symbol} {tgt_name}"
        detail += f"<br/>    Inbound path: {src_zone} -> {tgt_zone}"
        if route:
            detail += f"<br/>    Request channel: {route}"
        if auth:
            detail += f"<br/>    Authentication/Authorization: {auth}"
        detail += f"<br/>    Outbound/Response path: {tgt_zone} -> {src_zone}"
        flow_lines.append(detail)
        flow_index_lines.append(f"<b>S{i}</b>: {src_name} {dir_symbol} {tgt_name}")

        edge_style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;"
            "fontSize=13;fontStyle=1;strokeWidth=2.4;strokeColor=#1D4ED8;endArrow=block;endFill=1;"
            "labelBackgroundColor=#FFF7ED;labelBorderColor=#FB923C;"
        )
        if is_bidir:
            edge_style = (
                "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;"
                "fontSize=13;fontStyle=1;strokeWidth=2.6;strokeColor=#0F766E;"
                "endArrow=block;endFill=1;startArrow=block;startFill=1;"
                "labelBackgroundColor=#ECFEFF;labelBorderColor=#14B8A6;"
            )

        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"edge-{i}",
            value=f"S{i}",
            style=edge_style,
            parent="1",
            source=src,
            target=tgt,
            edge="1",
        )
        geom = ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
        # Add waypoints to separate parallel arrows and prevent merging
        offset = (i % 3 - 1) * 80  # Offset each arrow to separate them (-80, 0, 80)
        if offset != 0:
            midpoint = ET.SubElement(geom, "mxPoint", x=str(400 + offset), y="400")
            midpoint.set("as", "sourcePoint")

    flow_index_bg = ET.SubElement(
        root,
        "mxCell",
        id="lld-flow-index-bg",
        value="",
        style="rounded=1;fillColor=#FFF7ED;strokeColor=#FB923C;strokeWidth=1.5;",
        parent="1",
        vertex="1",
    )
    flow_index_height = max(100, 40 + len(flow_index_lines) * 16)
    ET.SubElement(flow_index_bg, "mxGeometry", x=str(PANEL_X), y="84", width="380", height=str(flow_index_height), **{"as": "geometry"})

    flow_index_title = ET.SubElement(
        root,
        "mxCell",
        id="lld-flow-index-title",
        value="Step Index (Arrow Labels)",
        style="text;fontSize=10;fontStyle=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(flow_index_title, "mxGeometry", x=str(PANEL_X + 10), y="92", width="360", height="16", **{"as": "geometry"})

    flow_index_text = ET.SubElement(
        root,
        "mxCell",
        id="lld-flow-index-text",
        value="<br/>".join(flow_index_lines) if flow_index_lines else "No indexed steps.",
        style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=9;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(flow_index_text, "mxGeometry", x=str(PANEL_X + 10), y="112", width="360", height=str(flow_index_height - 24), **{"as": "geometry"})

    flow_height = 0  # Data Flow Steps panel removed

    # Approved intra-identity auth panel
    auth_lines = [
        "<b>1.</b> Human access via Entra ID / AWS IAM Identity Center + MFA",
        "<b>2.</b> OIDC/OAuth2 token validation at entry points",
        "<b>3.</b> Service-to-service mTLS inside Private Subnet",
        "<b>4.</b> Workload identity (IAM Role / Managed Identity) for data access",
        "<b>5.</b> RBAC/least-privilege authorization for intra-service calls",
    ]
    if observed_auth:
        auth_lines.append("<b>Observed from table:</b> " + ", ".join(observed_auth))

    auth_bg = ET.SubElement(
        root,
        "mxCell",
        id="lld-auth-bg",
        value="",
        style="rounded=1;fillColor=#FFFEEB;strokeColor=#9AA5B1;strokeWidth=1.5;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(auth_bg, "mxGeometry", x=str(PANEL_X), y=str(168 + flow_index_height + flow_height), width="380", height="240", **{"as": "geometry"})

    auth_title = ET.SubElement(
        root,
        "mxCell",
        id="lld-auth-title",
        value="Approved Identity Auth",
        style="text;fontSize=10;fontStyle=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(auth_title, "mxGeometry", x=str(PANEL_X + 10), y=str(176 + flow_index_height + flow_height), width="360", height="16", **{"as": "geometry"})

    auth_text = ET.SubElement(
        root,
        "mxCell",
        id="lld-auth-text",
        value="<br/>".join(auth_lines),
        style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=8;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(auth_text, "mxGeometry", x=str(PANEL_X + 10), y=str(196 + flow_index_height + flow_height), width="360", height="208", **{"as": "geometry"})

    global_scope_unique = []
    for item in global_scope_items:
        if item not in global_scope_unique:
            global_scope_unique.append(item)
    global_scope_lines = [f"<b>{i}.</b> {name}" for i, name in enumerate(global_scope_unique, start=1)]
    if not global_scope_lines:
        global_scope_lines = ["No global-scope services identified from current component table."]

    scope_bg = ET.SubElement(
        root,
        "mxCell",
        id="lld-global-scope-bg",
        value="",
        style="rounded=1;fillColor=#ECFEFF;strokeColor=#0F766E;strokeWidth=1.5;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(scope_bg, "mxGeometry", x=str(PANEL_X), y=str(428 + flow_index_height + flow_height), width="400", height="140", **{"as": "geometry"})

    scope_title = ET.SubElement(
        root,
        "mxCell",
        id="lld-global-scope-title",
        value="Global-Scope Services",
        style="text;fontSize=10;fontStyle=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(scope_title, "mxGeometry", x=str(PANEL_X + 10), y=str(436 + flow_index_height + flow_height), width="380", height="16", **{"as": "geometry"})

    scope_text = ET.SubElement(
        root,
        "mxCell",
        id="lld-global-scope-text",
        value="<br/>".join(global_scope_lines),
        style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=8;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(scope_text, "mxGeometry", x=str(PANEL_X + 10), y=str(456 + flow_index_height + flow_height), width="380", height="104", **{"as": "geometry"})

    # AWS Placement Rules panel - explains service segregation logic
    rules_y = 456 + flow_index_height + flow_height + 120
    rules_bg = ET.SubElement(
        root,
        "mxCell",
        id="lld-aws-rules-bg",
        value="",
        style="rounded=1;fillColor=#FFF3E0;strokeColor=#E65100;strokeWidth=1.5;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(rules_bg, "mxGeometry", x=str(PANEL_X), y=str(rules_y), width="380", height="230", **{"as": "geometry"})
    rules_title = ET.SubElement(
        root,
        "mxCell",
        id="lld-aws-rules-title",
        value="AWS Service Placement Rules",
        style="text;fontSize=10;fontStyle=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(rules_title, "mxGeometry", x=str(PANEL_X + 10), y=str(rules_y + 8), width="360", height="16", **{"as": "geometry"})
    rules_lines = [
        "<b>Global Services</b> (no VPC boundary):",
        "&#x25CF; S3, IAM, STS, CloudFront, Route53",
        "&#x25CF; Accessible from any region/account",
        "&#x25CF; Placed in: <i>AWS Managed Services</i> zone",
        "",
        "<b>Regional Managed Services</b> (outside VPC):",
        "&#x25CF; CloudWatch, KMS, Secrets Manager, DynamoDB",
        "&#x25CF; SNS, SQS, CloudTrail (Audit Logging)",
        "&#x25CF; Placed in: <i>AWS Managed Services</i> zone",
        "",
        "<b>Connectivity Rule</b>:",
        "&#x25CF; VPC resources access managed services",
        "&#x25A0;  via <b>VPC Endpoints</b> (no public internet)",
        "&#x25A0;  Gateway Endpoint: S3, DynamoDB",
        "&#x25A0;  Interface Endpoint: all others",
    ]
    rules_text = ET.SubElement(
        root,
        "mxCell",
        id="lld-aws-rules-text",
        value="<br/>".join(rules_lines),
        style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=8;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(rules_text, "mxGeometry", x=str(PANEL_X + 10), y=str(rules_y + 28), width="360", height="196", **{"as": "geometry"})

    legend_bg = ET.SubElement(
        root,
        "mxCell",
        id="lld-legend-bg",
        value="",
        style="rounded=1;fillColor=#E8EEF8;strokeColor=#9AA5B1;strokeWidth=1.2;",
        parent="1",
        vertex="1",
    )
    legend_y = ZONE_Y + max_zone_h + 40  # always below the tallest zone
    ET.SubElement(legend_bg, "mxGeometry", x="20", y=str(legend_y), width=str(boundary_total_w - 20), height="30", **{"as": "geometry"})
    legend_text = ET.SubElement(
        root,
        "mxCell",
        id="lld-legend-text",
        value="Flow arrows are numbered. Each numbered step explains inbound path, request channel, auth, and outbound response path.",
        style="text;fontSize=9;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(legend_text, "mxGeometry", x="30", y=str(legend_y + 6), width="2990", height="18", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def _classify_network_path(conn: dict) -> str:
    """Return a high-level network path category for visual styling."""
    parts = " ".join([
        conn.get("network_path", ""),
        conn.get("protocol", ""),
        conn.get("port", ""),
    ]).lower()
    if any(k in parts for k in ["vpn", "site-to-site", "site to site", "ipsec"]):
        return "vpn"
    if any(k in parts for k in ["expressroute", "express route", "direct connect", "dx"]):
        return "expressroute"
    if any(k in parts for k in ["tls", "https", "443"]):
        return "tls"
    if any(k in parts for k in ["private link", "privatelink", "vpc endpoint"]):
        return "privatelink"
    if any(k in parts for k in ["internet", "public"]):
        return "internet"
    return "internal"


_NET_PATH_STYLES: dict[str, dict] = {
    "vpn": {
        "node_fill": "#FFF3CD", "node_stroke": "#D97706",
        "edge": "edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#D97706;strokeWidth=2.5;dashed=1;dashPattern=8 4;endArrow=block;endFill=1;fontSize=10;fontStyle=1;labelBackgroundColor=#FFF3CD;",
        "legend": "Site-to-Site VPN (IPSec)",
    },
    "expressroute": {
        "node_fill": "#E0F2F1", "node_stroke": "#00796B",
        "edge": "edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#00796B;strokeWidth=3;dashed=0;endArrow=block;endFill=1;fontSize=10;fontStyle=1;labelBackgroundColor=#E0F2F1;",
        "legend": "ExpressRoute / Direct Connect",
    },
    "tls": {
        "node_fill": "#EDE7F6", "node_stroke": "#5E35B1",
        "edge": "edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#5E35B1;strokeWidth=2;dashed=0;endArrow=block;endFill=1;fontSize=10;labelBackgroundColor=#EDE7F6;",
        "legend": "HTTPS / TLS",
    },
    "privatelink": {
        "node_fill": "#E8F5E9", "node_stroke": "#388E3C",
        "edge": "edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#388E3C;strokeWidth=2;dashed=0;endArrow=block;endFill=1;fontSize=10;labelBackgroundColor=#E8F5E9;",
        "legend": "Private Link / VPC Endpoint",
    },
    "internet": {
        "node_fill": "#FCE4EC", "node_stroke": "#C62828",
        "edge": "edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#C62828;strokeWidth=1.5;dashed=1;dashPattern=4 4;endArrow=block;endFill=1;fontSize=10;labelBackgroundColor=#FCE4EC;",
        "legend": "Internet / Public",
    },
    "internal": {
        "node_fill": "#E3F2FD", "node_stroke": "#1565C0",
        "edge": "edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#1565C0;strokeWidth=1.5;dashed=0;endArrow=block;endFill=1;fontSize=10;labelBackgroundColor=#E3F2FD;",
        "legend": "Internal / Private Network",
    },
}


def generate_lld_network_connections_drawio(connections: list[dict]) -> str:
    mxfile, root = _mxfile("LLD Network Connections")

    # ── Source nodes (left column) ──────────────────────────────────────────
    src_nodes: dict[str, str] = {}
    tgt_nodes: dict[str, str] = {}
    src_y = 80
    tgt_y = 80
    node_w, node_h = 200, 56
    src_x, tgt_x = 40, 560
    row_gap = 80

    def _make_node(name: str, nodes: dict, col_x: int, col_y_ref: list, path_type: str) -> str:
        key = name.lower().strip()
        if key in nodes:
            return nodes[key]
        nid = f"net-{_slug(name)}-{len(nodes)}"
        nodes[key] = nid
        style_info = _NET_PATH_STYLES.get(path_type, _NET_PATH_STYLES["internal"])
        cell = ET.SubElement(
            root,
            "mxCell",
            id=nid,
            value=f"<b>{name}</b>",
            style=(
                f"rounded=1;whiteSpace=wrap;align=center;html=1;"
                f"fillColor={style_info['node_fill']};strokeColor={style_info['node_stroke']};"
                "strokeWidth=1.5;fontSize=11;verticalAlign=middle;"
            ),
            parent="1",
            vertex="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(col_x), y=str(col_y_ref[0]), width=str(node_w), height=str(node_h), **{"as": "geometry"})
        col_y_ref[0] += row_gap
        return nid

    src_y_ref = [src_y]
    tgt_y_ref = [tgt_y]

    for i, c in enumerate(connections):
        path_type = _classify_network_path(c)
        s = _make_node(c["source"], src_nodes, src_x, src_y_ref, path_type)
        t = _make_node(c["target"], tgt_nodes, tgt_x, tgt_y_ref, path_type)

        proto = c.get("protocol", "")
        port = c.get("port", "")
        net_path = c.get("network_path", "")
        auth = c.get("auth", "")
        parts = [p for p in [proto, port, net_path, auth] if p]
        label_line1 = " | ".join(parts[:2]) if parts else ""
        label_line2 = " | ".join(parts[2:]) if len(parts) > 2 else ""
        label = label_line1 + (f"<br/>{label_line2}" if label_line2 else "")

        edge_style = _NET_PATH_STYLES.get(path_type, _NET_PATH_STYLES["internal"])["edge"]
        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"nedge-{i}",
            value=label,
            style=edge_style,
            parent="1",
            source=s,
            target=t,
            edge="1",
        )
        geom = ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
        # Add waypoints to separate parallel arrows - alternate vertical offset
        if i % 2 == 1:
            wp = ET.SubElement(geom, "mxPoint", x="300", y=str(80 + (i // 2) * 40))
            wp.set("as", "sourcePoint")

    # ── Legend panel ────────────────────────────────────────────────────────
    legend_x = 40
    legend_y = max(src_y_ref[0], tgt_y_ref[0]) + 40
    legend_bg = ET.SubElement(
        root, "mxCell", id="net-legend-bg", value="",
        style="rounded=1;fillColor=#F8FAFC;strokeColor=#9AA5B1;strokeWidth=1.5;",
        parent="1", vertex="1",
    )
    ET.SubElement(legend_bg, "mxGeometry", x=str(legend_x), y=str(legend_y), width="720", height="160", **{"as": "geometry"})
    legend_title = ET.SubElement(
        root, "mxCell", id="net-legend-title",
        value="<b>Network Path Legend</b>",
        style="text;html=1;fontSize=11;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1", vertex="1",
    )
    ET.SubElement(legend_title, "mxGeometry", x=str(legend_x + 12), y=str(legend_y + 10), width="300", height="20", **{"as": "geometry"})

    legend_items = [
        ("vpn", "━ ━  VPN (IPSec, Site-to-Site)", "#D97706"),
        ("expressroute", "━━━  ExpressRoute / Direct Connect", "#00796B"),
        ("tls", "━━━  HTTPS / TLS", "#5E35B1"),
        ("privatelink", "━━━  Private Link / VPC Endpoint", "#388E3C"),
        ("internet", "- -   Internet / Public", "#C62828"),
        ("internal", "━━━  Internal Network", "#1565C0"),
    ]
    cols, item_w, item_h = 3, 230, 30
    for idx, (key, text, color) in enumerate(legend_items):
        col = idx % cols
        lrow = idx // cols
        lx = legend_x + 12 + col * item_w
        ly = legend_y + 36 + lrow * item_h
        fill = _NET_PATH_STYLES[key]["node_fill"]
        stroke = _NET_PATH_STYLES[key]["node_stroke"]
        chip = ET.SubElement(
            root, "mxCell", id=f"net-legend-{key}",
            value=text,
            style=(
                f"rounded=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.5;"
                "fontSize=10;align=left;verticalAlign=middle;html=1;"
            ),
            parent="1", vertex="1",
        )
        ET.SubElement(chip, "mxGeometry", x=str(lx), y=str(ly), width=str(item_w - 10), height="24", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_lld_security_access_drawio(access_rows: list[dict]) -> str:
    mxfile, root = _mxfile("LLD Security Access")

    left_x = 60
    right_x = 560
    y = 80
    gap = 100
    actors: dict[str, str] = {}
    targets: dict[str, str] = {}

    def actor_node(name: str) -> str:
        if name in actors:
            return actors[name]
        aid = f"act-{_slug(name)}-{len(actors)}"
        yy = y + len(actors) * gap
        actors[name] = aid
        cell = ET.SubElement(
            root,
            "mxCell",
            id=aid,
            value=name,
            style="shape=mxgraph.aws4.users;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=11;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(left_x), y=str(yy), width="170", height="60", **{"as": "geometry"})
        return aid

    def target_node(name: str) -> str:
        if name in targets:
            return targets[name]
        tid = f"tgt-{_slug(name)}-{len(targets)}"
        yy = y + len(targets) * gap
        targets[name] = tid
        cell = ET.SubElement(
            root,
            "mxCell",
            id=tid,
            value=name,
            style="rounded=1;whiteSpace=wrap;align=center;fillColor=#f8cecc;strokeColor=#b85450;fontSize=11;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(right_x), y=str(yy), width="220", height="60", **{"as": "geometry"})
        return tid

    for i, row in enumerate(access_rows):
        src = actor_node(row["actor"])
        tgt = target_node(row["target"])
        label = " | ".join(
            [
                x
                for x in [
                    row.get("access_type", ""),
                    row.get("authn", ""),
                    row.get("authz", ""),
                    row.get("secret", ""),
                    row.get("encryption", ""),
                ]
                if x
            ]
        )
        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"sedge-{i}",
            value=label,
            style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;fontSize=10;",
            parent="1",
            source=src,
            target=tgt,
            edge="1",
        )
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


_DRAWIO_MACRO = (
    '<ac:structured-macro ac:name="drawio" ac:schema-version="1">'
    '<ac:parameter ac:name="border">true</ac:parameter>'
    '<ac:parameter ac:name="viewerToolbar">true</ac:parameter>'
    '<ac:parameter ac:name="simpleViewer">false</ac:parameter>'
    '<ac:parameter ac:name="editable">true</ac:parameter>'
    '<ac:parameter ac:name="diagramDisplayName">{display_name}</ac:parameter>'
    '<ac:parameter ac:name="diagramName">{filename}</ac:parameter>'
    '<ac:parameter ac:name="pageId">{page_id}</ac:parameter>'
    '</ac:structured-macro>'
)


def replace_lld_placeholder(html: str, key: str, filename: str, display_name: str, page_id: str) -> str:
    macro = _DRAWIO_MACRO.format(display_name=display_name, filename=filename, page_id=page_id)
    pattern = re.compile(
        r"<p[^>]*>\s*<strong[^>]*>\[\[LLD_DIAGRAM:" + re.escape(key) + r"\]\]</strong>\s*</p>",
        re.IGNORECASE,
    )
    new_html, count = pattern.subn(macro, html)
    if count == 0:
        new_html = html.replace(f"[[LLD_DIAGRAM:{key}]]", macro)
    return new_html


def replace_lld_flow_playback_tabs_placeholder(html: str, filename: str, display_name: str, page_id: str) -> str:
    """Replace flow playback placeholder with a single multi-tab drawio diagram."""
    macro = _DRAWIO_MACRO.format(display_name=display_name, filename=filename, page_id=page_id)
    pattern = re.compile(
        r"<p[^>]*>\s*<strong[^>]*>\[\[LLD_DIAGRAM:flow-playback-tabs\]\]</strong>\s*</p>",
        re.IGNORECASE,
    )
    new_html, count = pattern.subn(macro, html)
    if count == 0:
        new_html = html.replace("[[LLD_DIAGRAM:flow-playback-tabs]]", macro)
    return new_html


def generate_lld_flow_playback_multi_page_drawio(connections: list[dict]) -> str:
    """Generate a single drawio file with 8 tabs (pages), one for each step S1-S8.
    Includes AWS icons, clear direction indicators, and detailed explanations."""
    mxfile = ET.Element("mxfile")
    mxfile.set("host", "app.diagrams.net")
    mxfile.set("modified", "2024-01-01T00:00:00.000Z")
    mxfile.set("agent", "Mozilla/5.0")
    mxfile.set("version", "20.3.0")

    def _plain_step_phrase(source: str, target: str, protocol_text: str, path_text: str) -> tuple[str, str]:
        hints = f"{source} {target} {protocol_text} {path_text}".lower()
        if "sftp" in hints or "transfer" in hints:
            return ("Move file to the next system", "This keeps the ingestion flow moving safely.")
        if "bucket" in hints or "s3" in hints:
            return ("Store the file in landing storage", "This gives us a durable raw copy.")
        if "validation" in hints:
            return ("Check file quality and format", "This prevents bad data from moving forward.")
        if "queue" in hints:
            return ("Send work to the processing queue", "This smooths load and avoids bottlenecks.")
        if "database" in hints or "rds" in hints or "curated" in hints:
            return ("Save approved data to curated store", "This makes trusted data available for use.")
        if "monitor" in hints or "alert" in hints or "cloudwatch" in hints:
            return ("Send status and alert signals", "This helps operations react quickly.")
        return ("Pass data to the next component", "This continues the end-to-end processing path.")
    
    for step_index, conn in enumerate(connections, start=1):
        total_steps = len(connections)
        diagram = ET.SubElement(mxfile, "diagram", name=f"Step S{step_index}")
        model = ET.SubElement(
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
            pageWidth="1600",
            pageHeight="1200",
            math="0",
            shadow="0",
        )
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")

        src = (conn.get("source") or "Source").strip()
        tgt = (conn.get("target") or "Target").strip()
        protocol = (conn.get("protocol") or "").strip()
        port = (conn.get("port") or "").strip()
        path = (conn.get("network_path") or "").strip()
        auth = (conn.get("auth") or "").strip()

        # Title
        title = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-step-title-{step_index}",
            value=f"Step S{step_index} of S{total_steps}: {src} → {tgt}",
            style="text;fontSize=18;fontStyle=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(title, "mxGeometry", x="20", y="20", width="1540", height="40", **{"as": "geometry"})

        # Source node with icon
        src_card = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-step-src-card-{step_index}",
            value="",
            style="rounded=1;fillColor=#FFFFFF;strokeColor=#1D4ED8;strokeWidth=2.6;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(src_card, "mxGeometry", x="60", y="110", width="340", height="250", **{"as": "geometry"})

        src_icon_panel = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-step-src-icon-panel-{step_index}",
            value="",
            style="rounded=1;fillColor=#EFF6FF;strokeColor=#93C5FD;strokeWidth=1.2;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(src_icon_panel, "mxGeometry", x="150", y="132", width="160", height="160", **{"as": "geometry"})

        # Source icon area
        src_icon_hint = " ".join([src, (conn.get("protocol") or "").strip()]).lower()
        src_native_icon = _resolve_native_aws4_icon({"name": src, "service": conn.get("protocol", ""), "purpose": "", "layer": "", "network_zone": ""})
        src_icon_url = None if src_native_icon else get_icon_url(src_icon_hint)
        
        icon_sz = 126
        icon_x = 167
        icon_y = 150
        
        if src_native_icon:
            res_icon, fill_color = src_native_icon
            src_icon = ET.SubElement(
                root,
                "mxCell",
                id=f"flow-step-src-icon-{step_index}",
                value="",
                style=(
                    "shape=mxgraph.aws4.resourceIcon;"
                    f"resIcon=mxgraph.aws4.{res_icon};"
                    f"fillColor={fill_color};strokeColor=#FFFFFF;gradientColor=none;"
                    "dashed=0;aspect=fixed;outlineConnect=0;"
                ),
                parent="1",
                vertex="1",
            )
            ET.SubElement(src_icon, "mxGeometry", x=str(icon_x), y=str(icon_y), width=str(icon_sz), height=str(icon_sz), **{"as": "geometry"})
        elif src_icon_url:
            src_icon = ET.SubElement(
                root,
                "mxCell",
                id=f"flow-step-src-icon-{step_index}",
                value="",
                style=f"image;aspect=fixed;html=1;points=[];align=center;fontSize=12;image={_to_drawio_image_uri(src_icon_url)};",
                parent="1",
                vertex="1",
            )
            ET.SubElement(src_icon, "mxGeometry", x=str(icon_x), y=str(icon_y), width=str(icon_sz), height=str(icon_sz), **{"as": "geometry"})

        # Source label
        src_label = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-step-src-label-{step_index}",
            value=f"<b>{src}</b>",
            style="text;html=1;align=center;verticalAlign=bottom;fontSize=11;fontStyle=1;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(src_label, "mxGeometry", x="70", y="315", width="320", height="30", **{"as": "geometry"})

        # Arrow with label
        arrow_text = "←→" if any(k in f"{protocol} {path} {auth}".lower() for k in ["bi-directional", "bidirectional", "two-way", "two way", "request/response", "request-response", "mutual"]) else "→"
        arrow_label = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-step-arrow-{step_index}",
            value=f"<b>{arrow_text}</b><br/><b>S{step_index}</b>",
            style="text;html=1;align=center;verticalAlign=middle;fontSize=32;fontStyle=1;strokeColor=none;fillColor=none;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(arrow_label, "mxGeometry", x="700", y="165", width="120", height="120", **{"as": "geometry"})

        # Target node with icon
        tgt_card = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-step-tgt-card-{step_index}",
            value="",
            style="rounded=1;fillColor=#FFFFFF;strokeColor=#16A34A;strokeWidth=2.6;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(tgt_card, "mxGeometry", x="1120", y="110", width="340", height="250", **{"as": "geometry"})

        tgt_icon_panel = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-step-tgt-icon-panel-{step_index}",
            value="",
            style="rounded=1;fillColor=#ECFDF5;strokeColor=#86EFAC;strokeWidth=1.2;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(tgt_icon_panel, "mxGeometry", x="1210", y="132", width="160", height="160", **{"as": "geometry"})

        # Target icon area
        tgt_icon_hint = " ".join([tgt, (conn.get("protocol") or "").strip()]).lower()
        tgt_native_icon = _resolve_native_aws4_icon({"name": tgt, "service": conn.get("protocol", ""), "purpose": "", "layer": "", "network_zone": ""})
        tgt_icon_url = None if tgt_native_icon else get_icon_url(tgt_icon_hint)

        icon_x = 1227
        if tgt_native_icon:
            res_icon, fill_color = tgt_native_icon
            tgt_icon = ET.SubElement(
                root,
                "mxCell",
                id=f"flow-step-tgt-icon-{step_index}",
                value="",
                style=(
                    "shape=mxgraph.aws4.resourceIcon;"
                    f"resIcon=mxgraph.aws4.{res_icon};"
                    f"fillColor={fill_color};strokeColor=#FFFFFF;gradientColor=none;"
                    "dashed=0;aspect=fixed;outlineConnect=0;"
                ),
                parent="1",
                vertex="1",
            )
            ET.SubElement(tgt_icon, "mxGeometry", x=str(icon_x), y=str(icon_y), width=str(icon_sz), height=str(icon_sz), **{"as": "geometry"})
        elif tgt_icon_url:
            tgt_icon = ET.SubElement(
                root,
                "mxCell",
                id=f"flow-step-tgt-icon-{step_index}",
                value="",
                style=f"image;aspect=fixed;html=1;points=[];align=center;fontSize=12;image={_to_drawio_image_uri(tgt_icon_url)};",
                parent="1",
                vertex="1",
            )
            ET.SubElement(tgt_icon, "mxGeometry", x=str(icon_x), y=str(icon_y), width=str(icon_sz), height=str(icon_sz), **{"as": "geometry"})

        # Target label
        tgt_label = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-step-tgt-label-{step_index}",
            value=f"<b>{tgt}</b>",
            style="text;html=1;align=center;verticalAlign=bottom;fontSize=11;fontStyle=1;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(tgt_label, "mxGeometry", x="1130", y="315", width="320", height="30", **{"as": "geometry"})

        plain_action, plain_reason = _plain_step_phrase(src, tgt, protocol, path)
        simple_direction = "Two-way data flow" if arrow_text == "←→" else "One-way data flow"

        # Build plain-language explanation
        details_html = f"""
<b style="font-size:16px;">Step S{step_index}: {src} to {tgt}</b><br/>
<span style="font-size:13px;">{plain_action}</span><br/><br/>

<b style="font-size:13px;">Quick meaning</b><br/>
- {plain_reason}<br/>
- Direction: {simple_direction}<br/>
- Transport: {protocol if protocol else 'Not specified'} on port {port if port else 'N/A'}<br/>
- Path: {path if path else 'Not specified'}<br/>
- Security check: {auth if auth else 'Not specified'}<br/><br/>

<b style="font-size:13px;">In one line</b><br/>
Data moves from <b>{src}</b> to <b>{tgt}</b> in step <b>S{step_index}</b>.
"""

        # Fit explanation box to content length on each tab.
        details_line_count = details_html.count("<br/>") + 2
        details_y = 390
        details_text_y = 408
        details_text_height = max(180, min(500, details_line_count * 20))
        details_panel_height = details_text_height + 30

        details_panel = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-step-details-panel-{step_index}",
            value="",
            style="rounded=1;fillColor=#F0F9FF;strokeColor=#0EA5E9;strokeWidth=1.5;dashed=0;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(details_panel, "mxGeometry", x="50", y=str(details_y), width="1480", height=str(details_panel_height), **{"as": "geometry"})

        details_text = ET.SubElement(
            root,
            "mxCell",
            id=f"flow-step-details-text-{step_index}",
            value=details_html,
            style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=9;strokeColor=none;fillColor=none;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(details_text, "mxGeometry", x="80", y=str(details_text_y), width="1420", height=str(details_text_height), **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_lld_flow_step_drawio(step_index: int, total_steps: int, conn: dict) -> str:
    mxfile, root = _mxfile(f"LLD Flow Step S{step_index}")

    src = (conn.get("source") or "Source").strip()
    tgt = (conn.get("target") or "Target").strip()
    protocol = (conn.get("protocol") or "").strip()
    port = (conn.get("port") or "").strip()
    path = (conn.get("network_path") or "").strip()
    auth = (conn.get("auth") or "").strip()

    title = ET.SubElement(
        root,
        "mxCell",
        id=f"flow-step-title-{step_index}",
        value=f"Flow Playback: Step S{step_index} of S{total_steps}",
        style="text;fontSize=16;fontStyle=1;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(title, "mxGeometry", x="20", y="20", width="980", height="30", **{"as": "geometry"})

    src_node = ET.SubElement(
        root,
        "mxCell",
        id=f"flow-step-src-{step_index}",
        value=f"<b>{src}</b>",
        style="rounded=1;whiteSpace=wrap;html=1;align=center;verticalAlign=middle;fillColor=#DBEAFE;strokeColor=#1D4ED8;strokeWidth=1.8;fontSize=12;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(src_node, "mxGeometry", x="120", y="220", width="260", height="90", **{"as": "geometry"})

    tgt_node = ET.SubElement(
        root,
        "mxCell",
        id=f"flow-step-tgt-{step_index}",
        value=f"<b>{tgt}</b>",
        style="rounded=1;whiteSpace=wrap;html=1;align=center;verticalAlign=middle;fillColor=#DCFCE7;strokeColor=#16A34A;strokeWidth=1.8;fontSize=12;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(tgt_node, "mxGeometry", x="760", y="220", width="260", height="90", **{"as": "geometry"})

    route_parts = [x for x in [protocol, port, path] if x]
    route = " | ".join(route_parts) if route_parts else "No protocol details"
    bidir = any(k in f"{protocol} {path} {auth}".lower() for k in ["bi-directional", "bidirectional", "two-way", "two way", "request/response", "request-response", "mutual"])
    symbol = "<->" if bidir else "->"

    edge = ET.SubElement(
        root,
        "mxCell",
        id=f"flow-step-edge-{step_index}",
        value=f"S{step_index} {symbol}",
        style=(
            "edgeStyle=elbowEdgeStyle;elbow=horizontal;rounded=1;jettySize=auto;"
            "fontSize=14;fontStyle=1;strokeWidth=3;strokeColor=#EA580C;"
            "endArrow=block;endFill=1;labelBackgroundColor=#FFEDD5;labelBorderColor=#FB923C;"
            + ("startArrow=block;startFill=1;" if bidir else "")
        ),
        parent="1",
        source=f"flow-step-src-{step_index}",
        target=f"flow-step-tgt-{step_index}",
        edge="1",
    )
    ET.SubElement(edge, "mxGeometry", relative="1", x="0", y="-20", **{"as": "geometry"})

    details = [
        f"<b>Source:</b> {src}",
        f"<b>Target:</b> {tgt}",
        f"<b>Direction:</b> {'Bi-directional' if bidir else 'One-way'}",
        f"<b>Channel:</b> {route}",
    ]
    if auth:
        details.append(f"<b>Authentication/Authorization:</b> {auth}")

    panel = ET.SubElement(
        root,
        "mxCell",
        id=f"flow-step-panel-{step_index}",
        value="",
        style="rounded=1;fillColor=#F8FAFC;strokeColor=#94A3B8;strokeWidth=1.4;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(panel, "mxGeometry", x="120", y="360", width="900", height="170", **{"as": "geometry"})

    panel_text = ET.SubElement(
        root,
        "mxCell",
        id=f"flow-step-panel-text-{step_index}",
        value="<br/><br/>".join(details),
        style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=11;strokeColor=none;fillColor=none;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(panel_text, "mxGeometry", x="140", y="380", width="860", height="130", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


# Note: generate_lld_flow_step_drawio() is kept for potential future use but not called


def lld_detailed_sections_html() -> str:
    return """
<hr/>
<h2>Detailed Architecture Diagrams</h2>
<p><em>This section provides detailed LLD visualisations for architecture implementation, network/service connections, and security access control paths.</em></p>

<h3>1. Detailed Component Architecture</h3>
<p>Capture each deployable service/component with layer, network placement, and service implementation detail.</p>
<table>
  <thead>
    <tr><th>Component Name</th><th>Layer</th><th>Service / Technology</th><th>Network Zone / Subnet</th><th>Purpose</th></tr>
  </thead>
  <tbody>
    <tr><td></td><td>Edge / Network / Platform / Application / Data / Security</td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>
<p><strong>[[LLD_DIAGRAM:detailed-architecture]]</strong></p>

<h3>2. Detailed Network and Service Connections</h3>
<p>Capture all service-to-service and network-level paths, including protocols, ports, and auth method.</p>
<table>
  <thead>
    <tr><th>Source</th><th>Target</th><th>Protocol</th><th>Port</th><th>Network Path</th><th>Authentication Method</th></tr>
  </thead>
  <tbody>
    <tr><td></td><td></td><td>HTTPS / TCP / gRPC / AMQP</td><td></td><td>Internet / Private Link / VNet / Peering / Transit</td><td>mTLS / OAuth2 / API Key / Managed Identity</td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>
<p><strong>[[LLD_DIAGRAM:network-connections]]</strong></p>

<h3>3. Security Access Connections</h3>
<p>Capture identity-driven access links from users/services to target services and data stores with control details.</p>
<table>
  <thead>
    <tr><th>Actor / Service</th><th>Target Resource</th><th>Access Type</th><th>Authentication</th><th>Authorisation</th><th>Secret / Key Source</th><th>Encryption in Transit</th></tr>
  </thead>
  <tbody>
    <tr><td></td><td></td><td>Control Plane / Data Plane / Admin</td><td>Entra ID / OIDC / mTLS</td><td>RBAC / ABAC / ACL</td><td>Key Vault / KMS / Secret Manager</td><td>TLS 1.2+ / TLS 1.3</td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
  </tbody>
</table>
<p><strong>[[LLD_DIAGRAM:security-access]]</strong></p>

<h3>4. Flow Playback (Multi-Tab Diagram)</h3>
<p>Navigate through each step of the data flow using the tabs below. Each tab isolates one step (S1-S8) with source, target, channel, and authentication details.</p>
<p><strong>[[LLD_DIAGRAM:flow-playback-tabs]]</strong></p>
"""


def rebuild_lld_detailed_section(body_html: str) -> str:
    """Ensure exactly one LLD detailed-diagrams block exists (remove duplicates, keep one fresh block)."""
    soup = BeautifulSoup(body_html, "html.parser")

    first_marker = None
    for h2 in soup.find_all("h2"):
        if "detailed architecture diagrams" in h2.get_text(" ", strip=True).lower():
            first_marker = h2
            break

    if first_marker is not None:
        node = first_marker
        while node is not None:
            next_node = node.next_sibling
            node.decompose()
            node = next_node

    fragment = BeautifulSoup(lld_detailed_sections_html(), "html.parser")
    for child in list(fragment.contents):
        soup.append(child)

    return str(soup)


def default_lld_page_html() -> str:
    return """
<h1>Low-Level Design (LLD) Solution Architecture Template</h1>
<p><em>Implementation-level architecture detail for engineering delivery.</em></p>
""" + lld_detailed_sections_html()


def main() -> None:
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    main_title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "Solution Architecture")
    main_page_id = (os.getenv("CONFLUENCE_MAIN_PAGE_ID") or "520783944").strip()
    lld_title = os.getenv("CONFLUENCE_LLD_PAGE_TITLE", "Low-Level Design (LLD) Solution Architecture Template")
    lld_page_id_env = (os.getenv("CONFLUENCE_LLD_PAGE_ID") or "").strip()

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    print("=" * 80)
    print("LOW LEVEL DESIGN (LLD) DETAILED DIAGRAM GENERATOR")
    print("=" * 80)

    try:
        main_page = find_page_by_title(session, base_url, space_key, main_title)
    except ValueError:
        main_page = get_page_by_id(session, base_url, main_page_id)
    print(f"\nFound main page: {main_page['title']} (ID: {main_page['id']})")

    try:
        if lld_page_id_env:
            lld_page = get_page_by_id(session, base_url, lld_page_id_env)
        else:
            lld_page = find_page_by_title(session, base_url, space_key, lld_title)
        lld_page_id = lld_page["id"]
        lld_version = lld_page["version"]["number"]
        body_html = lld_page["body"]["storage"]["value"]
        print(f"Found LLD page: {lld_page['title']} (ID: {lld_page_id})")
    except ValueError:
        created = create_child_page(
            session,
            base_url,
            space_key,
            main_page["id"],
            lld_title,
            default_lld_page_html(),
        )
        lld_page_id = created["id"]
        lld_version = created["version"]["number"]
        body_html = created["body"]["storage"]["value"]
        print(f"Created LLD page: {lld_title} (ID: {lld_page_id})")

    updated_html = rebuild_lld_detailed_section(body_html)
    if updated_html != body_html:
        print("\nNormalizing LLD detailed diagram section (remove duplicates, keep one clean block)...")
        saved = update_page_body(
            session,
            base_url,
            lld_page_id,
            lld_version,
            lld_title,
            updated_html,
        )
        lld_version = saved["version"]["number"]
        body_html = updated_html
        print("  LLD section normalized.")

    print("\nSyncing HLD tables into LLD relevant tables and applying color theme...")
    synced_html, sync_summary = sync_main_to_lld_tables(body_html, main_page["body"]["storage"]["value"])
    if synced_html != body_html:
        saved = update_page_body(
            session,
            base_url,
            lld_page_id,
            lld_version,
            lld_title,
            synced_html,
        )
        lld_version = saved["version"]["number"]
        body_html = synced_html
    print(f"  Components synced: {sync_summary['components_synced']}")
    print(f"  Connections synced: {sync_summary['connections_synced']}")
    print(f"  Security links synced: {sync_summary['security_synced']}")
    print(f"  Data flows synced: {sync_summary['dataflows_synced']}")

    inherited_context = build_inherited_design_context(main_page["body"]["storage"]["value"])

    print("\nParsing LLD detailed tables...")
    components = parse_lld_components(body_html)
    connections = parse_lld_connections(body_html)
    security_rows = parse_lld_security_access(body_html)
    print(f"  Components: {len(components)}")
    print(f"  Connections: {len(connections)}")
    print(f"  Security access links: {len(security_rows)}")

    def _merge_components(primary: list[dict], inherited: list[dict]) -> list[dict]:
        merged: dict[str, dict] = {}
        for item in inherited:
            key = (item.get("name") or "").strip().lower()
            if key:
                merged[key] = dict(item)
        for item in primary:
            key = (item.get("name") or "").strip().lower()
            if not key:
                continue
            base = merged.get(key, {})
            merged[key] = {
                "name": item.get("name") or base.get("name", ""),
                "layer": item.get("layer") or base.get("layer", "Application"),
                "service": item.get("service") or base.get("service", ""),
                "network_zone": item.get("network_zone") or base.get("network_zone", "TBC"),
                "purpose": item.get("purpose") or base.get("purpose", ""),
            }
        return list(merged.values())

    def _merge_connections(primary: list[dict], inherited: list[dict]) -> list[dict]:
        merged: dict[tuple[str, str], dict] = {}
        for conn in inherited:
            sk = (conn.get("source") or "").strip().lower()
            tk = (conn.get("target") or "").strip().lower()
            if sk and tk:
                merged[(sk, tk)] = dict(conn)
        for conn in primary:
            sk = (conn.get("source") or "").strip().lower()
            tk = (conn.get("target") or "").strip().lower()
            if not sk or not tk:
                continue
            base = merged.get((sk, tk), {})
            merged[(sk, tk)] = {
                "source": conn.get("source") or base.get("source", ""),
                "target": conn.get("target") or base.get("target", ""),
                "protocol": conn.get("protocol") or base.get("protocol", ""),
                "port": conn.get("port") or base.get("port", ""),
                "network_path": conn.get("network_path") or base.get("network_path", ""),
                "auth": conn.get("auth") or base.get("auth", ""),
            }
        return list(merged.values())

    def _merge_security(primary: list[dict], inherited: list[dict]) -> list[dict]:
        merged: dict[tuple[str, str], dict] = {}
        for row in inherited:
            ak = (row.get("actor") or "").strip().lower()
            tk = (row.get("target") or "").strip().lower()
            if ak and tk:
                merged[(ak, tk)] = dict(row)
        for row in primary:
            ak = (row.get("actor") or "").strip().lower()
            tk = (row.get("target") or "").strip().lower()
            if not ak or not tk:
                continue
            base = merged.get((ak, tk), {})
            merged[(ak, tk)] = {
                "actor": row.get("actor") or base.get("actor", ""),
                "target": row.get("target") or base.get("target", ""),
                "access_type": row.get("access_type") or base.get("access_type", "Data Plane"),
                "authn": row.get("authn") or base.get("authn", ""),
                "authz": row.get("authz") or base.get("authz", "RBAC"),
                "secret": row.get("secret") or base.get("secret", "Managed Secret Store"),
                "encryption": row.get("encryption") or base.get("encryption", "TLS 1.2+"),
            }
        return list(merged.values())

    if not components and not connections:
        print("\nLLD tables are empty. Falling back to main page architecture tables...")
        components = inherited_context["components"]
        connections = inherited_context["connections"]
        print(f"  Fallback components: {len(components)}")
        print(f"  Fallback connections: {len(connections)}")

    # Always merge with inherited context so required components/paths are preserved.
    components = _merge_components(components, inherited_context["components"])
    connections = _merge_connections(connections, inherited_context["connections"])
    security_rows = _merge_security(security_rows, inherited_context["security_rows"])

    # ── EDAP pattern detection and automatic LLD diagram enrichment
    if EDAP_KB_AVAILABLE:
        # Build lightweight proxy lists from LLD-format dicts for the KB functions
        _hld_comps = [{"name": c.get("name", ""), "layer": c.get("layer", ""),
                       "technology": c.get("service", ""), "description": c.get("purpose", "")} for c in components]
        _hld_conns = [{"from": c.get("source", ""), "to": c.get("target", ""),
                       "label": c.get("protocol", "")} for c in connections]
        _hld_flows = [{"source": c.get("source", ""), "destination": c.get("target", ""),
                       "data": c.get("protocol", "")} for c in connections]
        _hld_ents  = [{"name": e.get("name", ""), "type": e.get("layer", ""),
                       "interaction": "", "direction": ""}
                     for e in inherited_context.get("context_entities", [])]
        explicit_edap = [p.strip() for p in os.getenv("EDAP_PATTERN_IDS", "").split(",") if p.strip()]
        edap_patterns = detect_edap_patterns(_hld_comps, _hld_conns, _hld_flows, _hld_ents, explicit_edap or None)
        if edap_patterns:
            print(f"\n  {build_edap_integration_summary(edap_patterns)}")
            # Inject EDAP AWS services as LLD-format components
            _existing_names = {c.get("name", "").lower() for c in components}
            for pattern in edap_patterns:
                for svc in pattern.get("aws_services", []):
                    if svc["name"].lower() not in _existing_names:
                        components.append({
                            "name": svc["name"],
                            "layer": svc.get("layer", "Managed"),
                            "service": svc.get("technology", ""),
                            "network_zone": svc.get("layer", "managed"),
                            "purpose": f"[{pattern['id']}] {pattern['name']}",
                        })
                        _existing_names.add(svc["name"].lower())
            # Inject EDAP connections as LLD-format connections
            _existing_conns = {(c.get("source", "").lower(), c.get("target", "").lower()) for c in connections}
            for pattern in edap_patterns:
                for conn in pattern.get("edap_connections", []):
                    key = (conn["from"].lower(), conn["to"].lower())
                    if key not in _existing_conns:
                        connections.append({
                            "source": conn["from"],
                            "target": conn["to"],
                            "protocol": conn.get("label", ""),
                            "port": "",
                            "network_path": "EDAP",
                            "auth": "IAM / SSE-KMS",
                        })
                        _existing_conns.add(key)
        else:
            print("\n  No EDAP integration patterns detected in LLD tables.")
            print("  Tip: set EDAP_PATTERN_IDS=EDAP-INT-01,EDAP-INT-03 in .env to force specific patterns.")
    else:
        edap_patterns = []

    # ── UKHSA patterns detection and automatic LLD diagram enrichment
    if UKHSA_KB_AVAILABLE:
        _hld_comps_u = [{"name": c.get("name", ""), "layer": c.get("layer", ""),
                         "technology": c.get("service", ""), "description": c.get("purpose", "")} for c in components]
        _hld_conns_u = [{"from": c.get("source", ""), "to": c.get("target", ""),
                         "label": c.get("protocol", "")} for c in connections]
        _hld_flows_u = [{"id": f"df-{i}", "source": c.get("source", ""), "destination": c.get("target", ""),
                         "data": c.get("protocol", "")} for i, c in enumerate(connections)]
        _hld_ents_u  = [{"name": e.get("name", ""), "type": e.get("layer", ""),
                         "interaction": "", "direction": ""}
                        for e in inherited_context.get("context_entities", [])]
        explicit_ukhsa = [p.strip() for p in os.getenv("UKHSA_PATTERN_IDS", "").split(",") if p.strip()]
        ukhsa_patterns = detect_ukhsa_patterns(_hld_comps_u, _hld_conns_u, _hld_flows_u, _hld_ents_u, explicit_ukhsa or None)
        if ukhsa_patterns:
            print(f"\n  {build_ukhsa_pattern_summary(ukhsa_patterns)}")
            # Inject UKHSA-pattern components as LLD-format components
            _existing_names = {c.get("name", "").lower() for c in components}
            for pattern in ukhsa_patterns:
                for svc in pattern.get("components", []):
                    if svc["name"].lower() not in _existing_names:
                        components.append({
                            "name": svc["name"],
                            "layer": svc.get("layer", "Managed"),
                            "service": svc.get("technology", ""),
                            "network_zone": svc.get("layer", "managed"),
                            "purpose": f"[{pattern['id']}] {pattern['name']}",
                        })
                        _existing_names.add(svc["name"].lower())
            # Inject UKHSA connections as LLD-format connections
            _existing_conns = {(c.get("source", "").lower(), c.get("target", "").lower()) for c in connections}
            for pattern in ukhsa_patterns:
                for conn in pattern.get("connections", []):
                    key = (conn["from"].lower(), conn["to"].lower())
                    if key not in _existing_conns:
                        connections.append({
                            "source": conn["from"],
                            "target": conn["to"],
                            "protocol": conn.get("label", ""),
                            "port": "",
                            "network_path": f"UKHSA-{pattern['family']}",
                            "auth": "IAM / KMS (UKHSA mandatory)",
                        })
                        _existing_conns.add(key)
        else:
            print("\n  No UKHSA patterns detected in LLD tables.")
            print("  Tip: set UKHSA_PATTERN_IDS=1A,3C,UKHSA-INF-01 in .env to force specific patterns.")
    else:
        ukhsa_patterns = []

    if not security_rows and connections:
        security_rows = derive_security_rows_from_connections(connections)
        if security_rows:
            print(f"  Derived security access links: {len(security_rows)}")

    print(
        "  Inherited context applied: "
        f"components={len(inherited_context['components'])}, "
        f"connections={len(inherited_context['connections'])}, "
        f"context_entities={len(inherited_context['context_entities'])}, "
        f"network_segmentation={len(inherited_context['segmentation'])}"
    )

    if not components:
        components = default_components_template()
        print("  Using starter template components for initial detailed diagram.")
    if not connections:
        connections = default_connections_template()
        print("  Using starter template network/service connections.")
    if not security_rows:
        security_rows = default_security_template()
        print("  Using starter template security access connections.")

    embed_html = body_html

    if components:
        print("\nGenerating detailed component architecture diagram...")
        xml = generate_lld_detailed_architecture_drawio(components, connections)
        save_local_drawio("lld-detailed-architecture.drawio", xml)
        upload_attachment(session, base_url, lld_page_id, "lld-detailed-architecture.drawio", xml)
        embed_html = replace_lld_placeholder(
            embed_html,
            "detailed-architecture",
            "lld-detailed-architecture.drawio",
            "LLD Detailed Architecture",
            lld_page_id,
        )

    if connections:
        print("\nGenerating network/service connections diagram...")
        xml = generate_lld_network_connections_drawio(connections)
        save_local_drawio("lld-network-connections.drawio", xml)
        upload_attachment(session, base_url, lld_page_id, "lld-network-connections.drawio", xml)
        embed_html = replace_lld_placeholder(
            embed_html,
            "network-connections",
            "lld-network-connections.drawio",
            "LLD Network Connections",
            lld_page_id,
        )

    if security_rows:
        print("\nGenerating security access connections diagram...")
        xml = generate_lld_security_access_drawio(security_rows)
        save_local_drawio("lld-security-access.drawio", xml)
        upload_attachment(session, base_url, lld_page_id, "lld-security-access.drawio", xml)
        embed_html = replace_lld_placeholder(
            embed_html,
            "security-access",
            "lld-security-access.drawio",
            "LLD Security Access Connections",
            lld_page_id,
        )

    if connections:
        print("\nGenerating flow playback (multi-tab diagram)...")
        xml = generate_lld_flow_playback_multi_page_drawio(connections)
        save_local_drawio("lld-flow-playback-tabs.drawio", xml)
        upload_attachment(session, base_url, lld_page_id, "lld-flow-playback-tabs.drawio", xml)
        embed_html = replace_lld_flow_playback_tabs_placeholder(
            embed_html,
            "lld-flow-playback-tabs.drawio",
            "LLD Flow Playback (Tabs)",
            lld_page_id,
        )

    if embed_html != body_html:
        print("\nUpdating LLD page with embedded diagrams...")
        updated = update_page_body(
            session,
            base_url,
            lld_page_id,
            lld_version,
            lld_title,
            embed_html,
        )
    else:
        # Placeholders already replaced in a previous run — force a minor page
        # update so Confluence invalidates its cached draw.io renders.
        print("\nForcing page refresh to invalidate Confluence diagram cache...")
        updated = update_page_body(
            session,
            base_url,
            lld_page_id,
            lld_version,
            lld_title,
            body_html,
            minor_edit=True,
        )
    links = updated.get("_links", {})
    page_url = f"{links.get('base', base_url)}{links.get('webui', '')}"
    print(f"  Page updated: {page_url}")

    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
