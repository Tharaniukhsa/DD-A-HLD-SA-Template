Enterprise Architecture Automation (Confluence + Diagram + Terraform)

Purpose
- This project automates UKHSA solution architecture documentation in Confluence.
- It creates/updates architecture pages, publishes approved data patterns, syncs questionnaire inputs, generates diagrams, and builds implementation starter outputs.

What This Codebase Does
1) Creates and updates Confluence architecture pages.
2) Publishes an approved data-patterns reference page in clean readable format.
3) Creates a questionnaire page for requirements and pattern selection.
4) Syncs questionnaire content into the main architecture page.
5) Generates draw.io architecture diagrams from Confluence table content.
6) Generates implementation artifacts (Terraform starter files + JSON summary).

Main Files
- confluence_enhance_main_page.py
  Creates/updates the main Solution Architecture page and approved patterns reference page.

- confluence_create_architecture_pages.py
  Creates architecture child pages (for structure such as LLD/ADR support content).

- confluence_create_questionnaire.py
  Creates questionnaire page used for requirements/pattern capture.

- confluence_sync_questionnaire_to_main.py
  Copies/syncs questionnaire content into the main architecture page.

- confluence_update_diagrams.py
  Reads architecture tables from Confluence and updates draw.io diagrams.

- confluence_generate_implementation_pack.py
  Produces implementation outputs:
  - output/terraform/aws/main.tf
  - output/terraform/azure/main.tf
  - output/implementation/summary.json

- UKHSA Cloud Strategy & Approved patterns.md
  Comprehensive consolidated reference combining UKHSA Cloud Strategy 2025 with approved data patterns.
  Includes: Cloud strategy vision/principles/operating model + 8 data pattern layers + ADRs + quick-pick cheatsheet.

Environment Setup
1) Create and activate virtual environment.
2) Install required packages (requests, python-dotenv, certifi, etc.).
3) Configure .env in project root.

Required .env Variables
- CONFLUENCE_BASE_URL=https://<your-tenant>.atlassian.net/wiki
- CONFLUENCE_SPACE_KEY=<space-key>
- CONFLUENCE_PARENT_PAGE_ID=<parent-page-id>
- CONFLUENCE_MAIN_PAGE_TITLE=Solution Architecture
- CONFLUENCE_USER_EMAIL=<email>
- CONFLUENCE_API_TOKEN=<token>

Optional .env Variables
- CONFLUENCE_PATTERNS_PAGE_TITLE=Approved Data Patterns Reference
- CONFLUENCE_CA_BUNDLE=<custom-ca-path>
- CONFLUENCE_SKIP_SSL_VERIFY=false

Recommended Execution Order
1) python confluence_enhance_main_page.py
2) python confluence_create_questionnaire.py
3) Fill or update questionnaire content in Confluence.
4) python confluence_sync_questionnaire_to_main.py
5) python confluence_update_diagrams.py
6) python confluence_generate_implementation_pack.py

Confluence Data Model Used by Diagram Generator
- Architecture Components
- Architecture Connections
- Data Flow Entries
- Dataset Inventory
- Dataset Relationships
- Context Entities

Output Folder
- output/
  Contains generated draw.io files and implementation outputs.

Notes
- Workshop scripts were removed from this workspace by request.
- If token-based auth fails with Bearer, scripts can fall back to Basic auth when email+token are present.
- TLS verification uses certifi by default.

Quick Run Example (Windows PowerShell)
- & ".\.venv\Scripts\python.exe" ".\confluence_enhance_main_page.py"
- & ".\.venv\Scripts\python.exe" ".\confluence_create_questionnaire.py"
- & ".\.venv\Scripts\python.exe" ".\confluence_sync_questionnaire_to_main.py"
- & ".\.venv\Scripts\python.exe" ".\confluence_update_diagrams.py"
- & ".\.venv\Scripts\python.exe" ".\confluence_generate_implementation_pack.py"

Troubleshooting
- 403 Unauthorized:
  Verify token validity, remove leading/trailing spaces in .env values, and confirm email/token pair.

- SSL issues:
  Set CONFLUENCE_CA_BUNDLE to your trusted CA path, or use default certifi certificate bundle.

- Empty diagrams:
  Ensure required Confluence tables exist and contain rows on the main architecture page.
