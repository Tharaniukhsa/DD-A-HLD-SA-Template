UKHSA Enterprise Architecture Automation
========================================
Automates UKHSA Solution Architecture documentation in Confluence.
Reads section tables from the HLD page → generates draw.io diagrams →
writes Terraform starters → creates child pages per project.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW THE SCRIPTS CONNECT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  setup_project.py
    └─► Creates a NEW project page hierarchy in Confluence:
        HLD page (cloned from LENS template, data cleared)
          └─ Architecture Diagrams (child)
          └─ Low-Level Design (child)
          └─ ADR Log (child)
        Writes .env.<project-slug> for the new project.

  confluence_enhance_main_page.py
    └─► Updates the MASTER HLD template page (ID 520783944).
        Injects: Fast-Fill guidance, How-to-Use box, Pattern Selection
        tables, Context Entities, Architecture Components, Connections,
        Roadmaps/Use-case sections, Approved Patterns link.
        Also upserts the Architecture Patterns Reference child page.

  confluence_create_questionnaire.py
    └─► Creates the Data Solution Architecture Questionnaire page
        (pattern tick-box inputs that drive the main HLD tables).

  confluence_sync_questionnaire_to_main.py
    └─► Reads completed Questionnaire → writes Sections 8–14 of the
        HLD main page (Pattern Selection, Components, Connections, etc.)

  confluence_update_diagrams.py
    └─► Reads Sections 9–14 of HLD page → generates 7 draw.io diagrams:
          1. Solution Architecture (layered component cards + icons)
          2. Data Flow Diagram
          3. Dataset Relationship Diagram
          4. Context View Diagram
          5. Logical View Diagram
          6. Authentication Flow Diagram
          7. Network Segregation Diagram
        Uploads diagrams as attachments to Architecture Diagrams child page.
        Also generates aws_architecture_diagram_generator.py LLD diagrams.

  confluence_generate_implementation_pack.py
    └─► Reads Components + Dataset Inventory from HLD page →
        Writes: output/terraform/aws/main.tf
                output/terraform/azure/main.tf
                output/implementation/summary.json

  aws_architecture_diagram_generator.py
    └─► Low-level diagram helper imported by confluence_update_diagrams.py.
        Generates detailed LLD draw.io tabs for each architectural flow step.

  enhanced_diagram_generator.py
    └─► Additional diagram generator for advanced LLD output (tabs/swimlanes).

DATA FLOW SUMMARY
  Confluence HLD tables
      │
      ├─► confluence_update_diagrams.py ──► draw.io .drawio files ──► Confluence Diagrams page
      ├─► confluence_sync_questionnaire_to_main.py ──► updates HLD sections 8–14
      └─► confluence_generate_implementation_pack.py ──► Terraform + JSON output

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENVIRONMENT SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Create and activate virtual environment:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

2. Install dependencies:
   pip install requests python-dotenv beautifulsoup4 lxml certifi

3. Copy .env and fill in values (see section below).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
.env FILE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Required:
  CONFLUENCE_BASE_URL=https://ukhsa.atlassian.net/wiki
  CONFLUENCE_SPACE_KEY=CDA
  CONFLUENCE_API_TOKEN=<token from https://id.atlassian.com/manage-profile/security/api-tokens>
  CONFLUENCE_USER_EMAIL=your.name@ukhsa.gov.uk

Optional (SSL — corporate proxy):
  CONFLUENCE_CA_BUNDLE=C:\path\to\ukhsa-root-ca.pem   ← preferred fix
  CONFLUENCE_SKIP_SSL_VERIFY=true                       ← temporary workaround only

Optional (page targeting):
  CONFLUENCE_MAIN_PAGE_TITLE=High-level Design (HLD) Solution Architecture Template
  CONFLUENCE_PARENT_PAGE_ID=173314084
  CONFLUENCE_SOURCE_PAGE_ID=<HLD page ID>       ← used by confluence_update_diagrams.py
  CONFLUENCE_TARGET_PAGE_ID=<Diagrams page ID>  ← used by confluence_update_diagrams.py
  CONFLUENCE_MAIN_PAGE_ID=<HLD page ID>         ← used by confluence_update_lld_diagrams.py
  CONFLUENCE_LLD_PAGE_ID=<LLD page ID>          ← used by confluence_update_lld_diagrams.py

