# AWS Services Icons Reference
## Complete LLD Diagram Support

### Overview
This document lists all 40+ AWS services now supported with professional SVG icons in architecture diagrams generated for Low-Level Design (LLD) documentation.

---

## **COMPUTE SERVICES** 🟠 (Orange)

| Service | Icon Name | Keywords | Use Case |
|---------|-----------|----------|----------|
| API Gateway | `API Gateway` | api, gateway | REST/HTTP API endpoints |
| Lambda | `Lambda` | lambda, serverless | Serverless functions |
| EC2 | `EC2` | ec2, instance, vm | Virtual machines |
| ECS | `ECS` | ecs, container, docker | Container orchestration |
| EKS | `EKS` | eks, kubernetes, k8s | Kubernetes clusters |
| Fargate | `Fargate` | fargate, serverless-containers | Serverless containers |
| App Runner | `AppRunner` | apprunner, app-runner | Managed application hosting |

---

## **DATABASE SERVICES** 🔵 (Blue)

| Service | Icon Name | Keywords | Use Case |
|---------|-----------|----------|----------|
| RDS | `RDS` | rds, sql, relational | Managed SQL databases |
| Aurora | `Aurora` | aurora, mysql, postgresql | Cloud-native SQL |
| DynamoDB | `DynamoDB` | dynamodb, nosql, table | NoSQL/DynamoDB tables |
| ElastiCache | `ElastiCache` | elasticache, redis, cache | In-memory caching |
| Neptune | `Neptune` | neptune, graph | Graph databases |
| DocumentDB | `DocumentDB` | documentdb, mongodb, document | Document databases |
| Redshift | `Redshift` | redshift, warehouse, analytics | Data warehouse |

---

## **STORAGE SERVICES** 🟢 (Green)

| Service | Icon Name | Keywords | Use Case |
|---------|-----------|----------|----------|
| S3 | `S3` | s3, bucket, storage, file | Object storage |
| EBS | `EBS` | ebs, volume, block | Block storage volumes |
| EFS | `EFS` | efs, filesystem | Elastic file system |
| Glacier | `Glacier` | glacier, archive | Long-term archival |
| FSx | `FSx` | fsx, file-server | Managed file servers |

---

## **NETWORKING SERVICES** 🔵 (Blue)

| Service | Icon Name | Keywords | Use Case |
|---------|-----------|----------|----------|
| CloudFront | `CloudFront` | cloudfront, cdn, distribution | Content delivery network |
| VPC | `VPC` | vpc, network, virtual | Virtual private cloud |
| ALB | `ALB` | alb, load-balancer, application | Application load balancer |
| NLB | `NLB` | nlb, network-lb | Network load balancer |
| Route 53 | `Route53` | route53, dns, hosted-zone | DNS management |
| Direct Connect | `DirectConnect` | directconnect, dx, connection | Dedicated network connection |
| VPN | `VPN` | vpn, connection | Virtual private network |
| NAT Gateway | `NAT Gateway` | nat, nat-gateway | Network address translation |
| Elastic IP | `Elastic IP` | eip, elastic-ip | Static IP address |

---

## **INTEGRATION SERVICES** 🟠 (Orange)

| Service | Icon Name | Keywords | Use Case |
|---------|-----------|----------|----------|
| SQS | `SQS` | sqs, queue, message | Message queuing |
| SNS | `SNS` | sns, notification, topic | Pub/Sub notifications |
| EventBridge | `EventBridge` | eventbridge, events, bus | Event routing & processing |
| Kinesis | `Kinesis` | kinesis, stream, data | Real-time data streaming |
| AppSync | `AppSync` | appsync, graphql | GraphQL API service |
| Cognito | `Cognito` | cognito, auth, authentication | User identity & auth |

---

## **SECURITY & MONITORING SERVICES** 🟠 (Orange)

