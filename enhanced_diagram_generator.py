"""
enhanced_diagram_generator.py
────────────────────────────
Generates advanced draw.io diagrams with:
- AWS service-specific icons and styling
- Authentication flow sequences
- Network segregation layers
- Detailed data flow annotations
"""

import xml.etree.ElementTree as ET
import re
import math


# ── AWS Icon URL Mapping ────────────────────────────────────────────────

AWS_ICON_URLS = {
    "API Gateway": "https://d1.awsstatic.com/webp/architecture-icons/arch_featured-services/arch_amazon-api-gateway_64@5x.webp",
    "Lambda": "https://d1.awsstatic.com/webp/architecture-icons/compute/arch_aws-lambda_64@5x.webp",
    "RDS": "https://d1.awsstatic.com/webp/architecture-icons/databases/arch_amazon-rds_64@5x.webp",
    "DynamoDB": "https://d1.awsstatic.com/webp/architecture-icons/databases/arch_amazon-dynamodb_64@5x.webp",
    "S3": "https://d1.awsstatic.com/webp/architecture-icons/storage/arch_amazon-s3_64@5x.webp",
    "CloudFront": "https://d1.awsstatic.com/webp/architecture-icons/networking-content-delivery/arch_amazon-cloudfront_64@5x.webp",
    "VPC": "https://d1.awsstatic.com/webp/architecture-icons/networking-content-delivery/arch_amazon-vpc_64@5x.webp",
    "Security Group": "https://d1.awsstatic.com/webp/architecture-icons/security-identity-compliance/arch_aws-security-groups_64@5x.webp",
    "Cognito": "https://d1.awsstatic.com/webp/architecture-icons/security-identity-compliance/arch_amazon-cognito_64@5x.webp",
    "KMS": "https://d1.awsstatic.com/webp/architecture-icons/security-identity-compliance/arch_aws-key-management-service_64@5x.webp",
    "CloudWatch": "https://d1.awsstatic.com/webp/architecture-icons/management-governance/arch_amazon-cloudwatch_64@5x.webp",
    "MSK": "https://d1.awsstatic.com/webp/architecture-icons/analytics/arch_amazon-msk_64@5x.webp",
    "EKS": "https://d1.awsstatic.com/webp/architecture-icons/compute/arch_amazon-eks_64@5x.webp",
    "EC2": "https://d1.awsstatic.com/webp/architecture-icons/compute/arch_amazon-ec2_64@5x.webp",
    "ALB": "https://d1.awsstatic.com/webp/architecture-icons/networking-content-delivery/arch_elastic-load-balancing_64@5x.webp",
}

SERVICE_TO_ICON_TYPE = {
    "cloudfront": "CloudFront",
    "api gateway": "API Gateway",
    "lambda": "Lambda",
    "rds": "RDS",
    "aurora": "RDS",
    "dynamodb": "DynamoDB",
    "s3": "S3",
    "cognito": "Cognito",
    "kms": "KMS",
    "msk": "MSK",
    "eks": "EKS",
    "ec2": "EC2",
    "alb": "ALB",
    "load balancer": "ALB",
}


def get_aws_icon_type(service_name: str) -> str | None:
    """Return AWS icon type for a service name."""
    name_lower = service_name.lower()
    for key, icon_type in SERVICE_TO_ICON_TYPE.items():
        if key in name_lower:
            return icon_type
    return None


# ── Enhanced Architecture Diagram with AWS Icons ────────────────────────

