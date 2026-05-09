# Enhanced Diagram Generation Guide

## What's New

You now have **enhanced diagram generation** that creates professional AWS architecture diagrams with:

✅ **AWS service icons** (Lambda, RDS, API Gateway, CloudFront, etc.)  
✅ **Authentication flow diagrams** (OAuth2 OIDC token exchanges)  
✅ **Network segregation diagrams** (VPC, subnets, security groups)  
✅ **Detailed data flow annotations** (step-by-step with protocols)  

---

## New Diagram Types (Automatically Generated)

### 1. **AWS Solution Architecture with Icons**
**What it shows:**
- Each service with its AWS icon
- Color-coded by layer (Edge/Network/Platform/Application/Data)
- Directional arrows with step labels
- Technology names and descriptions

**Example services recognized:**
- `CloudFront`, `API Gateway`, `Lambda`, `RDS`, `DynamoDB`, `S3`, `Cognito`, `EKS`, etc.

**Data input from HLD tables:**
- Architecture Components (name, layer, technology, description)
- Architecture Connections (from → to → step label)

**Output file:** `solution-architecture.drawio`

---

### 2. **Authentication Flow Diagram**
**What it shows:**
- 13-step OAuth2/OIDC authentication sequence
- User → Web App → API Gateway → Identity Provider (Cognito/Entra ID) → Service → Database
- Each step numbered and labeled

**Steps illustrated:**
```
Step 1:  User clicks Login
Step 2:  Redirect to Identity Provider
Step 3:  Authenticate credentials
Step 4:  Return auth code
Step 5:  Exchange code for access token
Step 6:  Return access token
Step 7:  API call with Bearer token
Step 8:  Token validation at gateway
Step 9:  Route to business service
Step 10: Query authorized data
Step 11: Return data
Step 12: Response to app
Step 13: Render secure UI
```

**Data input:** Auto-generated (no HLD table needed)

**Output file:** `authentication-flow-diagram.drawio`

---

### 3. **Network Segregation Diagram**
**What it shows:**
- Internet boundary
- Internet Gateway (IGW)
- VPC with subnets (public/private/data)
- Security groups with port ranges (80, 443, 3306, 5432, 6379, etc.)
- Component placement (ALB in public, EKS in private, RDS in data)
- Network routing paths

**Layers illustrated:**
```
┌─ Internet (0.0.0.0/0)
   ├─ Internet Gateway
   │  ├─ Public Subnet (10.0.1.0/24)
   │  │  └─ ALB (ports 80, 443)
   │  ├─ Private Subnet (10.0.2.0/24)
   │  │  └─ EKS Cluster (ports 6443, 8080)
   │  └─ Data Subnet (10.0.3.0/24)
   │     ├─ RDS Aurora (port 3306 TLS)
   │     └─ ElastiCache (port 6379 TLS)
```

**Data input:** Auto-generated (no HLD table needed)

**Output file:** `network-segregation-diagram.drawio`

---

## How to Use

### Step 1: Fill HLD Page Tables (Only for Solution Architecture)

Fill these tables on your HLD Confluence page:

**Architecture Components**
| No | Name | Layer | Technology | Description |
|----|------|-------|---|---|
| 1 | CloudFront WAF | Edge | CloudFront | Global CDN with WAF |
| 2 | API Gateway | Network | API Gateway | API routing and throttling |
| 3 | Lambda | Application | Lambda | Serverless compute |
| 4 | RDS Aurora | Data | RDS | PostgreSQL database |

**Architecture Connections**
| From Component | To Component | Connection Label |
|---|---|---|
| CloudFront WAF | API Gateway | Step 1: HTTPS 443 |
| API Gateway | Lambda | Step 2: Invoke function |
| Lambda | RDS Aurora | Step 3: Query database |

**Data Flow Entries**
| ID | Source | Destination | Data | Protocol |
|----|--------|-------------|------|----------|
| DF-1 | CloudFront WAF | API Gateway | HTTPS request | TLS 1.2 |
| DF-2 | API Gateway | Lambda | JSON payload | HTTPS |
| DF-3 | Lambda | RDS Aurora | SQL query | TLS |

### Step 2: Run Generator

