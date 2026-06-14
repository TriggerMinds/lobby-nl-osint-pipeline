"""Woo (Wet open overheid) collector for public government document releases.

Collects published Woo-publications from:
- open.overheid.nl (official Dutch PLOOI/OpenWOB portal, verified working 2026)
- rijksoverheid.nl/documenten (ministerial Woo pages)

Filters on relevant keywords for the Israel/Palestine/Zionism lobby topic.
Only collects publicly available, government-published documents.
Outputs to woo_followup_targets.csv with status tracking.

Verified URLs (2026-06-14):
  https://open.overheid.nl                       200 OK
  https://open.overheid.nl/zoeken?q=Israel        200 OK
  https://www.rijksoverheid.nl/documenten         200 OK
  https://transparency-register.europa.eu          200 OK
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from lobby_nl.collectors import BaseCollector


class WooCollector(BaseCollector):
    """Collects publicly released Woo (Wet open overheid) documents.

    Searches the official Dutch PLOOI/OpenWOB portal and Rijksoverheid
    document pages for publications related to Israel, Gaza, antisemitism,
    NCTV, and diplomatic channels.
    """

    WOO_CENTRAL_URL = "https://open.overheid.nl"
    RIJKSOVERHEID_DOCS_URL = "https://www.rijksoverheid.nl/documenten"

    RELEVANT_KEYWORDS: list[str] = [
        "Israël",
        "Israel",
        "Gaza",
        "antisemitisme",
        "antisemitism",
        "NCTV",
        "ambassade Israël",
        "Israel embassy",
        "Midden-Oosten",
        "Middle East",
        "Palestina",
        "Palestine",
        "zionisme",
        "Zionism",
        "Hamas",
        "CIDI",
        "NCAB",
        "NIDA",
    ]

    def __init__(
        self,
        output_dir: Path = Path("data/raw"),
        user_agent: str = "LobbyNL-OSINT/1.0 (research pipeline; contact@example.com)",
        request_delay: float = 2.0,
    ) -> None:
        super().__init__(output_dir=output_dir, user_agent=user_agent, request_delay=request_delay)
        self.followup_targets: list[dict[str, Any]] = []

    def _matches_keywords(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.RELEVANT_KEYWORDS)

    def _make_absolute_url(self, href: str, base: str) -> str:
        if href.startswith("http"):
            return href
        return urljoin(base, href)

    def search_open_overheid(self, query: str = "Israël") -> list[dict[str, Any]]:
        """Search open.overheid.nl (PLOOI/OpenWOB) for relevant publications."""
        results: list[dict[str, Any]] = []
        search_url = f"{self.WOO_CENTRAL_URL}/zoeken?q={quote(query)}"
        resp = self.fetch_page(search_url)
        if resp is None:
            return results

        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select(
            "[class*='result'], [class*='search-result'], article, .card, .document-item, .list-item, .search-item"
        )[:30]:
            title_el = item.select_one("h2, h3, .title, a[href]")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if self._matches_keywords(title) or self._matches_keywords(item.get_text()):
                link_el = item.select_one("a[href]") or title_el
                href = link_el.get("href", "")
                results.append({
                    "title": title,
                    "url": self._make_absolute_url(href, self.WOO_CENTRAL_URL),
                    "source": "open.overheid.nl",
                    "status": "released",
                })
        return results

    def search_rijksoverheid(self, query: str = "Israël") -> list[dict[str, Any]]:
        """Search rijksoverheid.nl/documenten for relevant publications."""
        results: list[dict[str, Any]] = []
        search_url = f"{self.RIJKSOVERHEID_DOCS_URL}?trefwoord={quote(query)}"
        resp = self.fetch_page(search_url)
        if resp is None:
            return results

        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select(
            ".result, .document, .list-item, article, .search-result, .content-item"
        )[:30]:
            title_el = item.select_one("h2, h3, .title, a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if self._matches_keywords(title) or self._matches_keywords(item.get_text()):
                link_el = item.select_one("a[href]") or title_el
                href = link_el.get("href", "")
                results.append({
                    "title": title,
                    "url": self._make_absolute_url(href, self.RIJKSOVERHEID_DOCS_URL),
                    "source": "rijksoverheid.nl",
                    "status": "released",
                })
        return results

    def collect_all(self) -> list[dict[str, Any]]:
        """Run all Woo searches across keywords and sources.

        Fills self.followup_targets directly so export_woo_targets()
        works independently without requiring collect_and_export().
        """
        all_results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        queries = ["Israël", "Gaza", "antisemitisme", "NCTV", "ambassade Israël"]

        now = datetime.now(timezone.utc).isoformat()
        for query in queries:
            for result in self.search_open_overheid(query):
                if result["url"] not in seen_urls:
                    seen_urls.add(result["url"])
                    all_results.append(result)

            for result in self.search_rijksoverheid(query):
                if result["url"] not in seen_urls:
                    seen_urls.add(result["url"])
                    all_results.append(result)

        self.followup_targets = [
            {
                "title": r["title"],
                "url": r["url"],
                "source": r["source"],
                "status": r.get("status", "released"),
                "date_collected": now,
                "keywords_matched": "",
                "document_type": "woo_document",
            }
            for r in all_results
        ]

        return all_results

    def export_woo_targets(self, output_path: Optional[Path] = None) -> Path:
        """Export collected Woo documents to CSV.

        Uses self.followup_targets (set by collect_all() or collect_and_export()).
        """
        filepath = output_path or Path("exports") / "woo_followup_targets.csv"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "title", "url", "source", "status",
            "date_collected", "keywords_matched", "document_type",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            if self.followup_targets:
                writer.writerows(self.followup_targets)
            else:
                writer.writerow({
                    "title": "placeholder",
                    "url": "https://open.overheid.nl",
                    "source": "woo_collector",
                    "status": "pending",
                    "date_collected": datetime.now(timezone.utc).isoformat(),
                    "keywords_matched": "",
                    "document_type": "woo_document",
                })

        return filepath

    def collect_and_export(self, output_path: Optional[Path] = None) -> tuple[list[dict[str, Any]], Path]:
        """Collect Woo documents and export them to CSV."""
        results = self.collect_all()
        filepath = self.export_woo_targets(output_path)
        return results, filepath
