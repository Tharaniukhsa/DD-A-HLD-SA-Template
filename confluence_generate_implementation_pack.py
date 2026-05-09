import json
import os
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup
import certifi
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from requests_negotiate_sspi import HttpNegotiateAuth

load_dotenv()


def get_auth():
    user_email = (os.getenv("CONFLUENCE_USER_EMAIL") or "").strip()
    api_token = (os.getenv("CONFLUENCE_API_TOKEN") or "").strip()
    if user_email and api_token:
        return HTTPBasicAuth(user_email, api_token)
    return HttpNegotiateAuth()


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


def find_page_by_title(session: requests.Session, base_url: str, space_key: str, title: str) -> dict:
    resp = session.get(
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


def _table_rows(table) -> list[list[str]]:
    rows = []
    for i, tr in enumerate(table.find_all("tr")):
        if i == 0:
            continue
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if any(cells):
            rows.append(cells)
    return rows


def _find_table_after_heading(soup, heading_text: str):
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
    output = []
    for row in _table_rows(table):
        name = row[1] if len(row) > 1 else ""
        if not name:
            continue
        output.append(
            {
                "name": name,
                "layer": row[2] if len(row) > 2 else "",
                "technology": row[3] if len(row) > 3 else "",
                "description": row[4] if len(row) > 4 else "",
            }
        )
    return output


def parse_dataset_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_after_heading(soup, "Dataset Inventory")
    if not table:
        return []
    output = []
    for row in _table_rows(table):
        name = row[1] if len(row) > 1 else ""
        if not name:
            continue
        output.append(
            {
                "id": row[0] if len(row) > 0 else "",
                "name": name,
                "type": row[2] if len(row) > 2 else "",
                "primary_key": row[3] if len(row) > 3 else "",
                "sensitivity": row[4] if len(row) > 4 else "",
                "retention": row[5] if len(row) > 5 else "",
            }
        )
    return output


def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build_aws_tf(components: list[dict], datasets: list[dict]) -> str:
    dataset_bucket = "ukhsa-data-lake"
    has_data_lake = any("lake" in d.get("type", "").lower() for d in datasets)
    storage_note = "# Generated from Confluence architecture page"

    return f'''terraform {{
  required_version = ">= 1.6.0"
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "eu-west-2"
}}

{storage_note}
resource "aws_s3_bucket" "data_lake" {{
  bucket = "{dataset_bucket}"
}}

resource "aws_s3_bucket_versioning" "data_lake" {{
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

resource "aws_kms_key" "data_key" {{
  description = "KMS key for data solution"
}}

# Components discovered: {len(components)}
# Datasets discovered: {len(datasets)}
# Data lake pattern present: {str(has_data_lake).lower()}
'''


def build_azure_tf(components: list[dict], datasets: list[dict]) -> str:
    return f'''terraform {{
  required_version = ">= 1.6.0"
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
}}

resource "azurerm_resource_group" "data_rg" {{
  name     = "rg-data-solution"
  location = "UK South"
}}

resource "azurerm_storage_account" "data_lake" {{
  name                     = "ukhsadatalake001"
  resource_group_name      = azurerm_resource_group.data_rg.name
  location                 = azurerm_resource_group.data_rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}}

# Components discovered: {len(components)}
# Datasets discovered: {len(datasets)}
'''


def main() -> None:
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "Solution Architecture")

    session = requests.Session()
    session.auth = get_auth()

    print(f"Finding page '{title}'...")
    page = find_page_by_title(session, base_url, space_key, title)
    html = page["body"]["storage"]["value"]

    components = parse_components(html)
    datasets = parse_dataset_inventory(html)

    root = os.path.dirname(__file__)
    aws_tf = os.path.join(root, "output", "terraform", "aws", "main.tf")
    azure_tf = os.path.join(root, "output", "terraform", "azure", "main.tf")
    summary_path = os.path.join(root, "output", "implementation", "summary.json")

    write_text(aws_tf, build_aws_tf(components, datasets))
    write_text(azure_tf, build_azure_tf(components, datasets))

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_page": {
            "id": page["id"],
            "title": page["title"],
        },
        "counts": {
            "components": len(components),
            "datasets": len(datasets),
        },
        "outputs": {
            "aws_terraform": os.path.relpath(aws_tf, root),
            "azure_terraform": os.path.relpath(azure_tf, root),
        },
        "note": "This is a starter Terraform scaffold generated from architecture inputs and must be reviewed by implementation engineers.",
    }

    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("Generated implementation pack:")
    print(f"  - {os.path.relpath(aws_tf, root)}")
    print(f"  - {os.path.relpath(azure_tf, root)}")
    print(f"  - {os.path.relpath(summary_path, root)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
