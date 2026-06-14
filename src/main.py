"""Main CLI entry point for Lobby NL OSINT Pipeline.

Usage:
    python -m src.main init            Initialize project structure
    python -m src.main collect         Run data collectors
    python -m src.main extract         Run entity extractors
    python -m src.main classify        Run actor classification
    python -m src.main validate        Run validation guards
    python -m src.main export          Run all exports
    python -m src.main report          Generate research report
    python -m src.main run-all         Run the complete pipeline
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="lobby-nl",
    help="Evidence-first OSINT research pipeline for Dutch lobbying practices.",
    no_args_is_help=True,
)


def _resolve_output_dir(output: Optional[Path] = None) -> Path:
    d = output or Path("data/processed")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve_reports_dir() -> Path:
    d = Path("reports")
    d.mkdir(parents=True, exist_ok=True)
    return d


@app.command()
def init(
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Initialize project directory structure.

    Creates: config/, data/input/, data/raw/, data/interim/, data/processed/, exports/, reports/
    Writes template seed files if they don't exist.
    """
    dirs = [
        "config",
        "data/input",
        "data/raw",
        "data/interim",
        "data/processed",
        "exports",
        "reports",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        typer.echo(f"  [OK] {d}/")

    seed_actors = Path("data/input/manual_seeds.csv")
    if not seed_actors.exists():
        seed_actors.write_text("actor_id,name,category,description,source_id,url,notes\n", encoding="utf-8")
        typer.echo(f"  [OK] {seed_actors}")

    seed_queries = Path("data/input/seed_queries.csv")
    if not seed_queries.exists():
        seed_queries.write_text("query_id,query,language,category,source,date_added\n", encoding="utf-8")
        typer.echo(f"  [OK] {seed_queries}")

    typer.echo("\n[OK] Project initialized. Run 'python -m src.main collect' next.")


@app.command()
def collect(
    config_file: Optional[Path] = typer.Option(
        Path("config/sources.yaml"), help="Path to sources YAML config"
    ),
    urls_file: Optional[Path] = typer.Option(None, help="Alternative: JSON file with URLs"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
    max_depth: int = typer.Option(1, help="Max crawl depth for linked pages"),
) -> None:
    """Collect data from web sources, parliamentary records, and EU register."""
    import yaml

    from lobby_nl.collectors import WebCollector, ArchiveCollector

    out_dir = _resolve_output_dir(output)
    raw_dir = Path("data/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)

    web = WebCollector(output_dir=raw_dir)
    archive = ArchiveCollector(output_dir=raw_dir)

    sources: list = []

    if urls_file and urls_file.exists():
        data = json.loads(urls_file.read_text(encoding="utf-8"))
        urls = data if isinstance(data, list) else data.get("urls", [])
        typer.echo(f"[INFO] Collecting {len(urls)} URLs from {urls_file}...")
        for url in urls:
            page_sources = web.collect_urls([url])
            sources.extend(page_sources)
    elif config_file and config_file.exists():
        cfg = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        all_urls: list[dict] = []
        for section_key, section_val in cfg.items():
            if isinstance(section_val, list):
                for entry in section_val:
                    if isinstance(entry, dict) and "url" in entry:
                        all_urls.append(entry)

        typer.echo(f"[INFO] Collecting {len(all_urls)} URLs from {config_file}...")
        for entry in all_urls:
            url = entry["url"]
            page_sources = web.collect_urls([url])
            for src in page_sources:
                src.metadata["config_section"] = entry.get("category", "")
                src.metadata["config_name"] = entry.get("name", "")
            sources.extend(page_sources)
    else:
        typer.echo(
            "[WARN] No config file found. Use --config-file or --urls-file.",
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(f"[INFO] Checking archives for {len(sources)} sources...")
    for src in sources:
        if src.url and not src.is_dead:
            archive_url = archive.check_archive(src.url)
            if archive_url:
                src.archive_url = archive_url
                src.archive_available = True

    all_data = {
        "sources": [s.model_dump() for s in sources],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(sources),
    }
    output_path = out_dir / "collected_data.json"
    output_path.write_text(
        json.dumps(all_data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    typer.echo(f"[OK] Collected {len(sources)} sources -> {output_path}")


@app.command()
def extract(
    input_file: Path = typer.Argument(..., help="JSON file with collected sources"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Extract actors, relationships, and claims from collected sources."""
    from lobby_nl.extractors import ActorExtractor, ClaimExtractor, RelationshipExtractor, MediaFramingExtractor
    from lobby_nl.models import Actor, Claim, Relationship, Source
    from lobby_nl.utils import compute_content_hash

    import pandas as pd

    out_dir = _resolve_output_dir(output)
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
            claims.append(Claim(**fc))

        found_rels = rel_extractor.extract_relationships(src.content_text or "", actors)
        for fr in found_rels:
            try:
                rel = Relationship(**fr)
                rel.source_ids = [src.source_id]
                relationships.append(rel)
            except Exception:
                pass

    framing_extractor = MediaFramingExtractor()
    framing_results = framing_extractor.extract_batch(sources, actors)
    if framing_results:
        exports_dir = Path("exports")
        exports_dir.mkdir(parents=True, exist_ok=True)
        framing_path = exports_dir / "media_framing_log.csv"
        pd.DataFrame(framing_results).to_csv(framing_path, index=False)
        typer.echo(f"[OK] Media framing patterns: {len(framing_results)} -> {framing_path}")

    all_data = {
        "actors": [a.model_dump() for a in actors],
        "claims": [c.model_dump() for c in claims],
        "relationships": [r.model_dump() for r in relationships],
        "sources": [s.model_dump() for s in sources],
        "media_framing": framing_results,
    }
    output_path = out_dir / "extracted_data.json"
    output_path.write_text(
        json.dumps(all_data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    typer.echo(
        f"[OK] Extracted {len(actors)} actors, {len(claims)} claims, "
        f"{len(relationships)} relationships -> {output_path}"
    )


@app.command()
def classify(
    input_file: Path = typer.Argument(..., help="JSON file with extracted data"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Classify actors into correct categories."""
    from lobby_nl.classifiers import Classifier
    from lobby_nl.models import Actor, Claim, Relationship, Source

    out_dir = _resolve_output_dir(output)
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
    output_path.write_text(
        json.dumps(all_data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    typer.echo(f"[OK] Classified {len(actors)} actors -> {output_path}")


@app.command()
def validate(
    input_file: Path = typer.Argument(..., help="JSON file with classified data"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Run all validation guards on the data."""
    from lobby_nl.models import Actor, Claim, Relationship, Source
    from lobby_nl.validators import ValidationGuards

    out_dir = _resolve_output_dir(output)
    data = json.loads(input_file.read_text(encoding="utf-8"))

    actors = [Actor(**a) for a in data.get("actors", [])]
    claims = [Claim(**c) for c in data.get("claims", [])]
    relationships = [Relationship(**r) for r in data.get("relationships", [])]
    sources = [Source(**s) for s in data.get("sources", [])]

    guards = ValidationGuards()
    report = guards.validate_all(actors, claims, relationships, sources)

    report_path = out_dir / "validation_report.json"
    report_path.write_text(
        json.dumps(
            {
                "is_valid": report.is_valid,
                "errors": report.errors,
                "warnings": report.warnings,
                "info": report.info,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    typer.echo(report.summary())
    if report.errors:
        for e in report.errors:
            typer.secho(
                f"  ERROR: {e['entity_type']}[{e['entity_id']}]: {e['message']}",
                fg="red",
            )
    if report.warnings:
        for w in report.warnings[:10]:
            typer.secho(
                f"  WARN: {w['entity_type']}[{w['entity_id']}]: {w['message']}",
                fg="yellow",
            )
    typer.echo(f"[OK] Validation report -> {report_path}")


@app.command()
def export(
    input_file: Path = typer.Argument(..., help="JSON file with validated data"),
    output: Optional[Path] = typer.Option(None, help="Output directory for exports"),
) -> None:
    """Export all data to CSV, Gephi, OpenRefine, JSON, Neo4j, and HTML report."""
    from lobby_nl.exporters import (
        CSVExporter,
        GephiExporter,
        HTMLReportExporter,
        JSONExporter,
        Neo4jExporter,
        OpenRefineExporter,
    )
    from lobby_nl.models import (
        Actor,
        Claim,
        DataGap,
        Event,
        Exclusion,
        OpacitySignal,
        ParliamentaryRecord,
        Relationship,
        Source,
        SourceConflict,
    )

    out_dir = output or Path("exports")
    reports_dir = _resolve_reports_dir()
    data = json.loads(input_file.read_text(encoding="utf-8"))

    actors = [Actor(**a) for a in data.get("actors", [])]
    claims = [Claim(**c) for c in data.get("claims", [])]
    relationships = [Relationship(**r) for r in data.get("relationships", [])]
    sources = [Source(**s) for s in data.get("sources", [])]
    events = [Event(**e) for e in data.get("events", [])]
    parliamentary = [
        ParliamentaryRecord(**p) for p in data.get("parliamentary_records", [])
    ]
    data_gaps = [DataGap(**g) for g in data.get("data_gaps", [])]
    opacity_signals = [OpacitySignal(**o) for o in data.get("opacity_signals", [])]
    source_conflicts = [
        SourceConflict(**c) for c in data.get("source_conflicts", [])
    ]
    exclusions = [Exclusion(**e) for e in data.get("exclusions", [])]

    csv_exporter = CSVExporter(output_dir=out_dir)
    csv_files = csv_exporter.export_all(
        actors,
        claims,
        relationships,
        sources,
        events,
        parliamentary,
        data_gaps,
        opacity_signals,
        source_conflicts,
        exclusions,
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
        actors,
        claims,
        relationships,
        sources,
        events,
        data_gaps,
        opacity_signals,
        [],
        [],
    )
    typer.echo(f"[OK] HTML report -> {reports_dir}")


@app.command()
def report(
    input_file: Path = typer.Argument(..., help="JSON file with collected data"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Run media framing analysis and archive diff checks."""
    from lobby_nl.analysis import ArchiveDiffAnalyzer, MediaFramingAnalyzer
    from lobby_nl.collectors import ArchiveCollector
    from lobby_nl.models import Actor, Source

    out_dir = output or Path("exports")
    data = json.loads(input_file.read_text(encoding="utf-8"))

    actors = [Actor(**a) for a in data.get("actors", [])]
    sources = [Source(**s) for s in data.get("sources", [])]

    framing = MediaFramingAnalyzer(output_dir=out_dir)
    patterns = framing.analyze_sources(sources, actors)
    framing.export_framing_log()
    typer.echo(f"[OK] Detected {len(patterns)} framing patterns")

    import pandas as pd

    guesting = framing.detect_recurring_guesting(sources, actors)
    freq_guest_path = out_dir / "recurring_guesting.csv"
    pd.DataFrame(guesting).to_csv(freq_guest_path, index=False)
    typer.echo(f"[OK] Recurring guesting -> {freq_guest_path}")

    archive = ArchiveCollector(output_dir=Path("data/raw"))
    diff_analyzer = ArchiveDiffAnalyzer(output_dir=out_dir)
    for src in sources:
        if src.url and not src.is_dead:
            archive_url = archive.check_archive(src.url)
            if archive_url and src.content_text:
                archived_text = archive.fetch_archived_page(archive_url)
                if archived_text:
                    comparison = archive.compare_versions(
                        src.content_text, archived_text, src.url
                    )
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
def run_all(
    config_file: Optional[Path] = typer.Option(
        Path("config/sources.yaml"), help="Path to sources YAML config"
    ),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Run the complete pipeline: collect -> extract -> classify -> validate -> export -> report."""
    import tempfile

    out_dir = _resolve_output_dir(output)
    reports_dir = _resolve_reports_dir()

    typer.echo("=" * 60)
    typer.echo("LOBBY NL - OSINT RESEARCH PIPELINE")
    typer.echo(f"Started: {datetime.now(timezone.utc).isoformat()}")
    typer.echo("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        collected_path = tmp_path / "collected.json"
        typer.echo("\n[1/5] COLLECTING...")
        collect(config_file=config_file, output=tmp_path)

        extracted_path = tmp_path / "extracted.json"
        typer.echo("\n[2/5] EXTRACTING...")
        if collected_path.exists():
            extract(input_file=collected_path, output=tmp_path)

        classified_path = tmp_path / "classified.json"
        typer.echo("\n[3/5] CLASSIFYING & VALIDATING...")
        if extracted_path.exists():
            classify(input_file=extracted_path, output=tmp_path)
        elif collected_path.exists():
            classify(input_file=collected_path, output=tmp_path)

        if classified_path.exists():
            validate(input_file=classified_path, output=tmp_path)

        typer.echo("\n[4/5] EXPORTING...")
        src_path = classified_path if classified_path.exists() else extracted_path
        if src_path.exists():
            export(input_file=src_path, output=out_dir)

        typer.echo("\n[5/5] REPORTING...")
        if src_path.exists():
            report(input_file=src_path, output=out_dir)

    audit_log = f"""# Audit Log - Lobby NL OSINT Research Pipeline

Generated: {datetime.now(timezone.utc).isoformat()}

## Research Principles Applied
- Only public, source-verifiable information used
- No inference from religion, ethnicity, surname, origin, race
- Actors classified only from public function, activity, role
- Fact, interpretation, hypothesis, uncertainty, missingness, opacity risk separated
- Weak and light signals retained but explicitly labeled

## Config
- Sources config: {config_file}
- Output directory: {out_dir}
- Reports directory: {reports_dir}
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
