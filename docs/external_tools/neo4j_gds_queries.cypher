// =============================================================================
// Neo4j Graph Data Science (GDS) Queries — Lobby NL OSINT Pipeline
// =============================================================================
// Usage:
//   1. Import the cypher script: neo4j < neo4j_import.cypher
//   2. Run GDS queries below
// =============================================================================

// =============================================================================
// PART 0: GRAPH PROJECTION (required before GDS algorithms)
// =============================================================================

// Project the actor graph for GDS algorithms
// Node labels: all actors imported as individual nodes
// Relationship types: all relationship types become edges
CALL gds.graph.project(
  'actor-graph',
  '*',                          // All node labels
  '*',                          // All relationship types
  {
    relationshipProperties: ['weight', 'confidence']
  }
);

// Alternative: project only specific relationship types and nodes
CALL gds.graph.project(
  'lobby-network',
  'Actor',                      // Only nodes labeled :Actor
  {
    LOBBIES: { type: 'LOBBIES', orientation: 'NATURAL' },
    COLLABORATES: { type: 'COLLABORATES', orientation: 'UNDIRECTED' },
    FUNDED_BY: { type: 'FUNDED_BY', orientation: 'NATURAL' },
    OPPOSES: { type: 'OPPOSES', orientation: 'UNDIRECTED' }
  },
  {
    relationshipProperties: ['weight']
  }
);

// Drop projection when done
// CALL gds.graph.drop('actor-graph');


// =============================================================================
// PART 1: PAGERANK — Most Central Actors
// =============================================================================
// Which actors are most central in the influence network?

CALL gds.pageRank.stream('actor-graph', {
  maxIterations: 20,
  dampingFactor: 0.85,
  relationshipWeightProperty: 'weight'
})
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS actor, score
RETURN actor.name AS actor_name,
       labels(actor) AS categories,
       score AS pagerank_score
ORDER BY score DESC
LIMIT 25;


// =============================================================================
// PART 2: LOUVAIN — Community Detection
// =============================================================================
// Which clusters of actors exist? Which communities are naturally formed?

CALL gds.louvain.stream('actor-graph', {
  relationshipWeightProperty: 'weight',
  includeIntermediateCommunities: false
})
YIELD nodeId, communityId, intermediateCommunityIds
WITH gds.util.asNode(nodeId) AS actor, communityId
RETURN communityId,
       collect(actor.name)[0..5] AS top_members,
       count(*) AS community_size
ORDER BY community_size DESC
LIMIT 20;

// Detailed community membership
CALL gds.louvain.stream('actor-graph', {
  relationshipWeightProperty: 'weight'
})
YIELD nodeId, communityId
WITH gds.util.asNode(nodeId) AS actor, communityId
RETURN communityId,
       actor.name AS actor_name,
       labels(actor) AS categories
ORDER BY communityId, actor_name;


// =============================================================================
// PART 3: BETWEENNESS CENTRALITY — Bridge Figures
// =============================================================================
// Which actors act as bridges between different parts of the network?
// These control information flow and connect otherwise separate clusters.

CALL gds.betweenness.stream('actor-graph', {
  relationshipWeightProperty: 'weight'
})
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS actor, score
RETURN actor.name AS bridge_actor,
       labels(actor) AS categories,
       score AS betweenness_score
ORDER BY score DESC
LIMIT 20;


// =============================================================================
// PART 4: SHORTEST PATH — Connection Routes
// =============================================================================
// What is the shortest influence path between two actors?

// First, find actor IDs
MATCH (a {name: 'CIDI - Centrum Informatie en Documentatie Israël'})
OPTIONAL MATCH (b {name: 'Ambassade van Israël in Den Haag'})
RETURN id(a) AS cidi_id, id(b) AS ambassade_id;

// Then run Dijkstra shortest path
// Replace sourceNode and targetNode with the actual IDs
MATCH (source:Actor {name: 'CIDI - Centrum Informatie en Documentatie Israël'})
MATCH (target:Actor {name: 'Tweede Kamer Commissie Buitenlandse Zaken'})
CALL gds.shortestPath.dijkstra.stream('actor-graph', {
  sourceNode: source,
  targetNode: target,
  relationshipWeightProperty: 'weight'
})
YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path
RETURN index,
       [nodeId IN nodeIds | gds.util.asNode(nodeId).name] AS path_actors,
       totalCost,
       costs
ORDER BY index;

// Alternative: find all paths up to length 3
MATCH (a:Actor {name: 'CIDI - Centrum Informatie en Documentatie Israël'})
MATCH (b:Actor {name: 'Tweede Kamer Commissie Buitenlandse Zaken'})
MATCH path = shortestPath((a)-[*..3]-(b))
RETURN path;


// =============================================================================
// PART 5: QUALITY CHECKS — Data Integrity
// =============================================================================

// 5a. Actors without sources (quality gate violation)
MATCH (a:Actor)
WHERE a.source_ids IS NULL OR size(a.source_ids) = 0
RETURN a.name AS actor_name,
       labels(a) AS categories,
       'MISSING_SOURCE' AS issue
