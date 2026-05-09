"""
Revert Solution Architecture page to clean state (remove sample data).
This restores the page to its original template structure without sample tables.
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


def build_clean_page():
    """Build the clean original page without sample data."""
    html_body = """<h1>Solution Architecture</h1>
<p><strong>Project:</strong> Solution Architecture Template</p>
<p><strong>Status:</strong> Template Ready</p>
<p><strong>Description:</strong> This page provides a template for documenting solution architectures using architecture components, connections, and data flows.</p>
<hr/>

<h2>Instructions</h2>
<p>Fill in the following tables to define your solution architecture:</p>
<ol>
<li>Add components to the <strong>Architecture Components</strong> table</li>
<li>Define connections between components in the <strong>Architecture Connections</strong> table</li>
<li>Describe data flows in the <strong>Data Flow Entries</strong> table</li>
<li>Run <code>confluence_update_diagrams.py</code> to auto-generate diagrams</li>
</ol>

<hr/>

<h2>Architecture Components</h2>
<p><em>Define all system components below. Columns: No, Name, Layer, Technology, Description</em></p>
<table>
<tbody>
<tr>
<th>No</th>
<th>Name</th>
<th>Layer</th>
<th>Technology</th>
<th>Description</th>
</tr>
</tbody>
</table>

<hr/>

<h2>Architecture Connections</h2>
<p><em>Define connections between components. Columns: From, To, Label</em></p>
<table>
<tbody>
<tr>
<th>From</th>
<th>To</th>
<th>Label</th>
</tr>
</tbody>
</table>

<hr/>

<h2>Data Flow Entries</h2>
<p><em>Define data flows and interactions. Columns: ID, Source, Destination, Data, Protocol</em></p>
<table>
<tbody>
<tr>
<th>ID</th>
<th>Source</th>
<th>Destination</th>
<th>Data</th>
<th>Protocol</th>
</tr>
</tbody>
</table>

<hr/>

<h2>Dataset Inventory</h2>
<p><em>Define datasets used in the solution. Columns: ID, Name, Type, Primary Key, Sensitivity, Retention</em></p>
<table>
<tbody>
<tr>
<th>ID</th>
<th>Name</th>
<th>Type</th>
<th>Primary Key</th>
<th>Sensitivity</th>
<th>Retention</th>
</tr>
</tbody>
</table>

<hr/>

<h2>Dataset Relationships</h2>
<p><em>Define relationships between datasets. Columns: Source, Target, Relation, Mapping</em></p>
<table>
<tbody>
<tr>
<th>Source</th>
<th>Target</th>
<th>Relation</th>
<th>Mapping</th>
</tr>
</tbody>
</table>

<hr/>

<h2>Context Entities</h2>
<p><em>Define external entities and stakeholders. Columns: Name, Type, Interaction</em></p>
<table>
<tbody>
<tr>
<th>Name</th>
<th>Type</th>
<th>Interaction</th>
</tr>
</tbody>
</table>

<hr/>

<h2>Generated Diagrams</h2>
<p><em>Diagrams will appear here after running confluence_update_diagrams.py</em></p>
<p>Supported diagrams:</p>
<ul>
<li>Solution Architecture Diagram</li>
<li>Data Flow Diagram</li>
<li>Dataset Relationship Diagram</li>
<li>Context View Diagram</li>
<li>Logical View Diagram</li>
</ul>
"""
    return html_body


def main():
    print("=" * 70)
    print("REVERT SOLUTION ARCHITECTURE PAGE TO CLEAN STATE")
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
        
        print("Building clean page template (removing sample data)...")
        html_body = build_clean_page()
        
        print("Updating Confluence page...")
        result = update_page_body(session, base_url, page_id, version, page_title, html_body)
        
        print("✓ Page reverted to clean state!")
        print()
        print("=" * 70)
        print("REVERT COMPLETE")
        print("=" * 70)
        print()
        print("The Solution Architecture page has been restored to its original")
        print("template state with empty tables. All sample data has been removed.")
        print()
        print(f"View page: {base_url}/spaces/{space_key}/pages/{page_id}/{page_title.replace(' ', '+')}")
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
