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
                    raise RuntimeError(f"Failed to upload {filename}: {resp.status_code} {resp.text}")
                print(f"  Uploaded: {filename}")
                return
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
            raise RuntimeError(f"Failed to upload {filename}: {resp.status_code} {resp.text}")
        print(f"  Uploaded: {filename}")
        return
    
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
<li>Complete the architecture tables in the main <strong>Solution Architecture</strong> page (Sections 10-13)</li>
<li>Run the diagram generation script: <code>./.venv/Scripts/python.exe ./confluence_update_diagrams.py</code></li>
<li>All diagrams will be auto-generated and embedded below</li>
</ol>

<hr/>

<h2>1. Context View Diagram</h2>
<p><strong>[[DIAGRAM:context-view]]</strong></p>

<h2>2. Logical View Diagram</h2>
<p><strong>[[DIAGRAM:logical-view]]</strong></p>

<h2>3. Solution Architecture Diagram</h2>
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
            "description": row[4] if len(row) > 4 else "",
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
                "primary_key": row[3] if len(row) > 3 else "",
                "sensitivity": row[4] if len(row) > 4 else "",
                "retention": row[5] if len(row) > 5 else "",
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
            }
        )
    return entities


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


def generate_dfd_drawio(dataflows: list[dict]) -> str:
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="Data Flow Diagram")
    ET.SubElement(diagram, "mxGraphModel",
                  dx="1422", dy="762", grid="1", gridSize="10", guides="1",
                  tooltips="1", connect="1", arrows="1", fold="1",
                  page="0", pageScale="1", pageWidth="1169", pageHeight="827",
                  math="0", shadow="0")
    root = ET.SubElement(diagram.find("mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    NODE_W, NODE_H = 140, 50
    X_GAP          = 60
    Y_CENTER        = 120
    x_counter       = [40]
    nodes: dict[str, str] = {}  # normalised name → cell id

    def get_or_create_node(name: str) -> str:
        key = name.strip().lower()
        if key not in nodes:
            cell_id = f"n-{_slug(name)}-{len(nodes)}"
            nodes[key] = cell_id
            x = x_counter[0]
            x_counter[0] += NODE_W + X_GAP
            cell = ET.SubElement(root, "mxCell",
                id=cell_id, value=name,
                style=("rounded=1;whiteSpace=wrap;align=center;"
                       "fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=11;"),
                parent="1", vertex="1",
            )
            ET.SubElement(cell, "mxGeometry",
                x=str(x), y=str(Y_CENTER),
                width=str(NODE_W), height=str(NODE_H),
                **{"as": "geometry"})
        return nodes[key]

    for i, flow in enumerate(dataflows):
        src_id = get_or_create_node(flow["source"])
        tgt_id = get_or_create_node(flow["destination"])
        label  = flow["data"]
        if flow["protocol"]:
            label += f"\n[{flow['protocol']}]"
        edge = ET.SubElement(root, "mxCell",
            id=f"df-e-{i}",
            value=label,
            style=("edgeStyle=orthogonalEdgeStyle;rounded=0;"
                   "orthogonalLoop=1;jettySize=auto;fontSize=10;"),
            parent="1", source=src_id, target=tgt_id, edge="1",
        )
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_dataset_relationship_drawio(datasets: list[dict], relationships: list[dict]) -> str:
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="Dataset Relationship Diagram")
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
        pageWidth="1169",
        pageHeight="827",
        math="0",
        shadow="0",
    )
    root = ET.SubElement(diagram.find("mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    BOX_W, BOX_H = 220, 70
    X_GAP, Y_GAP = 40, 40
    X_START, Y_START = 30, 30
    COLUMNS = 3

    dataset_cells: dict[str, str] = {}
    for i, ds in enumerate(datasets):
        row = i // COLUMNS
        col = i % COLUMNS
        x = X_START + col * (BOX_W + X_GAP)
        y = Y_START + row * (BOX_H + Y_GAP)
        cell_id = f"ds-{_slug(ds['name'])}-{i}"
        dataset_cells[ds["name"].lower()] = cell_id

        pk = f"PK: {ds['primary_key']}" if ds["primary_key"] else "PK: N/A"
        dtype = ds["type"] if ds["type"] else "Unknown"
        label = f"{ds['name']}\\n{dtype} | {pk}"
        cell = ET.SubElement(
            root,
            "mxCell",
            id=cell_id,
            value=label,
            style=(
                "rounded=1;whiteSpace=wrap;align=center;"
                "fillColor=#fff2cc;strokeColor=#d6b656;fontSize=11;"
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

    for i, rel in enumerate(relationships):
        src = dataset_cells.get(rel["source"].lower())
        tgt = dataset_cells.get(rel["target"].lower())
        if not src or not tgt:
            print(
                f"  Warning: skipping dataset relationship '{rel['source']} -> {rel['target']}' "
                "(dataset not found in Dataset Inventory)."
            )
            continue
        edge_label = rel["relation"]
        if rel["mapping"]:
            edge_label = f"{edge_label}\\n[{rel['mapping']}]" if edge_label else rel["mapping"]
        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"ds-edge-{i}",
            value=edge_label,
            style=(
                "edgeStyle=orthogonalEdgeStyle;rounded=0;"
                "orthogonalLoop=1;jettySize=auto;fontSize=10;"
            ),
            parent="1",
            source=src,
            target=tgt,
            edge="1",
        )
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_context_view_drawio(solution_name: str, entities: list[dict]) -> str:
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="Context View")
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
        pageWidth="1169",
        pageHeight="827",
        math="0",
        shadow="0",
    )
    root = ET.SubElement(diagram.find("mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    center_id = "solution-core"
    center = ET.SubElement(
        root,
        "mxCell",
        id=center_id,
        value=solution_name or "Data Solution",
        style="rounded=1;whiteSpace=wrap;align=center;fillColor=#ffe6cc;strokeColor=#d79b00;fontSize=12;fontStyle=1;",
        parent="1",
        vertex="1",
    )
    ET.SubElement(center, "mxGeometry", x="450", y="250", width="240", height="80", **{"as": "geometry"})

    radius = 260
    cx, cy = 570, 290
    import math

    for i, ent in enumerate(entities):
        angle = (2 * math.pi * i / max(1, len(entities)))
        x = int(cx + radius * math.cos(angle) - 90)
        y = int(cy + radius * math.sin(angle) - 30)
        ent_id = f"ctx-{_slug(ent['name'])}-{i}"
        node = ET.SubElement(
            root,
            "mxCell",
            id=ent_id,
            value=f"{ent['name']}\\n({ent['type']})" if ent.get("type") else ent["name"],
            style="rounded=1;whiteSpace=wrap;align=center;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=10;",
            parent="1",
            vertex="1",
        )
        ET.SubElement(node, "mxGeometry", x=str(x), y=str(y), width="180", height="60", **{"as": "geometry"})

        edge = ET.SubElement(
            root,
            "mxCell",
            id=f"ctx-edge-{i}",
            value=ent.get("interaction", ""),
            style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;fontSize=10;",
            parent="1",
            source=ent_id,
            target=center_id,
            edge="1",
        )
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})

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

    print(f"  Components: {len(components)} | "
          f"Connections: {len(connections)} | "
          f"Data flows:  {len(dataflows)} | "
          f"Datasets: {len(datasets)} | "
          f"Dataset relationships: {len(dataset_relationships)} | "
          f"Context entities: {len(context_entities)}")

    if not components and not dataflows and not datasets:
        print(
            "\nNo data found in source tables. Falling back to previously generated local draw.io files if available."
        )

    updated_html = target_body_html

    # ── Solution Architecture diagram (with AWS icons if available)
    if components:
        print("\nGenerating Solution Architecture diagram...")
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
            "solution-architecture.drawio", "Solution Architecture", target_page_id,
        )
    else:
        arch_xml = load_local_drawio("solution-architecture.drawio")
        if arch_xml:
            print("\nReusing existing local Solution Architecture diagram...")
            upload_attachment(session, base_url, target_page_id,
                              "solution-architecture.drawio", arch_xml)
            updated_html = replace_placeholder(
                updated_html, "solution-architecture",
                "solution-architecture.drawio", "Solution Architecture", target_page_id,
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

    # ── Logical View (reuses architecture component model)
    if components:
        print("\nGenerating Logical View Diagram...")
        logical_xml = generate_architecture_drawio(components, connections)
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
        print("  Showing: User → WebApp → API → Cognito → Service → Database")
        print("  Steps: OAuth2 token exchange, validation, and secure data access")
        auth_xml = generate_authentication_flow_diagram()
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
        net_xml = generate_network_segregation_diagram()
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
