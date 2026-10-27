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
-- AUDIT 3: Census Tract Socioeconomic Vulnerability (with LPAD 11-char guard)
-- ----------------------------------------------------------------------------
-- Always apply `LPAD(geo_id, 11, '0')` to prevent California's leading '0' in
-- FIPS '06' from being stripped and silently failing the join.
SELECT
  LPAD(CAST(geo_id AS STRING), 11, '0') AS tract_geoid,
  ROUND(total_pop, 0) AS total_pop,
  ROUND(median_income, 0) AS median_income,
  ROUND(poverty_rate * 100, 1) AS poverty_pct,
  ROUND(no_vehicle_rate * 100, 1) AS no_vehicle_pct,
  ROUND(assistance_rate * 100, 1) AS public_assistance_pct,
  ROUND(
    (poverty_rate / AVG(poverty_rate) OVER ()) * 0.5 +
    (no_vehicle_rate / AVG(no_vehicle_rate) OVER ()) * 0.3 +
    (assistance_rate / AVG(assistance_rate) OVER ()) * 0.2,
    2
  ) AS relative_need_multiplier
FROM `a4i_econ.tract_demographics`
ORDER BY relative_need_multiplier DESC;


-- ----------------------------------------------------------------------------
-- AUDIT 4: Real SBA 7(a) Loan & Charge-Off Ground-Truth Check
-- ----------------------------------------------------------------------------
SELECT
  b.business_id,
  b.name,
  b.address,
  b.naics4,
  l.bank_name,
  l.gross_approval,
  l.approval_date,
  l.loan_status,
  l.charged_off
FROM `a4i_econ.borrowed_from` l
JOIN `a4i_econ.businesses` b ON b.business_id = l.business_id
ORDER BY l.charged_off DESC, l.gross_approval DESC;
