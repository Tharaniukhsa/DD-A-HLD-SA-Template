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

# ── Indicative monthly cost ranges (£) per pattern ────────────────────────────
# Tuple order: (storage, compute, networking, monitoring, security, managed_services)
_PATTERN_COSTS: dict[str, tuple[int, int, int, int, int, int]] = {
    "1A":     (0,   20,  10,  5,   0,   0),   # API Pull (Lambda / API Gateway)
    "1B":     (30,  30,  15,  5,   0,   0),   # Batch File Upload (S3 / Transfer Family)
    "1C":     (20,  50,  25,  10,  0,   20),  # DB Replication (DMS / SCT)
    "1D":     (20,  80,  35,  15,  0,   60),  # Streaming Ingestion (Kinesis / MSK)
    "2A":     (0,   70,  0,   10,  0,   30),  # Batch ETL (Glue)
    "2B":     (0,   120, 20,  20,  0,   40),  # Real-time Stream Processing (Flink / KDA)
    "2C":     (0,   250, 10,  20,  0,   0),   # Spark / ML Jobs (EMR / SageMaker)
    "2D":     (0,   25,  5,   5,   0,   10),  # Federated Query (Athena)
    "3A":     (50,  80,  0,   10,  0,   20),  # OLTP (RDS / Aurora)
    "3B":     (80,  150, 0,   15,  0,   40),  # Data Warehouse (Redshift)
    "3C":     (60,  20,  10,  5,   0,   0),   # Data Lake (S3)
    "3D":     (15,  30,  5,   10,  0,   20),  # Time-Series (Timestream)
    "3E":     (20,  20,  5,   5,   0,   15),  # Document Store (DynamoDB)
    "4A":     (0,   30,  5,   5,   0,   15),  # Event-Driven (SNS / SQS / EventBridge)
    "4B":     (0,   20,  5,   5,   0,   10),  # ETL Orchestration (Step Functions)
    "4C":     (30,  20,  20,  5,   0,   0),   # Data Replication & Sync
    "5A":     (0,   0,   0,   10,  0,   25),  # Data Catalogue (Glue Catalog / Purview)
    "5B":     (0,   15,  0,   5,   0,   0),   # Data Quality
    "5C":     (0,   10,  0,   5,   0,   15),  # Data Lineage
    "6A":     (0,   0,   0,   0,   15,  0),   # Access Control (IAM / Lake Formation)
    "6B":     (0,   0,   0,   0,   25,  0),   # Encryption & KMS
    "6C":     (0,   0,   15,  0,   20,  0),   # Network Security (WAF / GuardDuty)
    "6D":     (0,   15,  0,   0,   20,  0),   # Data Masking / Anonymisation
    "7A":     (15,  0,   0,   50,  0,   0),   # Centralised Logging (CloudWatch / S3)
    "7B":     (0,   0,   0,   25,  0,   0),   # Performance Monitoring & Alerting
    "7C":     (0,   0,   0,   10,  0,   0),   # Cost Tracking (Cost Explorer)
    "8A":     (40,  70,  10,  0,   0,   0),   # High Availability (Multi-AZ)
    "8B":     (80,  70,  45,  0,   0,   0),   # Disaster Recovery (Cross-Region)
    "8C":     (25,  0,   0,   0,   0,   10),  # Backup & Point-in-Time Recovery
    "SBD-01": (0,   0,   0,   0,   10,  0),   # Threat Modelling
    "SBD-02": (0,   0,   0,   0,   10,  20),  # Secure SDLC
    "SBD-03": (0,   0,   0,   0,   5,   0),   # Privacy by Design
    "SBD-04": (5,   0,   0,   15,  10,  0),   # Security Telemetry
}

