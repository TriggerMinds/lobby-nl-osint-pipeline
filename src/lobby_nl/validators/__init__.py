"""Validation guards for the OSINT research pipeline.

Implements:
- identity_inference_guard
- overclaim_guard
- omission_guard
- duplicate_guard
- source_validator
- relationship_validator
- category_validator
- export_validator
"""

from __future__ import annotations

from typing import Any

from lobby_nl.models import (
    Actor,
    ActorCategory,
    CertaintyLevel,
    Claim,
    EvidenceStrength,
    Relationship,
    Source,
)


class ValidationReport:
    """Collects validation issues across the pipeline."""

    def __init__(self) -> None:
        self.errors: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []
        self.info: list[dict[str, Any]] = []

    def add_error(self, entity_type: str, entity_id: str, message: str) -> None:
        self.errors.append({"entity_type": entity_type, "entity_id": entity_id, "message": message})

    def add_warning(self, entity_type: str, entity_id: str, message: str) -> None:
        self.warnings.append(
            {"entity_type": entity_type, "entity_id": entity_id, "message": message}
        )

    def add_info(self, entity_type: str, entity_id: str, message: str) -> None:
        self.info.append({"entity_type": entity_type, "entity_id": entity_id, "message": message})

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        return (
            f"ValidationReport(errors={len(self.errors)}, "
            f"warnings={len(self.warnings)}, info={len(self.info)})"
        )


