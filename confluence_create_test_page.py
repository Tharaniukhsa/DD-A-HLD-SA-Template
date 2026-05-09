import json
import os
import sys

import certifi
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from requests_negotiate_sspi import HttpNegotiateAuth

# Auto-load .env from the project root so no manual env-var setup is needed.
load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def get_tls_verify_setting() -> bool | str:
    ca_bundle = (os.getenv("CONFLUENCE_CA_BUNDLE") or "").strip()
    if ca_bundle:
        if not os.path.exists(ca_bundle):
            raise ValueError(f"CONFLUENCE_CA_BUNDLE path does not exist: {ca_bundle}")
        return ca_bundle

    skip_verify = os.getenv("CONFLUENCE_SKIP_SSL_VERIFY", "false").strip().lower()
    if skip_verify in {"1", "true", "yes"}:
        print("Warning: SSL verification is disabled. Use for temporary testing only.")
        return False

    return certifi.where()


def _make_request(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    """
    Make HTTP request with automatic auth fallback.
    Tries Bearer auth first, then falls back to Basic auth if 403 received.
    """
    api_token = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    verify = kwargs.pop("verify", get_tls_verify_setting())
    
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


def build_page_payload(space_key: str, title: str, body_html: str, parent_page_id: str | None) -> dict:
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {
            "storage": {
                "value": body_html,
                "representation": "storage",
            }
        },
    }

    if parent_page_id:
        payload["ancestors"] = [{"id": parent_page_id}]

    return payload


def create_test_page() -> None:
    # Defaults are set for the UKHSA Confluence Cloud location shared by the user.
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    title = os.getenv("CONFLUENCE_TEST_PAGE_TITLE", "Solution Architecture - Test")
    parent_page_id = os.getenv("CONFLUENCE_PARENT_PAGE_ID", "173314084")

    body_html = os.getenv(
        "CONFLUENCE_TEST_PAGE_BODY",
        "<h1>SSO Test Page</h1><p>This page was created from Python using Windows SSO.</p>",
    )

    payload = build_page_payload(space_key, title, body_html, parent_page_id)

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )

    response = _make_request(
        session, "POST",
        f"{base_url}/rest/api/content",
        data=json.dumps(payload),
        timeout=30,
        verify=get_tls_verify_setting(),
    )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            "Failed to create Confluence page. "
            f"Status: {response.status_code}. Response: {response.text}"
        )

    page = response.json()
    links = page.get("_links", {})
    page_url = f"{links.get('base', base_url)}{links.get('webui', '')}"
    print(f"Page created successfully: {page_url}")


if __name__ == "__main__":
    try:
        create_test_page()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)