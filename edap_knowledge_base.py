"""
EDAP (Enterprise Data Analytics Platform) Knowledge Base
=========================================================
Source: UKHSA EDAP AWS Technical Design (V36+)
        https://ukhsa.atlassian.net/wiki/spaces/EDAP/pages/165357494/AWS+Technical+Design

This module is the single source of truth for EDAP architecture knowledge used
by the diagram generators.  When a new project needs to integrate data into EDAP,
importing this module and calling `detect_edap_patterns()` returns the set of
EDAP integration patterns relevant to that project.  The diagram generators then
auto-inject the correct EDAP components, connections, data-flows and context
entities so all diagrams are produced correctly without manual input.

EDAP Layers (in order of data flow)
-------------------------------------
  Ingestion  →  Raw  →  Conform  →  DataMart  →  Export / Analytics

EDAP Architecture Principles (from §3 of Technical Design)
------------------------------------------------------------
  - Prefer Native AWS Services over third-party
  - Prefer Serverless
  - Soft Infrastructure (all Terraform)
  - Immutable Server pattern
  - Multi-AZ, single region (eu-west-2)
  - Open File Formats (Apache Parquet, JSON, CSV)
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# EDAP Layer definitions
# ─────────────────────────────────────────────────────────────────────────────

EDAP_LAYERS = {
    "ingestion": {
        "label": "EDAP Ingestion Layer",
        "sublayers": ["Staging", "Cleared"],
        "technology": "Amazon S3",
        "description": (
            "Landing zone for all inbound data. Files land in Staging, are "
            "antivirus-scanned (Cloud Storage Security), then moved to Cleared "
            "to trigger Ingestion2Raw processing."
        ),
    },
    "raw": {
        "label": "EDAP Raw Layer",
        "technology": "Amazon S3 (Parquet/Snappy) + Glue Data Catalog + Lake Formation",
        "description": (
            "Parquet-converted data with RRD metadata tags. Governed by AWS Lake "
            "Formation (TBAC, column/row-level). EventBridge triggers Raw2Conform."
        ),
    },
    "conform": {
        "label": "EDAP Conform Layer",
        "technology": "Amazon S3 (Parquet) + Amazon Redshift Spectrum + Lake Formation",
        "description": (
            "Unified, curated datasets in canonical form. Exposed as Redshift "
            "Spectrum external tables. Governed by Lake Formation."
        ),
    },
    "datamart": {
        "label": "EDAP DataMart Layer",
        "technology": "Amazon Redshift (RA3)",
        "description": (
            "Dimensional data models for BI and reporting. Populated by "
            "Conform2DataMart Step Functions workflows."
        ),
    },
    "export": {
        "label": "EDAP Export / Analytics Layer",
        "technology": "Amazon Athena / Redshift Data API / API Gateway / Power BI Gateway",
        "description": (
            "Data access for analysts, dashboards, ML workloads and external "
            "consumers. Governed at query time by Lake Formation."
        ),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# EDAP Integration Patterns
# Each pattern captures:
#   - id, name, use_case
#   - trigger_keywords  — terms in project components/connections that activate this pattern
#   - edap_components   — EDAP-side components to inject into diagrams
#   - edap_connections  — connections to inject (from→to with label)
#   - data_flows        — data-flow entries (source, destination, data, protocol)
#   - context_entities  — context diagram additions
#   - layers_touched    — which EDAP layers are involved
#   - aws_services      — AWS services used (for LLD component injection)
#   - mandatory_controls
# ─────────────────────────────────────────────────────────────────────────────

EDAP_PATTERNS: list[dict] = [
    # ─────────────────────────────────────────────────────────────────────────
    # EDAP-INT-01  Source2Ingest – SFTP Push
    # ─────────────────────────────────────────────────────────────────────────
    {
        "id": "EDAP-INT-01",
        "name": "Source2Ingest – SFTP Push",
        "reference": "EDAP AWS Technical Design §6.1",
        "use_case": (
            "Third-party system initiates a file transfer into EDAP using SFTP "
            "(push from external source)"
        ),
        "trigger_keywords": [
            "sftp", "sftp push", "file transfer", "transfer family",
            "ftp", "secure file transfer",
        ],
        "layers_touched": ["ingestion", "raw"],
        "aws_services": [
            {"name": "AWS Transfer Family", "layer": "Network", "technology": "SFTP Server (VPC-hosted, S3 domain)"},
            {"name": "Network Load Balancer", "layer": "Network", "technology": "NLB (port 22, Elastic IPs per AZ)"},
            {"name": "S3 Ingestion Staging", "layer": "Data", "technology": "Amazon S3 (SSE-KMS)"},
            {"name": "S3 Ingestion Cleared", "layer": "Data", "technology": "Amazon S3 (SSE-KMS)"},
            {"name": "Antivirus Scanner", "layer": "Managed", "technology": "Cloud Storage Security (Fargate)"},
            {"name": "EventBridge", "layer": "Managed", "technology": "Amazon EventBridge"},
            {"name": "Step Functions I2R", "layer": "Managed", "technology": "AWS Step Functions"},
            {"name": "AWS KMS", "layer": "Managed", "technology": "AWS KMS (CMK)"},
            {"name": "CloudWatch Logs", "layer": "Managed", "technology": "Amazon CloudWatch"},
        ],
        "edap_components": [
            {"name": "AWS Transfer Family (SFTP)", "layer": "Network", "technology": "AWS Transfer Family"},
            {"name": "EDAP Ingestion Layer", "layer": "Data", "technology": "Amazon S3"},
            {"name": "Antivirus (Cloud Storage Security)", "layer": "Managed", "technology": "ECS Fargate"},
            {"name": "Step Functions (I2R)", "layer": "Managed", "technology": "AWS Step Functions"},
        ],
        "edap_connections": [
            {"from": "Source System", "to": "Network Load Balancer", "label": "SFTP :22 (via Elastic IP)"},
            {"from": "Network Load Balancer", "to": "AWS Transfer Family (SFTP)", "label": "routes to private NIC"},
            {"from": "AWS Transfer Family (SFTP)", "to": "EDAP Ingestion Layer", "label": "S3 PutObject → Staging"},
            {"from": "EDAP Ingestion Layer", "to": "Antivirus (Cloud Storage Security)", "label": "EventBridge: object created"},
            {"from": "Antivirus (Cloud Storage Security)", "to": "EDAP Ingestion Layer", "label": "move to Cleared / Quarantine"},
            {"from": "EDAP Ingestion Layer", "to": "Step Functions (I2R)", "label": "EventBridge: Cleared object"},
        ],
        "data_flows": [
            {"id": "DF-EDAP-01", "source": "Source System", "destination": "AWS Transfer Family (SFTP)", "data": "Source files (any format)", "protocol": "SFTP / TLS"},
            {"id": "DF-EDAP-02", "source": "AWS Transfer Family (SFTP)", "destination": "EDAP Ingestion Layer", "data": "Raw source files", "protocol": "S3 PutObject (SSE-KMS)"},
            {"id": "DF-EDAP-03", "source": "EDAP Ingestion Layer", "destination": "Step Functions (I2R)", "data": "EventBridge notification (S3 object created)", "protocol": "EventBridge"},
        ],
        "context_entities": [
            {"name": "EDAP Platform (UKHSA)", "type": "External System", "interaction": "Receives source files via SFTP and processes to Raw Layer", "direction": "In"},
            {"name": "AWS Transfer Family (SFTP)", "type": "Service", "interaction": "SFTP endpoint for file push", "direction": "In"},
        ],
        "mandatory_controls": [
            "SSE-KMS on Ingestion S3 buckets (Staging and Cleared)",
            "Bucket policy rejects non-KMS uploads",
            "IP filtering at external firewall or Network ACL",
            "Dedicated IAM role per Transfer Family user, scoped to target prefix only",
            "Transfer Family security policy: TransferSecurityPolicy-2020-06",
            "Antivirus scan before Ingestion2Raw processing",
            "CloudTrail data events on Ingestion buckets",
            "CloudWatch Logs for Transfer Family activity (/aws/transfer/<server>)",
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # EDAP-INT-02  Source2Ingest – Pull-Based Ingestion
    # ─────────────────────────────────────────────────────────────────────────
    {
        "id": "EDAP-INT-02",
        "name": "Source2Ingest – Pull-Based Ingestion",
        "reference": "EDAP AWS Technical Design §6.2, §6.3, §6.5, §6.8",
        "use_case": (
            "EDAP pulls data from an external SFTP server, REST API endpoint, "
            "S3 bucket, or web source on a schedule"
        ),
        "trigger_keywords": [
            "sftp pull", "api pull", "rest api", "restapi", "s3 pull", "s3 sync",
            "web scraping", "scraping", "scheduled pull", "appflow", "rclone",
            "pull from", "ingest from", "fetch from",
        ],
        "layers_touched": ["ingestion", "raw"],
        "aws_services": [
            {"name": "ECS Fargate Cluster", "layer": "Private", "technology": "Amazon ECS (Fargate)"},
            {"name": "ECR Repository", "layer": "Managed", "technology": "Amazon ECR (private, scan-on-push)"},
            {"name": "AppConfig", "layer": "Managed", "technology": "AWS AppConfig (versioned JSON)"},
            {"name": "Secrets Manager", "layer": "Managed", "technology": "AWS Secrets Manager"},
            {"name": "EventBridge Scheduler", "layer": "Managed", "technology": "Amazon EventBridge (rules)"},
            {"name": "S3 Ingestion Staging", "layer": "Data", "technology": "Amazon S3 (SSE-KMS)"},
            {"name": "NAT Gateway", "layer": "Public", "technology": "AWS NAT Gateway"},
            {"name": "CloudWatch Logs", "layer": "Managed", "technology": "Amazon CloudWatch"},
        ],
        "edap_components": [
            {"name": "ECS Fargate (Pull Client)", "layer": "Private", "technology": "Amazon ECS Fargate + ECR"},
            {"name": "AppConfig (Pipeline Config)", "layer": "Managed", "technology": "AWS AppConfig"},
            {"name": "Secrets Manager", "layer": "Managed", "technology": "AWS Secrets Manager"},
            {"name": "EDAP Ingestion Layer", "layer": "Data", "technology": "Amazon S3"},
        ],
        "edap_connections": [
            {"from": "EventBridge Scheduler", "to": "ECS Fargate (Pull Client)", "label": "scheduled trigger"},
            {"from": "ECS Fargate (Pull Client)", "to": "AppConfig (Pipeline Config)", "label": "fetch versioned task config"},
            {"from": "ECS Fargate (Pull Client)", "to": "Secrets Manager", "label": "fetch credentials"},
            {"from": "ECS Fargate (Pull Client)", "to": "External Source", "label": "SFTP/HTTPS/S3 pull"},
            {"from": "ECS Fargate (Pull Client)", "to": "EDAP Ingestion Layer", "label": "S3 PutObject → Staging"},
        ],
        "data_flows": [
            {"id": "DF-EDAP-04", "source": "External Source", "destination": "ECS Fargate (Pull Client)", "data": "Source files / API response", "protocol": "SFTP / HTTPS / S3 API"},
            {"id": "DF-EDAP-05", "source": "ECS Fargate (Pull Client)", "destination": "EDAP Ingestion Layer", "data": "Downloaded source files", "protocol": "S3 PutObject (SSE-KMS)"},
        ],
        "context_entities": [
            {"name": "EDAP Platform (UKHSA)", "type": "External System", "interaction": "Pulls source data on schedule and lands in Ingestion Layer", "direction": "In"},
        ],
        "mandatory_controls": [
            "ECR repositories private, images scanned on push",
            "Task IAM role scoped to target S3 prefix only",
            "Credentials only in Secrets Manager — never in AppConfig or task definition",
            "AppConfig configuration versioned",
            "Concurrent executions controlled by EventBridge schedule",
            "All container logs to CloudWatch via awslogs driver",
            "External traffic via NAT Gateway — no public Fargate IPs",
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # EDAP-INT-03  Source2Ingest – Streaming / Event
    # ─────────────────────────────────────────────────────────────────────────
    {
        "id": "EDAP-INT-03",
        "name": "Source2Ingest – Streaming / Event Ingestion",
        "reference": "EDAP AWS Technical Design §6.4, §6.13",
        "use_case": (
            "Continuous streamed records or discrete EventBridge events from a "
            "third-party land directly in the EDAP Raw Layer in near-real-time"
        ),
        "trigger_keywords": [
            "stream", "streaming", "kinesis", "eventbridge event", "event ingestion",
            "real-time", "realtime", "near real-time", "kafka", "mulesoft",
            "firehose", "event bus", "event driven",
        ],
        "layers_touched": ["raw"],
        "aws_services": [
            {"name": "Kinesis Data Firehose", "layer": "Managed", "technology": "Amazon Kinesis Data Firehose"},
            {"name": "Lambda Transformation", "layer": "Private", "technology": "AWS Lambda (RRD tagging + Parquet)"},
            {"name": "EventBridge (cross-account)", "layer": "Managed", "technology": "Amazon EventBridge"},
            {"name": "S3 Raw Layer", "layer": "Data", "technology": "Amazon S3 (Parquet/Snappy, SSE-KMS)"},
            {"name": "AppConfig", "layer": "Managed", "technology": "AWS AppConfig"},
            {"name": "AWS KMS", "layer": "Managed", "technology": "AWS KMS (CMK)"},
            {"name": "CloudWatch Logs", "layer": "Managed", "technology": "Amazon CloudWatch"},
        ],
        "edap_components": [
            {"name": "Kinesis Data Firehose", "layer": "Managed", "technology": "Amazon Kinesis Data Firehose"},
            {"name": "Lambda (RRD + Parquet Transform)", "layer": "Private", "technology": "AWS Lambda"},
            {"name": "EDAP Raw Layer", "layer": "Data", "technology": "Amazon S3 (Parquet)"},
        ],
        "edap_connections": [
            {"from": "Source System", "to": "Kinesis Data Firehose", "label": "Direct PUT / EventBridge rule"},
            {"from": "Kinesis Data Firehose", "to": "Lambda (RRD + Parquet Transform)", "label": "record transformation"},
            {"from": "Lambda (RRD + Parquet Transform)", "to": "EDAP Raw Layer", "label": "Parquet + Snappy (SSE-KMS)"},
            {"from": "Lambda (RRD + Parquet Transform)", "to": "S3 processing-failed", "label": "failed records"},
        ],
        "data_flows": [
            {"id": "DF-EDAP-06", "source": "Source System", "destination": "Kinesis Data Firehose", "data": "Streamed events / records", "protocol": "Kinesis PUT / EventBridge"},
            {"id": "DF-EDAP-07", "source": "Kinesis Data Firehose", "destination": "EDAP Raw Layer", "data": "Parquet records with RRD tags", "protocol": "S3 PutObject (SSE-KMS)"},
        ],
        "context_entities": [
            {"name": "EDAP Platform (UKHSA)", "type": "External System", "interaction": "Receives streamed events and writes to Raw Layer directly", "direction": "In"},
        ],
        "mandatory_controls": [
            "KMS CMK encryption on Firehose queue and target S3 bucket",
            "EventBridge resource policy restricts source accounts",
            "IAM role per stream source scoped to target Firehose only",
            "Record format conversion enabled (output: Parquet, Snappy)",
            "Failed records delivered to S3 processing-failed prefix",
            "CloudWatch alarm on Firehose DeliveryToS3.DataFreshness metric",
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # EDAP-INT-04  Source2Ingest – Azure / Cross-Cloud / Database Migration
    # ─────────────────────────────────────────────────────────────────────────
    {
        "id": "EDAP-INT-04",
        "name": "Source2Ingest – Azure / Cross-Cloud Ingestion",
        "reference": "EDAP AWS Technical Design §6.7, §6.10, §6.12",
        "use_case": (
            "Source data resides in Azure Blob Storage, an external S3 bucket, "
            "or a relational database requiring bulk or incremental migration into EDAP"
        ),
        "trigger_keywords": [
            "azure", "azure blob", "blob storage", "datasync", "data sync",
            "database migration", "dms", "cross-cloud", "cross cloud",
            "external s3", "s3 replication", "s3 sync", "azure object storage",
            "on-prem", "on premises", "on-premises",
        ],
        "layers_touched": ["ingestion", "raw"],
        "aws_services": [
            {"name": "AWS DataSync", "layer": "Managed", "technology": "AWS DataSync (tasks + schedules)"},
            {"name": "DataSync Agent (Azure)", "layer": "internet", "technology": "AWS DataSync Agent (VHD in Azure)"},
            {"name": "AWS DMS", "layer": "Managed", "technology": "AWS Database Migration Service"},
            {"name": "S3 Ingestion Staging", "layer": "Data", "technology": "Amazon S3 (SSE-KMS)"},
            {"name": "IAM Roles (DataSync)", "layer": "Managed", "technology": "AWS IAM"},
            {"name": "CloudWatch Logs", "layer": "Managed", "technology": "Amazon CloudWatch"},
        ],
        "edap_components": [
            {"name": "DataSync Agent (Azure-hosted)", "layer": "internet", "technology": "AWS DataSync Agent VHD"},
            {"name": "AWS DataSync", "layer": "Managed", "technology": "AWS DataSync"},
            {"name": "AWS DMS", "layer": "Managed", "technology": "AWS DMS"},
            {"name": "EDAP Ingestion Layer", "layer": "Data", "technology": "Amazon S3"},
        ],
        "edap_connections": [
            {"from": "Azure Blob Storage", "to": "DataSync Agent (Azure-hosted)", "label": "local read"},
            {"from": "DataSync Agent (Azure-hosted)", "to": "AWS DataSync", "label": "HTTPS outbound to DataSync endpoints"},
            {"from": "AWS DataSync", "to": "EDAP Ingestion Layer", "label": "scheduled sync → Staging"},
            {"from": "External Database", "to": "AWS DMS", "label": "replication task (full-load / CDC)"},
            {"from": "AWS DMS", "to": "EDAP Ingestion Layer", "label": "S3 target → Staging"},
        ],
        "data_flows": [
            {"id": "DF-EDAP-08", "source": "Azure Blob Storage", "destination": "AWS DataSync", "data": "Files / objects", "protocol": "HTTPS (DataSync Agent)"},
            {"id": "DF-EDAP-09", "source": "AWS DataSync", "destination": "EDAP Ingestion Layer", "data": "Synchronised files", "protocol": "S3 PutObject (SSE-KMS)"},
            {"id": "DF-EDAP-10", "source": "External Database", "destination": "EDAP Ingestion Layer", "data": "Table data (full-load / CDC)", "protocol": "AWS DMS → S3"},
        ],
        "context_entities": [
            {"name": "Azure Blob Storage / External DB", "type": "External System", "interaction": "Source data synchronised into EDAP via DataSync or DMS", "direction": "In"},
            {"name": "EDAP Platform (UKHSA)", "type": "External System", "interaction": "Receives cross-cloud data via DataSync Agent or DMS", "direction": "In"},
        ],
        "mandatory_controls": [
            "DataSync Agent deployed as VHD in Azure — no inbound firewall rules required in Azure",
            "DataSync CloudWatch log group with resource policy granting DataSync permissions",
            "IAM roles for DataSync scoped to source/target S3 prefixes",
            "KMS encryption on target S3 bucket",
            "DMS source endpoint credentials in Secrets Manager (read-only DB access only)",
            "CloudTrail data events on Ingestion buckets",
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # EDAP-INT-05  Ingestion2Raw + Raw2Conform Processing Pipeline
    # ─────────────────────────────────────────────────────────────────────────
    {
        "id": "EDAP-INT-05",
        "name": "Ingestion2Raw + Raw2Conform Processing Pipeline",
        "reference": "EDAP AWS Technical Design §8, §8.1, §10",
        "use_case": (
            "File-based ingested data must be validated, quality-checked, "
            "transformed to Parquet, RRD-tagged, and written through Raw to Conform"
        ),
        "trigger_keywords": [
            "i2r", "ingest2raw", "ingestion2raw", "raw2conform", "r2c",
            "parquet", "glue", "data quality", "databrew", "rrd tag",
            "step functions", "processing pipeline", "etl", "transform",
            "conform", "conformed", "lake formation",
        ],
        "layers_touched": ["ingestion", "raw", "conform"],
        "aws_services": [
            {"name": "Step Functions (I2R)", "layer": "Managed", "technology": "AWS Step Functions"},
            {"name": "Lambda (File Format Check)", "layer": "Private", "technology": "AWS Lambda"},
            {"name": "Lambda (Integrity Check)", "layer": "Private", "technology": "AWS Lambda"},
            {"name": "Glue DataBrew Profile Job", "layer": "Managed", "technology": "AWS Glue DataBrew"},
            {"name": "Glue Job (Parquet Transform)", "layer": "Managed", "technology": "AWS Glue (PySpark)"},
            {"name": "Glue Crawler", "layer": "Managed", "technology": "AWS Glue Crawler"},
            {"name": "Glue Data Catalog", "layer": "Managed", "technology": "AWS Glue Data Catalog"},
            {"name": "Lake Formation", "layer": "Managed", "technology": "AWS Lake Formation (TBAC)"},
            {"name": "SQS Lineage Queue", "layer": "Managed", "technology": "Amazon SQS (OpenLineage)"},
            {"name": "AppConfig (Pipeline Config)", "layer": "Managed", "technology": "AWS AppConfig"},
            {"name": "S3 Raw Layer", "layer": "Data", "technology": "Amazon S3 (Parquet/Snappy, SSE-KMS)"},
            {"name": "S3 Conform Layer", "layer": "Data", "technology": "Amazon S3 (Parquet, SSE-KMS)"},
            {"name": "Redshift Spectrum", "layer": "Data", "technology": "Amazon Redshift (RA3, Spectrum)"},
            {"name": "DynamoDB (Sync State)", "layer": "Managed", "technology": "Amazon DynamoDB"},
        ],
        "edap_components": [
            {"name": "Step Functions (I2R Workflow)", "layer": "Managed", "technology": "AWS Step Functions"},
            {"name": "Glue Job (Parquet + RRD Tag)", "layer": "Managed", "technology": "AWS Glue (PySpark)"},
            {"name": "Glue DataBrew (Quality)", "layer": "Managed", "technology": "AWS Glue DataBrew"},
            {"name": "EDAP Raw Layer", "layer": "Data", "technology": "Amazon S3 (Parquet)"},
            {"name": "Lake Formation", "layer": "Managed", "technology": "AWS Lake Formation"},
            {"name": "EDAP Conform Layer", "layer": "Data", "technology": "Amazon S3 + Redshift Spectrum"},
        ],
        "edap_connections": [
            {"from": "EDAP Ingestion Layer", "to": "Step Functions (I2R Workflow)", "label": "EventBridge: S3 Cleared object"},
            {"from": "Step Functions (I2R Workflow)", "to": "Glue DataBrew (Quality)", "label": "data quality profile"},
            {"from": "Step Functions (I2R Workflow)", "to": "Glue Job (Parquet + RRD Tag)", "label": "transform to Parquet + tag"},
            {"from": "Glue Job (Parquet + RRD Tag)", "to": "EDAP Raw Layer", "label": "write Parquet (Snappy, SSE-KMS)"},
            {"from": "EDAP Raw Layer", "to": "Lake Formation", "label": "register + TBAC grants"},
            {"from": "EDAP Raw Layer", "to": "EDAP Conform Layer", "label": "R2C: Step Functions → Glue → Conform"},
            {"from": "Step Functions (I2R Workflow)", "to": "SQS Lineage Queue", "label": "OpenLineage START/END messages"},
        ],
        "data_flows": [
            {"id": "DF-EDAP-11", "source": "EDAP Ingestion Layer", "destination": "Glue Job (Parquet + RRD Tag)", "data": "Raw files (any format)", "protocol": "S3 GetObject"},
            {"id": "DF-EDAP-12", "source": "Glue Job (Parquet + RRD Tag)", "destination": "EDAP Raw Layer", "data": "Parquet files with RRD metadata columns", "protocol": "S3 PutObject (SSE-KMS)"},
            {"id": "DF-EDAP-13", "source": "EDAP Raw Layer", "destination": "EDAP Conform Layer", "data": "Curated Parquet datasets", "protocol": "Glue Job (PySpark)"},
        ],
        "context_entities": [
            {"name": "EDAP Processing Pipeline", "type": "Internal System", "interaction": "Transforms ingested data through Raw and Conform layers with quality checks and RRD tagging", "direction": "Both"},
        ],
        "mandatory_controls": [
            "SSE-KMS on Raw and Conform S3 buckets",
            "Bucket policy rejects non-KMS uploads",
            "RRD columns on all Parquet writes: SourceSystemId (S-XXXXXXXX), DataPipelineId (P-XXXXXXXX), VisibilityCode (default V-ZZZZZZ)",
            "Glue DataBrew quality failure halts pipeline and raises CloudWatch alarm",
            "OpenLineage messages emitted to SQS on every pipeline START and END",
            "Lake Formation TBAC (Tag-Based Access Control) on all Raw and Conform tables",
            "EventBridge filters error prefixes to prevent reprocessing loops",
            "Glue continuous logging to CloudWatch (/aws-glue/jobs/logs-v2)",
            "All Lambda and Glue Jobs use VPC interfaces; S3 via Gateway VPC Endpoint",
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    # EDAP-INT-06  Analytics Access, Virtualisation and Export
    # ─────────────────────────────────────────────────────────────────────────
    {
        "id": "EDAP-INT-06",
        "name": "Analytics Access, Virtualisation and Export",
        "reference": "EDAP AWS Technical Design §14, §15, §16, §17, §18.6",
        "use_case": (
            "Data scientists, BI dashboards, ML pipelines or external consumers "
            "need to query, visualise, or export data from EDAP layers"
        ),
        "trigger_keywords": [
            "analytics", "reporting", "dashboard", "powerbi", "power bi",
            "quicksight", "athena", "redshift", "data virtualisation",
            "data virtualization", "sagemaker", "workspace", "ml", "machine learning",
            "export", "api access", "data science", "consume", "consumer",
        ],
        "layers_touched": ["conform", "datamart", "export"],
        "aws_services": [
            {"name": "Amazon Athena", "layer": "Managed", "technology": "Amazon Athena (Workgroup per user)"},
            {"name": "Redshift Data API", "layer": "Managed", "technology": "Amazon Redshift (RA3, Data API)"},
            {"name": "Lake Formation", "layer": "Managed", "technology": "AWS Lake Formation (fine-grained)"},
            {"name": "Power BI Gateway", "layer": "Private", "technology": "EC2 Windows (≥2 instances, multi-AZ)"},
            {"name": "SageMaker Notebooks", "layer": "Private", "technology": "Amazon SageMaker (VPC-only domain)"},
            {"name": "Amazon WorkSpaces", "layer": "Private", "technology": "Amazon WorkSpaces (separate VPC, AD Connector)"},
            {"name": "API Gateway", "layer": "Public", "technology": "Amazon API Gateway + Route53"},
            {"name": "Amazon QuickSight", "layer": "Managed", "technology": "Amazon QuickSight Enterprise"},
            {"name": "Step Functions (Export Flow)", "layer": "Managed", "technology": "AWS Step Functions"},
            {"name": "Kinesis Data Streams (Export)", "layer": "Managed", "technology": "Amazon Kinesis Data Streams (SSE-KMS)"},
        ],
        "edap_components": [
            {"name": "Amazon Athena", "layer": "Managed", "technology": "Amazon Athena"},
            {"name": "Amazon Redshift (DataMart)", "layer": "Data", "technology": "Amazon Redshift RA3"},
            {"name": "Power BI Gateway (EC2)", "layer": "Private", "technology": "EC2 Windows + Power BI"},
            {"name": "EDAP DataMart Layer", "layer": "Data", "technology": "Amazon Redshift"},
            {"name": "API Gateway (Export)", "layer": "Public", "technology": "Amazon API Gateway"},
        ],
        "edap_connections": [
            {"from": "Data Analyst (Azure AD)", "to": "Amazon Athena", "label": "JDBC/ODBC + Azure AD federation + MFA"},
            {"from": "Amazon Athena", "to": "EDAP Conform Layer", "label": "Lake Formation TBAC → S3 Parquet"},
            {"from": "Power BI Gateway (EC2)", "to": "Amazon Redshift (DataMart)", "label": "direct VPC connection (read-only)"},
            {"from": "Power BI Gateway (EC2)", "to": "Amazon Athena", "label": "VPC Endpoint (Athena Interface)"},
            {"from": "API Gateway (Export)", "to": "Amazon Redshift (DataMart)", "label": "Redshift Data API"},
        ],
        "data_flows": [
            {"id": "DF-EDAP-14", "source": "EDAP Conform Layer", "destination": "Amazon Athena", "data": "Parquet datasets via Glue Catalog", "protocol": "Athena SQL (VPC Endpoint)"},
            {"id": "DF-EDAP-15", "source": "EDAP DataMart Layer", "destination": "Power BI Gateway (EC2)", "data": "Query results", "protocol": "Redshift JDBC (private VPC)"},
            {"id": "DF-EDAP-16", "source": "EDAP DataMart Layer", "destination": "API Gateway (Export)", "data": "Structured export data", "protocol": "Redshift Data API / HTTPS"},
        ],
        "context_entities": [
            {"name": "Data Analysts / Scientists (UKHSA)", "type": "User", "interaction": "Query and analyse EDAP data via Athena, Redshift, SageMaker", "direction": "Out"},
            {"name": "Power BI Service (Microsoft)", "type": "External System", "interaction": "Connects to Power BI Gateway for dashboard data", "direction": "Both"},
            {"name": "External API Consumer", "type": "External System", "interaction": "Accesses export data via API Gateway + Redshift Data API", "direction": "Out"},
        ],
        "mandatory_controls": [
            "Athena per-user Workgroup with dedicated S3 query results bucket (SSE-KMS)",
            "Lake Formation fine-grained access enforced for all Athena and Redshift Spectrum queries",
            "Azure AD federated to AWS IAM for all human access; MFA enforced",
            "Power BI Gateway RDP access restricted by Security Group (no public RDP)",
            "Redshift not internet-facing (private subnets only)",
            "Redshift audit logs (connection + user-activity) to CloudWatch",
            "API Gateway with Route53 for Export REST API; IAM auth or Cognito",
            "QuickSight Enterprise enabled; VPC connection for Redshift/Athena",
            "SageMaker Notebooks in VPC-only domain; VPC Endpoints for all AWS API calls",
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# EDAP Global Architecture Context
# (always injected when any EDAP pattern is detected)
# ─────────────────────────────────────────────────────────────────────────────

EDAP_GLOBAL_CONTEXT = {
    "principles": [
        "Prefer Native AWS Services",
        "Prefer Serverless",
        "Soft Infrastructure (Terraform, Immutable)",
        "Multi-AZ — eu-west-2 only",
        "Open File Formats (Parquet, JSON, CSV)",
        "All traffic via VPC Endpoints — no public S3 access",
        "SSE-KMS encryption on all storage",
        "Least-privilege IAM — scoped to prefix, not bucket",
        "OpenLineage messages emitted on all pipeline START/END",
        "Lake Formation TBAC for all data layer access",
    ],
    "account_config": [
        "GuardDuty enabled (exports to S3 every 15 min, KMS-encrypted)",
        "AWS Macie enabled",
        "AWS Config enabled",
        "AWS Trusted Advisor enabled",
        "CloudTrail (Management + Data events: S3, Lambda, DynamoDB, Lake Formation)",
        "QuickSight Enterprise enabled",
        "Cost allocation tags enabled",
    ],
    "vpc_config": {
        "region": "eu-west-2",
        "multi_az": True,
        "subnet_types": ["private", "public"],
        "s3_gateway_endpoint": True,
        "nat_gateway": True,
        "internet_gateway": True,
        "service_endpoints": ["ECR", "Secrets Manager", "AppConfig", "Athena", "Step Functions"],
    },
    "identity": {
        "idp": "UKHSA Azure Active Directory (Entra ID)",
        "aws_integration": "AWS IAM Federation (SAML 2.0) + AD Connector for WorkSpaces",
        "mfa": "Enforced for all human accounts at IdP level",
        "workspaces_auth": "AD Connector → HALO AAD (trust with UKHSA AAD)",
    },
    "data_governance": {
        "lineage": "OpenLineage format → SQS Lineage Queue → Data Governance Tool",
        "catalogue": "AWS Glue Data Catalog → imported to Data Governance Tool",
        "quality": "AWS Glue DataBrew Profile Jobs → S3 → Data Governance Tool",
        "pii": "AWS Macie + SageMaker models for PII tagging",
        "access": "AWS Lake Formation (TBAC, column/row grants)",
    },
    "monitoring": {
        "security": "CloudTrail + CloudWatch + GuardDuty + AWS Config + Trusted Advisor",
        "application": "CloudWatch Logs + OpenLineage messages + Glue job metrics",
        "infrastructure": "CloudWatch metrics (Redshift focus) + Redshift Performance Insights",
        "data": "Glue DataBrew quality/profiling + AWS Macie (PII)",
    },
    "encryption": {
        "at_rest": "SSE-KMS (Customer Managed Key) on all S3 buckets, Kinesis streams, CloudWatch Log Groups",
        "in_transit": "TLS enforced on all endpoints; TransferSecurityPolicy-2020-06 for SFTP",
    },
    "cicd": {
        "platform": "Azure DevOps + GitHub (HALO)",
        "iac": "Terraform (all infrastructure — immutable, no manual provisioning)",
        "containers": "Amazon ECR (private, scan-on-push)",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Pattern Detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_edap_patterns(
    components: list[dict],
    connections: list[dict],
    dataflows: list[dict],
    context_entities: list[dict],
    explicit_pattern_ids: list[str] | None = None,
) -> list[dict]:
    """
    Detect which EDAP integration patterns apply to a project.

    Matches are based on keyword scanning of project input data.  Any pattern
    whose trigger_keywords appear in the aggregated text is returned.

    Parameters
    ----------
    components, connections, dataflows, context_entities :
        Parsed project input tables from the HLD Confluence page.
    explicit_pattern_ids :
        Optional list of pattern IDs (e.g. ["EDAP-INT-01", "EDAP-INT-03"]) to
        force-include regardless of keyword detection.  Use when the HLD author
        has explicitly selected patterns in Section 8.

    Returns
    -------
    List of matching EDAP pattern dicts (subset of EDAP_PATTERNS).
    """
    # Build a single lowercase text corpus from all project inputs
    corpus_parts = []
    for record in components:
        corpus_parts.extend(str(v) for v in record.values())
    for record in connections:
        corpus_parts.extend(str(v) for v in record.values())
    for record in dataflows:
        corpus_parts.extend(str(v) for v in record.values())
    for record in context_entities:
        corpus_parts.extend(str(v) for v in record.values())
    corpus = " ".join(corpus_parts).lower()

    matched = []
    seen_ids = set()

    # Force-include explicitly requested patterns first
    if explicit_pattern_ids:
        for pid in explicit_pattern_ids:
            for pattern in EDAP_PATTERNS:
                if pattern["id"] == pid and pid not in seen_ids:
                    matched.append(pattern)
                    seen_ids.add(pid)

    # Keyword-based detection
    for pattern in EDAP_PATTERNS:
        if pattern["id"] in seen_ids:
            continue
        if any(kw in corpus for kw in pattern["trigger_keywords"]):
            matched.append(pattern)
            seen_ids.add(pattern["id"])

    return matched


def inject_edap_into_components(
    components: list[dict],
    patterns: list[dict],
) -> list[dict]:
    """
    Merge EDAP AWS service components into a project's component list.

    Deduplicates by component name.  EDAP components are appended after
    existing project components so they don't interfere with existing ordering.
    """
    existing_names = {c["name"].lower() for c in components}
    result = list(components)
    for pattern in patterns:
        for svc in pattern.get("aws_services", []):
            if svc["name"].lower() not in existing_names:
                result.append({
                    "no": "",
                    "name": svc["name"],
                    "layer": svc.get("layer", "Managed"),
                    "technology": svc.get("technology", ""),
                    "direction": "",
                    "description": f"[EDAP {pattern['id']}] {pattern['name']}",
                })
                existing_names.add(svc["name"].lower())
    return result


def inject_edap_into_connections(
    connections: list[dict],
    patterns: list[dict],
) -> list[dict]:
    """
    Merge EDAP connection edges into a project's connection list.
    Deduplicates by (from, to) pair.
    """
    existing = {(c["from"].lower(), c["to"].lower()) for c in connections}
    result = list(connections)
    for pattern in patterns:
        for conn in pattern.get("edap_connections", []):
            key = (conn["from"].lower(), conn["to"].lower())
            if key not in existing:
                result.append(conn)
                existing.add(key)
    return result


def inject_edap_into_dataflows(
    dataflows: list[dict],
    patterns: list[dict],
) -> list[dict]:
    """Merge EDAP data-flow entries into a project's data-flow list."""
    existing_ids = {d.get("id", "").lower() for d in dataflows if d.get("id")}
    result = list(dataflows)
    for pattern in patterns:
        for flow in pattern.get("data_flows", []):
            if flow.get("id", "").lower() not in existing_ids:
                result.append(flow)
                existing_ids.add(flow.get("id", "").lower())
    return result


def inject_edap_into_context_entities(
    entities: list[dict],
    patterns: list[dict],
) -> list[dict]:
    """Merge EDAP context entities into a project's context entity list."""
    existing = {e["name"].lower() for e in entities}
    result = list(entities)
    for pattern in patterns:
        for entity in pattern.get("context_entities", []):
            if entity["name"].lower() not in existing:
                result.append(entity)
                existing.add(entity["name"].lower())
    return result


def build_edap_integration_summary(patterns: list[dict]) -> str:
    """Return a short human-readable summary of detected EDAP patterns."""
    if not patterns:
        return "No EDAP integration patterns detected."
    lines = ["EDAP Integration Patterns Detected:"]
    for p in patterns:
        lines.append(f"  [{p['id']}] {p['name']} — layers: {', '.join(p['layers_touched'])}")
    return "\n".join(lines)