class ValidationGuards:
    """Central validation system for all pipeline entities."""

    def __init__(self) -> None:
        self.report = ValidationReport()

    def identity_inference_guard(self, actors: list[Actor]) -> ValidationReport:
        """Prevent classification from identity alone.

        No Jewish civic actor auto-classified as lobby.
        No antisemitism-policy actor auto-classified as Zionist.
        No person included from identity alone.
        No organization classified from identity alone.
        """
        sensitive_combos = {
            ActorCategory.jewish_civic_org: [ActorCategory.pro_israel_org],
            ActorCategory.antisemitism_policy_infrastructure: [
                ActorCategory.pro_israel_org,
                ActorCategory.christian_zionist_org,
            ],
        }
        for actor in actors:
            for base_cat, forbidden_cats in sensitive_combos.items():
                if actor.category == base_cat:
                    for fc in forbidden_cats:
                        if fc in actor.subcategories:
                            if not any(
                                s.startswith("src_") for s in (actor.source_ids or [])
                            ) or len(actor.source_ids or []) <= 1:
                                self.report.add_warning(
                                    "Actor",
                                    actor.actor_id,
                                    f"Category {fc.value} applied to {base_cat.value} "
                                    f"without sufficient source backing: {actor.name}",
                                )
        return self.report

    def overclaim_guard(self, claims: list[Claim]) -> ValidationReport:
        """Prevent claims that overstate evidence."""
        for claim in claims:
            if claim.evidence_strength == EvidenceStrength.weak and claim.certainty in (
                CertaintyLevel.fact,
                CertaintyLevel.interpretation,
            ):
                self.report.add_warning(
                    "Claim",
                    claim.claim_id,
                    f"Weak evidence claim marked as {claim.certainty.value}: "
                    f"{claim.claim_text[:100]}",
                )
            if claim.certainty == CertaintyLevel.fact and not claim.source_id:
                self.report.add_error(
                    "Claim",
                    claim.claim_id,
                    f"Fact-level claim missing source: {claim.claim_text[:100]}",
                )
        return self.report

    def omission_guard(
        self,
        actors: list[Actor],
        claims: list[Claim],
        relationships: list[Relationship],
    ) -> ValidationReport:
        """Detect potential omissions: actors without claims or relationships."""
        actors_with_claims = {c.actor_id for c in claims}
        actors_with_rels = {r.actor_a_id for r in relationships} | {r.actor_b_id for r in relationships}
        for actor in actors:
            if actor.actor_id not in actors_with_claims and actor.actor_id not in actors_with_rels:
                if actor.category not in (
                    ActorCategory.archive_actor,
                    ActorCategory.unknown,
                ):
                    self.report.add_info(
                        "Actor",
                        actor.actor_id,
                        f"Actor has no claims or relationships: {actor.name}",
                    )
        return self.report

    def duplicate_guard(self, actors: list[Actor]) -> ValidationReport:
        """Detect potential duplicate actors."""
        from rapidfuzz import fuzz

        names = [(a.actor_id, a.name.lower().strip()) for a in actors]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                score = fuzz.ratio(names[i][1], names[j][1])
                if score > 90 and len(names[i][1]) > 5:
                    self.report.add_warning(
                        "Actor",
                        f"{names[i][0]}, {names[j][0]}",
                        f"Possible duplicate (score={score}): "
                        f"'{actors[i].name}' vs '{actors[j].name}'",
                    )
        return self.report

    def source_validator(self, sources: list[Source]) -> ValidationReport:
        """Validate source records.

        Every source must have access_date.
        Content hash should be present where possible.
        """
        for src in sources:
            if not src.access_date:
                self.report.add_error(
                    "Source",
                    src.source_id,
                    f"Source missing access_date: {src.url}",
                )
            if not src.content_hash and src.content_text:
                self.report.add_warning(
                    "Source",
                    src.source_id,
                    f"Source with content missing hash: {src.url}",
                )
            if src.is_dead or src.is_stale:
                self.report.add_info(
                    "Source",
                    src.source_id,
                    f"Source is dead/stale: {src.url}",
                )
        return self.report

    def relationship_validator(self, relationships: list[Relationship]) -> ValidationReport:
        """Validate relationships."""
        for rel in relationships:
            if not rel.source_ids:
                self.report.add_error(
                    "Relationship",
                    rel.relationship_id,
                    f"Relationship missing source: {rel.actor_a_id} - {rel.actor_b_id}",
                )
            if rel.evidence_strength in (EvidenceStrength.light, EvidenceStrength.weak):
                if not rel.notes:
                    self.report.add_warning(
                        "Relationship",
                        rel.relationship_id,
                        f"Weak/light relationship without notes: "
                        f"{rel.actor_a_id} - {rel.actor_b_id}",
                    )
        return self.report

    def category_validator(self, actors: list[Actor]) -> ValidationReport:
        """Validate actor categories are used correctly."""
        for actor in actors:
            if actor.is_organization and actor.category in (
                ActorCategory.celebrity_actor,
                ActorCategory.journalist_actor,
                ActorCategory.influencer_actor,
                ActorCategory.mayor_actor,
            ):
                self.report.add_warning(
                    "Actor",
                    actor.actor_id,
                    f"Organization {actor.name} has person-typical category {actor.category.value}",
                )
        return self.report

    def export_validator(
        self,
        actors: list[Actor],
        claims: list[Claim],
        relationships: list[Relationship],
    ) -> ValidationReport:
        """Pre-export validation: ensure all references are valid."""
        actor_ids = {a.actor_id for a in actors}
        source_ids = set()
        for a in actors:
            source_ids.update(a.source_ids)
        for c in claims:
            source_ids.add(c.source_id)
            source_ids.update(c.source_ids)
            if c.actor_id and c.actor_id not in actor_ids:
                self.report.add_error(
                    "Claim",
                    c.claim_id,
                    f"Claim references unknown actor: {c.actor_id}",
                )
        for r in relationships:
            source_ids.update(r.source_ids)
            if r.actor_a_id not in actor_ids:
                self.report.add_error(
                    "Relationship",
                    r.relationship_id,
                    f"Relationship references unknown actor_a: {r.actor_a_id}",
                )
            if r.actor_b_id not in actor_ids:
                self.report.add_error(
                    "Relationship",
                    r.relationship_id,
                    f"Relationship references unknown actor_b: {r.actor_b_id}",
                )
        for claim in claims:
            if claim.source_id and claim.source_id not in source_ids:
                self.report.add_warning(
                    "Claim",
                    claim.claim_id,
                    f"Claim source_id not in known sources (may be unresolved): {claim.source_id}",
                )
        return self.report

    def validate_all(
        self,
        actors: list[Actor],
        claims: list[Claim],
        relationships: list[Relationship],
        sources: list[Source],
    ) -> ValidationReport:
        """Run all validation guards."""
        self.identity_inference_guard(actors)
        self.overclaim_guard(claims)
        self.omission_guard(actors, claims, relationships)
        self.duplicate_guard(actors)
        self.source_validator(sources)
        self.relationship_validator(relationships)
        self.category_validator(actors)
        self.export_validator(actors, claims, relationships)
        return self.report
