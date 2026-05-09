#!/usr/bin/env python3
"""Check what tables exist on the HLD page."""

import os
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

load_dotenv()

base_url = os.getenv('CONFLUENCE_BASE_URL', 'https://ukhsa.atlassian.net/wiki').rstrip('/')
space_key = os.getenv('CONFLUENCE_SPACE_KEY', 'CDA')
api_token = os.getenv('CONFLUENCE_API_TOKEN', '').strip()

session = requests.Session()
session.headers.update({'Authorization': f'Bearer {api_token}', 'Accept': 'application/json'})

resp = session.get(
    f'{base_url}/rest/api/content',
    params={
        'spaceKey': space_key,
        'title': 'High-level Design (HLD) Solution Architecture Template',
        'expand': 'body.storage'
    },
    verify=False
)

if resp.status_code == 200:
    results = resp.json().get('results', [])
    if results:
        page = results[0]
        html = page['body']['storage']['value']
        soup = BeautifulSoup(html, 'html.parser')
        
        print(f"\n✓ Found HLD page: {page['title']}")
        print(f"  Page ID: {page['id']}")
        print(f"\nSections on this page:")
        print("=" * 70)
        
        # Find all headings and tables
        for tag in soup.find_all(['h2', 'h3', 'h4', 'table']):
            if tag.name in ['h2', 'h3', 'h4']:
                text = tag.get_text(strip=True)
                print(f"\n{tag.name.upper()}: {text}")
            elif tag.name == 'table':
                # Count rows in table
                rows = tag.find_all('tr')
                header_row = rows[0] if rows else None
                data_rows = rows[1:] if len(rows) > 1 else []
                
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                    print(f"   Table with {len(data_rows)} data rows")
                    print(f"   Columns: {' | '.join(headers)}")
                    
                    # Show first data row as sample
                    if data_rows:
                        first_row = [td.get_text(strip=True) for td in data_rows[0].find_all(['td', 'th'])]
                        print(f"   Sample: {' | '.join(first_row[:3])}...")
    else:
        print("✗ HLD page not found in Confluence")
        print(f"  Searched for: 'High-level Design (HLD) Solution Architecture Template' in space '{space_key}'")
else:
    print(f"✗ Error fetching page: {resp.status_code}")
    print(resp.text[:500])
