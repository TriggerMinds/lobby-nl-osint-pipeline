"""Data collectors for the OSINT research pipeline.

Collectors cover:
- Web scraping (organization websites, campaign sites, event pages)
- Parliamentary records (Tweede Kamer, Eerste Kamer)
- EU Transparency Register
- Archive collection (Internet Archive, Dutch web archiving)
"""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from lobby_nl.models import Source


class BaseCollector:
    """Base collector with common HTTP and archive functionality."""

    def __init__(
        self,
        output_dir: Path = Path("exports/raw"),
        user_agent: str = "LobbyNL-OSINT/1.0 (research pipeline; contact@example.com)",
        request_delay: float = 2.0,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.request_delay = request_delay
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()

    def fetch_page(self, url: str, timeout: int = 30) -> Optional[requests.Response]:
        self._rate_limit()
        try:
            resp = self.session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            print(f"[WARN] Failed to fetch {url}: {e}")
            return None

    def extract_html_content(self, html: str, url: str) -> tuple[str, str]:
        soup = BeautifulSoup(html, "lxml")
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return title, text

    def create_source(
        self,
        url: str,
        content: str,
        title: str = "",
        source_type: str = "web",
        archive_url: Optional[str] = None,
    ) -> Source:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return Source(
            url=url,
            title=title,
            source_type=source_type,
            content_text=content,
            content_hash=content_hash,
            archive_url=archive_url,
            archive_available=archive_url is not None,
            metadata={"collector": self.__class__.__name__},
        )


class WebCollector(BaseCollector):
    """Collects data from organization websites, campaign sites, event pages, etc."""

    def collect_urls(self, urls: list[str]) -> list[Source]:
        sources: list[Source] = []
        for url in urls:
            resp = self.fetch_page(url)
            if resp is None:
                sources.append(
                    Source(
                        url=url,
                        is_dead=True,
                        notes="Failed to fetch page",
                        metadata={"collector": self.__class__.__name__},
                    )
                )
                continue
            title, text = self.extract_html_content(resp.text, url)
            src = self.create_source(url, text, title, "web")
            src.content_markdown = text
            sources.append(src)
            self._save_raw(url, resp.text)
        return sources

    def collect_linked_pages(
        self, base_url: str, max_depth: int = 1, same_domain: bool = True
    ) -> list[Source]:
        sources: list[Source] = []
        visited: set[str] = set()
        to_visit = [(base_url, 0)]
        base_domain = urlparse(base_url).netloc
        while to_visit:
            url, depth = to_visit.pop(0)
            if url in visited or depth > max_depth:
                continue
            visited.add(url)
            resp = self.fetch_page(url)
            if resp is None:
                sources.append(Source(url=url, is_dead=True))
                continue
            title, text = self.extract_html_content(resp.text, url)
            src = self.create_source(url, text, title)
            sources.append(src)
            self._save_raw(url, resp.text)
            if depth < max_depth:
                soup = BeautifulSoup(resp.text, "lxml")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    full_url = urljoin(url, href)
                    if same_domain and urlparse(full_url).netloc != base_domain:
                        continue
                    if full_url.startswith("http") and full_url not in visited:
                        to_visit.append((full_url, depth + 1))
        return sources

    def _save_raw(self, url: str, html: str) -> None:
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", url)[:100]
        raw_path = self.output_dir / f"{safe_name}.html"
        raw_path.write_text(html, encoding="utf-8")


class ParliamentaryCollector(BaseCollector):
    """Collects parliamentary records via the official Tweede Kamer Open Data API.

    Uses the OData v4 endpoint at opendata.tweedekamer.nl.
    """

    TK_ODATA_BASE = "https://opendata.tweedekamer.nl/v1"
    EK_API_BASE = "https://www.eerstekamer.nl/"

    def search_tweede_kamer(
        self, query: str, max_results: int = 50
    ) -> list[dict[str, Any]]:
        """Search Tweede Kamer records using the Open Data API OData endpoint.

        Queries the /items endpoint with $filter on title and $top for limit.
        """
        results: list[dict[str, Any]] = []
        import urllib.parse

        endpoint = f"{self.TK_ODATA_BASE}/items"
        params: dict[str, str] = {
            "$filter": f"substringof('{query}', title)",
            "$top": str(max_results),
            "$orderby": "date desc",
            "$format": "json",
        }
        resp = self.fetch_page(f"{endpoint}?{urllib.parse.urlencode(params)}")
        if resp is None:
            return results
        try:
            data = resp.json()
            items = data.get("value", [])
            for item in items:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "date": item.get("date", ""),
                    "type": item.get("type", "kamerstuk"),
                    "id": item.get("id", ""),
                    "chamber": "Tweede Kamer",
                })
        except (ValueError, KeyError) as e:
            print(f"[WARN] Failed to parse TK OData response: {e}")
        return results

    def search_eerste_kamer(
        self, query: str, max_results: int = 50
    ) -> list[dict[str, Any]]:
        """Search Eerste Kamer records via the website search."""
        results: list[dict[str, Any]] = []
        import urllib.parse
        search_url = f"{self.EK_API_BASE}zoeken?q={urllib.parse.quote(query)}"
        resp = self.fetch_page(search_url)
        if resp is None:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select(".zoekresultaten .result")[:max_results]:
            title_el = item.select_one("a")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": urljoin(self.EK_API_BASE, title_el.get("href", "")),
                    "date": "",
                    "type": "eerstekamer",
                    "chamber": "Eerste Kamer",
                })
        if not results:
            for item in soup.select("a[href*='kamerstuk']")[:max_results]:
                if query.lower() in item.get_text(strip=True).lower():
                    results.append({
                        "title": item.get_text(strip=True),
                        "url": urljoin(self.EK_API_BASE, item.get("href", "")),
                        "date": "",
                        "type": "eerstekamer",
                        "chamber": "Eerste Kamer",
                    })
        return results

    def fetch_document(self, url: str) -> Optional[str]:
        """Fetch a specific parliamentary document as text."""
        resp = self.fetch_page(url)
        if resp is None:
            return None
        _, text = self.extract_html_content(resp.text, url)
        return text


