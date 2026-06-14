# OpenRefine Workflow — Lobby NL Integration

## Overview

OpenRefine is a powerful tool for cleaning, deduplicating, and reconciling actor data. The Lobby NL pipeline exports `openrefine_actors.csv`, `openrefine_relationships.csv`, and `openrefine_sources.csv` for import into OpenRefine.

## Step 1: Import

```bash
# In OpenRefine:
# 1. Click "Create Project" > "Get data from" > "This Computer"
# 2. Select exports/openrefine_actors.csv
# 3. Ensure "Parse next 1 line(s) as column headers" is checked
# 4. Click "Create Project"
```

Or via command line (OpenRefine server must be running):

```bash
# Start OpenRefine server
openrefine -p 3333

# Import via API
curl -X POST http://localhost:3333/command/core/create-project-from-upload \
  -H "Content-Type: text/csv" \
  --data-binary @exports/openrefine_actors.csv
```

## Step 2: Actor Name Deduplication

### Cluster & Edit Organisatienamen

```
# In OpenRefine:
1. Select "name" column
2. Click dropdown > "Facet" > "Text facet"
   — Check for obvious duplicates or variants

3. Click dropdown > "Edit cells" > "Cluster and edit..."
   — Method: "key collision" or "nearest neighbor"
   — Keying function: "fingerprint" or "metaphone3"
   — Merge identical or similar names

4. Common Dutch organization name variants to check:
   | Variant 1                    | Variant 2                    |
   |-----------------------------|------------------------------|
   | Stichting CIDI               | CIDI                          |
   | St. Christenen voor Israël   | Christenen voor Israël        |
   | CJO                          | Centraal Joods Overleg        |
   | NIDA                         | Nationaal Coördinator         |
   | NCAB                         | Nationaal Coördinator         |
   | Ambassade van Israël         | Israëlische Ambassade         |
   | Min. van Buitenlandse Zaken  | Ministerie van BuZa           |
   | TK                           | Tweede Kamer                  |
```

### GREL Expressions for Name Normalization

```
# Remove common prefixes
value.replace(/^Stichting /, "").replace(/^St\. /, "")

# Extract acronym from parenthetical
if(value.match(/\(([A-Z]+)\)/), value.match(/\(([A-Z]+)\)/)[0], value)

# Normalize spacing and capitalization
value.trim().replace(/\s+/, " ").toTitlecase()
```

## Step 3: Wikidata Reconciliation

### Setup Reconciliation Service

```bash
# OpenRefine already includes Wikidata reconciliation by default
# If not, add via: https://wikidata.reconci.link/
```

### Reconcile Against Wikidata

```
# In OpenRefine:
1. Select "name" column
2. Click dropdown > "Reconcile" > "Start reconciling..."
3. Service: "Wikidata (en)" or "Wikidata (nl)"
4. Configure:
   - Type: Organization (Q43229) or Person (Q215627)
   - Auto-match threshold: 0.8
5. Click "Start Reconciling"

# For Dutch-specific results:
- Use "Wikidata (nl)" service
- Add type constraint: Q29999 (Netherlands) or Q55 (Netherlands)
- Limit by country via SPARQL property P17
```

### Post-Reconciliation

```
# 1. Review unmatched items
   — Click "none" facet on reconciled column
   — Manually match or create new Wikidata items

# 2. Enrich with Wikidata data
   — Click dropdown > "Edit column" > "Add column from reconciled values..."
   — Add properties like:
     - P17 (country)
     - P31 (instance of)
     - P571 (inception date)
     - P856 (official website)
     - P101 (field of work)
     - P1416 (affiliation)

# 3. Verify mismatches
   — Click "Judgment" > "Best candidate's name"
   — Compare against original name
   — Flag potential false matches
```

## Step 4: Cross-Reference with EU Register

```
# 1. Import openrefine_sources.csv as second project

# 2. For EU Transparency Register sources:
   — Filter source_type = "eu_register"
   — Extract registration ID via GREL:
     value.match(/[A-Z]{3}-\d{6,}/)
   
# 3. Cross-reference:
   — Reconcile against EU Transparency Register API
   — Compare actor names with registration names
   — Flag discrepancies
```

## Step 5: Export Clean Dataset

```
# Export from OpenRefine:
1. Click "Export" > "Comma-separated value"
2. Save as exports/actors_cleaned.csv

# Or via API:
curl http://localhost:3333/command/core/export-rows/projectID/csv \
  -o exports/actors_cleaned.csv
```

## Step 6: Re-import into Pipeline

The cleaned CSV can be re-imported into the pipeline as verified seed data:

```python
import pandas as pd

# Load cleaned actors
cleaned = pd.read_csv("exports/actors_cleaned.csv")

# Convert to pipeline actor format
seeds = []
for _, row in cleaned.iterrows():
    seeds.append({
        "actor_id": row.get("actor_id", ""),
        "name": row["name"],
        "category": row.get("_entity_type", "unknown"),
        "description": row.get("description", ""),
        "source_id": row.get("source_id", "openrefine_reconciled"),
        "url": row.get("wikidata_url", row.get("website", "")),
        "notes": f"Cleaned via OpenRefine + Wikidata reconciliation. Wikidata ID: {row.get('wikidata', '')}",
    })

pd.DataFrame(seeds).to_csv("data/input/manual_seeds_openrefine.csv", index=False)
```

## Batch Processing Script

```bash
#!/bin/bash
# openrefine_clean_pipeline.sh — Full OpenRefine cleaning workflow

OPENREFINE_URL="http://localhost:3333"

# 1. Import actors
curl -s -X POST "$OPENREFINE_URL/command/core/create-project-from-upload" \
  -H "Content-Type: text/csv" \
  --data-binary @exports/openrefine_actors.csv | jq '.project'

# 2. Wait for project to load
sleep 3

# 3. Apply name clustering (via apply-operations)
#    — This would be the JSON operations from OpenRefine's history
#    — Save your operations as openrefine_operations.json first
curl -s -X POST "$OPENREFINE_URL/command/core/apply-operations" \
  -H "Content-Type: application/json" \
  -d @docs/external_tools/openrefine_operations.json

# 4. Export cleaned dataset
curl -s "$OPENREFINE_URL/command/core/export-rows/PROJECT_ID/csv" \
  -o exports/actors_cleaned.csv

echo "[OK] OpenRefine cleaning complete -> exports/actors_cleaned.csv"
```
