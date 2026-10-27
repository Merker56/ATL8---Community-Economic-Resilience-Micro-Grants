-- =============================================================================
-- A4I 2026 Challenge 3 — Track 3: Anchor Closure (Forward -> Backward Traversal)
--
-- Question: A large workplace block (`Employer`) announces it is closing in 90
-- days. Nobody has applied for relief yet.
--
-- Why most teams miss half of this track:
-- - Leg 1 (Forward along `DrawsFootfall`): Employer -> Frontline retail/cafes
--   that lose weekday footfall (`worker_share`).
-- - Leg 2 (Backward along `Supplies`, `<-[:Supplies]-`): Frontline cafes/retail
--   -> Upstream suppliers (roasters, bakeries, caterers, wholesalers) who never
--   sold to the office workers directly, but lose their B2B buyers when the
--   frontline businesses collapse!
-- =============================================================================

-- Query 3A: Discover Top Employer Blocks in the Corridor (to pick the Anchor Seed)
SELECT
  e.block_id,
  e.tract,
  e.jobs AS total_block_jobs,
  COUNT(DISTINCT f.business_id) AS frontline_businesses_served,
  ROUND(AVG(f.worker_share), 2) AS worker_share_per_business,
  t.poverty_rate AS tract_poverty_rate,
  t.no_vehicle_rate AS tract_no_vehicle_rate
FROM `a4i_econ.employer_blocks` e
LEFT JOIN `a4i_econ.draws_footfall_from` f ON f.block_id = e.block_id
LEFT JOIN `a4i_econ.tract_demographics` t ON t.geo_id = LPAD(e.tract, 11, '0')
GROUP BY e.block_id, e.tract, e.jobs, t.poverty_rate, t.no_vehicle_rate
HAVING frontline_businesses_served > 0
ORDER BY e.jobs DESC
LIMIT 10;

-- =============================================================================
-- Query 3B: Two-Leg Directional-Shift Traversal in GQL
-- Forward `-[:DrawsFootfall]->` then Backward `<-[:Supplies]-`
-- =============================================================================
WITH anchor_shock_paths AS (
  SELECT *
  FROM GRAPH_TABLE(
    a4i_econ.LocalEconomy
    MATCH (anchor:Employer)
          -[f:DrawsFootfall]->(frontline:Business)
          <-[s:Supplies]-(upstream:Business)
    WHERE upstream.business_id != frontline.business_id
    RETURN
      anchor.block_id AS closing_block_id,
      anchor.tract AS anchor_tract,
      anchor.jobs AS anchor_jobs_lost,
      frontline.business_id AS frontline_id,
      frontline.name AS frontline_name,
      frontline.address AS frontline_address,
      frontline.naics4 AS frontline_naics4,
      f.worker_share AS frontline_worker_share_lost,
      f.metres AS footfall_distance_m,
      upstream.business_id AS upstream_supplier_id,
      upstream.name AS upstream_supplier_name,
      upstream.address AS upstream_supplier_address,
      upstream.naics4 AS upstream_supplier_naics4,
      s.intensity AS supply_intensity,
      s.metres AS supply_distance_m,
      (f.worker_share * s.intensity) AS backward_shock_weight
  )
),
top_anchor AS (
  -- Automatically select the largest employer block with active footfall links
  -- (or replace with a specific `block_id` filter)
  SELECT closing_block_id
  FROM anchor_shock_paths
  GROUP BY closing_block_id, anchor_jobs_lost
  ORDER BY anchor_jobs_lost DESC
  LIMIT 1
)
SELECT
  p.closing_block_id,
  p.anchor_jobs_lost,
  p.upstream_supplier_id,
  p.upstream_supplier_name,
  p.upstream_supplier_address,
  p.upstream_supplier_naics4,
  COUNT(DISTINCT p.frontline_id) AS impacted_frontline_buyers,
  ROUND(SUM(p.frontline_worker_share_lost), 1) AS total_frontline_worker_footfall_exposed,
  ROUND(SUM(p.backward_shock_weight), 4) AS cumulative_upstream_shock_score,
  ARRAY_AGG(
    STRUCT(
      p.frontline_name,
      p.frontline_naics4,
      ROUND(p.frontline_worker_share_lost, 1) AS worker_share_lost,
      ROUND(p.supply_intensity, 4) AS b2b_intensity,
      ROUND(p.backward_shock_weight, 4) AS link_shock
    )
    ORDER BY p.backward_shock_weight DESC
    LIMIT 6
  ) AS impacted_buyer_channels
FROM anchor_shock_paths p
JOIN top_anchor ta ON ta.closing_block_id = p.closing_block_id
GROUP BY
  p.closing_block_id,
  p.anchor_jobs_lost,
  p.upstream_supplier_id,
  p.upstream_supplier_name,
  p.upstream_supplier_address,
  p.upstream_supplier_naics4
ORDER BY cumulative_upstream_shock_score DESC
LIMIT 15;
