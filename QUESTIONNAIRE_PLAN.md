# Questionnaire-Driven Solution Architecture Design Plan

## Overview
Transform the manual table-filling approach into a guided questionnaire that captures architecture decisions layer-by-layer, then auto-generates diagrams and links them to the LeanIX Business Capability Model.

---

## 1. Questionnaire Structure (Phase 1: Design)

### 1.1 Page Layout
```
Solution Architecture Questionnaire
├── Business Context Section
│   ├── Business Capability (reference to LeanIX)
│   ├── Business Outcome / Goal
│   ├── Primary Stakeholders
│   └── Strategic Alignment
│
├── Edge Layer Questions
│   ├── What are the entry points? (users, APIs, IoT, etc.)
│   ├── Technologies used (browsers, mobile, APIs)
│   └── Security considerations
│
├── Network Layer Questions
│   ├── Network architecture (VPC, firewalls, load balancers)
│   ├── Connectivity patterns
│   └── Resilience requirements
│
├── Platform Layer Questions
│   ├── Core platform services
│   ├── Identity & access management
│   └── Integration middleware
│
├── Application Layer Questions
│   ├── Application components
│   ├── Primary functions per component
│   ├── Technology stack choices
│   └── Scaling strategy
│
├── Data Layer Questions
│   ├── Data sources & destinations
│   ├── Storage types (RDBMS, NoSQL, Data Lake)
│   ├── Data flows & transformations
│   └── Data governance & retention
│
└── Integration & Cross-Cutting Questions
    ├── Key data flows
    ├── API integrations
    ├── Security & compliance needs
    └── Performance & availability targets
```

### 1.2 Question Types
- **Structured inputs** (text fields, dropdowns)
- **Multi-select** (choose applicable technologies, stakeholders)
- **Tables** (define components, connections within each layer)
- **References** (link to LeanIX capability IDs)
- **Conditional sections** (show/hide based on previous answers)

---

## 2. Data Capture Format (Phase 2: Implementation)

### Option A: Confluence Tables + Macros (Current)
**Pros:**
- No external tools needed
- Works in Cloud/Server/Data Center
- Easy to edit inline

**Cons:**
- Less interactive
- Manual validation
- Limited validation

### Option B: Confluence Forms (Confluence Cloud only)
**Pros:**
- Native form UI
- Built-in validation
- Structured data export

**Cons:**
- Cloud only
- Limited to Cloud API

### Option C: Embedded Web Form (Advanced)
**Pros:**
- Full control over UX
- Client-side validation
- Rich interactions

**Cons:**
- Requires external hosting/macro development
- More complex

**Recommendation:** Start with Option A (enhanced tables with clearer instructions), then move to Forms if using Cloud.

---

## 3. Information Model: Question → Component Mapping

### 3.1 Data Structure
```python
architecture_design = {
    "metadata": {
        "capability_id": "CAP-001",  # LeanIX ID
        "capability_name": "Digital Service Delivery",
        "business_outcome": "Enable users to access services 24/7",
        "stakeholders": ["Business Owner", "Chief Architect", "Security Lead"],
        "created_date": "2026-05-08",
    },
    "layers": {
        "edge": [
            {
                "component": "Web Portal",
                "technology": "React, CloudFront CDN",
                "function": "User interface for service access",
                "users": ["External Citizens", "Internal Staff"],
                "outflows": ["API calls to API Gateway"],
            }
        ],
        "network": [ ... ],
        "platform": [ ... ],
        "application": [ ... ],
        "data": [ ... ],
    },
    "dataflows": [
        {
            "from": "Web Portal",
            "to": "API Gateway",
            "data": "Service requests",
            "protocol": "HTTPS/REST",
        },
        ...
    ],
    "capability_mapping": {
        "cap_001": ["Web Portal", "API Gateway", "Backend Service"],
        "cap_002": ["Database", "Data Lake"],
    }
}
```

---

## 4. Processing Pipeline (Phase 3: Scripts)

### 4.1 New Script: `confluence_questionnaire_to_architecture.py`
**Input:** Questionnaire page HTML  
**Process:**
1. Parse questionnaire answers from Confluence page
2. Map answers to architecture components
3. Extract business capability context
4. Build internal data structure (JSON)

**Output:** Architecture data structure (in-memory or exported as JSON attachment)

### 4.2 Enhanced: `confluence_update_diagrams.py`
**Input:** Architecture data structure  
**Process:**
1. Generate Solution Architecture diagram (with capability labels)
2. Generate Data Flow Diagram
3. Generate Capability Realization Matrix (which components realize which capabilities)
4. Create visual link to LeanIX
5. Upload all as .drawio attachments

**Output:** Updated Confluence page with embedded diagrams + capability matrix

### 4.3 New Script: `confluence_generate_capability_report.py`
**Input:** Architecture data + capability mapping  
**Process:**
1. Generate a "Business Capability Realization" report
2. Show which layers/components realize each capability
3. Identify capability gaps
4. Generate compliance/risk matrix

**Output:** Embedded HTML report or separate page

---

## 5. LeanIX Integration Points

### 5.1 What to Capture from LeanIX
- Business Capability ID (e.g., `CAP-001`)
- Capability name and description
- Parent/child capability hierarchy
- Applications mapped to capability (in LeanIX)
- Status (planned, active, retiring)

### 5.2 How to Link
**Option A: Manual reference**
- User enters capability ID in questionnaire
- Script fetches capability name from a lookup table (manual or API)

**Option B: Embed LeanIX viewer**
- Add LeanIX embedded widget to the page
- Show Business Capability Model alongside questionnaire

**Option C: API Integration (requires LeanIX API token)**
- Script queries LeanIX API for capabilities
- Auto-populate dropdown with available capabilities
- Fetch capability details (description, status, applications)

