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
        return session_copy.request(method, url, verify=verify, **kwargs)

    return session.request(method, url, verify=verify, **kwargs)


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


def update_page_body(session: requests.Session, base_url: str, page_id: str, version_number: int, title: str, body_html: str) -> dict:
    payload = {
        "version": {"number": version_number + 1},
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

    if api_token:
        bearer = requests.Session()
        bearer.headers.update({"Authorization": f"Bearer {api_token}", "X-Atlassian-Token": "no-check"})
        try:
            if existing:
                att_id = existing[0]["id"]
                resp = bearer.post(f"{url}/{att_id}/data", files=_make_files_payload(), verify=verify, timeout=30)
            else:
                resp = bearer.post(url, files=_make_files_payload(), verify=verify, timeout=30)
            if resp.status_code != 403:
                if resp.status_code not in (200, 201):
                    raise RuntimeError(f"Failed to upload {filename}: {resp.status_code} {resp.text}")
                print(f"  Uploaded: {filename}")
                return
        except Exception:
            pass

    if user_email and api_token:
        basic = requests.Session()
        basic.auth = HTTPBasicAuth(user_email, api_token)
        basic.headers.update({"X-Atlassian-Token": "no-check"})
        if existing:
            att_id = existing[0]["id"]
            resp = basic.post(f"{url}/{att_id}/data", files=_make_files_payload(), verify=verify, timeout=30)
        else:
            resp = basic.post(url, files=_make_files_payload(), verify=verify, timeout=30)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to upload {filename}: {resp.status_code} {resp.text}")
        print(f"  Uploaded: {filename}")
        return

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
    main_components, main_connections = parse_main_components_and_connections(main_html)
    main_dataflows = parse_main_dataflows(main_html)
    derived_security = derive_security_rows_from_connections(main_connections)

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
        pageWidth="1600",
        pageHeight="1200",
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
    layer_colors = {
        "edge": "#dae8fc",
        "network": "#d5e8d4",
        "platform": "#fff2cc",
        "application": "#f8cecc",
        "data": "#e1d5e7",
        "security": "#f5f5f5",
    }

    buckets: dict[str, list[dict]] = {l: [] for l in layer_order}
    for comp in components:
        layer_raw = (comp.get("layer") or "Application").strip().lower()
        match = "Application"
        for known in layer_order:
            if known.lower() in layer_raw or layer_raw in known.lower():
                match = known
                break
        buckets[match].append(comp)

    y = 30
    layer_y: dict[str, int] = {}
    for layer in layer_order:
        if buckets[layer]:
            layer_y[layer] = y
            y += 95

    label_w = 150
    box_w = 190
    box_h = 58
    x_start = 180

    id_map: dict[str, str] = {}
    for layer in layer_order:
        comps = buckets[layer]
        if not comps:
            continue

        label = ET.SubElement(
            root,
            "mxCell",
            id=f"layer-{_slug(layer)}",
            value=layer,
            style=(
                f"rounded=1;whiteSpace=wrap;align=center;fillColor={layer_colors.get(layer.lower(), '#f5f5f5')};"
                "fontStyle=1;fontSize=11;strokeColor=#999999;"
            ),
            parent="1",
            vertex="1",
        )
        ET.SubElement(label, "mxGeometry", x="20", y=str(layer_y[layer]), width=str(label_w - 30), height="56", **{"as": "geometry"})

        for i, comp in enumerate(comps):
            cid = f"cmp-{_slug(comp['name'])}"
            id_map[comp["name"].lower()] = cid
            value = comp["name"]
            if comp.get("service"):
                value += f"\n({comp['service']})"
            if comp.get("network_zone"):
                value += f"\n[{comp['network_zone']}]"
            cell = ET.SubElement(
                root,
                "mxCell",
                id=cid,
                value=value,
                style=(
                    f"rounded=1;whiteSpace=wrap;align=center;fillColor={layer_colors.get(layer.lower(), '#ffffff')};"
                    "strokeColor=#666666;fontSize=11;"
                ),
                parent="1",
                vertex="1",
            )
            ET.SubElement(
                cell,
                "mxGeometry",
                x=str(x_start + i * (box_w + 30)),
                y=str(layer_y[layer]),
                width=str(box_w),
                height=str(box_h),
                **{"as": "geometry"},
            )

    for i, conn in enumerate(connections):
        src = id_map.get(conn["source"].lower())
        tgt = id_map.get(conn["target"].lower())
        if not src or not tgt:
            continue
        label = " | ".join([x for x in [conn.get("protocol", ""), conn.get("port", ""), conn.get("network_path", "")] if x])
        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"edge-{i}",
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


def generate_lld_network_connections_drawio(connections: list[dict]) -> str:
    mxfile, root = _mxfile("LLD Network Connections")

    node_map: dict[str, str] = {}
    x = 40
    y = 120
    row = 0

    def node(name: str) -> str:
        nonlocal x, y, row
        key = name.lower().strip()
        if key in node_map:
            return node_map[key]
        nid = f"net-{_slug(name)}-{len(node_map)}"
        node_map[key] = nid
        cell = ET.SubElement(
            root,
            "mxCell",
            id=nid,
            value=name,
            style="rounded=1;whiteSpace=wrap;align=center;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=11;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width="180", height="56", **{"as": "geometry"})
        x += 260
        row += 1
        if row % 4 == 0:
            x = 40
            y += 140
        return nid

    for i, c in enumerate(connections):
        s = node(c["source"])
        t = node(c["target"])
        label = " | ".join(
            [
                x
                for x in [
                    c.get("protocol", ""),
                    c.get("port", ""),
                    c.get("network_path", ""),
                    c.get("auth", ""),
                ]
                if x
            ]
        )
        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"nedge-{i}",
            value=label,
            style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;fontSize=10;",
            parent="1",
            source=s,
            target=t,
            edge="1",
        )
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})

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

    print("\nParsing LLD detailed tables...")
    components = parse_lld_components(body_html)
    connections = parse_lld_connections(body_html)
    security_rows = parse_lld_security_access(body_html)
    print(f"  Components: {len(components)}")
    print(f"  Connections: {len(connections)}")
    print(f"  Security access links: {len(security_rows)}")

    if not components and not connections:
        print("\nLLD tables are empty. Falling back to main page architecture tables...")
        main_body = main_page["body"]["storage"]["value"]
        main_components, main_connections = parse_main_components_and_connections(main_body)
        components = main_components
        connections = main_connections
        print(f"  Fallback components: {len(components)}")
        print(f"  Fallback connections: {len(connections)}")

    if not security_rows and connections:
        security_rows = derive_security_rows_from_connections(connections)
        if security_rows:
            print(f"  Derived security access links: {len(security_rows)}")

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
        links = updated.get("_links", {})
        page_url = f"{links.get('base', base_url)}{links.get('webui', '')}"
        print(f"  Page updated: {page_url}")
    else:
        print("\nNo diagram embeddings updated yet.")
        print("Fill in at least one LLD detailed table row, then rerun this script.")

    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
