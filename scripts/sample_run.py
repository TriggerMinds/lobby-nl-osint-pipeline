"""Generate sample data and run through the pipeline to produce example exports."""

import json
from datetime import datetime, timezone
from pathlib import Path

from lobby_nl.analysis import ArchiveDiffAnalyzer, MediaFramingAnalyzer
from lobby_nl.collectors import ArchiveCollector
from lobby_nl.exporters import CSVExporter, GephiExporter, HTMLReportExporter, JSONExporter, OpenRefineExporter, Neo4jExporter
from lobby_nl.models import (
    Actor,
    ActorCategory,
    CertaintyLevel,
    Claim,
    DataGap,
    Event,
    EvidenceStrength,
    EvidenceType,
    Exclusion,
    OpacityMechanism,
    OpacitySignal,
    ParliamentaryRecord,
    Relationship,
    RelationshipType,
    Source,
    SourceConflict,
)


def generate_spokesperson_person(spoke_id: str, name: str, org_actor_id: str, source_id: str, org_name: str) -> Actor:
    """Generate a natural-person spokesperson/leader linked to an org actor."""
    return Actor(
        actor_id=spoke_id,
        name=name,
        is_organization=False,
        is_person=True,
        category=ActorCategory.journalist_actor,
        role=f"Director/Spokesperson of {org_name}",
        public_function=org_name,
        source_ids=[source_id],
        description=f"Public spokesperson and director of {org_name}, appears in media, parliamentary settings, and public events as a representative of the organization.",
        confidence=0.85,
        certainty=CertaintyLevel.fact,
    )


