-- ============================================================================
-- A4I 2026 — Challenge 3: Community Economic Resilience & Micro-Grants
-- Corridor: Market/Castro (San Francisco, CA)
-- File: sql/02_gql_cascade_queries.sql
-- ============================================================================
-- BigQuery GQL Queries used by the ADK Agent (`agent/tools.py`) and notebooks.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- QUERY 1: Keystone Band Discovery (No HAVING in GQL -> Chain with NEXT + FILTER)
-- ----------------------------------------------------------------------------
-- Finds businesses in the actionable grant band (5 to 28 downstream businesses
-- reached within 2 hops), avoiding trivial leaves (0-1 reach) and giant virtual
-- mailbox hubs (140+ reach at 2261 Market St).
GRAPH a4i_econ.LocalEconomy
MATCH (seed:Business)-[e:Supplies]->{1,2}(exposed:Business)
WHERE seed.business_id != exposed.business_id
RETURN seed.business_id AS business_id,
       seed.name AS business_name,
       seed.address AS address,
       seed.naics4 AS naics4,
       COUNT(DISTINCT exposed.business_id) AS exposed_2hop
NEXT
FILTER exposed_2hop >= 5 AND exposed_2hop <= 28
RETURN business_id, business_name, address, naics4, exposed_2hop
ORDER BY exposed_2hop DESC;


-- ----------------------------------------------------------------------------
-- QUERY 2: Visual Cascade Path Traversal (Returns TO_JSON(p) under 2 MB limit)
-- ----------------------------------------------------------------------------
-- Uses `ANY SHORTEST` + `TO_JSON(p)` + `LIMIT 100` so BigQuery Graph / Console
-- renders the full multi-hop path rather than a flat table or truncated >2MB blob.
-- Example seed: '1328524-03-231' (Theatre Rhinoceros, 4229 18th St)
--           or  '1140504-03-171' (Cafe Du Nord, 2174 Market St E)
GRAPH a4i_econ.LocalEconomy
MATCH p = ANY SHORTEST (seed:Business WHERE seed.business_id = '1328524-03-231')
          -[:Supplies]->{1,2}(exposed:Business)
WHERE seed.business_id != exposed.business_id
RETURN TO_JSON(p) AS paths
LIMIT 100;


-- ----------------------------------------------------------------------------
-- QUERY 3: Detailed 1-Hop and 2-Hop Cascade Breakdown with Attenuated Intensity
-- ----------------------------------------------------------------------------
-- Extracts explicit 1-hop (`seed -> b1`) and 2-hop (`seed -> b1 -> b2`) supply
-- chains so the agent can cite exact intermediate links, distances, and
-- compounded BEA direct-requirements coefficients (`e1.intensity * e2.intensity`).
SELECT
  seed_id,
  seed_name,
  seed_address,
  seed_naics4,
  hop1_id,
  hop1_name,
  hop1_address,
  hop1_naics4,
  ROUND(hop1_intensity, 4) AS hop1_intensity,
  ROUND(hop1_metres, 1) AS hop1_metres,
  hop2_id,
  hop2_name,
  hop2_address,
  hop2_naics4,
  ROUND(hop2_intensity, 4) AS hop2_intensity,
  ROUND(hop1_intensity * COALESCE(hop2_intensity, 1.0), 5) AS compounded_intensity,
  ROUND(LEAST(hop1_intensity, COALESCE(hop2_intensity, hop1_intensity)), 4) AS bottleneck_intensity
FROM GRAPH_TABLE (
  a4i_econ.LocalEconomy
  MATCH (seed:Business WHERE seed.business_id = '1328524-03-231')
        -[e1:Supplies]->(b1:Business)
        -[e2:Supplies]->{0,1}(b2:Business)
  WHERE seed.business_id != b1.business_id
    AND b1.business_id != b2.business_id
    AND seed.business_id != b2.business_id
  COLUMNS (
    seed.business_id AS seed_id,
    seed.name AS seed_name,
    seed.address AS seed_address,
    seed.naics4 AS seed_naics4,
    b1.business_id AS hop1_id,
    b1.name AS hop1_name,
    b1.address AS hop1_address,
    b1.naics4 AS hop1_naics4,
    e1.intensity AS hop1_intensity,
    e1.metres AS hop1_metres,
    b2.business_id AS hop2_id,
    b2.name AS hop2_name,
    b2.address AS hop2_address,
    b2.naics4 AS hop2_naics4,
    e2.intensity AS hop2_intensity
  )
)
ORDER BY compounded_intensity DESC
LIMIT 100;


-- ----------------------------------------------------------------------------
-- QUERY 4: Track 3 Two-Direction Anchor Closure Simulation
-- ----------------------------------------------------------------------------
-- Runs FORWARD along `DrawsFootfall` (Employer block -> Consumer business)
-- and BACKWARD along `Supplies` (Consumer business <- Upstream local supplier).
-- Answers: "If workplace block 060750171011001 (785 jobs at Castro & Market)
-- downsizes by 50%, which storefront businesses lose daytime footfall AND which
-- upstream local suppliers lose their buyers?"
SELECT
  block_id,
  block_jobs,
  consumer_id,
  consumer_name,
  consumer_address,
  consumer_naics4,
  ROUND(worker_share, 2) AS daytime_worker_share,
  ROUND(footfall_metres, 1) AS footfall_metres,
  upstream_id,
  upstream_name,
  upstream_address,
  upstream_naics4,
  ROUND(supply_intensity, 4) AS upstream_supply_intensity
FROM GRAPH_TABLE (
  a4i_econ.LocalEconomy
  MATCH (emp:Employer WHERE emp.block_id = '060750171011001')
        -[df:DrawsFootfall]->(consumer:Business)
        <-[s:Supplies]-(upstream:Business)
  WHERE consumer.business_id != upstream.business_id
  COLUMNS (
    emp.block_id AS block_id,
    emp.jobs AS block_jobs,
    consumer.business_id AS consumer_id,
    consumer.name AS consumer_name,
    consumer.address AS consumer_address,
    consumer.naics4 AS consumer_naics4,
    df.worker_share AS worker_share,
    df.metres AS footfall_metres,
    upstream.business_id AS upstream_id,
    upstream.name AS upstream_name,
    upstream.address AS upstream_address,
    upstream.naics4 AS upstream_naics4,
    s.intensity AS supply_intensity
  )
)
ORDER BY daytime_worker_share DESC, upstream_supply_intensity DESC
LIMIT 100;
