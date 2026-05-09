"""
Create a separate "Architecture Diagrams" child page for all auto-generated diagrams.
Update the main Solution Architecture page Section 14 to reference this new page.
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
    if ca_bundle and os.path.exists(ca_bundle):
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

def get_page_by_id(session: requests.Session, base_url: str, page_id: str):
    resp = _make_request(
        session,
        "GET",
        f"{base_url}/rest/api/content/{page_id}",
        params={"expand": "body.storage,version"},
        headers=_accept_headers(),
        verify=get_tls_verify(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def create_child_page(session: requests.Session, base_url: str, parent_page_id: str, title: str, body_html: str):
    """Create a new page as a child of parent_page_id."""
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": "CDA"},
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
        raise RuntimeError(f"Failed to create page: {resp.status_code} {resp.text}")
    return resp.json()


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


def build_diagrams_page_content():
    """Build the Architecture Diagrams child page."""
    html = """<h1>Architecture Diagrams</h1>

<p><em>Auto-generated diagrams from the Solution Architecture design tables. All diagrams are editable in draw.io.</em></p>

<hr/>

<h2>How to Generate Diagrams</h2>
<ol>
<li>Complete the architecture tables in the main <strong>Solution Architecture</strong> page (Sections 10-13)</li>
<li>Run the diagram generation script:
<pre><code>./.venv/Scripts/python.exe ./confluence_update_diagrams.py</code></pre>
</li>
<li>All diagrams will be auto-generated and embedded below</li>
<li>Edit diagrams directly in Confluence using the draw.io editor</li>
<li>Download local copies from: <code>output/generated/*.drawio</code></li>
</ol>

<hr/>

<h2>1. Context View Diagram</h2>

<p><strong>Purpose:</strong> Shows the system boundary and all external entities (actors, systems, partners) that interact with the solution.</p>

<p><strong>Driven by:</strong> Section 9 – Context Entities table</p>

<p><strong>[[DIAGRAM:context-view]]</strong></p>

<div style="border: 1px dashed #ccc; padding: 10px; margin: 10px 0; background-color: #f9f9f9;">
<p><strong>Placeholder:</strong> Context diagram showing solution boundary and external interactions</p>
</div>

<hr/>

<h2>2. Logical View Diagram</h2>

<p><strong>Purpose:</strong> Shows services organized by responsibility and how they interact through APIs and messaging.</p>

<p><strong>Driven by:</strong> Sections 10-11 – Components and Connections tables</p>

<p><strong>[[DIAGRAM:logical-view]]</strong></p>

<div style="border: 1px dashed #ccc; padding: 10px; margin: 10px 0; background-color: #f9f9f9;">
<p><strong>Placeholder:</strong> Logical view showing service grouping and interactions</p>
</div>

<hr/>

<h2>3. Solution Architecture Diagram</h2>

<p><strong>Purpose:</strong> Layer-based architecture view showing components in Edge, Network, Platform, Application, and Data layers.</p>

<p><strong>Driven by:</strong> Sections 10-11 – Components and Connections tables</p>

<p><strong>[[DIAGRAM:solution-architecture]]</strong></p>

<div style="border: 1px dashed #ccc; padding: 10px; margin: 10px 0; background-color: #f9f9f9;">
<p><strong>Placeholder:</strong> Layered architecture diagram (Edge → Network → Platform → Application → Data)</p>
</div>

<hr/>

<h2>4. Data Flow Diagram (DFD)</h2>

<p><strong>Purpose:</strong> Shows all data movements between components and external entities. Includes data types, formats, protocols, and frequencies.</p>

<p><strong>Driven by:</strong> Section 12 – Data Flow Entries table</p>

<p><strong>[[DIAGRAM:data-flow]]</strong></p>

<div style="border: 1px dashed #ccc; padding: 10px; margin: 10px 0; background-color: #f9f9f9;">
<p><strong>Placeholder:</strong> Data flow diagram showing all data movements and transformations</p>
</div>

<hr/>

<h2>5. Dataset Relationship Diagram (ERD)</h2>

<p><strong>Purpose:</strong> Entity-Relationship Diagram showing datasets, their types, sensitivity levels, and relationships (1:1, 1:N, M:N).</p>

<p><strong>Driven by:</strong> Section 13 – Dataset Inventory and Relationships tables</p>

<p><strong>[[DIAGRAM:data-relationship]]</strong></p>

<div style="border: 1px dashed #ccc; padding: 10px; margin: 10px 0; background-color: #f9f9f9;">
<p><strong>Placeholder:</strong> Entity-relationship diagram showing dataset structure and cardinality</p>
</div>

<hr/>

<h2>Local Diagram Files</h2>

<p><strong>Location:</strong> <code>output/generated/</code></p>

<table>
<tbody>
<tr><th>Diagram</th><th>File Name</th><th>Format</th><th>Editable</th></tr>
<tr><td>Context View</td><td>context-view-diagram.drawio</td><td>draw.io XML</td><td>Yes (in Confluence or draw.io desktop)</td></tr>
<tr><td>Logical View</td><td>logical-view-diagram.drawio</td><td>draw.io XML</td><td>Yes</td></tr>
<tr><td>Solution Architecture</td><td>solution-architecture.drawio</td><td>draw.io XML</td><td>Yes</td></tr>
<tr><td>Data Flow Diagram</td><td>data-flow-diagram.drawio</td><td>draw.io XML</td><td>Yes</td></tr>
<tr><td>Dataset Relationship</td><td>data-relationship-diagram.drawio</td><td>draw.io XML</td><td>Yes</td></tr>
</tbody>
</table>

<hr/>

<h2>Using the Diagrams</h2>

<h3>In Confluence</h3>
<ol>
<li>Click on any embedded diagram to open the draw.io editor</li>
<li>Make changes directly</li>
<li>Click <strong>Save</strong> to update</li>
</ol>

<h3>Offline Editing</h3>
<ol>
<li>Download .drawio file from: <code>output/generated/</code></li>
<li>Open in <a href="https://app.diagrams.net/">diagrams.net</a> or draw.io desktop</li>
<li>Make changes</li>
<li>Export as: PNG, SVG, PDF, or native .drawio format</li>
</ol>

<h3>Re-generating Diagrams</h3>
<p>After updating the design tables (Sections 10-13), regenerate all diagrams:</p>
<pre><code>./.venv/Scripts/python.exe ./confluence_update_diagrams.py</code></pre>

<p><strong>Note:</strong> Regeneration will overwrite auto-generated diagrams but preserve your manual edits in draw.io if they were made within Confluence.</p>

<hr/>

<h2>Diagram Specifications</h2>

<h3>Color Legend</h3>
<table>
<tbody>
<tr><td style="background-color: #dae8fc;">&nbsp;</td><td><strong>Edge Layer</strong> – User-facing applications and CDN</td></tr>
<tr><td style="background-color: #d5e8d4;">&nbsp;</td><td><strong>Network Layer</strong> – Routing, security, load balancing</td></tr>
<tr><td style="background-color: #fff2cc;">&nbsp;</td><td><strong>Platform Layer</strong> – Cross-cutting services (IAM, encryption, logging)</td></tr>
<tr><td style="background-color: #f8cecc;">&nbsp;</td><td><strong>Application Layer</strong> – Business logic and services</td></tr>
<tr><td style="background-color: #e1d5e7;">&nbsp;</td><td><strong>Data Layer</strong> – Databases, data lakes, warehouses</td></tr>
</tbody>
</table>

<h3>Data Sensitivity Classification</h3>
<ul>
<li><strong>Personal Data:</strong> PII requiring special handling</li>
<li><strong>Official-Sensitive:</strong> Non-public government data</li>
<li><strong>Official:</strong> Public but not yet published</li>
</ul>

<hr/>

<h2>Exporting for Presentations</h2>

<ol>
<li>Open diagram in draw.io (Confluence or web)</li>
<li>Click <strong>File → Export As</strong></li>
<li>Choose format:
<ul>
<li><strong>PNG</strong> – Raster image for presentations</li>
<li><strong>SVG</strong> – Scalable for printing</li>
<li><strong>PDF</strong> – For document embedding</li>
</ul>
</li>
<li>Select resolution and click <strong>Export</strong></li>
</ol>

<hr/>

<h2>Related Pages</h2>
<ul>
<li><strong><ac:link><ri:page ri:content-title="Solution Architecture" ri:space-key="CDA"/><ac:plain-text-link-body>Solution Architecture – Requirements &amp; Design Pack</ac:plain-text-link-body></ac:link></strong></li>
</ul>

<hr/>

<p><em><strong>Last Generated:</strong> [Date]</em></p>
<p><em><strong>Generation Method:</strong> confluence_update_diagrams.py</em></p>
"""
    return html


def build_updated_main_page_section_14():
    """Build the updated Section 14 content for the main page (referencing the diagrams page)."""
    html = """<h2 ac:name="diagrams">14. Auto-Generated Diagrams</h2>

<p><em>All architectural diagrams are auto-generated from the tables above (Sections 10-13) and maintained on a separate page for clarity.</em></p>

<p><strong>To generate diagrams:</strong> Run <code>confluence_update_diagrams.py</code> after completing the architecture tables.</p>

<p><strong>All diagrams available on:</strong> <ac:link><ri:page ri:content-title="Architecture Diagrams" ri:space-key="CDA"/><ac:plain-text-link-body>Architecture Diagrams</ac:plain-text-link-body></ac:link></p>

<h3>Diagram Types Generated</h3>
<ul>
<li><strong>Context View</strong> – System boundary and external entities</li>
<li><strong>Logical View</strong> – Services by responsibility and interaction</li>
<li><strong>Solution Architecture</strong> – Layer-based component view (Edge, Network, Platform, Application, Data)</li>
<li><strong>Data Flow Diagram (DFD)</strong> – All data movements between components</li>
<li><strong>Dataset Relationship Diagram (ERD)</strong> – Datasets and their relationships</li>
</ul>

<h3>Files &amp; Exports</h3>
<table>
<tbody>
<tr><th>Diagram</th><th>Local File</th><th>Editable</th><th>Export Options</th></tr>
<tr><td>Context View</td><td>output/generated/context-view-diagram.drawio</td><td>Yes (draw.io)</td><td>PNG, SVG, PDF</td></tr>
<tr><td>Logical View</td><td>output/generated/logical-view-diagram.drawio</td><td>Yes (draw.io)</td><td>PNG, SVG, PDF</td></tr>
<tr><td>Solution Architecture</td><td>output/generated/solution-architecture.drawio</td><td>Yes (draw.io)</td><td>PNG, SVG, PDF</td></tr>
<tr><td>Data Flow Diagram</td><td>output/generated/data-flow-diagram.drawio</td><td>Yes (draw.io)</td><td>PNG, SVG, PDF</td></tr>
<tr><td>Dataset Relationship</td><td>output/generated/data-relationship-diagram.drawio</td><td>Yes (draw.io)</td><td>PNG, SVG, PDF</td></tr>
</tbody>
</table>"""
    return html


def main():
    print("=" * 80)
    print("CREATE SEPARATE ARCHITECTURE DIAGRAMS PAGE")
    print("=" * 80)
    print()
    
    base_url = "https://ukhsa.atlassian.net/wiki"
    space_key = "CDA"
    parent_page_title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "High-level Design (HLD) Solution Architecture Template")
    parent_page_id_fallback = (os.getenv("CONFLUENCE_MAIN_PAGE_ID") or "520783944").strip()
    diagrams_page_title = "Architecture Diagrams"
    
    try:
        session = requests.Session()
        session.headers.update(_accept_headers())

        # Step 1: Find parent page
        print("Step 1: Finding parent page...")
        try:
            parent_page = find_page_by_title(session, base_url, space_key, parent_page_title)
        except ValueError:
            parent_page = get_page_by_id(session, base_url, parent_page_id_fallback)
        parent_page_id = parent_page["id"]
        parent_page_title = parent_page["title"]
        print(f"  ✓ Found: {parent_page_title} (ID: {parent_page_id})")
        print()

        # Step 2: Create or find diagrams child page
        print("Step 2: Finding or creating Architecture Diagrams child page...")
        try:
            diagrams_page = find_page_by_title(session, base_url, space_key, diagrams_page_title)
            diagrams_page_id = diagrams_page["id"]
            diagrams_version = diagrams_page["version"]["number"]
            print(f"  ✓ Found existing page: {diagrams_page_title} (ID: {diagrams_page_id})")
            print("    Updating with latest content...")
            diagrams_html = build_diagrams_page_content()
            update_page_body(session, base_url, diagrams_page_id, diagrams_version, diagrams_page_title, diagrams_html)
            print(f"  ✓ Updated: {diagrams_page_title}")
        except ValueError:
            print(f"  ✓ Page not found, creating: {diagrams_page_title}")
            diagrams_html = build_diagrams_page_content()
            diagrams_result = create_child_page(session, base_url, parent_page_id, diagrams_page_title, diagrams_html)
            diagrams_page_id = diagrams_result["id"]
            print(f"  ✓ Created: {diagrams_page_title} (ID: {diagrams_page_id})")
        print()

        # Step 3: Update main page Section 14
        print("Step 3: Updating main page Section 14 to reference diagrams page...")

        # Get current main page content
        main_page = get_page_by_id(session, base_url, parent_page_id)
        main_page_version = main_page["version"]["number"]
        main_page_body = main_page["body"]["storage"]["value"]
        
        # Find and replace Section 14 - try multiple formats
        section_14_start = main_page_body.find('<h2>14. Auto-Generated Diagrams</h2>')
        if section_14_start == -1:
            section_14_start = main_page_body.find('<h2 ac:name="diagrams">14. Auto-Generated Diagrams</h2>')
        if section_14_start == -1:
            # Try finding just the heading
            section_14_start = main_page_body.find('14. Auto-Generated Diagrams')
            if section_14_start != -1:
                # Back up to find the opening <h2 tag
                section_14_start = main_page_body.rfind('<h2', 0, section_14_start)
        
        if section_14_start == -1:
            raise ValueError("Could not find Section 14 in main page. Checking page content...")
        
        # Find the end of Section 14 (start of next major section or end of content)
        section_14_end = main_page_body.find('<h2', section_14_start + 50)
        if section_14_end == -1:
            section_14_end = main_page_body.find('<hr/>', section_14_start + 200)
        
        new_section_14 = build_updated_main_page_section_14()
        updated_main_page_body = main_page_body[:section_14_start] + new_section_14 + main_page_body[section_14_end:]
        
        # Update main page
        update_page_body(session, base_url, parent_page_id, main_page_version, parent_page_title, updated_main_page_body)
        print("  ✓ Updated: Section 14 now references Architecture Diagrams page")
        print()
        
        print("=" * 80)
        print("✓ ARCHITECTURE DIAGRAMS PAGE CREATED SUCCESSFULLY")
        print("=" * 80)
        print()
        print("Changes Made:")
        print("  ✓ New child page created: 'Architecture Diagrams'")
        print("  ✓ Main page Section 14 updated with link to diagrams page")
        print("  ✓ Diagrams page includes:")
        print("    - Instructions for generating diagrams")
        print("    - Placeholders for all 5 diagram types")
        print("    - Color legend and data classification guide")
        print("    - Export and editing instructions")
        print()
        print("Next Steps:")
        print("  1. Complete architecture tables (Sections 10-13) in main page")
        print("  2. Run: confluence_update_diagrams.py")
        print("  3. Diagrams will auto-generate on Architecture Diagrams page")
        print()
        print("Page URLs:")
        print(f"  Main: {base_url}/spaces/{space_key}/pages/{parent_page_id}")
        print(f"  Diagrams: {base_url}/spaces/{space_key}/pages/{diagrams_page_id}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
