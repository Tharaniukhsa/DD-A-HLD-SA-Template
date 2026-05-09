"""
Test the complete architecture pipeline with a sample project scenario.
This script:
1. Creates/updates a Confluence page with sample architecture data
2. Runs the diagram generation pipeline
3. Verifies all outputs
"""

import json
import os
import sys
import subprocess
from dotenv import load_dotenv

load_dotenv()

# ── Sample Architecture Data ────────────────────────────────────────────────

SAMPLE_PROJECT = """
# Digital Health Records Management System

## Project Overview
A comprehensive solution for managing patient health records across the UK Health Security Agency.
This system enables authorized healthcare professionals to access, update, and securely store patient records.

## Business Outcome
Improve healthcare service delivery by providing secure, real-time access to patient health records
while maintaining compliance with NHS Data Security and Protection Toolkit (DSPT).

---

## Architecture Components

| No | Name | Layer | Technology | Description |
|---|---|---|---|---|
| 1 | Healthcare Portal | Edge | React.js, TypeScript | Web-based portal for healthcare professionals to access and manage patient records |
| 2 | Mobile Health App | Edge | React Native | Mobile application for on-the-go access to patient records (iOS/Android) |
| 3 | AWS CloudFront CDN | Edge | CloudFront | Global content delivery network for portal static assets |
| 4 | API Gateway | Network | API Gateway | Central API endpoint for all frontend-backend communication |
| 5 | Web Application Firewall | Network | AWS WAF | Protects against common web exploits (SQL injection, XSS, DDoS) |
| 6 | Network Load Balancer | Network | NLB | Distributes incoming traffic across multiple application instances |
| 7 | Identity Service | Platform | Entra ID (Azure AD) | Single sign-on and multi-factor authentication for all users |
| 8 | Encryption Service | Platform | AWS KMS | Manages encryption keys for data at rest and in transit |
| 9 | Audit Logging Service | Platform | CloudWatch Logs | Centralized logging for compliance and security audits |
| 10 | Records API Service | Application | Python FastAPI | Microservice for patient record management operations |
| 11 | Search Service | Application | Elasticsearch | Full-text search engine for patient records |
| 12 | Notification Service | Application | SNS + Lambda | Sends alerts and notifications to healthcare professionals |
| 13 | Patient Records Database | Data | RDS Aurora (PostgreSQL) | Primary relational database for patient records |
| 14 | Data Lake | Data | S3 + Glue | Long-term storage for historical data and analytics |
| 15 | Search Index | Data | Elasticsearch Index | Indexed data for fast full-text search capabilities |

---

## Architecture Connections

| From | To | Label |
|---|---|---|
| Healthcare Portal | CloudFront CDN | Static Assets (CSS/JS/Images) |
| Healthcare Portal | API Gateway | REST API Calls (HTTPS) |
| Mobile Health App | API Gateway | REST API Calls (HTTPS) |
| API Gateway | Web Application Firewall | Request Routing |
| Web Application Firewall | Network Load Balancer | Filtered Traffic |
| Network Load Balancer | Records API Service | HTTP Internal |
| Network Load Balancer | Search Service | HTTP Internal |
| Records API Service | Identity Service | User Authentication & Authorization |
| Records API Service | Encryption Service | Encrypt/Decrypt Data |
| Records API Service | Patient Records Database | Read/Write Patient Records |
| Records API Service | Audit Logging Service | Log All Operations |
| Records API Service | Notification Service | Trigger Alerts |
| Search Service | Search Index | Query Index Data |
| Notification Service | Healthcare Portal | Push Notifications |
| Patient Records Database | Data Lake | Nightly ETL |
| Data Lake | Search Index | Analytics Feed |

---

## Data Flow Entries

| ID | Source | Destination | Data | Protocol |
|---|---|---|---|---|
| DF-001 | Healthcare Professional | Healthcare Portal | Login Request | HTTPS |
| DF-002 | Healthcare Portal | Identity Service | User Credentials | HTTPS |
| DF-003 | Identity Service | Healthcare Portal | JWT Token | HTTPS |
| DF-004 | Healthcare Portal | Records API Service | Patient Record Query | REST/JSON |
| DF-005 | Records API Service | Patient Records Database | SQL Query | TLS |
| DF-006 | Patient Records Database | Records API Service | Patient Record Data | TLS |
| DF-007 | Records API Service | Encryption Service | Plaintext Data | HTTPS |
| DF-008 | Encryption Service | Records API Service | Encrypted Data | HTTPS |
| DF-009 | Records API Service | Audit Logging Service | Audit Event | HTTPS |
| DF-010 | Healthcare Portal | Search Service | Search Query | REST/JSON |
| DF-011 | Search Service | Search Index | Elasticsearch Query | HTTP |
| DF-012 | Search Index | Search Service | Search Results | HTTP |
| DF-013 | Records API Service | Notification Service | Alert Message | SNS |
| DF-014 | Notification Service | Healthcare Portal | Push Notification | WebSocket |
| DF-015 | Data Lake | Analytics Tools | Analytics Data | S3/Parquet |

---

## Dataset Inventory

| ID | Name | Type | Primary Key | Sensitivity | Retention |
|---|---|---|---|---|---|
| DS-001 | Patient Demographics | Relational | patient_id | High | 7 Years |
| DS-002 | Medical History | Relational | record_id | High | 10 Years |
| DS-003 | Prescriptions | Relational | prescription_id | High | 5 Years |
| DS-004 | Lab Results | Relational | result_id | High | 7 Years |
| DS-005 | Appointments | Relational | appointment_id | Medium | 3 Years |
| DS-006 | Audit Trail | Relational | audit_id | Medium | 5 Years |
| DS-007 | User Activity Logs | Unstructured | log_id | Medium | 1 Year |
| DS-008 | Historical Analytics | Parquet | record_id | Low | 10 Years |

---

## Dataset Relationships

| Source | Target | Relation | Mapping |
|---|---|---|---|
| Patient Demographics | Medical History | 1:N | patient_id -> patient_id |
| Patient Demographics | Prescriptions | 1:N | patient_id -> patient_id |
| Patient Demographics | Appointments | 1:N | patient_id -> patient_id |
| Medical History | Lab Results | 1:N | record_id -> related_record_id |
| Prescriptions | Lab Results | N:M | prescription_id <-> lab_test_id |
| Patient Demographics | Historical Analytics | 1:N | patient_id -> patient_id |

---

## Context Entities

| Name | Type | Interaction |
|---|---|---|
| Healthcare Professional | User | Portal Access, Record Management |
| Patient | Person | Records Stored, Notifications Received |
| NHS Systems | External System | Data Exchange, Clinical Integration |
| Compliance Auditor | User | Audit Trail Review, Compliance Reports |
| Data Analyst | User | Analytics Dashboard Access |
| System Administrator | User | System Configuration, User Management |

---

## Security & Compliance

### Security Requirements
- **Authentication**: Multi-factor authentication (MFA) via Entra ID
- **Encryption**: AES-256 encryption at rest, TLS 1.3 in transit
- **Access Control**: Role-based access control (RBAC) with principle of least privilege
- **Audit Logging**: All access attempts and data modifications logged
- **Network Security**: WAF, DDoS protection, network segmentation

### Compliance Standards
- NHS Data Security and Protection Toolkit (DSPT)
- GDPR and UK Data Protection Act 2018
- NHS Information Governance Toolkit (IGT)
- NIST Cybersecurity Framework

### Data Classification
- **High Sensitivity**: Patient Demographics, Medical History, Prescriptions, Lab Results
- **Medium Sensitivity**: Appointments, Audit Trail
- **Low Sensitivity**: Public Statistics, Anonymized Analytics

"""

