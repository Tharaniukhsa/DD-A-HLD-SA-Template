"""
aws_architecture_diagram_generator.py
──────────────────────────────────────
Generates AWS architecture diagrams with proper AWS service icons
using draw.io's native AWS shape library and embedded SVG icons.

This version produces diagrams matching AWS official architecture documentation style.
"""

import xml.etree.ElementTree as ET
import re
import base64
import os
import urllib.request
import zipfile
import textwrap
from pathlib import Path
from urllib.parse import quote


# AWS Service Icon Data (Base64 encoded minimal SVGs)
# Comprehensive AWS service icons for complete LLD diagrams
AWS_SERVICE_ICONS = {
    # Generic fallback icon for non-mapped technologies
    "Generic": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjNjc3RTlFIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iMjAiIGZpbGw9IndoaXRlIiBvcGFjaXR5PSIwLjkiLz48dGV4dCB4PSIzMiIgeT0iMzMiIGZvbnQtc2l6ZT0iMjAiIGZpbGw9IiM2NzdFOUUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj4/PC90ZXh0Pjwvc3ZnPg==",
    "AzureIdentity": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMDA3OEQ0Ii8+PHBhdGggZD0iTTMyIDEwTDIwIDIwVjM2QzIwIDQ0IDI2IDUwIDMyIDUyQzM4IDUwIDQ0IDQ0IDQ0IDM2VjIwWiIgZmlsbD0id2hpdGUiLz48Y2lyY2xlIGN4PSIzMiIgY3k9IjI4IiByPSI0IiBmaWxsPSIjMDA3OEQ0Ii8+PC9zdmc+",
    "AzureNetwork": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMDA3OEQ0Ii8+PHJlY3QgeD0iMTAiIHk9IjEwIiB3aWR0aD0iNDQiIGhlaWdodD0iNDQiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIvPjxwYXRoIGQ9Ik0xMCAzMkw1NCAzMk0zMiAxMEwzMiA1NCIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIi8+PC9zdmc+",

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
    "TransferFamily": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBhdGggZD0iTTEyIDIwIEw1MiAyMCBMNTIgNDQgTDEyIDQ0IFoiIGZpbGw9IndoaXRlIiBvcGFjaXR5PSIwLjM1Ii8+PHBhdGggZD0iTTIwIDMyIEw0NCAzMiIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSI0Ii8+PHBvbHlsaW5lIHBvaW50cz0iMzYsMjQgNDQsMzIgMzYsNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iNCIvPjwvc3ZnPg==",
    
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
    "InternetGateway": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHBvbHlnb24gcG9pbnRzPSIzMiw4IDU2LDMyIDMyLDU2IDgsMzIiIGZpbGw9IndoaXRlIi8+PHJlY3QgeD0iMjkiIHk9IjIyIiB3aWR0aD0iNiIgaGVpZ2h0PSIyMCIgZmlsbD0iIzIyNjJGRiIvPjwvc3ZnPg==",
    "RouteTable": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHJlY3QgeD0iMTAiIHk9IjE0IiB3aWR0aD0iNDQiIGhlaWdodD0iMzYiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMyIvPjxwb2x5bGluZSBwb2ludHM9IjE2LDI4IDI4LDI4IDI4LDIyIDQ0LDIyIiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiLz48cG9seWxpbmUgcG9pbnRzPSIzNiwyMCA0NCwyMiAzNiwyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIi8+PC9zdmc+",
    "SecurityGroup": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjRkY5OTAwIi8+PHBhdGggZD0iTTMyIDEwIEw0OCAxNiBMNDggMzQgQzQ4IDQ0IDQxIDUyIDMyIDU0IEMyMyA1MiAxNiA0NCAxNiAzNCBMMTYgMTYgWiIgZmlsbD0id2hpdGUiLz48L3N2Zz4",
    "PublicSubnet": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMjI2MkZGIi8+PHJlY3QgeD0iOCIgeT0iOCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiLz48dGV4dCB4PSIzMiIgeT0iMzQiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IndoaXRlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIj5QVUI8L3RleHQ+PC9zdmc+",
    "PrivateSubnet": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjMmY4NTVhIi8+PHJlY3QgeD0iOCIgeT0iOCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiLz48dGV4dCB4PSIzMiIgeT0iMzQiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IndoaXRlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIj5QUlY8L3RleHQ+PC9zdmc+",
    "DataSubnet": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiBmaWxsPSIjYTE2OTExIi8+PHJlY3QgeD0iOCIgeT0iOCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiLz48dGV4dCB4PSIzMiIgeT0iMzQiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IndoaXRlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIj5EQVRBPC90ZXh0Pjwvc3ZnPg==",
    
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

# Official AWS architecture icon package (from https://aws.amazon.com/architecture/icons/)
AWS_ICON_PACKAGE_ZIP_URL = (
    "https://d1.awsstatic.com/onedam/marketing-channels/website/aws/en_US/architecture/approved/architecture-icons/"
    "Icon-package_01302026.31b40d126ed27079b708594940ad577a86150582.zip"
)
AWS_ICON_CACHE_DIR = Path(".cache") / "awsi"
AWS_ICON_PACKAGE_ZIP = AWS_ICON_CACHE_DIR / "p.zip"
AWS_ICON_EXTRACT_DIR = AWS_ICON_CACHE_DIR / "e"

# Fallback icon files (used only if official package lookup fails)
AWS_OFFICIAL_ICON_URLS = {
    "API Gateway": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/api-gateway.png",
    "TransferFamily": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/migration-and-transfer/aws-transfer-family.png",
    "Lambda": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/compute/lambda-function.png",
    "EKS": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/compute/elastic-kubernetes-service.png",
    "RDS": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/database/rds.png",
    "S3": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/storage/simple-storage-service-s3.png",
    "SQS": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/integration/simple-queue-service-sqs.png",
    "CloudWatch": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/management-and-governance/cloudwatch.png",
    "IAM": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/security-identity-and-compliance/identity-and-access-management-iam.png",
    "KMS": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/security-identity-and-compliance/key-management-service.png",
    "SecretsManager": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/security-identity-and-compliance/secrets-manager.png",
    "WAF": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/security-identity-and-compliance/aws-waf.png",
    "CloudTrail": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/management-and-governance/cloudtrail.png",
    "CloudFront": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/cloudfront.png",
    "VPC": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/vpc.png",
    "ALB": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/elb-application-load-balancer.png",
    "DirectConnect": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/direct-connect.png",
    "VPN": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/vpn-connection.png",
    "NAT Gateway": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/nat-gateway.png",
    "Cognito": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/security/cognito.png",
    "InternetGateway": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/general/internet-gateway.png",
    "PublicSubnet": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/public-subnet.png",
    "PrivateSubnet": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/private-subnet.png",
    "DataSubnet": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/private-subnet.png",
    "RouteTable": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/route-table.png",
    "SecurityGroup": "https://raw.githubusercontent.com/mingrammer/diagrams/master/resources/aws/network/nacl.png",
}

_ICON_DATA_URI_CACHE: dict[str, str] = {}
_OFFICIAL_ICON_FILE_CACHE: dict[str, str] = {}

# Deterministic official icon paths when present in AWS icon package.
OFFICIAL_ICON_FILE_HINTS = {
    "VPC": ["Architecture-Group-Icons_01302026/Virtual-private-cloud-VPC_32.svg"],
    "PublicSubnet": ["Architecture-Group-Icons_01302026/Public-subnet_32.svg"],
    "PrivateSubnet": ["Architecture-Group-Icons_01302026/Private-subnet_32.svg"],
    "DataSubnet": ["Architecture-Group-Icons_01302026/Private-subnet_32.svg"],
}

ICON_NAME_KEYWORDS = {
    "API Gateway": ["api gateway"],
    "Lambda": ["lambda"],
    "S3": ["simple storage service", "s3"],
    "SQS": ["simple queue service", "sqs"],
    "CloudWatch": ["cloudwatch"],
    "IAM": ["identity and access management", "iam"],
    "KMS": ["key management service", "kms"],
    "SecretsManager": ["secrets manager", "secretsmanager"],
    "WAF": ["web application firewall", "waf"],
    "CloudTrail": ["cloudtrail"],
    "Glue": ["glue"],
    "TransferFamily": ["transfer family", "aws transfer"],
    "EKS": ["elastic kubernetes service", "eks"],
    "RDS": ["rds"],
    "CloudFront": ["cloudfront"],
    "VPC": ["vpc"],
    "ALB": ["application load balancer", "elb application load balancer", "alb"],
    "DirectConnect": ["direct connect"],
    "VPN": ["vpn connection", "site to site vpn", "client vpn", "vpn"],
    "NAT Gateway": ["nat gateway"],
    "Cognito": ["cognito"],
    "InternetGateway": ["internet gateway"],
    "PublicSubnet": ["public subnet"],
    "PrivateSubnet": ["private subnet"],
    "DataSubnet": ["private subnet", "subnet"],
    "RouteTable": ["route table"],
    "SecurityGroup": ["security group", "nacl"],
}

SERVICE_TO_ICON = {
    # Common generic/non-AWS descriptors
    "on-prem": "EC2",
    "on prem": "EC2",
    "onprem": "Generic",
    "server": "EC2",
    "runtime": "ECS",
    "app runtime": "ECS",
    "application runtime": "ECS",
    "application service": "ECS",
    "gateway": "API Gateway",
    "gateway / waf": "WAF",
    "azure entra id": "AzureIdentity",
    "entra id": "AzureIdentity",
    "azure identity": "AzureIdentity",
    "azure network": "AzureNetwork",
    "vnet": "AzureNetwork",
    "managed database": "RDS",
    "db": "RDS",
    "user": "IAM",
    "client": "CloudFront",
    "aws transfer family": "TransferFamily",
    "transfer family": "TransferFamily",
    "transfer endpoint": "TransferFamily",
    "sftp gateway": "TransferFamily",
    "sftp": "TransferFamily",
    "database": "RDS",

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
    "key vault": "KMS",
    "iam": "IAM",
    "entra": "IAM",
    "identity": "IAM",
    "waf": "WAF",
    "firewall": "WAF",
    "shield": "WAF",
    "guardduty": "CloudWatch",
    "defender": "CloudWatch",
    "cloudtrail": "CloudTrail",
    "activity log": "CloudTrail",
    "config": "CloudTrail",
    "policy": "IAM",
    "cost explorer": "CloudWatch",
    "cost management": "CloudWatch",
    "inspector": "CloudWatch",
    
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


# Deterministic icon mapping for core high-level runtime components.
# This ensures stable icon selection regardless of keyword collisions.
CORE_COMPONENT_ICON_OVERRIDES = {
    "on-prem business app": "EC2",
    "on-prem sftp server": "TransferFamily",
    "ukhsa intra identity": "AzureIdentity",
    "azure entra id": "AzureIdentity",
    "identity & access management (iam)": "AzureIdentity",
    "aws transfer endpoint": "TransferFamily",
    "raw landing bucket": "S3",
    "validation processor": "Lambda",
    "processing queue": "SQS",
    "curated database": "RDS",
    "monitoring and alerts": "CloudWatch",
}


def get_component_icon_url(component_name: str, technology: str = "", description: str = "") -> str | None:
    """Resolve icon URL with deterministic component-name overrides first."""
    comp_name = (component_name or "").strip().lower()
    for key, icon_name in CORE_COMPONENT_ICON_OVERRIDES.items():
        if key in comp_name:
            # Prefer official AWS SVG icon assets for better visual clarity.
            official_uri = _get_official_svg_icon_data_uri(icon_name)
            if official_uri:
                return official_uri

            # Fallback to compact embedded SVG for guaranteed visibility.
            return AWS_SERVICE_ICONS.get(icon_name) or AWS_SERVICE_ICONS.get("Generic")

    return get_icon_url(" ".join(part for part in [component_name, technology, description] if part))


def get_icon_url(service_name: str) -> str | None:
    """Get icon URL for a service using most-specific keyword matching."""
    name_lower = (service_name or "").lower()

    matches: list[tuple[int, str]] = []
    for key, icon_name in SERVICE_TO_ICON.items():
        if key in name_lower:
            # Prefer longer, more specific keys (e.g. "transfer family" over "server").
            matches.append((len(key), icon_name))

    if matches:
        matches.sort(key=lambda item: item[0], reverse=True)
        icon_name = matches[0][1]
        real_uri = _get_remote_icon_data_uri(icon_name)
        if real_uri:
            return real_uri
        return AWS_SERVICE_ICONS.get(icon_name) or AWS_SERVICE_ICONS.get("Generic")

    return AWS_SERVICE_ICONS.get("Generic")


def _get_remote_icon_data_uri(icon_name: str) -> str | None:
    """Download and cache a PNG icon as data URI so draw.io embeds real AWS icon art."""
    if icon_name in _ICON_DATA_URI_CACHE:
        return _ICON_DATA_URI_CACHE[icon_name]

    # First preference: official AWS architecture icon package.
    official_uri = _get_official_package_icon_data_uri(icon_name)
    if official_uri:
        _ICON_DATA_URI_CACHE[icon_name] = official_uri
        return official_uri

    icon_url = AWS_OFFICIAL_ICON_URLS.get(icon_name)
    if not icon_url:
        return None

    try:
        with urllib.request.urlopen(icon_url, timeout=10) as response:
            payload = response.read()
        if not _is_supported_image_payload(payload):
            return None
        uri = f"data:image/png;base64,{base64.b64encode(payload).decode('ascii')}"
        _ICON_DATA_URI_CACHE[icon_name] = uri
        return uri
    except Exception:
        return None


def _is_supported_image_payload(payload: bytes) -> bool:
    """Return True only for PNG/JPEG/GIF/SVG payloads.

    This avoids embedding HTML error pages as image data URIs.
    """
    if not payload:
        return False
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if payload.startswith(b"\xff\xd8\xff"):
        return True
    if payload.startswith(b"GIF87a") or payload.startswith(b"GIF89a"):
        return True

    head = payload[:512].lstrip().lower()
    if head.startswith(b"<?xml") or head.startswith(b"<svg"):
        return b"<svg" in payload[:4096].lower()
    return False


def _normalize_search_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _ensure_official_icon_package() -> bool:
    try:
        os.makedirs(AWS_ICON_CACHE_DIR, exist_ok=True)
        os.makedirs(AWS_ICON_EXTRACT_DIR, exist_ok=True)

        if not AWS_ICON_PACKAGE_ZIP.exists() or AWS_ICON_PACKAGE_ZIP.stat().st_size == 0:
            with urllib.request.urlopen(AWS_ICON_PACKAGE_ZIP_URL, timeout=20) as response:
                payload = response.read()
            AWS_ICON_PACKAGE_ZIP.write_bytes(payload)

        marker = AWS_ICON_EXTRACT_DIR / ".ok"
        if not marker.exists():
            with zipfile.ZipFile(AWS_ICON_PACKAGE_ZIP, "r") as zf:
                zf.extractall(AWS_ICON_EXTRACT_DIR)
            marker.write_text("ok", encoding="utf-8")
        return True
    except Exception:
        return False


def _match_official_icon_file(icon_name: str) -> Path | None:
    if icon_name in _OFFICIAL_ICON_FILE_CACHE:
        return Path(_OFFICIAL_ICON_FILE_CACHE[icon_name])

    # First try deterministic known-good paths.
    for rel_hint in OFFICIAL_ICON_FILE_HINTS.get(icon_name, []):
        candidate = AWS_ICON_EXTRACT_DIR / rel_hint
        if candidate.exists() and candidate.is_file():
            _OFFICIAL_ICON_FILE_CACHE[icon_name] = str(candidate)
            return candidate

    keywords = ICON_NAME_KEYWORDS.get(icon_name, [])
    if not keywords:
        return None

    candidates: list[tuple[int, Path]] = []
    for path in AWS_ICON_EXTRACT_DIR.rglob("*"):
        if not path.is_file():
            continue
        path_str = str(path)
        if "__MACOSX" in path_str:
            continue
        if path.name.startswith("._"):
            continue
        if path.suffix.lower() not in {".svg", ".png"}:
            continue
        normalized = _normalize_search_text(str(path))
        for kw in keywords:
            kw_norm = _normalize_search_text(kw)
            if kw_norm and kw_norm in normalized:
                # Prefer SVG first to avoid binary data-URI rendering issues on some Confluence draw.io versions.
                score = (0 if path.suffix.lower() == ".svg" else 1) * 10000 + len(path_str)
                candidates.append((score, path))
                break

    if not candidates:
        return None

    selected = sorted(candidates, key=lambda item: item[0])[0][1]
    _OFFICIAL_ICON_FILE_CACHE[icon_name] = str(selected)
    return selected


def _get_official_svg_icon_data_uri(icon_name: str) -> str | None:
    """Resolve official icon strictly as SVG, skipping PNG variants."""
    if not _ensure_official_icon_package():
        return None

    keywords = ICON_NAME_KEYWORDS.get(icon_name, [])
    if not keywords:
        return None

    # Check deterministic hints first if they point to SVG files.
    for rel_hint in OFFICIAL_ICON_FILE_HINTS.get(icon_name, []):
        candidate = AWS_ICON_EXTRACT_DIR / rel_hint
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() == ".svg":
            try:
                data = candidate.read_bytes()
                return f"data:image/svg+xml;base64,{base64.b64encode(data).decode('ascii')}"
            except Exception:
                return None

    candidates: list[Path] = []
    for path in AWS_ICON_EXTRACT_DIR.rglob("*.svg"):
        if not path.is_file():
            continue
        path_str = str(path)
        if "__MACOSX" in path_str or path.name.startswith("._"):
            continue
        normalized = _normalize_search_text(path_str)
        for kw in keywords:
            kw_norm = _normalize_search_text(kw)
            if kw_norm and kw_norm in normalized:
                candidates.append(path)
                break

    if not candidates:
        return None

    selected = sorted(candidates, key=lambda p: len(str(p)))[0]
    try:
        data = selected.read_bytes()
        return f"data:image/svg+xml;base64,{base64.b64encode(data).decode('ascii')}"
    except Exception:
        return None


def _get_official_package_icon_data_uri(icon_name: str) -> str | None:
    if not _ensure_official_icon_package():
        return None

    icon_file = _match_official_icon_file(icon_name)
    if not icon_file or not icon_file.exists():
        return None

    try:
        data = icon_file.read_bytes()
        if icon_file.suffix.lower() == ".svg":
            return f"data:image/svg+xml;base64,{base64.b64encode(data).decode('ascii')}"
        return f"data:image/png;base64,{base64.b64encode(data).decode('ascii')}"
    except Exception:
        return None


def _escape_style_value(value: str) -> str:
    """Escape style-delimiter characters for draw.io style values."""
    # draw.io style uses ';' as a key/value delimiter, so data URIs must escape it.
    return value.replace(";", "%3B")


def _to_drawio_image_uri(icon_uri: str) -> str:
    """Return a draw.io-safe image URI that avoids style delimiter issues."""
    prefix = "data:image/svg+xml;base64,"
    if icon_uri.startswith(prefix):
        encoded_svg = icon_uri[len(prefix):]
        svg_text = base64.b64decode(encoded_svg).decode("utf-8")
        # Use URL-encoded SVG payload to avoid ';base64' in style strings.
        return _escape_style_value(f"data:image/svg+xml,{quote(svg_text, safe='')}")

    if icon_uri.startswith("data:image/svg+xml,"):
        return _escape_style_value(icon_uri)

    # For PNG/JPEG/GIF data URIs, wrap inside an SVG image element, then URL-encode the SVG.
    # This avoids draw.io style parsing issues around ';base64' in style values on Confluence.
    binary_prefixes = (
        "data:image/png;base64,",
        "data:image/jpeg;base64,",
        "data:image/gif;base64,",
    )
    if any(icon_uri.startswith(p) for p in binary_prefixes):
        svg_wrapper = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64' viewBox='0 0 64 64'>"
            f"<image href='{icon_uri}' x='0' y='0' width='64' height='64' preserveAspectRatio='xMidYMid meet'/>"
            "</svg>"
        )
        return _escape_style_value(f"data:image/svg+xml,{quote(svg_wrapper, safe='')}")

    # Keep binary payload as-is (PNG/JPEG/GIF), but escape style delimiters so
    # draw.io does not split the URI into malformed style keys.
    return _escape_style_value(icon_uri)


def generate_aws_architecture_with_real_icons(components: list[dict], connections: list[dict]) -> str:
    """
    Generate professional AWS architecture diagram with actual AWS service icons.
    Uses draw.io's image support with base64-encoded SVG icons.
    """
    mxfile = ET.Element("mxfile", {"host": "Confluence", "modified": "", "agent": "", "version": "1.0", "type": "device"})
    diagram = ET.SubElement(mxfile, "diagram", {"id": "AWS_Architecture", "name": "High-level Architecture Diagram"})

    layer_order = ["Edge", "Network", "Platform", "Application", "Data"]
    layer_colors = {
           "Edge": "#FED7AA",
           "Network": "#BAE6FD",
           "Platform": "#BBFAA0",
           "Application": "#A5F3FC",
           "Data": "#FCD34D",
    }

    # Keep the HLD solution view concise: prioritize core runtime pipeline components.
    core_keywords = [
        "business app",
        "sftp",
        "transfer endpoint",
        "transfer family",
        "landing bucket",
        "raw landing",
        "validation processor",
        "processing queue",
        "curated database",
        "monitoring and alerts",
    ]
    control_plane_keywords = [
        "identity",
        "iam",
        "encryption",
        "secret",
        "threat",
        "vulnerability",
        "audit",
        "policy",
        "lineage",
        "cost",
        "privacy",
        "secure ci/cd",
    ]

    preserve_runtime_keywords = [
        "ukhsa intra identity",
        "azure entra id",
        "azure identity",
        "identity & access management (iam)",
    ]

    connections_for_diagram = list(connections)

    concise_components: list[dict] = []
    for comp in components:
        name = (comp.get("name") or "").lower()
        tech = (comp.get("technology") or "").lower()
        desc = (comp.get("description") or "").lower()
        haystack = f"{name} {tech} {desc}"

        if any(k in haystack for k in preserve_runtime_keywords):
            concise_components.append(comp)
            continue

        if any(k in haystack for k in control_plane_keywords):
            continue
        if any(k in haystack for k in core_keywords):
            concise_components.append(comp)

    # Ensure Azure identity/authentication is visible in HLD even when filtered from controls.
    identity_node_name = "Entra UKHSA Identity (Golden Source)"
    has_identity_node = any("entra" in (c.get("name") or "").lower() or "identity" in (c.get("name") or "").lower() for c in concise_components)
    if not has_identity_node:
        identity_candidate = next(
            (
                c for c in components
                if "entra" in (c.get("name") or "").lower()
                or "azure identity" in (c.get("name") or "").lower()
                or "identity & access management" in (c.get("name") or "").lower()
            ),
            None,
        )
        if identity_candidate:
            concise_components.append(identity_candidate)
            identity_node_name = identity_candidate.get("name") or identity_node_name
        else:
            concise_components.append({
                "name": identity_node_name,
                "technology": "Azure Entra ID",
                "description": "Golden source identity with federation and sync",
            })

    has_identity_connection = any(
        "identity" in ((conn.get("from") or "") + " " + (conn.get("to") or "") + " " + (conn.get("label") or "")).lower()
        or "entra" in ((conn.get("from") or "") + " " + (conn.get("to") or "") + " " + (conn.get("label") or "")).lower()
        for conn in connections_for_diagram
    )
    if not has_identity_connection:
        connections_for_diagram.append({
            "from": "Validation Processor",
            "to": identity_node_name,
            "label": "Authentication token validation (bi-directional)",
        })

    # Fallback for unexpected input: avoid empty output.
    if len(concise_components) < 4:
        concise_components = components

    # Enforce clear left-to-right runtime sequence for HLD readability.
    flow_order = [
        "on-prem business app",
        "on-prem sftp server",
        "identity",
        "entra",
        "aws transfer endpoint",
        "raw landing bucket",
        "validation processor",
        "processing queue",
        "curated database",
        "monitoring and alerts",
    ]

    def _flow_rank(comp: dict) -> tuple[int, str]:
        name_lc = (comp.get("name") or "").strip().lower()
        for idx, keyword in enumerate(flow_order):
            if keyword in name_lc:
                return (idx, name_lc)
        return (len(flow_order), name_lc)

    concise_components = sorted(concise_components, key=_flow_rank)
    component_direction_map = {
        (comp.get("name") or "").strip().lower(): (comp.get("direction") or "").strip().lower()
        for comp in concise_components
    }

    # Keep a single lane so the diagram naturally reads left -> right.
    layer_map = {layer: [] for layer in layer_order}
    layer_map["Application"] = concise_components

    lane_left = 30
    lane_top = 30
    lane_label_w = 140
    lane_gap = 24
    card_w = 190
    card_h = 145
    icon_w = 82
    icon_h = 82
    card_gap_x = 24
    card_gap_y = 20
    inner_left_pad = 22
    max_cols = max(1, len(concise_components))
    lane_inner_start = lane_left + lane_label_w + 20

    # Calculate pyramid tier structure for triangular layout
    total_comps = len(concise_components)
    pyramid_tiers = []
    tier_idx = 0
    comp_idx = 0
    while comp_idx < total_comps:
        tier_size = min(tier_idx + 1, total_comps - comp_idx)
        if tier_idx > 4:
            tier_size = total_comps - comp_idx
        pyramid_tiers.append(tier_size)
        comp_idx += tier_size
        tier_idx += 1
    
    max_tier_width = max(pyramid_tiers) if pyramid_tiers else 1
    
    occupied_layers = [l for l in layer_order if layer_map[l]]
    layer_heights = {}
    for layer in occupied_layers:
        count = len(layer_map[layer])
        num_tiers = len(pyramid_tiers) if pyramid_tiers else 1
        layer_heights[layer] = max(210, 22 + num_tiers * card_h + (num_tiers - 1) * card_gap_y + 22)

    right_panel_w = 320
    content_w = lane_inner_start + inner_left_pad + (max_tier_width * card_w) + ((max_tier_width - 1) * card_gap_x)
    page_w = max(2060, content_w + right_panel_w + 130)
    total_lane_h = sum(layer_heights.values()) + max(0, len(occupied_layers) - 1) * lane_gap
    page_h = max(1300, lane_top + total_lane_h + 100)
    lane_w = page_w - (lane_left + right_panel_w + 80)
    first_card_x = lane_inner_start + inner_left_pad
    def _is_onprem(comp: dict) -> bool:
        name_lc = (comp.get("name") or "").lower()
        return "on-prem" in name_lc or "on prem" in name_lc

    def _is_ukhsa_azure(comp: dict) -> bool:
        name_lc = (comp.get("name") or "").lower()
        return ("entra" in name_lc or "azure" in name_lc or "identity" in name_lc) and not _is_onprem(comp)

    def _is_ukhsa_aws(comp: dict) -> bool:
        name_lc = (comp.get("name") or "").lower()
        # UKHSA AWS components: transfer, landing, validation, processing, curated, monitoring
        ukhsa_aws_keywords = ["transfer endpoint", "landing bucket", "validation processor", "processing queue", "curated database", "monitoring"]
        return any(kw in name_lc for kw in ukhsa_aws_keywords)

    def _is_edap_aws(comp: dict) -> bool:
        name_lc = (comp.get("name") or "").lower()
        # EDAP is separate analytical account
        return "edap" in name_lc or ("aws" in name_lc and "edap" in name_lc)

    # Classify components by environment
    onprem_comps = [c for c in concise_components if _is_onprem(c)]
    azure_comps = [c for c in concise_components if _is_ukhsa_azure(c)]
    ukhsa_aws_comps = [c for c in concise_components if _is_ukhsa_aws(c)]
    edap_aws_comps = [c for c in concise_components if _is_edap_aws(c)]
    
    # Any remaining unclassified components go to UKHSA AWS by default
    classified = set()
    for c in onprem_comps + azure_comps + ukhsa_aws_comps + edap_aws_comps:
        classified.add((c.get("name") or "").lower())
    for c in concise_components:
        if (c.get("name") or "").lower() not in classified:
            ukhsa_aws_comps.append(c)

    # Calculate layout dimensions for 4 environment boxes side-by-side
    env_box_w = 450
    env_box_gap = 60
    env_box_h = 600
    env_height_spacing = env_box_h + 100
    
    # Reorder components: left-to-right flow across environments
    all_comps_by_env = [
        (onprem_comps, "UKHSA On-Premise", "#92400E", "#FEF3E2"),
        (azure_comps, "Entra UKHSA Identity (Golden Source)", "#1D4ED8", "#E8F1FF"),
        (ukhsa_aws_comps, "UKHSA AWS", "#0369A1", "#E0F2FE"),
        (edap_aws_comps, "EDAP AWS (Analytics)", "#7C3AED", "#F5E6FF"),
    ]
    
    # Recalculate page width to fit 4 boxes
    content_w = lane_inner_start + inner_left_pad + (4 * env_box_w) + (3 * env_box_gap)
    page_w = max(2400, content_w + right_panel_w + 60)
    lane_w = page_w - (lane_left + right_panel_w + 40)
    first_card_x = lane_inner_start + inner_left_pad

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

    def _wrap_words(text: str, width: int = 22) -> str:
        cleaned = " ".join((text or "").split())
        if not cleaned:
            return ""
        return "<br/>".join(textwrap.wrap(cleaned, width=width, break_long_words=False, break_on_hyphens=False))

    strategy_panel = ET.SubElement(root, "mxCell", {
        "id": "strategy-panel",
        "value": "",
        "style": "rounded=1;fillColor=#F8FAFD;strokeColor=#9AA5B1;strokeWidth=1.5;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(strategy_panel, "mxGeometry", {
        "x": str(page_w - right_panel_w - 24),
        "y": str(lane_top),
        "width": str(right_panel_w),
        "height": "220",
        "as": "geometry"
    })

    strategy_title = ET.SubElement(root, "mxCell", {
        "id": "strategy-title",
        "value": "Cloud Strategy Guardrails",
        "style": "text;fontSize=12;fontStyle=1;fillColor=none;strokeColor=none;align=left;spacingLeft=10;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(strategy_title, "mxGeometry", {
        "x": str(page_w - right_panel_w - 12),
        "y": str(lane_top + 8),
        "width": str(right_panel_w - 16),
        "height": "20",
        "as": "geometry"
    })

    strategy_text = ET.SubElement(root, "mxCell", {
        "id": "strategy-text",
        "value": "- This HLD view shows core runtime flow only\n- Identity golden source is Microsoft Entra ID (strategic landing zone)\n- Federation/sync supports Azure, AWS, and on-prem AD integration\n- Security/governance controls are detailed in Logical, Network, and Auth diagrams\n- Reliability via managed services and decoupled processing\n- Observability through monitoring and alerting",
        "style": "text;fontSize=10;fillColor=none;strokeColor=none;align=left;spacingLeft=10;whiteSpace=wrap;",
        "parent": "1",
        "vertex": "1"
    })
    ET.SubElement(strategy_text, "mxGeometry", {
        "x": str(page_w - right_panel_w - 12),
        "y": str(lane_top + 30),
        "width": str(right_panel_w - 16),
        "height": "180",
        "as": "geometry"
    })

    comp_cell = {}
    comp_geometry: dict[str, tuple[int, int]] = {}
    deferred_component_overlays: list[dict[str, str | int]] = []
    runtime_lane_y = lane_top
    runtime_lane_h = env_box_h
    
    # Create 4 environment boundaries
    env_positions = {}  # env_title -> (x_start, width, comps)
    current_env_x = first_card_x
    
    for env_comps, env_title, env_color, env_fill in all_comps_by_env:
        if not env_comps:
            continue
            
        env_boundary = ET.SubElement(root, "mxCell", {
            "id": f"env-boundary-{env_title.lower().replace(' ', '-')}",
            "value": "",
            "style": f"rounded=1;fillColor={env_fill};strokeColor={env_color};strokeWidth=2.5;dashed=1;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(env_boundary, "mxGeometry", {
            "x": str(current_env_x),
            "y": str(lane_top),
            "width": str(env_box_w),
            "height": str(env_box_h),
            "as": "geometry"
        })
        
        env_title_cell = ET.SubElement(root, "mxCell", {
            "id": f"env-title-{env_title.lower().replace(' ', '-')}",
            "value": env_title,
            "style": f"rounded=1;fillColor={env_color};strokeColor={env_color};strokeWidth=2;fontSize=12;fontStyle=1;align=center;verticalAlign=middle;fontColor=#FFFFFF;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(env_title_cell, "mxGeometry", {
            "x": str(current_env_x),
            "y": str(lane_top - 35),
            "width": str(env_box_w),
            "height": "30",
            "as": "geometry"
        })
        
        env_positions[env_title] = (current_env_x, env_box_w, env_comps)
        current_env_x += env_box_w + env_box_gap
    
    # Render components within each environment box
    for env_title, (env_x, env_box_w_val, env_comps) in env_positions.items():
        if not env_comps:
            continue
        
        # Calculate pyramid layout within this environment box
        total_comps = len(env_comps)
        pyramid_tiers = []
        tier_idx = 0
        comp_idx = 0
        while comp_idx < total_comps:
            tier_size = min(tier_idx + 1, total_comps - comp_idx)
            if tier_idx > 4:
                tier_size = total_comps - comp_idx
            pyramid_tiers.append(tier_size)
            comp_idx += tier_size
            tier_idx += 1
        
        max_tier_width = max(pyramid_tiers) if pyramid_tiers else 1
        
        # Render each component within its environment
        for i, comp in enumerate(env_comps):
            comp_name = (comp.get("name") or "Unnamed Component").strip()
            tech = (comp.get("technology") or "").strip()
            desc = (comp.get("description") or "").strip()
            slug = re.sub(r"[^a-z0-9]+", "-", comp_name.lower()).strip("-") or f"component-{i}"

            # Find which tier this component belongs to
            tier_row = 0
            comp_in_tier = 0
            tier_pos = 0
            for tier_idx, tier_size in enumerate(pyramid_tiers):
                if comp_in_tier + tier_size > i:
                    tier_row = tier_idx
                    tier_pos = i - comp_in_tier
                    break
                comp_in_tier += tier_size
            
            # Calculate position within tier (centered horizontally within environment box)
            tier_width = pyramid_tiers[tier_row]
            tier_total_width = tier_width * card_w + (tier_width - 1) * card_gap_x
            env_inner_x = env_x + (env_box_w_val - tier_total_width) / 2
            
            card_x = int(env_inner_x + tier_pos * (card_w + card_gap_x))
            card_y = lane_top + 50 + tier_row * (card_h + card_gap_y)
            
            card_id = f"c-{slug}"
            icon_id = f"{card_id}-icon"
            text_id = f"{card_id}-text"
            comp_cell[comp_name.lower()] = card_id
            comp_geometry[comp_name.lower()] = (card_x, card_y)

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

            icon_url = get_component_icon_url(comp_name, tech, desc)
            label_lines = [_wrap_words(comp_name, width=22)]
            if tech:
                label_lines.append(f"<span style='font-size:10px;color:#475467;'>[{_wrap_words(tech, width=24)}]</span>")
            label_text = "<br/>".join([line for line in label_lines if line])
            deferred_component_overlays.append({
                "icon_id": icon_id,
                "text_id": text_id,
                "icon_url": icon_url,
                "label_text": label_text,
                "card_x": card_x,
                "card_y": card_y,
            })

    # Add connections with explicit labels for HLD readability.
    legend_items = []
    valid_edge_count = 0
    source_anchor_counts: dict[tuple[str, str], int] = {}
    target_anchor_counts: dict[tuple[str, str], int] = {}
    anchor_slots_by_direction = {
        "One-way": ["0.24", "0.40", "0.56"],
        "Bi-directional": ["0.68", "0.80", "0.92"],
    }
    
    for i, conn in enumerate(connections_for_diagram):
        src = comp_cell.get(conn["from"].lower())
        tgt = comp_cell.get(conn["to"].lower())
        
        if not src or not tgt:
            print(f"  Warning: Skipping connection: {conn['from']} -> {conn['to']} (not found)")
            continue

        valid_edge_count += 1
        full_label = conn.get("label", "")
        edge_num = str(valid_edge_count)
        route_hint = f"{conn.get('from', '')} {conn.get('to', '')} {full_label}".lower()
        edge_label = edge_num

        stroke_color = "#2563EB"
        dashed = "0"
        bidirectional = any(x in route_hint for x in [
            "bi-directional", "bidirectional", "two-way", "two way", "both ways", "both directions", "<->", "↔"
        ])
        if not bidirectional:
            src_name_lc = (conn.get("from") or "").strip().lower()
            tgt_name_lc = (conn.get("to") or "").strip().lower()
            src_direction = component_direction_map.get(src_name_lc, "")
            tgt_direction = component_direction_map.get(tgt_name_lc, "")
            service_style_keywords = [
                "processing queue",
                "monitoring and alerts",
                "identity",
                "entra",
            ]
            touches_service_style_endpoint = any(
                keyword in src_name_lc or keyword in tgt_name_lc
                for keyword in service_style_keywords
            )
            if touches_service_style_endpoint and (src_direction == "both" or tgt_direction == "both"):
                bidirectional = True
        direction_name = "Bi-directional" if bidirectional else "One-way"
        stroke_color = "#059669" if bidirectional else "#2563EB"
        edge_label = f"{edge_num}↔" if bidirectional else f"{edge_num}→"
        if any(x in route_hint for x in ["vpn", "private", "internal", "direct connect"]):
            dashed = "1"

        start_arrow = "block" if bidirectional else "none"
        start_fill = "1" if bidirectional else "0"
        start_arrow_size = "14" if bidirectional else "0"

        # Route connectors away from icon centers by anchoring edges near card perimeters.
        edge_anchor_style = ""
        src_key = conn.get("from", "").lower()
        tgt_key = conn.get("to", "").lower()
        src_pos = comp_geometry.get(src_key)
        tgt_pos = comp_geometry.get(tgt_key)
        if src_pos and tgt_pos:
            direction_slots = anchor_slots_by_direction[direction_name]
            src_slot_key = (src_key, direction_name)
            tgt_slot_key = (tgt_key, direction_name)
            src_slot = source_anchor_counts.get(src_slot_key, 0)
            tgt_slot = target_anchor_counts.get(tgt_slot_key, 0)
            source_anchor_counts[src_slot_key] = src_slot + 1
            target_anchor_counts[tgt_slot_key] = tgt_slot + 1
            src_fraction = direction_slots[src_slot % len(direction_slots)]
            tgt_fraction = direction_slots[tgt_slot % len(direction_slots)]
            dx = tgt_pos[0] - src_pos[0]
            dy = tgt_pos[1] - src_pos[1]
            if abs(dx) >= abs(dy):
                if dx >= 0:
                    edge_anchor_style = f"exitX=1;exitY={src_fraction};entryX=0;entryY={tgt_fraction};exitPerimeter=1;entryPerimeter=1;"
                else:
                    edge_anchor_style = f"exitX=0;exitY={src_fraction};entryX=1;entryY={tgt_fraction};exitPerimeter=1;entryPerimeter=1;"
            else:
                if dy >= 0:
                    edge_anchor_style = f"exitX={src_fraction};exitY=1;entryX={tgt_fraction};entryY=0;exitPerimeter=1;entryPerimeter=1;"
                else:
                    edge_anchor_style = f"exitX={src_fraction};exitY=0;entryX={tgt_fraction};entryY=1;exitPerimeter=1;entryPerimeter=1;"
        
        edge = ET.SubElement(root, "mxCell", {
            "id": f"e-{i}",
            "value": edge_label,
            "style": f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=26;segment=20;{edge_anchor_style}sourcePerimeterSpacing=28;targetPerimeterSpacing=28;html=1;whiteSpace=wrap;align=center;verticalAlign=middle;fontSize=18;fontStyle=1;fontColor=#111111;labelBackgroundColor=#FEF9C3;labelBorderColor=#CA8A04;spacing=6;animation=1;startArrow={start_arrow};startFill={start_fill};startArrowSize={start_arrow_size};endArrow=block;endFill=1;endArrowSize=18;strokeWidth=2.5;strokeColor={stroke_color};dashed={dashed};",
            "parent": "1",
            "source": src,
            "target": tgt,
            "edge": "1"
        })
        edge_geometry_attrs = {"relative": "1", "as": "geometry"}
        if "queue depth monitoring" in full_label.lower():
            # Move this label below the edge so it does not overlap the database icon/card.
            edge_geometry_attrs["x"] = "-0.18"
            edge_geometry_attrs["y"] = "60"
        ET.SubElement(edge, "mxGeometry", edge_geometry_attrs)
        
        legend_items.append({
            "num": edge_num,
            "from": conn.get("from", ""),
            "to": conn.get("to", ""),
            "label": full_label,
            "direction": direction_name,
        })

    # Add legend box on the right side
    if legend_items:
        legend_x = int(page_w - right_panel_w - 24)
        legend_y = lane_top + 240
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
            "height": str(max(120, 38 + len(legend_items) * 52)),
            "as": "geometry"
        })
        
        legend_title = ET.SubElement(root, "mxCell", {
            "id": "legend-title",
            "value": "Connection Summary",
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
        
        for idx, item in enumerate(legend_items):
            num = item["num"]
            item_y = legend_y + 30 + idx * 52
            detail = (item.get("label") or "").strip() or "No additional details provided"
            item_text = (
                f"<b>Stage {num}</b>: {item.get('from', '')} -> {item.get('to', '')} [{item.get('direction', 'One-way')}]"
                f"<br/><span style='font-size:9px;color:#334155;'>{_wrap_words(detail, width=38)}</span>"
            )
            
            legend_item = ET.SubElement(root, "mxCell", {
                "id": f"legend-item-{num}",
                "value": item_text,
                "style": "text;html=1;fontSize=10;fillColor=none;strokeColor=none;align=left;spacingLeft=10;whiteSpace=wrap;verticalAlign=top;",
                "parent": "1",
                "vertex": "1"
            })
            ET.SubElement(legend_item, "mxGeometry", {
                "x": str(legend_x + 10),
                "y": str(item_y),
                "width": str(legend_w - 20),
                "height": "48",
                "as": "geometry"
            })

        legend_direction_key = ET.SubElement(root, "mxCell", {
            "id": "legend-direction-key",
            "value": "Arrow colours: Blue = One-way, Green = Bi-directional",
            "style": "text;fontSize=10;fontStyle=1;fillColor=none;strokeColor=none;align=left;spacingLeft=10;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(legend_direction_key, "mxGeometry", {
            "x": str(legend_x + 10),
            "y": str(legend_y + max(92, 34 + len(legend_items) * 52)),
            "width": str(legend_w - 20),
            "height": "18",
            "as": "geometry"
        })

    # Render icons and labels after edges so connectors do not visually sit on top of icons.
    for overlay in deferred_component_overlays:
        icon_style = "shape=mxgraph.basic.image;"
        icon_url = str(overlay["icon_url"] or "")
        if icon_url:
            drawio_icon_uri = _to_drawio_image_uri(icon_url)
            icon_style = f"shape=image;image={drawio_icon_uri};imageAspect=1;aspect=fixed;"

        icon = ET.SubElement(root, "mxCell", {
            "id": str(overlay["icon_id"]),
            "value": "",
            "style": icon_style + "strokeColor=none;fillColor=none;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(icon, "mxGeometry", {
            "x": str(int(overlay["card_x"]) + (card_w - icon_w) // 2),
            "y": str(int(overlay["card_y"]) + 10),
            "width": str(icon_w),
            "height": str(icon_h),
            "as": "geometry"
        })

        text = ET.SubElement(root, "mxCell", {
            "id": str(overlay["text_id"]),
            "value": str(overlay["label_text"]),
            "style": "text;html=1;whiteSpace=wrap;align=center;verticalAlign=top;fontSize=11;spacingTop=2;spacingLeft=2;spacingRight=2;strokeColor=none;fillColor=none;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(text, "mxGeometry", {
            "x": str(int(overlay["card_x"]) + 8),
            "y": str(int(overlay["card_y"]) + 98),
            "width": str(card_w - 16),
            "height": str(card_h - 102),
            "as": "geometry"
        })

    # Format XML
    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_detailed_network_diagram(
    components: list[dict],
    connections: list[dict],
    network_spec: dict | None = None,
) -> str:
    """
    Generate detailed network diagram showing security groups, subnets, and routing.
    The optional network_spec allows the main page to drive CIDRs, controls, and labels.
    """
    spec = network_spec or {}
    vpc_cidr = spec.get("vpc_cidr") or "10.0.0.0/16"
    public_subnet_cidr = spec.get("public_subnet_cidr") or "10.0.1.0/24"
    private_subnet_cidr = spec.get("private_subnet_cidr") or "10.0.2.0/24"
    data_subnet_cidr = spec.get("data_subnet_cidr") or "10.0.3.0/24"
    on_prem_cidr = spec.get("on_prem_cidr") or "172.16.0.0/16"
    connectivity_type = spec.get("connectivity_type") or "Site-to-Site VPN"
    public_ingress = spec.get("public_ingress") or "Internet -> IGW -> ALB"
    private_ingress = spec.get("private_ingress") or "On-prem -> VPN -> Private Route Table -> EKS"
    sg_public_rule = spec.get("sg_public_rule") or "HTTP(80), HTTPS(443)"
    sg_private_rule = spec.get("sg_private_rule") or "Internal east-west only"
    sg_data_rule = spec.get("sg_data_rule") or "DB ports (3306, 5432, 6379)"
    route_public = spec.get("route_public") or "0.0.0.0/0 via IGW"
    route_private = spec.get("route_private") or "On-prem CIDR via VPN"

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

    def add_icon_node(node_id: str, label: str, icon_key: str, x: int, y: int, w: int = 140, h: int = 120) -> None:
        icon_url = _get_remote_icon_data_uri(icon_key) or AWS_SERVICE_ICONS.get(icon_key) or AWS_SERVICE_ICONS.get("Generic")
        icon_style = "shape=mxgraph.basic.image;"
        if icon_url:
            icon_style = f"shape=image;image={_to_drawio_image_uri(icon_url)};imageAspect=1;aspect=fixed;"

        icon = ET.SubElement(root, "mxCell", {
            "id": f"{node_id}-icon",
            "value": "",
            "style": icon_style + "strokeColor=none;fillColor=none;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(icon, "mxGeometry", {
            "x": str(x),
            "y": str(y),
            "width": str(w),
            "height": str(h - 28),
            "as": "geometry"
        })

        text = ET.SubElement(root, "mxCell", {
            "id": f"{node_id}-text",
            "value": label,
            "style": "text;html=1;whiteSpace=wrap;align=center;verticalAlign=top;fontSize=11;fontStyle=1;strokeColor=none;fillColor=none;",
            "parent": "1",
            "vertex": "1"
        })
        ET.SubElement(text, "mxGeometry", {
            "x": str(x - 10),
            "y": str(y + h - 28),
            "width": str(w + 20),
            "height": "30",
            "as": "geometry"
        })

    # Draw VPC boundary (large rectangle)
    vpc = ET.SubElement(root, "mxCell", {
        "id": "vpc",
        "value": f"AWS VPC ({vpc_cidr})",
        "style": "rounded=0;fillColor=#F6FBFF;strokeColor=#146EB4;strokeWidth=3;dashed=1;fontSize=12;fontStyle=1;",
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
        "value": f"Public Subnet ({public_subnet_cidr})",
        "style": "rounded=0;fillColor=#EAF3FF;strokeColor=#2A6FB0;strokeWidth=2;dashed=1;fontSize=11;fontStyle=1;",
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
        "value": f"Private Subnet ({private_subnet_cidr})",
        "style": "rounded=0;fillColor=#EDF9ED;strokeColor=#2F855A;strokeWidth=2;dashed=1;fontSize=11;fontStyle=1;",
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
        "value": f"Data Subnet ({data_subnet_cidr})",
        "style": "rounded=0;fillColor=#FFF8E8;strokeColor=#A16911;strokeWidth=2;dashed=1;fontSize=11;fontStyle=1;",
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

    # Public/Private access and network boundary icons
    add_icon_node("internet", "Internet", "CloudFront", 55, 12, 120, 110)
    add_icon_node("igw", "Internet Gateway", "InternetGateway", 235, 12, 120, 110)
    add_icon_node("vpn", connectivity_type, "VPN", 430, 12, 130, 110)
    add_icon_node("onprem", f"On-Prem ({on_prem_cidr})", "DirectConnect", 600, 12, 130, 110)
    add_icon_node("azure-vnet", "Azure Network (VNet)", "AzureNetwork", 770, 12, 140, 110)
    add_icon_node("azure-identity", "Azure Entra ID\n(SSO + MFA)", "AzureIdentity", 950, 12, 140, 110)
    add_icon_node("vpc-icon", "VPC", "VPC", 1440, 12, 110, 105)
    add_icon_node("pub-subnet-icon", "Public Subnet", "PublicSubnet", 360, 78, 100, 92)
    add_icon_node("priv-subnet-icon", "Private Subnet", "PrivateSubnet", 910, 78, 100, 92)
    add_icon_node("data-subnet-icon", "Data Subnet", "DataSubnet", 1410, 78, 100, 92)

    # Security groups
    sg_public = ET.SubElement(root, "mxCell", {
        "id": "sg-pub",
        "value": f"SG: {sg_public_rule}",
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
    add_icon_node("sg-pub-icon", "Security Group", "SecurityGroup", 72, 126, 90, 82)

    sg_private = ET.SubElement(root, "mxCell", {
        "id": "sg-priv",
        "value": f"SG: {sg_private_rule}",
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
    add_icon_node("sg-priv-icon", "Security Group", "SecurityGroup", 622, 126, 90, 82)

    sg_data = ET.SubElement(root, "mxCell", {
        "id": "sg-data",
        "value": f"SG: {sg_data_rule}",
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
    add_icon_node("sg-data-icon", "Security Group", "SecurityGroup", 1172, 126, 90, 82)

    # Services in subnets (real icons)
    add_icon_node("alb", "Application Load Balancer", "ALB", 190, 140)
    add_icon_node("nat", "NAT Gateway", "NAT Gateway", 355, 140)
    add_icon_node("app", "EKS Cluster", "EKS", 735, 140)
    add_icon_node("route-private", f"Route Table\n{route_private}", "RouteTable", 900, 140)
    add_icon_node("db-rds", "RDS Aurora", "RDS", 1260, 140)

    # Connectivity paths with explicit public/private/VPN separation
    flows = [
        ("internet-icon", "igw-icon", public_ingress, "#D97706", 0),
        ("igw-icon", "alb-icon", route_public, "#D97706", 0),
        ("alb-icon", "app-icon", "App traffic", "#2563EB", 0),
        ("app-icon", "db-rds-icon", "Private DB query", "#2F855A", 0),
        ("onprem-icon", "vpn-icon", connectivity_type, "#0369A1", 1),
        ("onprem-icon", "azure-vnet-icon", "Private identity/network link", "#1D4ED8", 1),
        ("azure-vnet-icon", "azure-identity-icon", "SSO + MFA authentication", "#1D4ED8", 0),
        ("azure-identity-icon", "app-icon", "Federated token to app/API", "#1D4ED8", 0),
        ("vpn-icon", "route-private-icon", private_ingress, "#0369A1", 1),
        ("route-private-icon", "app-icon", "East-west private traffic", "#0369A1", 1),
    ]

    for i, (from_id, to_id, label, color, dashed) in enumerate(flows):
        edge = ET.SubElement(root, "mxCell", {
            "id": f"flow-{i}",
            "value": label,
            "style": f"edgeStyle=orthogonalEdgeStyle;rounded=1;fontSize=9;strokeWidth=2;strokeColor={color};fontStyle=1;dashed={dashed};endArrow=block;endFill=1;",
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
        "value": "Legend:\nOrange solid = Public ingress\nGreen solid = Private app/data path\nBlue dashed = VPN path from on-prem\nBlue solid = Azure identity/authentication path\nDashed boxes = Security boundaries",
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

# Template rule contract used by all projects that consume this generator.
# Keys in auth_rules:
# - include_reauth_on_validation_failure: include failed-validation -> reauthentication loop.
# - include_mfa_challenge: include explicit MFA challenge step.
# - include_token_refresh: include token refresh/reissue response path.
# - flow_mode: currently supports "sequence" and defaults to sequence-style output.
AUTH_FLOW_TEMPLATE_RULES = {
    "include_reauth_on_validation_failure": True,
    "include_mfa_challenge": True,
    "include_token_refresh": True,
    "flow_mode": "sequence",
}


def _build_auth_sequence_messages(auth_rules: dict | None = None) -> list[tuple[str, str, str, str, bool]]:
    rules = dict(AUTH_FLOW_TEMPLATE_RULES)
    if auth_rules:
        rules.update({k: v for k, v in auth_rules.items() if v is not None})

    messages = [
        ("user", "webapp", "1. Login request", "#111827", False),
        ("webapp", "api", "2. Forward to API", "#111827", False),
        ("api", "azure-vnet", "3. Identity request", "#1D4ED8", False),
    ]

    if rules.get("include_mfa_challenge", True):
        messages.append(("azure-vnet", "azure-identity", "4. SSO + MFA challenge", "#1D4ED8", False))
    else:
        messages.append(("azure-vnet", "azure-identity", "4. SSO challenge", "#1D4ED8", False))

    if rules.get("include_token_refresh", True):
        messages.extend([
            ("azure-identity", "api", "5. Federated token issued", "#1D4ED8", True),
            ("api", "webapp", "6. Token returned", "#1D4ED8", True),
        ])
    else:
        messages.extend([
            ("azure-identity", "api", "5. Access granted", "#1D4ED8", True),
            ("api", "webapp", "6. Authorization confirmed", "#1D4ED8", True),
        ])

    messages.extend([
        ("webapp", "service", "7. API call + token", "#111827", False),
        ("service", "db", "8. Query with auth context", "#111827", False),
    ])

    if rules.get("include_reauth_on_validation_failure", True):
        messages.extend([
            ("service", "api", "9. Token validation failed / expired", "#B91C1C", True),
            ("api", "webapp", "10. 401 Unauthorized - reauthenticate", "#B91C1C", True),
            ("webapp", "user", "11. Prompt for sign-in again", "#B91C1C", True),
            ("user", "webapp", "12. Re-enter credentials", "#111827", False),
            ("webapp", "api", "13. Reinitiate authentication flow", "#111827", False),
            ("api", "azure-identity", "14. New token request", "#1D4ED8", False),
            ("azure-identity", "api", "15. New token issued", "#1D4ED8", True),
            ("api", "service", "16. Retry processing with new token", "#111827", False),
        ])

    return messages


def generate_authentication_flow_diagram(auth_rules: dict | None = None) -> str:
    """Generate authentication flow as a sequence-style diagram (backward compatible)."""
    rules = dict(AUTH_FLOW_TEMPLATE_RULES)
    if auth_rules:
        rules.update({k: v for k, v in auth_rules.items() if v is not None})

    identity_desc = "SSO + MFA" if rules.get("include_mfa_challenge", True) else "SSO"

    mxfile = ET.Element("mxfile", {"host": "Confluence", "type": "device", "version": "1.0"})
    diagram = ET.SubElement(mxfile, "diagram", {"name": "Authentication Flow Sequence"})
    
    model = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "1600",
        "dy": "1600",
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
        "pageHeight": "1600",
        "math": "0",
        "shadow": "0"
    })
    
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    participants = [
        ("user", "User", "Consumer", "#FF9900"),
        ("webapp", "Web App", "Frontend", "#4B9BFF"),
        ("api", "API Gateway", "Backend API", "#FF9900"),
        ("azure-vnet", "Azure Network", "Identity Network", "#0078D4"),
        ("azure-identity", "Azure Entra ID", identity_desc, "#0078D4"),
        ("service", "Service", "Application", "#4B9BFF"),
        ("db", "Database", "Data Store", "#2262FF"),
    ]

    x_start = 60
    x_gap = 190
    head_y = 60
    head_w = 150
    head_h = 54
    line_y = 130
    line_h = 1300

    x_positions = {}
    for idx, (pid, name, desc, color) in enumerate(participants):
        x = x_start + idx * x_gap
        x_positions[pid] = x + (head_w // 2)

        head = ET.SubElement(root, "mxCell", {
            "id": pid,
            "value": f"{name}\n({desc})",
            "style": f"rounded=1;fillColor={color};strokeColor=#1F2937;strokeWidth=2;fontSize=11;fontStyle=1;align=center;verticalAlign=middle;",
            "parent": "1",
            "vertex": "1",
        })
        ET.SubElement(head, "mxGeometry", {
            "x": str(x),
            "y": str(head_y),
            "width": str(head_w),
            "height": str(head_h),
            "as": "geometry",
        })

        lifeline = ET.SubElement(root, "mxCell", {
            "id": f"{pid}-lifeline",
            "value": "",
            "style": "shape=line;strokeColor=#6B7280;dashed=1;strokeWidth=2;",
            "parent": "1",
            "vertex": "1",
        })
        ET.SubElement(lifeline, "mxGeometry", {
            "x": str(x + (head_w // 2) - 1),
            "y": str(line_y),
            "width": "2",
            "height": str(line_h),
            "as": "geometry",
        })

    messages = _build_auth_sequence_messages(rules)

    y = 190
    y_step = 95
    for i, (from_id, to_id, label, color, is_response) in enumerate(messages):
        source_anchor = ET.SubElement(root, "mxCell", {
            "id": f"msg-{i}-src",
            "value": "",
            "style": "ellipse;fillColor=none;strokeColor=none;",
            "parent": "1",
            "vertex": "1",
        })
        ET.SubElement(source_anchor, "mxGeometry", {
            "x": str(x_positions[from_id] - 3),
            "y": str(y - 3),
            "width": "6",
            "height": "6",
            "as": "geometry",
        })

        target_anchor = ET.SubElement(root, "mxCell", {
            "id": f"msg-{i}-tgt",
            "value": "",
            "style": "ellipse;fillColor=none;strokeColor=none;",
            "parent": "1",
            "vertex": "1",
        })
        ET.SubElement(target_anchor, "mxGeometry", {
            "x": str(x_positions[to_id] - 3),
            "y": str(y - 3),
            "width": "6",
            "height": "6",
            "as": "geometry",
        })

        line_style = (
            f"edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;"
            f"endArrow=block;endFill=1;strokeColor={color};fontSize=10;fontStyle=1;"
            f"dashed={'1' if is_response else '0'};"
        )
        edge = ET.SubElement(root, "mxCell", {
            "id": f"flow-{i}",
            "value": label,
            "style": line_style,
            "parent": "1",
            "source": f"msg-{i}-src",
            "target": f"msg-{i}-tgt",
            "edge": "1",
        })
        ET.SubElement(edge, "mxGeometry", {"relative": "1", "as": "geometry"})
        y += y_step

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def generate_network_segregation_diagram(network_spec: dict | None = None) -> str:
    """Generate network segregation diagram (backward compatible)."""
    return generate_detailed_network_diagram([], [], network_spec)
