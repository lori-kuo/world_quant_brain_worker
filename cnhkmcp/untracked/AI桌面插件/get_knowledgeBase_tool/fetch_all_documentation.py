"""Minimal helper script to log in, list tutorials, and dump each tutorial page.

- Prompts for email/password at runtime (keeps credentials out of source).
- Uses only the requests standard stack; no project-internal imports.
- Saves each page JSON to tutorial_dump/<index>_<page_id>.json for inspection.

Run with: python doc_fetch_sample.py
"""
import base64
import getpass
import json
import os
from typing import Any, Dict, Iterable, List, Optional

import requests

BASE_URL = "https://api.worldquantbrain.com"


def _basic_auth_header(email: str, password: str) -> Dict[str, str]:
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def authenticate(email: str, password: str) -> requests.Session:
    """Authenticate and return a session carrying the JWT cookie."""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/authentication", headers=_basic_auth_header(email, password), timeout=30)
    if resp.status_code != 201:
        raise RuntimeError(f"Authentication failed (status {resp.status_code}): {resp.text}")
    return session


def fetch_tutorials(session: requests.Session) -> List[Dict[str, Any]]:
    """Fetch tutorials list; handle a few common response shapes."""
    resp = session.get(f"{BASE_URL}/tutorials", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "results", "data", "tutorials"):
            maybe = data.get(key)
            if isinstance(maybe, list):
                return maybe
    return []


def fetch_tutorial_pages(session: requests.Session, tutorial_id: str) -> List[Dict[str, Any]]:
    """Fetch pages for a tutorial when the list entry only gives a tutorial id/slug."""
    resp = session.get(f"{BASE_URL}/tutorials/{tutorial_id}/pages", timeout=30)
    if resp.status_code == 404:
        return []  # graceful fallback
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "results", "pages", "data"):
            maybe = data.get(key)
            if isinstance(maybe, list):
                return maybe
    return []


def _extract_page_id(entry: Dict[str, Any]) -> Optional[str]:
    for key in ("page_id", "pageId", "id", "pageID", "slug", "code"):
        if key in entry and entry[key] is not None:
            return str(entry[key])
    return None


def fetch_page(session: requests.Session, page_id: str) -> Dict[str, Any]:
    resp = session.get(f"{BASE_URL}/tutorial-pages/{page_id}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def dump_pages(session: requests.Session, tutorials: List[Dict[str, Any]], out_dir: str = "tutorial_dump") -> None:
    os.makedirs(out_dir, exist_ok=True)

    # Save raw tutorials list for inspection
    with open(os.path.join(out_dir, "tutorials_raw.json"), "w", encoding="utf-8") as f:
        json.dump(tutorials, f, ensure_ascii=False, indent=2)

    def _iter_page_candidates(item: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        # If the tutorial entry already has pages array, yield them
        if isinstance(item.get("pages"), list):
            for p in item["pages"]:
                yield p
        # Else, try fetching pages via tutorial id/slug
        tutorial_id = _extract_page_id(item)
        if tutorial_id:
            pages = fetch_tutorial_pages(session, tutorial_id)
            for p in pages:
                yield p
        # Lastly, treat the tutorial itself as a single page if it has an id/slug
        if tutorial_id:
            yield {"id": tutorial_id, "title": item.get("title")}

    seen = 0
    for idx, item in enumerate(tutorials, start=1):
        for page_entry in _iter_page_candidates(item):
            page_id = _extract_page_id(page_entry)
            if not page_id:
                print(f"[{idx:03d}] skipped page (no id): {page_entry}")
                continue
            try:
                page = fetch_page(session, page_id)
            except requests.HTTPError as e:
                print(f"[{idx:03d}] page {page_id}  -> HTTP {e.response.status_code} ({page_entry})")
                continue
            seen += 1
            title = page.get("title") or page_entry.get("title") or item.get("title") or f"page_{page_id}"
            out_path = os.path.join(out_dir, f"{idx:03d}_{seen:02d}_{page_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(page, f, ensure_ascii=False, indent=2)
            snippet = page.get("code") or page.get("content") or str(page)[:120]
            print(f"[{idx:03d}] saved {title} -> {out_path}; sample: {str(snippet)[:80]}")


def main() -> None:
    email = input("BRAIN email: ").strip()
    password = getpass.getpass("BRAIN password: ")
    session = authenticate(email, password)
    tutorials = fetch_tutorials(session)
    print(f"Fetched {len(tutorials)} tutorials")
    dump_pages(session, tutorials)


if __name__ == "__main__":
    main()