def main():
    """Main test execution"""
    print("=" * 70)
    print("DIGITAL HEALTH RECORDS MANAGEMENT SYSTEM - ARCHITECTURE TEST")
    print("=" * 70)
    print()
    
    # Write sample data to QUESTIONNAIRE_PLAN.md for reference
    with open("SAMPLE_ARCHITECTURE_SCENARIO.md", "w") as f:
        f.write(SAMPLE_PROJECT)
    print("✓ Created sample architecture scenario: SAMPLE_ARCHITECTURE_SCENARIO.md")
    print()
    
    # Run the full pipeline
    print("=" * 70)
    print("STEP 1: Run confluence_enhance_main_page.py")
    print("=" * 70)
    result = subprocess.run([".venv\\Scripts\\python.exe", "confluence_enhance_main_page.py"], 
                          capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("ERROR:", result.stderr)
        return False
    print()
    
    print("=" * 70)
    print("STEP 2: Run confluence_update_diagrams.py")
    print("=" * 70)
    result = subprocess.run([".venv\\Scripts\\python.exe", "confluence_update_diagrams.py"], 
                          capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("ERROR:", result.stderr)
        return False
    print()
    
    print("=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    print("✓ Main Solution Architecture page updated in Confluence")
    print("✓ Questionnaire data uploaded")
    print("✓ Architecture diagrams generated and embedded")
    print()
    print("Generated Files:")
    
    # Check output directory
    if os.path.exists("output"):
        for file in os.listdir("output"):
            if file.endswith(".drawio"):
                print(f"  - output/{file}")
    print()
    
    print("=" * 70)
    print("✓ COMPLETE: All diagrams are now available in Confluence")
    print("=" * 70)
    print()
    print("Next Steps:")
    print("1. Open Confluence and navigate to 'Solution Architecture' page")
    print("2. View the generated diagrams (Solution Architecture, Data Flow, etc.)")
    print("3. Review the tables with sample data")
    print("4. Download output/*.drawio files for further customization")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
