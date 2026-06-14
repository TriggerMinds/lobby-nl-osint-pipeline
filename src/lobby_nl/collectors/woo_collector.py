"""Woo (Wet open overheid) collector for public government document releases.

Collects published Woo-publications from:
- woo.nl (central Woo portal)
- rijksoverheid.nl/documenten/woo-verzoeken (ministerial Woo pages)

Filters on relevant keywords for the Israel/Palestine/Zionism lobby topic.
Only collects publicly available, government-published documents.
Outputs to woo_followup_targets.csv with status tracking.
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

    Searches the Dutch government's Woo publication portals for documents
    related to Israel, Gaza, antisemitism, NCTV, and diplomatic channels.
    Only collects publicly available documents - no private or pending requests.
    """

    WOO_CENTRAL_URL = "https://www.woo.nl"
    RIJKSOVERHEID_WOO_URL = "https://www.rijksoverheid.nl/documenten/woo-verzoeken"

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

    def search_woo_nl(self, query: str = "Israël") -> list[dict[str, Any]]:
        """Search woo.nl for relevant publications."""
        results: list[dict[str, Any]] = []
        search_url = f"{self.WOO_CENTRAL_URL}/zoeken?q={quote(query)}"
        resp = self.fetch_page(search_url)
        if resp is None:
            return results

        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select(".zoekresultaat, .result-item, article, .card")[:30]:
            title_el = item.select_one("h2, h3, .title, a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if self._matches_keywords(title):
                link_el = item.select_one("a[href]") or title_el
                href = link_el.get("href", "")
                if href.startswith("/"):
                    href = urljoin(self.WOO_CENTRAL_URL, href)
                results.append({
                    "title": title,
                    "url": href,
                    "source": "woo.nl",
                    "status": "released",
                })
        return results

    def search_rijksoverheid_woo(self, query: str = "Israël") -> list[dict[str, Any]]:
        """Search rijksoverheid.nl/woo-verzoeken for relevant publications."""
        results: list[dict[str, Any]] = []
        search_url = (
            f"{self.RIJKSOVERHEID_WOO_URL}?"
            f"trefwoord={quote(query)}"
        )
        resp = self.fetch_page(search_url)
        if resp is None:
            return results

        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select(".result, .document, .woo-item, article, .list-item")[:30]:
            title_el = item.select_one("h2, h3, .title, a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if self._matches_keywords(title):
                link_el = item.select_one("a[href]") or title_el
                href = link_el.get("href", "")
                if href.startswith("/"):
                    href = urljoin(self.RIJKSOVERHEID_WOO_URL, href)
                results.append({
                    "title": title,
                    "url": href,
                    "source": "rijksoverheid.nl",
                    "status": "released",
                })
        return results

    def collect_all(self) -> list[dict[str, Any]]:
        """Run all Woo searches across keywords and sources."""
        all_results: list[dict[str, Any]] = []
        queries = ["Israël", "Gaza", "antisemitisme", "NCTV", "ambassade Israël"]

        for query in queries:
            woo_results = self.search_woo_nl(query)
            for r in woo_results:
                if r not in all_results:
                    all_results.append(r)

            rv_results = self.search_rijksoverheid_woo(query)
            for r in rv_results:
                if r not in all_results:
                    all_results.append(r)

        return all_results

    def export_woo_targets(self, output_path: Optional[Path] = None) -> Path:
        """Export collected Woo documents to CSV.

        Columns: title, url, source, status, keywords_matched, date_collected
        """
        filepath = output_path or self.output_dir.parent / "exports" / "woo_followup_targets.csv"
        if not filepath.parent.exists():
            filepath.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "title", "url", "source", "status",
            "date_collected", "keywords_matched",
            "document_type",
        ]

        now = datetime.now(timezone.utc).isoformat()
        for target in self.followup_targets:
            target.setdefault("date_collected", now)
            target.setdefault("document_type", "woo_document")

        # Also include collected results as followup targets
        if not self.followup_targets:
            pass  # targets collected by collect_all()

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            if self.followup_targets:
                writer.writerows(self.followup_targets)
            else:
                writer.writerow({
                    "title": "placeholder",
                    "url": "",
                    "source": "woo_collector",
                    "status": "pending",
                    "date_collected": now,
                    "keywords_matched": "",
                    "document_type": "woo_document",
                })

        return filepath

    def collect_and_export(self, output_path: Optional[Path] = None) -> tuple[list[dict[str, Any]], Path]:
        """Collect Woo documents and export them to CSV."""
        results = self.collect_all()
        self.followup_targets = [
            {
                "title": r["title"],
                "url": r["url"],
                "source": r["source"],
                "status": r.get("status", "released"),
                "date_collected": datetime.now(timezone.utc).isoformat(),
                "keywords_matched": "",
                "document_type": "woo_document",
            }
            for r in results
        ]
        filepath = self.export_woo_targets(output_path)
        return results, filepath