_INF_TSA_COSTS: dict[str, tuple[int, int, int, int, int, int]] = {
    "UKHSA-INF-01": (0,  50, 30, 10, 0,  50),  # Landing Zone (Control Tower)
    "UKHSA-INF-02": (0,  0,  80, 5,  0,  0),   # Connectivity (Transit Gateway)
    "UKHSA-INF-03": (0,  20, 20, 5,  20, 0),   # Zero Trust Access
    "UKHSA-INF-04": (0,  0,  5,  0,  0,  10),  # DNS (Route53 / Resolver)
    "UKHSA-INF-05": (0,  0,  0,  5,  20, 30),  # Identity (IAM Identity Center / SSO)
    "UKHSA-INF-06": (0,  100,10, 15, 0,  0),   # Platform (EKS / ECS)
    # UKHSA-INF-07: OpenShift + cross-environment connection costs
    # Tuple order: (storage, compute, networking, monitoring, security, managed_services)
    # Networking column covers all cross-environment link charges.
    # On-Prem DC ↔ AWS:   Direct Connect port hours (~£140/mo 1Gbps) + data transfer (~£0.02/GB out)
    # On-Prem DC ↔ Azure: ExpressRoute circuit fee (~£200/mo 1Gbps) + data transfer (~£0.02/GB out)
    # On-Prem ↔ OCP:      Internal LAN — no cloud cost (£0)
    # OCP ↔ AWS:          PrivateLink endpoint (~£7/mo per AZ) + per-GB (~£0.01/GB)
    # OCP ↔ Azure:        Shared ExpressRoute private peering — no additional circuit fee
    # AWS ↔ Azure:        Inter-cloud egress — highest risk (~£0.07–0.08/GB from AWS to Azure)
    "UKHSA-INF-07": (0,  60, 195, 10, 15, 20),  # OpenShift (OCP) + cross-env connectivity
    "TSA-NET-01":   (0,  0,  30, 0,  0,  0),   # Network Segmentation
    "TSA-NET-02":   (0,  0,  20, 0,  0,  0),   # Network Isolation
    "TSA-IDN-01":   (0,  0,  0,  0,  20, 20),  # JIT / PIM Privileged Access
    "TSA-IDN-02":   (0,  0,  0,  0,  15, 10),  # Identity Lifecycle (JML)
    # Cross-environment connection cost keys — used when a project explicitly
    # selects a connectivity type rather than an infrastructure pattern.
    "XENV-ONPREM-AWS":   (0, 0, 160, 5, 0, 0),  # Direct Connect port + data transfer
    "XENV-ONPREM-AZURE": (0, 0, 220, 5, 0, 0),  # ExpressRoute circuit + data transfer
    "XENV-ONPREM-OCP":   (0, 0,   0, 0, 0, 0),  # Internal LAN — £0 cloud cost
    "XENV-OCP-AWS":      (0, 0,  20, 5, 5, 0),  # PrivateLink endpoint hours + per-GB
    "XENV-OCP-AZURE":    (0, 0,   5, 5, 5, 0),  # Shared ExpressRoute — marginal cost
    "XENV-AWS-AZURE":    (0, 0, 350, 5, 0, 0),  # Inter-cloud egress (highest cost risk)
}

# Cost area names — order matches tuple positions above
_COST_AREAS = [
    "Storage",
    "Compute / Processing",
    "Data Transfer / Networking",
    "Monitoring / Logging",
    "Security / IAM",
    "Managed Services / Licensing",
]


def _score_complexity(selected_patterns: list[str]) -> tuple[str, str, list[str]]:
    """
    Score workload complexity from selected patterns and return a recommended option.
    Returns: (option_letter, tier_label, rationale_bullets)
    Option A = Simple/Baseline, B = Standard/Cloud-Native, C = Advanced/Enterprise.
    """
    patterns = set(p.upper() for p in selected_patterns)
    has_streaming = bool({"1D", "2B"} & patterns)
    has_ml        = "2C" in patterns
    has_full_gov  = len({"5A", "5B", "5C"} & patterns) >= 2
    has_masking   = "6D" in patterns
    has_dr        = "8B" in patterns
    has_ha        = "8A" in patterns
    has_dw_lake   = bool({"3B", "3C"} & patterns)

    # Count data-layer patterns (1A–8C format)
    data_pats = [p for p in patterns if re.match(r"^[1-8][A-D]$", p)]
    n = len(data_pats)

    score = n
    if has_streaming: score += 4
    if has_ml:        score += 4
    if has_full_gov:  score += 3
    if has_masking:   score += 2
    if has_dr:        score += 3
    if has_ha:        score += 2
    if has_dw_lake:   score += 2

    if score < 10:
        option, label = "A", "Simple / Baseline"
        bullets: list[str] = [
            f"Low complexity: {n} data-layer pattern(s) selected.",
            "No real-time streaming or advanced ML detected.",
            "Standard batch or API workload — minimal managed services, lower operational overhead.",
            "Lowest estimated build and run cost tier.",
        ]
    elif score < 20:
        option, label = "B", "Standard / Cloud-Native"
        bullets = [
            f"Moderate complexity: {n} data-layer pattern(s) selected.",
            "Balanced capability and cost — standard UKHSA cloud-native approach.",
        ]
        if has_streaming:
            bullets.append("Streaming selected — Kinesis or MSK required; monitor ongoing cost.")
        if has_ha:
            bullets.append("High Availability (multi-AZ) selected — resilient deployment recommended.")
        bullets.append("Best fit for most UKHSA operational and analytical workloads.")
    else:
        option, label = "C", "Advanced / Enterprise"
        bullets = [
            f"High complexity: {n} data-layer pattern(s) selected — complex workload.",
        ]
        if has_streaming and has_ml:
            bullets.append("Real-time streaming + ML/Spark — advanced data pipeline required.")
        if has_full_gov:
            bullets.append("Full governance suite (catalogue, quality, lineage) selected.")
        if has_dr:
            bullets.append("Cross-region Disaster Recovery selected — highest resilience and cost tier.")
        if has_masking:
            bullets.append("Data masking / anonymisation required — additional security controls needed.")
        bullets.append("Enterprise-scale workload — plan for higher build effort and operational investment.")

    return option, label, bullets