Per-project .env files:
  setup_project.py writes .env.<project-slug> with all four page IDs automatically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECOMMENDED EXECUTION ORDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A. Maintain the master LENS HLD template:
   python confluence_enhance_main_page.py

B. Bootstrap a new project (run once per project):
   python setup_project.py
   → answer prompts for project name
   → loads .env.<slug> for subsequent scripts

C. New project workflow (after setup):
   1. Fill Sections 1–8 manually in Confluence HLD page
   2. python confluence_sync_questionnaire_to_main.py   (if using questionnaire)
   3. $env:CONFLUENCE_SOURCE_PAGE_ID=<hld-id>
      $env:CONFLUENCE_TARGET_PAGE_ID=<diagrams-id>
      python confluence_update_diagrams.py
   4. python confluence_generate_implementation_pack.py

D. Quick re-run for diagram updates only:
   python confluence_update_diagrams.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIAGRAM ICON SUPPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

confluence_update_diagrams.py auto-resolves icons from component names/
technology fields. Supported icon families (draw.io shape libraries):

  AWS      → mxgraph.aws4.resourceIcon  (orange/blue/purple AWS service icons)
             Matched on: EC2, S3, RDS, Lambda, ECS, Fargate, SageMaker, Glue,
             Kinesis, Redshift, Athena, Step Functions, API Gateway, WAF,
             CloudFront, IAM, KMS, GuardDuty, CloudTrail, SNS, SQS, EKS, EMR,
             Lake Formation, Secrets Manager, Transfer Family …

  Azure    → mxgraph.azure2             (blue Azure service icons)
             Matched on: Entra ID, APIM, Azure Functions, Blob Storage,
             Azure SQL, Cosmos DB, AKS, Container Instances, Azure DevOps,
             Azure Monitor, Key Vault, Service Bus, Event Hubs, Data Factory,
             Synapse Analytics, Azure Firewall, Load Balancer, App Service …

  On-Prem  → mxgraph.network            (grey network/infrastructure icons)
             Matched on: on-prem server, on-premises database, firewall,
             router, switch, load balancer, SFTP server, data centre,
             user, end user, analyst, laptop, desktop …

  OpenShift→ mxgraph.redhat             (Red Hat / OpenShift icons)
             Matched on: OpenShift, pod, operator, pipeline, Tekton,
             registry, Quay, ingress route, Ansible …

To trigger an icon: use the keyword in the component Name, Technology,
or Description columns in Section 10 (Architecture Components).

