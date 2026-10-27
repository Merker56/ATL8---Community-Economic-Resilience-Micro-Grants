-- ============================================================================
-- A4I 2026 — Challenge 3: Community Economic Resilience & Micro-Grants
-- Corridor: Market/Castro (San Francisco, CA)
-- File: sql/01_create_property_graph.sql
-- ============================================================================
--
-- Property Graph Schema (`a4i_econ.LocalEconomy`):
--   Node Tables (2):
--     1. `businesses` (KEY (business_id)): 327 active privacy-filtered storefronts across 62 NAICS4 industries.
--     2. `employer_blocks` (KEY (block_id)): 10 LODES 8 workplace Census blocks totaling 1,842 storefront jobs (5,041 total WAC jobs).
--   Edge Tables (3):
--     1. `supplies` (SOURCE KEY (supplier_id) REFERENCES businesses, DESTINATION KEY (buyer_id) REFERENCES businesses):
--        1,199 directed edges (gravity_intensity = bea_use_share * exp(-metres / 500)).
--     2. `draws_footfall_from` (SOURCE KEY (business_id) REFERENCES businesses, DESTINATION KEY (block_id) REFERENCES employer_blocks):
--        677 gravity-weighted footfall edges.
--     3. `borrowed_from` (SOURCE KEY (business_id) REFERENCES businesses, DESTINATION KEY (block_id) REFERENCES employer_blocks):
--        9 historical SBA 7(a) loans (2 verified charge-offs).
--   Relational Join Table (1):
--     1. `tract_demographics`: 8 ACS 5-Year Census Tracts joined via LPAD(CAST(geo_id AS STRING), 11, '0').
--
-- Pre-Flight Checklist (The 7 BigQuery Property Graph Traps):
--   1. In NODE TABLES and EDGE TABLES, write `a4i_econ.businesses`
--      DATASET-QUALIFIED and UNBACKTICKED. Do NOT wrap a 3-part name in backticks.
--   2. In REFERENCES, use the UNQUALIFIED node table name:
--      `REFERENCES businesses (business_id)` (no `a4i_econ.` prefix).
--   3. Element keys (`business_id`, `block_id`, `edge_id`) MUST be unique and
--      non-null; BigQuery does not enforce uniqueness and silently multiplies paths.
--   4. Property names are GLOBAL across the graph and must agree on data type:
--      `employer_blocks.jobs` is INT64, whereas `draws_footfall_from.worker_share`
--      is FLOAT64. Never expose both as `jobs`.
-- ============================================================================

-- Step 0A: Idempotent schema enrichment on `a4i_econ.businesses` for tract & hygiene flags
ALTER TABLE `a4i_econ.businesses`
  ADD COLUMN IF NOT EXISTS tract_geoid STRING,
  ADD COLUMN IF NOT EXISTS is_virtual_mailbox_hub BOOL,
  ADD COLUMN IF NOT EXISTS corridor_naics4_peers INT64;

-- Step 0B: Idempotent schema enrichment on `a4i_econ.employer_blocks` for corridor storefront jobs (1,842 total)
ALTER TABLE `a4i_econ.employer_blocks`
  ADD COLUMN IF NOT EXISTS corridor_storefront_jobs INT64;

-- Step 0C: Idempotent schema enrichment on `a4i_econ.supplies` for +10 Bonus Merchant Intake & distance-decay intensity
ALTER TABLE `a4i_econ.supplies`
  ADD COLUMN IF NOT EXISTS bea_use_share FLOAT64,
  ADD COLUMN IF NOT EXISTS gravity_intensity FLOAT64,
  ADD COLUMN IF NOT EXISTS edge_origin STRING,
  ADD COLUMN IF NOT EXISTS is_verified BOOL;

UPDATE `a4i_econ.supplies`
SET
  bea_use_share = COALESCE(bea_use_share, intensity),
  gravity_intensity = COALESCE(gravity_intensity, ROUND(intensity * EXP(-metres / 500.0), 6)),
  edge_origin = COALESCE(edge_origin, 'MODELED_BEA'),
  is_verified = COALESCE(is_verified, FALSE)
WHERE edge_origin IS NULL OR is_verified IS NULL OR gravity_intensity IS NULL;

-- Step 0D: Idempotent schema enrichment on `a4i_econ.draws_footfall_from` for gravity-weighted footfall
ALTER TABLE `a4i_econ.draws_footfall_from`
  ADD COLUMN IF NOT EXISTS gravity_weight FLOAT64,
  ADD COLUMN IF NOT EXISTS gravity_worker_share FLOAT64;

-- Step 0E: Idempotent schema enrichment on `a4i_econ.borrowed_from` so SBA 7(a) loans have `edge_id` & `block_id`
ALTER TABLE `a4i_econ.borrowed_from`
  ADD COLUMN IF NOT EXISTS edge_id STRING,
  ADD COLUMN IF NOT EXISTS block_id STRING,
  ADD COLUMN IF NOT EXISTS metres FLOAT64;

-- Step 1: Declare the Property Graph over the 2 Node Tables and 3 Edge Tables.
CREATE OR REPLACE PROPERTY GRAPH a4i_econ.LocalEconomy
  NODE TABLES (
    a4i_econ.businesses
      KEY (business_id)
      LABEL Business
      PROPERTIES (
        business_id,
        name,
        legal_name,
        address,
        zip,
        naics,
        naics4,
        corridor,
        latitude,
        longitude,
        tract_geoid,
        is_virtual_mailbox_hub,
        corridor_naics4_peers
      ),
    a4i_econ.employer_blocks
      KEY (block_id)
      LABEL EmployerBlock
      PROPERTIES (
        block_id,
        tract,
        jobs,
        corridor_storefront_jobs,
        lat,
        lon
      )
  )
  EDGE TABLES (
    a4i_econ.supplies
      KEY (edge_id)
      SOURCE KEY (supplier_id) REFERENCES businesses (business_id)
      DESTINATION KEY (buyer_id) REFERENCES businesses (business_id)
      LABEL Supplies
      PROPERTIES (
        edge_id,
        bea_use_share,
        intensity,
        gravity_intensity,
        metres,
        edge_origin,
        is_verified
      ),
    a4i_econ.draws_footfall_from
      KEY (edge_id)
      SOURCE KEY (business_id) REFERENCES businesses (business_id)
      DESTINATION KEY (block_id) REFERENCES employer_blocks (block_id)
      LABEL DrawsFootfall
      PROPERTIES (
        edge_id,
        worker_share,
        gravity_weight,
        gravity_worker_share,
        metres
      ),
    a4i_econ.borrowed_from
      KEY (edge_id)
      SOURCE KEY (business_id) REFERENCES businesses (business_id)
      DESTINATION KEY (block_id) REFERENCES employer_blocks (block_id)
      LABEL BorrowedFrom
      PROPERTIES (
        edge_id,
        bank_name,
        gross_approval,
        approval_date,
        loan_status,
        charged_off,
        metres
      )
  );
