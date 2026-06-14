# Gephi Workflow — Lobby NL Integration

## Overview

Gephi visualizes the actor network graph. The Lobby NL pipeline exports `gephi_nodes.csv` and `gephi_edges.csv` ready for import.

## Step 1: Import Data

```
# In Gephi:
1. File > "Import spreadsheet..."
2. Select exports/gephi_nodes.csv
   - "Import as": Nodes table
   - Columns: Id, Label, Category, Type, Country, Confidence
   - Click "Next" > "Finish"

3. File > "Import spreadsheet..."
4. Select exports/gephi_edges.csv
   - "Import as": Edges table
   - Source: Source, Target: Target
   - "Append to existing workspace" = checked
   - Click "Next" > "Finish"
```

## Step 2: Add Evidence Strength as Numeric Column

The pipeline exports `Evidence` as string values in the edges file. Convert to numeric for weighting:

```
# In Gephi Data Laboratory:
1. Edges tab > "Add column" (Add edge column button)
2. Column name: evidence_numeric
3. Type: Integer
4. Click "OK"

# Use "Fill column with a value" or run:
# Copy data to column > Python/JS script:
evidence_map = {'hard': 10, 'strong': 8, 'medium': 5, 'light': 2, 'weak': 1}
```

Or via GREL expression on the edges table:
```
if(value == 'hard', 10,
  if(value == 'strong', 8,
    if(value == 'medium', 5,
      if(value == 'light', 2,
        if(value == 'weak', 1, 1)
      )
    )
  )
)
```

Apply this to the `evidence_numeric` column using the "Evidence" column as input.

## Step 3: Layout — ForceAtlas2

```
# In Gephi:
1. Layout panel (left sidebar) > "ForceAtlas 2"
2. Configure:
   - Mode: LinLog (tick checkbox)
   - Edge Weight Influence: 1.0
   - Scaling: 50.0
   - Gravity: 30.0
   - "Prevent Overlap" = checked
   - "Approximate Repulsion" = checked (for large graphs)
3. Click "Run"
4. Wait for stabilization (watch the "Speed" metric, stop when < 0.1)
```

For large graphs (>1000 nodes), use these tweaks:
```
   - Scaling: 100.0
   - Gravity: 50.0
   - Edge Weight Influence: 0.5
```

## Step 4: Coloring

### Node Color = Category

```
# In Gephi Appearance panel:
1. Nodes > "Partition" (color palette icon)
2. Select attribute: "Category"
3. Click "Apply"

# Manual color scheme for key categories:
| Category                          | Color          | Hex     |
|-----------------------------------|----------------|---------|
| pro_israel_org                    | Dark Blue      | #1F4E79 |
| christian_zionist_org             | Purple         | #7030A0 |
| jewish_civic_org                  | Light Blue     | #5B9BD5 |
| israeli_diplomatic_channel        | Red            | #FF0000 |
| antisemitism_policy_infrastructure| Orange         | #ED7D31 |
| parliamentary_actor               | Green          | #70AD47 |
| palestine_rights_counter_lobby    | Lime Green     | #A5D61E |
| media_actor                       | Gray           | #808080 |
| funding_actor                     | Gold           | #FFD700 |
| unknown                           | Light Gray     | #D9D9D9 |
```

### Edge Color = Relationship Strength

```
# In Gephi Appearance panel:
1. Edges > "Ranking" (color)
2. Select attribute: "Weight"
3. Color gradient: Light Gray (#E0E0E0) to Dark Gray (#404040)
4. Click "Apply"

# Or by evidence strength:
1. Edges > "Partition"
2. Select attribute: "Evidence" (hard/strong/medium/light/weak)
3. Configure colors:
   - hard:      #000000 (Black)
   - strong:    #404040 (Dark Gray)
   - medium:    #808080 (Gray)
   - light:     #C0C0C0 (Silver)
   - weak:      #E0E0E0 (Light Gray)
```

### Node Size = Confidence

```
# In Gephi Appearance panel:
1. Nodes > "Ranking" (size)
2. Select attribute: "Confidence"
3. Min size: 5, Max size: 30
4. Click "Apply"
```

## Step 5: Community Detection — Louvain Modularity

