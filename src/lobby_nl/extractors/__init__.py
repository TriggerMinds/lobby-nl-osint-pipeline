"""Entity extractors for parsing collected source content into structured data."""

from __future__ import annotations

import re
from typing import Any

from lobby_nl.models import (
    Actor,
    ActorCategory,
    EvidenceStrength,
    EvidenceType,
    RelationshipType,
    Source,
)


class ActorExtractor:
    """Extracts actors from source content using keywords, patterns, and context."""

    KEYWORD_CATEGORY_MAP: dict[str, ActorCategory] = {
        "christelijke zionist": ActorCategory.christian_zionist_org,
        "christian zionist": ActorCategory.christian_zionist_org,
        "christenen voor israël": ActorCategory.christian_zionist_org,
        "christians for israel": ActorCategory.christian_zionist_org,
        "cijo": ActorCategory.jewish_civic_org,
        "centraal joods overleg": ActorCategory.jewish_civic_org,
        "joods maatschappelijk": ActorCategory.jewish_civic_org,
        "joodse gemeente": ActorCategory.jewish_civic_org,
        "ambassade van israël": ActorCategory.israeli_diplomatic_channel,
        "israeli embassy": ActorCategory.israeli_diplomatic_channel,
        "israëlische ambassade": ActorCategory.israeli_diplomatic_channel,
        "nida": ActorCategory.antisemitism_policy_infrastructure,
        "nationaal coördinator antisemitisme": ActorCategory.antisemitism_policy_infrastructure,
        "antisemitisme coördinator": ActorCategory.antisemitism_policy_infrastructure,
        "cid": ActorCategory.campaign_actor,
        "tweede kamer": ActorCategory.house_actor,
        "eerste kamer": ActorCategory.senate_actor,
        "ministerie van": ActorCategory.ministry_actor,
        "minister van": ActorCategory.ministry_actor,
        "palestina": ActorCategory.palestine_rights_counter_lobby,
        "palestijn": ActorCategory.palestine_rights_counter_lobby,
        "palestine": ActorCategory.palestine_rights_counter_lobby,
        "bds": ActorCategory.palestine_rights_counter_lobby,
        "nos": ActorCategory.public_broadcaster_actor,
        "npo": ActorCategory.public_broadcaster_actor,
        "volkskrant": ActorCategory.media_actor,
        "nrc": ActorCategory.media_actor,
        "telegraaf": ActorCategory.media_actor,
        "trouw": ActorCategory.media_actor,
        "ad": ActorCategory.media_actor,
        "parool": ActorCategory.media_actor,
        "nederlands dagblad": ActorCategory.media_actor,
        "reformatorisch dagblad": ActorCategory.media_actor,
        "elsevier": ActorCategory.media_actor,
        "ew": ActorCategory.media_actor,
        "hp/de tijd": ActorCategory.media_actor,
        "vrij nederland": ActorCategory.media_actor,
        "groene amsterdammer": ActorCategory.media_actor,
        "joop": ActorCategory.alternative_media_actor,
        "de correspondent": ActorCategory.alternative_media_actor,
        "follow the money": ActorCategory.alternative_media_actor,
        "ftm": ActorCategory.alternative_media_actor,
        "geenstijl": ActorCategory.alternative_media_actor,
        "opiniez": ActorCategory.alternative_media_actor,
        "cidc": ActorCategory.think_tank_actor,
        "clingendael": ActorCategory.think_tank_actor,
        "hcss": ActorCategory.think_tank_actor,
        "the hague centre": ActorCategory.think_tank_actor,
        "universiteit": ActorCategory.academic_actor,
        "universiteit van": ActorCategory.academic_actor,
        "vrije universiteit": ActorCategory.academic_actor,
        "vu": ActorCategory.academic_actor,
        "uva": ActorCategory.academic_actor,
        "universiteit leiden": ActorCategory.academic_actor,
        "erasmus universiteit": ActorCategory.academic_actor,
        "universiteit utrecht": ActorCategory.academic_actor,
        "radboud": ActorCategory.academic_actor,
        "stichting": ActorCategory.funding_actor,
        "fonds": ActorCategory.funding_actor,
        "foundation": ActorCategory.funding_actor,
        "advocaten": ActorCategory.law_firm_actor,
        "lawyers": ActorCategory.law_firm_actor,
        "lobby": ActorCategory.pr_or_consultancy_actor,
        "public affairs": ActorCategory.pr_or_consultancy_actor,
        "communicatie": ActorCategory.pr_or_consultancy_actor,
        "politie": ActorCategory.police_actor,
        "aivd": ActorCategory.security_actor,
        "nctv": ActorCategory.security_actor,
        "nctb": ActorCategory.security_actor,
        "openbaar ministerie": ActorCategory.security_actor,
        "burgemeester": ActorCategory.mayor_actor,
        "gemeente": ActorCategory.municipal_actor,
        "wethouder": ActorCategory.municipal_actor,
    }

    def extract_actors_from_source(
        self, source: Source
    ) -> list[tuple[str, ActorCategory]]:
        """Extract potential actor names and categories from source content."""
        found: list[tuple[str, ActorCategory]] = []
        text_lower = source.content_text.lower() if source.content_text else ""
        for keyword, category in self.KEYWORD_CATEGORY_MAP.items():
            if keyword in text_lower:
                found.append((keyword.title() if len(keyword) > 3 else keyword.upper(), category))
        return found

    def extract_organization_names(self, text: str) -> list[str]:
        """Extract potential organization names using capitalization patterns."""
        pattern = r"\b([A-Z][a-zÀ-ÿ]+(?:\s+(?:[A-Z][a-zÀ-ÿ]+|van|de|der|den|het|en|&|voor|te|ter|tot|uit|over|onder|bij|op|in|aan|met|naar|door|om|tussen|vanuit|vanwege|gedurende|binnen|buiten|zonder|tegen)){1,6})\b"
        matches = re.findall(pattern, text)
        return list(set(m for m in matches if len(m) > 5))

    def extract_person_names(self, text: str) -> list[str]:
        """Extract potential person names (Dutch patterns)."""
        pattern = r"\b([A-Z][a-zÀ-ÿ]+(?:\s+[A-Z][a-zÀ-ÿ]+){1,3})\b"
        matches = re.findall(pattern, text)
        filtered = []
        for m in matches:
            parts = m.split()
            if len(parts) >= 2:
                filtered.append(m)
        return list(set(filtered))


