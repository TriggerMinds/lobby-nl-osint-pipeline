"""CLI for the Lobby NL OSINT Research Pipeline.

Usage:
    lobby-nl collect        Run data collectors
    lobby-nl extract        Run entity extractors
    lobby-nl classify       Run actor classification
    lobby-nl validate       Run validation guards
    lobby-nl export         Run all exports
    lobby-nl analyze        Run media framing analysis
    lobby-nl full-pipeline  Run the complete pipeline
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import typer

app = typer.Typer(
    name="lobby-nl",
    help="Evidence-first OSINT research pipeline for Dutch lobbying practices.",
    no_args_is_help=True,
)


def _get_output_dir() -> Path:
    return Path("exports")


def _get_reports_dir() -> Path:
    return Path("reports")


@app.command()
def collect(
    urls_file: Optional[Path] = typer.Option(None, help="JSON file with URLs to collect"),
    max_depth: int = typer.Option(1, help="Max crawl depth for linked pages"),
    output: Optional[Path] = typer.Option(None, help="Output directory for raw data"),
) -> None:
    """Collect data from web sources, parliamentary records, and EU register."""
    from lobby_nl.collectors import WebCollector, ArchiveCollector

    out_dir = output or _get_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    web = WebCollector(output_dir=out_dir / "raw")
    archive = ArchiveCollector(output_dir=out_dir / "raw")

    sources: list = []

    default_urls = [
        "https://www.cidi.nl/",
        "https://www.cjo.nl/",
        "https://www.nida.nl/",
        "https://www.christenenvoorisrael.nl/",
        "https://www.houseofrepresentatives.nl/",
        "https://www.eerstekamer.nl/",
        "https://www.rijksoverheid.nl/",
        "https://ec.europa.eu/transparencyregister/",
    ]

    urls = default_urls
    if urls_file and urls_file.exists():
        data = json.loads(urls_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            urls = data
        elif isinstance(data, dict) and "urls" in data:
            urls = data["urls"]

    print(f"[INFO] Collecting from {len(urls)} URLs (depth=domain-config)...")
    for url in urls:
        print(f"  Crawling: {url}")
        page_sources = web.collect_linked_pages(url, max_depth=None)
        sources.extend(page_sources)
        print(f"    -> {len(page_sources)} pages")

    print("[INFO] Checking archives for collected URLs...")
    for src in sources:
        if src.url and not src.is_dead:
            archive_url = archive.check_archive(src.url)
            if archive_url:
                src.archive_url = archive_url
                src.archive_available = True

    all_data = {
        "sources": [s.model_dump() for s in sources],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "url_count": len(urls),
        "opacity_signals": [s.model_dump() for s in web.opacity_signals],
    }
    output_path = out_dir / "collected_data.json"
    output_path.write_text(json.dumps(all_data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    typer.echo(f"[OK] Collected {len(sources)} sources -> {output_path}")


@app.command()
def extract(
    input_file: Path = typer.Argument(..., help="JSON file with collected sources"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Extract actors, relationships, and claims from collected sources."""
    from lobby_nl.extractors import ActorExtractor, ClaimExtractor, RelationshipExtractor
    from lobby_nl.models import Actor, Claim, Relationship, Source
    from lobby_nl.utils import compute_content_hash

    out_dir = output or _get_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(input_file.read_text(encoding="utf-8"))
    raw_sources = data.get("sources", [])

    actor_extractor = ActorExtractor()
    claim_extractor = ClaimExtractor()
    rel_extractor = RelationshipExtractor()

    actors: list[Actor] = []
    claims: list[Claim] = []
    relationships: list[Relationship] = []
    sources: list[Source] = []

    for raw in raw_sources:
        src = Source(**raw)
        if not src.content_hash and src.content_text:
            src.content_hash = compute_content_hash(src.content_text)
        sources.append(src)

    for src in sources:
        found_actors = actor_extractor.extract_actors_from_source(src)
        for name, category in found_actors:
            actor = Actor(
                name=name,
                category=category,
                source_ids=[src.source_id],
                description=f"Extracted from {src.url}",
            )
            actors.append(actor)

        found_claims = claim_extractor.extract_claims(src, [a.actor_id for a in actors])
        for fc in found_claims:
            claim = Claim(**fc)
            claims.append(claim)

        found_rels = rel_extractor.extract_relationships(src.content_text or "", actors)
        for fr in found_rels:
            try:
                rel = Relationship(**fr)
                rel.source_ids = [src.source_id]
                relationships.append(rel)
            except Exception:
                pass

    all_data = {
        "actors": [a.model_dump() for a in actors],
        "claims": [c.model_dump() for c in claims],
        "relationships": [r.model_dump() for r in relationships],
        "sources": [s.model_dump() for s in sources],
    }
    output_path = out_dir / "extracted_data.json"
    output_path.write_text(json.dumps(all_data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    typer.echo(f"[OK] Extracted {len(actors)} actors, {len(claims)} claims, {len(relationships)} relationships -> {output_path}")


@app.command()
def classify(
    input_file: Path = typer.Argument(..., help="JSON file with extracted data"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Classify actors into correct categories."""
    from lobby_nl.classifiers import Classifier
    from lobby_nl.models import Actor, Claim, Relationship, Source

    out_dir = output or _get_output_dir()
    data = json.loads(input_file.read_text(encoding="utf-8"))

    actors = [Actor(**a) for a in data.get("actors", [])]
    claims = [Claim(**c) for c in data.get("claims", [])]
    relationships = [Relationship(**r) for r in data.get("relationships", [])]
    sources = [Source(**s) for s in data.get("sources", [])]

    source_texts = {s.source_id: s.content_text for s in sources if s.content_text}

    classifier = Classifier()
    actors = classifier.classify_batch(actors, source_texts)

    all_data = {
        "actors": [a.model_dump() for a in actors],
        "claims": [c.model_dump() for c in claims],
        "relationships": [r.model_dump() for r in relationships],
        "sources": [s.model_dump() for s in sources],
    }
    output_path = out_dir / "classified_data.json"
    output_path.write_text(json.dumps(all_data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    typer.echo(f"[OK] Classified {len(actors)} actors -> {output_path}")


@app.command()
def validate(
    input_file: Path = typer.Argument(..., help="JSON file with classified data"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Run all validation guards on the data."""
    from lobby_nl.models import Actor, Claim, Relationship, Source
    from lobby_nl.validators import ValidationGuards

    out_dir = output or _get_output_dir()
    data = json.loads(input_file.read_text(encoding="utf-8"))

    actors = [Actor(**a) for a in data.get("actors", [])]
    claims = [Claim(**c) for c in data.get("claims", [])]
    relationships = [Relationship(**r) for r in data.get("relationships", [])]
    sources = [Source(**s) for s in data.get("sources", [])]

    guards = ValidationGuards()
    report = guards.validate_all(actors, claims, relationships, sources)

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "validation_report.json"
    report_path.write_text(json.dumps({
        "is_valid": report.is_valid,
        "errors": report.errors,
        "warnings": report.warnings,
        "info": report.info,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    typer.echo(report.summary())
    if report.errors:
        for e in report.errors:
            typer.secho(f"  ERROR: {e['entity_type']}[{e['entity_id']}]: {e['message']}", fg="red")
    if report.warnings:
        for w in report.warnings[:10]:
            typer.secho(f"  WARN: {w['entity_type']}[{w['entity_id']}]: {w['message']}", fg="yellow")
    typer.echo(f"[OK] Validation report -> {report_path}")


@app.command()
def export(
    input_file: Path = typer.Argument(..., help="JSON file with validated data"),
    output: Optional[Path] = typer.Option(None, help="Output directory for exports"),
) -> None:
    """Export all data to CSV, Gephi, OpenRefine, JSON, and HTML report."""
    from lobby_nl.exporters import (
        CSVExporter, GephiExporter, OpenRefineExporter, JSONExporter,
        HTMLReportExporter, Neo4jExporter,
    )
    from lobby_nl.models import Actor, Claim, DataGap, Event, Exclusion, OpacitySignal, ParliamentaryRecord, Relationship, Source, SourceConflict

    out_dir = output or _get_output_dir()
    reports_dir = _get_reports_dir()
    data = json.loads(input_file.read_text(encoding="utf-8"))

    actors = [Actor(**a) for a in data.get("actors", [])]
    claims = [Claim(**c) for c in data.get("claims", [])]
    relationships = [Relationship(**r) for r in data.get("relationships", [])]
    sources = [Source(**s) for s in data.get("sources", [])]
    events = [Event(**e) for e in data.get("events", [])]
    parliamentary = [ParliamentaryRecord(**p) for p in data.get("parliamentary_records", [])]
    data_gaps = [DataGap(**g) for g in data.get("data_gaps", [])]
    opacity_signals = [OpacitySignal(**o) for o in data.get("opacity_signals", [])]
    source_conflicts = [SourceConflict(**c) for c in data.get("source_conflicts", [])]
    exclusions = [Exclusion(**e) for e in data.get("exclusions", [])]

    csv_exporter = CSVExporter(output_dir=out_dir)
    csv_files = csv_exporter.export_all(
        actors, claims, relationships, sources, events,
        parliamentary, data_gaps, opacity_signals, source_conflicts, exclusions,
    )
    typer.echo(f"[OK] CSV exports ({len(csv_files)} files) -> {out_dir}")

    gephi = GephiExporter(output_dir=out_dir)
    gephi.export_nodes(actors)
    gephi.export_edges(relationships)
    typer.echo(f"[OK] Gephi exports -> {out_dir}")

    ore = OpenRefineExporter(output_dir=out_dir)
    ore.export_actors(actors)
    ore.export_relationships(relationships)
    ore.export_sources(sources)
    typer.echo(f"[OK] OpenRefine exports -> {out_dir}")

    neo = Neo4jExporter(output_dir=out_dir)
    neo.export_cypher(actors, relationships)
    typer.echo(f"[OK] Neo4j Cypher export -> {out_dir}")

    json_ex = JSONExporter(output_dir=out_dir)
    json_ex.export_evidence_graph(actors, claims, relationships, sources, events)
    typer.echo(f"[OK] JSON evidence graph -> {out_dir}")

    html_ex = HTMLReportExporter(output_dir=reports_dir)
    html_ex.generate_report(
        actors, claims, relationships, sources, events,
        data_gaps, opacity_signals, [], [],
    )
    typer.echo(f"[OK] HTML report -> {reports_dir}")


@app.command()
def analyze(
    input_file: Path = typer.Argument(..., help="JSON file with collected data"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Run media framing analysis and archive diff checks."""
    from lobby_nl.analysis import MediaFramingAnalyzer, ArchiveDiffAnalyzer
    from lobby_nl.collectors import ArchiveCollector
    from lobby_nl.models import Actor, Source

    out_dir = output or _get_output_dir()
    data = json.loads(input_file.read_text(encoding="utf-8"))

    actors = [Actor(**a) for a in data.get("actors", [])]
    sources = [Source(**s) for s in data.get("sources", [])]

    framing = MediaFramingAnalyzer(output_dir=out_dir)
    patterns = framing.analyze_sources(sources, actors)
    framing.export_framing_log()
    typer.echo(f"[OK] Detected {len(patterns)} framing patterns")

    guesting = framing.detect_recurring_guesting(sources, actors)
    freq_guest_path = out_dir / "recurring_guesting.csv"
    import pandas as pd
    pd.DataFrame(guesting).to_csv(freq_guest_path, index=False)
    typer.echo(f"[OK] Recurring guesting -> {freq_guest_path}")

    archive = ArchiveCollector(output_dir=out_dir / "raw")
    diff_analyzer = ArchiveDiffAnalyzer(output_dir=out_dir)
    for src in sources:
        if src.url and not src.is_dead:
            archive_url = archive.check_archive(src.url)
            if archive_url and src.content_text:
                archived_text = archive.fetch_archived_page(archive_url)
                if archived_text:
                    comparison = archive.compare_versions(src.content_text, archived_text, src.url)
                    diff_analyzer.log_diff(
                        src.url,
                        comparison["current_hash"],
                        comparison["archived_hash"],
                        comparison["diff_lines"],
                        comparison["changed"],
                    )
    diff_analyzer.export_diffs()
    diff_analyzer.export_disappearances()
    typer.echo(f"[OK] Archive diffs -> {out_dir}")


@app.command()
def full_pipeline(
    urls_file: Optional[Path] = typer.Option(None, help="JSON file with URLs to collect"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Run the complete pipeline: collect -> extract -> classify -> validate -> export -> analyze."""
    import tempfile
    import json as json_mod
    from datetime import datetime, timezone

    out_dir = output or _get_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = _get_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    typer.echo("=" * 60)
    typer.echo("LOBBY NL - OSINT RESEARCH PIPELINE")
    typer.echo("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        typer.echo("\n[1/6] COLLECTING...")
        collected_path = tmp_path / "collected_data.json"
        if urls_file:
            from lobby_nl.collectors import WebCollector, ArchiveCollector
            urls_data = json_mod.loads(urls_file.read_text(encoding="utf-8"))
            urls = urls_data if isinstance(urls_data, list) else urls_data.get("urls", [])
            web = WebCollector(output_dir=out_dir / "raw")
            archive = ArchiveCollector(output_dir=out_dir / "raw")
            sources = []

            # URLs per cluster
            cluster_urls = {
                "pro_israel": [
                    "https://www.cidi.nl/",
                    "https://www.nik.nl/",
                ],
                "christian_zionist": [
                    "https://www.christenenvoorisrael.nl/",
                    "https://www.cvi.nl/",
                ],
                "jewish_civic": [
                    "https://www.cjo.nl/",
                    "https://www.joods.nl/",
                ],
                "antisemitism_policy": [
                    "https://www.nida.nl/",
                    "https://www.rijksoverheid.nl/onderwerpen/antisemitisme",
                ],
                "palestine_rights": [
                    "https://www.palestina-komitee.nl/",
                    "https://www.docp.nl/",
                ],
                "parliamentary": [
                    "https://www.tweedekamer.nl/",
                    "https://www.eerstekamer.nl/",
                ],
                "media": [
                    "https://nos.nl/",
                    "https://www.volkskrant.nl/",
                    "https://www.nrc.nl/",
                ],
            }

            for cluster, cluster_urls_list in cluster_urls.items():
                typer.echo(f"  Cluster: {cluster} ({len(cluster_urls_list)} URLs, depth=domain-config)")
                for url in cluster_urls_list:
                    page_sources = web.collect_linked_pages(url, max_depth=None)
                    for src in page_sources:
                        if not src.is_dead:
                            archive_url = archive.check_archive(src.url)
                            if archive_url:
                                src.archive_url = archive_url
                                src.archive_available = True
                    sources.extend(page_sources)
                    typer.echo(f"    {url}: {len(page_sources)} pages")

            opacity_signals = [s.model_dump() for s in web.opacity_signals]
            if opacity_signals:
                typer.echo(f"  [OPACITY] {len(opacity_signals)} signal(s) logged")
                for sig in web.opacity_signals:
                    typer.echo(f"    - {sig.signal_type.value}: {sig.description[:100]}")

            all_data = {
                "sources": [s.model_dump() for s in sources],
                "url_count": len(urls),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "opacity_signals": opacity_signals,
            }
            collected_path.write_text(json_mod.dumps(all_data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        else:
            collect(urls_file=None, max_depth=1, output=tmp_path)

        typer.echo("\n[2/6] EXTRACTING...")
        extracted_path = tmp_path / "extracted.json"
        extract(input_file=collected_path, output=out_dir)
        from lobby_nl.collectors import WebCollector
        from lobby_nl.extractors import ActorExtractor, ClaimExtractor, RelationshipExtractor
        from lobby_nl.models import Actor, Claim, Relationship, Source
        from lobby_nl.utils import compute_content_hash

        if collected_path.exists():
            data = json_mod.loads(collected_path.read_text(encoding="utf-8"))
        else:
            data = {"sources": []}
        raw_sources = data.get("sources", [])
        actor_extractor = ActorExtractor()
        claim_extractor = ClaimExtractor()
        rel_extractor = RelationshipExtractor()
        actors: list[Actor] = []
        claims: list[Claim] = []
        relationships: list[Relationship] = []
        sources: list[Source] = []

        for raw in raw_sources:
            src = Source(**raw)
            if not src.content_hash and src.content_text:
                src.content_hash = compute_content_hash(src.content_text)
            sources.append(src)

        for src in sources:
            found_actors = actor_extractor.extract_actors_from_source(src)
            for name, category in found_actors:
                actor = Actor(name=name, category=category, source_ids=[src.source_id], description=f"Extracted from {src.url}")
                actors.append(actor)
            found_claims = claim_extractor.extract_claims(src, [a.actor_id for a in actors])
            for fc in found_claims:
                claims.append(Claim(**fc))
            found_rels = rel_extractor.extract_relationships(src.content_text or "", actors)
            for fr in found_rels:
                try:
                    rel = Relationship(**fr)
                    rel.source_ids = [src.source_id]
                    relationships.append(rel)
                except Exception:
                    pass

        all_data = {
            "actors": [a.model_dump() for a in actors],
            "claims": [c.model_dump() for c in claims],
            "relationships": [r.model_dump() for r in relationships],
            "sources": [s.model_dump() for s in sources],
        }
        extracted_path.write_text(json_mod.dumps(all_data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        typer.echo("\n[3/6] CLASSIFYING...")
        classified_path = tmp_path / "classified.json"
        classify(input_file=extracted_path if extracted_path.exists() else collected_path, output=out_dir)
        from lobby_nl.classifiers import Classifier
        classifier = Classifier()
        source_texts = {s.source_id: s.content_text for s in sources if s.content_text}
        actors = classifier.classify_batch(actors, source_texts)
        classified_data = {
            "actors": [a.model_dump() for a in actors],
            "claims": [c.model_dump() for c in claims],
            "relationships": [r.model_dump() for r in relationships],
            "sources": [s.model_dump() for s in sources],
        }
        classified_path.write_text(json_mod.dumps(classified_data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        typer.echo("\n[4/6] VALIDATING...")
        validate(input_file=classified_path, output=out_dir)

        typer.echo("\n[5/6] EXPORTING...")
        export(input_file=classified_path, output=out_dir)

        typer.echo("\n[6/6] ANALYZING...")
        analyze(input_file=classified_path, output=out_dir)

    audit_log = f"""# Audit Log - Lobby NL OSINT Research Pipeline

Generated: {datetime.now(timezone.utc).isoformat()}

## Research Principles Applied
- Only public, source-verifiable information used
- No inference from religion, ethnicity, surname, origin, race, or protected attributes
- Actors classified only from public function, public activity, public role, documented interaction
- Fact, interpretation, hypothesis, uncertainty, missingness, opacity risk, and exclusion separated
- Actors not omitted because politically sensitive or reputationally inconvenient
- Actors not included without public-source evidence
- Weak and light signals retained but explicitly labeled
- Lack of evidence not treated as lack of activity
- Lack of evidence not treated as proof of concealment

## Structural Limitations (Netherlands)
- No general mandatory Dutch lobby register
- Dutch parliamentary lobby register reflects access-pass evidence, not full lobbying activity
- Ministerial agendas are indicative and may be incomplete
- Woo records may be delayed, refused, redacted, fragmented, or jurisdictional
- Influence can occur through formal and informal channels
- Relevant public data split across websites, parliamentary records, PDFs, media, events, archives

## Opacity Mechanisms Monitored
- Hard-to-trace funding, intermediary structures, cross-border/offshore structures
- Link rot, source removal, archive disappearance, stale documents
- Legal complexity as delay mechanism, reputational pressure
- Delegitimization patterns, conflicting information, disinformation indicators
- Media-framing asymmetry, institutional non-response, partial disclosure

## Quality Gates
- Every actor must have at least one source_id
- Every claim must have source_id
- Every relationship must have source_id
- Every source must have access_date and content_hash where possible
- No person included from identity alone
- No organization classified from identity alone
- No Jewish civic actor auto-classified as lobby
- No antisemitism-policy actor auto-classified as Zionist
- Christian Zionist actors separated
- Diplomatic actors separated
- Counter-lobby actors included
- Light and weak signals retained and labeled
- Missingness logged as DataGap
- Archive checks attempted where possible

## Collector Adapters
- WebCollector: General web scraping (requests + BeautifulSoup)
- Fallback chain: requests → Playwright (JS rendering) → Crawl4AI (stealth, anti-bot)
- Domain-specific crawl depth via config/sources.yaml
- robots.txt respected; blocked paths logged as OpacitySignals
- Attempted alternative entry points (sitemap.xml, /nieuws, /publicaties) on robots.txt blocks
- ParliamentaryCollector: Tweede Kamer and Eerste Kamer search
- EURegisterCollector: EU Transparency Register search
- ArchiveCollector: Internet Archive Wayback Machine lookup
- Manual import path available for sources requiring authentication or limited access

## Assumptions
- Public sources may be incomplete. Data gaps are documented rather than silently filled.
- Placeholder adapters created for sources requiring interactive access (parliamentary APIs, Woo portals).
- Archive checks use Internet Archive; Dutch web archiving (KB) may require separate access.
- Media framing analysis uses keyword-based pattern detection and does not assert coordination.
"""
    audit_path = reports_dir / "audit_log.md"
    audit_path.write_text(audit_log, encoding="utf-8")
    typer.echo(f"\n[OK] Audit log -> {audit_path}")

    typer.echo("\n" + "=" * 60)
    typer.echo("PIPELINE COMPLETE")
    typer.echo(f"Outputs: {out_dir}")
    typer.echo(f"Reports: {reports_dir}")
    typer.echo("=" * 60)


if __name__ == "__main__":
    app()
