"""
aws_architecture_diagram_generator.py
──────────────────────────────────────
Generates AWS architecture diagrams with proper AWS service icons
using draw.io's native AWS shape library and embedded SVG icons.

This version produces diagrams matching AWS official architecture documentation style.
"""

import xml.etree.ElementTree as ET
import re


# AWS Service Icon Data (Base64 encoded minimal SVGs)
# Comprehensive AWS service icons for complete LLD diagrams
AWS_SERVICE_ICONS = {
    # Compute Services
    "API Gateway": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHRleHQgeD0iMzIiIHk9IjMyIiBmb250LXNpemU9IjIwIiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkFQSTwvdGV4dD48L3N2Zz4=",
    "Lambda": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBvbHlnb24gcG9pbnRzPSIzMiw4IDE2LDMyIDMyLDMyIDIwLDY0IDQ4LDQ4IDM2LDQ4IiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPg==",
    "EC2": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHJlY3QgeD0iOCIgeT0iOCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiBmaWxsPSJ3aGl0ZSIgcng9IjMiLz48L3N2Zz4=",
    "ECS": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PGcgZmlsbD0id2hpdGUiPjxyZWN0IHg9IjEwIiB5PSIxMCIgd2lkdGg9IjE0IiBoZWlnaHQ9IjE0Ii8+PHJlY3QgeD0iMjgiIHk9IjEwIiB3aWR0aD0iMTQiIGhlaWdodD0iMTQiLz48cmVjdCB4PSI0NiIgeT0iMTAiIHdpZHRoPSIxNCIgaGVpZ2h0PSIxNCIvPjxyZWN0IHg9IjEwIiB5PSIyOCIgd2lkdGg9IjE0IiBoZWlnaHQ9IjE0Ii8+PHJlY3QgeD0iMjgiIHk9IjI4IiB3aWR0aD0iMTQiIGhlaWdodD0iMTQiLz48cmVjdCB4PSI0NiIgeT0iMjgiIHdpZHRoPSIxNCIgaGVpZ2h0PSIxNCIvPjwvZz48L3N2Zz4=",
    "EKS": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBvbHlnb24gcG9pbnRzPSIzMiwxMiAyMCwyOCAyNCw0OCA0MCw0OCA0NCwyOCIgZmlsbD0id2hpdGUiLz48L3N2Zz4=",
    "Fargate": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PGNpcmNsZSBjeD0iMjQiIGN5PSIyNCIgcj0iOCIgZmlsbD0id2hpdGUiLz48Y2lyY2xlIGN4PSI0MCIgY3k9IjQwIiByPSI4IiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPg==",
    "AppRunner": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHRleHQgeD0iMzIiIHk9IjMyIiBmb250LXNpemU9IjE2IiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuKGkDwvdGV4dD48L3N2Zz4=",
    
    # Database Services
    "RDS": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iOCIgZmlsbD0id2hpdGUiIG9wYWNpdHk9IjAuNyIvPjxyZWN0IHg9IjEyIiB5PSIyOCIgd2lkdGg9IjQwIiBoZWlnaHQ9IjI0IiBmaWxsPSJ3aGl0ZSIgcng9IjIiLz48L3N2Zz4=",
    "DynamoDB": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHBhdGggZD0iTTggMzJDOCAyMCAxNiAxMiAzMiAxMkM0OCA4IDU2IDIwIDU2IDMyQzU2IDQ0IDQ4IDUyIDMyIDUyQzE2IDUyIDggNDQgOCAzMloiIGZpbGw9IndoaXRlIi8+PC9zdmc+",
    "Aurora": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHBhdGggZD0iTTMyIDAgTDU2IDIwIEw2NCA0OCBMMzIgNjQgTDAgNDggTDggMjAgWiIgZmlsbD0id2hpdGUiLz48L3N2Zz4=",
    "ElastiCache": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iMjAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMjQiLz48L3N2Zz4=",
    "Neptune": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHBvbHlnb24gcG9pbnRzPSIzMiwwIDA6MzIgMzIsNjQgNjQsMzIiIGZpbGw9IndoaXRlIi8+PC9zdmc+",
    "DocumentDB": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHJlY3QgeD0iMTAiIHk9IjEwIiB3aWR0aD0iNDQiIGhlaWdodD0iNDQiIGZpbGw9IndoaXRlIiByeD0iMyIvPjwvc3ZnPg==",
    "Redshift": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHRleHQgeD0iMzIiIHk9IjMyIiBmb250LXNpemU9IjI0IiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuKEogwvdGV4dD48L3N2Zz4=",
    
    # Storage Services
    "S3": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMzI4MjM3Ii8+PHJlY3QgeD0iOCIgeT0iOCIgd2lkdGg9IjE2IiBoZWlnaHQ9IjQ4IiBmaWxsPSJ3aGl0ZSIvPjxyZWN0IHg9IjI0IiB5PSI4IiB3aWR0aD0iMTYiIGhlaWdodD0iNDgiIGZpbGw9IndoaXRlIiBvcGFjaXR5PSIwLjgiLz48cmVjdCB4PSI0MCIgeT0iOCIgd2lkdGg9IjE2IiBoZWlnaHQ9IjQ4IiBmaWxsPSJ3aGl0ZSIgb3BhY2l0eT0iMC42Ii8+PC9zdmc+",
    "EBS": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMzI4MjM3Ii8+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iMjAiIGZpbGw9IndoaXRlIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iOCIgZmlsbD0iIzMyODIzNyIvPjwvc3ZnPg==",
    "EFS": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMzI4MjM3Ii8+PHRleHQgeD0iMzIiIHk9IjMyIiBmb250LXNpemU9IjI0IiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuKOswwvdGV4dD48L3N2Zz4=",
    "Glacier": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMzI4MjM3Ii8+PHBvbHlnb24gcG9pbnRzPSIzMiw4IDE2LDMyIDMyLDMyIDI4LDU2IDM2LDU2IDMyLDMyIDQ4LDMyIiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPg==",
    "FSx": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMzI4MjM3Ii8+PHBhdGggZD0iTTAgMzIgTDE2IDAgTDMyIDMyIEwxNiA2NCBaIE0zMiAzMiBMMzIgMzIgTDQ4IDAgTDY0IDMyIEw0OCA2NCBaMzIgMzIiIGZpbGw9IndoaXRlIi8+PC9zdmc+",
    
    # Networking Services
    "CloudFront": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iMjAiIGZpbGw9IndoaXRlIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iOCIgZmlsbD0iI0ZGOTkwMCIvPjwvc3ZnPg==",
    "VPC": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHJlY3QgeD0iOCIgeT0iOCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHJ4PSI0Ii8+PC9zdmc+",
    "ALB": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHJlY3QgeD0iMTIiIHk9IjEyIiB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIGZpbGw9IndoaXRlIi8+PHRleHQgeD0iMzIiIHk9IjMyIiBmb250LXNpemU9IjIwIiBmaWxsPSIjMjI2MkZGIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+QjwvdGV4dD48L3N2Zz4=",
    "NLB": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHBvbHlnb24gcG9pbnRzPSIzMiwxMiAxMiwyMCAyMCw0OCA0NCw0OCA1MiwyMCIgZmlsbD0id2hpdGUiLz48L3N2Zz4=",
    "Route53": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iOCIgZmlsbD0id2hpdGUiLz48cmVjdCB4PSIyNiIgeT0iOCIgd2lkdGg9IjEyIiBoZWlnaHQ9IjQ4IiBmaWxsPSJ3aGl0ZSIgb3BhY2l0eT0iMC41Ii8+PHJlY3QgeD0iOCIgeT0iMjYiIHdpZHRoPSI0OCIgaGVpZ2h0PSIxMiIgZmlsbD0id2hpdGUiIG9wYWNpdHk9IjAuNSIvPjwvc3ZnPg==",
    "DirectConnect": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHBhdGggZD0iTTggOCBMMzIgMzIgTDU2IDggTTggNTYgTDMyIDMyIEw1NiA1NiIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSI0IiBmaWxsPSJub25lIi8+PC9zdmc+",
    "VPN": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHJlY3QgeD0iMTYiIHk9IjEwIiB3aWR0aD0iMzIiIGhlaWdodD0iMjQiIGZpbGw9IndoaXRlIiByeD0iMyIvPjxwb2x5Z29uIHBvaW50cz0iMzIsNDAgMTYsMzAgNDgsMzAiIGZpbGw9IndoaXRlIi8+PC9zdmc+",
    "NAT Gateway": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHRleHQgeD0iMzIiIHk9IjMyIiBmb250LXNpemU9IjE4IiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuKEoDwvdGV4dD48L3N2Zz4=",
    "Elastic IP": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iMTgiIGZpbGw9IndoaXRlIi8+PC9zdmc+",
    
    # Integration Services
    "SQS": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHJlY3QgeD0iOCIgeT0iOCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiBmaWxsPSJ3aGl0ZSIgcng9IjMiLz48L3N2Zz4=",
    "SNS": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIyMCIgcj0iOCIgZmlsbD0id2hpdGUiLz48cGF0aCBkPSJNMjAgNDAgTDIwIDU2IEw0NCA1NiBMNDQgNDAiIGZpbGw9IndoaXRlIi8+PC9zdmc+",
    "EventBridge": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBvbHlnb24gcG9pbnRzPSIzMiwxMiA2LDI0IDEwLDQ4IDU0LDQ4IDU4LDI0IiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPg==",
    "Kinesis": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBhdGggZD0iTTggMzIgUTMyIDAgNTYgMzIgUSAzMiA2NCA4IDMyIiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPg==",
    "AppSync": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBhdGggZD0iTTE2IDMyIEwyNCAxNiBMMzIgMzIgTDI0IDQ4IFoxNiAzMiBMMjQgMjQgTDMyIDE2IE0zMiAzMiBMNDAgMjQgTDQ4IDE2IE00MCAzMiBMMzIgNDAgTDI0IDQ4IiBmaWxsPSJ3aGl0ZSIgZmlsbC1ydWxlPSJldmVub2RkIi8+PC9zdmc+",
    "Cognito": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PGNpcmNsZSBjeD0iMjQiIGN5PSIyNCIgcj0iOCIgZmlsbD0id2hpdGUiLz48Y2lyY2xlIGN4PSI0MCIgY3k9IjI0IiByPSI4IiBmaWxsPSJ3aGl0ZSIvPjxyZWN0IHg9IjE2IiB5PSIzNiIgd2lkdGg9IjMyIiBoZWlnaHQ9IjE2IiBmaWxsPSJ3aGl0ZSIgcng9IjIiLz48L3N2Zz4=",
    
    # Security & Monitoring
    "CloudWatch": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHJlY3QgeD0iOCIgeT0iOCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiLz48cG9seWxpbmUgcG9pbnRzPSI4LDMyIDE2LDI0IDI0LDMyIDMyLDI0IDQwLDMyIDQ4LDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiLz48L3N2Zz4=",
    "X-Ray": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBhdGggZD0iTTMyIDggTDUwIDI2IEw1MCA0MiBMMzIgNjAgTDE0IDQyIEwxNCAyNiBaMzIgMTYgTDQyIDI2IEw0MiA0MCBMMzIgNDggTDIyIDQwIEwyMiAyNiBaMzIgMjQgTDM4IDMwIEwzOCAzOCBMMzIgNDQgTDI2IDM4IEwyNiAzMCBaMzIgMzIgTDM2IDM2IEwzNiAzOCBMMzIgNDIgTDI4IDM4IEwyOCAzNiBaMzIgMzIiIGZpbGw9IndoaXRlIi8+PC9zdmc+",
    "CloudTrail": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHRleHQgeD0iMzIiIHk9IjMyIiBmb250LXNpemU9IjI0IiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuKEoDwvdGV4dD48L3N2Zz4=",
    "KMS": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHJlY3QgeD0iMTYiIHk9IjI0IiB3aWR0aD0iMzIiIGhlaWdodD0iMjQiIGZpbGw9IndoaXRlIiByeD0iMyIvPjxjaXJjbGUgY3g9IjMyIiBjeT0iMzYiIHI9IjQiIGZpbGw9IiNGRjk5MDAiLz48L3N2Zz4=",
    "SecretsManager": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBhdGggZD0iTTIwIDI0IEMyMCAyMCAyNCAyMCAyOCAyMCBMMzYgMjAgQzQwIDIwIDQ0IDI0IDQ0IDI4IEw0NCAzNiBDNDQgNDAgNDAgNDQgMzYgNDQgTDI4IDQ0IEMyNCA0NCAyMCA0MCAyMCAzNiBaMzIgMzIgQzMwIDMyIDI4IDM0IDI4IDM2IEMyOCAzOCAzMCA0MCAzMiA0MCBDMzQgNDAgMzYgMzggMzYgMzYgQzM2IDM0IDM0IDMyIDMyIDMyIiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPg==",
    "IAM": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIyMCIgcj0iNiIgZmlsbD0id2hpdGUiLz48cGF0aCBkPSJNMjAgMzAgTDQ0IDMwIEw0NCA1MCBDNDQgNTIgNDIgNTQgNDAgNTQgTDI0IDU0IEMyMiA1NCAyMCA1MiAyMCA1MCBMMjAgMzAiIGZpbGw9IndoaXRlIi8+PC9zdmc+",
    "WAF": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBhdGggZD0iTTMyIDEwIEw0OCAyMCBMNDggNDQgTDMyIDU0IEwxNiA0NCBMMTYgMjAgWiIgZmlsbD0id2hpdGUiLz48cGF0aCBkPSJNMzIgMjAgTDQyIDI2IEw0MiA0MCBMMzIgNDYgTDIyIDQwIEwyMiAyNiBaMzIgMjggTDM4IDMyIEwzOCAzNCBMMzIgMzggTDI2IDM0IEwyNiAzMiBaMzIgMzIiIGZpbGw9IiNGRjk5MDAiLz48L3N2Zz4=",
    
    # Analytics & BI
    "Athena": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHRleHQgeD0iMzIiIHk9IjMyIiBmb250LXNpemU9IjI0IiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPuKOswwvdGV4dD48L3N2Zz4=",
    "QuickSight": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBvbHlnb24gcG9pbnRzPSI4LDMyIDE2LDE2IDI0LDI4IDMyLDAgNDAsNDAgNTIsOCA2MCw0OCIgZmlsbD0id2hpdGUiLz48L3N2Zz4=",
    "Glue": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iNiIgZmlsbD0id2hpdGUiLz48Y2lyY2xlIGN4PSI0NCIgY3k9IjQ0IiByPSI2IiBmaWxsPSJ3aGl0ZSIvPjxyZWN0IHg9IjE4IiB5PSIyNiIgd2lkdGg9IjI4IiBoZWlnaHQ9IjEyIiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPg==",
    "EMR": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHJlY3QgeD0iOCIgeT0iOCIgd2lkdGg9IjE2IiBoZWlnaHQ9IjQ4IiBmaWxsPSJ3aGl0ZSIvPjxyZWN0IHg9IjI4IiB5PSI4IiB3aWR0aD0iMTYiIGhlaWdodD0iNDgiIGZpbGw9IndoaXRlIi8+PHJlY3QgeD0iNDgiIHk9IjgiIHdpZHRoPSIxNiIgaGVpZ2h0PSI0OCIgZmlsbD0id2hpdGUiLz48L3N2Zz4=",
    
    # ML Services
    "SageMaker": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBvbHlnb24gcG9pbnRzPSIzMiw4IDE2LDMyIDMyLDU2IDQ4LDMyIiBmaWxsPSJ3aGl0ZSIgZmlsbC1ydWxlPSJldmVub2RkIi8+PC9zdmc+",
    
    # Container Services
    "ECR": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHJlY3QgeD0iMTAiIHk9IjEwIiB3aWR0aD0iNDQiIGhlaWdodD0iNDQiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgcng9IjMiLz48Y2lyY2xlIGN4PSIzMiIgY3k9IjMyIiByPSI2IiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPg==",
    
    # Developer Tools
    "CodeBuild": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBvbHlnb24gcG9pbnRzPSIyMiwxMCAzNCwxMCAzNCwxNiAyOCwyOCAyMiwyOCAyMiwxNiIgZmlsbD0id2hpdGUiLz48cmVjdCB4PSIxNiIgeT0iMzAiIHdpZHRoPSI2IiBoZWlnaHQ9IjIwIiBmaWxsPSJ3aGl0ZSIvPjxyZWN0IHg9IjI4IiB5PSIzMCIgd2lkdGg9IjYiIGhlaWdodD0iMjAiIGZpbGw9IndoaXRlIi8+PHJlY3QgeD0iNDAiIHk9IjMwIiB3aWR0aD0iNiIgaGVpZ2h0PSIyMCIgZmlsbD0id2hpdGUiLz48L3N2Zz4=",
    "CodePipeline": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBvbHlnb24gcG9pbnRzPSIxMiwzMiA4LDI0IDE2LDI0IiBmaWxsPSJ3aGl0ZSIvPjxyZWN0IHg9IjE4IiB5PSIyOCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjgiIGZpbGw9IndoaXRlIi8+PHBvbHlnb24gcG9pbnRzPSI1MiwzMiA0OCwyNCA1NiwyNCIgZmlsbD0id2hpdGUiLz48L3N2Zz4=",
}

