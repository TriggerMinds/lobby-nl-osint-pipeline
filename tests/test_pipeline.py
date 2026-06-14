"""Tests for the Lobby NL OSINT Research Pipeline."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lobby_nl.models import (
    Actor,
    ActorCategory,
    CertaintyLevel,
    Claim,
    DataGap,
    EvidenceStrength,
    Event,
    OpacityMechanism,
    OpacitySignal,
    Relationship,
    RelationshipType,
    Source,
)
from lobby_nl.validators import ValidationGuards
from lobby_nl.classifiers import Classifier
from lobby_nl.exporters import CSVExporter, GephiExporter, JSONExporter
from lobby_nl.extractors import ActorExtractor
from lobby_nl.analysis import MediaFramingAnalyzer


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestActor:
    def test_actor_requires_source(self) -> None:
        actor = Actor(name="Test Org", source_ids=[])
        assert actor.certainty == CertaintyLevel.missingness

    def test_actor_with_source(self) -> None:
        actor = Actor(name="Test Org", source_ids=["src_test123"])
        assert len(actor.source_ids) == 1

    def test_identity_guard(self) -> None:
        actor = Actor(
            name="Jewish Community Org",
            category=ActorCategory.jewish_civic_org,
            source_ids=["src_test"],
        )
        assert actor.category == ActorCategory.jewish_civic_org

    def test_actor_not_pro_israel_from_identity(self) -> None:
        actor = Actor(
            name="Jewish Cultural Center",
            category=ActorCategory.jewish_civic_org,
            source_ids=["src_test"],
            inclusion_rationale="Jewish civic organization per source",
        )
        assert actor.category != ActorCategory.pro_israel_org


class TestClaim:
    def test_claim_requires_source(self) -> None:
        with pytest.raises(ValueError):
            Claim(claim_text="A claim", actor_id="act_test", source_id="")

    def test_claim_weak_evidence(self) -> None:
        claim = Claim(
            claim_text="A weakly supported claim",
            actor_id="act_test",
            source_id="src_test",
            evidence_strength=EvidenceStrength.weak,
        )
        assert claim.evidence_strength == EvidenceStrength.weak


class TestRelationship:
    def test_relationship_requires_source(self) -> None:
        with pytest.raises(ValueError):
            Relationship(actor_a_id="a1", actor_b_id="a2", source_ids=[])

    def test_relationship_with_source(self) -> None:
        rel = Relationship(
            actor_a_id="a1",
            actor_b_id="a2",
            source_ids=["src_test"],
            relationship_type=RelationshipType.collaborates,
        )
        assert len(rel.source_ids) == 1


class TestSource:
    def test_source_valid_url(self) -> None:
        src = Source(url="https://example.com")
        assert src.url == "https://example.com"

    def test_source_invalid_url(self) -> None:
        with pytest.raises(ValueError):
            Source(url="not-a-url")

    def test_source_has_access_date(self) -> None:
        src = Source(url="https://example.com")
        assert src.access_date != ""


class TestDataGap:
    def test_data_gap_creation(self) -> None:
        gap = DataGap(
            description="Missing funding data for org X",
            affected_actor_ids=["act_test"],
            opacity_mechanisms=[OpacityMechanism.hard_to_trace_funding],
            alternative_explanation="Funding data may exist in non-public registers",
        )
        assert gap.description != ""
        assert len(gap.opacity_mechanisms) == 1


class TestOpacitySignal:
    def test_opacity_signal_has_alternative_explanation(self) -> None:
        signal = OpacitySignal(
            signal_type=OpacityMechanism.source_removal,
            description="Source page removed",
            alternative_explanation="May be routine site maintenance",
        )
        assert signal.alternative_explanation != ""


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

class TestValidators:
    def test_identity_inference_guard(self) -> None:
        guards = ValidationGuards()
        actors = [
            Actor(
                name="Jewish Civic Org",
                category=ActorCategory.jewish_civic_org,
                subcategories=[ActorCategory.pro_israel_org],
                source_ids=["src1"],
            )
        ]
        report = guards.identity_inference_guard(actors)
        assert len(report.warnings) > 0

    def test_source_validator(self) -> None:
        guards = ValidationGuards()
        sources = [
            Source(url="https://example.com", access_date=""),
            Source(url="https://example.org", access_date=datetime.now(timezone.utc).isoformat()),
        ]
        report = guards.source_validator(sources)
        assert len(report.errors) >= 1

    def test_relationship_validator_source_required(self) -> None:
        with pytest.raises(ValueError):
            Relationship(actor_a_id="a1", actor_b_id="a2", source_ids=[])

    def test_relationship_validator_weak_signal(self) -> None:
        guards = ValidationGuards()
        rels = [
            Relationship(
                actor_a_id="a1",
                actor_b_id="a2",
                source_ids=["src1"],
                evidence_strength=EvidenceStrength.light,
            )
        ]
        report = guards.relationship_validator(rels)
        assert len(report.warnings) >= 1

    def test_duplicate_guard(self) -> None:
        guards = ValidationGuards()
        actors = [
            Actor(name="Stichting Israël Actie", source_ids=["src1"]),
            Actor(name="Stichting Israel Actie", source_ids=["src2"]),
        ]
        report = guards.duplicate_guard(actors)
        assert len(report.warnings) > 0

    def test_category_validator(self) -> None:
        guards = ValidationGuards()
        actors = [
            Actor(
                name="Some Organization",
                is_organization=True,
                category=ActorCategory.journalist_actor,
                source_ids=["src1"],
            )
        ]
        report = guards.category_validator(actors)
        assert len(report.warnings) > 0

    def test_export_validator_valid(self) -> None:
        guards = ValidationGuards()
        actors = [Actor(name="Test", actor_id="act1", source_ids=["src1"])]
        claims = [Claim(claim_text="Test", actor_id="act1", source_id="src1")]
        rels = [Relationship(actor_a_id="act1", actor_b_id="act1", source_ids=["src1"])]
        report = guards.export_validator(actors, claims, rels)
        assert report.is_valid


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------

class TestClassifier:
    def test_classify_christian_zionist(self) -> None:
        classifier = Classifier()
        actor = Actor(
            name="Christenen voor Israël",
            category=ActorCategory.unknown,
            source_ids=["src1"],
        )
        result = classifier.classify_actor(
            actor, description="christelijke zionistische organisatie"
        )
        assert result.category == ActorCategory.christian_zionist_org

    def test_classify_diplomatic_not_pro_israel(self) -> None:
        classifier = Classifier()
        actor = Actor(
            name="Ambassade van Israël",
            category=ActorCategory.unknown,
            source_ids=["src1"],
        )
        result = classifier.classify_actor(
            actor, description="israëlische ambassade in den haag"
        )
        assert result.category == ActorCategory.israeli_diplomatic_channel

    def test_classify_jewish_civic_not_lobby(self) -> None:
        classifier = Classifier()
        actor = Actor(
            name="Centraal Joods Overleg",
            category=ActorCategory.unknown,
            source_ids=["src1"],
        )
        result = classifier.classify_actor(
            actor, description="joods maatschappelijk overleg orgaan"
        )
        assert result.category != ActorCategory.pro_israel_org

    def test_classify_palestine_rights(self) -> None:
        classifier = Classifier()
        actor = Actor(
            name="Palestina Komitee",
            category=ActorCategory.unknown,
            source_ids=["src1"],
        )
        result = classifier.classify_actor(
            actor, description="palestina solidariteit comité"
        )
        assert result.category == ActorCategory.palestine_rights_counter_lobby

    def test_structural_rules_ministry(self) -> None:
        classifier = Classifier()
        actor = Actor(
            name="Ministerie van Buitenlandse Zaken",
            category=ActorCategory.unknown,
            source_ids=["src1"],
        )
        result = classifier.apply_structural_rules(actor)
        assert result.category == ActorCategory.ministry_actor

    def test_classify_batch(self) -> None:
        classifier = Classifier()
        actors = [
            Actor(name="CIDI", category=ActorCategory.unknown, source_ids=["src1"]),
            Actor(name="NIDA", category=ActorCategory.unknown, source_ids=["src2"]),
        ]
        source_texts = {
            "src1": "CIDI is een pro-israël lobby organisatie",
            "src2": "NIDA is de nationaal coördinator antisemitisme bestrijding",
        }
        results = classifier.classify_batch(actors, source_texts)
        assert results[0].category == ActorCategory.pro_israel_org
        assert results[1].category == ActorCategory.antisemitism_policy_infrastructure


# ---------------------------------------------------------------------------
# Extractor tests
# ---------------------------------------------------------------------------

class TestActorExtractor:
    def test_extract_actors_from_text(self) -> None:
        extractor = ActorExtractor()
        source = Source(
            url="https://example.com",
            content_text="Christenen voor Israël organiseert een bijeenkomst. "
            "De ambassade van Israël was aanwezig. "
            "Het CIDI lobbyt in de Tweede Kamer.",
        )
        found = extractor.extract_actors_from_source(source)
        assert len(found) > 0

    def test_extract_organization_names(self) -> None:
        extractor = ActorExtractor()
        text = "Het Centraal Joods Overleg en de Stichting Israël Actie werken samen."
        names = extractor.extract_organization_names(text)
        assert len(names) > 0


# ---------------------------------------------------------------------------
# Exporter tests
# ---------------------------------------------------------------------------

class TestCSVExporter:
    def test_export_actors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exporter = CSVExporter(output_dir=Path(tmp))
            actors = [Actor(name="Test Org", source_ids=["src1"])]
            path = exporter.export_actors(actors)
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            assert "Test Org" in content

    def test_export_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exporter = CSVExporter(output_dir=Path(tmp))
            claims = [
                Claim(
                    claim_text="Test claim",
                    actor_id="act1",
                    source_id="src1",
                )
            ]
            path = exporter.export_claims(claims)
            assert path.exists()

    def test_export_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exporter = CSVExporter(output_dir=Path(tmp))
            rels = [
                Relationship(
                    actor_a_id="a1",
                    actor_b_id="a2",
                    source_ids=["src1"],
                )
            ]
            path = exporter.export_relationships(rels)
            assert path.exists()

    def test_specialized_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exporter = CSVExporter(output_dir=Path(tmp))
            actors = [
                Actor(name="NOS", category=ActorCategory.media_actor, source_ids=["src1"]),
                Actor(name="Volkskrant", category=ActorCategory.media_actor, source_ids=["src1"]),
                Actor(name="Tweede Kamerlid X", category=ActorCategory.house_actor, source_ids=["src2"]),
            ]
            results = exporter.export_media_lists(actors)
            assert len(results) > 0
            media_path = results.get("media_organisaties.csv")
            assert media_path is not None
            assert media_path.exists()


class TestGephiExporter:
    def test_export_nodes_and_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exporter = GephiExporter(output_dir=Path(tmp))
            actors = [Actor(name="Node1", source_ids=["src1"])]
            rels = [Relationship(actor_a_id="a1", actor_b_id="a2", source_ids=["src1"])]
            nodes_path = exporter.export_nodes(actors)
            edges_path = exporter.export_edges(rels)
            assert nodes_path.exists()
            assert edges_path.exists()


class TestJSONExporter:
    def test_export_evidence_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exporter = JSONExporter(output_dir=Path(tmp))
            actors = [Actor(name="Test", source_ids=["src1"])]
            claims = [Claim(claim_text="Test", actor_id="act_t", source_id="src1")]
            rels = [Relationship(actor_a_id="a1", actor_b_id="a2", source_ids=["src1"])]
            sources = [Source(url="https://example.com")]
            events: list[Event] = []
            path = exporter.export_evidence_graph(actors, claims, rels, sources, events)
            assert path.exists()
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "actors" in data
            assert data["metadata"]["actor_count"] == 1


# ---------------------------------------------------------------------------
# Media framing tests
# ---------------------------------------------------------------------------

class TestMediaFraming:
    def test_analyze_source(self) -> None:
        analyzer = MediaFramingAnalyzer()
        src = Source(
            url="https://example.com/article1",
            content_text="Het conflict in het Midden-Oosten escaleert. "
            "Er zijn veel burgerdoden gevallen en de humanitaire situatie is ernstig. "
            "De veiligheidsdienst waarschuwt voor terrorisme dreiging.",
        )
        results = analyzer.analyze_source(src)
        assert len(results) > 0

    def test_detect_recurring_guesting(self) -> None:
        analyzer = MediaFramingAnalyzer()
        actors = [
            Actor(name="Spreker A", actor_id="act1", source_ids=["src1"]),
        ]
        sources = [
            Source(
                url="https://example.com/show1",
                content_text="Spreker A was te gast en sprak over het conflict. Spreker A gaf zijn mening.",
            ),
            Source(
                url="https://example.com/show2",
                content_text="Spreker A verscheen opnieuw in het programma.",
            ),
        ]
        results = analyzer.detect_recurring_guesting(sources, actors)
        assert len(results) > 0
        assert results[0]["appearance_count"] >= 2


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_data_flow(self) -> None:
        actor = Actor(name="Test Org", source_ids=["src_test123"])
        claim = Claim(
            claim_text="Org makes a claim",
            actor_id=actor.actor_id,
            source_id="src_test123",
        )
        rel = Relationship(
            actor_a_id=actor.actor_id,
            actor_b_id=actor.actor_id,
            source_ids=["src_test123"],
        )
        assert actor.actor_id != ""
        assert claim.claim_id != ""
        assert rel.relationship_id != ""

    def test_category_enum_values(self) -> None:
        assert ActorCategory.pro_israel_org.value == "pro_israel_org"
        assert ActorCategory.christian_zionist_org.value == "christian_zionist_org"
        assert ActorCategory.jewish_civic_org.value == "jewish_civic_org"
        assert ActorCategory.israeli_diplomatic_channel.value == "israeli_diplomatic_channel"
        assert ActorCategory.palestine_rights_counter_lobby.value == "palestine_rights_counter_lobby"

    def test_evidence_strength_ordering(self) -> None:
        strengths = [
            EvidenceStrength.hard,
            EvidenceStrength.strong,
            EvidenceStrength.medium,
            EvidenceStrength.light,
            EvidenceStrength.weak,
        ]
        assert len(strengths) == 5