def generate_sample_data() -> dict:
    now = datetime.now(timezone.utc).isoformat()

    sources = [
        Source(
            source_id="src_cidi_2026",
            url="https://www.cidi.nl/over-cidi",
            title="Over CIDI | Centrum Informatie en Documentatie Israël",
            source_type="web",
            content_text="CIDI is een pro-Israël lobby organisatie die zich inzet voor de bestrijding van antisemitisme. CIDI onderhoudt nauwe contacten met de Tweede Kamer en organiseert jaarlijks evenementen. CIDI werkt samen met Christenen voor Israël en heeft banden met de Israëlische ambassade.",
            content_hash="abc123_cidi",
        ),
        Source(
            source_id="src_nida_2026",
            url="https://www.nida.nl/over-ons",
            title="Nationaal Coördinator Antisemitismebestrijding",
            source_type="web",
            content_text="De NCAB (NIDA) is het nationale coördinatiepunt voor de bestrijding van antisemitisme in Nederland. De coördinator brengt jaarlijks rapport uit aan de Tweede Kamer over antisemitisme trends. NCAB werkt samen met politie, OM, en maatschappelijke organisaties.",
            content_hash="def456_nida",
        ),
        Source(
            source_id="src_cvi_2026",
            url="https://www.christenenvoorisrael.nl/",
            title="Christenen voor Israël - Bijbelse Zionisme Organisatie",
            source_type="web",
            content_text="Christenen voor Israël is een christelijk-zionistische organisatie die Israël steunt op bijbelse gronden. De organisatie organiseert jaarlijks de Israëlzondag en campagnes. CVI lobbyt actief in de Tweede Kamer en werkt samen met CIDI.",
            content_hash="ghi789_cvi",
        ),
        Source(
            source_id="src_cjo_2026",
            url="https://www.cjo.nl/",
            title="Centraal Joods Overleg - Joods Maatschappelijk Overleg",
            source_type="web",
            content_text="Het Centraal Joods Overleg vertegenwoordigt de Joodse gemeenschap in Nederland. CJO behartigt belangen van Joodse organisaties op het gebied van religie, cultuur, onderwijs en maatschappij. CJO is geen pro-Israël lobby maar een Joods maatschappelijk platform.",
            content_hash="jkl012_cjo",
        ),
        Source(
            source_id="src_pk_2026",
            url="https://www.palestina-komitee.nl/",
            title="Palestina Komitee - Solidariteit met Palestina",
            source_type="web",
            content_text="Het Palestina Komitee is een solidariteitsorganisatie voor Palestijnse rechten. De organisatie organiseert demonstraties, campagnes en bewustwordingsactiviteiten. Het komitee steunt BDS en werkt tegen de Israëlische bezetting.",
            content_hash="mno345_pk",
        ),
        Source(
            source_id="src_vk_2026",
            url="https://www.volkskrant.nl/nieuws/israel-palestina",
            title="Volkskrant - Israel-Palestina Conflict Artikelen",
            source_type="media",
            content_text="De situatie in het Midden-Oosten escaleert verder. Israëlische bombardementen op Gaza hebben tot vele burgerdoden geleid. Internationale oproepen tot een staakt-het-vuren nemen toe. De humanitaire situatie in de bezette gebieden verslechtert. Het conflict en de bezetting duren voort. Antisemitisme in Nederland neemt toe na de gebeurtenissen.",
            content_hash="pqr678_vk",
        ),
        Source(
            source_id="src_tk_2026",
            url="https://www.tweedekamer.nl/kamerstukken/",
            title="Tweede Kamer - Commissiedebat Midden-Oosten",
            source_type="parliamentary",
            content_text="Verslag van het commissiedebat over de situatie in het Midden-Oosten. Aanwezig waren vertegenwoordigers van CIDI, het Palestina Komitee, en Christenen voor Israël. De Kamer sprak over antisemitisme bestrijding, de twee-statenoplossing, en Nederlandse betrokkenheid bij het vredesproces.",
            content_hash="stu901_tk",
        ),
    ]

    actors = [
        Actor(
            actor_id="act_cidi",
            name="CIDI - Centrum Informatie en Documentatie Israël",
            category=ActorCategory.pro_israel_org,
            description="Pro-Israël lobby en documentatiecentrum, actief in antisemitisme bestrijding en Israël-advocacy",
            source_ids=["src_cidi_2026"],
            role="Lobby organizatie",
            public_function="Israël-advocacy, antisemitisme bestrijding",
            confidence=0.9,
            certainty=CertaintyLevel.fact,
            website="https://www.cidi.nl/",
        ),
        generate_spokesperson_person("act_cidi_spoke", "Jaap Hamburger", "act_cidi", "src_cidi_2026", "CIDI"),
        Actor(
            actor_id="act_nida",
            name="NCAB - Nationaal Coördinator Antisemitismebestrijding",
            category=ActorCategory.antisemitism_policy_infrastructure,
            description="Nationaal coördinatiepunt antisemitisme bestrijding, rapporteert aan Tweede Kamer",
            source_ids=["src_nida_2026"],
            role="Overheidscoördinator",
            public_function="Antisemitisme bestrijding",
            confidence=1.0,
            certainty=CertaintyLevel.fact,
            website="https://www.nida.nl/",
        ),
        Actor(
            actor_id="act_cvi",
            name="Christenen voor Israël International",
            category=ActorCategory.christian_zionist_org,
            description="Christelijk-zionistische organisatie, steunt Israël op bijbelse gronden",
            source_ids=["src_cvi_2026"],
            role="Christelijk-zionistische organisatie",
            public_function="Christelijke Israël-ondersteuning en lobby",
            confidence=0.95,
            certainty=CertaintyLevel.fact,
            website="https://www.christenenvoorisrael.nl/",
        ),
        generate_spokesperson_person("act_cvi_spoke", "Roger van Oordt", "act_cvi", "src_cvi_2026", "Christenen voor Israël"),
        Actor(
            actor_id="act_cjo",
            name="Centraal Joods Overleg",
            category=ActorCategory.jewish_civic_org,
            description="Joods maatschappelijk overlegorgaan, vertegenwoordigt Joodse gemeenschap in NL",
            source_ids=["src_cjo_2026"],
            role="Joods maatschappelijk platform",
            public_function="Vertegenwoordiging Joodse gemeenschap",
            confidence=0.9,
            certainty=CertaintyLevel.fact,
            website="https://www.cjo.nl/",
        ),
        Actor(
            actor_id="act_pk",
            name="Palestina Komitee",
            category=ActorCategory.palestine_rights_counter_lobby,
            description="Solidariteitsorganisatie voor Palestijnse rechten, organiseert demonstraties en campagnes",
            source_ids=["src_pk_2026"],
            role="Solidariteitsorganisatie",
            public_function="Palestina-solidariteit en BDS-campagnes",
            confidence=0.90,
            certainty=CertaintyLevel.fact,
            website="https://www.palestina-komitee.nl/",
        ),
        Actor(
            actor_id="act_volkskrant",
            name="De Volkskrant",
            category=ActorCategory.media_actor,
            description="Nederlands dagblad, rapporteert over Midden-Oosten conflict en binnenlandse politiek",
            source_ids=["src_vk_2026"],
            role="Dagblad / nieuwsmedia",
            public_function="Nieuwsverslaggeving",
            confidence=1.0,
            certainty=CertaintyLevel.fact,
            website="https://www.volkskrant.nl/",
        ),
        Actor(
            actor_id="act_tk_commissie",
            name="Tweede Kamer Commissie Buitenlandse Zaken",
            category=ActorCategory.committee_actor,
            description="Parlementaire commissie voor buitenlandse zaken, behandelt Midden-Oosten dossiers",
            source_ids=["src_tk_2026"],
            role="Parlementaire commissie",
            public_function="Kamercommissie Buitenlandse Zaken",
            confidence=1.0,
            certainty=CertaintyLevel.fact,
        ),
        Actor(
            actor_id="act_bz",
            name="Ministerie van Buitenlandse Zaken",
            category=ActorCategory.ministry_actor,
            description="Ministerie verantwoordelijk voor Nederlands buitenlandbeleid inclusief Midden-Oosten",
            source_ids=["src_tk_2026"],
            role="Ministerie",
            public_function="Buitenlands beleid",
            confidence=1.0,
            certainty=CertaintyLevel.fact,
        ),
        Actor(
            actor_id="act_politie",
            name="Politie Nederland - Eenheid Den Haag",
            category=ActorCategory.police_actor,
            description="Handhaving openbare orde bij demonstraties gerelateerd aan Midden-Oosten conflict",
            source_ids=["src_nida_2026"],
            role="Politie eenheid",
            public_function="Openbare orde handhaving",
            confidence=0.8,
            certainty=CertaintyLevel.fact,
        ),
        Actor(
            actor_id="act_isr_amb",
            name="Ambassade van Israël in Den Haag",
            category=ActorCategory.israeli_diplomatic_channel,
            description="Israëlische diplomatieke vertegenwoordiging in Nederland",
            source_ids=["src_cidi_2026"],
            role="Diplomatieke missie",
            public_function="Diplomatieke vertegenwoordiging Israël",
            confidence=1.0,
            certainty=CertaintyLevel.fact,
        ),
    ]

    claims = [
        Claim(
            claim_id="clm_cidi_tk",
            actor_id="act_cidi",
            claim_text="CIDI stelt dat antisemitisme in Nederland is toegenomen en vraagt de Tweede Kamer om strengere maatregelen.",
            source_id="src_cidi_2026",
            topic="antisemitisme bestrijding",
            evidence_type=EvidenceType.documentary_evidence,
            evidence_strength=EvidenceStrength.strong,
        ),
        Claim(
            claim_id="clm_cvi_israel_support",
            actor_id="act_cvi",
            claim_text="Christenen voor Israël verklaart dat Nederland Israël onvoorwaardelijk moet steunen op bijbelse gronden.",
            source_id="src_cvi_2026",
            topic="Israël steun",
            evidence_type=EvidenceType.documentary_evidence,
            evidence_strength=EvidenceStrength.medium,
        ),
        Claim(
            claim_id="clm_pk_bezetting",
            actor_id="act_pk",
            claim_text="Het Palestina Komitee betoogt dat de Israëlische bezetting illegaal is en dat Nederland sancties moet opleggen.",
            source_id="src_pk_2026",
            topic="bezetting / sancties",
            evidence_type=EvidenceType.documentary_evidence,
            evidence_strength=EvidenceStrength.medium,
        ),
        Claim(
            claim_id="clm_nida_rapport",
            actor_id="act_nida",
            claim_text="NCAB rapport stelt dat antisemitisme in Nederland met 30% is toegenomen in het afgelopen jaar.",
            source_id="src_nida_2026",
            topic="antisemitisme cijfers",
            evidence_type=EvidenceType.parliamentary_evidence,
            evidence_strength=EvidenceStrength.strong,
        ),
        Claim(
            claim_id="clm_media_conflict",
            actor_id="act_volkskrant",
            claim_text="De Volkskrant rapporteert dat de humanitaire situatie in Gaza ernstig verslechterd is.",
            source_id="src_vk_2026",
            topic="humanitaire situatie Gaza",
            evidence_type=EvidenceType.media_framing_evidence,
            evidence_strength=EvidenceStrength.light,
        ),
    ]

    relationships = [
        Relationship(
            relationship_id="rel_cidi_cvi_collab",
            actor_a_id="act_cidi",
            actor_b_id="act_cvi",
            relationship_type=RelationshipType.collaborates,
            source_ids=["src_cidi_2026"],
            evidence_type=EvidenceType.network_evidence,
            evidence_strength=EvidenceStrength.medium,
            description="CIDI en Christenen voor Israël werken samen aan pro-Israël campagne en lobby",
        ),
        Relationship(
            relationship_id="rel_cidi_tk_collab",
            actor_a_id="act_cidi",
            actor_b_id="act_tk_commissie",
            relationship_type=RelationshipType.lobbies,
            source_ids=["src_cidi_2026", "src_tk_2026"],
            evidence_type=EvidenceType.institutional_interaction_evidence,
            evidence_strength=EvidenceStrength.strong,
            description="CIDI lobbyt actief bij de Tweede Kamer commissie Buitenlandse Zaken",
        ),
        Relationship(
            relationship_id="rel_cvi_tk_collab",
            actor_a_id="act_cvi",
            actor_b_id="act_tk_commissie",
            relationship_type=RelationshipType.lobbies,
            source_ids=["src_cvi_2026", "src_tk_2026"],
            evidence_type=EvidenceType.institutional_interaction_evidence,
            evidence_strength=EvidenceStrength.medium,
            description="Christenen voor Israël lobbyt bij de Tweede Kamer",
        ),
        Relationship(
            relationship_id="rel_pk_opp_cidi",
            actor_a_id="act_pk",
            actor_b_id="act_cidi",
            relationship_type=RelationshipType.opposes,
            source_ids=["src_pk_2026"],
            evidence_type=EvidenceType.network_evidence,
            evidence_strength=EvidenceStrength.medium,
            description="Palestina Komitee en CIDI staan tegenover elkaar in het debat",
        ),
        Relationship(
            relationship_id="rel_cidi_spoke_cidi",
            actor_a_id="act_cidi_spoke",
            actor_b_id="act_cidi",
            relationship_type=RelationshipType.member_of,
            source_ids=["src_cidi_2026"],
            evidence_type=EvidenceType.osint_evidence,
            evidence_strength=EvidenceStrength.hard,
            description="Jaap Hamburger is directeur en publiek gezicht van CIDI",
        ),
        Relationship(
            relationship_id="rel_cvi_spoke_cvi",
            actor_a_id="act_cvi_spoke",
            actor_b_id="act_cvi",
            relationship_type=RelationshipType.member_of,
            source_ids=["src_cvi_2026"],
            evidence_type=EvidenceType.osint_evidence,
            evidence_strength=EvidenceStrength.hard,
            description="Roger van Oordt is directeur van Christenen voor Israël",
        ),
        Relationship(
            relationship_id="rel_nida_tk",
            actor_a_id="act_nida",
            actor_b_id="act_tk_commissie",
            relationship_type=RelationshipType.parliamentary_relation,
            source_ids=["src_nida_2026"],
            evidence_type=EvidenceType.parliamentary_evidence,
            evidence_strength=EvidenceStrength.hard,
            description="NCAB rapporteert jaarlijks aan de Tweede Kamer",
        ),
        Relationship(
            relationship_id="rel_cidi_isr_amb",
            actor_a_id="act_cidi",
            actor_b_id="act_isr_amb",
            relationship_type=RelationshipType.collaborates,
            source_ids=["src_cidi_2026"],
            evidence_type=EvidenceType.network_evidence,
            evidence_strength=EvidenceStrength.medium,
            description="CIDI onderhoudt banden met de Israëlische ambassade",
        ),
        Relationship(
            relationship_id="rel_bz_tk",
            actor_a_id="act_bz",
            actor_b_id="act_tk_commissie",
            relationship_type=RelationshipType.parliamentary_relation,
            source_ids=["src_tk_2026"],
            evidence_type=EvidenceType.institutional_interaction_evidence,
            evidence_strength=EvidenceStrength.hard,
            description="Ministerie rapporteert aan Kamercommissie Buitenlandse Zaken",
        ),
    ]

    events = [
        Event(
            event_id="evt_israel_zondag_2026",
            name="Israëlzondag 2026",
            event_type="religieus evenement / campagne",
            date="2026-10-04",
            location="Diverse kerken Nederland",
            country="NL",
            organizer_id="act_cvi",
            organizer_name="Christenen voor Israël",
            participant_ids=["act_cidi"],
            description="Jaarlijkse Israëlzondag georganiseerd door Christenen voor Israël",
            topics=["Israël", "Bijbelse profetie", "Christelijk Zionisme"],
        ),
        Event(
            event_id="evt_pk_demo_2026",
            name="Palestina Solidariteitsdemonstratie",
            event_type="demonstratie",
            date="2026-05-15",
            location="Dam, Amsterdam",
            country="NL",
            organizer_id="act_pk",
            organizer_name="Palestina Komitee",
            participant_ids=["act_politie"],
            description="Demonstratie tegen de Israëlische bezetting op Nakba-dag",
            topics=["Palestina", "bezetting", "mensenrechten"],
        ),
    ]

    parliamentary = [
        ParliamentaryRecord(
            record_id="par_tk_2026_bz",
            chamber="Tweede Kamer",
            document_type="commissiedebat",
            title="Commissiedebat Midden-Oosten",
            date="2026-03-15",
            document_number="2026Z04567",
            committee="Buitenlandse Zaken",
            topics=["Midden-Oosten", "Israël", "Palestina", "antisemitisme"],
            source_ids=["src_tk_2026"],
        ),
    ]

    data_gaps = [
        DataGap(
            gap_id="gap_funding_cidi",
            gap_type="funding",
            description="Financieringsbronnen van CIDI niet volledig openbaar. Jaarverslag geeft beperkte informatie over donoren.",
            affected_actor_ids=["act_cidi"],
            opacity_mechanisms=[OpacityMechanism.hard_to_trace_funding],
            alternative_explanation="Donorprivacy kan legitiem zijn, maar bemoeilijkt traceerbaarheid van belangen",
            severity="medium",
        ),
        DataGap(
            gap_id="gap_funding_cvi",
            gap_type="funding",
            description="Financieringsstructuur Christenen voor Israël deels ondoorzichtig. Internationale financieringsstromen onduidelijk.",
            affected_actor_ids=["act_cvi"],
            opacity_mechanisms=[
                OpacityMechanism.hard_to_trace_funding,
                OpacityMechanism.cross_border_offshore,
            ],
            alternative_explanation="Internationale kerkelijke fondsenwerving is complex maar niet per definitie verhullend",
            severity="medium",
        ),
        DataGap(
            gap_id="gap_lobby_register",
            gap_type="structural",
            description="Nederland kent geen algemeen verplicht lobbyregister. Parlementair lobbyregister dekt alleen toegangspas-houders, niet alle lobbyactiviteit.",
            affected_actor_ids=["act_cidi", "act_cvi"],
            opacity_mechanisms=[OpacityMechanism.partial_disclosure],
            alternative_explanation="Structured limitation of Dutch transparency framework",
            severity="high",
        ),
    ]

    opacity_signals = [
        OpacitySignal(
            signal_id="opq_cidi_intermediary",
            signal_type=OpacityMechanism.intermediary_structures,
            description="CIDI opereert mogelijk via intermediaire organisaties voor indirecte beïnvloeding van Kamerleden.",
            actor_ids=["act_cidi"],
            evidence_strength=EvidenceStrength.light,
            alternative_explanation="Samenwerkingsverbanden met andere organisaties zijn gebruikelijk en niet per definitie verhullend",
        ),
        OpacitySignal(
            signal_id="opq_source_stale",
            signal_type=OpacityMechanism.stale_documents,
            description="Sommige brondocumenten op organisatiewebsites zijn verouderd en niet bijgewerkt sinds 2022.",
            evidence_strength=EvidenceStrength.weak,
            alternative_explanation="Websites worden onregelmatig bijgewerkt door beperkte middelen",
        ),
    ]

    source_conflicts = [
        SourceConflict(
            conflict_id="cnf_antisemitism_cijfers",
            source_a_id="src_nida_2026",
            source_b_id="src_cidi_2026",
            description="NCAB en CIDI geven verschillende cijfers over antisemitisme trends in Nederland.",
            conflict_type="data_contradiction",
            resolution="unresolved",
            notes="NCAB baseert zich op politie- en OM-data; CIDI op eigen meldpunt. Methodologische verschillen verklaren deels het verschil.",
        ),
    ]

    exclusions = [
        Exclusion(
            exclusion_id="exc_minor_org_x",
            entity_name="Kleine Israël-vriendenkring Regio Noord",
            exclusion_reason="Onvoldoende publieke bronnen beschikbaar. Organisatie lijkt inactief sinds 2024. Geen parlementaire of media relevantie.",
            notes="Kan opnieuw worden opgenomen indien nieuwe bronnen beschikbaar komen.",
        ),
    ]

    return {
        "actors": actors,
        "claims": claims,
        "relationships": relationships,
        "sources": sources,
        "events": events,
        "parliamentary_records": parliamentary,
        "data_gaps": data_gaps,
        "opacity_signals": opacity_signals,
        "source_conflicts": source_conflicts,
        "exclusions": exclusions,
    }


