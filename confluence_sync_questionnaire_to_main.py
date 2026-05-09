import json
import os
import re
import subprocess
import sys

from bs4 import BeautifulSoup
import certifi
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from requests_negotiate_sspi import HttpNegotiateAuth

load_dotenv()


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


def _make_request(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    api_token = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    verify = kwargs.pop("verify", get_tls_verify())

    if api_token:
        bearer_session = requests.Session()
        bearer_session.headers.update(session.headers)
        bearer_session.headers.update({"Authorization": f"Bearer {api_token}"})
        try:
            resp = bearer_session.request(method, url, verify=verify, **kwargs)
            if resp.status_code != 403:
                return resp
        except Exception:
            pass

    if user_email and api_token:
        basic_session = requests.Session()
        basic_session.headers.update(session.headers)
        basic_session.auth = HTTPBasicAuth(user_email, api_token)
        return basic_session.request(method, url, verify=verify, **kwargs)

    sso_session = requests.Session()
    sso_session.headers.update(session.headers)
    sso_session.auth = HttpNegotiateAuth()
    return sso_session.request(method, url, verify=verify, **kwargs)


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


def update_page_body(session: requests.Session, base_url: str, page: dict, body_html: str) -> dict:
    payload = {
        "version": {"number": page["version"]["number"] + 1},
        "title": page["title"],
        "type": "page",
        "body": {"storage": {"value": body_html, "representation": "storage"}},
    }
    resp = _make_request(
        session,
        "PUT",
        f"{base_url}/rest/api/content/{page['id']}",
        data=json.dumps(payload),
        headers=_json_headers(),
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to update page: {resp.status_code} {resp.text}")
    return resp.json()


def normalize_field_name(text: str) -> str:
    cleaned = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True).lower()
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def table_after_heading(soup: BeautifulSoup, heading_text: str):
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if heading_text.lower() in tag.get_text(" ", strip=True).lower():
            nxt = tag.find_next_sibling()
            while nxt and nxt.name in {"p", "ul", "ol", "hr", "ac:structured-macro"}:
                nxt = nxt.find_next_sibling()
            if nxt and nxt.name == "table":
                return nxt
    return None


def extract_key_value_table(table_tag) -> dict:
    data = {}
    if not table_tag:
        return data
    rows = table_tag.find_all("tr")
    for tr in rows[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        key = normalize_field_name(cells[0].decode_contents())
        value = cells[1].get_text(" ", strip=True)
        if key and value:
            data[key] = value
    return data


def update_main_field_table(table_tag, updates: dict) -> int:
    changed = 0
    if not table_tag:
        return changed
    for tr in table_tag.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        key = normalize_field_name(cells[0].decode_contents())
        if key in updates and updates[key].strip():
            cells[1].string = updates[key].strip()
            changed += 1
    return changed


def extract_dataflows(questionnaire_soup: BeautifulSoup) -> list[dict]:
    q_table = table_after_heading(questionnaire_soup, "9. Data Flows Summary")
    rows_out = []
    if not q_table:
        return rows_out

    rows = q_table.find_all("tr")
    for tr in rows[1:]:
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 6:
            continue
        flow_id, src, dst, data_type, freq, vol = cells[:6]
        if not any([flow_id, src, dst, data_type, freq, vol]):
            continue
        if all(x.startswith("e.g.") or x == "" for x in [src, dst, data_type]):
            continue
        data_desc = data_type
        if vol:
            data_desc = f"{data_type} (Volume: {vol})" if data_type else f"Volume: {vol}"
        rows_out.append(
            {
                "flow_id": flow_id,
                "source": src,
                "destination": dst,
                "data_description": data_desc,
                "frequency": freq,
            }
        )
    return rows_out


def write_dataflows_to_main(main_soup: BeautifulSoup, flows: list[dict]) -> int:
    m_table = table_after_heading(main_soup, "12. Data Flow Entries")
    if not m_table:
        return 0

    body = m_table.find("tbody")
    if not body:
        return 0

    existing_rows = body.find_all("tr")
    for tr in existing_rows:
        tr.decompose()

    for i, flow in enumerate(flows, start=1):
        tr = main_soup.new_tag("tr")
        values = [
            flow.get("flow_id") or f"F{i}",
            flow.get("source", ""),
            flow.get("destination", ""),
            flow.get("data_description", ""),
            "",
            "",
            flow.get("frequency", ""),
            "",
        ]
        for value in values:
            td = main_soup.new_tag("td")
            td.string = value
            tr.append(td)
        body.append(tr)

    return len(flows)


def sync_questionnaire_to_main(main_html: str, questionnaire_html: str) -> tuple[str, dict]:
    main_soup = BeautifulSoup(main_html, "html.parser")
    q_soup = BeautifulSoup(questionnaire_html, "html.parser")

    q_business_table = table_after_heading(q_soup, "1. Business Context")
    business_data = extract_key_value_table(q_business_table)

    overview_updates = {
        "solution name": business_data.get("solution name", ""),
        "leanix business capability id": business_data.get("leanix business capability id", ""),
        "primary stakeholders": business_data.get("primary stakeholders", ""),
        "data sensitivity classification": business_data.get("data sensitivity level", ""),
    }

    intro_updates = {
        "business capability supported": business_data.get("business capability name", ""),
        "expected business outcomes": business_data.get("business outcome / goal", ""),
        "solution description": business_data.get("data domain", ""),
    }

    overview_table = table_after_heading(main_soup, "1. Solution Overview")
    intro_table = table_after_heading(main_soup, "2. Introduction")

    overview_count = update_main_field_table(overview_table, overview_updates)
    intro_count = update_main_field_table(intro_table, intro_updates)

    flows = extract_dataflows(q_soup)
    flows_count = write_dataflows_to_main(main_soup, flows)

    summary = {
        "overview_fields_updated": overview_count,
        "introduction_fields_updated": intro_count,
        "dataflows_updated": flows_count,
    }

    return str(main_soup), summary


def run_diagram_generation(workspace: str, main_page_id: str | None = None) -> None:
    script = os.path.join(workspace, "confluence_update_diagrams.py")
    cmd = [sys.executable, script]
    env = os.environ.copy()
    if main_page_id:
        env["CONFLUENCE_ARCHITECTURE_PAGE_ID"] = str(main_page_id)
    subprocess.run(cmd, check=True, cwd=workspace, env=env)


def run_lld_sync_and_diagrams(workspace: str) -> None:
    script = os.path.join(workspace, "confluence_update_lld_diagrams.py")
    cmd = [sys.executable, script]
    subprocess.run(cmd, check=True, cwd=workspace)


def main() -> None:
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    main_page_title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "Solution Architecture")
    main_page_id = (os.getenv("CONFLUENCE_MAIN_PAGE_ID") or "520783944").strip()
    questionnaire_title = os.getenv("CONFLUENCE_QUESTIONNAIRE_PAGE_TITLE", "Data Solution Architecture Questionnaire")
    auto_generate = os.getenv("CONFLUENCE_AUTO_GENERATE_DIAGRAMS", "true").strip().lower() in {"1", "true", "yes"}
    auto_sync_lld = os.getenv("CONFLUENCE_AUTO_SYNC_LLD", "true").strip().lower() in {"1", "true", "yes"}

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    print(f"Finding main page '{main_page_title}'...")
    try:
        main_page = find_page_by_title(session, base_url, space_key, main_page_title)
    except ValueError:
        main_page = get_page_by_id(session, base_url, main_page_id)

    print(f"Finding questionnaire page '{questionnaire_title}'...")
    questionnaire_page = find_page_by_title(session, base_url, space_key, questionnaire_title)

    updated_html, sync_summary = sync_questionnaire_to_main(
        main_page["body"]["storage"]["value"],
        questionnaire_page["body"]["storage"]["value"],
    )

    print("Sync summary:")
    print(f"  Overview fields updated: {sync_summary['overview_fields_updated']}")
    print(f"  Introduction fields updated: {sync_summary['introduction_fields_updated']}")
    print(f"  Data flow rows updated: {sync_summary['dataflows_updated']}")

    update_page_body(session, base_url, main_page, updated_html)
    print("Main page updated from questionnaire.")

    if auto_generate:
        workspace = os.path.dirname(__file__)
        print("Auto-generating diagrams...")
        run_diagram_generation(workspace, str(main_page.get("id", main_page_id)))
        print("Diagrams regenerated.")

        if auto_sync_lld:
            print("Auto-syncing HLD to LLD and regenerating LLD detailed diagrams...")
            run_lld_sync_and_diagrams(workspace)
            print("LLD synced and detailed diagrams regenerated.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
