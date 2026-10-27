-- =============================================================================
-- A4I 2026 Challenge 3 — Equity, Industry Bias & SBA Ground-Truth Audits
--
-- Covers the 25-point "Rigor & Judgment" rubric:
-- 1. Mechanical Industry Bias Audit (Section 10): Proves whether the BEA edge
--    generator over-recommends input-heavy sectors (restaurants, manufacturing)
--    relative to the corridor's true business mix.
-- 2. Neighborhood Equity Audit (Section 9 & 10): Compares ACS poverty,
--    no-vehicle, and public-assistance rates across corridor tracts.
-- 3. SBA 7(a) Loan & Charge-Off Ground Truth (Section 6): Inspects the ONLY
--    fully-real B2B relationship and real business failure outcomes.
-- =============================================================================

-- Audit 1: Mechanical Industry Bias (Top 2-Hop Cascade Suppliers vs. Corridor Baseline)
WITH corridor_mix AS (
  SELECT
    SUBSTR(naics4, 1, 2) AS naics2,
    CASE SUBSTR(naics4, 1, 2)
      WHEN '72' THEN '72 - Food Services & Drinking Places'
      WHEN '44' THEN '44-45 - Retail Trade'
      WHEN '45' THEN '44-45 - Retail Trade'
      WHEN '31' THEN '31-33 - Manufacturing & Micro-Producers'
      WHEN '32' THEN '31-33 - Manufacturing & Micro-Producers'
      WHEN '33' THEN '31-33 - Manufacturing & Micro-Producers'
      WHEN '54' THEN '54 - Professional & Technical Services'
      WHEN '81' THEN '81 - Personal & Repair Services'
      WHEN '71' THEN '71 - Arts, Entertainment & Recreation'
      WHEN '51' THEN '51 - Information'
      WHEN '62' THEN '62 - Health Care & Social Assistance'
      ELSE CONCAT(SUBSTR(naics4, 1, 2), ' - Other')
    END AS sector_label,
    COUNT(*) AS corridor_businesses
  FROM `a4i_econ.businesses`
  GROUP BY naics2, sector_label
),
cascade_suppliers AS (
  SELECT DISTINCT a.supplier_id
  FROM `a4i_econ.supplies` a
  JOIN `a4i_econ.supplies` b ON b.supplier_id = a.buyer_id
  WHERE b.buyer_id != a.supplier_id
),
recommended_mix AS (
  SELECT
    SUBSTR(b.naics4, 1, 2) AS naics2,
    COUNT(*) AS cascade_businesses
  FROM cascade_suppliers cs
  JOIN `a4i_econ.businesses` b ON b.business_id = cs.supplier_id
  GROUP BY naics2
),
totals AS (
  SELECT
    (SELECT COUNT(*) FROM `a4i_econ.businesses`) AS total_corridor,
    (SELECT COUNT(*) FROM cascade_suppliers) AS total_cascade
)
SELECT
  c.sector_label,
  c.corridor_businesses,
  ROUND(SAFE_DIVIDE(c.corridor_businesses, t.total_corridor) * 100, 1) AS corridor_share_pct,
  COALESCE(r.cascade_businesses, 0) AS businesses_with_2hop_cascade,
  ROUND(SAFE_DIVIDE(COALESCE(r.cascade_businesses, 0), t.total_cascade) * 100, 1) AS cascade_share_pct,
  ROUND(
    SAFE_DIVIDE(
      SAFE_DIVIDE(COALESCE(r.cascade_businesses, 0), t.total_cascade),
      SAFE_DIVIDE(c.corridor_businesses, t.total_corridor)
    ),
    2
  ) AS representation_ratio,
  CASE
    WHEN SAFE_DIVIDE(
      SAFE_DIVIDE(COALESCE(r.cascade_businesses, 0), t.total_cascade),
      SAFE_DIVIDE(c.corridor_businesses, t.total_corridor)
    ) >= 1.5 THEN 'OVER-REPRESENTED (BEA Input-Heavy Bias)'
    WHEN COALESCE(r.cascade_businesses, 0) = 0
      OR SAFE_DIVIDE(
        SAFE_DIVIDE(COALESCE(r.cascade_businesses, 0), t.total_cascade),
        SAFE_DIVIDE(c.corridor_businesses, t.total_corridor)
      ) <= 0.5 THEN 'UNDER-REPRESENTED (Service-Light / Leaf Blindspot)'
    ELSE 'BALANCED'
  END AS bias_diagnosis
FROM corridor_mix c
CROSS JOIN totals t
LEFT JOIN recommended_mix r ON r.naics2 = c.naics2
ORDER BY corridor_businesses DESC;

-- =============================================================================
-- Audit 2: Census Tract Need & Equity Profile (Using LPAD(geo_id, 11, '0'))
-- =============================================================================
SELECT
  LPAD(t.geo_id, 11, '0') AS tract_geo_id,
  CAST(t.total_pop AS INT64) AS total_pop,
  CAST(t.median_income AS INT64) AS median_income,
  ROUND(t.poverty_rate * 100, 1) AS poverty_rate_pct,
  ROUND(t.no_vehicle_rate * 100, 1) AS no_vehicle_rate_pct,
  ROUND(t.assistance_rate * 100, 1) AS public_assistance_pct,
  ROUND(
    AVG(t.poverty_rate) OVER () * 100, 1
  ) AS corridor_mean_poverty_pct,
  IF(
    t.poverty_rate >= AVG(t.poverty_rate) OVER (),
    'HIGH_NEED_PRIORITY_TRACT',
    'BELOW_CORRIDOR_MEAN_POVERTY'
  ) AS equity_tier
FROM `a4i_econ.tract_demographics` t
ORDER BY t.poverty_rate DESC;

-- =============================================================================
-- Audit 3: Real SBA 7(a) Loans & Charge-Off Ground Truth (`borrowed_from`)
-- =============================================================================
SELECT
  b.business_id,
  b.name AS business_name,
  b.address,
  b.naics4,
  l.bank_name,
  l.gross_approval,
  l.approval_date,
  l.loan_status,
  l.charged_off,
  (SELECT COUNT(DISTINCT s.buyer_id) FROM `a4i_econ.supplies` s WHERE s.supplier_id = b.business_id) AS direct_buyers_downstream,
  (SELECT COUNT(DISTINCT s.supplier_id) FROM `a4i_econ.supplies` s WHERE s.buyer_id = b.business_id) AS direct_suppliers_upstream
FROM `a4i_econ.borrowed_from` l
JOIN `a4i_econ.businesses` b ON b.business_id = l.business_id
ORDER BY l.charged_off DESC, l.gross_approval DESC;