**Recommendation:** Start with Option A (manual), move to Option C if you have LeanIX API access.

---

## 6. Diagram Generation Strategy

### 6.1 Solution Architecture Diagram
```
┌─ CAPABILITY: Digital Service Delivery ──────────────────┐
│                                                           │
│  Edge              Network         Platform              │
│  ┌──────────┐     ┌──────────┐    ┌──────────┐           │
│  │Web Portal├────→│API GW    ├───→│Identity  │           │
│  └──────────┘     └──────────┘    │Service   │           │
│                        ↓           └──────────┘           │
│                   ┌──────────┐          ↓                 │
│                   │Load Bal. │    ┌──────────┐            │
│                   └──────────┘    │API Auth  │            │
│                        ↓          └──────────┘            │
│  Application       ┌──────────┐                           │
│  ┌──────────┐     │Backend    │                           │
│  │Service A ├────→│Service    │                           │
│  └──────────┘     └──────────┘                           │
│                        ↓                                  │
│  Data          ┌──────────────┐                          │
│  ┌──────────┐  │Database      │                          │
│  │Data Lake ├→ │(Aurora)      │                          │
│  └──────────┘  └──────────────┘                          │
└──────────────────────────────────────────────────────────┘
```

### 6.2 Capability Realization Matrix
```
Component / Service    | Capability 1 | Capability 2 | Capability 3
─────────────────────────────────────────────────────────────────
Web Portal             | Primary      | Primary      | N/A
API Gateway            | Primary      | Primary      | Support
Identity Service       | Support      | Primary      | Support
Backend Service        | Primary      | Primary      | Primary
Database               | Support      | Support      | Support
```

### 6.3 Data Flow Diagram (Enhanced)
```
User Input → [Web Portal] ──HTTP/REST──> [API Gateway]
                                              │
                                         [Token Check]
                                              │
                    ┌─────────────────────────┼─────────────┐
                    ↓                         ↓             ↓
              [Service A]           [Service B]      [Service C]
                    │                    │                │
                    └────────┬───────────┬────────────────┘
                             ↓
                        [Database]
                             ↓
                        [Data Lake]
```

---

## 7. Implementation Roadmap

### Phase 1: Questionnaire Template (Week 1)
- [ ] Design questionnaire structure (sections, questions, answer types)
- [ ] Create Confluence page with structured tables/form
- [ ] Add inline instructions and examples
- [ ] Link to LeanIX Business Capability Model reference

### Phase 2: Data Extraction Script (Week 2)
- [ ] `confluence_questionnaire_to_architecture.py`
  - Parse questionnaire answers
  - Validate layer structure
  - Build architecture data structure
  - Export as JSON

### Phase 3: Enhanced Diagram Generation (Week 2-3)
- [ ] Update `confluence_update_diagrams.py`
  - Accept architecture data structure as input
  - Add capability labels to diagram
  - Generate capability matrix table
  - Embed capability mapping visualization

### Phase 4: LeanIX Integration (Week 3-4)
- [ ] Create `confluence_leanix_bridge.py`
  - Query LeanIX API for capability details
  - Create capability lookup/dropdown
  - Auto-populate capability info in questionnaire

### Phase 5: Reporting & Insights (Week 4-5)
- [ ] `confluence_generate_capability_report.py`
  - Identify capability gaps
  - Show coverage matrix
  - Generate recommendations
  - Create executive summary

---

## 8. Execution Workflow (End-User View)

```
1. User navigates to "Solution Architecture Questionnaire" page
   ↓
2. User fills in guided questionnaire:
   - Business capability (dropdown linked to LeanIX)
   - Answer questions for each layer
   - Define components, technologies, data flows
   ↓
3. User clicks "Generate Architecture"
   ↓
4. Backend processing:
   - Parse questionnaire answers
   - Map to components
   - Generate diagrams
   - Create capability matrix
   ↓
5. Diagrams appear on page automatically:
   - Solution Architecture diagram (with capability color-coding)
   - Data Flow Diagram
   - Capability Realization Matrix
   - Business Context summary
   ↓
6. User can iterate:
   - Update questionnaire
   - Click "Refresh Diagrams"
   - Diagrams update in real-time
```

---

## 9. Technical Considerations

### 9.1 Data Validation
- Validate layer names (Edge, Network, Platform, Application, Data)
- Check component names are unique within layer
- Verify all referenced components exist
- Validate capability IDs match LeanIX records

### 9.2 Diagram Performance
- Large architectures (50+ components) may slow down rendering
- Consider splitting into sub-diagrams per layer or capability
- Use pagination for component lists

### 9.3 Versioning & Audit Trail
- Store each questionnaire version
- Capture who answered, when, and why changes were made
- Link to architecture decisions (ADRs)

### 9.4 Export & Sharing
- Export architecture to JSON/YAML for version control
- Generate PDF report for stakeholders
- API endpoint to query architecture data programmatically

---

## 10. Success Criteria

- [ ] Questionnaire captures all necessary architecture details
- [ ] Diagrams auto-generate with <2 second latency
- [ ] Business capability mapping is visible on diagrams
- [ ] Users can iterate and update without manual script runs
- [ ] Links to LeanIX Business Capability Model are functional
- [ ] Non-technical stakeholders can understand the diagrams
- [ ] Architecture decisions are traceable back to questionnaire answers

---

## Next Steps

1. **Confirm questionnaire structure** with your team
2. **Define LeanIX integration scope** (manual vs. API)
3. **Choose data capture format** (tables vs. forms)
4. **Start Phase 1** (Questionnaire template page design)

Would you like me to proceed with any of these phases?