class EURegisterCollector(BaseCollector):
    """Collects data from the EU Transparency Register via lobbying.eu."""

    EU_REGISTER_URL = "https://api.lobbying.eu/v1"
    EU_FALLBACK_URL = "https://lobbying.eu"

    def search_organization(self, name: str) -> list[dict[str, Any]]:
        """Search the EU Transparency Register via the lobbying.eu search page.

        Uses the API where available, falls back to web scraping.
        """
        results: list[dict[str, Any]] = []

        import urllib.parse
        search_url = (
            f"{self.EU_FALLBACK_URL}/search?"
            f"q={urllib.parse.quote(name)}"
        )
        resp = self.fetch_page(search_url)
        if resp is None:
            return results

        soup = BeautifulSoup(resp.text, "lxml")
        for card in soup.select("[class*='card'], [class*='result'], [class*='organization']"):
            name_el = card.select_one("h2, h3, .name, .title")
            if name_el:
                name_text = name_el.get_text(strip=True)
                reg_number = ""
                reg_el = card.select_one("[class*='reg'], [class*='id'], .registration")
                if reg_el:
                    reg_number = reg_el.get_text(strip=True)
                country = ""
                country_el = card.select_one("[class*='country'], [class*='location']")
                if country_el:
                    country = country_el.get_text(strip=True)
                results.append({
                    "name": name_text,
                    "reg_number": reg_number,
                    "country": country,
                })

        if not results:
            for row in soup.select("table tr")[1:10]:
                cells = row.select("td")
                if len(cells) >= 2:
                    results.append({
                        "name": cells[0].get_text(strip=True),
                        "reg_number": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                        "country": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                    })

        return results


class ArchiveCollector(BaseCollector):
    """Collects archival snapshots via Internet Archive and other sources."""

    WAYBACK_AVAILABLE_URL = "https://archive.org/wayback/available"

    def check_archive(self, url: str) -> Optional[str]:
        resp = self.fetch_page(
            f"{self.WAYBACK_AVAILABLE_URL}?url={url}"
        )
        if resp is None:
            return None
        try:
            data = resp.json()
            if data.get("archived_snapshots"):
                return data["archived_snapshots"].get("closest", {}).get("url")
        except (ValueError, KeyError):
            pass
        return None

    def fetch_archived_page(self, archive_url: str) -> Optional[str]:
        resp = self.fetch_page(archive_url)
        if resp is None:
            return None
        _, text = self.extract_html_content(resp.text, archive_url)
        return text

    def compare_versions(
        self, current_text: str, archived_text: str, url: str
    ) -> dict[str, Any]:
        current_hash = hashlib.sha256(current_text.encode()).hexdigest()
        archived_hash = hashlib.sha256(archived_text.encode()).hexdigest()
        changed = current_hash != archived_hash
        import difflib

        diff = list(
            difflib.unified_diff(
                archived_text.splitlines(),
                current_text.splitlines(),
                lineterm="",
                fromfile="archive",
                tofile="current",
            )
        )
        return {
            "url": url,
            "changed": changed,
            "current_hash": current_hash,
            "archived_hash": archived_hash,
            "diff_lines": diff[:500],
        }
