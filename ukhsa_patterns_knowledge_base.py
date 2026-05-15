"""
UKHSA Patterns Knowledge Base
==============================
Sources:
  - UKHSA Cloud Strategy & Approved Patterns (28 data patterns, 10 ADRs)
  - UKHSA Baseline Current State Architecture (INF-01 to INF-06)
  - UKHSA Target State Architecture v1.0 (Mar 2025)
    * TSA-LZ: Landing Zones
    * TSA-NET: Networking
    * TSA-IDN: Identity
    * TSA-PLT: Platform Designs (CCF-mapped)

This module is the single source of truth for ALL UKHSA-approved architecture
patterns (excluding EDAP-specific patterns which remain in edap_knowledge_base.py).

Usage by diagram generators:
  from ukhsa_patterns_knowledge_base import (
      detect_ukhsa_patterns,
      inject_ukhsa_into_components,
      inject_ukhsa_into_connections,
      inject_ukhsa_into_dataflows,
      inject_ukhsa_into_context_entities,
      build_ukhsa_pattern_summary,
      UKHSA_MANDATORY_CONTROLS,
  )

Pattern detection scans project components, connections, dataflows, and
context entities for trigger keywords and returns the matched pattern dicts.
Manual override is supported via explicit_pattern_ids (list of IDs like
["1A", "TSA-IDN", "UKHSA-INF-02"]).
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# UKHSA INFRASTRUCTURE PATTERNS  (UKHSA-INF-01 to UKHSA-INF-06)
# Source: Baseline Current State Architecture §3–6
# ─────────────────────────────────────────────────────────────────────────────

INFRA_PATTERNS: list[dict] = [
    {
        "id": "UKHSA-INF-01",
        "name": "Strategic Landing Zone Placement",
        "family": "Infrastructure",
        "reference": "Baseline Current State Architecture §3",
        "use_case": "All new workloads must deploy to UKHSA strategic landing zones (AWS HALO or Azure PHECloud)",
        "trigger_keywords": [
            "landing zone", "lz", "aws account", "azure subscription", "workload placement",
            "account vending", "subscription vending", "control tower", "management group",
            "new workload", "new project", "cloud deployment",
        ],
        "aws_services": [
            {"name": "AWS Organizations", "layer": "Managed", "technology": "AWS Organizations (OU hierarchy)"},
            {"name": "AWS Control Tower", "layer": "Managed", "technology": "AWS Control Tower (LZ automation)"},
            {"name": "AWS Config", "layer": "Managed", "technology": "AWS Config (compliance rules)"},
            {"name": "AWS Security Hub", "layer": "Managed", "technology": "AWS Security Hub (CSPM)"},
            {"name": "Service Control Policies", "layer": "Managed", "technology": "AWS SCPs (org-level guardrails)"},
            {"name": "AWS CloudTrail", "layer": "Managed", "technology": "AWS CloudTrail (org trail)"},
        ],
        "azure_services": [
            {"name": "Azure Management Groups", "layer": "Managed", "technology": "Azure Management Group hierarchy"},
            {"name": "Azure Policy", "layer": "Managed", "technology": "Azure Policy (compliance guardrails)"},
            {"name": "Microsoft Defender for Cloud", "layer": "Managed", "technology": "CSPM + workload protection"},
        ],
        "components": [
            {"name": "AWS Organizations (OU Hierarchy)", "layer": "Managed", "technology": "AWS Organizations"},
            {"name": "AWS Control Tower", "layer": "Managed", "technology": "AWS Control Tower"},
            {"name": "AWS Security Hub", "layer": "Managed", "technology": "AWS Security Hub"},
            {"name": "Service Control Policies (SCPs)", "layer": "Managed", "technology": "AWS SCPs"},
        ],
        "connections": [
            {"from": "Workload Account", "to": "AWS Organizations (OU Hierarchy)", "label": "governed by OU policies"},
            {"from": "AWS Control Tower", "to": "Workload Account", "label": "vends account with guardrails"},
            {"from": "AWS Security Hub", "to": "Workload Account", "label": "aggregates compliance findings"},
        ],
        "data_flows": [],
        "context_entities": [
            {"name": "UKHSA AWS Landing Zone (HALO)", "type": "External System", "interaction": "Strategic AWS landing zone — all new AWS workloads must deploy here", "direction": "In"},
            {"name": "UKHSA Azure Landing Zone (PHECloud)", "type": "External System", "interaction": "Strategic Azure landing zone — all new Azure workloads must deploy here", "direction": "In"},
        ],
        "mandatory_controls": [
            "All new workloads must deploy to UKHSA strategic LZ (AWS HALO or Azure PHECloud)",
            "No new deployments to legacy LZs (PHE Azure, NIHP Azure, PHE AWS)",
            "All infrastructure via IaC (Terraform mandatory — ADR-009)",
            "AWS Config enabled with organisation-wide rules",
            "SCPs at OU level to enforce security guardrails",
            "CloudTrail org trail enabled for all accounts",
        ],
    },

    {
        "id": "UKHSA-INF-02",
        "name": "Hybrid Cloud Connectivity",
        "family": "Infrastructure",
        "reference": "Baseline Current State Architecture §4 / Target State §3",
        "use_case": "Secure, high-performance connectivity between AWS/Azure LZs and on-premises data centres",
        "trigger_keywords": [
            "direct connect", "expressroute", "on-prem", "on-premises", "on premises",
            "hybrid", "hybrid connectivity", "vpn", "site to site", "private link",
            "mpls", "wan", "data centre", "datacenter", "porton", "colindale",
            "palo alto", "firewall", "network", "connectivity",
        ],
        "aws_services": [
            {"name": "AWS Direct Connect", "layer": "Network", "technology": "AWS Direct Connect (dedicated private connection)"},
            {"name": "AWS Transit Gateway", "layer": "Network", "technology": "AWS Transit Gateway (hub-and-spoke routing)"},
            {"name": "AWS Network Firewall", "layer": "Network", "technology": "AWS Network Firewall (east-west inspection)"},
            {"name": "AWS VPC", "layer": "Network", "technology": "Amazon VPC (isolated network segments)"},
            {"name": "NAT Gateway", "layer": "Network", "technology": "AWS NAT Gateway (private subnet egress)"},
            {"name": "VPC Flow Logs", "layer": "Managed", "technology": "VPC Flow Logs → CloudWatch"},
        ],
        "azure_services": [
            {"name": "Azure ExpressRoute", "layer": "Network", "technology": "Azure ExpressRoute (dedicated private connection)"},
            {"name": "Azure Virtual WAN", "layer": "Network", "technology": "Azure Virtual WAN (global transit hub)"},
            {"name": "Azure Firewall", "layer": "Network", "technology": "Azure Firewall (centralised egress + inspection)"},
        ],
        "components": [
            {"name": "AWS Direct Connect", "layer": "Network", "technology": "AWS Direct Connect"},
            {"name": "AWS Transit Gateway", "layer": "Network", "technology": "AWS Transit Gateway"},
            {"name": "On-Premises Data Centre", "layer": "internet", "technology": "UKHSA DC (Porton/Colindale)"},
            {"name": "Palo Alto Firewall", "layer": "Network", "technology": "Palo Alto NGFW (N/S traffic)"},
        ],
        "connections": [
            {"from": "On-Premises Data Centre", "to": "AWS Direct Connect", "label": "dedicated private circuit (Virgin Media MPLS)"},
            {"from": "AWS Direct Connect", "to": "AWS Transit Gateway", "label": "private VIF → TGW attachment"},
            {"from": "AWS Transit Gateway", "to": "AWS VPC", "label": "routes to workload VPCs"},
            {"from": "On-Premises Data Centre", "to": "Palo Alto Firewall", "label": "N/S traffic inspection"},
        ],
        "data_flows": [
            {"id": "DF-INF-02-01", "source": "On-Premises DC", "destination": "AWS VPC", "data": "Hybrid workload traffic", "protocol": "Direct Connect / BGP"},
        ],
        "context_entities": [
            {"name": "UKHSA On-Premises DC (Porton/Colindale)", "type": "External System", "interaction": "Connected via Direct Connect and ExpressRoute for hybrid access", "direction": "Both"},
        ],
        "mandatory_controls": [
            "No direct internet access to cloud landing zones",
            "All traffic between cloud and on-prem via Direct Connect or ExpressRoute",
            "Palo Alto firewalls inspect all N/S traffic at DC perimeter",
            "VPC Flow Logs enabled on all VPCs",
            "Target state: enable local internet breakout via zScaler (remove on-prem backhaul)",
            "Target state: establish direct AWS↔Azure connectivity (Equinix/Megaport or ZPA)",
        ],
    },

    {
        "id": "UKHSA-INF-03",
        "name": "Zero Trust End-User Access (zScaler)",
        "family": "Infrastructure",
        "reference": "Baseline Current State Architecture §4 / Target State §3 / ADR-010",
        "use_case": "All end-user internet access inspected and controlled via zScaler Zero Trust Exchange",
        "trigger_keywords": [
            "zero trust", "ztna", "ztna", "zscaler", "zpa", "zia",
            "end user", "user access", "remote access", "vpn replacement",
            "internet access", "web filtering", "proxy", "sase",
        ],
        "aws_services": [
            {"name": "AWS Verified Access", "layer": "Network", "technology": "AWS Verified Access (cloud-native ZTNA alternative)"},
            {"name": "AWS IAM Identity Center", "layer": "Managed", "technology": "AWS IAM Identity Center (SSO)"},
        ],
        "azure_services": [
            {"name": "Microsoft Entra ID", "layer": "Managed", "technology": "Microsoft Entra ID (identity provider)"},
        ],
        "components": [
            {"name": "zScaler Zero Trust Exchange", "layer": "internet", "technology": "zScaler ZTE (SaaS)"},
            {"name": "zScaler Private Access (ZPA)", "layer": "internet", "technology": "zScaler ZPA"},
            {"name": "zScaler Internet Access (ZIA)", "layer": "internet", "technology": "zScaler ZIA"},
            {"name": "End User Device", "layer": "internet", "technology": "Managed device + zScaler client"},
        ],
        "connections": [
            {"from": "End User Device", "to": "zScaler Zero Trust Exchange", "label": "all internet traffic inspected (no direct traversal)"},
            {"from": "zScaler Zero Trust Exchange", "to": "Private Application", "label": "ZPA: identity-verified app access"},
            {"from": "zScaler Zero Trust Exchange", "to": "Internet", "label": "ZIA: filtered egress"},
        ],
        "data_flows": [
            {"id": "DF-INF-03-01", "source": "End User Device", "destination": "Private Application", "data": "User requests", "protocol": "HTTPS via zScaler ZPA (ZTNA)"},
        ],
        "context_entities": [
            {"name": "zScaler Zero Trust Exchange", "type": "External System", "interaction": "Inspects and controls all end-user internet and application access", "direction": "Both"},
        ],
        "mandatory_controls": [
            "No direct internet traversal for end users — all traffic via zScaler",
            "zScaler ZPA for private application access (replaces VPN)",
            "zScaler ZIA for internet access (URL filtering, SSL inspection)",
            "MFA enforced at identity provider (Entra ID) before zScaler access",
            "ADR-010: Zero Trust mandatory for all new connectivity",
        ],
    },

    {
        "id": "UKHSA-INF-04",
        "name": "Split-Horizon DNS",
        "family": "Infrastructure",
        "reference": "Baseline Current State Architecture §4 / Target State §3",
        "use_case": "Consistent split-horizon DNS across hybrid and multi-cloud with Route 53 as strategic resolver",
        "trigger_keywords": [
            "dns", "route 53", "route53", "private hosted zone", "dns resolution",
            "split horizon", "split-horizon", "dnssec", "private dns",
            "public dns", "name resolution", "ukhsa.gov.uk", "domain",
        ],
        "aws_services": [
            {"name": "Amazon Route 53", "layer": "Managed", "technology": "Amazon Route 53 (Public + Private Hosted Zones)"},
            {"name": "Route 53 Resolver", "layer": "Managed", "technology": "Route 53 Resolver (inbound/outbound rules)"},
            {"name": "Route 53 Health Checks", "layer": "Managed", "technology": "Route 53 Health Checks (failover routing)"},
        ],
        "azure_services": [
            {"name": "Azure DNS Private Zones", "layer": "Managed", "technology": "Azure DNS Private Zones"},
        ],
        "components": [
            {"name": "Amazon Route 53 (Public)", "layer": "Public", "technology": "Route 53 Public Hosted Zone"},
            {"name": "Amazon Route 53 (Private)", "layer": "Network", "technology": "Route 53 Private Hosted Zone"},
            {"name": "Route 53 Resolver", "layer": "Network", "technology": "Route 53 Resolver Endpoints"},
            {"name": "On-Prem DNS Server", "layer": "internet", "technology": "On-premises DNS (Porton/Colindale)"},
        ],
        "connections": [
            {"from": "Internal Client", "to": "Route 53 Resolver", "label": "private DNS query"},
            {"from": "Route 53 Resolver", "to": "Amazon Route 53 (Private)", "label": "resolve *.aws.ukhsa.gov.uk"},
            {"from": "Route 53 Resolver", "to": "On-Prem DNS Server", "label": "forward on-prem zone queries"},
            {"from": "External Client", "to": "Amazon Route 53 (Public)", "label": "public DNS resolution"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "DNS naming: *.[workload].[hyperscaler].[parent-domain] (e.g. api.edap.aws.ukhsa.gov.uk)",
            "Internal and external DNS use same naming standard for PKI compatibility",
            "Root zone (ukhsa.gov.uk) managed by Cyber/Networking Team",
            "Landing zone DNS zones created by Platform Engineering via LZ codebase",
            "Workload DNS zones created during account vending; managed by workload team via IaC",
            "DNSSEC enabled for domain integrity protection",
            "Target state: migrate ukhsa.gov.uk and phe.gov.uk from Azure to Route 53",
        ],
    },

    {
        "id": "UKHSA-INF-05",
        "name": "Federated Identity (Entra ID Golden Source)",
        "family": "Infrastructure",
        "reference": "Baseline Current State Architecture §5 / Target State §4 / ADR-010",
        "use_case": "Microsoft Entra ID as single golden source IdP — federated to AWS, SaaS, and all workloads",
        "trigger_keywords": [
            "identity", "entra id", "azure ad", "azure active directory",
            "iam identity center", "sso", "single sign on", "federation",
            "federated auth", "mfa", "multi factor", "rbac", "abac",
            "local accounts", "local iam", "provisioning", "scim",
            "privileged identity", "pim", "jit", "just in time",
            "joiner mover leaver", "jml", "user lifecycle",
        ],
        "aws_services": [
            {"name": "AWS IAM Identity Center", "layer": "Managed", "technology": "AWS IAM Identity Center (SSO + Permission Sets)"},
            {"name": "AWS IAM", "layer": "Managed", "technology": "AWS IAM (roles, permission boundaries, SCPs)"},
            {"name": "AWS IAM Access Analyzer", "layer": "Managed", "technology": "AWS IAM Access Analyzer"},
            {"name": "AWS CloudTrail", "layer": "Managed", "technology": "AWS CloudTrail (identity audit)"},
        ],
        "azure_services": [
            {"name": "Microsoft Entra ID", "layer": "Managed", "technology": "Microsoft Entra ID (primary IdP)"},
            {"name": "Entra ID PIM", "layer": "Managed", "technology": "Entra ID Privileged Identity Management"},
            {"name": "Azure Sentinel", "layer": "Managed", "technology": "Microsoft Sentinel (SIEM — identity signals)"},
        ],
        "components": [
            {"name": "Microsoft Entra ID", "layer": "Managed", "technology": "Microsoft Entra ID (Golden Source IdP)"},
            {"name": "AWS IAM Identity Center", "layer": "Managed", "technology": "AWS IAM Identity Center"},
            {"name": "Entra ID PIM", "layer": "Managed", "technology": "Privileged Identity Management (JIT)"},
            {"name": "SCIM Provisioning", "layer": "Managed", "technology": "SCIM 2.0 (auto-provisioning)"},
            {"name": "HR System Integration", "layer": "Managed", "technology": "HR → Entra ID Lifecycle Workflows"},
        ],
        "connections": [
            {"from": "Microsoft Entra ID", "to": "AWS IAM Identity Center", "label": "SAML 2.0 federation + SCIM provisioning"},
            {"from": "Microsoft Entra ID", "to": "SaaS Applications", "label": "federated SSO (SAML/OIDC)"},
            {"from": "Entra ID PIM", "to": "AWS IAM Identity Center", "label": "JIT role activation (time-bound)"},
            {"from": "HR System Integration", "to": "Microsoft Entra ID", "label": "Joiner/Mover/Leaver automation"},
            {"from": "Microsoft Entra ID", "to": "On-Premises AD", "label": "Entra ID Connect sync"},
        ],
        "data_flows": [
            {"id": "DF-INF-05-01", "source": "User", "destination": "AWS Console / CLI", "data": "Federated authentication token", "protocol": "SAML 2.0 / OIDC via Entra ID"},
        ],
        "context_entities": [
            {"name": "Microsoft Entra ID (UKHSA Tenant)", "type": "External System", "interaction": "Golden source IdP — federated to all AWS accounts, SaaS platforms, and on-prem", "direction": "Both"},
        ],
        "mandatory_controls": [
            "No local IAM users in any workload account — enforced via SCPs",
            "All access via Entra ID federation + AWS IAM Identity Center",
            "MFA enforced for all user accounts — no exceptions",
            "JIT access for elevated permissions via Entra ID PIM (time-bound, approval workflow)",
            "SCIM provisioning for automated role assignment based on HR attributes",
            "Breakglass accounts isolated in dedicated AWS account / Azure subscription",
            "Quarterly access reviews via PIM + IAM Access Analyzer",
            "ADR-010: Zero Trust — continuous verification of every access request",
        ],
    },

    {
        "id": "UKHSA-INF-06",
        "name": "Approved Platform Portfolio",
        "family": "Infrastructure",
        "reference": "Baseline Current State Architecture §6 / Target State §5",
        "use_case": "Select from UKHSA-approved platforms and shared services — EDAP for analytics, APIM for APIs, Sentinel for SIEM",
        "trigger_keywords": [
            "platform", "edap", "analytics platform", "api management", "apim",
            "virtual desktop", "avd", "vdi", "sentinel", "siem", "vmware",
            "hpc", "atlassian", "confluence", "jira", "shared service",
            "service mesh", "api gateway", "api platform",
        ],
        "aws_services": [
            {"name": "EDAP (AWS Analytics Platform)", "layer": "Managed", "technology": "EDAP — UKHSA AWS analytics platform"},
        ],
        "azure_services": [
            {"name": "Azure API Management (APIM)", "layer": "Managed", "technology": "Azure APIM (centralised API gateway)"},
            {"name": "Microsoft Sentinel", "layer": "Managed", "technology": "Microsoft Sentinel (SIEM/SOAR)"},
            {"name": "Azure Virtual Desktop (AVD)", "layer": "Managed", "technology": "Azure Virtual Desktop"},
        ],
        "components": [
            {"name": "EDAP (AWS Analytics)", "layer": "Managed", "technology": "EDAP — see EDAP-INT-01 to INT-06"},
            {"name": "Azure APIM", "layer": "Managed", "technology": "Azure API Management"},
            {"name": "Microsoft Sentinel (SIEM)", "layer": "Managed", "technology": "Microsoft Sentinel"},
            {"name": "Azure Virtual Desktop (AVD)", "layer": "Managed", "technology": "Azure AVD"},
        ],
        "connections": [
            {"from": "Workload API", "to": "Azure APIM", "label": "all external APIs published via APIM"},
            {"from": "Cloud Workloads", "to": "Microsoft Sentinel (SIEM)", "label": "security logs + alerts forwarded"},
        ],
        "data_flows": [],
        "context_entities": [
            {"name": "UKHSA EDAP Platform", "type": "External System", "interaction": "Mandatory analytics platform for all data/analytics workloads", "direction": "Both"},
            {"name": "Azure APIM", "type": "External System", "interaction": "Centralised API gateway for all external-facing APIs", "direction": "Both"},
        ],
        "mandatory_controls": [
            "EDAP is mandatory for all analytics workloads — exception via ARB only",
            "All external-facing APIs published via Azure APIM",
            "Security logs forwarded to Microsoft Sentinel (SIEM)",
            "VMware on Azure: migration to Azure-native target — no new VMware deployments",
            "ADR-009: IaC mandatory for all platform infrastructure",
        ],
    },

    {
        "id": "UKHSA-INF-07",
        "name": "OpenShift Container Platform — Internal Environment",
        "family": "Infrastructure",
        "reference": "UKHSA Baseline Current State Architecture §5 / CCoE Platform Register",
        "use_case": (
            "UKHSA on-premises OpenShift cluster (OCP) hosting containerised workloads. "
            "Connects to AWS via Transit Gateway + PrivateLink, to Azure via ExpressRoute "
            "Private Endpoint, and to on-premises DC via internal LAN/SDN. "
            "All four UKHSA internal environments (On-Prem DC, OpenShift, AWS, Azure) are "
            "classified as 'internal' — external data sources must be drawn outside this boundary."
        ),
        "trigger_keywords": [
            "openshift", "open shift", "ocp", "red hat", "redhat",
            "container platform", "kubernetes on-prem", "openshift cluster",
            "tekton", "openshift pipeline", "openshift route", "quay",
            "openshift registry", "openshift operator", "openshift pod",
            "ansible", "internal environment", "internal zone",
        ],
        "aws_services": [
            {"name": "AWS PrivateLink", "layer": "Network", "technology": "AWS PrivateLink (private endpoint to OCP services)"},
            {"name": "AWS Transit Gateway", "layer": "Network", "technology": "AWS Transit Gateway (OCP VPC attachment)"},
            {"name": "AWS Direct Connect", "layer": "Network", "technology": "AWS Direct Connect (on-prem / OCP egress path)"},
        ],
        "azure_services": [
            {"name": "Azure Private Endpoint", "layer": "Network", "technology": "Azure Private Endpoint (OCP → Azure PaaS)"},
            {"name": "Azure ExpressRoute", "layer": "Network", "technology": "Azure ExpressRoute (OCP on-prem to Azure)"},
        ],
        "components": [
            {"name": "OpenShift Cluster (OCP)", "layer": "Application", "technology": "Red Hat OpenShift Container Platform (on-premises)"},
            {"name": "OpenShift Router / Ingress", "layer": "Network", "technology": "OpenShift HAProxy Route (north-south ingress)"},
            {"name": "OpenShift Registry (Quay)", "layer": "Application", "technology": "Red Hat Quay — internal container image registry"},
            {"name": "Tekton CI/CD Pipeline", "layer": "Application", "technology": "OpenShift Pipelines (Tekton)"},
            {"name": "OpenShift PrivateLink Endpoint", "layer": "Network", "technology": "AWS PrivateLink endpoint (OCP → AWS)"},
        ],
        "connections": [
            {"from": "OpenShift Cluster (OCP)", "to": "OpenShift PrivateLink Endpoint", "label": "private service call (no public internet)"},
            {"from": "OpenShift PrivateLink Endpoint", "to": "AWS Transit Gateway", "label": "PrivateLink → TGW attachment"},
            {"from": "OpenShift Cluster (OCP)", "to": "On-Premises Data Centre", "label": "internal LAN / SDN (same DC)"},
            {"from": "OpenShift Cluster (OCP)", "to": "Azure Private Endpoint", "label": "ExpressRoute private peering"},
            {"from": "Tekton CI/CD Pipeline", "to": "OpenShift Registry (Quay)", "label": "push/pull container images"},
        ],
        "data_flows": [
            {"id": "DF-INF-07-01", "source": "OpenShift Cluster (OCP)", "destination": "AWS VPC (via PrivateLink)", "data": "Application API calls / data writes", "protocol": "HTTPS / gRPC — PrivateLink"},
            {"id": "DF-INF-07-02", "source": "OpenShift Cluster (OCP)", "destination": "Azure PaaS (via Private Endpoint)", "data": "Application data / service calls", "protocol": "HTTPS — ExpressRoute private peering"},
            {"id": "DF-INF-07-03", "source": "On-Premises DC", "destination": "OpenShift Cluster (OCP)", "data": "Internal service traffic", "protocol": "Internal LAN / SDN"},
        ],
        "context_entities": [
            {
                "name": "UKHSA OpenShift Cluster (On-Prem OCP)",
                "type": "Internal System",
                "interaction": (
                    "On-premises OpenShift container platform — part of UKHSA internal zone. "
                    "Connects to AWS via PrivateLink/TGW and Azure via ExpressRoute. "
                    "External sources must NOT connect directly; route via approved ingress gateway."
                ),
                "direction": "Both",
                "zone": "internal",
            },
        ],
        "mandatory_controls": [
            "OpenShift cluster must reside within UKHSA internal zone — no direct public internet exposure",
            "All OCP → AWS traffic via AWS PrivateLink (no public endpoints)",
            "All OCP → Azure traffic via ExpressRoute private peering (no public endpoints)",
            "Container images sourced only from Quay internal registry (no public Docker Hub pulls in prod)",
            "Tekton pipelines must pass SAST/DAST scans before promoting to production namespace",
            "Network policies (Kubernetes NetworkPolicy) enforced for all namespaces — default-deny",
            "OpenShift audit logs forwarded to Microsoft Sentinel (SIEM) via FluentD/Vector",
            "IaC mandatory for all cluster configuration (Ansible / GitOps / ArgoCD) — ADR-009",
            "External data sources drawn outside the UKHSA internal boundary with labelled connection type",
        ],
        # ── Internal environment topology context ──────────────────────────────
        # Used by diagram generators to draw the correct zone boundaries.
        "internal_environments": [
            {
                "name": "On-Premises DC",
                "label": "UKHSA On-Premises\n(Porton / Colindale)",
                "fill_color": "#f5f5f5",
                "stroke_color": "#616161",
                "icon": "onprem:datacenter",
            },
            {
                "name": "OpenShift (OCP)",
                "label": "UKHSA OpenShift\n(On-Prem OCP)",
                "fill_color": "#fff0f0",
                "stroke_color": "#CC0000",
                "icon": "openshift:openshift",
            },
            {
                "name": "AWS",
                "label": "UKHSA AWS\n(HALO Landing Zone)",
                "fill_color": "#fff8e1",
                "stroke_color": "#FF9900",
                "icon": "aws:general",
            },
            {
                "name": "Azure",
                "label": "UKHSA Azure\n(PHECloud Landing Zone)",
                "fill_color": "#e8f4fd",
                "stroke_color": "#0078D4",
                "icon": "azure:entra_id",
            },
        ],
        "cross_environment_connections": [
            {"from": "On-Premises DC", "to": "AWS", "label": "Direct Connect\n(Virgin Media MPLS)", "protocol": "BGP / MPLS", "cost_driver": "DC port hours + data transfer"},
            {"from": "On-Premises DC", "to": "Azure", "label": "ExpressRoute\n(dedicated circuit)", "protocol": "BGP / MPLS", "cost_driver": "ExpressRoute circuit fee + data transfer"},
            {"from": "On-Premises DC", "to": "OpenShift (OCP)", "label": "Internal LAN / SDN", "protocol": "Internal (no cloud cost)", "cost_driver": "None (internal LAN)"},
            {"from": "OpenShift (OCP)", "to": "AWS", "label": "PrivateLink\n(no public internet)", "protocol": "HTTPS / gRPC", "cost_driver": "PrivateLink endpoint hours + per-GB"},
            {"from": "OpenShift (OCP)", "to": "Azure", "label": "ExpressRoute\nPrivate Peering", "protocol": "HTTPS", "cost_driver": "ExpressRoute circuit (shared with DC)"},
            {"from": "AWS", "to": "Azure", "label": "Inter-cloud egress\n(highest cost risk)", "protocol": "HTTPS / direct peering", "cost_driver": "AWS egress ~£0.07–0.08/GB (highest cost)"},
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# DATA PATTERNS  (1A–8B — 28 patterns across 8 layers)
# Source: UKHSA Cloud Strategy & Approved Patterns
# ─────────────────────────────────────────────────────────────────────────────

DATA_PATTERNS: list[dict] = [
    # Layer 1 — Ingestion
    {
        "id": "1A",
        "name": "Direct API Ingestion",
        "family": "Data Ingestion",
        "reference": "UKHSA Cloud Strategy — Layer 1A",
        "use_case": "Real-time or continuous feeds from external APIs",
        "trigger_keywords": [
            "api ingestion", "api gateway ingestion", "webhook", "rest api ingest",
            "continuous feed", "api feed", "http ingest",
        ],
        "aws_services": [
            {"name": "Amazon API Gateway", "layer": "Public", "technology": "Amazon API Gateway (REST/HTTP)"},
            {"name": "Amazon SQS", "layer": "Managed", "technology": "Amazon SQS (buffer queue)"},
            {"name": "Amazon EventBridge", "layer": "Managed", "technology": "Amazon EventBridge (routing)"},
            {"name": "AWS Lambda", "layer": "Private", "technology": "AWS Lambda (processing)"},
        ],
        "components": [
            {"name": "Amazon API Gateway", "layer": "Public", "technology": "Amazon API Gateway"},
            {"name": "Amazon SQS", "layer": "Managed", "technology": "Amazon SQS"},
            {"name": "Amazon EventBridge", "layer": "Managed", "technology": "Amazon EventBridge"},
        ],
        "connections": [
            {"from": "External API Source", "to": "Amazon API Gateway", "label": "REST/HTTPS"},
            {"from": "Amazon API Gateway", "to": "Amazon SQS", "label": "enqueue message"},
            {"from": "Amazon SQS", "to": "Amazon EventBridge", "label": "route event"},
        ],
        "data_flows": [
            {"id": "DF-1A-01", "source": "External API", "destination": "Amazon API Gateway", "data": "API payload", "protocol": "HTTPS REST"},
        ],
        "context_entities": [],
        "mandatory_controls": [
            "API Gateway with WAF and authentication (API key, IAM, or Cognito)",
            "SQS encrypted with KMS CMK",
            "Dead-letter queue configured for failed messages",
            "VPC Endpoint for SQS — no public API calls",
        ],
    },

    {
        "id": "1B",
        "name": "Batch File Upload",
        "family": "Data Ingestion",
        "reference": "UKHSA Cloud Strategy — Layer 1B",
        "use_case": "Bulk scheduled file transfers from external sources",
        "trigger_keywords": [
            "batch file", "bulk upload", "scheduled file", "sftp", "file upload",
            "csv upload", "excel upload", "bulk ingest", "batch ingest",
        ],
        "aws_services": [
            {"name": "Amazon S3", "layer": "Data", "technology": "Amazon S3 (SSE-KMS)"},
            {"name": "AWS Glue", "layer": "Managed", "technology": "AWS Glue (ETL)"},
            {"name": "AWS Transfer Family", "layer": "Network", "technology": "AWS Transfer Family (SFTP)"},
        ],
        "components": [
            {"name": "AWS Transfer Family (SFTP)", "layer": "Network", "technology": "AWS Transfer Family"},
            {"name": "Amazon S3 (Staging)", "layer": "Data", "technology": "Amazon S3"},
            {"name": "AWS Glue (ETL)", "layer": "Managed", "technology": "AWS Glue"},
        ],
        "connections": [
            {"from": "External Source", "to": "AWS Transfer Family (SFTP)", "label": "SFTP push"},
            {"from": "AWS Transfer Family (SFTP)", "to": "Amazon S3 (Staging)", "label": "S3 PutObject"},
            {"from": "Amazon S3 (Staging)", "to": "AWS Glue (ETL)", "label": "EventBridge trigger"},
        ],
        "data_flows": [
            {"id": "DF-1B-01", "source": "External Source", "destination": "Amazon S3 (Staging)", "data": "Bulk files (CSV/JSON/Parquet)", "protocol": "SFTP / S3 API"},
        ],
        "context_entities": [],
        "mandatory_controls": [
            "SSE-KMS on all S3 buckets",
            "Antivirus scan before processing",
            "Transfer Family security policy: TransferSecurityPolicy-2020-06",
        ],
    },

    {
        "id": "1C",
        "name": "Database Replication",
        "family": "Data Ingestion",
        "reference": "UKHSA Cloud Strategy — Layer 1C",
        "use_case": "Sync operational or on-prem database to cloud for analytics or DR",
        "trigger_keywords": [
            "database replication", "db sync", "dms", "cdc", "change data capture",
            "database migration", "rds replication", "aurora replication",
            "sync database", "operational db", "source database",
        ],
        "aws_services": [
            {"name": "AWS DMS", "layer": "Managed", "technology": "AWS Database Migration Service (full-load + CDC)"},
            {"name": "Amazon RDS", "layer": "Data", "technology": "Amazon RDS (target)"},
            {"name": "Amazon Aurora", "layer": "Data", "technology": "Amazon Aurora PostgreSQL"},
        ],
        "components": [
            {"name": "AWS DMS Replication Task", "layer": "Managed", "technology": "AWS DMS"},
            {"name": "Amazon Aurora PostgreSQL", "layer": "Data", "technology": "Amazon Aurora PostgreSQL"},
        ],
        "connections": [
            {"from": "Source Database", "to": "AWS DMS Replication Task", "label": "CDC / full-load replication"},
            {"from": "AWS DMS Replication Task", "to": "Amazon Aurora PostgreSQL", "label": "replicated data"},
        ],
        "data_flows": [
            {"id": "DF-1C-01", "source": "Source Database", "destination": "Amazon Aurora PostgreSQL", "data": "Database rows (CDC)", "protocol": "AWS DMS"},
        ],
        "context_entities": [],
        "mandatory_controls": [
            "DMS source credentials in AWS Secrets Manager (read-only)",
            "KMS encryption on target RDS/Aurora",
            "ADR-001: Aurora PostgreSQL is preferred relational target",
        ],
    },

    {
        "id": "1D",
        "name": "Streaming Ingestion",
        "family": "Data Ingestion",
        "reference": "UKHSA Cloud Strategy — Layer 1D",
        "use_case": "High-speed sensor data, metrics, IoT, or event streams",
        "trigger_keywords": [
            "streaming", "kinesis", "kafka", "msk", "iot", "sensor data",
            "high velocity", "real time ingest", "event stream", "message stream",
        ],
        "aws_services": [
            {"name": "Amazon Kinesis Data Streams", "layer": "Managed", "technology": "Amazon Kinesis Data Streams"},
            {"name": "Amazon MSK", "layer": "Managed", "technology": "Amazon MSK (Managed Kafka)"},
            {"name": "AWS Lambda", "layer": "Private", "technology": "AWS Lambda (stream consumer)"},
        ],
        "components": [
            {"name": "Amazon Kinesis Data Streams", "layer": "Managed", "technology": "Amazon Kinesis"},
            {"name": "Amazon MSK (Kafka)", "layer": "Managed", "technology": "Amazon MSK"},
            {"name": "AWS Lambda (Consumer)", "layer": "Private", "technology": "AWS Lambda"},
        ],
        "connections": [
            {"from": "Stream Producer", "to": "Amazon Kinesis Data Streams", "label": "PutRecord (real-time)"},
            {"from": "Amazon Kinesis Data Streams", "to": "AWS Lambda (Consumer)", "label": "stream trigger"},
        ],
        "data_flows": [
            {"id": "DF-1D-01", "source": "Stream Producer", "destination": "Amazon Kinesis Data Streams", "data": "Streaming events", "protocol": "Kinesis PUT"},
        ],
        "context_entities": [],
        "mandatory_controls": [
            "KMS CMK encryption on Kinesis streams and MSK clusters",
            "VPC-only Kinesis endpoint — no public access",
        ],
    },

    # Layer 2 — Processing
    {
        "id": "2A",
        "name": "Batch ETL",
        "family": "Data Processing",
        "reference": "UKHSA Cloud Strategy — Layer 2A",
        "use_case": "Nightly or scheduled large-volume data transformation jobs",
        "trigger_keywords": [
            "batch etl", "etl", "batch processing", "nightly job", "scheduled job",
            "glue job", "databrew", "step functions", "data pipeline", "transform",
        ],
        "aws_services": [
            {"name": "AWS Glue", "layer": "Managed", "technology": "AWS Glue (Spark ETL Jobs)"},
            {"name": "AWS Step Functions", "layer": "Managed", "technology": "AWS Step Functions (orchestration)"},
            {"name": "AWS Glue DataBrew", "layer": "Managed", "technology": "AWS Glue DataBrew (data prep)"},
        ],
        "components": [
            {"name": "AWS Step Functions", "layer": "Managed", "technology": "AWS Step Functions"},
            {"name": "AWS Glue (Batch ETL)", "layer": "Managed", "technology": "AWS Glue"},
            {"name": "AWS Glue DataBrew", "layer": "Managed", "technology": "AWS Glue DataBrew"},
        ],
        "connections": [
            {"from": "EventBridge Scheduler", "to": "AWS Step Functions", "label": "scheduled trigger"},
            {"from": "AWS Step Functions", "to": "AWS Glue (Batch ETL)", "label": "execute ETL job"},
            {"from": "AWS Glue (Batch ETL)", "to": "Target Data Store", "label": "write transformed data"},
        ],
        "data_flows": [
            {"id": "DF-2A-01", "source": "Source Data Store", "destination": "Target Data Store", "data": "Transformed dataset", "protocol": "Glue Spark Job"},
        ],
        "context_entities": [],
        "mandatory_controls": [
            "Glue jobs use VPC network interfaces",
            "S3 access via S3 Gateway VPC Endpoint",
            "Glue continuous logging to CloudWatch (/aws-glue/jobs/logs-v2)",
        ],
    },

    {
        "id": "2B",
        "name": "Real-Time Stream Processing",
        "family": "Data Processing",
        "reference": "UKHSA Cloud Strategy — Layer 2B",
        "use_case": "Instant anomaly detection, live dashboards, real-time alerting",
        "trigger_keywords": [
            "real-time processing", "stream processing", "kinesis analytics",
            "anomaly detection", "live dashboard", "real time alert",
        ],
        "aws_services": [
            {"name": "Amazon Kinesis Data Analytics", "layer": "Managed", "technology": "Kinesis Data Analytics (Flink)"},
            {"name": "AWS Lambda", "layer": "Private", "technology": "AWS Lambda (real-time processing)"},
        ],
        "components": [
            {"name": "Amazon Kinesis Data Analytics", "layer": "Managed", "technology": "Kinesis Data Analytics"},
            {"name": "AWS Lambda (Real-Time)", "layer": "Private", "technology": "AWS Lambda"},
        ],
        "connections": [
            {"from": "Amazon Kinesis Data Streams", "to": "Amazon Kinesis Data Analytics", "label": "stream input"},
            {"from": "Amazon Kinesis Data Analytics", "to": "AWS Lambda (Real-Time)", "label": "anomaly/alert output"},
        ],
        "data_flows": [
            {"id": "DF-2B-01", "source": "Kinesis Stream", "destination": "Kinesis Data Analytics", "data": "Event stream", "protocol": "Kinesis"},
        ],
        "context_entities": [],
        "mandatory_controls": ["KMS encryption on Kinesis streams", "VPC-only Lambda functions"],
    },

    {
        "id": "2C",
        "name": "Scheduled Spark / ML Jobs",
        "family": "Data Processing",
        "reference": "UKHSA Cloud Strategy — Layer 2C",
        "use_case": "ML model training or large-scale Spark processing that runs then stops",
        "trigger_keywords": [
            "spark", "emr", "sagemaker training", "ml training", "machine learning job",
            "model training", "batch ml", "large scale processing",
        ],
        "aws_services": [
            {"name": "Amazon EMR", "layer": "Managed", "technology": "Amazon EMR (transient cluster)"},
            {"name": "Amazon SageMaker", "layer": "Managed", "technology": "Amazon SageMaker (training jobs)"},
        ],
        "components": [
            {"name": "Amazon EMR Cluster", "layer": "Private", "technology": "Amazon EMR"},
            {"name": "Amazon SageMaker Training", "layer": "Managed", "technology": "Amazon SageMaker"},
        ],
        "connections": [
            {"from": "EventBridge Scheduler", "to": "Amazon EMR Cluster", "label": "launch transient cluster"},
            {"from": "Amazon EMR Cluster", "to": "Amazon S3", "label": "read/write training data"},
        ],
        "data_flows": [
            {"id": "DF-2C-01", "source": "S3 Training Dataset", "destination": "Amazon SageMaker Training", "data": "ML training data", "protocol": "S3 GetObject"},
        ],
        "context_entities": [],
        "mandatory_controls": ["EMR clusters in private subnets only", "SageMaker VPC-only domain"],
    },

    {
        "id": "2D",
        "name": "Federated Query",
        "family": "Data Processing",
        "reference": "UKHSA Cloud Strategy — Layer 2D / ADR-003",
        "use_case": "Cross-dataset analysis without copying data — Athena and Redshift Spectrum",
        "trigger_keywords": [
            "federated query", "athena", "redshift spectrum", "query across",
            "cross dataset", "data virtualisation", "data virtualization",
            "s3 select", "query s3",
        ],
        "aws_services": [
            {"name": "Amazon Athena", "layer": "Managed", "technology": "Amazon Athena (serverless SQL)"},
            {"name": "Amazon Redshift Spectrum", "layer": "Managed", "technology": "Redshift Spectrum (S3 queries)"},
            {"name": "AWS Glue Data Catalog", "layer": "Managed", "technology": "AWS Glue Data Catalog (schema)"},
        ],
        "components": [
            {"name": "Amazon Athena", "layer": "Managed", "technology": "Amazon Athena"},
            {"name": "Amazon Redshift Spectrum", "layer": "Managed", "technology": "Redshift Spectrum"},
            {"name": "AWS Glue Data Catalog", "layer": "Managed", "technology": "Glue Data Catalog"},
        ],
        "connections": [
            {"from": "Analyst", "to": "Amazon Athena", "label": "SQL query (Workgroup)"},
            {"from": "Amazon Athena", "to": "AWS Glue Data Catalog", "label": "schema resolution"},
            {"from": "Amazon Athena", "to": "Amazon S3", "label": "read Parquet via Lake Formation"},
        ],
        "data_flows": [
            {"id": "DF-2D-01", "source": "Analyst", "destination": "Amazon Athena", "data": "SQL query", "protocol": "JDBC/ODBC via Athena Workgroup"},
        ],
        "context_entities": [],
        "mandatory_controls": [
            "ADR-003: Use Redshift Spectrum for queries > 100GB",
            "Per-user Athena Workgroup with dedicated S3 query results bucket (SSE-KMS)",
            "Lake Formation fine-grained access on all tables",
        ],
    },

    # Layer 3 — Storage
    {
        "id": "3A",
        "name": "Transactional Database (OLTP)",
        "family": "Data Storage",
        "reference": "UKHSA Cloud Strategy — Layer 3A / ADR-001",
        "use_case": "Operational systems requiring ACID transactions",
        "trigger_keywords": [
            "database", "rds", "aurora", "postgresql", "mysql", "oltp",
            "transactional", "relational", "sql", "operational database",
        ],
        "aws_services": [
            {"name": "Amazon Aurora PostgreSQL", "layer": "Data", "technology": "Amazon Aurora PostgreSQL (Multi-AZ)"},
            {"name": "Amazon RDS", "layer": "Data", "technology": "Amazon RDS (Multi-AZ)"},
            {"name": "Amazon DynamoDB", "layer": "Data", "technology": "Amazon DynamoDB (NoSQL)"},
        ],
        "components": [
            {"name": "Amazon Aurora PostgreSQL", "layer": "Data", "technology": "Amazon Aurora PostgreSQL"},
            {"name": "Amazon RDS", "layer": "Data", "technology": "Amazon RDS"},
        ],
        "connections": [
            {"from": "Application Layer", "to": "Amazon Aurora PostgreSQL", "label": "JDBC/HTTPS (private subnet)"},
        ],
        "data_flows": [
            {"id": "DF-3A-01", "source": "Application", "destination": "Amazon Aurora PostgreSQL", "data": "Transactional queries", "protocol": "PostgreSQL protocol (TLS 1.2+)"},
        ],
        "context_entities": [],
        "mandatory_controls": [
            "ADR-001: Aurora PostgreSQL is preferred relational database",
            "Multi-AZ deployment mandatory for production",
            "KMS encryption at rest",
            "TLS 1.2+ enforced (ADR-005)",
            "Database credentials in Secrets Manager with auto-rotation",
        ],
    },

    {
        "id": "3B",
        "name": "Data Warehouse (OLAP)",
        "family": "Data Storage",
        "reference": "UKHSA Cloud Strategy — Layer 3B / ADR-003",
        "use_case": "Historical reporting and complex analytical queries",
        "trigger_keywords": [
            "data warehouse", "redshift", "olap", "reporting", "analytics store",
            "warehouse", "dimensional model", "star schema",
        ],
        "aws_services": [
            {"name": "Amazon Redshift", "layer": "Data", "technology": "Amazon Redshift (RA3 nodes)"},
            {"name": "Amazon QuickSight", "layer": "Managed", "technology": "Amazon QuickSight Enterprise"},
        ],
        "components": [
            {"name": "Amazon Redshift", "layer": "Data", "technology": "Amazon Redshift RA3"},
            {"name": "Amazon QuickSight", "layer": "Managed", "technology": "Amazon QuickSight Enterprise"},
        ],
        "connections": [
            {"from": "Application / BI Tool", "to": "Amazon Redshift", "label": "JDBC (private VPC)"},
            {"from": "Amazon QuickSight", "to": "Amazon Redshift", "label": "VPC connection"},
        ],
        "data_flows": [
            {"id": "DF-3B-01", "source": "Conform Layer", "destination": "Amazon Redshift", "data": "Curated datasets", "protocol": "Glue Job / Redshift COPY"},
        ],
        "context_entities": [],
        "mandatory_controls": [
            "ADR-003: Redshift Spectrum for > 100GB queries",
            "Redshift not internet-facing (private subnets)",
            "KMS CMK encryption for sensitive data (ADR-006)",
        ],
    },

    {
        "id": "3C",
        "name": "Data Lake (Bronze/Silver/Gold)",
        "family": "Data Storage",
        "reference": "UKHSA Cloud Strategy — Layer 3C / ADR-002 / ADR-007",
        "use_case": "Centralised storage for raw, conformed, and curated datasets",
        "trigger_keywords": [
            "data lake", "s3 lake", "bronze silver gold", "bronze", "silver", "gold",
            "lake formation", "glue catalog", "parquet", "raw layer", "conform layer",
        ],
        "aws_services": [
            {"name": "Amazon S3", "layer": "Data", "technology": "Amazon S3 (Parquet, SSE-KMS)"},
            {"name": "AWS Glue Data Catalog", "layer": "Managed", "technology": "AWS Glue Data Catalog"},
            {"name": "AWS Lake Formation", "layer": "Managed", "technology": "AWS Lake Formation (TBAC)"},
        ],
        "components": [
            {"name": "Amazon S3 (Data Lake)", "layer": "Data", "technology": "Amazon S3"},
            {"name": "AWS Glue Data Catalog", "layer": "Managed", "technology": "AWS Glue Data Catalog"},
            {"name": "AWS Lake Formation", "layer": "Managed", "technology": "AWS Lake Formation"},
        ],
        "connections": [
            {"from": "Ingestion Pipeline", "to": "Amazon S3 (Data Lake)", "label": "write Bronze (raw)"},
            {"from": "ETL Pipeline", "to": "Amazon S3 (Data Lake)", "label": "write Silver (conformed)"},
            {"from": "Transform Pipeline", "to": "Amazon S3 (Data Lake)", "label": "write Gold (curated)"},
            {"from": "AWS Glue Data Catalog", "to": "AWS Lake Formation", "label": "schema + TBAC registration"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "ADR-002: S3 + Glue not HDFS",
            "ADR-007: Bronze/Silver/Gold tier naming convention",
            "SSE-KMS on all S3 buckets — bucket policy rejects non-KMS uploads",
            "Lake Formation TBAC on all tables",
            "S3 versioning enabled; lifecycle policies for cost control",
        ],
    },

    {
        "id": "3D",
        "name": "Time-Series Database",
        "family": "Data Storage",
        "reference": "UKHSA Cloud Strategy — Layer 3D",
        "use_case": "Lab capacity, infection rates, or metrics captured per minute/second",
        "trigger_keywords": [
            "time series", "timestream", "metrics", "lab capacity",
            "infection rate", "time-series", "iot metrics",
        ],
        "aws_services": [
            {"name": "Amazon Timestream", "layer": "Data", "technology": "Amazon Timestream (serverless time-series)"},
        ],
        "components": [
            {"name": "Amazon Timestream", "layer": "Data", "technology": "Amazon Timestream"},
        ],
        "connections": [
            {"from": "Metrics Producer", "to": "Amazon Timestream", "label": "write time-series records"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": ["KMS CMK encryption on Timestream database", "VPC Endpoint for Timestream"],
    },

    {
        "id": "3E",
        "name": "Document Store",
        "family": "Data Storage",
        "reference": "UKHSA Cloud Strategy — Layer 3E",
        "use_case": "Nested, variable-structure, or schema-flexible data",
        "trigger_keywords": [
            "nosql", "dynamodb", "documentdb", "mongodb", "opensearch",
            "document store", "json store", "schema flexible", "variable schema",
        ],
        "aws_services": [
            {"name": "Amazon DynamoDB", "layer": "Data", "technology": "Amazon DynamoDB (serverless NoSQL)"},
            {"name": "Amazon DocumentDB", "layer": "Data", "technology": "Amazon DocumentDB (MongoDB-compatible)"},
            {"name": "Amazon OpenSearch", "layer": "Data", "technology": "Amazon OpenSearch Service"},
        ],
        "components": [
            {"name": "Amazon DynamoDB", "layer": "Data", "technology": "Amazon DynamoDB"},
            {"name": "Amazon OpenSearch", "layer": "Data", "technology": "Amazon OpenSearch Service"},
        ],
        "connections": [
            {"from": "Application Layer", "to": "Amazon DynamoDB", "label": "document read/write (VPC endpoint)"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "DynamoDB encryption at rest with KMS CMK",
            "DynamoDB tables in VPC-only access mode",
            "OpenSearch in VPC — no public endpoint",
        ],
    },

    # Layer 4 — Integration
    {
        "id": "4A",
        "name": "Event-Driven Pipelines",
        "family": "Data Integration",
        "reference": "UKHSA Cloud Strategy — Layer 4A / ADR-004",
        "use_case": "Loosely-coupled services reacting to data changes or domain events",
        "trigger_keywords": [
            "event driven", "eventbridge", "events", "event bus",
            "loosely coupled", "pub sub", "publish subscribe",
            "sqs", "sns", "message queue", "event notification",
        ],
        "aws_services": [
            {"name": "Amazon EventBridge", "layer": "Managed", "technology": "Amazon EventBridge (event routing)"},
            {"name": "Amazon SQS", "layer": "Managed", "technology": "Amazon SQS (message queue)"},
            {"name": "Amazon SNS", "layer": "Managed", "technology": "Amazon SNS (fan-out notifications)"},
            {"name": "AWS Lambda", "layer": "Private", "technology": "AWS Lambda (event consumer)"},
        ],
        "components": [
            {"name": "Amazon EventBridge", "layer": "Managed", "technology": "Amazon EventBridge"},
            {"name": "Amazon SQS", "layer": "Managed", "technology": "Amazon SQS"},
            {"name": "Amazon SNS", "layer": "Managed", "technology": "Amazon SNS"},
            {"name": "AWS Lambda (Event Consumer)", "layer": "Private", "technology": "AWS Lambda"},
        ],
        "connections": [
            {"from": "Event Producer", "to": "Amazon EventBridge", "label": "PutEvents"},
            {"from": "Amazon EventBridge", "to": "Amazon SQS", "label": "route to queue (ADR-004)"},
            {"from": "Amazon SQS", "to": "AWS Lambda (Event Consumer)", "label": "trigger Lambda"},
        ],
        "data_flows": [
            {"id": "DF-4A-01", "source": "Event Producer", "destination": "AWS Lambda (Event Consumer)", "data": "Domain event", "protocol": "EventBridge → SQS → Lambda"},
        ],
        "context_entities": [],
        "mandatory_controls": [
            "ADR-004: Use EventBridge over raw SNS/SQS for event routing",
            "SQS KMS CMK encryption",
            "Dead-letter queue on all SQS queues",
            "EventBridge resource policies restrict cross-account access",
        ],
    },

    {
        "id": "4B",
        "name": "ETL Orchestration",
        "family": "Data Integration",
        "reference": "UKHSA Cloud Strategy — Layer 4B",
        "use_case": "Complex multi-step workflows with dependencies, retries, and branching",
        "trigger_keywords": [
            "orchestration", "workflow", "step functions", "airflow", "mwaa",
            "pipeline orchestration", "multi step", "complex pipeline",
        ],
        "aws_services": [
            {"name": "AWS Step Functions", "layer": "Managed", "technology": "AWS Step Functions (Express/Standard)"},
            {"name": "Amazon MWAA", "layer": "Managed", "technology": "Amazon MWAA (Apache Airflow)"},
        ],
        "components": [
            {"name": "AWS Step Functions", "layer": "Managed", "technology": "AWS Step Functions"},
            {"name": "Amazon MWAA (Airflow)", "layer": "Managed", "technology": "Amazon MWAA"},
        ],
        "connections": [
            {"from": "EventBridge Trigger", "to": "AWS Step Functions", "label": "start execution"},
            {"from": "AWS Step Functions", "to": "Downstream Services", "label": "orchestrate multi-step workflow"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": ["Step Functions execution logs to CloudWatch", "MWAA in VPC-only mode"],
    },

    {
        "id": "4C",
        "name": "Data Replication & Sync",
        "family": "Data Integration",
        "reference": "UKHSA Cloud Strategy — Layer 4C",
        "use_case": "High availability, compliance archiving, or multi-region data copies",
        "trigger_keywords": [
            "replication", "cross region", "crr", "s3 replication",
            "rds replica", "read replica", "multi region", "dr replication",
            "data sync", "data replication",
        ],
        "aws_services": [
            {"name": "S3 Cross-Region Replication", "layer": "Managed", "technology": "S3 CRR (automatic)"},
            {"name": "Amazon RDS Read Replicas", "layer": "Data", "technology": "RDS Read Replicas (cross-region)"},
        ],
        "components": [
            {"name": "S3 Cross-Region Replication (CRR)", "layer": "Managed", "technology": "S3 CRR"},
            {"name": "RDS Read Replica", "layer": "Data", "technology": "Amazon RDS Read Replica"},
        ],
        "connections": [
            {"from": "Primary S3 Bucket", "to": "S3 Cross-Region Replication (CRR)", "label": "auto-replicate to DR region"},
            {"from": "Primary RDS", "to": "RDS Read Replica", "label": "async replication"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": ["KMS CMK replication for encrypted buckets", "Replication destination bucket in separate region"],
    },

    # Layer 5 — Governance
    {
        "id": "5A",
        "name": "Centralised Data Catalogue",
        "family": "Data Governance",
        "reference": "UKHSA Cloud Strategy — Layer 5A",
        "use_case": "Discoverability, metadata management, and access control across all datasets",
        "trigger_keywords": [
            "data catalogue", "data catalog", "metadata", "glue catalog",
            "lake formation", "data discovery", "data governance",
        ],
        "aws_services": [
            {"name": "AWS Glue Data Catalog", "layer": "Managed", "technology": "AWS Glue Data Catalog"},
            {"name": "AWS Lake Formation", "layer": "Managed", "technology": "AWS Lake Formation (governance)"},
        ],
        "components": [
            {"name": "AWS Glue Data Catalog", "layer": "Managed", "technology": "AWS Glue Data Catalog"},
            {"name": "AWS Lake Formation", "layer": "Managed", "technology": "AWS Lake Formation"},
        ],
        "connections": [
            {"from": "AWS Glue Crawler", "to": "AWS Glue Data Catalog", "label": "register schema"},
            {"from": "AWS Glue Data Catalog", "to": "AWS Lake Formation", "label": "TBAC permissions"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "Lake Formation TBAC on all catalogued tables",
            "Glue Crawlers run on all new data lake zones",
        ],
    },

    {
        "id": "5B",
        "name": "Data Quality & Validation",
        "family": "Data Governance",
        "reference": "UKHSA Cloud Strategy — Layer 5B",
        "use_case": "Automated quality checks before data is promoted between layers",
        "trigger_keywords": [
            "data quality", "validation", "quality check", "databrew",
            "data profiling", "quality gate", "data cleansing",
        ],
        "aws_services": [
            {"name": "AWS Glue DataBrew", "layer": "Managed", "technology": "AWS Glue DataBrew (profile + quality)"},
            {"name": "Amazon EventBridge", "layer": "Managed", "technology": "Amazon EventBridge (alerting on failure)"},
        ],
        "components": [
            {"name": "AWS Glue DataBrew", "layer": "Managed", "technology": "AWS Glue DataBrew"},
        ],
        "connections": [
            {"from": "Ingestion Pipeline", "to": "AWS Glue DataBrew", "label": "quality profile job"},
            {"from": "AWS Glue DataBrew", "to": "Amazon EventBridge", "label": "quality failure alert"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "DataBrew quality failure halts pipeline — raises CloudWatch alarm",
            "Quality rules defined per feed in AppConfig",
        ],
    },

    {
        "id": "5C",
        "name": "Data Lineage & Audit Trail",
        "family": "Data Governance",
        "reference": "UKHSA Cloud Strategy — Layer 5C",
        "use_case": "Regulatory compliance, root-cause analysis, and data provenance tracking",
        "trigger_keywords": [
            "data lineage", "audit trail", "cloudtrail", "provenance",
            "data audit", "compliance audit", "openlineage", "lineage",
        ],
        "aws_services": [
            {"name": "AWS CloudTrail", "layer": "Managed", "technology": "AWS CloudTrail (data events)"},
            {"name": "AWS Lake Formation", "layer": "Managed", "technology": "Lake Formation (lineage)"},
            {"name": "Amazon S3 Access Logs", "layer": "Managed", "technology": "S3 Server Access Logging"},
        ],
        "components": [
            {"name": "AWS CloudTrail", "layer": "Managed", "technology": "AWS CloudTrail"},
            {"name": "AWS Lake Formation (Lineage)", "layer": "Managed", "technology": "AWS Lake Formation"},
        ],
        "connections": [
            {"from": "All Pipeline Steps", "to": "AWS CloudTrail", "label": "API audit events"},
            {"from": "Glue/Step Functions Jobs", "to": "SQS Lineage Queue", "label": "OpenLineage START/END messages"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "CloudTrail org trail with S3 data events enabled",
            "OpenLineage messages emitted on all pipeline START and END",
            "Lineage data retained per compliance requirements",
        ],
    },

    # Layer 6 — Security (MANDATORY)
    {
        "id": "6A",
        "name": "Access Control",
        "family": "Security & Compliance",
        "reference": "UKHSA Cloud Strategy — Layer 6A / ADR-010",
        "use_case": "Fine-grained identity-based access to all data assets",
        "trigger_keywords": [
            "access control", "iam", "lake formation access", "s3 object lock",
            "mfa", "rbac", "least privilege", "permission", "authorisation",
        ],
        "aws_services": [
            {"name": "AWS IAM", "layer": "Managed", "technology": "AWS IAM (roles, policies, permission boundaries)"},
            {"name": "AWS Lake Formation", "layer": "Managed", "technology": "Lake Formation (column/row-level TBAC)"},
            {"name": "Amazon S3 Object Lock", "layer": "Data", "technology": "S3 Object Lock (WORM compliance)"},
        ],
        "azure_services": [
            {"name": "Microsoft Entra ID", "layer": "Managed", "technology": "Entra ID (federated identity)"},
        ],
        "components": [
            {"name": "AWS IAM", "layer": "Managed", "technology": "AWS IAM"},
            {"name": "AWS Lake Formation (TBAC)", "layer": "Managed", "technology": "AWS Lake Formation"},
        ],
        "connections": [],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "ADR-010: Zero Trust — identity verified at every layer",
            "MFA mandatory for all users",
            "Lake Formation TBAC on all data lake tables",
            "S3 Object Lock for compliance-required immutability",
            "No local IAM users — federated auth only",
        ],
    },

    {
        "id": "6B",
        "name": "Encryption & Key Management",
        "family": "Security & Compliance",
        "reference": "UKHSA Cloud Strategy — Layer 6B / ADR-005 / ADR-006",
        "use_case": "Data at-rest and in-transit encryption with managed key lifecycle",
        "trigger_keywords": [
            "encryption", "kms", "key management", "tls", "ssl",
            "secrets manager", "certificate", "acm", "encrypt",
            "sensitive data", "pii", "confidential",
        ],
        "aws_services": [
            {"name": "AWS KMS", "layer": "Managed", "technology": "AWS KMS (customer-managed CMKs)"},
            {"name": "AWS Secrets Manager", "layer": "Managed", "technology": "AWS Secrets Manager (credential rotation)"},
            {"name": "AWS Certificate Manager", "layer": "Managed", "technology": "AWS ACM (TLS certificates)"},
        ],
        "components": [
            {"name": "AWS KMS (CMK)", "layer": "Managed", "technology": "AWS KMS"},
            {"name": "AWS Secrets Manager", "layer": "Managed", "technology": "AWS Secrets Manager"},
            {"name": "AWS ACM", "layer": "Managed", "technology": "AWS Certificate Manager"},
        ],
        "connections": [
            {"from": "All Data Stores", "to": "AWS KMS (CMK)", "label": "SSE-KMS encryption at rest"},
            {"from": "All Services", "to": "AWS ACM", "label": "TLS 1.2+ certificates"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "ADR-005: TLS 1.2+ minimum for all data in transit",
            "ADR-006: Customer-managed KMS CMKs for all sensitive data",
            "Secrets Manager for all credentials — never hardcoded",
            "90-day secret rotation enforced (SEC-IAM-05)",
            "KMS key rotation enabled",
        ],
    },

    {
        "id": "6C",
        "name": "Network Security & Isolation",
        "family": "Security & Compliance",
        "reference": "UKHSA Cloud Strategy — Layer 6C / ADR-010",
        "use_case": "Network-level controls preventing data exfiltration and lateral movement",
        "trigger_keywords": [
            "vpc", "private subnet", "security group", "nacl", "vpc endpoint",
            "privatelink", "waf", "network isolation", "network security",
            "private network", "egress control",
        ],
        "aws_services": [
            {"name": "Amazon VPC", "layer": "Network", "technology": "Amazon VPC (isolated network)"},
            {"name": "Security Groups", "layer": "Network", "technology": "AWS Security Groups (stateful)"},
            {"name": "VPC Endpoints", "layer": "Network", "technology": "VPC Gateway + Interface Endpoints"},
            {"name": "AWS PrivateLink", "layer": "Network", "technology": "AWS PrivateLink"},
            {"name": "AWS WAF", "layer": "Public", "technology": "AWS WAF (web application firewall)"},
        ],
        "components": [
            {"name": "Amazon VPC", "layer": "Network", "technology": "Amazon VPC"},
            {"name": "VPC Endpoints", "layer": "Network", "technology": "VPC Endpoints (S3, STS, etc.)"},
            {"name": "AWS WAF", "layer": "Public", "technology": "AWS WAF"},
            {"name": "Security Groups", "layer": "Network", "technology": "AWS Security Groups"},
        ],
        "connections": [
            {"from": "Private Subnet Resources", "to": "VPC Endpoints", "label": "private API access (no internet)"},
            {"from": "Internet", "to": "AWS WAF", "label": "filtered ingress"},
            {"from": "AWS WAF", "to": "Application Load Balancer", "label": "inspected traffic"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "All workloads in private subnets (SEC-APS-03)",
            "No public S3 bucket access — S3 Gateway VPC Endpoint mandatory",
            "WAF on all public-facing load balancers",
            "VPC Flow Logs enabled",
            "Security Groups default-deny (least-privilege ingress/egress)",
        ],
    },

    {
        "id": "6D",
        "name": "Data Masking & Anonymisation",
        "family": "Security & Compliance",
        "reference": "UKHSA Cloud Strategy — Layer 6D",
        "use_case": "PII/sensitive data de-identification for non-production and analytics use",
        "trigger_keywords": [
            "masking", "anonymisation", "anonymization", "pii", "gdpr",
            "data masking", "de-identification", "redaction", "pseudonymisation",
        ],
        "aws_services": [
            {"name": "AWS Glue DataBrew", "layer": "Managed", "technology": "Glue DataBrew (masking transforms)"},
            {"name": "AWS Lambda", "layer": "Private", "technology": "Lambda (custom anonymisation)"},
        ],
        "components": [
            {"name": "AWS Glue DataBrew (Masking)", "layer": "Managed", "technology": "AWS Glue DataBrew"},
            {"name": "AWS Lambda (Anonymisation)", "layer": "Private", "technology": "AWS Lambda"},
        ],
        "connections": [
            {"from": "Raw PII Data", "to": "AWS Glue DataBrew (Masking)", "label": "apply masking transforms"},
            {"from": "AWS Glue DataBrew (Masking)", "to": "Masked Data Store", "label": "write masked output"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "PII never written to non-production environments without masking",
            "DPIA completed for any PII processing",
            "UK GDPR and NHS DSPT compliance documented",
        ],
    },

    # Layer 7 — Monitoring
    {
        "id": "7A",
        "name": "Centralised Logging",
        "family": "Monitoring & Observability",
        "reference": "UKHSA Cloud Strategy — Layer 7A",
        "use_case": "Unified audit trail, security investigation, and operational diagnostics",
        "trigger_keywords": [
            "logging", "cloudwatch logs", "cloudtrail", "x-ray", "observability",
            "centralised logging", "log aggregation", "audit log",
        ],
        "aws_services": [
            {"name": "Amazon CloudWatch Logs", "layer": "Managed", "technology": "Amazon CloudWatch Logs"},
            {"name": "AWS X-Ray", "layer": "Managed", "technology": "AWS X-Ray (distributed tracing)"},
            {"name": "AWS CloudTrail", "layer": "Managed", "technology": "AWS CloudTrail (API audit)"},
            {"name": "Amazon EventBridge", "layer": "Managed", "technology": "Amazon EventBridge (event routing)"},
        ],
        "components": [
            {"name": "Amazon CloudWatch Logs", "layer": "Managed", "technology": "Amazon CloudWatch Logs"},
            {"name": "AWS CloudTrail", "layer": "Managed", "technology": "AWS CloudTrail"},
            {"name": "AWS X-Ray", "layer": "Managed", "technology": "AWS X-Ray"},
        ],
        "connections": [
            {"from": "All Workloads", "to": "Amazon CloudWatch Logs", "label": "log streams forwarded"},
            {"from": "All API Calls", "to": "AWS CloudTrail", "label": "management + data events"},
            {"from": "Amazon CloudWatch Logs", "to": "Microsoft Sentinel (SIEM)", "label": "forward to SIEM"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "CloudTrail org trail with management and S3 data events",
            "CloudWatch Log groups with 90-day+ retention",
            "All security logs forwarded to Microsoft Sentinel",
            "X-Ray tracing enabled for all Lambda and API Gateway",
        ],
    },

    {
        "id": "7B",
        "name": "Performance Monitoring & Alerting",
        "family": "Monitoring & Observability",
        "reference": "UKHSA Cloud Strategy — Layer 7B",
        "use_case": "Proactive detection of degradation, capacity issues, or SLA breaches",
        "trigger_keywords": [
            "monitoring", "alerting", "cloudwatch alarms", "alarm", "sla",
            "performance monitoring", "health check", "dashboard",
        ],
        "aws_services": [
            {"name": "Amazon CloudWatch Metrics", "layer": "Managed", "technology": "Amazon CloudWatch Metrics"},
            {"name": "Amazon CloudWatch Alarms", "layer": "Managed", "technology": "CloudWatch Alarms (threshold alerts)"},
            {"name": "Amazon SNS", "layer": "Managed", "technology": "Amazon SNS (alert notifications)"},
        ],
        "components": [
            {"name": "Amazon CloudWatch Alarms", "layer": "Managed", "technology": "CloudWatch Alarms"},
            {"name": "Amazon SNS (Alerts)", "layer": "Managed", "technology": "Amazon SNS"},
        ],
        "connections": [
            {"from": "Amazon CloudWatch Alarms", "to": "Amazon SNS (Alerts)", "label": "alarm state change notification"},
            {"from": "Amazon SNS (Alerts)", "to": "Ops Team / PagerDuty", "label": "alert notification"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "Alarms on all critical metrics (latency, error rate, capacity)",
            "SNS topics encrypted with KMS",
            "Integration with ServiceNow/PagerDuty for incident management",
        ],
    },

    {
        "id": "7C",
        "name": "Cost Tracking & Optimisation",
        "family": "Monitoring & Observability",
        "reference": "UKHSA Cloud Strategy — Layer 7C",
        "use_case": "FinOps — spend visibility, anomaly detection, and rightsizing",
        "trigger_keywords": [
            "cost", "finops", "cost explorer", "budgets", "cost optimisation",
            "cost optimization", "rightsizing", "tagging", "chargeback", "showback",
        ],
        "aws_services": [
            {"name": "AWS Cost Explorer", "layer": "Managed", "technology": "AWS Cost Explorer"},
            {"name": "AWS Budgets", "layer": "Managed", "technology": "AWS Budgets (threshold alerts)"},
            {"name": "AWS Compute Optimizer", "layer": "Managed", "technology": "AWS Compute Optimizer"},
        ],
        "components": [
            {"name": "AWS Cost Explorer", "layer": "Managed", "technology": "AWS Cost Explorer"},
            {"name": "AWS Budgets", "layer": "Managed", "technology": "AWS Budgets"},
            {"name": "AWS Compute Optimizer", "layer": "Managed", "technology": "AWS Compute Optimizer"},
        ],
        "connections": [
            {"from": "AWS Cost Explorer", "to": "Finance Team", "label": "cost allocation report (tagged by team/project)"},
            {"from": "AWS Budgets", "to": "Amazon SNS (Alerts)", "label": "budget threshold alert"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "Resource tagging policy enforced via SCPs (team, project, environment)",
            "Budget alerts configured per account and OU",
            "Chargeback/showback model implemented (FIN-COA-01, FIN-COB-01)",
            "Data lifecycle policies to prevent indefinite log/observability storage (FIN-COB-02)",
        ],
    },

    # Layer 8 — Resilience
    {
        "id": "8A",
        "name": "Backup & Point-in-Time Recovery",
        "family": "Resilience & DR",
        "reference": "UKHSA Cloud Strategy — Layer 8A",
        "use_case": "Data protection against accidental deletion, corruption, or ransomware",
        "trigger_keywords": [
            "backup", "recovery", "point in time", "pitr", "snapshot",
            "s3 versioning", "aws backup", "restore", "dr", "disaster recovery",
        ],
        "aws_services": [
            {"name": "AWS Backup", "layer": "Managed", "technology": "AWS Backup (centralised backup)"},
            {"name": "Amazon RDS Snapshots", "layer": "Data", "technology": "RDS automated snapshots"},
            {"name": "S3 Versioning", "layer": "Data", "technology": "S3 Versioning + MFA Delete"},
        ],
        "components": [
            {"name": "AWS Backup", "layer": "Managed", "technology": "AWS Backup"},
            {"name": "Amazon S3 (Versioned)", "layer": "Data", "technology": "S3 with Versioning"},
        ],
        "connections": [
            {"from": "AWS Backup", "to": "All Workload Resources", "label": "centralised backup policy"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "AWS Backup vault with KMS encryption and cross-account copy to DR account",
            "S3 versioning + MFA Delete on all critical buckets",
            "RDS automated backups with 30-day retention minimum",
            "Backup RPO/RTO documented in runbook",
        ],
    },

    {
        "id": "8B",
        "name": "Multi-Region Failover",
        "family": "Resilience & DR",
        "reference": "UKHSA Cloud Strategy — Layer 8B",
        "use_case": "Business continuity for critical workloads with low RTO/RPO",
        "trigger_keywords": [
            "multi region", "multi-region", "failover", "route 53 failover",
            "cross region", "disaster recovery", "rto", "rpo", "high availability",
            "active passive", "active active",
        ],
        "aws_services": [
            {"name": "Amazon Route 53 (Failover)", "layer": "Managed", "technology": "Route 53 health-check based failover"},
            {"name": "S3 Cross-Region Replication", "layer": "Data", "technology": "S3 CRR (eu-west-2 → eu-west-1)"},
            {"name": "Amazon RDS Read Replicas", "layer": "Data", "technology": "RDS cross-region read replicas"},
        ],
        "components": [
            {"name": "Amazon Route 53 (Failover Routing)", "layer": "Managed", "technology": "Route 53"},
            {"name": "S3 Cross-Region Replication (CRR)", "layer": "Data", "technology": "S3 CRR"},
            {"name": "RDS Cross-Region Replica", "layer": "Data", "technology": "RDS Read Replica"},
        ],
        "connections": [
            {"from": "Amazon Route 53 (Failover Routing)", "to": "Primary Region", "label": "primary health check"},
            {"from": "Amazon Route 53 (Failover Routing)", "to": "DR Region", "label": "failover on health check failure"},
            {"from": "Primary S3 Bucket", "to": "S3 Cross-Region Replication (CRR)", "label": "continuous replication"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "Route 53 health checks on all critical endpoints",
            "S3 CRR destination bucket in different region with KMS CMK copy",
            "RDS cross-region replica promoted only on confirmed DR event",
            "DR runbook tested quarterly",
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# TARGET STATE NETWORKING PATTERNS  (TSA-NET)
# Source: Target State Architecture §3
# ─────────────────────────────────────────────────────────────────────────────

TSA_NET_PATTERNS: list[dict] = [
    {
        "id": "TSA-NET-01",
        "name": "Hub-and-Spoke (Transit Gateway + Virtual WAN)",
        "family": "Networking",
        "reference": "Target State Architecture §3 — Inter VPC/VNet Pattern 1",
        "use_case": "Centralised routing across multiple VPCs/VNets in multi-account/multi-region",
        "trigger_keywords": [
            "transit gateway", "tgw", "virtual wan", "vwan", "hub spoke",
            "centralised routing", "multi vpc", "multi account routing",
        ],
        "aws_services": [
            {"name": "AWS Transit Gateway", "layer": "Network", "technology": "AWS Transit Gateway"},
            {"name": "AWS Network Firewall", "layer": "Network", "technology": "AWS Network Firewall (east-west inspection)"},
            {"name": "Amazon VPC", "layer": "Network", "technology": "Amazon VPC"},
        ],
        "azure_services": [
            {"name": "Azure Virtual WAN", "layer": "Network", "technology": "Azure Virtual WAN"},
            {"name": "Azure Firewall", "layer": "Network", "technology": "Azure Firewall"},
        ],
        "components": [
            {"name": "AWS Transit Gateway", "layer": "Network", "technology": "AWS TGW"},
            {"name": "AWS Network Firewall", "layer": "Network", "technology": "AWS Network Firewall"},
            {"name": "VPC (Spoke)", "layer": "Network", "technology": "Amazon VPC"},
        ],
        "connections": [
            {"from": "VPC (Spoke)", "to": "AWS Transit Gateway", "label": "TGW attachment"},
            {"from": "AWS Transit Gateway", "to": "AWS Network Firewall", "label": "east-west inspection"},
            {"from": "AWS Transit Gateway", "to": "On-Premises DC", "label": "Direct Connect via TGW"},
        ],
        "data_flows": [],
        "context_entities": [],
        "mandatory_controls": [
            "TGW route tables segment prod/non-prod traffic",
            "Network Firewall inspects east-west traffic",
            "VPC Flow Logs on all attached VPCs",
        ],
    },

    {
        "id": "TSA-NET-02",
        "name": "Centralised Ingress (ALB + WAF)",
        "family": "Networking",
        "reference": "Target State Architecture §3 — Public Ingress Pattern 1",
        "use_case": "Single WAF-protected ingress point for all public-facing workloads",
        "trigger_keywords": [
            "alb", "application load balancer", "waf", "ingress", "public facing",
            "centralised ingress", "load balancer", "https ingress",
        ],
        "aws_services": [
            {"name": "Application Load Balancer", "layer": "Public", "technology": "AWS ALB (HTTPS listener)"},
            {"name": "AWS WAF", "layer": "Public", "technology": "AWS WAF (OWASP managed rules)"},
            {"name": "AWS Certificate Manager", "layer": "Managed", "technology": "AWS ACM (TLS cert)"},
            {"name": "Amazon Route 53", "layer": "Managed", "technology": "Route 53 (DNS routing)"},
        ],
        "components": [
            {"name": "Application Load Balancer", "layer": "Public", "technology": "AWS ALB"},
            {"name": "AWS WAF", "layer": "Public", "technology": "AWS WAF"},
            {"name": "Amazon Route 53", "layer": "Managed", "technology": "Amazon Route 53"},
        ],
        "connections": [
            {"from": "Internet", "to": "AWS WAF", "label": "HTTPS filtered ingress"},
            {"from": "AWS WAF", "to": "Application Load Balancer", "label": "inspected traffic"},
            {"from": "Application Load Balancer", "to": "Application Tier", "label": "to private subnet"},
            {"from": "Amazon Route 53", "to": "Application Load Balancer", "label": "DNS A/ALIAS record"},
        ],
        "data_flows": [
            {"id": "DF-NET-02-01", "source": "Internet", "destination": "Application Tier", "data": "HTTPS requests", "protocol": "HTTPS via WAF + ALB"},
        ],
        "context_entities": [],
        "mandatory_controls": [
            "WAF OWASP Top 10 managed rules enabled",
            "ALB listener on HTTPS only (HTTP → HTTPS redirect)",
            "ACM certificate (TLS 1.2+ — ADR-005)",
            "Access logs to S3 (SSE-KMS)",
        ],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# ARCHITECTURE DECISION RECORDS (ADRs)
# Source: UKHSA Cloud Strategy & Approved Patterns
# ─────────────────────────────────────────────────────────────────────────────

ADRS: list[dict] = [
    {"id": "ADR-001", "decision": "Aurora PostgreSQL is the preferred relational database", "patterns_affected": ["3A"]},
    {"id": "ADR-002", "decision": "Use Amazon S3 + AWS Glue — not HDFS", "patterns_affected": ["3C"]},
    {"id": "ADR-003", "decision": "Use Amazon Redshift Spectrum for queries > 100 GB", "patterns_affected": ["2D", "3B"]},
    {"id": "ADR-004", "decision": "Use Amazon EventBridge over raw SNS/SQS for event routing", "patterns_affected": ["4A"]},
    {"id": "ADR-005", "decision": "TLS 1.2+ minimum for all data in transit", "patterns_affected": ["6B"]},
    {"id": "ADR-006", "decision": "Customer-managed KMS CMKs for all sensitive data", "patterns_affected": ["6B"]},
    {"id": "ADR-007", "decision": "Bronze/Silver/Gold data lake tier naming convention", "patterns_affected": ["3C"]},
    {"id": "ADR-008", "decision": "Multi-cloud strategy: AWS primary analytics, Azure primary SaaS/identity", "patterns_affected": ["UKHSA-INF-01", "UKHSA-INF-05"]},
    {"id": "ADR-009", "decision": "Infrastructure as Code (IaC) mandatory for all cloud resources", "patterns_affected": ["All"]},
    {"id": "ADR-010", "decision": "Zero Trust Network Architecture for all new connectivity", "patterns_affected": ["6A", "6C", "UKHSA-INF-03", "UKHSA-INF-05"]},
]

# ─────────────────────────────────────────────────────────────────────────────
# MANDATORY CONTROLS (always applied regardless of pattern)
# ─────────────────────────────────────────────────────────────────────────────

UKHSA_MANDATORY_CONTROLS: list[str] = [
    "All infrastructure via IaC (Terraform) — ADR-009",
    "All workloads in private subnets — no public resources without WAF (SEC-APS-03)",
    "KMS CMK encryption at rest for all sensitive data — ADR-006",
    "TLS 1.2+ enforced for all data in transit — ADR-005",
    "No local IAM users in any AWS account — federated auth via Entra ID + IAM Identity Center",
    "MFA enforced for all user accounts",
    "AWS CloudTrail org trail with management + S3 data events",
    "Resource tagging mandatory (team, project, environment) for cost allocation",
    "AWS Security Hub and Microsoft Defender for Cloud enabled",
    "Microsoft Sentinel receiving all security logs",
]

# ─────────────────────────────────────────────────────────────────────────────
# COMBINED PATTERN CATALOGUE
# ─────────────────────────────────────────────────────────────────────────────

ALL_UKHSA_PATTERNS: list[dict] = INFRA_PATTERNS + DATA_PATTERNS + TSA_NET_PATTERNS


# ─────────────────────────────────────────────────────────────────────────────
# DETECTION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def detect_ukhsa_patterns(
    components: list[dict],
    connections: list[dict],
    dataflows: list[dict],
    context_entities: list[dict],
    explicit_pattern_ids: list[str] | None = None,
) -> list[dict]:
    """
    Detect which UKHSA patterns apply to the project.

    Scans all project text for trigger keywords from every pattern.
    If explicit_pattern_ids is provided those patterns are always included
    (supports manual override via UKHSA_PATTERN_IDS env var).

    Returns list of matching pattern dicts.
    """
    # Build a single lowercase text corpus from all project elements
    corpus_parts: list[str] = []
    for item in components + connections + dataflows + context_entities:
        for val in item.values():
            if isinstance(val, str):
                corpus_parts.append(val.lower())
    corpus = " ".join(corpus_parts)

    matched: list[dict] = []
    matched_ids: set[str] = set()

    # Keyword-based detection
    for pattern in ALL_UKHSA_PATTERNS:
        if pattern["id"] in matched_ids:
            continue
        for kw in pattern.get("trigger_keywords", []):
            if kw.lower() in corpus:
                matched.append(pattern)
                matched_ids.add(pattern["id"])
                break

    # Explicit override (always add, dedup)
    if explicit_pattern_ids:
        id_lookup = {p["id"]: p for p in ALL_UKHSA_PATTERNS}
        for pid in explicit_pattern_ids:
            pid = pid.strip().upper()
            if pid not in matched_ids and pid in id_lookup:
                matched.append(id_lookup[pid])
                matched_ids.add(pid)

    # Layer 6 patterns are MANDATORY — always include if any data pattern detected
    data_pattern_ids = {p["id"] for p in DATA_PATTERNS}
    if any(p["id"] in data_pattern_ids for p in matched):
        security_ids = {"6A", "6B", "6C"}
        id_lookup = {p["id"]: p for p in ALL_UKHSA_PATTERNS}
        for sid in security_ids:
            if sid not in matched_ids and sid in id_lookup:
                matched.append(id_lookup[sid])
                matched_ids.add(sid)

    return matched


# ─────────────────────────────────────────────────────────────────────────────
# INJECTION FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _dedup(existing: list[dict], new_items: list[dict], key: str = "name") -> list[dict]:
    """Merge new_items into existing, deduplicating by key."""
    existing_keys = {item.get(key, "").lower() for item in existing}
    result = list(existing)
    for item in new_items:
        if item.get(key, "").lower() not in existing_keys:
            result.append(item)
            existing_keys.add(item.get(key, "").lower())
    return result


def inject_ukhsa_into_components(
    components: list[dict],
    matched_patterns: list[dict],
) -> list[dict]:
    """Inject pattern components into the project component list (dedup by name)."""
    for pattern in matched_patterns:
        components = _dedup(components, pattern.get("components", []))
    return components


def inject_ukhsa_into_connections(
    connections: list[dict],
    matched_patterns: list[dict],
) -> list[dict]:
    """Inject pattern connections into the project connection list."""
    for pattern in matched_patterns:
        for conn in pattern.get("connections", []):
            existing_key = (conn["from"].lower(), conn["to"].lower())
            existing_pairs = {(c.get("from", "").lower(), c.get("to", "").lower()) for c in connections}
            if existing_key not in existing_pairs:
                connections.append(conn)
    return connections


def inject_ukhsa_into_dataflows(
    dataflows: list[dict],
    matched_patterns: list[dict],
) -> list[dict]:
    """Inject pattern data flows into the project data flow list (dedup by id)."""
    for pattern in matched_patterns:
        dataflows = _dedup(dataflows, pattern.get("data_flows", []), key="id")
    return dataflows


def inject_ukhsa_into_context_entities(
    context_entities: list[dict],
    matched_patterns: list[dict],
) -> list[dict]:
    """Inject pattern context entities (dedup by name)."""
    for pattern in matched_patterns:
        context_entities = _dedup(context_entities, pattern.get("context_entities", []))
    return context_entities


def get_mandatory_controls_for_patterns(matched_patterns: list[dict]) -> list[str]:
    """Collect all mandatory controls from matched patterns plus the global mandatory controls."""
    controls: list[str] = list(UKHSA_MANDATORY_CONTROLS)
    seen: set[str] = set(controls)
    for pattern in matched_patterns:
        for ctrl in pattern.get("mandatory_controls", []):
            if ctrl not in seen:
                controls.append(ctrl)
                seen.add(ctrl)
    return controls


def build_ukhsa_pattern_summary(matched_patterns: list[dict]) -> str:
    """Return a human-readable summary of detected/applied UKHSA patterns."""
    if not matched_patterns:
        return "No UKHSA patterns detected."

    lines: list[str] = ["UKHSA Patterns Applied:"]
    by_family: dict[str, list[dict]] = {}
    for p in matched_patterns:
        fam = p.get("family", "Other")
        by_family.setdefault(fam, []).append(p)

    for family, patterns in sorted(by_family.items()):
        lines.append(f"\n  [{family}]")
        for p in patterns:
            lines.append(f"    {p['id']}: {p['name']}")
            lines.append(f"      Use case: {p['use_case']}")

    lines.append(f"\n  Mandatory controls: {len(get_mandatory_controls_for_patterns(matched_patterns))} rules applied")
    return "\n".join(lines)


def get_adrs_for_patterns(matched_patterns: list[dict]) -> list[dict]:
    """Return the ADRs relevant to the matched patterns."""
    matched_ids = {p["id"] for p in matched_patterns}
    relevant = []
    for adr in ADRS:
        for affected in adr.get("patterns_affected", []):
            if affected == "All" or affected in matched_ids:
                relevant.append(adr)
                break
    return relevant
