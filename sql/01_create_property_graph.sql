-- ============================================================================
-- A4I 2026 — Challenge 3: Community Economic Resilience & Micro-Grants
-- Corridor: Market/Castro (San Francisco, CA)
-- File: sql/01_create_property_graph.sql
-- ============================================================================
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

-- Step 0: Optional schema extension on `a4i_econ.supplies` to support the
-- +10 Bonus Conversational Merchant Supplier Intake tool (`is_verified`, `edge_origin`).
ALTER TABLE `a4i_econ.supplies`
  ADD COLUMN IF NOT EXISTS edge_origin STRING,
  ADD COLUMN IF NOT EXISTS is_verified BOOL;

-- Step 1: Declare the Property Graph over the loaded Market/Castro tables.
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
        longitude
      ),
    a4i_econ.employer_blocks
      KEY (block_id)
      LABEL Employer
      PROPERTIES (
        block_id,
        tract,
        jobs,
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
        intensity,
        metres
      ),
    a4i_econ.draws_footfall_from
      KEY (edge_id)
      SOURCE KEY (block_id) REFERENCES employer_blocks (block_id)
      DESTINATION KEY (business_id) REFERENCES businesses (business_id)
      LABEL DrawsFootfall
      PROPERTIES (
        edge_id,
        worker_share,
        metres
      )
  );
