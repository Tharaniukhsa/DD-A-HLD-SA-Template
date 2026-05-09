# UKHSA Approved Cloud Strategy & Approved Data Patterns 2025

**Document Version:** 1.2 (May 2025)  
**Status:** Published  
**Classification:** Official  

---

## Table of Contents

### Part 1: UKHSA Cloud Strategy 2025
1. [Executive Summary](#part-1-executive-summary)
2. [Cloud Vision & Objectives](#cloud-vision--objectives)
3. [Strategic Cloud Principles](#strategic-cloud-principles)
4. [Technical Cloud Principles](#technical-cloud-principles)
5. [Cloud Operating Model](#cloud-operating-model)
6. [Cloud Platforms & Architecture](#cloud-platforms--architecture)

### Part 2: Approved Data Patterns by Layer
7. [Data Ingestion Layer](#part-2-data-ingestion-layer)
8. [Data Processing Layer](#data-processing-layer)
9. [Data Storage Layer](#data-storage-layer)
10. [Data Integration & Movement](#data-integration--movement-layer)
11. [Data Governance & Cataloging](#data-governance--cataloging-layer)
12. [Security & Compliance Layer](#security--compliance-layer)
13. [Monitoring & Observability](#monitoring--observability-layer)
14. [Resilience & Disaster Recovery](#resilience--disaster-recovery)

### Part 3: Architecture Decision Records & Quick Reference
15. [Approved ADRs](#approved-adrs)
16. [Quick-Pick Cheat Sheet](#quick-pick-cheat-sheet)
17. [Glossary](#glossary)

---

# PART 1: UKHSA CLOUD STRATEGY 2025

## Executive Summary

UKHSA was established in 2021 to lead the UK's health security response, building on Public Health England and NHS Test and Trace. Through these organisations, UKHSA inherited a complex technology landscape spanning on-premise and public cloud environments.

**Key Challenge:** Tactical cloud adoption during COVID-19 created diverse, inconsistent infrastructure across AWS and Azure with varying maturity levels, security standards, and cost management. This complexity hinders the agency's ability to respond quickly to health security threats.

**Strategic Response:** This Cloud Strategy describes how UKHSA will consolidate, standardise, and optimise its cloud environments through:
- A Cloud Centre of Excellence (CCoE) for governance
- Consistent multi-cloud platforms (AWS + Azure)
- Cloud Control Framework for security and compliance
- Approved data patterns for architecture standardisation

**Strategic Vision:**
> "UKHSA will leverage the scalability, agility, security and advanced capabilities of cloud technology, as a key enabler of the Agency's aim to be a scientific and operational leader in proactive and responsive health security."

---

## Cloud Vision & Objectives

### UKHSA Cloud Vision

UKHSA cloud environments will be the foundation of technology infrastructure enabling:
- **Rapid Response:** Scale quickly when new health threats emerge
- **Advanced Analytics:** Bring together disease, genomic, and environmental data
- **Scientific Innovation:** Provide computing power for research and vaccine development
- **Cost Efficiency:** Streamline operations and reduce infrastructure costs
- **Seamless Collaboration:** Share real-time data with partners, the NHS, and international agencies

### UKHSA Cloud Objectives

1. **Enable rapid collaboration** with partners, universities, and industry
2. **Support scientific research** with powerful analytics and computing tools
3. **Simplify data sharing** across systems securely
4. **Scale quickly** when responding to health emergencies
5. **Maintain security and compliance** with UK government standards
6. **Reduce costs** through efficient cloud operations
7. **Build accountability** across teams for resource usage
8. **Make tools easy to use** for non-technical staff
9. **Help the whole organisation adopt cloud** confidently

---

## Strategic Cloud Principles

UKHSA will achieve its Cloud Vision through five core principles:

### 1. Reduce Risk
**We understand cloud risks and put controls in place to manage them.**  
Controls will prevent misconfigured systems, detect problems automatically, and clarify who is responsible for what.

### 2. Increase Consistency
**Teams use the same tools and approaches for the same problems.**  
This reduces confusion, makes training easier, and means solutions work reliably.

### 3. Accelerate Delivery
**Make it fast and easy for teams to launch new cloud solutions.**  
Pre-approved patterns and self-service support reduce delays from governance reviews.

### 4. Build Culture
**Foster continuous improvement and cost awareness across the organisation.**  
Success requires shared ownership and transparent communication.

### 5. Enable Adoption
**Help teams confidently adopt cloud.**  
Role-based training (for researchers, analysts, operations) plus dedicated advisory support make adoption easy.

---

## Technical Cloud Principles

To balance innovation with security and cost control, UKHSA adopts these technical approaches:

1. **Multi-Cloud (AWS + Azure)** — Use both cloud providers to avoid being locked into one
2. **Prefer Cloud-Native Services** — Use managed cloud services instead of building from scratch
3. **Keep Platforms Up-to-Date** — Regular security updates and modernisation prevent technical debt
4. **Minimize On-Premises Dependencies** — Reduce reliance on legacy data centres
5. **Immutable Infrastructure** — Design systems that don't change after deployment (rebuild instead)
6. **Cloud-First Mindset** — Modernize legacy systems rather than just moving them as-is
7. **Automate Everything** — Use Infrastructure as Code to ensure consistency and speed
8. **Reuse and Share** — Build components once, share them across teams
9. **Centralise What Makes Sense** — Centralise platform capabilities to reduce duplication
10. **Optimise for Cost and Performance** — Right-size resources to save money and meet performance needs
11. **Security Built In** — Design security controls from the start, not as an afterthought

---

## Cloud Operating Model

UKHSA will operate cloud through a **Cloud Centre of Excellence (CCoE)** — a central team that ensures best practices are followed consistently across the organisation.

### The CCoE Will:
- Set and enforce cloud standards and policies
- Approve architecture patterns to speed up projects
- Manage platform services and the service catalogue
- Ensure compliance with security and cost controls
- Support teams adopting cloud confidently

### How It Works:
- **In-House Teams** (Cloud Business Office) handle governance, standards, training, and cost management
- **Partner Teams** (Cloud Platform Engineering) manage the day-to-day cloud infrastructure
- **Governance Forums** meet regularly (weekly, fortnightly, monthly) to review decisions and solve problems

### The Cloud Platforms:
UKHSA will have one consistent cloud platform on **AWS** and one on **Azure**, each with:
- Pre-approved accounts for new projects
- Built-in security controls and monitoring
- A catalogue of ready-to-use services
- Standard architecture patterns for common problems

---

## Cloud Platforms & Architecture

### Where We Are Today
- Cloud systems spread across AWS and Azure with varying standards
- Some legacy systems still on-premises that need cloud support
- High-performance computing on-premises with cloud burst capacity

### Where We're Going
- Single, consistent cloud platform on each cloud provider (AWS and Azure)
- All new projects launch through standardised accounts with built-in controls
- Reusable services and patterns available to speed up delivery
- Cloud remains secure by design with monitoring and compliance built-in

### Core Platform Capabilities
Each cloud platform will provide:
- **Account Setup:** Automated provisioning of new project accounts
- **Security Controls:** Preventative guardrails (stop bad configurations) + detective controls (catch problems)
- **Platform Services:** Pre-built capabilities teams can use immediately
- **Architecture Patterns:** Reference designs pre-approved by governance
- **Compliance Monitoring:** Continuous verification that systems meet standards

### Identity & Access
- **Zero Trust:** Every access request verified, not just perimeter trust
- **Single Sign-On:** One identity works everywhere (on-premises, AWS, Azure, SaaS)
- **Least Privilege:** Teams only get access they need
- **Monitoring:** All access logged and audited

### Networking
- Cloud networks don't depend on on-premises infrastructure
- Direct connectivity between AWS and Azure
- Security applied consistently everywhere
- Encrypted data movement across networks

---

---

# PART 2: APPROVED DATA PATTERNS AT A GLANCE

## Overview

Approved data patterns are standardised, pre-approved architectural blueprints that UKHSA teams use when designing data solutions. Instead of reinventing solutions, teams pick the pattern that matches their needs, and it comes with security and compliance built in.

**8 Layers × 28 Patterns:**
- **Data Ingestion** — How data arrives (4 patterns)
- **Data Processing** — How data is cleaned and transformed (4 patterns)
- **Data Storage** — Where data lives persistently (5 patterns)
- **Data Integration** — How systems stay loosely coupled (3 patterns)
- **Data Governance** — Knowing what you have (3 patterns)
- **Security & Compliance** — Keeping data safe — **MANDATORY** (4 patterns)
- **Monitoring & Observability** — Seeing what's happening (3 patterns)
- **Resilience & Disaster Recovery** — Keeping systems running (2 patterns)

---

## Data Patterns Summary by Layer

### 1. Data Ingestion Layer — How Data Enters UKHSA

| When You Need | Pattern | Example | AWS Services |
|---|---|---|---|
| **Real-time data from API calls** | Direct API Ingestion | NHS hospital sending admission data continuously | API Gateway, SQS, EventBridge |
| **Bulk files on schedule** | Batch File Upload | Partner sending monthly CSV reports | S3, AWS Glue, SFTP |
| **Keep existing database in sync** | Database Replication | Mirror operational case system to cloud for analytics | DMS, RDS, Aurora |
| **High-speed streaming data** | Streaming Ingestion | Live lab sensor readings or surveillance metrics | Kinesis, MSK (Kafka), Lambda |

---

### 2. Data Processing Layer — Cleaning & Transforming Data

| When You Need | Pattern | Example | AWS Services |
|---|---|---|---|
| **Scheduled large batch processing** | Batch ETL | Nightly job: dedup lab results, validate, load warehouse | AWS Glue, Step Functions, DataBrew |
| **Instant processing of data** | Real-time Stream Processing | Alert if infection rate spikes above threshold | Kinesis Data Analytics, Lambda |
| **Heavy analytics / ML training** | Scheduled Spark/ML Jobs | Monthly predictive disease modelling (runs once, then stops)| EMR, SageMaker |
| **Query across multiple data stores** | Federated Query | Cross-dataset analysis (cases + genomics + labs) without copying data | Athena, Redshift Spectrum |

---

### 3. Data Storage Layer — Where Data Lives Persistently

| When You Need | Pattern | Use Case | AWS Services |
|---|---|---|---|
| **Live operational database** | Transactional DB (OLTP) | Patient records, case management, real-time dashboards | Aurora PostgreSQL, RDS, DynamoDB |
| **Historical reporting / BI** | Data Warehouse (OLAP) | Multi-year trend analysis, annual surveillance reports | Redshift, QuickSight |
| **Unstructured / mixed data** | Data Lake (Bronze/Silver/Gold) | Genomic files, documents, raw data with audit trail | S3 (3 zones), Glue Catalog, Lake Formation |
| **Sensor / metrics over time** | Time-Series Database | Lab capacity per hour, infection rate per minute | Timestream |
| **Nested / variable-structure data** | Document Store | Case investigation records, incident reports, event logs | DynamoDB, DocumentDB, OpenSearch |

---

### 4. Data Integration & Movement Layer — Systems Staying Loosely Coupled

| When You Need | Pattern | Example | AWS Services |
|---|---|---|---|
| **Event-driven workflows** | Event-Driven Pipelines | "New data arrived" event triggers downstream validation | EventBridge, SQS, SNS, Lambda |
| **Complex multi-step workflows** | ETL Orchestration | Daily: ingest → transform → validate → publish (with retry logic) | Step Functions, Apache Airflow |
| **High availability / compliance** | Data Replication & Sync | Keep backup in secondary region; read replicas for analytics | S3 Cross-Region Replication, RDS Read Replicas |

---

### 5. Data Governance & Cataloging Layer — Knowing What You Have

| When You Need | Pattern | Example | AWS Services |
|---|---|---|---|
| **Discover & govern all datasets** | Centralised Data Catalogue | "What epidemiological datasets exist, who owns them, sensitivity level?" | Glue Catalog, Lake Formation |
| **Prevent bad data** | Data Quality & Validation | Before publishing, validate ranges, check for nulls, remove duplicates | Glue DataBrew, Quality Checks, EventBridge |
| **Compliance & forensics** | Data Lineage & Audit Trail | "Trace where this data came from, all transformations, who accessed it" | Lake Formation, CloudTrail, S3 access logs |

---

### 6. Security & Compliance Layer — Keeping Data Safe (**MANDATORY FOR ALL SOLUTIONS**)

| Control | Pattern | Standard | AWS Services |
|---|---|---|---|
| **Who can access what** | Access Control (IAM + Entra ID) | Single identity, MFA mandatory, temporary credentials only | IAM, Entra ID, Lake Formation, S3 Object Lock |
| **Data protection at rest & in transit** | Encryption & Key Management | AES-256 at rest, TLS 1.2+ in transit, customer-managed keys | KMS, Secrets Manager, ACM |
| **Network isolation** | Network Security & Isolation | Private VPC only, no public internet, VPC endpoints | VPC, Security Groups, VPC Endpoints, PrivateLink, WAF |
| **Share data safely** | Data Masking & Anonymisation | Remove names/IDs or replace with tokens before sharing externally | Glue DataBrew, Lambda, RDS, Redshift |

---

### 7. Monitoring & Observability Layer — Seeing What's Happening

| When You Need | Pattern | Example | AWS Services |
|---|---|---|---|
| **Know what happened** | Centralised Logging & Monitoring | Pipeline error → log captured → on-call team alerted automatically | CloudWatch Logs, X-Ray, EventBridge, CloudTrail |
| **Know if it's performing** | Performance Monitoring & Alerting | Alert if query takes > 30 seconds, or if cost spikes | CloudWatch Metrics, CloudWatch Alarms, SNS |
| **Know where money is going** | Cost Tracking & Optimisation | Dashboard shows cost per project/team; alert if budget exceeded | Cost Explorer, Budgets, Compute Optimizer |

---

### 8. Resilience & Disaster Recovery Layer — Keeping Systems Running

| When You Need | Pattern | Example | AWS Services |
|---|---|---|---|
| **Survive accidents & failures** | Backup & Point-in-Time Recovery | Daily snapshots; restore epidemiological DB to any point in last 35 days | AWS Backup, RDS snapshots, S3 versioning |
| **Survive regional outage** | Multi-Region Failover | London region unavailable → traffic auto-routes to Ireland | Route 53, S3 Cross-Region Replication, RDS replicas |

---

## How to Use These Patterns

**Step 1: Identify Your Problem**  
"I need to ingest real-time lab test results continuously."  
→ Data Ingestion Layer

**Step 2: Pick the Pattern**  
"Data arrives continuously, I need it instantly."  
→ Direct API Ingestion (Pattern 1A)

**Step 3: Apply Mandatory Security**  
All solutions must include:
- Access Control (IAM + Entra ID) ✓
- Encryption (at rest + in transit) ✓
- Network Security (private VPC) ✓
- Data Masking (if sharing externally) ✓
- Monitoring & Logging ✓
- Backup & Recovery ✓

**Step 4: Reference the Service Catalogue**  
Use AWS services from the patterns above (pre-configured, secure, support available).


# PART 3: ARCHITECTURE DECISION RECORDS & QUICK REFERENCE

## Approved ADRs

These are firm decisions that apply to **all** UKHSA data solutions. You do not need to re-justify these — they are already decided:

| ADR | Decision | Why |
|-----|----------|-----|
| **ADR-001** | Use PostgreSQL (not MySQL) for new OLTP systems | Better JSON support, window functions, standards compliance |
| **ADR-002** | Use S3 + Glue instead of HDFS for data lakes | Serverless — no cluster to manage, lower cost, simpler |
| **ADR-003** | Prefer Redshift Spectrum over Athena for queries on datasets >100 GB | Significantly better performance at large scale |
| **ADR-004** | Use EventBridge over SNS/SQS for event orchestration | Built-in schema validation, event routing without code |
| **ADR-005** | All data in transit must use TLS 1.2 or higher | Mandatory per UKHSA security standards |
| **ADR-006** | Customer-managed KMS keys required for sensitive data | GDPR and Data Protection Act compliance |
| **ADR-007** | All data lakes must use Bronze/Silver/Gold three-zone model | Enforces data quality gates, traceability, governance |
| **ADR-008** | Multi-cloud strategy (AWS + Azure) for avoiding lock-in | Flexibility, competitive pricing, resilience |
| **ADR-009** | Infrastructure as Code (IaC) mandatory for production | Consistency, repeatability, auditability |
| **ADR-010** | Zero Trust identity model across all cloud environments | Security by default, principle of least privilege |

---

## Quick-Pick Cheat Sheet

**Not sure which pattern to pick?** Use this table as a starting point:

| If you need to… | Start with this pattern | Why |
|---|---|---|
| Receive data from external API in real time | **1A** Direct API Ingestion | Real-time, always-on feed |
| Accept large file upload from partner | **1B** Batch File Upload | Bulk data, scheduled arrivals |
| Mirror legacy database into AWS | **1C** Database Replication | Continuous sync, operational system |
| Ingest thousands of sensor readings per second | **1D** Streaming Ingestion | Very high frequency |
| Run nightly data cleaning & transformation | **2A** Batch ETL | Scheduled, large volume |
| Detect anomalies the moment data arrives | **2B** Real-time Stream Processing | Instant response needed |
| Train machine learning model | **2C** Scheduled Spark / ML Jobs | Complex computation, scheduled |
| Query several databases without moving data | **2D** Federated Query | Ad-hoc analysis across sources |
| Store operational, live-query data | **3A** Transactional Database | Many simultaneous users |
| Run complex reports across years of history | **3B** Data Warehouse | Historical reporting, large scale |
| Store raw and mixed-format data flexibly | **3C** Data Lake (Bronze/Silver/Gold) | Exploratory analytics, mixed schemas |
| Store time-stamped metrics or sensor data | **3D** Time-Series Database | Metrics over time, high frequency |
| Store JSON documents or event logs | **3E** Document Store | Nested, variable-structure data |
| Trigger downstream systems when data arrives | **4A** Event-Driven Pipelines | Decoupled systems, event reaction |
| Coordinate multi-step data pipeline | **4B** ETL Orchestration | Complex dependencies, workflow |
| Keep two regions in sync for resilience | **4C** Data Replication & Sync | High availability, compliance |
| Discover and document all datasets | **5A** Centralised Data Catalogue | Governance, discovery, lineage |
| Prevent bad data from spreading | **5B** Data Quality & Validation | Quality gates, compliance |
| Prove data came through approved pathway | **5C** Data Lineage & Audit Trail | Audit trail, GDPR, incident response |
| Control who accesses what data | **6A** Access Control (IAM + Entra ID) | Security by default, least privilege |
| Protect sensitive data at rest and in transit | **6B** Encryption & Key Management | Mandatory for sensitive/restricted data |
| Prevent data from crossing public internet | **6C** Network Security & Isolation | Production systems, compliance |
| Share data with external researchers | **6D** Data Masking & Anonymisation | GDPR compliance, PII protection |
| Debug system issues and audit activity | **7A** Centralised Logging | Troubleshooting, compliance, incident response |
| Alert when data quality degrades | **7B** Data Quality Monitoring | SLAs, early warning |
| Track and optimise cloud costs | **7C** Performance & Cost Monitoring | Cost governance, efficiency |
| Prevent data loss from system failure | **8A** Backup Strategy | Disaster recovery, criticality levels |
| Survive regional outage | **8B** Multi-AZ / Multi-Region | Critical services, resilience |

---

## Glossary

| Term | Definition |
|------|-----------|
| **ADR** | Architecture Decision Record — a firm decision applied across UKHSA |
| **API** | Application Programming Interface — a way for systems to talk to each other |
| **AWS** | Amazon Web Services |
| **Azure / Entra ID** | Microsoft cloud platform and identity service |
| **CBO** | Cloud Business Office — in-house resources managing governance |
| **CCoE** | Cloud Centre of Excellence — centralised governance body |
| **CDC** | Change Data Capture — tracking changes to database records |
| **CPE** | Cloud Platform Engineering — outsourced delivery partners |
| **ETL** | Extract, Transform, Load — data pipeline pattern |
| **GDPR** | General Data Protection Regulation — EU data protection law |
| **IAM** | Identity and Access Management — user authentication and authorisation |
| **IaC** | Infrastructure as Code — defining infrastructure via code |
| **KMS** | Key Management Service — encryption key management |
| **MFA** | Multi-Factor Authentication — multiple verification methods required |
| **OLAP** | Online Analytical Processing — complex queries on historical data |
| **OLTP** | Online Transaction Processing — many small reads/writes |
| **OKR** | Objectives and Key Results — goal-setting framework |
| **PII** | Personally Identifiable Information — data that identifies an individual |
| **RPO** | Recovery Point Objective — maximum data loss acceptable |
| **RTO** | Recovery Time Objective — maximum recovery time acceptable |
| **SaaS** | Software as a Service — vendor-hosted software |
| **SIEM** | Security Information and Event Management — security monitoring |
| **SLA** | Service Level Agreement — promised availability/quality |
| **VPC** | Virtual Private Cloud — isolated network |
| **Zero Trust** | Security model assuming no implicit trust, verify everything |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-04-25 | Dan Farrar | Initial issue of Cloud Strategy |
| 1.1 | 2025-05-01 | Sean Spicer | TRB comments incorporated |
| 1.2 | 2025-05-21 | Combined | Merged Cloud Strategy v1.2 with Approved Data Patterns; plain-English data patterns added |

---

**Document Status:** This is a controlled document. The electronic version in the workspace is the controlled copy. Printed copies are not controlled.

**Next Review:** 2025-11-21

**Owner:** UKHSA Cloud Centre of Excellence