def generate_aws_architecture_with_icons(components: list[dict], connections: list[dict]) -> str:
    """
    Generate solution architecture diagram with AWS service icons and detailed styling.
    """
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="AWS Solution Architecture")
    ET.SubElement(diagram, "mxGraphModel",
                  dx="1600", dy="900", grid="1", gridSize="10", guides="1",
                  tooltips="1", connect="1", arrows="1", fold="1",
                  page="0", pageScale="1", pageWidth="1400", pageHeight="900",
                  math="0", shadow="0")
    root = ET.SubElement(diagram.find("mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    # Layer definitions with colors
    LAYER_ORDER = ["Edge", "Network", "Platform", "Application", "Data"]
    LAYER_COLORS = {
        "Edge": {"bg": "#FF9900", "border": "#FF6600"},
        "Network": {"bg": "#146EB4", "border": "#0A4C8C"},
        "Platform": {"bg": "#759C3E", "border": "#5A7C2F"},
        "Application": {"bg": "#4B9BFF", "border": "#2A6EC9"},
        "Data": {"bg": "#FF9900", "border": "#FF6600"},
    }

    # Group by layer
    layer_map = {l: [] for l in LAYER_ORDER}
    for comp in components:
        layer = comp.get("layer", "Application").strip()
        for known in LAYER_ORDER:
            if known.lower() in layer.lower() or layer.lower() in known.lower():
                layer_map[known].append(comp)
                break
        else:
            layer_map["Application"].append(comp)

    # Calculate positions
    y_cursor = 30
    layer_y = {}
    LAYER_HEIGHT = 120
    BOX_W, BOX_H = 140, 100

    for layer in LAYER_ORDER:
        if layer_map[layer]:
            layer_y[layer] = y_cursor
            # Add layer background band
            band_height = LAYER_HEIGHT
            band = ET.SubElement(root, "mxCell",
                id=f"band-{layer.lower()}",
                style=f"rounded=0;fillColor={LAYER_COLORS[layer]['bg']}33;strokeColor={LAYER_COLORS[layer]['border']};strokeWidth=2;dashed=1;",
                parent="1", vertex="1")
            ET.SubElement(band, "mxGeometry",
                x="10", y=str(y_cursor - 20),
                width="1380", height=str(band_height),
                **{"as": "geometry"})

            # Layer label
            label = ET.SubElement(root, "mxCell",
                id=f"lbl-{layer.lower()}",
                value=f"{layer} Layer",
                style=f"fontSize=14;fontStyle=1;fillColor={LAYER_COLORS[layer]['bg']};strokeColor={LAYER_COLORS[layer]['border']};textOpacity=80;",
                parent="1", vertex="1")
            ET.SubElement(label, "mxGeometry",
                x="10", y=str(y_cursor - 20),
                width="100", height="25",
                **{"as": "geometry"})

            y_cursor += LAYER_HEIGHT + 30

    # Place components with icons
    comp_cell = {}
    x_counter = {layer: 140 for layer in LAYER_ORDER}

    for layer in LAYER_ORDER:
        for comp in layer_map[layer]:
            comp_name = comp["name"]
            tech = comp.get("technology", "")
            desc = comp.get("description", "")

            cell_id = f"c-{comp_name.lower().replace(' ', '-')}"
            comp_cell[comp_name.lower()] = cell_id

            icon_type = get_aws_icon_type(tech)
            icon_url = AWS_ICON_URLS.get(icon_type, "") if icon_type else ""

            x = x_counter[layer]
            y = layer_y[layer] + 20

            # Component box with icon and label
            style = f"rounded=1;fillColor={LAYER_COLORS[layer]['bg']};strokeColor={LAYER_COLORS[layer]['border']};strokeWidth=2;"
            if icon_url:
                style += f"image={icon_url};imageAspect=1;"

            cell = ET.SubElement(root, "mxCell",
                id=cell_id,
                value=f"{comp_name}\n({tech})\n{desc}",
                style=style,
                parent="1", vertex="1")
            ET.SubElement(cell, "mxGeometry",
                x=str(x), y=str(y),
                width=str(BOX_W), height=str(BOX_H),
                **{"as": "geometry"})

            x_counter[layer] += BOX_W + 20

    # Add connections with labels and step numbers
    for i, conn in enumerate(connections):
        src = comp_cell.get(conn["from"].lower())
        tgt = comp_cell.get(conn["to"].lower())
        if not src or not tgt:
            continue

        label = conn.get("label", "")
        edge = ET.SubElement(root, "mxCell",
            id=f"e-{i}",
            value=label,
            style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;fontSize=11;fontStyle=1;",
            parent="1", source=src, target=tgt, edge="1")
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


# ── Authentication Flow Diagram ──────────────────────────────────────────

def generate_authentication_flow_diagram() -> str:
    """
    Generate a sequence diagram for the authentication flow.
    Shows: User -> Web App -> API Gateway -> Identity Provider -> Service -> DB
    """
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="Authentication Flow Sequence")
    graph_model = ET.SubElement(diagram, "mxGraphModel",
                                dx="1400", dy="800", grid="1", gridSize="10", guides="1",
                                tooltips="1", connect="1", arrows="1", fold="1")

    # Define the sequence diagram elements
    user = ET.SubElement(graph_model, "User", label="User")
    web_app = ET.SubElement(graph_model, "WebApp", label="Web App")
    api_gateway = ET.SubElement(graph_model, "APIGateway", label="API Gateway")
    identity_provider = ET.SubElement(graph_model, "IdentityProvider", label="Identity Provider")
    service = ET.SubElement(graph_model, "Service", label="Service")
    database = ET.SubElement(graph_model, "Database", label="Database")

    # Define the sequence flow
    ET.SubElement(graph_model, "Sequence", source=user, target=web_app, label="Login Request")
    ET.SubElement(graph_model, "Sequence", source=web_app, target=api_gateway, label="API Call")
    ET.SubElement(graph_model, "Sequence", source=api_gateway, target=identity_provider, label="Token Validation")
    ET.SubElement(graph_model, "Sequence", source=identity_provider, target=service, label="Service Request")
    ET.SubElement(graph_model, "Sequence", source=service, target=database, label="Data Query")

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


# ── Network Segregation Diagram ──────────────────────────────────────────

def generate_network_segregation_diagram() -> str:
    """
    Generate network segmentation diagram showing VPC, subnets, security groups, and routing.
    """
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name="Network Segregation")
    ET.SubElement(diagram, "mxGraphModel",
                  dx="1400", dy="1000", grid="1", gridSize="10", guides="1",
                  tooltips="1", connect="1", arrows="1", fold="1",
                  page="0", pageScale="1", pageWidth="1400", pageHeight="1000",
                  math="0", shadow="0")
    root = ET.SubElement(diagram.find("mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    # Internet boundary
    internet = ET.SubElement(root, "mxCell",
        id="internet",
        value="Internet (0.0.0.0/0)",
        style="rounded=1;fillColor=#FFE6CC;strokeColor=#FF8800;strokeWidth=3;fontSize=12;fontStyle=1;",
        parent="1", vertex="1")
    ET.SubElement(internet, "mxGeometry", x="50", y="20", width="1300", height="60", **{"as": "geometry"})

    # Internet Gateway
    igw = ET.SubElement(root, "mxCell",
        id="igw",
        value="Internet Gateway\n(IGW)",
        style="rounded=1;fillColor=#4B9BFF;strokeColor=#2A6EC9;fontSize=10;fontStyle=1;",
        parent="1", vertex="1")
    ET.SubElement(igw, "mxGeometry", x="600", y="110", width="120", height="60", **{"as": "geometry"})

    # Edge connection
    edge_igw = ET.SubElement(root, "mxCell",
        id="edge-internet-igw",
        style="edgeStyle=orthogonalEdgeStyle;rounded=1;",
        parent="1", source="internet", target="igw", edge="1")
    ET.SubElement(edge_igw, "mxGeometry", relative="1", **{"as": "geometry"})

    # VPC boundary
    vpc = ET.SubElement(root, "mxCell",
        id="vpc",
        value="VPC (10.0.0.0/16)",
        style="rounded=0;fillColor=#E8F4F8;strokeColor=#146EB4;strokeWidth=3;dashed=1;fontSize=11;fontStyle=1;",
        parent="1", vertex="1")
    ET.SubElement(vpc, "mxGeometry", x="50", y="200", width="1300", height="750", **{"as": "geometry"})

    # Public Subnet
    pub_subnet = ET.SubElement(root, "mxCell",
        id="pub-subnet",
        value="Public Subnet (10.0.1.0/24)",
        style="rounded=0;fillColor=#D4E8F7;strokeColor=#0A4C8C;strokeWidth=2;dashed=1;fontSize=10;",
        parent="1", vertex="1")
    ET.SubElement(pub_subnet, "mxGeometry", x="80", y="240", width="580", height="200", **{"as": "geometry"})

    # Private Subnet
    priv_subnet = ET.SubElement(root, "mxCell",
        id="priv-subnet",
        value="Private Subnet (10.0.2.0/24)",
        style="rounded=0;fillColor=#D4E8F7;strokeColor=#0A4C8C;strokeWidth=2;dashed=1;fontSize=10;",
        parent="1", vertex="1")
    ET.SubElement(priv_subnet, "mxGeometry", x="750", y="240", width="580", height="200", **{"as": "geometry"})

    # Data Subnet
    data_subnet = ET.SubElement(root, "mxCell",
        id="data-subnet",
        value="Data Subnet (10.0.3.0/24)",
        style="rounded=0;fillColor=#D4E8F7;strokeColor=#0A4C8C;strokeWidth=2;dashed=1;fontSize=10;",
        parent="1", vertex="1")
    ET.SubElement(data_subnet, "mxGeometry", x="400", y="520", width="580", height="150", **{"as": "geometry"})

    # Security groups and components
    components = [
        ("pub-alb", "ALB\n(Public SG)", 150, 280, "#4B9BFF"),
        ("app-eks", "EKS Cluster\n(Private SG)", 820, 280, "#4B9BFF"),
        ("data-rds", "RDS Aurora\n(Data SG)", 550, 560, "#FF9900"),
        ("data-cache", "ElastiCache\n(Data SG)", 750, 560, "#FF9900"),
    ]

    comp_ids = {}
    for comp_id, label, x, y, color in components:
        comp_ids[comp_id] = comp_id
        cell = ET.SubElement(root, "mxCell",
            id=comp_id,
            value=label,
            style=f"rounded=1;fillColor={color};strokeColor=#000;strokeWidth=2;fontSize=9;fontStyle=1;",
            parent="1", vertex="1")
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width="100", height="60", **{"as": "geometry"})

    # Security group boundaries
    sg_boxes = [
        ("sg-public", "Public SG\n(80, 443)", 130, 260, 600, 180),
        ("sg-private", "Private SG\n(6443, 8080)", 800, 260, 600, 180),
        ("sg-data", "Data SG\n(3306, 5432, 6379)", 380, 500, 600, 170),
    ]

    for sg_id, sg_label, x, y, w, h in sg_boxes:
        sg = ET.SubElement(root, "mxCell",
            id=sg_id,
            value=sg_label,
            style="rounded=0;fillColor=none;strokeColor=#FF6600;strokeWidth=2;dashed=1;fontSize=8;",
            parent="1", vertex="1")
        ET.SubElement(sg, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as": "geometry"})

    # Data flows through network
    flows = [
        ("igw", "pub-alb", "HTTPS 443"),
        ("pub-alb", "app-eks", "Internal routing"),
        ("app-eks", "data-rds", "SQL/TLS 3306"),
        ("app-eks", "data-cache", "Redis 6379"),
    ]

    for i, (from_id, to_id, label) in enumerate(flows):
        edge = ET.SubElement(root, "mxCell",
            id=f"flow-{i}",
            value=label,
            style="edgeStyle=orthogonalEdgeStyle;rounded=1;fontSize=9;",
            parent="1", source=from_id, target=to_id, edge="1")
        ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})

    # Legend
    legend_y = 750
    legend_items = [
        ("Orange: Unencrypted or public facing", 100),
        ("Blue: Encrypted, private routing", 110),
        ("Dashed: Security boundaries", 120),
        ("NAT Gateway required for private → internet", 130),
    ]

    for i, (text, x) in enumerate(legend_items):
        note = ET.SubElement(root, "mxCell",
            id=f"legend-{i}",
            value=text,
            style="fontSize=8;fillColor=none;strokeColor=none;",
            parent="1", vertex="1")
        ET.SubElement(note, "mxGeometry", x=str(x), y=str(legend_y + i * 15), width="400", height="12", **{"as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


# ── Export ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test generation
    components = [
        {"name": "CloudFront WAF", "layer": "Edge", "technology": "CloudFront", "description": "Global edge"},
        {"name": "API Gateway", "layer": "Network", "technology": "API Gateway", "description": "API entry"},
        {"name": "Lambda", "layer": "Application", "technology": "Lambda", "description": "Compute"},
        {"name": "RDS Aurora", "layer": "Data", "technology": "RDS", "description": "Database"},
    ]

    connections = [
        {"from": "CloudFront WAF", "to": "API Gateway", "label": "Step 1: HTTPS request"},
        {"from": "API Gateway", "to": "Lambda", "label": "Step 2: Invoke"},
        {"from": "Lambda", "to": "RDS Aurora", "label": "Step 3: Query"},
    ]

    print("Generated AWS Architecture with Icons")
    arch_xml = generate_aws_architecture_with_icons(components, connections)
    print(f"Length: {len(arch_xml)} bytes")

    print("\nGenerated Authentication Flow")
    auth_xml = generate_authentication_flow_diagram()
    print(f"Length: {len(auth_xml)} bytes")

    print("\nGenerated Network Segregation")
    net_xml = generate_network_segregation_diagram()
    print(f"Length: {len(net_xml)} bytes")