class RelationshipExtractor:
    """Extracts relationships between actors from source content."""

    RELATIONSHIP_PATTERNS: list[tuple[str, RelationshipType]] = [
        (r"werkt samen met", RelationshipType.collaborates),
        (r"samen(?:ge)?werkt", RelationshipType.collaborates),
        (r"partnerschap", RelationshipType.collaborates),
        (r"partners", RelationshipType.collaborates),
        (r"gefinancierd door", RelationshipType.funded_by),
        (r"financieel gesteund door", RelationshipType.funded_by),
        (r"sponsor", RelationshipType.funds),
        (r"donatie", RelationshipType.funding_relation),
        (r"gesubsidieerd door", RelationshipType.funded_by),
        (r"lid van", RelationshipType.member_of),
        (r"aangesloten bij", RelationshipType.member_of),
        (r"bestuurslid", RelationshipType.member_of),
        (r"voorzitter van", RelationshipType.member_of),
        (r"directeur van", RelationshipType.employed_by),
        (r"werknemer bij", RelationshipType.employed_by),
        (r"adviseur", RelationshipType.advises),
        (r"advies", RelationshipType.advises),
        (r"spreekt op", RelationshipType.speaks_at),
        (r"spreker", RelationshipType.speaks_at),
        (r"bijeenkomst", RelationshipType.event_relation),
        (r"conferentie", RelationshipType.event_relation),
        (r"vertegenwoordigt", RelationshipType.represents),
        (r"vertegenwoordiger", RelationshipType.represents),
        (r"ambassadeur", RelationshipType.diplomatic_relation),
        (r"gezant", RelationshipType.diplomatic_relation),
        (r"lobby", RelationshipType.lobbies),
        (r"beïnvloed", RelationshipType.lobbies),
    ]

    def extract_relationships(
        self, text: str, actors: list[Actor]
    ) -> list[dict[str, Any]]:
        """Extract potential relationships from text given known actors."""
        relationships: list[dict[str, Any]] = []
        text_lower = text.lower()
        actor_names = {a.name.lower(): a.actor_id for a in actors}
        for pattern, rel_type in self.RELATIONSHIP_PATTERNS:
            for match in re.finditer(pattern, text_lower):
                context_start = max(0, match.start() - 200)
                context_end = min(len(text_lower), match.end() + 200)
                context = text_lower[context_start:context_end]
                found_actors = [
                    actor_names[name]
                    for name in actor_names
                    if name in context
                ]
                if len(found_actors) >= 2:
                    relationships.append(
                        {
                            "actor_a_id": found_actors[0],
                            "actor_b_id": found_actors[1],
                            "relationship_type": rel_type,
                            "evidence_strength": EvidenceStrength.light,
                            "context_excerpt": context[:300],
                        }
                    )
        return relationships


