# Lobby NL - OSINT Research Pipeline

Evidence-first, source-verifiable open-source intelligence research pipeline for mapping lobbying practices, geopolitical influence, public advocacy, media framing, institutional networks, parliamentary activity, and counter-lobby dynamics in the Netherlands related to Israel, Zionism, antisemitism policy, Christian Zionism, Jewish civic organizations, Israeli state/diplomatic channels, and Palestine-rights advocacy.

## Research Principles

- Only public, source-verifiable information
- Never infer from religion, ethnicity, surname, origin, race, or protected attributes
- Classify actors only from public function, activity, role, documented interaction, public statement, event presence, or source-backed network relevance
- Separate fact, interpretation, hypothesis, uncertainty, missingness, opacity risk, and exclusion
- Do not omit actors because they are politically sensitive
- Do not include actors without public-source evidence
- Retain weak and light signals but label them explicitly
- Lack of evidence is not lack of activity; lack of evidence is not concealment

## Installation

```bash
pip install -e .
playwright install chromium
```

## Quick Start

```bash
lobby-nl full-pipeline
```

This runs the complete pipeline:
1. **Collect** - Web scraping, parliamentary records, EU register, archive checks
2. **Extract** - Actor names, claims, relationships from sources
3. **Classify** - Category assignment with identity-inference prevention
4. **Validate** - All 8 validation guards
5. **Export** - CSV, Gephi, OpenRefine, JSON, HTML report
6. **Analyze** - Media framing patterns, archive diffs

## Individual Commands

```bash
lobby-nl collect --urls-file urls.json --max-depth 2
lobby-nl extract exports/collected_data.json
lobby-nl classify exports/extracted_data.json
lobby-nl validate exports/classified_data.json
lobby-nl export exports/classified_data.json
lobby-nl analyze exports/classified_data.json
```

## Actor Categories (30)

| Category | Description |
|---|---|
| pro_israel_org | Pro-Israel advocacy organizations |
| christian_zionist_org | Christian Zionist organizations (separate) |
| jewish_civic_org | Jewish civic/societal organizations (not auto-lobby) |
| israeli_diplomatic_channel | Israeli state/diplomatic entities |
| antisemitism_policy_infrastructure | Dutch antisemitism policy bodies |
| parliamentary_actor | General parliamentary actors |
| palestine_rights_counter_lobby | Palestine-rights / counter-lobby actors |
| eu_register_actor | EU Transparency Register actors |
| media_actor | Traditional media organizations |
| alternative_media_actor | Alternative/independent media |
| journalist_actor | Individual journalists |
| influencer_actor | Public digital amplifiers |
| talkshow_or_program_actor | Talk show hosts/programs |
| podcast_actor | Podcast hosts/programs |
| newsletter_actor | Newsletter authors |
| party_actor | Political parties |
| senate_actor | Eerste Kamer members |
| house_actor | Tweede Kamer members |
| committee_actor | Parliamentary committees |
| government_actor | Government institutions |
| ministry_actor | Ministries/departments |
| municipal_actor | Municipal actors |
| mayor_actor | Mayors |
| police_actor | Police actors |
| security_actor | Security/intelligence actors |
| academic_actor | Academic institutions |
| think_tank_actor | Think tanks |
| funding_actor | Funders/donors |
| pr_or_consultancy_actor | PR/lobbying firms |
| law_firm_actor | Law firms |
| event_platform_actor | Event organizers/venues |
| celebrity_actor | Public figures |
| religious_actor | Religious actors |
| archive_actor | Archive services |
| social_platform_actor | Social platform presences |
| unknown | Unresolved actors |

## Evidence Types & Strength

**Types**: legal_evidence, documentary_evidence, registry_evidence, parliamentary_evidence, OSINT_evidence, behavioral_pattern_evidence, network_evidence, financial_trace_evidence, institutional_interaction_evidence, media_framing_evidence, event_evidence, archival_evidence, weak_associative_evidence

**Strength**: hard, strong, medium, light, weak

## Exports

### Core CSVs
- `actors.csv`, `claims.csv`, `relationships.csv`, `sources.csv`
- `events.csv`, `parliamentary_records.csv`
- `data_gaps.csv`, `opacity_signals.csv`, `source_conflicts.csv`, `exclusions.csv`

### Specialized Lists (22 files)
- `media_actors.csv`, `alternative_media_actors.csv`
- `journalists_and_presenters.csv`, `talkshows_programs_podcasts.csv`
- `political_parties.csv`, `first_chamber_actors.csv`, `second_chamber_actors.csv`
- `committees_and_delegations.csv`, `ministries_and_departments.csv`
- `municipal_actors.csv`, `mayors.csv`, `police_and_security_actors.csv`
- `public_figures_and_celebrities.csv`, `academics_thinktanks_experts.csv`
- `funders_donors_sponsors.csv`, `law_firms_pr_consultancies.csv`
- `events_and_venues.csv`, `media_framing_log.csv`
- `platform_presence_log.csv`, `cross_border_entities.csv`
- `archived_source_diffs.csv`, `source_disappearance_log.csv`
- `netherlands_relevance_matrix.csv`

### Visualization
- `gephi_nodes.csv` + `gephi_edges.csv` (Gephi network visualization)
- `openrefine_export.tsv` (OpenRefine compatible)
- `evidence_graph.json` (full JSON graph)

### Reports
- `reports/research_report.html` (HTML summary)
- `reports/audit_log.md` (research assumptions and limitations)

## Validation Guards

| Guard | Description |
|---|---|
| identity_inference_guard | Prevents classification from identity alone |
| overclaim_guard | Prevents claims that overstate evidence |
| omission_guard | Detects actors without claims/relationships |
| duplicate_guard | Detects potential duplicate actors |
| source_validator | Validates source records |
| relationship_validator | Validates relationship data |
| category_validator | Checks category appropriateness |
| export_validator | Validates referential integrity |

## Structural Limitations (Netherlands)

- No general mandatory Dutch lobby register
- Parliamentary lobby register = access-pass evidence only
- Ministerial agendas may be incomplete
- Woo records may be delayed, refused, redacted, fragmented
- Influence through formal and informal channels
- Public data split across websites, PDFs, media, events, archives

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting
ruff check src/ tests/

# Type checking
mypy src/
```

## License

MIT