def _estimate_costs(selected_patterns: list[str]) -> dict[str, tuple[int, int, int]]:
    """
    Estimate indicative monthly costs (£) per area for Options A, B, C.
    Option B = all selected patterns; A = minimal subset (no HA/DR/streaming/ML, scaled down);
    C = all selected + HA+DR if not already selected, plus 20% enterprise overhead.
    Returns: {area_name: (optA_£, optB_£, optC_£)}
    """
    patterns = set(p.upper() for p in selected_patterns)

    # Sum costs for Option B (all selected patterns)
    totals = [0] * 6
    for pid in patterns:
        costs = _PATTERN_COSTS.get(pid) or _INF_TSA_COSTS.get(pid)
        if costs:
            for i in range(6):
                totals[i] += costs[i]

    # Option A: remove HA, DR, ML, streaming costs then scale down to 65%
    opt_a = list(totals)
    for pid in ("8A", "8B", "2C", "2B", "1D"):
        if pid in patterns:
            c = _PATTERN_COSTS.get(pid, (0,) * 6)
            for i in range(6):
                opt_a[i] -= c[i]
    opt_a = [max(int(v * 0.65), 0) for v in opt_a]

    # Option C: add HA + DR if not already selected, then +20% enterprise overhead
    opt_c = list(totals)
    for pid in ("8A", "8B"):
        if pid not in patterns:
            c = _PATTERN_COSTS.get(pid, (0,) * 6)
            for i in range(6):
                opt_c[i] += c[i]
    opt_c = [int(v * 1.20) for v in opt_c]

    return {area: (opt_a[i], totals[i], opt_c[i]) for i, area in enumerate(_COST_AREAS)}


def insert_hld_recommendation(
    main_soup: BeautifulSoup,
    option: str,
    label: str,
    bullets: list[str],
) -> bool:
    """
    Insert an info callout with the auto-recommendation just before the
    Section 7 option comparison table, replacing any previous recommendation.
    Returns True if the insertion point was found and the panel was inserted.
    """
    bullet_items = "".join(f"<li>{b}</li>" for b in bullets)
    rec_html = (
        '<ac:structured-macro ac:name="info" ac:schema-version="1">'
        f'<ac:parameter ac:name="title">&#128161; Auto-Recommendation: Option {option} \u2013 {label}</ac:parameter>'
        "<ac:rich-text-body>"
        f"<p><strong>Based on the patterns selected in the questionnaire, "
        f"<u>Option {option} ({label})</u> is the recommended starting point.</strong></p>"
        f"<ul>{bullet_items}</ul>"
        "<p><em>Review the option table below, adjust to your project context, "
        "and record your final decision in the Decision Status column.</em></p>"
        "</ac:rich-text-body>"
        "</ac:structured-macro>"
    )

    # Remove any previous auto-recommendation macro to avoid duplicates
    for macro in main_soup.find_all("ac:structured-macro", attrs={"ac:name": "info"}):
        title_param = macro.find("ac:parameter", attrs={"ac:name": "title"})
        if title_param and "Auto-Recommendation" in (title_param.get_text() or ""):
            macro.decompose()

    # Insert before the first table after the Section 7 heading
    for heading in main_soup.find_all(["h2"]):
        if re.search(r"7\.\s*Architecture Decision", heading.get_text(), re.IGNORECASE):
            nxt = heading.find_next_sibling()
            while nxt and nxt.name not in {"table"}:
                nxt = nxt.find_next_sibling()
            if nxt:
                rec_soup = BeautifulSoup(rec_html, "html.parser")
                nxt.insert_before(rec_soup)
                return True
    return False