```
# In Gephi Statistics panel:
1. "Network Overview" tab
2. Run "Modularity"
   - Resolution: 1.0
   - Use weights: checked
   - Randomization: enabled
3. Click "OK"

# Color by community:
1. Nodes > "Partition"
2. Select attribute: "Modularity Class"
3. Click "Apply"

# Expected clusters (example):
- Cluster 0: Pro-Israel network (CIDI + supporters)
- Cluster 1: Christian Zionist network
- Cluster 2: Counter-lobby network (Palestina Komitee + allies)
- Cluster 3: Parliamentary/government network
- Cluster 4: Media/journalist network
```

## Step 6: Centrality Metrics

```
# In Gephi Statistics panel:
1. Run "Average Degree" — basic connectivity
2. Run "Network Diameter" — graph reach
   - Check "Directed" if relationships are directed
3. Run "Eigenvector Centrality" — influence (who is connected to influential nodes?)
   - Use edge weight: evidence_numeric
4. Run "Betweenness Centrality" — bridge actors (who controls information flow?)
   - These are the actors connecting different clusters

# Visualize centrality:
1. Nodes > "Ranking" (size)
2. Select: "Eigenvector Centrality" or "Betweenness Centrality"
3. This shows the most influential / bridging actors
```

## Step 7: Filtering

```
# Filter panel (right sidebar):
1. "Topology" > "Degree Range"
   - Min: 1 — removes isolated nodes
2. "Edges" > "Edge Weight"
   - Min: 3 — shows only medium+ evidence relationships
3. "Attributes" > "Partition" > "Category"
   - Filter to specific actor types for focused analysis

# Useful filter presets:
# Core lobby network:
- Keep nodes: Category IN [pro_israel_org, parliamentary_actor, israeli_diplomatic_channel]

# Counter-lobby comparison:
- Keep nodes: Category IN [palestine_rights_counter_lobby, parliamentary_actor]

# Media influence:
- Keep nodes: Category IN [media_actor, journalist_actor, parliamentary_actor]
```

## Step 8: Export

```
# PNG Export (Preview panel):
1. Click "Refresh" to render
2. Configure background: White (#FFFFFF)
3. File > "Export" > "PNG..."
   - Resolution: 4K (3840x2160)
   - Antialiasing: 4x
4. Save as: exports/gephi_network.png

# GEXF Export (for sharing):
1. File > "Export" > "Graph file..."
2. Format: GEXF
3. Save as: exports/gephi_network.gexf

# SVG Export (for publication):
1. File > "Export" > "SVG/PDF/PNG..."
2. Format: SVG
3. Save as: exports/gephi_network.svg
```

## Automation Script

Gephi supports headless mode via its scripting plugin:

```python
# gephi_headless_script.py — requires Gephi Toolkit
from org.gephi.io.importer.api import ImportController
from org.gephi.io.processor.plugin import DefaultProcessor
from org.gephi.project.api import ProjectController
from org.gephi.statistics.plugin import Modularity
from org.gephi.layout.plugin.forceAtlas2 import ForceAtlas2

# Import nodes and edges
import_controller = Lookup.getDefault().lookup(ImportController)
container = import_controller.importFile(File("exports/gephi_nodes.csv"))
# ... full automation setup

# Run ForceAtlas2 layout
layout = ForceAtlas2(layout_builder)
layout.setGraphModel(graph_model)
layout.initAlgo()
for i in range(1000):
    if layout.canAlgo():
        layout.goAlgo()
layout.endAlgo()

# Run modularity
modularity = Modularity()
modularity.execute(graph_model)

# Export
export_controller.exportFile(File("exports/gephi_network.png"))
```

This requires the [Gephi Toolkit](https://gephi.org/toolkit/) Java library.

## Quick Reference: Evidence → Visual Weight Mapping

| Evidence Strength | Edge Weight | Edge Color  | Node Effect          |
|------------------|-------------|-------------|---------------------|
| hard             | 10          | #000000     | High confidence (≥0.9) |
| strong           | 8           | #404040     | Visible              |
| medium           | 5           | #808080     | Standard             |
| light            | 2           | #C0C0C0     | Thin, semi-transparent |
| weak             | 1           | #E0E0E0     | Thin, transparent    |
