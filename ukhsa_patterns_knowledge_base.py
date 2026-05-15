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
# CONNECTIVITY OPTIONS REFERENCE
# Source:  UKHSA Cloud Strategy & Approved Patterns v1.2 (§ Networking)
#          AWS Networking documentation (Direct Connect, TGW, PrivateLink, VPN)
#          Azure Networking documentation (ExpressRoute, Virtual WAN, Private Endpoint)
#          NCSC Cloud Security Guidance — network architecture
#          Equinix/Megaport inter-cloud fabric documentation
#
# This is the single reference used by diagram generators and the HLD template
# to populate Section 9 "Connectivity & Integration Options" and the cost table.
#
# Structure per option:
#   id              — unique key
#   name            — display name
#   category        — On-Prem→Cloud | Cloud-to-Cloud | Internal-Cloud | Internet-Facing | Zero-Trust
#   applicable_from — list of source environment labels
#   applicable_to   — list of destination environment labels
#   description     — plain-English summary
#   when_to_use     — bullet list of selection criteria
#   when_not_to_use — list of anti-patterns
#   best_practices  — mandatory/recommended controls
#   aws_component   — AWS service name (if applicable)
#   azure_component — Azure service name (if applicable)
#   bandwidth       — typical throughput range
#   latency         — expected latency characteristic
#   redundancy      — HA/failover approach
#   indicative_cost — rough monthly £ guidance (see _XENV costs for precise figures)
#   ukhsa_status    — Approved | Conditional | Not-Approved
#   diagram_style   — edge style token for diagram generator ("solid" | "dashed" | "dotted")
#   diagram_color   — hex color for edge
# ─────────────────────────────────────────────────────────────────────────────

