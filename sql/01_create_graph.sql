-- =============================================================================
-- A4I 2026 Challenge 3: Unified BigQuery Property Graph DDL
-- Dataset: a4i_econ | Graph: a4i_econ.LocalEconomy
--
-- Trap Checklist (from Notebook Section 13):
-- 1. NODE TABLES and EDGE TABLES use `a4i_econ.<table>` (dataset-qualified, NO backticks).
-- 2. REFERENCES clauses use `<table> (<key>)` (NO dataset prefix).
-- 3. `employer_blocks` exposes `jobs` (INT64) while `draws_footfall_from` exposes
--    `worker_share` (FLOAT64) so global property types never conflict.
-- =============================================================================

CREATE OR REPLACE PROPERTY GRAPH a4i_econ.LocalEconomy
  NODE TABLES (
    a4i_econ.businesses
      KEY (business_id)
      LABEL Business PROPERTIES (
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
      LABEL Employer PROPERTIES (
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
      LABEL Supplies PROPERTIES (
        edge_id,
        intensity,
        metres
      ),
    a4i_econ.draws_footfall_from
      KEY (edge_id)
      SOURCE KEY (block_id) REFERENCES employer_blocks (block_id)
      DESTINATION KEY (business_id) REFERENCES businesses (business_id)
      LABEL DrawsFootfall PROPERTIES (
        edge_id,
        worker_share,
        metres
      )
  );
