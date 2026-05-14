import os, requests, re
from dotenv import load_dotenv
load_dotenv()

base = os.getenv('CONFLUENCE_BASE_URL')
auth = (os.getenv('CONFLUENCE_USER_EMAIL'), os.getenv('CONFLUENCE_API_TOKEN'))
r = requests.get(f'{base}/rest/api/content/520783944?expand=body.storage', auth=auth)
body = r.json().get('body', {}).get('storage', {}).get('value', '')

# Get content before Section 1
intro_end = body.find('section1')
intro = body[:intro_end] if intro_end > 0 else body[:10000]

# Extract each structured macro
macros = re.findall(r'<ac:structured-macro[^>]*>(.*?)</ac:structured-macro>', intro, re.DOTALL)
for i, m in enumerate(macros):
    t_match = re.search(r'ac:name="title">(.*?)</ac:parameter>', m, re.DOTALL)
    b_match = re.search(r'<ac:rich-text-body>(.*?)</ac:rich-text-body>', m, re.DOTALL)
    title = re.sub(r'<[^>]+>', '', t_match.group(1)).strip() if t_match else 'untitled'
    content = re.sub(r'<[^>]+>', ' ', b_match.group(1)).strip() if b_match else ''
    content = re.sub(r'\s+', ' ', content)
    print(f'=== PANEL {i+1}: {title} ===')
    print(content[:3000])
    print()
