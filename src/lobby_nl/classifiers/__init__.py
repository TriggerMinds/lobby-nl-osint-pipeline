"""Actor classifier for categorizing extracted actors.

Separates:
- Jewish civic organizations from pro-Israel lobby organizations
- Antisemitism policy infrastructure from Zionist organizations
- Christian Zionist organizations as separate
- Israeli diplomatic channels as separate state/diplomatic
- Counter-lobby / Palestine-rights actors
- Media and government layers
"""

from __future__ import annotations

from typing import Any

from lobby_nl.models import (
    Actor,
    ActorCategory,
    CertaintyLevel,
)


class Classifier:
    """Classifies actors into correct categories based on evidence, not identity."""

    CATEGORY_RULES: dict[ActorCategory, dict[str, Any]] = {
        ActorCategory.pro_israel_org: {
            "indicators": [
                "pro-israel lobby", "israel lobby", "israel advocacy",
                "supports israel", "stand with israel", "israël steunen",
                "israël lobby", "pro-israël organisatie",
            ],
            "requires_source": True,
            "exclude_if_only": [
                "joods", "jewish", "joodse", "antisemitisme",
            ],
        },
        ActorCategory.christian_zionist_org: {
            "indicators": [
                "christian zionist", "christelijke zionist",
                "christians for israel", "christenen voor israël",
                "christelijk israël", "bijbelse zionist",
            ],
            "requires_source": True,
            "separate_from": [ActorCategory.pro_israel_org, ActorCategory.jewish_civic_org],
        },
        ActorCategory.jewish_civic_org: {
            "indicators": [
                "joods maatschappelijk", "joodse gemeenschap",
                "joods cultureel", "synagoge", "joods overleg",
                "joodse organisatie", "jewish community",
            ],
            "requires_source": True,
            "never_auto_classify_as": [
                ActorCategory.pro_israel_org,
                ActorCategory.israeli_diplomatic_channel,
            ],
        },
        ActorCategory.israeli_diplomatic_channel: {
            "indicators": [
                "israeli embassy", "israëlische ambassade",
                "israëlisch ministerie", "israel ministry",
                "israëlische regering", "israeli government",
            ],
            "requires_source": True,
            "separate_from": [ActorCategory.pro_israel_org],
        },
        ActorCategory.antisemitism_policy_infrastructure: {
            "indicators": [
                "antisemitisme coördinator", "nida",
                "nationaal coördinator antisemitisme",
                "antisemitism coordinator", "bestrijding antisemitisme",
            ],
            "requires_source": True,
            "never_auto_classify_as": [
                ActorCategory.pro_israel_org,
                ActorCategory.christian_zionist_org,
            ],
        },
        ActorCategory.palestine_rights_counter_lobby: {
            "indicators": [
                "palestina solidariteit", "palestine solidarity",
                "palestijnse rechten", "palestinian rights",
                "bds", "boycot desinvestering sancties",
                "stop de bezetting", "end the occupation",
                "free palestine", "vrij palestina",
                "palestina comité", "palestine committee",
            ],
            "requires_source": True,
        },
    }

    def classify_actor(
        self, actor: Actor, description: str = "", source_texts: list[str] | None = None
    ) -> Actor:
        """Classify an actor based on source evidence, not identity."""
        combined_text = (description + " " + " ".join(source_texts or [])).lower()

        matched_categories: list[tuple[ActorCategory, float]] = []
        for category, rules in self.CATEGORY_RULES.items():
            score = 0.0
            for indicator in rules.get("indicators", []):
                if indicator.lower() in combined_text:
                    score += 1.0
            if score > 0:
                matched_categories.append((category, score))

        matched_categories.sort(key=lambda x: x[1], reverse=True)
        if matched_categories:
            best_category, best_score = matched_categories[0]
            if actor.category == ActorCategory.unknown:
                actor.category = best_category
                actor.confidence = min(0.9, 0.4 + best_score * 0.1)
            actor.subcategories = [
                cat for cat, _ in matched_categories[1:3] if cat != best_category
            ]
        return actor

    def apply_structural_rules(self, actor: Actor) -> Actor:
        """Apply structural classification rules."""
        if actor.is_organization:
            name_lower = actor.name.lower()
            if any(k in name_lower for k in ("ministerie van",)):
                actor.category = ActorCategory.ministry_actor
                actor.certainty = CertaintyLevel.fact
            elif any(k in name_lower for k in ("tweede kamer",)):
                actor.category = ActorCategory.house_actor
            elif any(k in name_lower for k in ("eerste kamer",)):
                actor.category = ActorCategory.senate_actor
            elif any(k in name_lower for k in ("politie",)):
                actor.category = ActorCategory.police_actor
            elif any(k in name_lower for k in ("aivd", "nctv", "nctb")):
                actor.category = ActorCategory.security_actor
            elif any(k in name_lower for k in ("universiteit", "hogeschool")):
                actor.category = ActorCategory.academic_actor
            elif any(k in name_lower for k in ("fonds", "stichting", "foundation")):
                pass
            elif any(k in name_lower for k in ("advocaten", "lawyers", "juridisch")):
                actor.category = ActorCategory.law_firm_actor
        return actor

    def classify_batch(self, actors: list[Actor], source_texts: dict[str, str] | None = None) -> list[Actor]:
        """Classify a batch of actors."""
        for actor in actors:
            actor = self.apply_structural_rules(actor)
            if actor.category == ActorCategory.unknown:
                actor = self.classify_actor(
                    actor,
                    description=actor.description,
                    source_texts=(
                        [source_texts[sid] for sid in actor.source_ids if sid in (source_texts or {})]
                        if source_texts
                        else None
                    ),
                )
        return actors
