# AGENTS.md - Lobby NL OSINT Research Pipeline

## Project Overview

Evidence-first, source-verifiable OSINT pipeline for mapping lobbying practices in the Netherlands. The pipeline collects, extracts, classifies, validates, and exports structured data about actors, claims, relationships, events, and parliamentary records.

## Architecture

```
src/lobby_nl/
├── models/          # Pydantic data models (Actor, Claim, Relationship, Source, etc.)
├── collectors/      # Data collection (web, parliamentary, EU register, archive)
├── extractors/      # Entity extraction from source text
├── classifiers/     # Actor category classification with identity guards
├── validators/      # 8 validation guards
├── exporters/       # CSV, Gephi, OpenRefine, JSON, HTML exports
├── analysis/        # Media framing, archive diff analysis
├── cli/             # Typer CLI (main.py = entry point)
└── utils.py         # Shared utilities
```

## Key Commands

```bash
# Install
pip install -e .
playwright install chromium

# Run full pipeline
lobby-nl full-pipeline

# Individual steps
lobby-nl collect --urls-file urls.json
lobby-nl extract exports/collected_data.json
lobby-nl classify exports/extracted_data.json
lobby-nl validate exports/classified_data.json
lobby-nl export exports/classified_data.json
lobby-nl analyze exports/classified_data.json

# Development
pytest tests/ -v
ruff check src/ tests/
mypy src/
```

## Research Principles (DO NOT VIOLATE)

1. Only public, source-verifiable information
2. Never infer from religion, ethnicity, surname, origin, race
3. Classify actors only from public function, activity, role
4. Separate fact, interpretation, hypothesis, uncertainty
5. Do not omit politically sensitive actors
6. Do not include actors without public-source evidence
7. Retain weak/light signals but label them
8. Lack of evidence != lack of activity != concealment

## Category Rules

- Jewish civic organizations are NOT automatically pro-Israel or lobby
- Antisemitism policy infrastructure is NOT automatically Zionist
- Christian Zionism must remain SEPARATE
- Israeli diplomatic channels are SEPARATE as state/diplomatic
- Counter-lobby / Palestine-rights actors MUST be included
- Media actors are NOT automatically advocacy
- Government/police actors are NOT automatically ideological

## Data Model

- Actor: 30 categories, requires source_ids
- Claim: requires source_id, evidence strength + type
- Relationship: requires source_ids, typed
- Source: requires access_date, content_hash preferred
- Event: organizers, participants, speakers
- ParliamentaryRecord: chamber, document type, topics
- DataGap: missingness logged with alternative explanation
- OpacitySignal: opacity mechanism with alternative explanation
- SourceConflict: contradiction tracking
- Exclusion: documented exclusion with reason

## Adding New Collectors

1. Extend `BaseCollector` in `collectors/__init__.py`
2. Add collector-specific methods
3. Register in CLI commands
4. Add tests in `tests/test_pipeline.py`

## Adding New Actor Categories

1. Add to `ActorCategory` enum in `models/__init__.py`
2. Add classification rules in `classifiers/__init__.py`
3. Add keyword mapping in `extractors/__init__.py`
4. Add to appropriate export filters in `exporters/__init__.py`
5. Update tests
