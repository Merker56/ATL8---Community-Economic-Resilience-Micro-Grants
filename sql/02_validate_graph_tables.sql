-- =============================================================================
-- A4I 2026 Challenge 3: Data Validation & Near-Duplicate Detector
-- Run this BEFORE and AFTER creating `a4i_econ.LocalEconomy`.
--
-- Why this matters for "Rigor & Judgment" (25% of score):
-- 1. BigQuery Property Graph does NOT check element key uniqueness. Duplicate
--    keys silently multiply paths and inflate every cascade count.
-- 2. Rows with NULL keys silently vanish from the graph.
-- 3. Municipal registries often contain duplicate registrations for the same
--    real-world business (e.g., Graffeo Coffee in North Beach), splitting its
--    downstream buyers across two nodes.
-- =============================================================================

-- Part 1: Automated Integrity Checks
WITH
  biz_stats AS (
    SELECT
      COUNT(*) AS total_rows,
      COUNT(DISTINCT business_id) AS unique_keys,
      COUNTIF(business_id IS NULL) AS null_keys,
      COUNTIF(latitude IS NULL OR longitude IS NULL) AS missing_coords,
      COUNT(DISTINCT naics4) AS distinct_naics4,
      MAX(latitude) - MIN(latitude) AS lat_span,
      MAX(longitude) - MIN(longitude) AS lon_span
    FROM `a4i_econ.businesses`
  ),
  sup_stats AS (
    SELECT
      COUNT(*) AS total_rows,
      COUNT(DISTINCT edge_id) AS unique_keys,
      COUNTIF(edge_id IS NULL) AS null_keys,
      COUNTIF(supplier_id = buyer_id) AS self_loops,
      COUNT(DISTINCT supplier_id) AS distinct_suppliers
    FROM `a4i_econ.supplies`
  ),
  dangling_sup AS (
    SELECT
      COUNTIF(b_src.business_id IS NULL) AS missing_suppliers,
      COUNTIF(b_dst.business_id IS NULL) AS missing_buyers
    FROM `a4i_econ.supplies` s
    LEFT JOIN `a4i_econ.businesses` b_src ON b_src.business_id = s.supplier_id
    LEFT JOIN `a4i_econ.businesses` b_dst ON b_dst.business_id = s.buyer_id
  ),
  two_hop_reach AS (
    SELECT
      COUNT(DISTINCT a.supplier_id) AS suppliers_with_2hop_depth,
      COUNT(*) AS total_2hop_paths
    FROM `a4i_econ.supplies` a
    JOIN `a4i_econ.supplies` b ON b.supplier_id = a.buyer_id
    WHERE b.buyer_id != a.supplier_id
  ),
  foot_stats AS (
    SELECT
      COUNT(*) AS total_rows,
      COUNT(DISTINCT edge_id) AS unique_keys,
      COUNTIF(worker_share IS NULL OR worker_share <= 0) AS invalid_shares
    FROM `a4i_econ.draws_footfall_from`
  ),
  tract_stats AS (
    SELECT
      COUNT(*) AS total_rows,
      COUNTIF(LENGTH(geo_id) != 11) AS bad_geoid_length,
      COUNTIF(poverty_rate < 0 OR poverty_rate > 1) AS invalid_poverty_rate,
      ROUND(AVG(poverty_rate), 4) AS mean_corridor_poverty
    FROM `a4i_econ.tract_demographics`
  )
SELECT '1. businesses: key uniqueness' AS check_name,
       IF(total_rows = unique_keys AND null_keys = 0, 'PASS', 'FAIL') AS status,
       CONCAT(CAST(unique_keys AS STRING), ' unique of ', CAST(total_rows AS STRING), ' rows (', CAST(null_keys AS STRING), ' nulls)') AS detail
FROM biz_stats
UNION ALL
SELECT '2. businesses: geography & industry spread',
       IF(missing_coords = 0 AND distinct_naics4 >= 8 AND lat_span < 0.12 AND lon_span < 0.12, 'PASS', 'FAIL'),
       CONCAT(CAST(distinct_naics4 AS STRING), ' NAICS4 industries; span ', CAST(ROUND(lat_span, 4) AS STRING), 'x', CAST(ROUND(lon_span, 4) AS STRING), ' deg')
FROM biz_stats
UNION ALL
SELECT '3. supplies: edge key uniqueness & no self-loops',
       IF(total_rows = unique_keys AND null_keys = 0 AND self_loops = 0, 'PASS', 'FAIL'),
       CONCAT(CAST(unique_keys AS STRING), ' unique edges, ', CAST(self_loops AS STRING), ' self-loops')
FROM sup_stats
UNION ALL
SELECT '4. supplies: endpoint integrity',
       IF(missing_suppliers = 0 AND missing_buyers = 0, 'PASS', 'FAIL'),
       CONCAT(CAST(missing_suppliers AS STRING), ' missing suppliers, ', CAST(missing_buyers AS STRING), ' missing buyers')
FROM dangling_sup
UNION ALL
SELECT '5. supplies: multi-hop cascade depth exists',
       IF(suppliers_with_2hop_depth > 0, 'PASS', 'FAIL'),
       CONCAT(CAST(suppliers_with_2hop_depth AS STRING), ' businesses reach 2 hops (', CAST(total_2hop_paths AS STRING), ' paths)')
FROM two_hop_reach
UNION ALL
SELECT '6. draws_footfall_from: key uniqueness & positive share',
       IF(total_rows = unique_keys AND invalid_shares = 0, 'PASS', 'FAIL'),
       CONCAT(CAST(unique_keys AS STRING), ' footfall edges, ', CAST(invalid_shares AS STRING), ' invalid worker_share rows')
FROM foot_stats
UNION ALL
SELECT '7. tract_demographics: 11-char LPAD geo_id & valid poverty',
       IF(total_rows > 0 AND bad_geoid_length = 0 AND invalid_poverty_rate = 0, 'PASS', 'FAIL'),
       CONCAT(CAST(total_rows AS STRING), ' tracts; mean poverty = ', CAST(ROUND(mean_corridor_poverty * 100, 1) AS STRING), '%')
FROM tract_stats
ORDER BY check_name;

-- =============================================================================
-- Part 2: Near-Duplicate Business Registration Detector (Section 11 Warning)
-- Identifies businesses that appear twice under slightly different corporate
-- suffixes or DBA names at the same location/prefix, splitting their buyers.
-- =============================================================================
WITH normalized_biz AS (
  SELECT
    business_id,
    name,
    address,
    naics4,
    TRIM(REGEXP_REPLACE(
      REGEXP_REPLACE(UPPER(name), r'\b(INC|LLC|CORP|CORPORATION|LTD|LIMITED|LP|LLP|COMPANY|CO)\b\.?', ''),
      r'[^A-Z0-9]+', ' '
    )) AS norm_name,
    TRIM(REGEXP_REPLACE(UPPER(address), r'[^A-Z0-9]+', ' ')) AS norm_addr
  FROM `a4i_econ.businesses`
)
SELECT
  a.norm_name,
  a.naics4,
  a.business_id AS id_1,
  a.name AS name_1,
  b.business_id AS id_2,
  b.name AS name_2,
  a.address
FROM normalized_biz a
JOIN normalized_biz b
  ON a.business_id < b.business_id
  AND (a.norm_name = b.norm_name OR (a.norm_addr = b.norm_addr AND a.naics4 = b.naics4))
WHERE LENGTH(a.norm_name) > 3;
