#!/usr/bin/env python3
"""Extract LLD updates from synced template."""
import re
from html import unescape

with open('main_page_template.synced.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find Section 16 (LLD Summary)
match = re.search(r'<h2[^>]*>16\..*?Low-Level Design.*?</h2>(.*?)(?=<h2[^>]*>17\.)', html, re.DOTALL | re.IGNORECASE)

if match:
    section = match.group(1)
    # Extract all table cell content
    cells = re.findall(r'<p[^>]*>([^<]*)</p>', section)
    print("LLD Table cells with content:")
    print("=" * 100)
    for i, cell in enumerate(cells):
        clean = unescape(cell.strip())
        if clean and not clean.startswith('local-id'):
            print(f"Row {i}: {clean}")
else:
    print("LLD Section not found")
