"""Export system for the OSINT research pipeline.

Exports ALL of these CSV files:

# HOOFD CATEGORIEEN (8 core clusters)
pro_israel_organisaties.csv
christenzionistische_organisaties.csv
joodse_maatschappelijke_organisaties.csv
israelische_diplomatieke_kanalen.csv
antisemitismebestrijding_infrastructuur.csv
parlementaire_netwerken.csv
tegenlobby_palestina_rechten.csv
eu_registers_nederlandse_actoren.csv

# MEDIA & JOURNALISTEN (11)
media_organisaties.csv, alternatieve_media.csv, journalisten_columnisten.csv,
presentatoren_talkshows.csv, podcasts_nieuwsbulletins.csv, nieuwsbrief_auteurs.csv,
influencers_social_media.csv, opiniemakers_activisten.csv,
public_broadcaster_actors.csv, media_framing_log.csv, platform_presence_log.csv

# POLITIEK & OVERHEID (11)
politieke_partijen.csv, eerste_kamer_leden.csv, tweede_kamer_leden.csv,
kamer_commissies_delegaties.csv, ministeries_departementen.csv,
uitvoeringsorganisaties.csv, gemeenten_municipal_actors.csv,
burgemeesters_mayors.csv, politie_veiligheid_actors.csv,
nctv_veiligheidsnetwerken.csv, semi_publieke_instellingen.csv

# PUBLIEKE FIGUREN & EXPERTS (8)
bekende_nederlanders_celebrities.csv, academici_universiteiten.csv,
denktanks_experts.csv, sprekers_conferentie_speakers.csv,
onderzoekers_research_centers.csv, consultants_adviseurs.csv,
experts_media_gasten.csv, diaspora_organisaties.csv

# FINANCIERING & LOBBY (5)
fondsen_donoren_sponsors.csv, grantmakers_stichtingen.csv,
lobby_firmen.csv, pr_bureaus.csv, advocatenkantoren_law_firms.csv

# EVENTS & PLATFORMS (3)
event_organisators.csv, venues_locaties.csv, events_and_venues.csv

# DATA QUALITY & TRANSPARANTIE (11)
cross_border_entities.csv, netherlands_relevance_matrix.csv,
archived_source_diffs.csv, source_disappearance_log.csv,
removed_or_dead_sources.csv, woo_followup_targets.csv,
source_conflicts.csv, exclusions.csv, uncertainty_log.csv,
missingness_report.csv, obstruction_risk_log.csv

# AANVULLENDE (9)
unverifiable_claims.csv, confidence_by_actor.csv,
confidence_by_relationship.csv, archive_comparison_log.csv,
actor_relationship_matrix.csv, power_mapping_matrix.csv,
influence_network_map.csv, network_clustering.csv, temporal_timeline.csv

# DATA EXPORTS (5)
gephi_nodes.csv, gephi_edges.csv, neo4j_import.cypher,
openrefine_actors.csv, openrefine_relationships.csv, openrefine_sources.csv
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import networkx as nx

from lobby_nl.models import (
    Actor,
    Claim,
    DataGap,
    EvidenceStrength,
    Event,
    Exclusion,
    OpacityMechanism,
    OpacitySignal,
    ParliamentaryRecord,
    Relationship,
    Source,
    SourceConflict,
)


def _to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj


def _flatten_list(v: Any) -> str:
    if isinstance(v, (list, tuple)):
        return "|".join(str(x) for x in v)
    return str(v) if v is not None else ""


class CSVExporter:
    """Exports data to CSV files with Dutch-named specialized lists."""

    def __init__(self, output_dir: Path = Path("exports")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _write_csv(
        self, filename: str, rows: list[dict[str, Any]], fieldnames: Optional[list[str]] = None
    ) -> Path:
        filepath = self.output_dir / filename
        if not rows:
            filepath.write_text("", encoding="utf-8")
            return filepath
        if fieldnames is None:
            fieldnames = list(rows[0].keys())
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return filepath

    def _filter_actors(self, actors: list[Actor], categories: list[str]) -> list[Actor]:
        return [
            a
            for a in actors
            if a.category.value in categories
            or any(sc.value in categories for sc in a.subcategories)
        ]

    # --- CORE EXPORTS ---

    def export_actors(self, actors: list[Actor]) -> Path:
        return self._write_csv("actors.csv", [_to_dict(a) for a in actors])

    def export_claims(self, claims: list[Claim]) -> Path:
        return self._write_csv("claims.csv", [_to_dict(c) for c in claims])

    def export_relationships(self, relationships: list[Relationship]) -> Path:
        rows = []
        for r in relationships:
            d = _to_dict(r)
            d["source_ids"] = json.dumps(d.get("source_ids", []))
            rows.append(d)
        return self._write_csv("relationships.csv", rows)

    def export_sources(self, sources: list[Source]) -> Path:
        return self._write_csv("sources.csv", [_to_dict(s) for s in sources])

    def export_events(self, events: list[Event]) -> Path:
        return self._write_csv("events.csv", [_to_dict(e) for e in events])

    def export_parliamentary_records(self, records: list[ParliamentaryRecord]) -> Path:
        return self._write_csv("parliamentary_records.csv", [_to_dict(r) for r in records])

    def export_data_gaps(self, gaps: list[DataGap]) -> Path:
        return self._write_csv("data_gaps.csv", [_to_dict(g) for g in gaps])

    def export_opacity_signals(self, signals: list[OpacitySignal]) -> Path:
        return self._write_csv("opacity_signals.csv", [_to_dict(s) for s in signals])

    def export_source_conflicts(self, conflicts: list[SourceConflict]) -> Path:
        return self._write_csv("source_conflicts.csv", [_to_dict(c) for c in conflicts])

    def export_exclusions(self, exclusions: list[Exclusion]) -> Path:
        return self._write_csv("exclusions.csv", [_to_dict(e) for e in exclusions])

    # --- HOOFD CATEGORIEEN ---

    def export_core_clusters(self, actors: list[Actor]) -> dict[str, Path]:
        cluster_map: dict[str, list[str]] = {
            "pro_israel_organisaties.csv": ["pro_israel_org"],
            "christenzionistische_organisaties.csv": ["christian_zionist_org"],
            "joodse_maatschappelijke_organisaties.csv": ["jewish_civic_org"],
            "israelische_diplomatieke_kanalen.csv": ["israeli_diplomatic_channel"],
            "antisemitismebestrijding_infrastructuur.csv": ["antisemitism_policy_infrastructure"],
            "parlementaire_netwerken.csv": ["parliamentary_actor"],
            "tegenlobby_palestina_rechten.csv": ["palestine_rights_counter_lobby"],
            "eu_registers_nederlandse_actoren.csv": ["eu_register_actor"],
        }
        results: dict[str, Path] = {}
        for filename, categories in cluster_map.items():
            filtered = self._filter_actors(actors, categories)
            results[filename] = self._write_csv(filename, [_to_dict(a) for a in filtered])
        return results

    # --- MEDIA & JOURNALISTEN ---

    def export_media_lists(self, actors: list[Actor]) -> dict[str, Path]:
        media_map: dict[str, list[str]] = {
            "media_organisaties.csv": ["media_actor", "media_framing_actor"],
            "alternatieve_media.csv": ["alternative_media_actor"],
            "journalisten_columnisten.csv": ["journalist_actor"],
            "presentatoren_talkshows.csv": ["talkshow_or_program_actor", "presenter_actor"],
            "podcasts_nieuwsbulletins.csv": ["podcast_actor"],
            "nieuwsbrief_auteurs.csv": ["newsletter_actor", "newsletter_author_actor"],
            "influencers_social_media.csv": ["influencer_actor", "social_platform_actor"],
            "opiniemakers_activisten.csv": ["campaign_actor", "opining_activist_actor"],
            "public_broadcaster_actors.csv": ["public_broadcaster_actor"],
            "platform_presence_log.csv": ["social_platform_actor", "platform_actor"],
        }
        results: dict[str, Path] = {}
        for filename, categories in media_map.items():
            filtered = self._filter_actors(actors, categories)
            results[filename] = self._write_csv(filename, [_to_dict(a) for a in filtered])
        return results

    # --- POLITIEK & OVERHEID ---

    def export_politics_lists(self, actors: list[Actor]) -> dict[str, Path]:
        politics_map: dict[str, list[str]] = {
            "politieke_partijen.csv": ["party_actor"],
            "eerste_kamer_leden.csv": ["senate_actor"],
            "tweede_kamer_leden.csv": ["house_actor"],
            "kamer_commissies_delegaties.csv": ["committee_actor", "parliamentary_actor"],
            "ministeries_departementen.csv": ["ministry_actor", "government_actor", "department_actor"],
            "uitvoeringsorganisaties.csv": ["government_actor", "department_actor", "implementation_org_actor"],
            "gemeenten_municipal_actors.csv": ["municipal_actor"],
            "burgemeesters_mayors.csv": ["mayor_actor"],
            "politie_veiligheid_actors.csv": ["police_actor", "security_actor"],
            "nctv_veiligheidsnetwerken.csv": ["security_actor", "nctv_actor"],
            "semi_publieke_instellingen.csv": ["education_actor", "semi_government_actor"],
        }
        results: dict[str, Path] = {}
        for filename, categories in politics_map.items():
            filtered = self._filter_actors(actors, categories)
            results[filename] = self._write_csv(filename, [_to_dict(a) for a in filtered])
        return results

    # --- PUBLIEKE FIGUREN & EXPERTS ---

    def export_figures_lists(self, actors: list[Actor]) -> dict[str, Path]:
        figures_map: dict[str, list[str]] = {
            "bekende_nederlanders_celebrities.csv": ["celebrity_actor"],
            "academici_universiteiten.csv": ["academic_actor", "education_actor", "researcher_actor"],
            "denktanks_experts.csv": ["think_tank_actor"],
            "sprekers_conferentie_speakers.csv": ["celebrity_actor", "academic_actor", "speaker_event_actor"],
            "onderzoekers_research_centers.csv": ["research_actor", "researcher_actor", "academic_actor"],
            "consultants_adviseurs.csv": ["pr_or_consultancy_actor", "consultant_advisor_actor"],
            "experts_media_gasten.csv": ["academic_actor", "think_tank_actor", "journalist_actor", "expert_media_guest_actor"],
            "diaspora_organisaties.csv": ["diaspora_actor"],
        }
        results: dict[str, Path] = {}
        for filename, categories in figures_map.items():
            filtered = self._filter_actors(actors, categories)
            results[filename] = self._write_csv(filename, [_to_dict(a) for a in filtered])
        return results

    # --- FINANCIERING & LOBBY ---

    def export_finance_lists(self, actors: list[Actor]) -> dict[str, Path]:
        finance_map: dict[str, list[str]] = {
            "fondsen_donoren_sponsors.csv": ["funding_actor", "donor_actor", "sponsor_actor"],
            "grantmakers_stichtingen.csv": ["funding_actor", "grantmaker_actor", "foundation_actor"],
            "lobby_firmen.csv": ["pr_or_consultancy_actor", "lobbying_firm_actor"],
            "pr_bureaus.csv": ["pr_or_consultancy_actor", "pr_firm_actor"],
            "advocatenkantoren_law_firms.csv": ["law_firm_actor"],
        }
        results: dict[str, Path] = {}
        for filename, categories in finance_map.items():
            filtered = self._filter_actors(actors, categories)
            results[filename] = self._write_csv(filename, [_to_dict(a) for a in filtered])
        return results

    # --- EVENTS & PLATFORMS ---

    def export_event_lists(self, actors: list[Actor], events: list[Event]) -> dict[str, Path]:
        event_organizers = self._filter_actors(actors, ["event_platform_actor", "event_organizer_actor"])
        results: dict[str, Path] = {}
        results["event_organisators.csv"] = self._write_csv(
            "event_organisators.csv", [_to_dict(a) for a in event_organizers]
        )
        venues_rows = [
            {"venue_name": e.venue_name, "location": e.location, "city": e.city, "event_id": e.event_id}
            for e in events
            if e.venue_name
        ]
        results["venues_locaties.csv"] = self._write_csv("venues_locaties.csv", venues_rows)
        results["events_and_venues.csv"] = self._write_csv(
            "events_and_venues.csv", [_to_dict(e) for e in events]
        )
        return results

    # --- DATA QUALITY & TRANSPARANTIE ---

    def export_quality_lists(
        self,
        actors: list[Actor],
        claims: list[Claim],
        relationships: list[Relationship],
        sources: list[Source],
        data_gaps: list[DataGap],
        opacity_signals: list[OpacitySignal],
        source_conflicts: list[SourceConflict],
        exclusions: list[Exclusion],
    ) -> dict[str, Path]:
        results: dict[str, Path] = {}

        cross_border = [
            a for a in actors
            if a.country != "NL"
            or "NL" not in a.countries_active
            or len(a.countries_active) > 1
        ]
        results["cross_border_entities.csv"] = self._write_csv(
            "cross_border_entities.csv", [_to_dict(a) for a in cross_border]
        )

        relevance_rows = []
        for a in actors:
            relevance_rows.append({
                "actor_id": a.actor_id,
                "name": a.name,
                "category": a.category.value,
                "country": a.country,
                "source_count": len(a.source_ids),
                "relationship_count": a.relationship_count,
                "confidence": a.confidence,
                "is_dutch": a.is_dutch,
                "is_active": a.is_active,
            })
        results["netherlands_relevance_matrix.csv"] = self._write_csv(
            "netherlands_relevance_matrix.csv", relevance_rows
        )

        dead_sources = [s for s in sources if s.is_dead or s.is_stale]
        results["removed_or_dead_sources.csv"] = self._write_csv(
            "removed_or_dead_sources.csv",
            [_to_dict(s) for s in dead_sources],
        )

        woo_targets_rows = [
            {
                "gap_id": g.gap_id,
                "description": g.description,
                "affected_actor_ids": _flatten_list(g.affected_actor_ids),
                "follow_up": True,
            }
            for g in data_gaps
            if any(
                m in (OpacityMechanism.partial_disclosure, OpacityMechanism.institutional_non_response)
                for m in g.opacity_mechanisms
            )
        ]
        results["woo_followup_targets.csv"] = self._write_csv(
            "woo_followup_targets.csv", woo_targets_rows
        )

        results["source_conflicts.csv"] = self._write_csv(
            "source_conflicts.csv", [_to_dict(c) for c in source_conflicts]
        )
        results["exclusions.csv"] = self._write_csv(
            "exclusions.csv", [_to_dict(e) for e in exclusions]
        )

        uncertainty_rows = []
        for entity_list, entity_type in [
            (actors, "actor"),
            (claims, "claim"),
            (relationships, "relationship"),
        ]:
            for e in entity_list:
                c = getattr(e, "certainty", None)
                if c and c.value in ("uncertainty", "hypothesis", "missingness", "opacity_risk"):
                    uncertainty_rows.append({
                        "entity_type": entity_type,
                        "entity_id": getattr(e, f"{entity_type}_id", ""),
                        "certainty": c.value,
                        "name": getattr(e, "name", getattr(e, "claim_text", ""))[:200],
                    })
        results["uncertainty_log.csv"] = self._write_csv("uncertainty_log.csv", uncertainty_rows)

        results["missingness_report.csv"] = self._write_csv(
            "missingness_report.csv", [_to_dict(g) for g in data_gaps]
        )

        obstruction_rows = []
        for s in opacity_signals:
            obstruction_rows.append({
                "signal_id": s.signal_id,
                "signal_type": s.signal_type.value,
                "description": s.description,
                "actor_ids": _flatten_list(s.actor_ids),
                "evidence_strength": s.evidence_strength.value,
                "certainty": s.certainty.value,
                "alternative_explanation": s.alternative_explanation,
            })
        results["obstruction_risk_log.csv"] = self._write_csv(
            "obstruction_risk_log.csv", obstruction_rows
        )

        return results

    # --- AANVULLENDE ---

    def export_supplemental_lists(
        self,
        actors: list[Actor],
        claims: list[Claim],
        relationships: list[Relationship],
        sources: list[Source],
        events: list[Event],
    ) -> dict[str, Path]:
        results: dict[str, Path] = {}

        unverifiable_c = [c for c in claims if c.evidence_strength in (EvidenceStrength.weak, EvidenceStrength.light)]
        results["unverifiable_claims.csv"] = self._write_csv(
            "unverifiable_claims.csv", [_to_dict(c) for c in unverifiable_c]
        )

        confidence_actors = [
            {"actor_id": a.actor_id, "name": a.name, "category": a.category.value, "confidence": a.confidence}
            for a in actors
        ]
        results["confidence_by_actor.csv"] = self._write_csv(
            "confidence_by_actor.csv", confidence_actors
        )

        confidence_rels = [
            {
                "relationship_id": r.relationship_id,
                "actor_a_id": r.actor_a_id,
                "actor_b_id": r.actor_b_id,
                "type": r.relationship_type.value,
                "weight": r.weight,
                "evidence_strength": r.evidence_strength.value,
            }
            for r in relationships
        ]
        results["confidence_by_relationship.csv"] = self._write_csv(
            "confidence_by_relationship.csv", confidence_rels
        )

        archive_comparisons = []
        for s in sources:
            if s.archive_available and s.archive_url:
                archive_comparisons.append({
                    "url": s.url,
                    "archive_url": s.archive_url,
                    "content_hash": s.content_hash or "",
                    "is_dead": s.is_dead,
                    "is_changed": s.is_changed,
                })
        results["archive_comparison_log.csv"] = self._write_csv(
            "archive_comparison_log.csv", archive_comparisons
        )

        actor_ids = {a.actor_id for a in actors}
        actor_name_lookup = {a.actor_id: a.name for a in actors}
        matrix_rows = []
        for a_id in sorted(actor_ids):
            row: dict[str, str] = {"actor_id": a_id}
            for b_id in sorted(actor_ids):
                if a_id == b_id:
                    row[b_id] = "0"
                else:
                    connected = any(
                        (r.actor_a_id == a_id and r.actor_b_id == b_id)
                        or (r.actor_a_id == b_id and r.actor_b_id == a_id)
                        for r in relationships
                    )
                    row[b_id] = "1" if connected else "0"
            matrix_rows.append(row)
        results["actor_relationship_matrix.csv"] = self._write_csv(
            "actor_relationship_matrix.csv", matrix_rows
        )

        graph = nx.Graph()
        for r in relationships:
            graph.add_edge(r.actor_a_id, r.actor_b_id, weight=r.weight)
        centrality = nx.degree_centrality(graph) if graph.nodes else {}
        power_rows = []
        for a_id, cent in sorted(centrality.items(), key=lambda x: x[1], reverse=True):
            power_rows.append({
                "actor_id": a_id,
                "name": actor_name_lookup.get(a_id, ""),
                "centrality": cent,
                "degree": graph.degree(a_id) if a_id in graph else 0,
            })
        results["power_mapping_matrix.csv"] = self._write_csv("power_mapping_matrix.csv", power_rows)

        influence_rows = []
        for r in relationships:
            influence_rows.append({
                "source": r.actor_a_id,
                "target": r.actor_b_id,
                "weight": r.weight,
                "type": r.relationship_type.value,
            })
        results["influence_network_map.csv"] = self._write_csv(
            "influence_network_map.csv", influence_rows
        )

        clusters: dict[str, list[str]] = {}
        if graph.nodes:
            try:
                from networkx.algorithms.community import greedy_modularity_communities
                communities = greedy_modularity_communities(graph)
                for i, comm in enumerate(communities):
                    clusters[f"cluster_{i}"] = list(comm)
            except Exception:
                pass
        cluster_rows = []
        for cluster_name, members in clusters.items():
            for member in members:
                cluster_rows.append({
                    "cluster": cluster_name,
                    "actor_id": member,
                    "actor_name": actor_name_lookup.get(member, ""),
                })
        results["network_clustering.csv"] = self._write_csv("network_clustering.csv", cluster_rows)

        timeline_rows = []
        for e in events:
            timeline_rows.append({
                "date": e.date,
                "event_type": e.event_type,
                "name": e.name,
                "entity_type": "event",
                "entity_id": e.event_id,
            })
        for c in claims:
            if c.date:
                timeline_rows.append({
                    "date": c.date,
                    "event_type": "claim",
                    "name": c.claim_text[:200],
                    "entity_type": "claim",
                    "entity_id": c.claim_id,
                })
        results["temporal_timeline.csv"] = self._write_csv("temporal_timeline.csv", timeline_rows)

        return results

    # --- FULL EXPORT ---

    def export_all(
        self,
        actors: list[Actor],
        claims: list[Claim],
        relationships: list[Relationship],
        sources: list[Source],
        events: list[Event],
        parliamentary_records: list[ParliamentaryRecord],
        data_gaps: list[DataGap],
        opacity_signals: list[OpacitySignal],
        source_conflicts: list[SourceConflict],
        exclusions: list[Exclusion],
    ) -> dict[str, Path]:
        files: dict[str, Path] = {}
        files["actors.csv"] = self.export_actors(actors)
        files["claims.csv"] = self.export_claims(claims)
        files["relationships.csv"] = self.export_relationships(relationships)
        files["sources.csv"] = self.export_sources(sources)
        files["events.csv"] = self.export_events(events)
        files["parliamentary_records.csv"] = self.export_parliamentary_records(parliamentary_records)
        files["data_gaps.csv"] = self.export_data_gaps(data_gaps)
        files["opacity_signals.csv"] = self.export_opacity_signals(opacity_signals)
        files["source_conflicts.csv"] = self.export_source_conflicts(source_conflicts)
        files["exclusions.csv"] = self.export_exclusions(exclusions)
        files.update(self.export_core_clusters(actors))
        files.update(self.export_media_lists(actors))
        files.update(self.export_politics_lists(actors))
        files.update(self.export_figures_lists(actors))
        files.update(self.export_finance_lists(actors))
        files.update(self.export_event_lists(actors, events))
        files.update(
            self.export_quality_lists(
                actors, claims, relationships, sources,
                data_gaps, opacity_signals, source_conflicts, exclusions,
            )
        )
        files.update(self.export_supplemental_lists(actors, claims, relationships, sources, events))
        return files


class GephiExporter:
    """Exports network data in Gephi-compatible format."""

    def __init__(self, output_dir: Path = Path("exports")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_nodes(self, actors: list[Actor]) -> Path:
        nodes = []
        for a in actors:
            nodes.append({
                "Id": a.actor_id,
                "Label": a.name,
                "Category": a.category.value,
                "Type": "person" if a.is_person else "organization",
                "Country": a.country,
                "Confidence": a.confidence,
            })
        filepath = self.output_dir / "gephi_nodes.csv"
        pd.DataFrame(nodes).to_csv(filepath, index=False)
        return filepath

    def export_edges(self, relationships: list[Relationship]) -> Path:
        edges = []
        for r in relationships:
            edges.append({
                "Source": r.actor_a_id,
                "Target": r.actor_b_id,
                "Type": r.relationship_type.value,
                "Weight": r.weight,
                "Evidence": r.evidence_strength.value,
                "Direction": r.direction,
            })
        filepath = self.output_dir / "gephi_edges.csv"
        pd.DataFrame(edges).to_csv(filepath, index=False)
        return filepath


class Neo4jExporter:
    """Exports data as Neo4j Cypher import file."""

    def __init__(self, output_dir: Path = Path("exports")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_cypher(self, actors: list[Actor], relationships: list[Relationship]) -> Path:
        lines = ["// Neo4j import script - Lobby NL OSINT Pipeline"]
        lines.append(f"// Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append("")
        lines.append("// Create actors")
        for a in actors:
            name_escaped = a.name.replace("'", "\\'")
            lines.append(
                f"CREATE (a:{a.actor_id} {{name: '{name_escaped}', "
                f"category: '{a.category.value}', "
                f"confidence: {a.confidence}, "
                f"country: '{a.country}'}});"
            )
        lines.append("")
        lines.append("// Create relationships")
        for r in relationships:
            lines.append(
                f"MATCH (a:{r.actor_a_id}), (b:{r.actor_b_id}) "
                f"CREATE (a)-[:{r.relationship_type.value} {{weight: {r.weight}, "
                f"evidence: '{r.evidence_strength.value}'}}]->(b);"
            )
        filepath = self.output_dir / "neo4j_import.cypher"
        filepath.write_text("\n".join(lines), encoding="utf-8")
        return filepath


class OpenRefineExporter:
    """Exports data in OpenRefine-compatible format (separate files)."""

    def __init__(self, output_dir: Path = Path("exports")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_actors(self, actors: list[Actor]) -> Path:
        rows = []
        for a in actors:
            d = _to_dict(a)
            d["_entity_type"] = "actor"
            rows.append(d)
        filepath = self.output_dir / "openrefine_actors.csv"
        if rows:
            pd.DataFrame(rows).to_csv(filepath, index=False)
        return filepath

    def export_relationships(self, relationships: list[Relationship]) -> Path:
        rows = []
        for r in relationships:
            d = _to_dict(r)
            d["_entity_type"] = "relationship"
            d["source_ids"] = json.dumps(d.get("source_ids", []))
            rows.append(d)
        filepath = self.output_dir / "openrefine_relationships.csv"
        if rows:
            pd.DataFrame(rows).to_csv(filepath, index=False)
        return filepath

    def export_sources(self, sources: list[Source]) -> Path:
        rows = []
        for s in sources:
            d = _to_dict(s)
            d["_entity_type"] = "source"
            rows.append(d)
        filepath = self.output_dir / "openrefine_sources.csv"
        if rows:
            pd.DataFrame(rows).to_csv(filepath, index=False)
        return filepath


class JSONExporter:
    """Exports the full evidence graph as JSON."""

    def __init__(self, output_dir: Path = Path("exports")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_evidence_graph(
        self,
        actors: list[Actor],
        claims: list[Claim],
        relationships: list[Relationship],
        sources: list[Source],
        events: list[Event],
    ) -> Path:
        graph = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "pipeline_version": "1.0.0",
                "actor_count": len(actors),
                "claim_count": len(claims),
                "relationship_count": len(relationships),
                "source_count": len(sources),
                "event_count": len(events),
            },
            "actors": [_to_dict(a) for a in actors],
            "claims": [_to_dict(c) for c in claims],
            "relationships": [_to_dict(r) for r in relationships],
            "sources": [_to_dict(s) for s in sources],
            "events": [_to_dict(e) for e in events],
        }
        filepath = self.output_dir / "evidence_graph.json"
        filepath.write_text(
            json.dumps(graph, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        return filepath


class HTMLReportExporter:
    """Generates HTML summary report."""

    def __init__(self, output_dir: Path = Path("reports")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        actors: list[Actor],
        claims: list[Claim],
        relationships: list[Relationship],
        sources: list[Source],
        events: list[Event],
        data_gaps: list[DataGap],
        opacity_signals: list[OpacitySignal],
        validation_errors: list[dict[str, Any]],
        validation_warnings: list[dict[str, Any]],
    ) -> Path:
        category_counts: dict[str, int] = {}
        for a in actors:
            cat = a.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        evidence_strength_counts: dict[str, int] = {}
        for c in claims:
            es = c.evidence_strength.value
            evidence_strength_counts[es] = evidence_strength_counts.get(es, 0) + 1

        dead_sources = [s for s in sources if s.is_dead]
        stale_sources = [s for s in sources if s.is_stale]

        html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>Lobby NL - OSINT Research Report</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #f5f5f5; }}
.warning {{ background: #fff3cd; }}
.error {{ background: #f8d7da; }}
.section {{ margin: 30px 0; }}
</style>
</head>
<body>
<h1>Lobby NL - OSINT Research Pipeline Report</h1>
<p>Gegenereerd: {datetime.now(timezone.utc).isoformat()}</p>

<div class="section">
<h2>Samenvatting</h2>
<table>
<tr><td>Totaal Actoren</td><td>{len(actors)}</td></tr>
<tr><td>Totaal Claims</td><td>{len(claims)}</td></tr>
<tr><td>Totaal Relaties</td><td>{len(relationships)}</td></tr>
<tr><td>Totaal Bronnen</td><td>{len(sources)}</td></tr>
<tr><td>Totaal Events</td><td>{len(events)}</td></tr>
<tr><td>Data Gaps</td><td>{len(data_gaps)}</td></tr>
<tr><td>Opacity Signals</td><td>{len(opacity_signals)}</td></tr>
<tr><td>Dode Bronnen</td><td>{len(dead_sources)}</td></tr>
<tr><td>Verouderde Bronnen</td><td>{len(stale_sources)}</td></tr>
</table>
</div>

<div class="section">
<h2>Acteur Categorieen</h2>
<table>
<tr><th>Categorie</th><th>Aantal</th></tr>
{"".join(f"<tr><td>{cat}</td><td>{count}</td></tr>" for cat, count in sorted(category_counts.items()))}
</table>
</div>

<div class="section">
<h2>Bewijs Sterkte Verdeling</h2>
<table>
<tr><th>Sterkte</th><th>Aantal</th></tr>
{"".join(f"<tr><td>{es}</td><td>{count}</td></tr>" for es, count in sorted(evidence_strength_counts.items()))}
</table>
</div>

<div class="section">
<h2>Dode/Verouderde Bronnen</h2>
<table>
<tr><th>URL</th><th>Type</th></tr>
{"".join(f"<tr class='error'><td>{s.url}</td><td>Dood</td></tr>" for s in dead_sources)}
{"".join(f"<tr class='warning'><td>{s.url}</td><td>Verouderd</td></tr>" for s in stale_sources)}
</table>
</div>

<div class="section">
<h2>Validatie Issues</h2>
<h3>Fouten ({len(validation_errors)})</h3>
{"".join(f"<p class='error'>{e['entity_type']}[{e['entity_id']}]: {e['message']}</p>" for e in validation_errors)}
<h3>Waarschuwingen ({len(validation_warnings)})</h3>
{"".join(f"<p class='warning'>{w['entity_type']}[{w['entity_id']}]: {w['message']}</p>" for w in validation_warnings)}
</div>

<div class="section">
<h2>Structurele Beperkingen (Nederland)</h2>
<ul>
<li>Geen algemeen verplicht lobbyregister</li>
<li>Parlementair lobbyregister = alleen toegangspas-bewijs</li>
<li>Ministeriele agendas kunnen onvolledig zijn</li>
<li>Woo-documenten kunnen vertraagd, geweigerd, of gefragmenteerd zijn</li>
<li>Invloed via zowel formele als informele kanalen</li>
<li>Publieke data verspreid over websites, Kamerstukken, PDFs, media, events, archieven</li>
</ul>
</div>

<div class="section">
<h2>Quality Gates</h2>
<ul>
<li>Elke acteur heeft minstens een source_id: {'OK' if all(len(a.source_ids) >= 1 for a in actors) else 'FOUT'}</li>
<li>Elke claim heeft source_id: {'OK' if all(c.source_id for c in claims) else 'FOUT'}</li>
<li>Elke relatie heeft source_id: {'OK' if all(len(r.source_ids) >= 1 for r in relationships) else 'FOUT'}</li>
</ul>
</div>

</body>
</html>"""
        filepath = self.output_dir / "research_report.html"
        filepath.write_text(html, encoding="utf-8")
        return filepath
