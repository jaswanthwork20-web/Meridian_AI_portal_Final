"""
Confluence Ingest Module
Downloads or syncs space documentation from Atlassian Confluence Cloud API into local docs.
"""
import os
import json
import base64
import urllib.request
import re

CONFLUENCE_URL = os.getenv("CONFLUENCE_BASE_URL", "https://agnishpaul2002.atlassian.net/wiki")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL", "agnishpaul2002@gmail.com")
CONFLUENCE_API_KEY = os.getenv("CONFLUENCE_API_KEY", "")
CONFLUENCE_SPACE = os.getenv("CONFLUENCE_SPACE_KEY", "SELFHELP")

def fetch_confluence_pages(space_key: str = CONFLUENCE_SPACE) -> list[dict]:
    if not CONFLUENCE_API_KEY:
        print("[Ingest] No CONFLUENCE_API_KEY set. Skipping live sync.")
        return []
    url = f"{CONFLUENCE_URL}/rest/api/content?spaceKey={space_key}&expand=body.storage,version"
    auth_str = f"{CONFLUENCE_EMAIL}:{CONFLUENCE_API_KEY}"
    auth_header = "Basic " + base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    req = urllib.request.Request(url, headers={"Authorization": auth_header, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("results", [])
    except Exception as e:
        print(f"[Ingest Error]: {e}")
        return []

def strip_html_tags(html: str) -> str:
    clean = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', clean).strip()

def sync_to_docs(output_dir: str):
    pages = fetch_confluence_pages()
    for p in pages:
        title = p.get("title", "Untitled")
        html_body = p.get("body", {}).get("storage", {}).get("value", "")
        text = strip_html_tags(html_body)
        fname = re.sub(r'[^a-zA-Z0-9_-]', '_', title) + ".md"
        with open(os.path.join(output_dir, fname), "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n{text}\n")
    print(f"[Ingest] Synced {len(pages)} pages to {output_dir}")

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    sync_to_docs(os.path.join(base, "docs"))