def fill_cost_comparison(
    main_soup: BeautifulSoup,
    costs: dict[str, tuple[int, int, int]],
    recommended_option: str,
) -> int:
    """
    Fill the Solution Option Cost Comparison table with indicative costs.
    Also marks the recommended option in the Option-Level Summary table.
    Returns count of rows updated.
    """
    table = table_after_heading(main_soup, "Solution Option Cost Comparison")
    if not table:
        return 0

    filled = 0
    for tr in table.find_all("tr")[1:]:  # skip header
        cells = tr.find_all(["td", "th"])
        if len(cells) < 4:
            continue
        row_label = cells[0].get_text(" ", strip=True).lower()

        if "total" in row_label:
            total_a = sum(v[0] for v in costs.values())
            total_b = sum(v[1] for v in costs.values())
            total_c = sum(v[2] for v in costs.values())
            for idx, val in enumerate([total_a, total_b, total_c], 1):
                if idx < len(cells):
                    strong = cells[idx].find("strong")
                    target = strong if strong else cells[idx]
                    target.string = f"\u00a3{val:,}"
            filled += 1
            continue

        for area, (opt_a, opt_b, opt_c) in costs.items():
            area_key = area.split(" /")[0].split(" ")[0].lower()
            if area_key in row_label:
                for idx, val in enumerate([opt_a, opt_b, opt_c], 1):
                    if idx < len(cells):
                        cells[idx].string = f"\u00a3{val:,}" if val > 0 else "< \u00a310"
                filled += 1
                break

    # Fill Option-Level Summary (16a / recommended Preferred? column)
    for heading in main_soup.find_all(["h3"]):
        heading_text = heading.get_text(" ", strip=True).lower()
        if "option-level" in heading_text or "comparison summary" in heading_text:
            nxt = heading.find_next_sibling()
            while nxt and nxt.name != "table":
                nxt = nxt.find_next_sibling()
            if nxt:
                for tr in nxt.find_all("tr")[1:]:
                    cells = tr.find_all(["td", "th"])
                    if len(cells) >= 5:
                        opt_label = cells[0].get_text(" ", strip=True)
                        if recommended_option.upper() in opt_label.upper():
                            cells[4].string = "Yes \u2013 Recommended"
                        elif not cells[4].get_text(strip=True):
                            cells[4].string = "No"
            break

    return filled


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


# ── Pattern ID extraction map: text in parentheses → canonical ID ─────────────
_PATTERN_ID_RE = re.compile(r"\((?:Pattern\s+)?([A-Za-z0-9][A-Za-z0-9\-]+)\)", re.IGNORECASE)
_SELECTED_POSITIVE = re.compile(r"^(?:yes|\u2611|\u2713|\u2714|x|selected)", re.IGNORECASE)


def _is_selected(cell_text: str) -> bool:
    """Return True if the 'Selected?' cell has been positively filled by the user."""
    t = cell_text.strip()
    # Unselected placeholder contains ☐ (U+2610 BALLOT BOX)
    if t.startswith("\u2610"):
        return False
    return bool(_SELECTED_POSITIVE.match(t))


def extract_selected_patterns(q_soup: BeautifulSoup) -> list[str]:
    """
    Scan every pattern-selection table in the questionnaire (Sections 2–11).
    A row is selected when the 3rd column (index 2) has been positively filled.
    Returns a deduped list of canonical pattern IDs e.g. ['1A', '3C', 'UKHSA-INF-01'].
    """
    selected: list[str] = []
    seen: set[str] = set()

    for table in q_soup.find_all("table"):
        rows = table.find_all("tr")
        # Pattern selection tables have ≥ 3 columns; skip key-value (2-col) tables
        header_cells = rows[0].find_all(["th", "td"]) if rows else []
        if len(header_cells) < 3:
            continue
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            # 3rd column is the Selected? column
            selected_text = cells[2].get_text(" ", strip=True)
            if not _is_selected(selected_text):
                continue
            # Extract pattern ID from 1st column parenthetical
            first_cell_text = cells[0].get_text(" ", strip=True)
            m = _PATTERN_ID_RE.search(first_cell_text)
            if m:
                pid = m.group(1).upper()
                if pid not in seen:
                    selected.append(pid)
                    seen.add(pid)
    return selected


