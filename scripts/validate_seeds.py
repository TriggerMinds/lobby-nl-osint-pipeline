"""Validate manual_seeds.csv for completeness and correctness.

Checks:
- Every record has actor_id, name, category, url, notes
- Category is a valid ActorCategory value
- Notes contains "seed_only"
- actor_id is unique
- Prints summary report per category, saves to data/input/seed_validation_report.txt
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEEDS_PATH = REPO_ROOT / "data" / "input" / "manual_seeds.csv"
REPORT_PATH = REPO_ROOT / "data" / "input" / "seed_validation_report.txt"

# NOTE: This set mirrors ActorCategory enum in src/lobby_nl/models/__init__.py.
# When adding a new category to the enum, also add it here to prevent drift.
ALLOWED_CATEGORIES = {
    "pro_israel_org",
    "christian_zionist_org",
    "jewish_civic_org",
    "israeli_diplomatic_channel",
    "antisemitism_policy_infrastructure",
    "parliamentary_actor",
    "palestine_rights_counter_lobby",
    "eu_register_actor",
    "media_actor",
    "alternative_media_actor",
    "journalist_actor",
    "influencer_actor",
    "talkshow_or_program_actor",
    "podcast_actor",
    "newsletter_actor",
    "party_actor",
    "senate_actor",
    "house_actor",
    "committee_actor",
    "government_actor",
    "ministry_actor",
    "municipal_actor",
    "mayor_actor",
    "police_actor",
    "security_actor",
    "public_broadcaster_actor",
    "academic_actor",
    "think_tank_actor",
    "education_actor",
    "research_actor",
    "funding_actor",
    "donor_actor",
    "pr_or_consultancy_actor",
    "law_firm_actor",
    "event_platform_actor",
    "celebrity_actor",
    "religious_actor",
    "diaspora_actor",
    "archive_actor",
    "social_platform_actor",
    "campaign_actor",
    "presenter_actor",
    "newsletter_author_actor",
    "opining_activist_actor",
    "media_framing_actor",
    "department_actor",
    "implementation_org_actor",
    "nctv_actor",
    "semi_government_actor",
    "speaker_event_actor",
    "researcher_actor",
    "consultant_advisor_actor",
    "expert_media_guest_actor",
    "sponsor_actor",
    "grantmaker_actor",
    "foundation_actor",
    "lobbying_firm_actor",
    "pr_firm_actor",
    "event_organizer_actor",
    "venue_actor",
    "platform_actor",
    "unknown",
}

REQUIRED_FIELDS = {"actor_id", "name", "category", "url", "notes"}


def validate_seeds() -> tuple[list[str], list[str], dict[str, dict]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    category_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "missing_fields": []})

    if not SEEDS_PATH.exists():
        errors.append(f"File not found: {SEEDS_PATH}")
        return errors, warnings, dict(category_stats)

    with open(SEEDS_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        errors.append("manual_seeds.csv contains no data rows")
        return errors, warnings, dict(category_stats)

    for i, row in enumerate(rows, start=2):
        row_id = row.get("actor_id", "").strip()
        category = row.get("category", "").strip()
        notes = row.get("notes", "").strip()
        lineno = f"line {i}"

        for field in REQUIRED_FIELDS:
            if not row.get(field, "").strip():
                errors.append(f"{lineno}: missing required field '{field}'")
                category_stats[category or "UNKNOWN"]["missing_fields"].append(field)

        if row_id and row_id in seen_ids:
            errors.append(f"{lineno}: duplicate actor_id '{row_id}'")
        if row_id:
            seen_ids.add(row_id)

        if category and category not in ALLOWED_CATEGORIES:
            errors.append(f"{lineno}: invalid category '{category}'")

        if notes and "seed_only" not in notes:
            errors.append(f"{lineno}: notes missing 'seed_only' marker")

        cat = category if category else "UNKNOWN"
        category_stats[cat]["count"] += 1

    return errors, warnings, dict(category_stats)


def generate_report(errors: list[str], warnings: list[str], category_stats: dict) -> str:
    lines: list[str] = []
    total_seeds = sum(v["count"] for v in category_stats.values())

    lines.append("=" * 60)
    lines.append("Seed Validation Report — manual_seeds.csv")
    lines.append("=" * 60)
    lines.append(f"Total seeds: {total_seeds}")
    lines.append(f"Errors: {len(errors)}")
    lines.append(f"Warnings: {len(warnings)}")
    lines.append("")

    lines.append("-" * 40)
    lines.append("Per Category Summary")
    lines.append("-" * 40)
    for cat in sorted(category_stats.keys()):
        stats = category_stats[cat]
        missing = stats.get("missing_fields", [])
        flag = ""
        if missing:
            flag = f"  [MISSING: {', '.join(missing)}]"
        lines.append(f"  {cat}: {stats['count']} seeds{flag}")

    if errors:
        lines.append("")
        lines.append("-" * 40)
        lines.append("Errors")
        lines.append("-" * 40)
        for e in errors:
            lines.append(f"  ERROR: {e}")

    if warnings:
        lines.append("")
        lines.append("-" * 40)
        lines.append("Warnings")
        lines.append("-" * 40)
        for w in warnings:
            lines.append(f"  WARN: {w}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    errors, warnings, stats = validate_seeds()
    report = generate_report(errors, warnings, stats)

    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)

    if errors:
        print("\nValidation FAILED — fix the errors above.")
        return 1
    else:
        print("\nValidation PASSED.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