| Service | Icon Name | Keywords | Use Case |
|---------|-----------|----------|----------|
| CloudWatch | `CloudWatch` | cloudwatch, monitoring, logs | Monitoring & logging |
| X-Ray | `X-Ray` | x-ray, xray, tracing | Distributed tracing |
| CloudTrail | `CloudTrail` | cloudtrail, audit, logging | Audit logging |
| KMS | `KMS` | kms, encryption, key-management | Encryption key management |
| Secrets Manager | `SecretsManager` | secretsmanager, secrets | Secret storage |
| IAM | `IAM` | iam, identity, roles | Identity & access management |
| WAF | `WAF` | waf, firewall, protection | Web application firewall |

---

## **ANALYTICS & BI SERVICES** 🟠 (Orange)

| Service | Icon Name | Keywords | Use Case |
|---------|-----------|----------|----------|
| Athena | `Athena` | athena, query, sql | SQL queries on S3 |
| QuickSight | `QuickSight` | quicksight, bi, dashboard | Business intelligence |
| Glue | `Glue` | glue, etl, data-catalog | ETL & data catalog |
| EMR | `EMR` | emr, hadoop, spark | Big data processing |

---

## **MACHINE LEARNING SERVICES** 🟠 (Orange)

| Service | Icon Name | Keywords | Use Case |
|---------|-----------|----------|----------|
| SageMaker | `SageMaker` | sagemaker, ml, machine-learning | ML model training/hosting |

---

## **CONTAINER & REGISTRY SERVICES** 🟠 (Orange)

| Service | Icon Name | Keywords | Use Case |
|---------|-----------|----------|----------|
| ECR | `ECR` | ecr, registry, container-registry | Container image registry |

---

## **DEVELOPER TOOLS SERVICES** 🟠 (Orange)

| Service | Icon Name | Keywords | Use Case |
|---------|-----------|----------|----------|
| CodeBuild | `CodeBuild` | codebuild, build, ci | Build automation |
| CodePipeline | `CodePipeline` | codepipeline, ci/cd, pipeline | CI/CD pipeline orchestration |

---

## **USAGE IN CONFLUENCE HLD TABLES**

When filling in the **Architecture Components** table in your HLD page, use the **Technology** column with any of the keywords listed above:

### Example:

| No | Component Name | Layer | Technology | Description |
|----|---|---|---|---|
| 1 | API Layer | Application | API Gateway | REST endpoints |
| 2 | Auth | Application | Cognito | User authentication |
| 3 | Processing | Application | Lambda | Event processors |
| 4 | Data Store | Data | RDS Aurora | PostgreSQL database |
| 5 | Cache | Data | ElastiCache Redis | Session caching |
| 6 | Files | Data | S3 | File storage |
| 7 | CDN | Edge | CloudFront | Content delivery |
| 8 | Network | Network | VPC | Isolated network |
| 9 | Monitoring | Platform | CloudWatch | Logs & metrics |
| 10 | Security | Platform | KMS | Encryption keys |

---

## **AUTO-ICON MATCHING LOGIC**

The system automatically matches:
- Service names (case-insensitive)
- Common abbreviations (e.g., "ECS" → ECS container service)
- Descriptive keywords (e.g., "cache" → ElastiCache, "queue" → SQS)

### Example Matches:
```
"lambda" → Lambda icon
"api gateway" → API Gateway icon
"rds aurora" → RDS icon
"nosql" → DynamoDB icon
"kubernetes" → EKS icon
"auth" → Cognito icon
"load balancer" → ALB icon
```

---

## **DIAGRAM GENERATION WORKFLOW**

1. **Fill HLD Table** - Enter components with Technology field using AWS service names
2. **Run Script** - `python confluence_update_diagrams.py`
3. **Get Icons** - System matches technology to icons automatically
4. **Upload Diagrams** - Professional AWS icon diagrams created
5. **Embed in Confluence** - Diagrams appear on Architecture Diagrams page

---

## **SUPPORTED DIAGRAM TYPES**

### 1. **Solution Architecture Diagram**
Shows all HLD components with AWS icons organized by layer:
- **Edge Layer** (Orange): CDN, external services
- **Network Layer** (Blue): VPC, load balancers, networking
- **Platform Layer** (Orange): Monitoring, security
- **Application Layer** (Light Blue): APIs, compute, services
- **Data Layer** (Blue): Databases, storage, caching