Example:
  Name: "Data Processing"  Technology: "AWS Glue"  → Glue icon (orange)
  Name: "Identity"         Technology: "Entra ID"  → Azure Entra icon (blue)
  Name: "Legacy DB Server" Technology: "On-Prem"   → server icon (grey)
  Name: "App Runtime"      Technology: "OpenShift"  → OpenShift icon (red)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HLD PAGE SECTION REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1.  Solution Overview            — governance front sheet
  2.  Introduction                 — plain-English problem + outcome
  3.  Background                   — as-is architecture snapshot
  4.  Pain Points                  — current constraints and problems
  5.  Functional Requirements      — what the system must do
  6.  Non-Functional Requirements  — performance, security, availability
  7.  Architecture Decision (HLD Options) — 2–3 options with pros/cons
  8.  Pattern Selection (8a–8f)    — UKHSA approved patterns tick-box
  9.  Context Entities             — external actors/systems → Context View diagram
  10. Architecture Components      — components with layer/cloud/tech → Solution Architecture diagram
  11. Architecture Connections     — source→dest flows → Connection diagrams
  12. Network Segmentation         — VPC/subnet CIDRs → Network diagram
  13. Data Flow Entries            — numbered flows → Data Flow diagram
  14. Dataset Inventory            — datasets + relationships → Dataset diagram
  15. Low-Level Design Summary     — LLD pointers
  16. Solution Option Cost Comparison — cost comparison table
  17. Implementation Handover      — delivery checklist
  18. Acronyms & Glossary          — reference (managed manually in Confluence)
  19. Reference Documents          — links + attachments
  20. [Section added manually]     — additional section

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
APPROVED PATTERNS REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Section 8 Pattern Selection uses UKHSA-approved pattern codes.
Full reference: UKHSA Cloud Strategy & Approved patterns.md

  Ingestion  (1A–1E): Batch SFTP, S3 Events, API Pull, Streaming, Direct Connect
  Processing (2A–2E): Serverless ETL, Spark, Scheduled Jobs, Real-time, ML
  Storage    (3A–3E): Data Lake (S3), Relational, Time-Series, Graph, Object
  Integration(4A–4C): REST API, Event-Driven, File Exchange
  Governance (5A–5C): Data Catalogue, Access Control, Lineage
  Security   (6A–6D): Access Control, Encryption, Network Security, DLP
  Observability(7A–7C): Centralised Logging, Tracing, Alerting
  Backup     (8a):    Backup & DR
  INF        (INF-01–INF-06): Landing Zone, Hybrid, Shared Services,
                               Split DNS, Federated Identity, GPU/ML Infra
  TSA-NET    (TSA-NET-01–02): Platform Segmentation, Public Endpoint

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  output/generated/           draw.io diagram files (uploaded to Confluence)
  output/terraform/aws/       AWS Terraform scaffold (main.tf)
  output/terraform/azure/     Azure Terraform scaffold (main.tf)
  output/implementation/      summary.json implementation pack

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SSL error (UNEXPECTED_EOF / certificate verify failed):
  The UKHSA corporate proxy intercepts TLS.
  Fix 1 (recommended): Set CONFLUENCE_CA_BUNDLE to the UKHSA root CA .pem path.
                        Ask IT for the certificate or export from Windows cert store.
  Fix 2 (temporary):   $env:CONFLUENCE_SKIP_SSL_VERIFY="true"
                        or set CONFLUENCE_SKIP_SSL_VERIFY=true in .env

403 Forbidden:
  Token may have expired. Rotate at:
  https://id.atlassian.com/manage-profile/security/api-tokens
  Ensure CONFLUENCE_USER_EMAIL is also set (Basic auth fallback).

Empty diagrams:
  Sections 9–14 must contain data rows. Check the HLD page tables.

Sections appearing in wrong order (e.g. 18 after 20):
  Run confluence_enhance_main_page.py — it corrects section ordering.

Fast-Fill / How-to-Use headings missing:
  Run confluence_enhance_main_page.py — _replace_intro_panels restores them.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECURITY NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Never commit .env to version control (it is in .gitignore).
- Rotate your API token if it appears in terminal output or logs.
- CONFLUENCE_SKIP_SSL_VERIFY=true disables all certificate validation.
  Use only temporarily and never in shared/CI environments.
- .env.<project-slug> files contain page IDs only — no credentials.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KNOWN LIMITATIONS & SUGGESTED IMPROVEMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current limitations:
- No shared utility module: auth/TLS/request helpers are duplicated across
  confluence_enhance_main_page.py, confluence_update_diagrams.py,
  setup_project.py, and confluence_generate_implementation_pack.py.
- Icons only render if keyword matches exactly — hyphenation variants
  (e.g. "on-prem" vs "on premises") may miss. Add synonyms to _HLD_ICON_HINTS.
- Terraform output is a starter scaffold only; modules/variables not wired.

Suggested improvements:
- Extract shared auth/TLS/Confluence API calls into confluence_client.py.
- Add a --dry-run flag to preview changes without writing to Confluence.
- Add --project flag to confluence_update_diagrams.py to load .env.<slug>
  automatically without manual $env: exports.
