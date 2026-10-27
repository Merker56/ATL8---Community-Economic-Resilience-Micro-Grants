#!/usr/bin/env bash
# =============================================================================
# A4I 2026 Challenge 3: Data Track One-Command Setup & Graph Builder
#
# Runs:
#   1. scripts/load.sh <corridor> (loads 6 tables + creates Enterprise reservation)
#   2. sql/01_create_graph.sql (creates `a4i_econ.LocalEconomy` property graph)
#   3. sql/02_validate_graph_tables.sql (runs 7 integrity checks + duplicate check)
#   4. Prints ready-to-use "Golden Seed IDs" for Track 1, Track 2, and Track 3
#
# Usage:
#   bash scripts/setup_data_and_graph.sh [corridor]
# =============================================================================

set -euo pipefail

RAW_CORRIDOR="${1:-central-market}"
CORRIDOR="$(echo "${RAW_CORRIDOR}" | tr '[:upper:] /' '[:lower:]--')"
LOCATION="US"
DATASET="a4i_econ"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

bold "=== Step 1/4: Loading BigQuery tables & reservation for '${CORRIDOR}' ==="
bash "${REPO_ROOT}/scripts/load.sh" "${CORRIDOR}"

PROJECT_ID="$(gcloud config get-value project 2>/dev/null || true)"

bold "=== Step 2/4: Creating Property Graph ${DATASET}.LocalEconomy ==="
bq --project_id="${PROJECT_ID}" --location="${LOCATION}" \
   query --use_legacy_sql=false \
   < "${REPO_ROOT}/sql/01_create_graph.sql"
info "Property Graph ${DATASET}.LocalEconomy created."
echo

bold "=== Step 3/4: Running Validation & Duplicate Registration Checks ==="
bq --project_id="${PROJECT_ID}" --location="${LOCATION}" \
   query --use_legacy_sql=false \
   < "${REPO_ROOT}/sql/02_validate_graph_tables.sql"
echo

bold "=== Step 4/4: Extracting Golden Seed IDs for All 3 Tracks ==="
info "1. Top Sweet-Spot Suppliers (Track 1 Applicants & Track 2 Micro-Producers):"
bq --project_id="${PROJECT_ID}" --location="${LOCATION}" \
   query --use_legacy_sql=false \
   "WITH one_hop AS (
      SELECT supplier_id AS root, buyer_id AS reached, 1 AS hops FROM \`${PROJECT_ID}.${DATASET}.supplies\`
    ),
    two_hop AS (
      SELECT a.supplier_id AS root, b.buyer_id AS reached, 2 AS hops
      FROM \`${PROJECT_ID}.${DATASET}.supplies\` a
      JOIN \`${PROJECT_ID}.${DATASET}.supplies\` b ON b.supplier_id = a.buyer_id
      WHERE b.buyer_id != a.supplier_id
    ),
    reach AS (SELECT * FROM one_hop UNION ALL SELECT * FROM two_hop)
    SELECT b.business_id, b.name, b.naics4,
           COUNT(DISTINCT IF(hops = 1, reached, NULL)) AS direct_1hop,
           COUNT(DISTINCT reached) AS total_2hop,
           CASE
             WHEN COUNT(DISTINCT reached) > 25 THEN 'GIANT_HUB (Test Hub-Avoidance)'
             WHEN COUNT(DISTINCT reached) BETWEEN 5 AND 25 THEN 'SWEET_SPOT (Target Recommendation)'
             ELSE 'SMALL_SUPPLIER'
           END AS demo_role
    FROM reach r
    JOIN \`${PROJECT_ID}.${DATASET}.businesses\` b ON b.business_id = r.root
    GROUP BY b.business_id, b.name, b.naics4
    ORDER BY total_2hop DESC
    LIMIT 12;"

echo
info "2. Sample Leaf Businesses (0 downstream supply edges - Test Refusal / Honest Comparison):"
bq --project_id="${PROJECT_ID}" --location="${LOCATION}" \
   query --use_legacy_sql=false \
   "SELECT b.business_id, b.name, b.naics4, b.address
    FROM \`${PROJECT_ID}.${DATASET}.businesses\` b
    LEFT JOIN \`${PROJECT_ID}.${DATASET}.supplies\` s ON s.supplier_id = b.business_id
    WHERE s.supplier_id IS NULL
    LIMIT 5;"

echo
info "3. Top Employer Blocks (Track 3 Anchor Closure Seeds):"
bq --project_id="${PROJECT_ID}" --location="${LOCATION}" \
   query --use_legacy_sql=false \
   "SELECT e.block_id, e.tract, e.jobs, COUNT(DISTINCT f.business_id) AS frontline_businesses
    FROM \`${PROJECT_ID}.${DATASET}.employer_blocks\` e
    JOIN \`${PROJECT_ID}.${DATASET}.draws_footfall_from\` f ON f.block_id = e.block_id
    GROUP BY e.block_id, e.tract, e.jobs
    ORDER BY e.jobs DESC
    LIMIT 5;"

bold "=== Data Track Setup Complete! ==="