SERVICE_TO_ICON = {
    # Compute
    "api gateway": "API Gateway",
    "api": "API Gateway",
    "lambda": "Lambda",
    "ec2": "EC2",
    "ecs": "ECS",
    "container": "ECS",
    "eks": "EKS",
    "kubernetes": "EKS",
    "fargate": "Fargate",
    "apprunner": "AppRunner",
    "app runner": "AppRunner",
    
    # Database
    "rds": "RDS",
    "aurora": "Aurora",
    "dynamodb": "DynamoDB",
    "nosql": "DynamoDB",
    "elasticache": "ElastiCache",
    "redis": "ElastiCache",
    "cache": "ElastiCache",
    "neptune": "Neptune",
    "documentdb": "DocumentDB",
    "document": "DocumentDB",
    "redshift": "Redshift",
    "warehouse": "Redshift",
    
    # Storage
    "s3": "S3",
    "storage": "S3",
    "bucket": "S3",
    "ebs": "EBS",
    "volume": "EBS",
    "efs": "EFS",
    "filesystem": "EFS",
    "glacier": "Glacier",
    "archive": "Glacier",
    "fsx": "FSx",
    "file": "FSx",
    
    # Networking
    "cloudfront": "CloudFront",
    "cdn": "CloudFront",
    "vpc": "VPC",
    "alb": "ALB",
    "nlb": "NLB",
    "load balancer": "ALB",
    "route53": "Route53",
    "dns": "Route53",
    "directconnect": "DirectConnect",
    "vpn": "VPN",
    "nat": "NAT Gateway",
    "nat gateway": "NAT Gateway",
    "elastic ip": "Elastic IP",
    "eip": "Elastic IP",
    
    # Integration
    "sqs": "SQS",
    "queue": "SQS",
    "sns": "SNS",
    "notification": "SNS",
    "eventbridge": "EventBridge",
    "events": "EventBridge",
    "kinesis": "Kinesis",
    "stream": "Kinesis",
    "appsync": "AppSync",
    "graphql": "AppSync",
    "cognito": "Cognito",
    "auth": "Cognito",
    "authentication": "Cognito",
    
    # Security & Monitoring
    "cloudwatch": "CloudWatch",
    "monitoring": "CloudWatch",
    "x-ray": "X-Ray",
    "xray": "X-Ray",
    "tracing": "X-Ray",
    "cloudtrail": "CloudTrail",
    "audit": "CloudTrail",
    "kms": "KMS",
    "encryption": "KMS",
    "secretsmanager": "SecretsManager",
    "secrets": "SecretsManager",
    "iam": "IAM",
    "identity": "IAM",
    "waf": "WAF",
    "firewall": "WAF",
    
    # Analytics
    "athena": "Athena",
    "query": "Athena",
    "quicksight": "QuickSight",
    "bi": "QuickSight",
    "glue": "Glue",
    "etl": "Glue",
    "emr": "EMR",
    "hadoop": "EMR",
    
    # ML
    "sagemaker": "SageMaker",
    "ml": "SageMaker",
    
    # Containers
    "ecr": "ECR",
    "registry": "ECR",
    
    # Developer Tools
    "codebuild": "CodeBuild",
    "build": "CodeBuild",
    "codepipeline": "CodePipeline",
    "ci/cd": "CodePipeline",
    "pipeline": "CodePipeline",
}


