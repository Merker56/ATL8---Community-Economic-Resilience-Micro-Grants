-- ============================================================================
-- A4I 2026 — Challenge 3: Community Economic Resilience & Micro-Grants
-- Corridor: Market/Castro (San Francisco, CA)
-- File: sql/03_equity_and_bias_audit.sql
-- ============================================================================
-- Implements Section 10 ("Auditing the outcome") and Section 11 ("Look at that
-- list again, skeptically"):
--   1. Mechanical BEA Industry Bias Audit (input-heavy industries vs. personal services)
--   2. Virtual Mailbox Hub & Duplicate DBA Registration Audit
--   3. Census Tract Equity & Vulnerability Audit (with LPAD(geo_id, 11, '0'))
--   4. SBA 7(a) Loan & Charge-Off Ground-Truth Validation
-- ============================================================================

-- ----------------------------------------------------------------------------
-- AUDIT 1: Mechanical BEA Supply-Edge Bias by Industry Sector
-- ----------------------------------------------------------------------------
-- Demonstrates that NAICS 51 (Information/Cloud), 71 (Arts/Performing Arts),
-- and 31 (Beverage Mfg) accumulate far more outgoing supply edges per business
-- than NAICS 81 (Personal Care/Barbers/Dry Cleaners) or 62 (Health/Social Care).
WITH corridor_mix AS (
  SELECT
    SUBSTR(naics4, 1, 2) AS naics2,
    COUNT(DISTINCT business_id) AS corridor_businesses,
    ROUND(COUNT(DISTINCT business_id) / SUM(COUNT(DISTINCT business_id)) OVER (), 4) AS share_of_corridor
  FROM `a4i_econ.businesses`
  GROUP BY naics2
),
edge_mix AS (
  SELECT
    SUBSTR(b.naics4, 1, 2) AS naics2,
    COUNT(DISTINCT s.supplier_id) AS active_suppliers,
    COUNT(*) AS outgoing_edges,
    ROUND(COUNT(*) / SUM(COUNT(*)) OVER (), 4) AS share_of_supply_edges
  FROM `a4i_econ.supplies` s
  JOIN `a4i_econ.businesses` b ON b.business_id = s.supplier_id
  GROUP BY naics2
)
SELECT
  c.naics2,
  c.corridor_businesses,
  c.share_of_corridor,
  COALESCE(e.active_suppliers, 0) AS active_suppliers,
  COALESCE(e.outgoing_edges, 0) AS outgoing_edges,
  COALESCE(e.share_of_supply_edges, 0.0) AS share_of_supply_edges,
  ROUND(SAFE_DIVIDE(COALESCE(e.share_of_supply_edges, 0.0), c.share_of_corridor), 2) AS representation_ratio
FROM corridor_mix c
LEFT JOIN edge_mix e USING (naics2)
ORDER BY representation_ratio DESC;


-- ----------------------------------------------------------------------------
-- AUDIT 1B: Single-Supplier NAICS4 Monopoly Artifact Check
-- ----------------------------------------------------------------------------
-- Identifies NAICS4 industries with only 1 supplier in Market/Castro that
-- accumulate massive mechanical outgoing supply edges (e.g., Primo at 4201 18th St,
-- NAICS 3121 Beverage Manufacturing with 76 direct buyers).
SELECT
  b.naics4,
  COUNT(DISTINCT b.business_id) AS corridor_suppliers_in_naics4,
  ANY_VALUE(b.business_id) AS sample_business_id,
  ANY_VALUE(b.name) AS sample_business_name,
  ANY_VALUE(b.address) AS sample_address,
  COUNT(s.edge_id) AS outgoing_supply_edges,
  ROUND(SUM(s.intensity), 4) AS total_1hop_intensity
FROM `a4i_econ.businesses` b
LEFT JOIN `a4i_econ.supplies` s ON s.supplier_id = b.business_id
GROUP BY b.naics4
HAVING COUNT(DISTINCT b.business_id) = 1 AND COUNT(s.edge_id) >= 10
ORDER BY outgoing_supply_edges DESC;


-- ----------------------------------------------------------------------------
-- AUDIT 2A: Commercial Mail-Drop / Virtual Office Hub Detection
-- ----------------------------------------------------------------------------
-- Uncovers why 2261 Market St (140 entities) and 584 Castro St (21 entities)
-- dominate raw graph centrality: bare mailbox numbers ('2261 Market Street 4303')
-- bypass the standard residential regex `r'\b(apt|unit|ste|suite)\b|#'`.
SELECT
  REGEXP_REPLACE(UPPER(TRIM(address)), r'\s+\d{3,5}$', '') AS normalized_street_address,
  COUNT(DISTINCT business_id) AS registered_businesses,
  COUNT(DISTINCT naics4) AS distinct_industries,
  ARRAY_AGG(name LIMIT 5) AS sample_dba_names
FROM `a4i_econ.businesses`
GROUP BY normalized_street_address
HAVING COUNT(DISTINCT business_id) >= 3
ORDER BY registered_businesses DESC;


-- ----------------------------------------------------------------------------
-- AUDIT 2B: Duplicate / Split DBA Registration Detection
-- ----------------------------------------------------------------------------
-- Finds businesses registered multiple times under identical or near-identical
-- DBA names (e.g., 'The Castro' at 429 & 449 Castro St, 'Midnight Sun' &
-- 'The Midnight Sun' at 4067 18th St, 'The Edge' at 4149 18th St), which splits
-- their customer edges across two nodes.
SELECT
  REGEXP_REPLACE(REGEXP_REPLACE(UPPER(TRIM(name)), r'^THE\s+', ''), r'[^A-Z0-9 ]', '') AS normalized_dba,
  COUNT(DISTINCT business_id) AS registration_count,
  ARRAY_AGG(STRUCT(business_id, name, address, naics4)) AS records
FROM `a4i_econ.businesses`
GROUP BY normalized_dba
HAVING COUNT(DISTINCT business_id) > 1
ORDER BY registration_count DESC;


-- ----------------------------------------------------------------------------
-- AUDIT 3: Census Tract Socioeconomic Vulnerability & Storefront Join (LPAD 11-char)
-- ----------------------------------------------------------------------------
-- Joins `a4i_econ.tract_demographics` with `a4i_econ.businesses` via
-- `LPAD(CAST(geo_id AS STRING), 11, '0')` to prevent California's leading '0'
-- in FIPS '06' from being stripped and silently failing the relational join.
WITH tract_storefronts AS (
  SELECT
    LPAD(CAST(tract_geoid AS STRING), 11, '0') AS tract_geoid,
    COUNT(DISTINCT business_id) AS active_storefronts,
    COUNTIF(NOT COALESCE(is_virtual_mailbox_hub, FALSE)) AS brick_and_mortar_storefronts
  FROM `a4i_econ.businesses`
  GROUP BY tract_geoid
)
SELECT
  LPAD(CAST(t.geo_id AS STRING), 11, '0') AS tract_geoid,
  COALESCE(ts.active_storefronts, 0) AS active_storefronts,
  COALESCE(ts.brick_and_mortar_storefronts, 0) AS brick_and_mortar_storefronts,
  ROUND(t.total_pop, 0) AS total_pop,
  ROUND(t.median_income, 0) AS median_income,
  ROUND(t.poverty_rate * 100, 1) AS poverty_pct,
  ROUND(t.no_vehicle_rate * 100, 1) AS no_vehicle_pct,
  ROUND(t.assistance_rate * 100, 1) AS public_assistance_pct,
  ROUND(
    (t.poverty_rate / AVG(t.poverty_rate) OVER ()) * 0.6 +
    (t.no_vehicle_rate / AVG(t.no_vehicle_rate) OVER ()) * 0.4,
    2
  ) AS relative_need_multiplier
FROM `a4i_econ.tract_demographics` t
LEFT JOIN tract_storefronts ts
  ON LPAD(CAST(t.geo_id AS STRING), 11, '0') = ts.tract_geoid
ORDER BY relative_need_multiplier DESC;


-- ----------------------------------------------------------------------------
-- AUDIT 4: Real SBA 7(a) Loan & Charge-Off Ground-Truth Check (`borrowed_from`)
-- ----------------------------------------------------------------------------
SELECT
  l.edge_id,
  b.business_id,
  b.name,
  b.address,
  b.naics4,
  l.block_id AS nearest_employer_block_id,
  e.jobs AS block_wac_jobs,
  l.bank_name,
  l.gross_approval,
  l.approval_date,
  l.loan_status,
  l.charged_off
FROM `a4i_econ.borrowed_from` l
JOIN `a4i_econ.businesses` b ON b.business_id = l.business_id
LEFT JOIN `a4i_econ.employer_blocks` e ON e.block_id = l.block_id
ORDER BY l.charged_off DESC, l.gross_approval DESC;
