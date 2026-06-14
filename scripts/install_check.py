"""Verify that all dependencies from requirements.txt are installed correctly.

Handles Windows-specific issues:
- playwright: check browser binary installed
- spacy: check nl_core_news_sm model downloaded
- crawl4ai: check post-install setup
- lxml: detect missing Visual C++ runtime
- pymupdf: import as fitz, not pymupdf
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

# NOTE: This dict must stay in sync with requirements.txt.
# When adding/removing a package in requirements.txt, update this dict too.
# Import names differ from pip names for: bs4/beautifulsoup4, fitz/pymupdf,
# yaml/pyyaml, dotenv/python-dotenv, readability_lxml/readability-lxml.
PACKAGES = {
    "pandas": "pandas",
    "duckdb": "duckdb",
    "pydantic": "pydantic",
    "typer": "typer",
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "playwright": "playwright",
    "readability": "readability-lxml",
    "waybackpy": "waybackpy",
    "yaml": "pyyaml",
    "networkx": "networkx",
    "rapidfuzz": "rapidfuzz",
    "pdfplumber": "pdfplumber",
    "fitz": "pymupdf",
    "dotenv": "python-dotenv",
    "rich": "rich",
    "lxml": "lxml",
    "spacy": "spacy",
    "crawl4ai": "crawl4ai",
    "httpx": "httpx",
    "charset_normalizer": "charset-normalizer",
    "certifi": "certifi",
    "urllib3": "urllib3",
    "tqdm": "tqdm",
    "colorama": "colorama",
}


def check_imports() -> dict[str, bool]:
    results: dict[str, bool] = {}
    for import_name, pip_name in PACKAGES.items():
        try:
            importlib.import_module(import_name)
            results[pip_name] = True
        except ImportError:
            results[pip_name] = False
    return results


def check_playwright_chromium() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "from playwright.sync_api import sync_playwright; "
             "p = sync_playwright().start(); "
             "b = p.chromium.launch(headless=True); "
             "b.close(); p.stop(); print('OK')"],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0 and "OK" in result.stdout
    except Exception:
        return False


def check_spacy_model() -> bool:
    try:
        import spacy
        spacy.load("nl_core_news_sm")
        return True
    except Exception:
        return False


def check_lxml() -> tuple[bool, str | None]:
    try:
        import lxml
        return True, None
    except ImportError as e:
        msg = str(e)
        if "DLL" in msg or "dll" in msg or "WinError" in msg:
            return False, "Visual C++ runtime missing. Install from https://lxml.de/installation.html"
        return False, None


def check_crawl4ai_setup() -> bool:
    db_path = Path.home() / ".crawl4ai" / "crawl4ai.db"
    return db_path.exists()


def main() -> int:
    print("=== Lobby NL OSINT Pipeline - Dependency Check ===\n")

    results = check_imports()
    all_ok = True

    for pip_name, ok in results.items():
        status = "OK" if ok else "MISSING"
        print(f"  [{status:>7}] {pip_name}")
        if not ok:
            all_ok = False

    print()

    if results["playwright"]:
        if check_playwright_chromium():
            print("  [     OK] playwright chromium browser")
        else:
            print("  [MISSING] playwright chromium browser")
            print("    Fix: playwright install chromium")
            all_ok = False
    else:
        print("  [   SKIP] playwright (package missing)")

    if results["spacy"]:
        if check_spacy_model():
            print("  [     OK] spacy nl_core_news_sm model")
        else:
            print("  [MISSING] spacy nl_core_news_sm model")
            print("    Fix: python -m spacy download nl_core_news_sm")
            all_ok = False
    else:
        print("  [   SKIP] spacy (package missing)")

    if results["crawl4ai"]:
        if check_crawl4ai_setup():
            print("  [     OK] crawl4ai setup")
        else:
            print("  [MISSING] crawl4ai post-install setup")
            print("    Fix: crawl4ai-setup")
            all_ok = False
    else:
        print("  [   SKIP] crawl4ai (package missing)")

    lxml_ok, lxml_extra = check_lxml()
    if lxml_ok:
        print("  [     OK] lxml (no DLL issues)")
    else:
        print("  [   WARN] lxml DLL issue")
        if lxml_extra:
            print(f"    Info: {lxml_extra}")
        all_ok = False

    print()
    if all_ok:
        print("All dependencies OK.")
        return 0
    else:
        print("Some dependencies are missing. See fix instructions above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