def extract_data_sources(q_soup: BeautifulSoup) -> list[dict]:
    """
    Read Section 2.2 Data Sources table → return as component dicts.
    Columns: No | Source Name | Ingestion Pattern | Data Type | Frequency | Expected Volume
    """
    table = table_after_heading(q_soup, "2.2 Data Sources")
    if not table:
        # fallback: try broader heading
        table = table_after_heading(q_soup, "Data Sources")
    sources: list[dict] = []
    if not table:
        return sources
    for tr in table.find_all("tr")[1:]:
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        name = cells[1] if len(cells) > 1 else ""
        pattern = cells[2] if len(cells) > 2 else ""
        data_type = cells[3] if len(cells) > 3 else ""
        if not name or name.lower().startswith("source name"):
            continue
        sources.append({
            "name": name,
            "layer": "internet",
            "technology": f"{data_type} via {pattern}".strip(" via"),
            "description": f"Ingestion: {pattern} | Data: {data_type}",
        })
    return sources


def extract_transform_components(q_soup: BeautifulSoup) -> list[dict]:
    """
    Read Section 3.2 Transformation Components table → return as component dicts.
    Columns: No | Component Name | Pattern | Input Data | Output Data | Business Logic
    """
    table = table_after_heading(q_soup, "3.2 Transformation Components")
    if not table:
        table = table_after_heading(q_soup, "Transformation Components")
    components: list[dict] = []
    if not table:
        return components
    for tr in table.find_all("tr")[1:]:
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        name = cells[1] if len(cells) > 1 else ""
        pattern = cells[2] if len(cells) > 2 else ""
        logic = cells[5] if len(cells) > 5 else ""
        if not name or name.lower().startswith("component"):
            continue
        components.append({
            "name": name,
            "layer": "Private",
            "technology": pattern,
            "description": logic,
        })
    return components


def write_components_to_main(main_soup: BeautifulSoup, new_components: list[dict]) -> int:
    """
    Merge new_components into the main SA page's Components table (Section 9 or 10).
    Deduplicates by component name. Only adds rows not already present.
    """
    table = table_after_heading(main_soup, "9. Architecture Components")
    if not table:
        table = table_after_heading(main_soup, "Components")
    if not table:
        return 0

    body = table.find("tbody") or table
    existing_names = set()
    for tr in body.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if cells:
            existing_names.add(cells[0].get_text(" ", strip=True).lower())

    added = 0
    for comp in new_components:
        if comp["name"].lower() in existing_names:
            continue
        tr = main_soup.new_tag("tr")
        for val in [
            comp.get("name", ""),
            comp.get("layer", ""),
            comp.get("technology", ""),
            comp.get("description", ""),
            "", "",
        ]:
            td = main_soup.new_tag("td")
            td.string = val
            tr.append(td)
        body.append(tr)
        existing_names.add(comp["name"].lower())
        added += 1
    return added


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


def sync_questionnaire_to_main(
    main_html: str,
    questionnaire_html: str,
) -> tuple[str, dict, list[str]]:
    """
    Merge questionnaire answers into the main SA page HTML.
    Returns (updated_html, summary_dict, selected_pattern_ids).
    """
    main_soup = BeautifulSoup(main_html, "html.parser")
    q_soup = BeautifulSoup(questionnaire_html, "html.parser")

    # ── Section 1: Business Context → Overview + Intro tables
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

    # ── Sections 2–11: Extract selected pattern IDs
    selected_patterns = extract_selected_patterns(q_soup)

    # ── Section 2.2: Data Sources → Components table
    data_sources = extract_data_sources(q_soup)
    transform_comps = extract_transform_components(q_soup)
    all_new_components = data_sources + transform_comps
    components_added = write_components_to_main(main_soup, all_new_components)

    # ── Section 9: Data Flows → Data Flow Entries table
    flows = extract_dataflows(q_soup)
    flows_count = write_dataflows_to_main(main_soup, flows)

    # ── Section 7: Auto-recommend best HLD option based on selected patterns
    option, label, bullets = _score_complexity(selected_patterns)
    rec_inserted = insert_hld_recommendation(main_soup, option, label, bullets)
    print(f"  HLD recommendation: Option {option} — {label} (inserted={rec_inserted})")

    # ── Section 16/17: Auto-fill Cost Comparison table from pattern cost estimates
    costs = _estimate_costs(selected_patterns)
    costs_filled = fill_cost_comparison(main_soup, costs, option)
    print(f"  Cost comparison: {costs_filled} row(s) filled (Option {option} recommended)")

    summary = {
        "overview_fields_updated": overview_count,
        "introduction_fields_updated": intro_count,
        "components_added": components_added,
        "dataflows_updated": flows_count,
        "patterns_selected": selected_patterns,
        "hld_recommendation": f"Option {option} \u2013 {label}",
        "cost_areas_filled": costs_filled,
    }

    return str(main_soup), summary, selected_patterns


