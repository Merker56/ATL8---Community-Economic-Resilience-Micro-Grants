-- =============================================================================
-- A4I 2026 Challenge 3 — Track 1: Main Street Relief (Applicant Queue)
--
-- Question: A grant officer has a queue of distressed applicants and a fixed
-- budget. Which closures cause the most multi-hop downstream damage, how strong
-- are the links, and are downstream dependents already fragile (SBA loans)?
-- =============================================================================

-- Query 1A: Multi-Hop (1 and 2 Hops) Cascade Evaluation for Applicant Queue
-- Replace the array below with specific applicant `business_id`s, or leave the
-- subquery to evaluate the top candidate suppliers in the corridor.
WITH raw_paths AS (
  SELECT *
  FROM GRAPH_TABLE(
    a4i_econ.LocalEconomy
    MATCH (seed:Business)-[e1:Supplies]->(hop1:Business)
    RETURN
      seed.business_id AS applicant_id,
      seed.name AS applicant_name,
      seed.address AS applicant_address,
      seed.naics4 AS applicant_naics4,
      hop1.business_id AS exposed_id,
      hop1.name AS exposed_name,
      hop1.naics4 AS exposed_naics4,
      1 AS hop_distance,
      e1.intensity AS path_weight,
      e1.metres AS total_metres,
      CONCAT(seed.name, ' --[', CAST(ROUND(e1.intensity, 3) AS STRING), ']--> ', hop1.name) AS cascade_path_text
    UNION ALL
    MATCH (seed:Business)-[e1:Supplies]->(hop1:Business)-[e2:Supplies]->(hop2:Business)
    WHERE hop2.business_id != seed.business_id
    RETURN
      seed.business_id AS applicant_id,
      seed.name AS applicant_name,
      seed.address AS applicant_address,
      seed.naics4 AS applicant_naics4,
      hop2.business_id AS exposed_id,
      hop2.name AS exposed_name,
      hop2.naics4 AS exposed_naics4,
      2 AS hop_distance,
      (e1.intensity * e2.intensity) AS path_weight,
      (e1.metres + e2.metres) AS total_metres,
      CONCAT(
        seed.name, ' --[', CAST(ROUND(e1.intensity, 3) AS STRING), ']--> ',
        hop1.name, ' --[', CAST(ROUND(e2.intensity, 3) AS STRING), ']--> ',
        hop2.name
      ) AS cascade_path_text
  )
),
best_path_per_pair AS (
  -- Deduplicate multiple routes between the same applicant and exposed business,
  -- keeping the shortest hop first and strongest path_weight second.
  SELECT * EXCEPT(rn)
  FROM (
    SELECT *,
      ROW_NUMBER() OVER (
        PARTITION BY applicant_id, exposed_id
        ORDER BY hop_distance ASC, path_weight DESC
      ) AS rn
    FROM raw_paths
  )
  WHERE rn = 1
)
SELECT
  p.applicant_id,
  p.applicant_name,
  p.applicant_address,
  p.applicant_naics4,
  COUNT(DISTINCT IF(p.hop_distance = 1, p.exposed_id, NULL)) AS direct_1hop_dependents,
  COUNT(DISTINCT IF(p.hop_distance = 2, p.exposed_id, NULL)) AS indirect_2hop_dependents,
  COUNT(DISTINCT p.exposed_id) AS total_exposed_businesses,
  ROUND(SUM(p.path_weight), 4) AS cumulative_cascade_weight,
  -- Hub-avoidance flag: hubs reaching >25 nodes are typically diversified/robust
  CASE
    WHEN COUNT(DISTINCT p.exposed_id) = 0 THEN 'LEAF_NO_CASCADE'
    WHEN COUNT(DISTINCT p.exposed_id) > 25 THEN 'GIANT_HUB_CHECK_ROBUSTNESS'
    WHEN COUNT(DISTINCT p.exposed_id) BETWEEN 5 AND 25 THEN 'SWEET_SPOT_HIGH_LEVERAGE'
    ELSE 'LOCALIZED_SUPPLIER'
  END AS advisor_tier,
  ARRAY_AGG(
    STRUCT(
      p.exposed_name,
      p.exposed_naics4,
      p.hop_distance,
      ROUND(p.path_weight, 4) AS weight,
      p.cascade_path_text
    )
    ORDER BY p.hop_distance ASC, p.path_weight DESC
    LIMIT 8
  ) AS top_protected_paths
FROM best_path_per_pair p
GROUP BY
  p.applicant_id,
  p.applicant_name,
  p.applicant_address,
  p.applicant_naics4
ORDER BY
  -- Prioritize sweet-spot multi-hop suppliers with real 2-hop cascades
  IF(COUNT(DISTINCT p.exposed_id) BETWEEN 5 AND 25, 1, 2) ASC,
  cumulative_cascade_weight DESC
LIMIT 20;

-- =============================================================================
-- Query 1B: Visual Graph Path Query for Notebook / UI (`TO_JSON` + `ANY SHORTEST`)
-- Obeys Trap #2 (must wrap path `p` in `TO_JSON`) and Trap #3 (use `ANY SHORTEST`
-- to stay well under the 2 MB visualization cap).
-- =============================================================================
-- GRAPH a4i_econ.LocalEconomy
-- MATCH p = ANY SHORTEST (seed:Business WHERE seed.business_id = @seed_business_id)
--           -[:Supplies]->{1,2}(exposed:Business)
-- WHERE exposed.business_id != seed.business_id
-- RETURN TO_JSON(p) AS paths
-- LIMIT 50;
