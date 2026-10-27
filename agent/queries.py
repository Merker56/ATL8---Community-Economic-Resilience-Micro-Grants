"""
Parameterized BigQuery SQL & GQL queries for all 3 Challenge 3 tracks.
Matches the SQL files in `sql/03_...` through `sql/06_...` and supports
evaluating ALL applicants in any loaded corridor (e.g., "Central Market",
"Market/Castro" / "Market-castro", "Chinatown", "24th St", etc.) holistically.
"""

TRACK1_APPLICANT_CASCADE_GQL = """
WITH target_applicants AS (
  SELECT business_id, name, address, naics4, corridor, tract
  FROM `a4i_econ.businesses`
  WHERE (
    @corridor = ''
    OR REGEXP_REPLACE(LOWER(corridor), r'[^a-z0-9]', '') = REGEXP_REPLACE(LOWER(@corridor), r'[^a-z0-9]', '')
  )
  AND (@evaluate_all = TRUE OR business_id IN UNNEST(@applicant_ids))
),
raw_paths AS (
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
),
incoming_local AS (
  SELECT buyer_id, COUNT(DISTINCT supplier_id) AS local_upstream_suppliers_count
  FROM `a4i_econ.supplies`
  GROUP BY buyer_id
),
footfall_stats AS (
  SELECT business_id, ROUND(SUM(worker_share), 1) AS daily_worker_footfall_share
  FROM `a4i_econ.draws_footfall_from`
  GROUP BY business_id
),
sba_stats AS (
  SELECT
    business_id,
    COUNT(*) AS own_sba_loan_count,
    LOGICAL_OR(charged_off) AS own_sba_charged_off
  FROM `a4i_econ.borrowed_from`
  GROUP BY business_id
),
industry_peers AS (
  SELECT naics4, COUNT(DISTINCT business_id) AS corridor_peers
  FROM target_applicants
  GROUP BY naics4
)
SELECT
  b.business_id AS applicant_id,
  b.name AS applicant_name,
  b.address AS applicant_address,
  b.naics4 AS applicant_naics4,
  b.corridor AS applicant_corridor,
  b.tract AS tract_geo_id,
  ROUND(COALESCE(td.poverty_rate, 0.20) * 100, 1) AS tract_poverty_rate_pct,
  ROUND(COALESCE(td.no_vehicle_rate, 0.50) * 100, 1) AS tract_no_vehicle_rate_pct,
  ROUND(COALESCE(td.assistance_rate, 0.15) * 100, 1) AS tract_assistance_rate_pct,
  COUNT(DISTINCT IF(p.hop_distance = 1, p.exposed_id, NULL)) AS direct_1hop_dependents,
  COUNT(DISTINCT IF(p.hop_distance = 2, p.exposed_id, NULL)) AS indirect_2hop_dependents,
  COUNT(DISTINCT p.exposed_id) AS total_exposed_businesses,
  ROUND(COALESCE(SUM(p.path_weight), 0.0), 4) AS cumulative_cascade_weight,
  COALESCE(il.local_upstream_suppliers_count, 0) AS local_upstream_suppliers_count,
  COALESCE(fs.daily_worker_footfall_share, 0.0) AS daily_worker_footfall_share,
  IF(COALESCE(ip.corridor_peers, 1) = 1 AND COUNT(DISTINCT p.exposed_id) > 0, TRUE, FALSE) AS is_sole_corridor_supplier,
  COALESCE(sb.own_sba_loan_count, 0) AS own_sba_loan_count,
  COALESCE(sb.own_sba_charged_off, FALSE) AS own_sba_charged_off
FROM target_applicants b
LEFT JOIN best_path_per_pair p ON p.applicant_id = b.business_id
LEFT JOIN `a4i_econ.tract_demographics` td ON LPAD(CAST(td.geo_id AS STRING), 11, '0') = LPAD(CAST(b.tract AS STRING), 11, '0')
LEFT JOIN incoming_local il ON il.buyer_id = b.business_id
LEFT JOIN footfall_stats fs ON fs.business_id = b.business_id
LEFT JOIN sba_stats sb ON sb.business_id = b.business_id
LEFT JOIN industry_peers ip ON ip.naics4 = b.naics4
GROUP BY
  b.business_id, b.name, b.address, b.naics4, b.corridor, b.tract,
  td.poverty_rate, td.no_vehicle_rate, td.assistance_rate,
  il.local_upstream_suppliers_count, fs.daily_worker_footfall_share,
  ip.corridor_peers, sb.own_sba_loan_count, sb.own_sba_charged_off
ORDER BY cumulative_cascade_weight DESC
"""

TRACK1_PATHS_DETAIL_GQL = """
SELECT *
FROM GRAPH_TABLE(
  a4i_econ.LocalEconomy
  MATCH (seed:Business)-[e1:Supplies]->(hop1:Business)
  WHERE (@evaluate_all = TRUE OR seed.business_id IN UNNEST(@applicant_ids))
  RETURN
    seed.business_id AS applicant_id,
    hop1.business_id AS exposed_id,
    hop1.name AS exposed_name,
    hop1.naics4 AS exposed_naics4,
    1 AS hop_distance,
    ROUND(e1.intensity, 4) AS path_weight,
    CONCAT(seed.name, ' --[', CAST(ROUND(e1.intensity, 3) AS STRING), ']--> ', hop1.name) AS cascade_path_text
  UNION ALL
  MATCH (seed:Business)-[e1:Supplies]->(hop1:Business)-[e2:Supplies]->(hop2:Business)
  WHERE (@evaluate_all = TRUE OR seed.business_id IN UNNEST(@applicant_ids))
    AND hop2.business_id != seed.business_id
  RETURN
    seed.business_id AS applicant_id,
    hop2.business_id AS exposed_id,
    hop2.name AS exposed_name,
    hop2.naics4 AS exposed_naics4,
    2 AS hop_distance,
    ROUND(e1.intensity * e2.intensity, 4) AS path_weight,
    CONCAT(
      seed.name, ' --[', CAST(ROUND(e1.intensity, 3) AS STRING), ']--> ',
      hop1.name, ' --[', CAST(ROUND(e2.intensity, 3) AS STRING), ']--> ',
      hop2.name
    ) AS cascade_path_text
)
ORDER BY applicant_id, hop_distance ASC, path_weight DESC
LIMIT 250
"""