def get_icon_url(service_name: str) -> str | None:
    """Get icon URL for a service."""
    name_lower = service_name.lower()
    for key, icon_name in SERVICE_TO_ICON.items():
        if key in name_lower:
            return AWS_SERVICE_ICONS.get(icon_name)
    return None


def generate_aws_architecture_with_real_icons(components: list[dict], connections: list[dict]) -> str:
    """
    Generate professional AWS architecture diagram with actual AWS service icons.
    Uses draw.io's image support with base64-encoded SVG icons.
    """
    mxfile = ET.Element("mxfile", {"host": "Confluence", "modified": "", "agent": "", "version": "1.0", "type": "device"})
    diagram = ET.SubElement(mxfile, "diagram", {"id": "AWS_Architecture", "name": "AWS Architecture"})

    layer_order = ["Edge", "Network", "Platform", "Application", "Data"]
    layer_colors = {
        "Edge": "#FFE8CC",
        "Network": "#DDEBFF",
        "Platform": "#E7F5E7",
        "Application": "#E8F1FF",
        "Data": "#FFF4D6",
    }

    # Group components by layer and normalize unknown values to Application.
    layer_map = {layer: [] for layer in layer_order}
    for comp in components:
        raw_layer = (comp.get("layer") or "Application").strip().lower()
        resolved = "Application"
        for known in layer_order:
            if known.lower() in raw_layer or raw_layer in known.lower():
                resolved = known
                break
        layer_map[resolved].append(comp)

    lane_left = 30
    lane_top = 30
    lane_label_w = 140
    lane_gap = 24
    card_w = 220
    card_h = 170
    icon_w = 96
    icon_h = 96
    card_gap_x = 34
    card_gap_y = 20
    inner_left_pad = 22
    max_cols = 4
    lane_inner_start = lane_left + lane_label_w + 20

    occupied_layers = [l for l in layer_order if layer_map[l]]
    layer_heights = {}
    for layer in occupied_layers:
        count = len(layer_map[layer])
        rows = (count + max_cols - 1) // max_cols
        layer_heights[layer] = max(210, 22 + rows * card_h + (rows - 1) * card_gap_y + 22)

    page_w = max(1980, lane_inner_start + inner_left_pad + (max_cols * card_w) + ((max_cols - 1) * card_gap_x) + 360)
    total_lane_h = sum(layer_heights.values()) + max(0, len(occupied_layers) - 1) * lane_gap
    page_h = max(1300, lane_top + total_lane_h + 100)

    model = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "2000",
        "dy": "1200",
        "grid": "1",
        "gridSize": "10",
        "guides": "1",
        "tooltips": "1",
        "connect": "1",
        "arrows": "1",
        "fold": "1",
        "page": "0",
        "pageScale": "1",
        "pageWidth": str(page_w),
        "pageHeight": str(page_h),
        "math": "0",
        "shadow": "0"
    })

    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    comp_cell = {}
    lane_y_cursor = lane_top
    for layer in layer_order:
        comps = layer_map[layer]
        if not comps:
            continue

        lane_h = layer_heights[layer]
        lane_y = lane_y_cursor
        lane_bg = ET.SubElement(root, "mxCell", {
            "id": f"lane-{layer.lower()}",
            "value": "",
            "style": f"rounded=1;fillColor={layer_colors[layer]};strokeColor=#B9C2CF;strokeWidth=1;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(lane_bg, "mxGeometry", {
            "x": str(lane_left),
            "y": str(lane_y),
            "width": str(page_w - 60),
            "height": str(lane_h),
            "as": "geometry"
        })

        lane_title = ET.SubElement(root, "mxCell", {
            "id": f"lane-title-{layer.lower()}",
            "value": layer,
            "style": "rounded=1;fillColor=#FFFFFF;strokeColor=#9AA5B1;strokeWidth=1;fontSize=13;fontStyle=1;align=center;verticalAlign=middle;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(lane_title, "mxGeometry", {
            "x": str(lane_left + 10),
            "y": str(lane_y + 18),
            "width": str(lane_label_w - 20),
            "height": "42",
            "as": "geometry"
        })

        for i, comp in enumerate(comps):
            comp_name = (comp.get("name") or "Unnamed Component").strip()
            tech = (comp.get("technology") or "").strip()
            desc = (comp.get("description") or "").strip()
            slug = re.sub(r"[^a-z0-9]+", "-", comp_name.lower()).strip("-") or f"component-{i}"

            col = i % max_cols
            row = i // max_cols
            card_x = lane_inner_start + inner_left_pad + col * (card_w + card_gap_x)
            card_y = lane_y + 20 + row * (card_h + card_gap_y)
            card_id = f"c-{slug}"
            icon_id = f"{card_id}-icon"
            text_id = f"{card_id}-text"
            comp_cell[comp_name.lower()] = card_id

            card = ET.SubElement(root, "mxCell", {
                "id": card_id,
                "value": "",
                "style": "rounded=1;fillColor=#FFFFFF;strokeColor=#7B8794;strokeWidth=1;",
                "parent": "1",
                "vertex": "1"
            })
            ET.SubElement(card, "mxGeometry", {
                "x": str(card_x),
                "y": str(card_y),
                "width": str(card_w),
                "height": str(card_h),
                "as": "geometry"
            })

            icon_url = get_icon_url(tech)
            icon_style = "shape=mxgraph.basic.image;"
            if icon_url:
                icon_style = f"shape=image;image={icon_url};"
            icon = ET.SubElement(root, "mxCell", {
                "id": icon_id,
                "value": "",
                "style": icon_style + "strokeColor=none;fillColor=none;",
                "parent": "1",
                "vertex": "1"
            })
            ET.SubElement(icon, "mxGeometry", {
                "x": str(card_x + (card_w - icon_w) // 2),
                "y": str(card_y + 8),
                "width": str(icon_w),
                "height": str(icon_h),
                "as": "geometry"
            })

            label_parts = [comp_name]
            if tech:
                label_parts.append(f"({tech})")
            if desc:
                short_desc = desc[:75] + ("..." if len(desc) > 75 else "")
                label_parts.append(short_desc)
            label_text = "\n".join(label_parts)

            text = ET.SubElement(root, "mxCell", {
                "id": text_id,
                "value": label_text,
                "style": "text;html=1;whiteSpace=wrap;align=center;verticalAlign=top;fontSize=11;spacingTop=2;strokeColor=none;fillColor=none;",
                "parent": "1",
                "vertex": "1"
            })
            ET.SubElement(text, "mxGeometry", {
                "x": str(card_x + 8),
                "y": str(card_y + 108),
                "width": str(card_w - 16),
                "height": str(card_h - 112),
                "as": "geometry"
            })

        lane_y_cursor += lane_h + lane_gap

    # Add connections with numbered labels
    legend_items = []
    valid_edge_count = 0
    
    for i, conn in enumerate(connections):
        src = comp_cell.get(conn["from"].lower())
        tgt = comp_cell.get(conn["to"].lower())
        
        if not src or not tgt:
            print(f"  Warning: Skipping connection: {conn['from']} -> {conn['to']} (not found)")
            continue

        valid_edge_count += 1
        full_label = conn.get("label", "")
        edge_num = str(valid_edge_count)
        
        edge = ET.SubElement(root, "mxCell", {
            "id": f"e-{i}",
            "value": edge_num,
            "style": "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;fontSize=11;fontStyle=1;endArrow=block;endFill=1;strokeWidth=1.4;",
            "parent": "1",
            "source": src,
            "target": tgt,
            "edge": "1"
        })
        ET.SubElement(edge, "mxGeometry", {"relative": "1", "as": "geometry"})
        
        if full_label:
            legend_items.append((edge_num, full_label))

    # Add legend box on the right side
    if legend_items:
        legend_x = int(page_w - 320)
        legend_y = lane_top + 40
        legend_w = 300
        
        legend_bg = ET.SubElement(root, "mxCell", {
            "id": "legend-bg",
            "value": "",
            "style": "rounded=1;fillColor=#FFFEF0;strokeColor=#9AA5B1;strokeWidth=2;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(legend_bg, "mxGeometry", {
            "x": str(legend_x),
            "y": str(legend_y),
            "width": str(legend_w),
            "height": str(max(60, 30 + len(legend_items) * 24)),
            "as": "geometry"
        })
        
        legend_title = ET.SubElement(root, "mxCell", {
            "id": "legend-title",
            "value": "Data Flow Steps",
            "style": "text;fontSize=12;fontStyle=1;fillColor=none;strokeColor=none;align=left;spacingLeft=10;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(legend_title, "mxGeometry", {
            "x": str(legend_x + 10),
            "y": str(legend_y + 6),
            "width": str(legend_w - 20),
            "height": "20",
            "as": "geometry"
        })
        
        for idx, (num, desc) in enumerate(legend_items):
            item_y = legend_y + 28 + idx * 22
            item_text = f"{num}. {desc}"
            
            legend_item = ET.SubElement(root, "mxCell", {
                "id": f"legend-item-{num}",
                "value": item_text,
                "style": "text;fontSize=9;fillColor=none;strokeColor=none;align=left;spacingLeft=10;whiteSpace=wrap;",
                "parent": "1",
                "vertex": "1"
            })
            ET.SubElement(legend_item, "mxGeometry", {
                "x": str(legend_x + 10),
                "y": str(item_y),
                "width": str(legend_w - 20),
                "height": "20",
                "as": "geometry"
            })

    # Format XML
    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_detailed_network_diagram(components: list[dict], connections: list[dict]) -> str:
    """
    Generate detailed network diagram showing security groups, subnets, and routing.
    """
    mxfile = ET.Element("mxfile", {"host": "Confluence", "type": "device", "version": "1.0"})
    diagram = ET.SubElement(mxfile, "diagram", {"name": "Network Architecture"})
    
    model = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "1800",
        "dy": "1000",
        "grid": "1",
        "gridSize": "10",
        "guides": "1",
        "tooltips": "1",
        "connect": "1",
        "arrows": "1",
        "fold": "1",
        "page": "0",
        "pageScale": "1",
        "pageWidth": "1600",
        "pageHeight": "1000",
        "math": "0",
        "shadow": "0"
    })
    
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    # Draw VPC boundary (large rectangle)
    vpc = ET.SubElement(root, "mxCell", {
        "id": "vpc",
        "value": "AWS VPC (10.0.0.0/16)",
        "style": "rounded=0;fillColor=#E8F4F8;strokeColor=#146EB4;strokeWidth=3;dashed=1;fontSize=12;fontStyle=1;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(vpc, "mxGeometry", {
        "x": "20",
        "y": "50",
        "width": "1560",
        "height": "850",
        "as": "geometry"
    })

    # Public Subnet
    pub_subnet = ET.SubElement(root, "mxCell", {
        "id": "pub-subnet",
        "value": "Public Subnet (10.0.1.0/24)",
        "style": "rounded=0;fillColor=#D4E8F7;strokeColor=#0A4C8C;strokeWidth=2;dashed=1;fontSize=11;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(pub_subnet, "mxGeometry", {
        "x": "50",
        "y": "80",
        "width": "450",
        "height": "200",
        "as": "geometry"
    })

    # Private Subnet
    priv_subnet = ET.SubElement(root, "mxCell", {
        "id": "priv-subnet",
        "value": "Private Subnet (10.0.2.0/24)",
        "style": "rounded=0;fillColor=#D4E8F7;strokeColor=#0A4C8C;strokeWidth=2;dashed=1;fontSize=11;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(priv_subnet, "mxGeometry", {
        "x": "600",
        "y": "80",
        "width": "450",
        "height": "200",
        "as": "geometry"
    })

    # Data Subnet
    data_subnet = ET.SubElement(root, "mxCell", {
        "id": "data-subnet",
        "value": "Data Subnet (10.0.3.0/24)",
        "style": "rounded=0;fillColor=#D4E8F7;strokeColor=#0A4C8C;strokeWidth=2;dashed=1;fontSize=11;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(data_subnet, "mxGeometry", {
        "x": "1150",
        "y": "80",
        "width": "400",
        "height": "200",
        "as": "geometry"
    })

    # Internet Gateway
    igw = ET.SubElement(root, "mxCell", {
        "id": "igw",
        "value": "Internet\nGateway",
        "style": "rounded=1;fillColor=#FF9900;strokeColor=#000;strokeWidth=2;fontSize=11;fontStyle=1;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(igw, "mxGeometry", {
        "x": "325",
        "y": "20",
        "width": "100",
        "height": "50",
        "as": "geometry"
    })

    # Security Groups
    sg_public = ET.SubElement(root, "mxCell", {
        "id": "sg-pub",
        "value": "SG: HTTP(80), HTTPS(443)",
        "style": "rounded=0;fillColor=none;strokeColor=#FF6600;strokeWidth=2;dashed=1;fontSize=9;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(sg_public, "mxGeometry", {
        "x": "60",
        "y": "100",
        "width": "430",
        "height": "160",
        "as": "geometry"
    })

    sg_private = ET.SubElement(root, "mxCell", {
        "id": "sg-priv",
        "value": "SG: Internal Only",
        "style": "rounded=0;fillColor=none;strokeColor=#FF6600;strokeWidth=2;dashed=1;fontSize=9;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(sg_private, "mxGeometry", {
        "x": "610",
        "y": "100",
        "width": "430",
        "height": "160",
        "as": "geometry"
    })

    sg_data = ET.SubElement(root, "mxCell", {
        "id": "sg-data",
        "value": "SG: DB Ports (3306, 5432, 6379)",
        "style": "rounded=0;fillColor=none;strokeColor=#FF6600;strokeWidth=2;dashed=1;fontSize=9;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(sg_data, "mxGeometry", {
        "x": "1160",
        "y": "100",
        "width": "380",
        "height": "160",
        "as": "geometry"
    })

    # Services in subnets
    services = [
        ("alb", "ALB", 100, 130, "#FF9900"),
        ("app", "EKS", 650, 130, "#4B9BFF"),
        ("db-rds", "RDS Aurora", 1200, 130, "#2262FF"),
    ]

    for service_id, label, x, y, color in services:
        svc = ET.SubElement(root, "mxCell", {
            "id": service_id,
            "value": label,
            "style": f"rounded=1;fillColor={color};strokeColor=#000;strokeWidth=2;fontSize=10;fontStyle=1;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(svc, "mxGeometry", {
            "x": str(x),
            "y": str(y),
            "width": "100",
            "height": "60",
            "as": "geometry"
        })

    # Data flows
    flows = [
        ("igw", "alb", "Route to ALB"),
        ("alb", "app", "Forward to EKS"),
        ("app", "db-rds", "Query DB"),
    ]

    for i, (from_id, to_id, label) in enumerate(flows):
        edge = ET.SubElement(root, "mxCell", {
            "id": f"flow-{i}",
            "value": label,
            "style": "edgeStyle=orthogonalEdgeStyle;rounded=1;fontSize=9;",
            "parent": "1",
            "source": from_id,
            "target": to_id,
            "edge": "1"
        })
        ET.SubElement(edge, "mxGeometry", {"relative": "1", "as": "geometry"})

    # Legend
    legend_y = 350
    legend = ET.SubElement(root, "mxCell", {
        "id": "legend",
        "value": "Legend:\n🟠 Orange = AWS Service\n🔵 Blue = Compute/Storage\n📊 Dashed = Security Boundary\n─ Solid = Data Flow",
        "style": "fontSize=10;fillColor=none;strokeColor=none;align=left;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(legend, "mxGeometry", {
        "x": "50",
        "y": str(legend_y),
        "width": "400",
        "height": "100",
        "as": "geometry"
    })

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