### 2. **Authentication Flow Diagram**
Visualizes OAuth2/Cognito authentication flows:
- User → WebApp → API → Cognito → Service → Database

### 3. **Network Segregation Diagram**
Shows VPC architecture:
- Internet Gateway
- Public/Private/Data subnets
- Security groups
- Service routing

### 4. **Data Flow Diagram**
Shows data movement between components

### 5. **Logical View Diagram**
Application architecture and dependencies

### 6. **Context View Diagram**
System context and external entities

### 7. **Dataset Relationship Diagram**
Data model and entity relationships

---

## **CUSTOMIZATION**

To add custom services or modify icons:

Edit `aws_architecture_diagram_generator.py`:

```python
# Add to AWS_SERVICE_ICONS dictionary:
"MyService": "data:image/svg+xml;base64,<svg>...</svg>",

# Add to SERVICE_TO_ICON mapping:
"myservice": "MyService",
"my-service": "MyService",
```

---

## **BEST PRACTICES**

### For LLD Documentation:
✅ Use 2-4 word component names
✅ Match technology to actual AWS service
✅ Keep descriptions brief (< 50 chars)
✅ Use consistent naming conventions
✅ Layer components correctly (Edge→Network→Platform→Application→Data)

### Component Naming:
✅ "API Layer" (clear, specific)
❌ "API" (too vague)
✅ "RDS Aurora DB" (specific)
❌ "Database" (too generic)
✅ "Lambda Processors" (clear purpose)
❌ "Lambda" (vague)

---

## **EXAMPLE LLD WITH ALL SERVICES**

```
┌─ CloudFront (Edge) ─────────────────────────┐
│  ↓                                             │
├─ VPC (Network) ───────────────────────────────┤
│  ├─ ALB (load balancer)                       │
│  ├─ ECS (microservices)                       │
│  ├─ Lambda (serverless)                       │
│  └─ NAT Gateway (egress)                      │
│                                                │
│  Data Layer:                                   │
│  ├─ RDS Aurora (relational DB)                │
│  ├─ DynamoDB (NoSQL)                          │
│  ├─ ElastiCache (redis cache)                │
│  ├─ S3 (storage)                              │
│  ├─ EFS (file system)                         │
│  └─ Glacier (archives)                        │
│                                                │
│  Integration:                                  │
│  ├─ SQS (message queue)                       │
│  ├─ SNS (notifications)                       │
│  ├─ EventBridge (event routing)              │
│  ├─ Kinesis (streaming)                       │
│  └─ AppSync (GraphQL)                         │
│                                                │
│  Security/Monitoring:                          │
│  ├─ Cognito (authentication)                  │
│  ├─ KMS (encryption)                          │
│  ├─ IAM (access control)                      │
│  ├─ CloudWatch (monitoring)                   │
│  ├─ X-Ray (tracing)                           │
│  └─ CloudTrail (audit)                        │
│                                                │
│  Analytics:                                    │
│  ├─ Athena (SQL queries)                      │
│  ├─ Glue (ETL)                                │
│  ├─ QuickSight (BI)                           │
│  └─ EMR (big data)                            │
│                                                │
│  ML:                                           │
│  └─ SageMaker (ML models)                     │
│                                                │
│  DevOps:                                       │
│  ├─ ECR (container registry)                  │
│  ├─ CodeBuild (CI)                            │
│  └─ CodePipeline (CD)                         │
└─────────────────────────────────────────────────┘
```

---

## **QUICK REFERENCE - ICON COLORS**

| Color | Services | Use For |
|-------|----------|---------|
| 🟠 Orange (#FF9900) | Compute, Integration, Analytics, Tools | Application & processing layer |
| 🔵 Blue (#2262FF) | Database, Networking, Security | Data & infrastructure layer |
| 🟢 Green (#328237) | Storage | Persistent data layer |

---

**Last Updated:** May 2026
**Total Services Supported:** 40+
**Diagram Types:** 7
**Automatic Icon Matching:** ✅ Enabled
