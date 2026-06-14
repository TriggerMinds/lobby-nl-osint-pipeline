"""Media framing analysis module.

Tracks repeated framing patterns, recurring guesting, recurring amplification,
repeated op-ed alignment, repeated source quotation, and topic clustering.

Does not classify media framing as coordination unless source-backed.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from lobby_nl.models import (
    Actor,
    EvidenceStrength,
    Source,
)


class FramingPattern:
    """A detected framing pattern across media sources."""

    def __init__(
        self,
        pattern_id: str = "",
        pattern_type: str = "",
        description: str = "",
        source_ids: list[str] | None = None,
        actor_ids: list[str] | None = None,
        frequency: int = 0,
        evidence_strength: EvidenceStrength = EvidenceStrength.light,
        alternative_explanation: str = "",
    ) -> None:
        self.pattern_id = pattern_id
        self.pattern_type = pattern_type
        self.description = description
        self.source_ids = source_ids or []
        self.actor_ids = actor_ids or []
        self.frequency = frequency
        self.evidence_strength = evidence_strength
        self.alternative_explanation = alternative_explanation


class MediaFramingAnalyzer:
    """Analyzes media sources for framing patterns."""

    FRAMING_KEYWORDS = {
        "conflict_frame": [
            "conflict", "oorlog", "strijd", "aanval", "gevecht",
            "escalatie", "geweld", "bombardement", "raket",
        ],
        "victim_frame": [
            "slachtoffer", "onschuldig", "burgerdoden", "humanitair",
            "lijden", "getroffen", "vluchteling",
        ],
        "security_frame": [
            "veiligheid", "dreiging", "terrorisme", "extremisme",
            "radicalisering", "veiligheidsdienst",
        ],
        "legitimacy_frame": [
            "recht op bestaan", "legitiem", "soevereiniteit",
            "erkennen", "tweestatenoplossing",
        ],
        "antisemitism_frame": [
            "antisemitisme", "jodenhaat", "antisemitisch",
            "jodenster", "holocaust",
        ],
        "apartheid_frame": [
            "apartheid", "bezetting", "kolonisatie", "nederzettingen",
            "bezette gebieden", "mensenrechten",
        ],
        "lobby_frame": [
            "lobby", "beïnvloeding", "invloed", "belangenbehartiging",
            "pressiegroep", "sponsoring",
        ],
    }

    def __init__(self, output_dir: Path = Path("exports")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.patterns: list[FramingPattern] = []

    def analyze_source(
        self, source: Source, actor_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        results = []
        if not source.content_text:
            return results
        text_lower = source.content_text.lower()
        for frame_name, keywords in self.FRAMING_KEYWORDS.items():
            matches = [kw for kw in keywords if kw in text_lower]
            if len(matches) >= 2:
                results.append({
                    "source_url": source.url,
                    "frame_type": frame_name,
                    "matched_keywords": matches,
                    "match_count": len(matches),
                    "actor_ids": actor_ids or [],
                })
        return results

    def analyze_sources(
        self, sources: list[Source], actors: list[Actor]
    ) -> list[FramingPattern]:
        actor_lookup = {a.name.lower(): a.actor_id for a in actors}
        all_results: list[dict[str, Any]] = []
        for src in sources:
            found_actor_ids = [
                actor_lookup[name]
                for name in actor_lookup
                if src.content_text and name in src.content_text.lower()
            ]
            results = self.analyze_source(src, found_actor_ids)
            all_results.extend(results)

        df = pd.DataFrame(all_results) if all_results else pd.DataFrame()
        if df.empty:
            return self.patterns

        grouped = df.groupby(["frame_type"]).agg(
            frequency=("source_url", "count"),
            unique_sources=("source_url", "nunique"),
            avg_matches=("match_count", "mean"),
            total_matches=("match_count", "sum"),
        ).reset_index()

        for _, row in grouped.iterrows():
            pattern = FramingPattern(
                pattern_id=f"fp_{row['frame_type']}",
                pattern_type=row["frame_type"],
                description=f"Frame '{row['frame_type']}' found in {row['frequency']} instances "
                f"across {row['unique_sources']} unique sources "
                f"(avg keywords per instance: {row['avg_matches']:.1f})",
                frequency=int(row["frequency"]),
                evidence_strength=(
                    EvidenceStrength.medium if row["frequency"] > 5 else EvidenceStrength.light
                ),
                alternative_explanation="May reflect general news framing rather than coordinated messaging",
            )
            self.patterns.append(pattern)

        return self.patterns

    def export_framing_log(self) -> Path:
        filepath = self.output_dir / "media_framing_log.csv"
        rows = [
            {
                "pattern_id": p.pattern_id,
                "pattern_type": p.pattern_type,
                "description": p.description,
                "frequency": p.frequency,
                "evidence_strength": p.evidence_strength.value,
                "alternative_explanation": p.alternative_explanation,
            }
            for p in self.patterns
        ]
        pd.DataFrame(rows).to_csv(filepath, index=False)
        return filepath

    def detect_recurring_guesting(
        self, sources: list[Source], actors: list[Actor]
    ) -> list[dict[str, Any]]:
        """Detect recurring guest appearances across talk shows and programs."""
        actor_name_counts: Counter[str] = Counter()
        actor_source_map: dict[str, list[str]] = {}
        for src in sources:
            if not src.content_text:
                continue
            text_lower = src.content_text.lower()
            for actor in actors:
                if actor.name.lower() in text_lower:
                    actor_name_counts[actor.actor_id] += 1
                    actor_source_map.setdefault(actor.actor_id, []).append(src.url)
        results = []
        for actor_id, count in actor_name_counts.most_common():
            if count >= 2:
                actor = next((a for a in actors if a.actor_id == actor_id), None)
                results.append({
                    "actor_id": actor_id,
                    "actor_name": actor.name if actor else "unknown",
                    "appearance_count": count,
                    "sources": actor_source_map.get(actor_id, []),
                    "flag": "recurring_guest" if count > 5 else "frequent_mention",
                })
        return results


class ArchiveDiffAnalyzer:
    """Compares current and archived page versions, logs changes."""

    def __init__(self, output_dir: Path = Path("exports")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.diffs: list[dict[str, Any]] = []
        self.disappearances: list[dict[str, Any]] = []

    def log_diff(
        self, url: str, current_hash: str, archived_hash: str, diff_lines: list[str], changed: bool
    ) -> None:
        self.diffs.append({
            "url": url,
            "changed": changed,
            "current_hash": current_hash,
            "archived_hash": archived_hash,
            "diff_line_count": len(diff_lines),
            "diff_preview": "\n".join(diff_lines[:50]),
            "date_detected": datetime.now(timezone.utc).isoformat(),
        })

    def log_disappearance(self, url: str, reason: str) -> None:
        self.disappearances.append({
            "url": url,
            "reason": reason,
            "date_detected": datetime.now(timezone.utc).isoformat(),
        })

    def export_diffs(self) -> Path:
        filepath = self.output_dir / "archived_source_diffs.csv"
        pd.DataFrame(self.diffs).to_csv(filepath, index=False)
        return filepath

    def export_disappearances(self) -> Path:
        filepath = self.output_dir / "source_disappearance_log.csv"
        pd.DataFrame(self.disappearances).to_csv(filepath, index=False)
        return filepath
