import html as _html
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("CONFLUENCE_API_TOKEN", "")
r = requests.get(
    "https://ukhsa.atlassian.net/wiki/rest/api/content/520783944",
    params={"expand": "body.storage,version"},
    headers={"Authorization": f"Bearer {token}"},
    verify=False,
)
data = r.json()
body = data["body"]["storage"]["value"]
print("VERSION:", data["version"]["number"])

for macro, label in [("tip", "FAST FILL"), ("info", "HOW TO USE")]:
    m = re.search(
        r'<ac:structured-macro\s+ac:name="' + macro + r'"[^>]*>.*?<ac:rich-text-body>(.*?)</ac:rich-text-body>',
        body, re.DOTALL,
    )
    print(f"\n=== {label} ===")
    if m:
        text = _html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).strip()
        print(text[:500])
    else:
        print("NOT FOUND")