TRACK2_MICRO_PRODUCERS_GQL = """
WITH sweet_spot_producers AS (
  SELECT *
  FROM GRAPH_TABLE(
    a4i_econ.LocalEconomy
    MATCH (seed:Business)-[e:Supplies]->{1,2}(exposed:Business)
    WHERE exposed.business_id != seed.business_id
    RETURN
      seed.business_id AS producer_id,
      seed.name AS producer_name,
      seed.address AS producer_address,
      seed.naics4 AS producer_naics4,
      COUNT(DISTINCT exposed.business_id) AS exposed_2hop
    NEXT
    FILTER exposed_2hop >= @min_reach AND exposed_2hop <= @max_reach
    RETURN
      producer_id,
      producer_name,
      producer_address,
      producer_naics4,
      exposed_2hop
  )
),
industry_scarcity AS (
  SELECT naics4, COUNT(DISTINCT business_id) AS corridor_peers
  FROM `a4i_econ.businesses`
  GROUP BY naics4
),
direct_stats AS (
  SELECT
    supplier_id,
    COUNT(DISTINCT buyer_id) AS direct_buyers,
    ROUND(SUM(intensity), 4) AS total_direct_intensity
  FROM `a4i_econ.supplies`
  GROUP BY supplier_id
)
SELECT
  sp.producer_id,
  sp.producer_name,
  sp.producer_address,
  sp.producer_naics4,
  COALESCE(d.direct_buyers, 0) AS direct_1hop_buyers,
  sp.exposed_2hop AS total_2hop_exposed,
  (sp.exposed_2hop - COALESCE(d.direct_buyers, 0)) AS hidden_2nd_hop_dependents,
  COALESCE(d.total_direct_intensity, 0.0) AS direct_supply_intensity,
  sc.corridor_peers AS same_industry_peers_in_corridor,
  IF(sc.corridor_peers = 1, TRUE, FALSE) AS is_sole_corridor_supplier,
  ROUND(
    (sp.exposed_2hop * 1.0)
    + ((sp.exposed_2hop - COALESCE(d.direct_buyers, 0)) * 1.5)
    + IF(sc.corridor_peers = 1, 10.0, 0.0)
    + (COALESCE(d.total_direct_intensity, 0.0) * 20.0),
    2
  ) AS continuity_priority_score
FROM sweet_spot_producers sp
LEFT JOIN industry_scarcity sc ON sc.naics4 = sp.producer_naics4
LEFT JOIN direct_stats d ON d.supplier_id = sp.producer_id
ORDER BY continuity_priority_score DESC, total_2hop_exposed DESC
LIMIT 25
"""

TRACK3_ANCHOR_CLOSURE_GQL = """
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
      upstream.business_id AS upstream_supplier_id,
      upstream.name AS upstream_supplier_name,
      upstream.address AS upstream_supplier_address,
      upstream.naics4 AS upstream_supplier_naics4,
      s.intensity AS supply_intensity,
      (f.worker_share * s.intensity) AS backward_shock_weight
  )
),
target_block AS (
  SELECT closing_block_id
  FROM anchor_shock_paths
  WHERE @block_id = 'auto' OR closing_block_id = @block_id
  GROUP BY closing_block_id, anchor_jobs_lost
  ORDER BY anchor_jobs_lost DESC
  LIMIT 1
)
SELECT
  p.closing_block_id,
  p.anchor_tract,
  p.anchor_jobs_lost,
  p.upstream_supplier_id,
  p.upstream_supplier_name,
  p.upstream_supplier_address,
  p.upstream_supplier_naics4,
  COUNT(DISTINCT p.frontline_id) AS impacted_frontline_buyers,
  ROUND(SUM(p.frontline_worker_share_lost), 1) AS total_frontline_worker_footfall_exposed,
  ROUND(SUM(p.backward_shock_weight), 4) AS cumulative_upstream_shock_score,
  STRING_AGG(
    CONCAT(
      'Employer(', p.closing_block_id, ') --[Footfall: ', CAST(ROUND(p.frontline_worker_share_lost, 0) AS STRING),
      ' workers]--> ', p.frontline_name, ' <--[Supplies: ', CAST(ROUND(p.supply_intensity, 3) AS STRING),
      ']-- ', p.upstream_supplier_name
    ),
    ' | '
    ORDER BY p.backward_shock_weight DESC
    LIMIT 4
  ) AS two_leg_traversal_paths
FROM anchor_shock_paths p
JOIN target_block tb ON tb.closing_block_id = p.closing_block_id
GROUP BY
  p.closing_block_id,
  p.anchor_tract,
  p.anchor_jobs_lost,
  p.upstream_supplier_id,
  p.upstream_supplier_name,
  p.upstream_supplier_address,
  p.upstream_supplier_naics4
ORDER BY cumulative_upstream_shock_score DESC
LIMIT 15
"""