- Wire popular cross-cloud patterns (e.g. Zero Trust, Service Mesh, GitOps)
  into Section 8 pattern rows to cover Azure-native and hybrid workloads.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UKHSA REFERENCE LINKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Security:
  CIS Benchmarks: https://www.cisecurity.org/cis-benchmarks
  Enterprise Guide Rails: https://ukhsa.atlassian.net/wiki/spaces/AT/pages/170626343
  Secure by Design SAT: https://ukhsa.atlassian.net/wiki/spaces/CDA/pages/521568547

Network Design:
  Network Design: https://ukhsa.atlassian.net/wiki/spaces/HALO/pages/172255190
  Strategic Network Summary: https://ukhsa.atlassian.net/wiki/spaces/HIDM/pages/167629598
  Cloud Network Security Pattern: https://ukhsa.atlassian.net/wiki/spaces/AT/pages/170627256

Governance:
  Governance controls: https://ukhsa.atlassian.net/wiki/spaces/UAOM/pages/484737698
  Governance Domains: https://ukhsa.atlassian.net/wiki/spaces/EDCE/pages/448954953

Data Protection:
  DPIA Review Process: https://ukhsa.atlassian.net/wiki/spaces/HALO/pages/172194466
  Data sharing arrangements: https://ukhsa.atlassian.net/wiki/spaces/EDGE/pages/164039010

EDAP Integration:
  All new analytical workloads must integrate with EDAP (AWS-based central
  data platform: Ingestion → Raw → Conform → DataMart → Export/Analytics)
  or explicitly justify a non-EDAP pattern in Section 7 (HLD Options).


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

Cross-Team Policies and Standards (Apply at All Layers)

Security
- CIS Benchmarks: https://www.cisecurity.org/cis-benchmarks
- Enterprise Guide Rails Catalogue: https://ukhsa.atlassian.net/wiki/spaces/AT/pages/170626343/Enterprise+Guide+Rails+Catalogue+Strategic?pageId=170626343
- Security Frameworks and Legislations: https://ukhsa.atlassian.net/wiki/spaces/CCE/pages/176654107/Frameworks+and+Legislations

Network Design
- Network Design: https://ukhsa.atlassian.net/wiki/spaces/HALO/pages/172255190/Network+Design
- Strategic Network Summary: https://ukhsa.atlassian.net/wiki/spaces/HIDM/pages/167629598/Strategic+Network+Summary
- Cloud Network Security Pattern: https://ukhsa.atlassian.net/wiki/spaces/AT/pages/170627256/Cloud+Network+Security+Pattern

Governance Controls
- Governance controls: https://ukhsa.atlassian.net/wiki/spaces/UAOM/pages/484737698/Governance+controls
- Governance Domains: https://ukhsa.atlassian.net/wiki/spaces/EDCE/pages/448954953/Governance+Domains
- Governance risks and issues: https://ukhsa.atlassian.net/wiki/spaces/ICTPMO/pages/175112629/Governance+risks+and+issues

Data Protection, DPIA and Data Sharing
- UKHSA Cloud Platform Data Protection Impact Assessment (DPIA) Review Process: https://ukhsa.atlassian.net/wiki/spaces/HALO/pages/172194466/UKHSA+Cloud+Platform+Data+Protection+Impact+Assessment+DPIA+Review+Process
- Data sharing arrangements (WIP): https://ukhsa.atlassian.net/wiki/spaces/EDGE/pages/164039010/Data+sharing+arrangements+WIP

ITSM Management
- ITSM Problem Management Policy: https://ukhsa.atlassian.net/wiki/spaces/ISM/pages/167627576/ITSM+Problem+Management+Policy

EDAP Integration Requirement
- EDAP is the analytical platform where analytical programs are being migrated to AWS.
- For any new analytical requirement, architecture must be designed to integrate with EDAP, or explicitly justify a non-EDAP pattern.

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
