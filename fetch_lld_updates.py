#!/usr/bin/env python3
"""Fetch latest LLD updates from Confluence and sync to local template."""
import os
import requests
from confluence_enhance_main_page import find_page_by_title, save_synced_template, _make_request, get_tls_verify

base_url = os.getenv('CONFLUENCE_BASE_URL', 'https://ukhsa.atlassian.net/wiki').rstrip('/')
space_key = os.getenv('CONFLUENCE_SPACE_KEY', 'CDA')
title = 'High-level Design (HLD) Solution Architecture Template'

session = requests.Session()
session.headers.update({'Accept': 'application/json'})

try:
    print(f"Fetching latest page '{title}' from Confluence...")
    page = find_page_by_title(session, base_url, space_key, title)
    current_body = page.get('body', {}).get('storage', {}).get('value', '')
    if current_body:
        save_synced_template(current_body)
        print("✓ Successfully synced latest page from Confluence (including manual LLD updates)")
    else:
        print("✗ No page body found")
except Exception as e:
    print(f"✗ Error fetching page: {e}")
    import traceback
    traceback.print_exc()