def main():
    output_dir = Path("exports")
    reports_dir = Path("reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    data = generate_sample_data()

    written_data = {
        "actors": [a.model_dump() for a in data["actors"]],
        "claims": [c.model_dump() for c in data["claims"]],
        "relationships": [r.model_dump() for r in data["relationships"]],
        "sources": [s.model_dump() for s in data["sources"]],
        "events": [e.model_dump() for e in data["events"]],
        "parliamentary_records": [p.model_dump() for p in data["parliamentary_records"]],
        "data_gaps": [g.model_dump() for g in data["data_gaps"]],
        "opacity_signals": [o.model_dump() for o in data["opacity_signals"]],
        "source_conflicts": [c.model_dump() for c in data["source_conflicts"]],
        "exclusions": [e.model_dump() for e in data["exclusions"]],
    }

    classified_path = output_dir / "sample_classified.json"
    classified_path.write_text(
        json.dumps(written_data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(f"[OK] Sample data generated -> {classified_path}")

    csv_exporter = CSVExporter(output_dir=output_dir)
    csv_files = csv_exporter.export_all(
        data["actors"], data["claims"], data["relationships"],
        data["sources"], data["events"], data["parliamentary_records"],
        data["data_gaps"], data["opacity_signals"],
        data["source_conflicts"], data["exclusions"],
    )
    print(f"[OK] CSV exports ({len(csv_files)} files)")

    gephi = GephiExporter(output_dir=output_dir)
    gephi.export_nodes(data["actors"])
    gephi.export_edges(data["relationships"])
    print("[OK] Gephi exports")

    ore = OpenRefineExporter(output_dir=output_dir)
    ore.export_actors(data["actors"])
    ore.export_relationships(data["relationships"])
    ore.export_sources(data["sources"])
    print("[OK] OpenRefine exports (3 files)")

    neo = Neo4jExporter(output_dir=output_dir)
    neo.export_cypher(data["actors"], data["relationships"])
    print("[OK] Neo4j Cypher export")

    json_ex = JSONExporter(output_dir=output_dir)
    json_ex.export_evidence_graph(
        data["actors"], data["claims"], data["relationships"],
        data["sources"], data["events"],
    )
    print("[OK] JSON evidence graph")

    html_ex = HTMLReportExporter(output_dir=reports_dir)
    html_ex.generate_report(
        data["actors"], data["claims"], data["relationships"],
        data["sources"], data["events"],
        data["data_gaps"], data["opacity_signals"],
        [], [],
    )
    print(f"[OK] HTML report -> {reports_dir}")

    framing = MediaFramingAnalyzer(output_dir=output_dir)
    patterns = framing.analyze_sources(data["sources"], data["actors"])
    framing.export_framing_log()
    print(f"[OK] Detected {len(patterns)} framing patterns")

    import pandas as pd
    guesting = framing.detect_recurring_guesting(data["sources"], data["actors"])
    freq_guest_path = output_dir / "recurring_guesting.csv"
    pd.DataFrame(guesting).to_csv(freq_guest_path, index=False)
    print(f"[OK] Recurring guesting -> {freq_guest_path}")

    from lobby_nl.collectors import ArchiveCollector
    from lobby_nl.analysis import ArchiveDiffAnalyzer
    archive = ArchiveCollector(output_dir=output_dir / "raw")
    diff_analyzer = ArchiveDiffAnalyzer(output_dir=output_dir)
    diff_analyzer.log_diff(
        "https://www.cidi.nl/over-cidi", "abc123_new", "abc123_old",
        ["- Oude tekst over CIDI", "+ Nieuwe tekst over CIDI"], True,
    )
    diff_analyzer.log_disappearance(
        "https://old-site.example.com/report-2024.pdf",
        "Page removed, no redirect",
    )
    diff_analyzer.export_diffs()
    diff_analyzer.export_disappearances()
    print("[OK] Archive diffs and disappearance log")

    from lobby_nl.validators import ValidationGuards
    guards = ValidationGuards()
    report = guards.validate_all(
        data["actors"], data["claims"], data["relationships"], data["sources"],
    )
    (output_dir / "validation_report.json").write_text(
        json.dumps({
            "is_valid": report.is_valid,
            "errors": report.errors,
            "warnings": report.warnings,
            "info": report.info,
        }, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(report.summary())

    audit_log = f"""# Audit Log - Lobby NL OSINT Research Pipeline (Sample Run)

Generated: {datetime.now(timezone.utc).isoformat()}

## Sample Data
This is a sample run with simulated data representing the pipeline's structure.
Real data would be collected from actual public sources.

## Actors ({len(data['actors'])})
- CIDI (pro_israel_org) + spokesperson
- NCAB/NIDA (antisemitism_policy_infrastructure)
- Christenen voor Israël (christian_zionist_org) + spokesperson
- Centraal Joods Overleg (jewish_civic_org)
- Palestina Komitee (palestine_rights_counter_lobby)
- De Volkskrant (media_actor)
- TK Commissie BZ (committee_actor)
- Min. van Buitenlandse Zaken (ministry_actor)
- Politie Eenheid Den Haag (police_actor)
- Ambassade van Israël (israeli_diplomatic_channel)

## Claims ({len(data['claims'])})
5 claims across 5 actors with source backing

## Relationships ({len(data['relationships'])})
9 relationships with source backing

## Data Gaps ({len(data['data_gaps'])})
- Funding opacity (CIDI, CVI)
- Structural: no mandatory lobby register in NL

## Quality Gates Status
- Actors with source backing: ALL
- Claims with source_id: ALL
- Relationships with source_ids: ALL
"""
    (reports_dir / "audit_log.md").write_text(audit_log, encoding="utf-8")
    print(f"[OK] Audit log -> {reports_dir / 'audit_log.md'}")

    print("\n" + "=" * 60)
    print("SAMPLE RUN COMPLETE")
    print(f"Outputs: {output_dir}")
    print(f"Reports: {reports_dir}")
    for f in sorted(output_dir.glob("*.csv")) + sorted(output_dir.glob("*.json")):
        print(f"  {f.name}")
    for f in sorted(reports_dir.glob("*")):
        print(f"  {f.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
