-- =============================================================================
-- A4I 2026 Challenge 3 — Track 2: Micro-Producer & Supply Continuity
--
-- Question: Nobody has applied yet. An upstream supplier or small producer may
-- be quietly failing. Which non-obvious businesses in the corridor hold up
-- between 5 and 25 downstream businesses across 1–2 hops, and which ones are
-- the ONLY local supplier for their industry in the corridor (irreplaceable)?
-- =============================================================================

-- Query 2A: Pure GQL Sweet-Spot Discovery using `NEXT` + `FILTER` (Section 13 Pattern)
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
    FILTER exposed_2hop >= 5 AND exposed_2hop <= 25
    RETURN
      producer_id,
      producer_name,
      producer_address,
      producer_naics4,
      exposed_2hop
  )
),
-- Check how many local competitors exist in the same 4-digit NAICS industry.
-- A producer with `corridor_peers = 1` is a local monopoly for that input!
industry_scarcity AS (
  SELECT
    naics4,
    COUNT(DISTINCT business_id) AS corridor_peers
  FROM `a4i_econ.businesses`
  GROUP BY naics4
),
-- Compute direct 1-hop intensity and 2-hop reach breakdown
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
  -- Composite continuity priority score: rewards hidden 2nd-hop reach + local scarcity
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
ORDER BY continuity_priority_score DESC, total_2hop_exposed DESC;