```powershell
cd "C:\Users\Tharani.SebiGeorge\OneDrive - UK Health Security Agency\Desktop\Enterprise - Architecture"
.\.venv\Scripts\Activate.ps1
python confluence_update_diagrams.py
```

### Step 3: Review Output

Two locations:

**Confluence (Live):**
- Page: "Architecture Diagrams"
- You'll see 8 embedded diagrams:
  1. Solution Architecture (with AWS icons)
  2. Logical View
  3. Data Flow Diagram
  4. Dataset Relationship
  5. Context View
  6. **Authentication Flow** ← NEW
  7. **Network Segregation** ← NEW
  8. AWS-enhanced Solution Architecture ← NEW

**Local Files (Editable):**
```
output/generated/
├── solution-architecture.drawio
├── authentication-flow-diagram.drawio
├── network-segregation-diagram.drawio
├── data-flow-diagram.drawio
├── logical-view-diagram.drawio
├── context-view-diagram.drawio
├── data-relationship-diagram.drawio
└── [others]
```

Open any `.drawio` file in:
- Confluence (inline editor)
- [draw.io desktop](https://www.draw.io)
- VS Code (with Draw.io extension)

---

## Example: Full Option 1 AWS Workflow

### Your HLD Page Inputs:

**Architecture Components (from earlier template):**
- CloudFront WAF (Edge)
- API Gateway (Network)
- Identity Provider (Platform)
- Core Business API (Application)
- Transaction Store (Data)
- etc. [14 total]

**Architecture Connections (from earlier template):**
- CloudFront WAF → API Gateway: "Step 1: Inbound HTTPS 443"
- API Gateway → Identity Provider: "Step 2: OAuth2 token"
- API Gateway → Core Business API: "Step 3: Policy validated"
- etc. [12 total]

### Generated Output:

1. **Solution Architecture Diagram**
   - Each component has AWS icon
   - Layer color bands (orange edges, blue network, green platform, blue app, orange data)
   - Arrows labeled with step numbers
   - Shows technology stack

2. **Authentication Flow Diagram**
   - Shows how CloudFront → API → Cognito validates user
   - Token exchange visible
   - Service-to-database call shows authorized data access

3. **Network Segregation Diagram**
   - Internet → IGW routing
   - Public subnet has CloudFront endpoint
   - Private subnet has API/Lambda
   - Data subnet has RDS with TLS 3306
   - Security group rules shown

---

## Customization

### Add More Services to AWS Icon Mapping

Edit `enhanced_diagram_generator.py`:

```python
SERVICE_TO_ICON_TYPE = {
    "dynamodb": "DynamoDB",
    "elasticache": "Cache",
    "msk": "MSK",
    # Add yours...
}
```

### Modify Authentication Steps

Edit the `generate_authentication_flow_diagram()` function to add/remove OAuth steps or swap identity providers.

### Adjust Network CIDR Ranges

Edit network segregation diagram to use your actual VPC/subnet CIDR blocks (currently 10.0.0.0/16).

---

## FAQ

**Q: Do I need to fill all HLD tables?**  
A: No. Solution Architecture needs Components + Connections. Authentication Flow and Network Segregation auto-generate.

**Q: Can I edit diagrams in Confluence?**  
A: Yes! Click the diagram → draw.io editor opens inline. Changes persist to attachment.

**Q: How do I update diagrams after changing HLD?**  
A: Edit HLD tables, run script again. Old diagrams are replaced.

**Q: What if my service isn't recognized?**  
A: Add to `SERVICE_TO_ICON_TYPE` dict in `enhanced_diagram_generator.py`, or use generic technology field and it will render as styled box.

**Q: Can I use Azure/GCP icons instead?**  
A: Yes! Modify `AWS_ICON_URLS` dict to use Azure/GCP icon URLs from their documentation sites.

---

## Next Steps

1. **First test:** Use Option 1 AWS data from earlier email
2. **Fill HLD tables** in Confluence
3. **Run script** to generate all 8 diagrams
4. **Review** Confluence Architecture Diagrams page
5. **Export .drawio files** for offline edits or presentations
6. **Customize** legend, step counts, or CIDR ranges as needed