def run_diagram_generation(
    workspace: str,
    main_page_id: str | None = None,
    ukhsa_pattern_ids: list[str] | None = None,
    edap_pattern_ids: list[str] | None = None,
) -> None:
    script = os.path.join(workspace, "confluence_update_diagrams.py")
    cmd = [sys.executable, script]
    env = os.environ.copy()
    if main_page_id:
        env["CONFLUENCE_ARCHITECTURE_PAGE_ID"] = str(main_page_id)
    if ukhsa_pattern_ids:
        env["UKHSA_PATTERN_IDS"] = ",".join(ukhsa_pattern_ids)
        print(f"  Passing UKHSA_PATTERN_IDS={env['UKHSA_PATTERN_IDS']}")
    if edap_pattern_ids:
        env["EDAP_PATTERN_IDS"] = ",".join(edap_pattern_ids)
        print(f"  Passing EDAP_PATTERN_IDS={env['EDAP_PATTERN_IDS']}")
    subprocess.run(cmd, check=True, cwd=workspace, env=env)


def run_lld_sync_and_diagrams(
    workspace: str,
    ukhsa_pattern_ids: list[str] | None = None,
    edap_pattern_ids: list[str] | None = None,
) -> None:
    script = os.path.join(workspace, "confluence_update_lld_diagrams.py")
    cmd = [sys.executable, script]
    env = os.environ.copy()
    if ukhsa_pattern_ids:
        env["UKHSA_PATTERN_IDS"] = ",".join(ukhsa_pattern_ids)
    if edap_pattern_ids:
        env["EDAP_PATTERN_IDS"] = ",".join(edap_pattern_ids)
    subprocess.run(cmd, check=True, cwd=workspace, env=env)


def main() -> None:
    base_url = os.getenv("CONFLUENCE_BASE_URL", "https://ukhsa.atlassian.net/wiki").rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "CDA")
    main_page_title = os.getenv("CONFLUENCE_MAIN_PAGE_TITLE", "High-level Design (HLD) Solution Architecture Template")
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

    updated_html, sync_summary, selected_patterns = sync_questionnaire_to_main(
        main_page["body"]["storage"]["value"],
        questionnaire_page["body"]["storage"]["value"],
    )

    print("Sync summary:")
    print(f"  Overview fields updated:      {sync_summary['overview_fields_updated']}")
    print(f"  Introduction fields updated:  {sync_summary['introduction_fields_updated']}")
    print(f"  Components added:             {sync_summary['components_added']}")
    print(f"  Data flow rows updated:       {sync_summary['dataflows_updated']}")
    if sync_summary['patterns_selected']:
        print(f"  Patterns selected:            {', '.join(sync_summary['patterns_selected'])}")
    else:
        print("  Patterns selected:            (none ticked — keyword detection will apply)")

    update_page_body(session, base_url, main_page, updated_html)
    print("Main page updated from questionnaire.")

    # Separate EDAP vs UKHSA pattern IDs for the respective env vars
    edap_ids = [p for p in selected_patterns if p.upper().startswith("EDAP")]
    ukhsa_ids = [p for p in selected_patterns if not p.upper().startswith("EDAP")]

    if auto_generate:
        workspace = os.path.dirname(__file__)
        print("Auto-generating diagrams...")
        run_diagram_generation(
            workspace,
            str(main_page.get("id", main_page_id)),
            ukhsa_pattern_ids=ukhsa_ids or None,
            edap_pattern_ids=edap_ids or None,
        )
        print("Diagrams regenerated.")

        if auto_sync_lld:
            print("Auto-syncing HLD to LLD and regenerating LLD detailed diagrams...")
            run_lld_sync_and_diagrams(
                workspace,
                ukhsa_pattern_ids=ukhsa_ids or None,
                edap_pattern_ids=edap_ids or None,
            )
            print("LLD synced and detailed diagrams regenerated.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