class ClaimExtractor:
    """Extracts claims from source content."""

    CLAIM_INDICATORS = [
        r"stelt dat",
        r"beweert dat",
        r"volgens",
        r"verklaart",
        r"aldus",
        r"zegt dat",
        r"betoogt",
        r"concludeert",
        r"oordeelt",
        r"vindt dat",
        r"is van mening",
    ]

    def extract_claims(self, source: Source, actor_ids: list[str]) -> list[dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        if not source.content_text:
            return claims
        text = source.content_text.lower()
        for indicator in self.CLAIM_INDICATORS:
            for match in re.finditer(indicator, text):
                start = match.start()
                end = min(len(text), start + 500)
                claim_text = source.content_text[start:end]
                claims.append(
                    {
                        "claim_text": claim_text.strip()[:300],
                        "source_id": source.source_id,
                        "evidence_type": EvidenceType.osint_evidence,
                        "evidence_strength": EvidenceStrength.medium,
                    }
                )
        return claims


class MediaFramingExtractor:
    """Detects repeated framing patterns and actor-keyword co-occurrence in sources.

    Populates the media_framing_log.csv with concrete detections.
    """

    FRAMING_KEYWORDS: dict[str, list[str]] = {
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

    def extract_framing(
        self, source: Source, actor_ids: list[str], actor_names: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Detect framing patterns and actor-keyword co-occurrences in a source."""
        results: list[dict[str, Any]] = []
        if not source.content_text:
            return results
        text_lower = source.content_text.lower()
        for frame_name, keywords in self.FRAMING_KEYWORDS.items():
            matched = [kw for kw in keywords if kw in text_lower]
            if len(matched) >= 2:
                found_actors = [
                    actor_names.get(aid, "")
                    for aid in actor_ids
                    if actor_names.get(aid, "").lower() in text_lower
                ]
                results.append({
                    "source_url": source.url,
                    "frame_type": frame_name,
                    "matched_keywords": "|".join(matched),
                    "match_count": len(matched),
                    "actor_names": "|".join(found_actors) if found_actors else "",
                    "actor_ids": "|".join(actor_ids) if actor_ids else "",
                })
        return results

    def extract_batch(
        self,
        sources: list[Source],
        actors: list[Actor],
    ) -> list[dict[str, Any]]:
        """Extract framing patterns across all sources."""
        actor_name_lookup = {a.actor_id: a.name for a in actors}
        all_framing: list[dict[str, Any]] = []
        for src in sources:
            found_actor_ids = [
                actor_name_lookup[name]
                for name in actor_name_lookup
                if src.content_text and name in src.content_text.lower()
            ]
            framing = self.extract_framing(src, found_actor_ids, actor_name_lookup)
            all_framing.extend(framing)
        return all_framing