ORDER BY actor_name;

// 5b. All actors per category (export verification)
MATCH (a:Actor)
RETURN labels(a)[0] AS category,
       count(*) AS actor_count,
       collect(a.name)[0..10] AS sample_actors
ORDER BY actor_count DESC;

// 5c. All relationships by evidence strength
MATCH ()-[r]->()
RETURN type(r) AS relationship_type,
       r.evidence_strength AS evidence,
       count(*) AS count
ORDER BY relationship_type, evidence;

// 5d. Isolated actors (no relationships)
MATCH (a:Actor)
WHERE NOT (a)-[]-()
RETURN a.name AS isolated_actor,
       labels(a) AS categories,
       'ISOLATED' AS issue
ORDER BY isolated_actor;

// 5e. Duplicate actor detection (same name, different IDs)
MATCH (a:Actor), (b:Actor)
WHERE a.name = b.name AND id(a) < id(b)
RETURN a.name AS duplicate_name,
       id(a) AS id_1,
       id(b) AS id_2,
       'DUPLICATE' AS issue;


// =============================================================================
// PART 6: CATEGORY-SPECIFIC QUERIES
// =============================================================================

// 6a. Pro-Israel lobby network
MATCH (a:Actor {category: 'pro_israel_org'})
OPTIONAL MATCH (a)-[r]->(b)
RETURN a.name AS actor,
       type(r) AS relationship,
       b.name AS connected_to;

// 6b. Christian Zionist organizations and their connections
MATCH (a:Actor {category: 'christian_zionist_org'})
OPTIONAL MATCH (a)-[r]->(b)
RETURN a.name AS actor,
       type(r) AS relationship,
       b.name AS connected_to;

// 6c. Counter-lobby vs Pro-Israel overlap in parliamentary contacts
MATCH (pro:Actor {category: 'pro_israel_org'})-[r1]->(p:Actor {category: 'committee_actor'})
MATCH (counter:Actor {category: 'palestine_rights_counter_lobby'})-[r2]->(p)
RETURN p.name AS committee_actor,
       collect(DISTINCT pro.name) AS pro_israel_contacts,
       collect(DISTINCT counter.name) AS counter_lobby_contacts;

// 6d. Funding network (who funds whom?)
MATCH (funder:Actor {category: 'funding_actor'})-[r:FUNDED_BY|FUNDS]->(recipient:Actor)
RETURN funder.name AS funder,
       type(r) AS flow,
       recipient.name AS recipient,
       r.evidence_strength AS evidence;

// 6e. Parliamentary actors receiving most lobbying
MATCH (lobby:Actor)-[r:LOBBIES]->(parliament:Actor {category: 'parliamentary_actor'})
RETURN parliament.name AS targeted_parliamentarian,
       count(r) AS lobby_contacts,
       collect(lobby.name) AS lobby_sources
ORDER BY lobby_contacts DESC;


// =============================================================================
// PART 7: TEMPORAL ANALYSIS
// =============================================================================

// 7a. Events timeline by date
MATCH (e:Event)
WHERE e.date IS NOT NULL
RETURN e.date AS event_date,
       e.name AS event_name,
       e.organizer_name AS organizer,
       e.city AS location
ORDER BY e.date;

// 7b. Claims timeline
MATCH (c:Claim)
WHERE c.date IS NOT NULL
RETURN c.date AS claim_date,
       c.topic AS topic,
       c.actor_id AS actor,
       c.evidence_strength AS evidence
ORDER BY c.date;


// =============================================================================
// PART 8: ADVANCED GDS — NODE SIMILARITY
// =============================================================================
// Which actors are structurally similar in the graph?

CALL gds.nodeSimilarity.stream('actor-graph', {
  topK: 5,
  topP: 0.5
})
YIELD node1, node2, similarity
WITH gds.util.asNode(node1) AS actor1,
     gds.util.asNode(node2) AS actor2,
     similarity
WHERE similarity > 0.5
RETURN actor1.name AS actor_a,
       actor2.name AS actor_b,
       similarity
ORDER BY similarity DESC
LIMIT 20;


// =============================================================================
// PART 9: EVIDENCE STRENGTH DISTRIBUTION
// =============================================================================

// Distribution of evidence strength across relationships
MATCH ()-[r]->()
RETURN r.evidence_strength AS evidence_level,
       count(*) AS relationship_count,
       collect(DISTINCT type(r)) AS relationship_types
ORDER BY relationship_count DESC;

// Actors with most "weak" evidence relationships (risk assessment)
MATCH (a:Actor)-[r]->()
WHERE r.evidence_strength = 'weak'
RETURN a.name AS actor,
       count(r) AS weak_relationship_count
ORDER BY weak_relationship_count DESC
LIMIT 25;


// =============================================================================
// PART 10: CLEANUP
// =============================================================================

// Clean up projections when analysis is complete
// CALL gds.graph.drop('actor-graph');
// CALL gds.graph.drop('lobby-network');

// Verify projections are dropped
// CALL gds.graph.list();