if __name__ == "__main__":
    # Test
    components = [
        {"name": "CloudFront", "layer": "Edge", "technology": "CloudFront", "description": "CDN"},
        {"name": "ALB", "layer": "Network", "technology": "ALB", "description": "Load Balancer"},
        {"name": "EKS Cluster", "layer": "Application", "technology": "EKS", "description": "Kubernetes"},
        {"name": "RDS Aurora", "layer": "Data", "technology": "RDS", "description": "Database"},
    ]
    
    connections = [
        {"from": "CloudFront", "to": "ALB", "label": "Step 1: HTTPS"},
        {"from": "ALB", "to": "EKS Cluster", "label": "Step 2: Route"},
        {"from": "EKS Cluster", "to": "RDS Aurora", "label": "Step 3: Query"},
    ]
    
    print("Generating AWS Architecture with Icons...")
    arch = generate_aws_architecture_with_real_icons(components, connections)
    print(f"✓ Architecture diagram: {len(arch)} bytes")
    
    print("Generating Network Diagram...")
    net = generate_detailed_network_diagram(components, connections)
    print(f"✓ Network diagram: {len(net)} bytes")
    
    print("\n✅ Both diagrams ready to embed in Confluence!")


# Aliases for backward compatibility with old function names
def generate_authentication_flow_diagram() -> str:
    """Generate authentication flow diagram (backward compatible)."""
    mxfile = ET.Element("mxfile", {"host": "Confluence", "type": "device", "version": "1.0"})
    diagram = ET.SubElement(mxfile, "diagram", {"name": "Authentication Flow"})
    
    model = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "1600",
        "dy": "900",
        "grid": "1",
        "gridSize": "10",
        "guides": "1",
        "tooltips": "1",
        "connect": "1",
        "arrows": "1",
        "fold": "1",
        "page": "0",
        "pageScale": "1",
        "pageWidth": "1600",
        "pageHeight": "900",
        "math": "0",
        "shadow": "0"
    })
    
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    # Components in auth flow
    components = [
        ("user", "User", 50, 350, "#FF9900", "Customer"),
        ("webapp", "Web App", 200, 350, "#4B9BFF", "Frontend"),
        ("api", "API Gateway", 350, 350, "#FF9900", "Backend API"),
        ("cognito", "AWS Cognito", 500, 350, "#FF9900", "Authentication"),
        ("service", "Service", 650, 350, "#4B9BFF", "Application"),
        ("db", "Database", 800, 350, "#2262FF", "Data Store"),
    ]

    for comp_id, label, x, y, color, desc in components:
        comp = ET.SubElement(root, "mxCell", {
            "id": comp_id,
            "value": f"{label}\n({desc})",
            "style": f"rounded=1;fillColor={color};strokeColor=#000;strokeWidth=2;fontSize=11;fontStyle=1;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(comp, "mxGeometry", {
            "x": str(x),
            "y": str(y),
            "width": "120",
            "height": "80",
            "as": "geometry"
        })

    # Authentication flow arrows
    flows = [
        ("user", "webapp", "1. Login Request"),
        ("webapp", "api", "2. Forward to API"),
        ("api", "cognito", "3. OAuth2 Request"),
        ("cognito", "api", "4. Token Issued"),
        ("api", "webapp", "5. Token Returned"),
        ("webapp", "user", "6. Session Started"),
        ("webapp", "service", "7. API Call + Token"),
        ("service", "db", "8. Query with Auth"),
    ]

    for i, (from_id, to_id, label) in enumerate(flows):
        edge = ET.SubElement(root, "mxCell", {
            "id": f"flow-{i}",
            "value": label,
            "style": "edgeStyle=orthogonalEdgeStyle;rounded=1;fontSize=9;fontStyle=1;",
            "parent": "1",
            "source": from_id,
            "target": to_id,
            "edge": "1"
        })
        ET.SubElement(edge, "mxGeometry", {"relative": "1", "as": "geometry"})

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_network_segregation_diagram() -> str:
    """Generate network segregation diagram (backward compatible)."""
    return generate_detailed_network_diagram([], [])