CONNECTIVITY_OPTIONS: list[dict] = [

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY 1 — On-Premises ↔ Cloud
    # ═══════════════════════════════════════════════════════════════════════

    {
        "id": "CONN-01",
        "name": "AWS Direct Connect",
        "category": "On-Prem→Cloud",
        "applicable_from": ["On-Premises DC", "OpenShift (OCP)"],
        "applicable_to": ["AWS"],
        "description": (
            "Dedicated private fibre circuit between UKHSA DC (Porton/Colindale) and "
            "AWS eu-west-2. Traffic never traverses the public internet. "
            "UKHSA uses Virgin Media MPLS to the Direct Connect location, then a "
            "private VIF into AWS Transit Gateway."
        ),
        "when_to_use": [
            "Production workloads requiring consistent bandwidth (>100 Mbps)",
            "Sensitive/OFFICIAL-SENSITIVE data that must not cross public internet",
            "High-volume data transfers (DB replication, EDAP ingestion at scale)",
            "Low-latency requirements (<10 ms on-prem to AWS)",
            "UKHSA primary connectivity — all new hybrid workloads",
        ],
        "when_not_to_use": [
            "Dev/test environments where cost is a concern — use Site-to-Site VPN instead",
            "Temporary connectivity needs (proof-of-concept) — VPN is faster to provision",
            "Small data volumes (<10 GB/month) — cost-benefit does not justify circuit fee",
        ],
        "best_practices": [
            "Terminate Direct Connect into AWS Transit Gateway (TGW) — single hub for all VPCs",
            "Use private VIF (not public VIF) — keeps traffic off internet completely",
            "Enable BGP authentication (MD5) on the virtual interface",
            "Provision at least 2× connections to different DX locations for redundancy (ADR-010 HA)",
            "Add Site-to-Site VPN as cold standby failover path (auto-failover via BGP)",
            "VPC Flow Logs enabled on all attached VPCs",
            "All data in transit encrypted at application layer (TLS 1.2+) even though circuit is private",
            "Monitor with CloudWatch for DirectConnect connection state and BGP status alarms",
        ],
        "aws_component": "AWS Direct Connect + Transit Gateway",
        "azure_component": "N/A",
        "bandwidth": "1 Gbps / 10 Gbps dedicated (sub-1G via hosted connection)",
        "latency": "<10 ms on-prem to AWS eu-west-2",
        "redundancy": "Dual connections + Site-to-Site VPN warm standby",
        "indicative_cost": "£140–£280/mo port fee + £0.02/GB data transfer out of AWS",
        "ukhsa_status": "Approved — primary on-prem→AWS path",
        "availability": "available",   # Live in production — Virgin Media MPLS → DX → AWS TGW
        "diagram_style": "solid",
        "diagram_color": "#FF9900",
    },

    {
        "id": "CONN-02",
        "name": "AWS Site-to-Site VPN",
        "category": "On-Prem→Cloud",
        "applicable_from": ["On-Premises DC", "OpenShift (OCP)", "Remote Site"],
        "applicable_to": ["AWS"],
        "description": (
            "IPsec VPN tunnels over the public internet between UKHSA on-premises "
            "routers and AWS Virtual Private Gateway or Transit Gateway. "
            "Each VPN connection provides two tunnels for redundancy. "
            "Encrypted but subject to internet latency variability."
        ),
        "when_to_use": [
            "Backup / failover path for AWS Direct Connect (cold standby)",
            "Dev/test environments — quick, cheap connectivity",
            "Remote sites or branch offices without Direct Connect",
            "Emergency connectivity when primary circuit is down",
            "Small-volume transfers (<10 GB/month) where Direct Connect cost is not justified",
        ],
        "when_not_to_use": [
            "Primary production connectivity — use Direct Connect instead",
            "High-throughput workloads (>500 Mbps) — VPN throughput is capped",
            "Ultra-low-latency requirements — internet routing adds unpredictable latency",
            "In isolation for OFFICIAL-SENSITIVE data without compensating controls",
        ],
        "best_practices": [
            "Use IKEv2 (not IKEv1) for stronger security",
            "Enable both tunnels and configure BGP for active/active redundancy",
            "Use TGW attachment (not VGW) to allow routing to multiple VPCs",
            "Set Dead Peer Detection (DPD) to clear tunnels rapidly on failure",
            "Combine with Direct Connect: DX primary, VPN warm standby via BGP AS-PATH manipulation",
            "Restrict Security Groups to only accept traffic from known on-prem IP ranges",
            "Log tunnel state changes to CloudWatch and alert on tunnel down",
            "Do NOT store VPN pre-shared keys in code — use Secrets Manager",
        ],
        "aws_component": "AWS Site-to-Site VPN + Transit Gateway",
        "azure_component": "N/A (AWS-specific; see CONN-05 for Azure equivalent)",
        "bandwidth": "Up to 1.25 Gbps per tunnel (2 tunnels per connection = 2.5 Gbps max)",
        "latency": "15–50 ms typical (internet-dependent)",
        "redundancy": "2 tunnels per connection; use as DX warm standby via BGP",
        "indicative_cost": "£30–£50/mo per connection + £0.05/GB data transfer",
        "ukhsa_status": "Approved — dev/test and DX failover only",
        "availability": "available",   # Available — used as DX warm standby and in dev/test accounts
        "diagram_style": "dashed",
        "diagram_color": "#FF9900",
    },

    {
        "id": "CONN-03",
        "name": "Azure ExpressRoute",
        "category": "On-Prem→Cloud",
        "applicable_from": ["On-Premises DC", "OpenShift (OCP)"],
        "applicable_to": ["Azure"],
        "description": (
            "Dedicated private circuit from UKHSA DC to Microsoft Azure via a "
            "connectivity provider (Equinix/Megaport). Traffic does not traverse "
            "the public internet. Terminates into Azure Virtual WAN or ExpressRoute Gateway "
            "and routes to Azure VNets."
        ),
        "when_to_use": [
            "Production workloads on Azure requiring consistent bandwidth",
            "Microsoft 365 / Entra ID integration at scale (reduces internet backhaul)",
            "Sensitive data that must not cross public internet",
            "High-volume data transfers to Azure (EDAP→Azure, Sentinel log ingestion)",
            "UKHSA primary connectivity — all new hybrid on-prem→Azure paths",
        ],
        "when_not_to_use": [
            "Dev/test — use Azure VPN Gateway instead",
            "Low-volume or transient workloads",
            "Azure services that don't support private peering (some SaaS)",
        ],
        "best_practices": [
            "Use Private Peering (not Microsoft Peering) for private Azure PaaS access",
            "Enable ExpressRoute Global Reach only if cross-site on-prem routing is needed",
            "Terminate into Azure Virtual WAN hub for hub-and-spoke routing to all VNets",
            "Deploy two circuits at different peering locations for 99.95% SLA",
            "Add Azure VPN Gateway as warm standby (ExpressRoute + VPN coexistence)",
            "Enable Route Filters to limit BGP prefixes advertised (prevent route leakage)",
            "Configure BFD (Bidirectional Forwarding Detection) for fast failover (<1 s)",
            "All on-prem to Azure traffic encrypted TLS 1.2+ regardless of private circuit",
        ],
        "aws_component": "N/A",
        "azure_component": "Azure ExpressRoute + Azure Virtual WAN",
        "bandwidth": "50 Mbps to 10 Gbps (bandwidth select at provisioning)",
        "latency": "<10 ms on-prem to Azure UK South",
        "redundancy": "Dual circuits at diverse peering locations + VPN warm standby",
        "indicative_cost": "£200–£400/mo circuit fee + £0.02/GB egress from Azure",
        "ukhsa_status": "Approved — primary on-prem→Azure path",
        "availability": "available",   # Live in production — UKHSA DC → ExpressRoute → Azure VWAN
        "diagram_style": "solid",
        "diagram_color": "#0078D4",
    },

    {
        "id": "CONN-04",
        "name": "Azure VPN Gateway (Site-to-Site)",
        "category": "On-Prem→Cloud",
        "applicable_from": ["On-Premises DC", "OpenShift (OCP)", "Remote Site"],
        "applicable_to": ["Azure"],
        "description": (
            "IPsec/IKE VPN tunnels from on-premises devices to Azure VPN Gateway. "
            "Traffic encrypted over the public internet. "
            "Supports Active-Active gateway configuration for redundancy."
        ),
        "when_to_use": [
            "Backup / failover for ExpressRoute (warm standby via BGP)",
            "Dev/test connectivity to Azure — fast to provision, low cost",
            "Remote sites without ExpressRoute circuit",
            "Temporary or short-duration Azure access",
        ],
        "when_not_to_use": [
            "Primary production path — use ExpressRoute instead",
            "High-throughput (>1 Gbps) — VPN Gateway max throughput is limited",
            "Latency-sensitive workloads",
        ],
        "best_practices": [
            "Use VpnGw2 or higher SKU for production (supports BGP and higher throughput)",
            "Enable Active-Active mode (two gateway instances, two tunnels per connection)",
            "Use IKEv2 and AES-256/SHA-256 cipher policies — disable legacy weak ciphers",
            "Use BGP over static routing for automatic failover",
            "Pair with ExpressRoute: ER primary, VPN standby using route preference",
            "Store pre-shared keys in Azure Key Vault — never hardcode",
            "Enable diagnostic logs for VPN gateway and route all to Log Analytics",
        ],
        "aws_component": "N/A (Azure-specific; see CONN-02 for AWS equivalent)",
        "azure_component": "Azure VPN Gateway (Site-to-Site) + Virtual Network Gateway",
        "bandwidth": "Up to 10 Gbps (VpnGw5 SKU); 650 Mbps on VpnGw1",
        "latency": "15–50 ms typical (internet-dependent)",
        "redundancy": "Active-Active with BGP failover; combine with ExpressRoute",
        "indicative_cost": "£160–£420/mo gateway SKU + £0.05/GB egress",
        "ukhsa_status": "Approved — dev/test and ER failover only",
        "availability": "available",   # Available — Azure VPN Gateway can be provisioned on demand
        "diagram_style": "dashed",
        "diagram_color": "#0078D4",
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY 2 — Cloud-to-Cloud (AWS ↔ Azure)
    # ═══════════════════════════════════════════════════════════════════════

    {
        "id": "CONN-05",
        "name": "AWS ↔ Azure via Equinix/Megaport Fabric",
        "category": "Cloud-to-Cloud",
        "applicable_from": ["AWS"],
        "applicable_to": ["Azure"],
        "description": (
            "Dedicated inter-cloud private connection via a neutral co-location "
            "exchange (Equinix or Megaport). AWS Direct Connect and Azure ExpressRoute "
            "circuits both terminate at the exchange fabric, creating a private "
            "AWS→Azure path without traversing the public internet. "
            "UKHSA target state per UKHSA-INF-02 mandatory controls."
        ),
        "when_to_use": [
            "Large-volume data movement between AWS (EDAP) and Azure (Sentinel, Synapse)",
            "Latency-sensitive cross-cloud workloads (<10 ms requirement)",
            "OFFICIAL-SENSITIVE data that must never cross public internet",
            "Target state for all production AWS↔Azure connectivity",
        ],
        "when_not_to_use": [
            "Dev/test — use internet-routed VPN or public endpoints instead",
            "Small data volumes (<100 GB/month) — cost of fabric ports not justified",
        ],
        "best_practices": [
            "Use redundant fabric connections (two cross-connects at same exchange)",
            "Run BGP between AWS TGW and Azure VWAN hub via fabric",
            "Separate routing domains: keep AWS and Azure VRFs/route tables isolated",
            "Encrypt at application layer (TLS 1.2+) even on private fabric",
            "Monitor with both AWS CloudWatch (DX metrics) and Azure Monitor (ER metrics)",
            "Agree an egress cost allocation model — AWS charges ~£0.07/GB leaving AWS",
        ],
        "aws_component": "AWS Direct Connect → Equinix/Megaport fabric",
        "azure_component": "Azure ExpressRoute → Equinix/Megaport fabric",
        "bandwidth": "1–10 Gbps (matches lowest of DX/ER port sizes)",
        "latency": "<5 ms AWS eu-west-2 ↔ Azure UK South (co-located exchange)",
        "redundancy": "Dual cross-connects at exchange + cloud-side circuit redundancy",
        "indicative_cost": "£300–£600/mo fabric port fee + AWS egress ~£0.07/GB",
        "ukhsa_status": "Approved — target state for production AWS↔Azure (UKHSA-INF-02)",
        "availability": "in-progress",  # Target state — not yet provisioned; planned via Equinix/Megaport (UKHSA-INF-02)
        "diagram_style": "solid",
        "diagram_color": "#7B1FA2",
    },

    {
        "id": "CONN-06",
        "name": "AWS ↔ Azure via Internet (IPsec VPN)",
        "category": "Cloud-to-Cloud",
        "applicable_from": ["AWS"],
        "applicable_to": ["Azure"],
        "description": (
            "IPsec tunnels between AWS Virtual Private Gateway (or TGW) and "
            "Azure VPN Gateway over the public internet. "
            "Encrypted but subject to internet routing variability and egress costs. "
            "Interim solution only — Equinix/Megaport fabric is the UKHSA target state."
        ),
        "when_to_use": [
            "Dev/test cross-cloud connectivity",
            "Interim solution before Equinix/Megaport fabric is provisioned",
            "Low-volume (<50 GB/month) cross-cloud data transfers",
            "Emergency connectivity when primary path is unavailable",
        ],
        "when_not_to_use": [
            "Production workloads with OFFICIAL-SENSITIVE data",
            "High-throughput or latency-sensitive paths",
            "Permanent production connectivity — migrate to fabric as soon as feasible",
        ],
        "best_practices": [
            "IKEv2 with AES-256-GCM and SHA-384 HMAC — disable legacy IKEv1 and weak ciphers",
            "Apply TLS 1.2+ at application layer as second encryption layer",
            "Restrict Security Group / NSG rules to specific peer IP ranges",
            "Monitor both ends: AWS CloudWatch VPN tunnel state + Azure VPN Gateway diagnostics",
            "Document as interim with target migration date to CONN-05 (fabric)",
        ],
        "aws_component": "AWS Virtual Private Gateway or TGW VPN attachment",
        "azure_component": "Azure VPN Gateway",
        "bandwidth": "Up to 1.25 Gbps per tunnel",
        "latency": "20–60 ms (internet-dependent)",
        "redundancy": "Two tunnels per connection; Active-Active on Azure side",
        "indicative_cost": "£30–50/mo VPN gateway + AWS egress ~£0.07/GB + Azure egress ~£0.05/GB",
        "ukhsa_status": "Conditional — dev/test and interim only; not for production OFFICIAL-SENSITIVE",
        "availability": "available",   # Available now as interim; must migrate to CONN-05 (fabric) for production
        "diagram_style": "dashed",
        "diagram_color": "#7B1FA2",
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY 3 — Internal Cloud Connectivity (within AWS / within Azure)
    # ═══════════════════════════════════════════════════════════════════════

    {
        "id": "CONN-07",
        "name": "AWS Transit Gateway (Hub-and-Spoke)",
        "category": "Internal-Cloud",
        "applicable_from": ["AWS"],
        "applicable_to": ["AWS"],
        "description": (
            "AWS Transit Gateway acts as a regional network hub connecting all UKHSA "
            "VPCs, Direct Connect, Site-to-Site VPN, and SD-WAN attachments. "
            "Replaces full-mesh VPC peering. All east-west traffic inspected by "
            "AWS Network Firewall before routing."
        ),
        "when_to_use": [
            "All multi-VPC AWS architectures at UKHSA (mandatory per UKHSA-INF-02)",
            "Connecting on-prem (DX/VPN) to multiple VPCs via a single attachment",
            "Centralised egress and east-west traffic inspection",
            "Transitive routing between VPCs that cannot peer directly",
        ],
        "when_not_to_use": [
            "Single-VPC workloads — VPC Peering or VPC Endpoints are simpler and cheaper",
            "Cross-region routing without TGW peering — requires explicit TGW peering setup",
        ],
        "best_practices": [
            "Segment TGW route tables by environment (prod, non-prod, shared-services)",
            "Deploy AWS Network Firewall in a dedicated Inspection VPC attached to TGW",
            "Use blackhole routes in TGW route tables to block unwanted VPC-to-VPC paths",
            "Enable TGW flow logs → S3 / CloudWatch for traffic visibility",
            "Use Resource Access Manager (RAM) for cross-account TGW sharing",
            "Tag all TGW attachments with project, team, environment for cost allocation",
        ],
        "aws_component": "AWS Transit Gateway + AWS Network Firewall",
        "azure_component": "N/A",
        "bandwidth": "50 Gbps per TGW (burst), 10 Gbps per VPC attachment",
        "latency": "<1 ms within region",
        "redundancy": "Multi-AZ by default; TGW is a regional managed service",
        "indicative_cost": "£30–80/mo (attachment hours + data processing @ £0.02/GB)",
        "ukhsa_status": "Approved — mandatory for all multi-VPC AWS at UKHSA",
        "availability": "available",   # Live — AWS Transit Gateway deployed in all UKHSA HALO accounts
        "diagram_style": "solid",
        "diagram_color": "#FF9900",
    },

    {
        "id": "CONN-08",
        "name": "AWS VPC Peering",
        "category": "Internal-Cloud",
        "applicable_from": ["AWS"],
        "applicable_to": ["AWS"],
        "description": (
            "Direct point-to-point encrypted connection between two VPCs. "
            "Traffic stays within AWS backbone. No bandwidth limits, no gateway. "
            "Does NOT support transitive routing — each pair needs its own peering connection."
        ),
        "when_to_use": [
            "Simple two-VPC connectivity where TGW overhead is not justified",
            "Dev/test inter-VPC access",
            "Cross-account access to a shared service VPC (e.g., logging, DNS)",
        ],
        "when_not_to_use": [
            "More than 3–4 VPCs — use TGW instead (VPC Peering creates N² connections)",
            "Anywhere transitive routing is needed (A→B→C) — TGW required",
            "Overlapping CIDR ranges between VPCs",
        ],
        "best_practices": [
            "Ensure non-overlapping CIDR ranges before creating peering (cannot be changed)",
            "Apply least-privilege Security Group rules to peering connections",
            "Accept peering requests only from known, trusted account IDs",
            "Prefer TGW for production multi-VPC architectures",
        ],
        "aws_component": "VPC Peering Connection",
        "azure_component": "N/A (see CONN-10 for Azure equivalent)",
        "bandwidth": "No explicit limit (limited by instance bandwidth)",
        "latency": "<1 ms within region; <5 ms cross-region",
        "redundancy": "AWS-managed, inherently redundant within region",
        "indicative_cost": "£0.01/GB data transfer (same region) / £0.02/GB cross-region",
        "ukhsa_status": "Approved — simple two-VPC or shared-service use cases",
        "availability": "available",   # Available — standard AWS capability in all HALO accounts
        "diagram_style": "solid",
        "diagram_color": "#FF9900",
    },

    {
        "id": "CONN-09",
        "name": "AWS PrivateLink (VPC Endpoint Services)",
        "category": "Internal-Cloud",
        "applicable_from": ["AWS", "OpenShift (OCP)"],
        "applicable_to": ["AWS"],
        "description": (
            "Expose a service (NLB-backed) as a private endpoint consumable by "
            "other VPCs or on-premises without VPC peering or TGW. "
            "Traffic stays on AWS backbone. Solves overlapping-CIDR and "
            "transitive routing limitations of VPC Peering. "
            "Also used by OpenShift clusters to call AWS services privately."
        ),
        "when_to_use": [
            "Expose a shared microservice to multiple consumer VPCs without full peering",
            "Connect OpenShift on-prem to AWS services without public internet",
            "SaaS-style service sharing across AWS accounts/VPCs",
            "Access AWS managed services (S3, SQS, KMS, etc.) from private subnets (Gateway/Interface endpoints)",
        ],
        "when_not_to_use": [
            "Full network access between VPCs — use TGW or VPC Peering instead",
            "UDP-based services — PrivateLink only supports TCP",
            "Where bidirectional initiation is needed (PrivateLink is one-directional consumer→service)",
        ],
        "best_practices": [
            "Use Interface Endpoints (PrivateLink) for all AWS service API calls from private subnets",
            "Use Gateway Endpoints for S3 and DynamoDB (free, preferred over interface endpoints)",
            "Enable Private DNS for VPC Interface Endpoints so service hostnames resolve privately",
            "Restrict endpoint policies to specific IAM principals and actions (least privilege)",
            "Enable VPC Endpoint connection acceptance — require explicit approval for consumer VPCs",
        ],
        "aws_component": "AWS PrivateLink (Interface VPC Endpoints / Endpoint Services)",
        "azure_component": "N/A (see CONN-11 for Azure equivalent)",
        "bandwidth": "10 Gbps per endpoint (burst to 40 Gbps)",
        "latency": "<1 ms within region",
        "redundancy": "Multi-AZ endpoint across all AZs",
        "indicative_cost": "£6–£10/mo per endpoint + £0.01/GB data processed",
        "ukhsa_status": "Approved — mandatory for all AWS PaaS access from private subnets",
        "availability": "available",   # Live — VPC Interface Endpoints in use across EDAP and HALO workloads
        "diagram_style": "solid",
        "diagram_color": "#FF9900",
    },

    {
        "id": "CONN-10",
        "name": "Azure VNet Peering",
        "category": "Internal-Cloud",
        "applicable_from": ["Azure"],
        "applicable_to": ["Azure"],
        "description": (
            "Direct encrypted connectivity between two Azure VNets using Azure backbone. "
            "Supports same-region and cross-region (Global VNet Peering). "
            "Does NOT support transitive routing — use Azure Virtual WAN for hub-and-spoke."
        ),
        "when_to_use": [
            "Simple two-VNet connectivity",
            "Cross-account (cross-subscription) VNet access to shared services",
            "Dev/test inter-VNet access",
        ],
        "when_not_to_use": [
            "More than 3–4 VNets — use Azure Virtual WAN instead",
            "Transitive routing required (A→B→C)",
            "Overlapping address spaces",
        ],
        "best_practices": [
            "Set 'Allow forwarded traffic' only if explicitly required",
            "Disable 'Allow gateway transit' unless specifically using hub-spoke model",
            "Apply NSG rules to subnets to restrict lateral movement over peering",
            "Prefer Virtual WAN for production multi-VNet UKHSA architectures",
        ],
        "aws_component": "N/A (see CONN-08 for AWS equivalent)",
        "azure_component": "Azure VNet Peering",
        "bandwidth": "Limited by VM NIC bandwidth (not the peering itself)",
        "latency": "<2 ms same region; varies for global peering",
        "redundancy": "Azure-managed, inherently redundant",
        "indicative_cost": "£0.01–0.02/GB inbound + outbound (same region); higher cross-region",
        "ukhsa_status": "Approved — simple two-VNet or shared-service use cases",
        "availability": "available",   # Available — standard Azure capability in all PHECloud subscriptions
        "diagram_style": "solid",
        "diagram_color": "#0078D4",
    },

    {
        "id": "CONN-11",
        "name": "Azure Private Endpoint",
        "category": "Internal-Cloud",
        "applicable_from": ["Azure", "On-Premises DC", "OpenShift (OCP)"],
        "applicable_to": ["Azure"],
        "description": (
            "Private IP address inside a VNet connected to an Azure PaaS service "
            "(Storage, SQL, Key Vault, Service Bus, etc.). "
            "Traffic never leaves Azure backbone. Disables public endpoint on the service. "
            "Used by OpenShift to access Azure PaaS privately via ExpressRoute."
        ),
        "when_to_use": [
            "All production Azure PaaS services (Storage, SQL, Key Vault, Service Bus) — mandatory",
            "On-prem or OCP access to Azure PaaS over ExpressRoute without public internet",
            "Any service handling OFFICIAL-SENSITIVE or above data",
        ],
        "when_not_to_use": [
            "Dev/test with public endpoints only — but still preferred even in dev",
            "Services that do not support Private Endpoints (check Azure docs)",
        ],
        "best_practices": [
            "Disable public network access on the PaaS service immediately after Private Endpoint creation",
            "Use Private DNS Zones (privatelink.*.core.windows.net etc.) for correct name resolution",
            "Deploy Private DNS Zones centrally in hub VNet and link to spoke VNets",
            "Apply NSG to the subnet containing the Private Endpoint (NSG support is now GA)",
            "On-prem DNS: configure conditional forwarders to Azure DNS Private Resolver",
        ],
        "aws_component": "N/A (see CONN-09 for AWS equivalent)",
        "azure_component": "Azure Private Endpoint + Private DNS Zone",
        "bandwidth": "Limited by service and VM bandwidth",
        "latency": "<1 ms within region",
        "redundancy": "Azure zone-redundant (for ZR PaaS services)",
        "indicative_cost": "£6–£8/mo per endpoint + £0.01/GB data processed",
        "ukhsa_status": "Approved — mandatory for all Azure PaaS in production",
        "availability": "available",   # Live — Azure Private Endpoints deployed across PHECloud PaaS services
        "diagram_style": "solid",
        "diagram_color": "#0078D4",
    },

    {
        "id": "CONN-12",
        "name": "Azure Virtual WAN (Hub-and-Spoke)",
        "category": "Internal-Cloud",
        "applicable_from": ["Azure"],
        "applicable_to": ["Azure"],
        "description": (
            "Microsoft-managed network hub connecting all UKHSA Azure VNets, "
            "ExpressRoute circuits, and VPN connections. "
            "Equivalent to AWS Transit Gateway. Provides centralised routing, "
            "Azure Firewall integration, and automated spoke VNet connections."
        ),
        "when_to_use": [
            "All multi-VNet Azure architectures at UKHSA (mandatory for new deployments)",
            "Centralised firewall inspection for east-west and north-south Azure traffic",
            "Connecting on-prem (ExpressRoute/VPN) to multiple Azure VNets",
        ],
        "when_not_to_use": [
            "Single-VNet deployments — direct peering is simpler",
            "Azure Virtual WAN Standard tier required for Azure Firewall — check budget",
        ],
        "best_practices": [
            "Deploy Secured Virtual Hub (Virtual WAN + Azure Firewall) for production",
            "Use routing intent to force all internet-bound and private traffic through Azure Firewall",
            "Separate Virtual WAN hubs per region — do not extend a single hub globally",
            "Use Azure Monitor + NSG flow logs for traffic visibility",
            "Apply RBAC to prevent spoke VNets from modifying hub routing",
        ],
        "aws_component": "N/A (see CONN-07 for AWS equivalent)",
        "azure_component": "Azure Virtual WAN (Standard) + Azure Firewall",
        "bandwidth": "20 Gbps per hub (aggregate)",
        "latency": "<1 ms within region",
        "redundancy": "Zone-redundant managed service",
        "indicative_cost": "£200–£400/mo hub fee + £0.02/GB data processed",
        "ukhsa_status": "Approved — mandatory for multi-VNet Azure at UKHSA",
        "availability": "available",   # Live — Azure Virtual WAN deployed in PHECloud hub
        "diagram_style": "solid",
        "diagram_color": "#0078D4",
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY 4 — Internet-Facing Connectivity
    # ═══════════════════════════════════════════════════════════════════════

    {
        "id": "CONN-13",
        "name": "AWS Internet Gateway + WAF + CloudFront",
        "category": "Internet-Facing",
        "applicable_from": ["Internet / External Users"],
        "applicable_to": ["AWS"],
        "description": (
            "Standard AWS internet ingress pattern: Internet Gateway for VPC internet routing, "
            "CloudFront CDN for edge caching and DDoS mitigation, "
            "AWS WAF for L7 inspection and bot protection, "
            "Application Load Balancer in public subnet terminating TLS."
        ),
        "when_to_use": [
            "Public-facing APIs or web applications hosted on AWS",
            "External data collection endpoints (e.g., survey forms, public health portals)",
            "Any workload receiving traffic from the internet",
        ],
        "when_not_to_use": [
            "Internal-only workloads — use PrivateLink / Direct Connect only",
            "OFFICIAL-SENSITIVE data APIs should use private connectivity not public internet",
        ],
        "best_practices": [
            "WAF is MANDATORY for all public-facing endpoints (SEC-APS-03)",
            "Use CloudFront with AWS Shield Standard (free) for DDoS mitigation",
            "Enable AWS Shield Advanced for critical public services",
            "ALB access logs and WAF logs to S3 + CloudWatch",
            "HTTPS only — redirect HTTP 301 to HTTPS; use ACM for TLS certificates",
            "Set Content-Security-Policy, HSTS, X-Frame-Options headers",
            "Restrict Security Group on ALB to 0.0.0.0/0:443 only (no port 80 pass-through)",
            "Use Cognito or API Gateway authoriser for authenticated public APIs",
        ],
        "aws_component": "Internet Gateway + CloudFront + WAF + ALB + ACM",
        "azure_component": "N/A",
        "bandwidth": "No explicit limit (CloudFront scales automatically)",
        "latency": "Depends on CloudFront PoP proximity to user",
        "redundancy": "CloudFront global edge network; Multi-AZ ALB",
        "indicative_cost": "£20–100/mo depending on request volume and WAF rule sets",
        "ukhsa_status": "Approved — mandatory WAF for all public endpoints",
        "availability": "available",   # Live — Internet Gateway + CloudFront + WAF in use on HALO public workloads
        "diagram_style": "dotted",
        "diagram_color": "#DD344C",
    },

    {
        "id": "CONN-14",
        "name": "Azure Front Door + Azure WAF",
        "category": "Internet-Facing",
        "applicable_from": ["Internet / External Users"],
        "applicable_to": ["Azure"],
        "description": (
            "Azure global load balancer providing CDN, SSL offload, WAF, and "
            "health-based routing for internet-facing Azure workloads. "
            "Azure WAF (OWASP Core Rule Set) provides L7 protection."
        ),
        "when_to_use": [
            "Public-facing Azure App Service, AKS, or API Management workloads",
            "Multi-region Azure deployments needing global traffic routing",
            "APIs published via Azure APIM with external consumers",
        ],
        "when_not_to_use": [
            "Internal-only Azure workloads — use Private Endpoints instead",
        ],
        "best_practices": [
            "Azure WAF OWASP 3.2 ruleset mandatory for all production endpoints",
            "Enable Azure DDoS Network Protection on public VNets",
            "HTTPS only with TLS 1.2 minimum policy",
            "Lock App Service / AKS ingress to accept traffic only from Front Door IPs",
            "Diagnostic logs to Log Analytics (linked to Microsoft Sentinel)",
        ],
        "aws_component": "N/A (see CONN-13 for AWS equivalent)",
        "azure_component": "Azure Front Door (Standard/Premium) + Azure WAF Policy",
        "bandwidth": "Scales globally with Azure edge PoPs",
        "latency": "Depends on Front Door PoP proximity",
        "redundancy": "Global anycast — inherently multi-region",
        "indicative_cost": "£50–200/mo depending on origin routing rules and WAF policies",
        "ukhsa_status": "Approved — mandatory WAF for all public Azure endpoints",
        "availability": "available",   # Live — Azure Front Door + WAF in use for APIM and Azure App Service workloads
        "diagram_style": "dotted",
        "diagram_color": "#0078D4",
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY 5 — Zero Trust / SASE
    # ═══════════════════════════════════════════════════════════════════════

    {
        "id": "CONN-15",
        "name": "zScaler Private Access (ZPA) — Zero Trust App Access",
        "category": "Zero-Trust",
        "applicable_from": ["End User Devices", "Remote Workers"],
        "applicable_to": ["AWS", "Azure", "On-Premises DC", "OpenShift (OCP)"],
        "description": (
            "zScaler ZPA replaces traditional VPN for end-user access to private applications. "
            "Users connect to an application proxy via the ZTE cloud; no network-level access granted. "
            "Identity verified via Microsoft Entra ID before any application session. "
            "UKHSA target state per ADR-010 Zero Trust Network Architecture."
        ),
        "when_to_use": [
            "All end-user remote access to private cloud or on-prem applications (replaces VPN)",
            "Third-party / partner access to internal systems without network-level exposure",
            "Developer access to cloud management planes",
            "Any access pattern where least-privilege per-application access is needed",
        ],
        "when_not_to_use": [
            "Machine-to-machine (M2M) or service-account connectivity — use PrivateLink or DX instead",
            "High-bandwidth bulk data transfer (ZPA is optimised for interactive/API sessions)",
        ],
        "best_practices": [
            "Integrate ZPA with Microsoft Entra ID (Conditional Access) — block access without MFA",
            "Use App Connectors deployed in private subnets (no inbound firewall rules needed)",
            "Segment applications into ZPA Segment Groups — staff see only their authorised apps",
            "Enable Continuous Trust Assessment — terminate session if device posture degrades",
            "Log all ZPA sessions to Microsoft Sentinel (SIEM) via ZPA Log Streaming",
            "Remove Site-to-Site VPN once ZPA covers all user-facing applications",
        ],
        "aws_component": "ZPA App Connector on EC2 in private subnet",
        "azure_component": "ZPA App Connector on Azure VM in private subnet",
        "bandwidth": "Suitable for interactive sessions; not bulk transfer",
        "latency": "5–20 ms overhead vs direct (identity verification at ZTE PoP)",
        "redundancy": "Multiple ZTE PoPs; deploy App Connectors in multiple AZs",
        "indicative_cost": "Licensing per user (contact zScaler) — no per-GB data cost",
        "ukhsa_status": "Approved — target state for all end-user access (ADR-010)",
        "availability": "in-progress",  # Deployment in progress — replacing legacy VPN for end-user access (ADR-010 target)
        "diagram_style": "dashed",
        "diagram_color": "#1565C0",
    },

    {
        "id": "CONN-16",
        "name": "zScaler Internet Access (ZIA) — Secure Internet Egress",
        "category": "Zero-Trust",
        "applicable_from": ["End User Devices", "Cloud Workloads (outbound)"],
        "applicable_to": ["Internet"],
        "description": (
            "All outbound internet traffic from UKHSA devices and workloads "
            "routed through zScaler ZIA for SSL inspection, URL filtering, "
            "DLP scanning, and threat protection. "
            "Removes requirement for on-premises internet backhaul proxy. "
            "UKHSA target state for internet egress."
        ),
        "when_to_use": [
            "All UKHSA end-user devices requiring internet access",
            "Cloud workload outbound internet traffic where content inspection is needed",
            "Replacing on-premises web proxy (Bluecoat/Squid) for cloud-first egress",
        ],
        "when_not_to_use": [
            "Machine-to-machine API calls to known trusted endpoints — use Security Groups/NSG allowlists",
        ],
        "best_practices": [
            "Enable SSL inspection for all categories (except banking/medical exclusions per policy)",
            "Configure Cloud Firewall policies to block unknown/uncategorised destinations",
            "Route cloud workload egress via ZIA using PAC file or GRE/IPsec tunnel to ZTE",
            "Log all ZIA events to Microsoft Sentinel",
            "Disable direct on-prem internet backhaul once ZIA deployed (remove hairpin)",
        ],
        "aws_component": "ZIA via GRE tunnel from AWS NAT Gateway / TGW",
        "azure_component": "ZIA via GRE tunnel from Azure VWAN or NVA",
        "bandwidth": "Scales with ZTE PoP capacity",
        "latency": "2–10 ms at nearest ZTE PoP",
        "redundancy": "ZScaler global PoP network (99.999% SLA)",
        "indicative_cost": "Licensing per user — no per-GB cost",
        "ukhsa_status": "Approved — target state for secure internet egress",
        "availability": "in-progress",  # Deployment in progress — replacing on-prem internet backhaul hairpin
        "diagram_style": "dotted",
        "diagram_color": "#1565C0",
    },

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY 6 — OpenShift ↔ Cloud (internal cross-environment)
    # ═══════════════════════════════════════════════════════════════════════

    {
        "id": "CONN-17",
        "name": "OpenShift → AWS via AWS PrivateLink",
        "category": "On-Prem→Cloud",
        "applicable_from": ["OpenShift (OCP)"],
        "applicable_to": ["AWS"],
        "description": (
            "OpenShift pods call AWS services (S3, SQS, RDS, Lambda) via AWS PrivateLink "
            "Interface Endpoints. Traffic flows over the existing Direct Connect circuit "
            "from on-prem DC to AWS, then via private VIF to TGW, to the endpoint. "
            "No public internet traversal."
        ),
        "when_to_use": [
            "OCP workloads writing data to EDAP (S3 staging buckets)",
            "OCP services calling AWS Lambda / SQS for event-driven integration",
            "OCP databases connecting to RDS/Aurora read replicas in AWS",
        ],
        "when_not_to_use": [
            "High-bandwidth bulk transfer (>500 Mbps) — Direct Connect bandwidth is shared with DC",
        ],
        "best_practices": [
            "Use IAM Roles for Service Accounts (IRSA) or external-secrets-operator with AWS Secrets Manager",
            "Kubernetes NetworkPolicy: deny all by default, allow only specific pods to call AWS endpoints",
            "Do not store AWS credentials in OCP secrets — use workload identity / IRSA",
            "mTLS between OCP and AWS API endpoints where supported",
        ],
        "aws_component": "AWS PrivateLink Interface Endpoints + Direct Connect (shared)",
        "azure_component": "N/A",
        "bandwidth": "Shared with Direct Connect circuit capacity",
        "latency": "<10 ms OCP pod to AWS endpoint (same DC–cloud latency as DX)",
        "redundancy": "Relies on Direct Connect redundancy (dual DX circuits)",
        "indicative_cost": "£6–10/mo per interface endpoint + DX data transfer",
        "ukhsa_status": "Approved",
        "availability": "in-progress",  # Dependent on OCP cluster connectivity being established — available once OCP provisioned
        "diagram_style": "solid",
        "diagram_color": "#CC0000",
    },

    {
        "id": "CONN-18",
        "name": "OpenShift → Azure via ExpressRoute Private Peering",
        "category": "On-Prem→Cloud",
        "applicable_from": ["OpenShift (OCP)"],
        "applicable_to": ["Azure"],
        "description": (
            "OCP pods access Azure PaaS (Key Vault, Storage, Service Bus) via "
            "Azure Private Endpoints reachable over the ExpressRoute private peering "
            "from the on-premises DC. No public internet traversal."
        ),
        "when_to_use": [
            "OCP services consuming Azure Key Vault secrets or certificates",
            "OCP writing to Azure Blob Storage or Azure Service Bus",
            "OCP authentication via Microsoft Entra ID workload identity (OIDC)",
        ],
        "when_not_to_use": [
            "Workloads that can run natively on Azure AKS — avoid OCP→Azure latency",
        ],
        "best_practices": [
            "Use Microsoft Entra Workload Identity for OCP pods (OIDC federation) — no client secrets",
            "Azure Private DNS Resolver configured with on-prem DNS forwarder for privatelink zones",
            "Kubernetes NetworkPolicy restricts Azure endpoint access to authorised namespaces only",
        ],
        "aws_component": "N/A",
        "azure_component": "Azure Private Endpoint + ExpressRoute Private Peering",
        "bandwidth": "Shared with ExpressRoute circuit capacity",
        "latency": "<10 ms OCP to Azure endpoint",
        "redundancy": "Dual ExpressRoute circuits",
        "indicative_cost": "Marginal (shared ER circuit) + £6–8/mo per Private Endpoint",
        "ukhsa_status": "Approved",
        "availability": "in-progress",  # Dependent on OCP cluster connectivity being established — available once OCP provisioned
        "diagram_style": "solid",
        "diagram_color": "#CC0000",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# CONNECTIVITY SELECTION GUIDE
# Quick-pick matrix: source environment × destination environment → recommended option(s)
# ─────────────────────────────────────────────────────────────────────────────

CONNECTIVITY_SELECTION_GUIDE: dict[tuple[str, str], dict] = {
    ("On-Premises DC", "AWS"): {
        "primary":   "CONN-01",  # Direct Connect
        "secondary": "CONN-02",  # Site-to-Site VPN (failover)
        "note": "DX primary — VPN as BGP warm standby failover",
    },
    ("On-Premises DC", "Azure"): {
        "primary":   "CONN-03",  # ExpressRoute
        "secondary": "CONN-04",  # Azure VPN Gateway (failover)
        "note": "ER primary — Azure VPN Gateway warm standby",
    },
    ("On-Premises DC", "OpenShift (OCP)"): {
        "primary":   None,       # Internal LAN
        "secondary": None,
        "note": "Internal LAN / SDN — no cloud cost",
    },
    ("OpenShift (OCP)", "AWS"): {
        "primary":   "CONN-17",  # PrivateLink over DX
        "secondary": "CONN-02",  # VPN fallback
        "note": "PrivateLink over shared Direct Connect circuit",
    },
    ("OpenShift (OCP)", "Azure"): {
        "primary":   "CONN-18",  # ExpressRoute private peering
        "secondary": "CONN-04",  # Azure VPN
        "note": "Shared ExpressRoute private peering",
    },
    ("AWS", "Azure"): {
        "primary":   "CONN-05",  # Equinix/Megaport fabric (target state)
        "secondary": "CONN-06",  # Internet VPN (interim)
        "note": "Fabric is UKHSA target state — VPN is interim only",
    },
    ("AWS", "AWS"): {
        "primary":   "CONN-07",  # Transit Gateway
        "secondary": "CONN-09",  # PrivateLink for service access
        "note": "TGW for VPC routing; PrivateLink for service endpoints",
    },
    ("Azure", "Azure"): {
        "primary":   "CONN-12",  # Virtual WAN
        "secondary": "CONN-11",  # Private Endpoint for PaaS
        "note": "Virtual WAN for VNet routing; Private Endpoint for PaaS",
    },
    ("End User", "AWS"): {
        "primary":   "CONN-15",  # ZPA
        "secondary": "CONN-13",  # Internet + WAF (for public APIs)
        "note": "ZPA for private access; Internet+WAF for public APIs only",
    },
    ("End User", "Azure"): {
        "primary":   "CONN-15",  # ZPA
        "secondary": "CONN-14",  # Azure Front Door + WAF (public APIs)
        "note": "ZPA for private access; Front Door+WAF for public APIs",
    },
    ("Internet / External", "AWS"): {
        "primary":   "CONN-13",  # Internet Gateway + WAF + CloudFront
        "secondary": None,
        "note": "WAF mandatory — no public access without WAF",
    },
    ("Internet / External", "Azure"): {
        "primary":   "CONN-14",  # Azure Front Door + WAF
        "secondary": None,
        "note": "WAF mandatory — no public access without WAF",
    },
}


def get_connectivity_options_for(
    source_env: str,
    dest_env: str,
) -> list[dict]:
    """
    Return CONNECTIVITY_OPTIONS entries applicable for a given source→destination pair.
    Performs case-insensitive partial-match lookup.
    """
    src_lc = source_env.lower()
    dst_lc = dest_env.lower()
    results = []
    for opt in CONNECTIVITY_OPTIONS:
        src_match = any(src_lc in s.lower() or s.lower() in src_lc for s in opt["applicable_from"])
        dst_match = any(dst_lc in s.lower() or s.lower() in dst_lc for s in opt["applicable_to"])
        if src_match and dst_match:
            results.append(opt)
    return results


def get_connectivity_selection(source_env: str, dest_env: str) -> dict | None:
    """Return the selection guide entry (primary/secondary/note) for a source→dest pair."""
    for (src, dst), guide in CONNECTIVITY_SELECTION_GUIDE.items():
        if source_env.lower() in src.lower() or src.lower() in source_env.lower():
            if dest_env.lower() in dst.lower() or dst.lower() in dest_env.lower():
                return guide
    return None


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
