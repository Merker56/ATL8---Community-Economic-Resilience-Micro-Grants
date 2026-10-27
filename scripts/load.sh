#!/usr/bin/env bash
#
# A4I 2026 - Challenge 3: Community Economic Resilience & Micro-Grants
# Headless fallback for notebooks/c3_01_load_explore.ipynb
#
# Rebuilds the same BigQuery tables the notebook produces, from a pre-staged
# snapshot in Cloud Storage. Use this when a Colab Enterprise runtime is slow or
# unavailable, or when one of the upstream publishers is not cooperating.
#
# Run it from the repo root in Cloud Shell (no chmod needed - invoke with bash):
#     bash scripts/load.sh                 # defaults to central-market
#     bash scripts/load.sh 24th-st
#     bash scripts/load.sh --list          # show available corridors
#
# You still want the notebook if you can run it. It explains which of the
# connections in your graph are measured and which are modeled, and you will be
# asked about that. This script gets you the same tables without the teaching.

set -euo pipefail

BUCKET="gs://class-demo/a4i-2026/challenge-3-micro-grants"
DATASET="a4i_econ"
LOCATION="US"
TABLES=(businesses employer_blocks supplies draws_footfall_from borrowed_from tract_demographics)

# Tables that must have rows for the challenge to be doable at all. borrowed_from
# can legitimately be empty - a corridor where nobody took an SBA loan is a real
# corridor - so it is loaded but not required.
REQUIRED=(businesses supplies tract_demographics)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
info()  { printf '  %s\n' "$*"; }
fail()  { printf '\n\033[1mERROR:\033[0m %s\n\n%s\n\n' "$*" \
          "This script is safe to run again - every table load replaces whatever was there." >&2
          exit 1; }

on_interrupt() {
  printf '\n\n\033[1mInterrupted.\033[0m Nothing is broken.\n'
  printf 'Every load replaces the whole table, so just run this script again:\n'
  printf '    bash scripts/load.sh %s\n\n' "${CORRIDOR:-<corridor>}"
  exit 130
}
trap on_interrupt INT TERM

list_corridors() {
  bold "Corridors available in the snapshot"
  if ! gcloud storage ls "${BUCKET}/" 2>/dev/null | sed 's|.*/\([^/]*\)/$|  \1|' | grep -v '^\s*$'; then
    fail "Could not list ${BUCKET}/. Check that you have network access."
  fi
  echo
  echo "Usage: bash scripts/load.sh <corridor>"
}

# --------------------------------------------------------------------------
# Arguments
# --------------------------------------------------------------------------
CORRIDOR="${1:-central-market}"

if [[ "${CORRIDOR}" == "--list" || "${CORRIDOR}" == "-l" ]]; then
  list_corridors
  exit 0
fi

if [[ "${CORRIDOR}" == "--help" || "${CORRIDOR}" == "-h" ]]; then
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

CORRIDOR="$(echo "${CORRIDOR}" | tr '[:upper:] ' '[:lower:]-')"
SRC="${BUCKET}/${CORRIDOR}"

# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------
bold "A4I Challenge 3 - loading data for: ${CORRIDOR}"
echo

command -v bq     >/dev/null 2>&1 || fail "'bq' not found. Run this in Cloud Shell."
command -v gcloud >/dev/null 2>&1 || fail "'gcloud' not found. Run this in Cloud Shell."

PROJECT_ID="$(gcloud config get-value project 2>/dev/null || true)"
[[ -n "${PROJECT_ID}" && "${PROJECT_ID}" != "(unset)" ]] \
  || fail "No project set. Run: gcloud config set project YOUR_PROJECT_ID"

info "Project  : ${PROJECT_ID}"
info "Source   : ${SRC}"
info "Dataset  : ${DATASET} (${LOCATION})"
echo

if ! gcloud storage ls "${SRC}/" >/dev/null 2>&1; then
  echo
  bold "No snapshot found for '${CORRIDOR}'."
  echo
  list_corridors
  exit 1
fi

# --------------------------------------------------------------------------
# A graph-capable reservation
# --------------------------------------------------------------------------
# BigQuery Graph queries (GQL / GRAPH_TABLE) run only under an Enterprise or
# Enterprise Plus edition reservation (since October 2026). A fresh project is
# on-demand and has none. Zero baseline slots plus autoscaling costs nothing idle.
# Both commands are idempotent: "already exists" is success.
bold "0/3  Graph-capable reservation"
RESERVATION="a4i-graph"
gcloud services enable bigqueryreservation.googleapis.com --project="${PROJECT_ID}" --quiet >/dev/null 2>&1 \
  || info "could not enable bigqueryreservation.googleapis.com (may already be on)"
if bq --project_id="${PROJECT_ID}" --location="${LOCATION}" show --reservation "${RESERVATION}" >/dev/null 2>&1; then
  info "reservation ${RESERVATION} already exists - reusing it"
else
  bq --project_id="${PROJECT_ID}" --location="${LOCATION}" mk --reservation \
     --edition=ENTERPRISE --slots=0 --autoscale_max_slots=50 --ignore_idle_slots=true "${RESERVATION}" \
     && info "created reservation ${RESERVATION} (Enterprise, 0 baseline, autoscale to 50)" \
     || fail "could not create the reservation. Graph queries will fail until one exists; tell a coach."
fi
if bq --project_id="${PROJECT_ID}" --location="${LOCATION}" ls --reservation_assignment 2>/dev/null \
     | grep -q "${RESERVATION}"; then
  info "this project is already assigned to ${RESERVATION}"
else
  bq --project_id="${PROJECT_ID}" --location="${LOCATION}" mk --reservation_assignment \
     --reservation_id="${PROJECT_ID}:${LOCATION}.${RESERVATION}" \
     --assignee_type=PROJECT --assignee_id="${PROJECT_ID}" --job_type=QUERY \
     && info "assigned this project's queries to ${RESERVATION} (takes about a minute to apply)" \
     || info "assignment not created (it may already exist) - if graph queries fail, tell a coach"
fi
echo

# --------------------------------------------------------------------------
# Create the dataset
# --------------------------------------------------------------------------
bold "1/3  Creating dataset"

# `bq ls -d NAME` does NOT ask "does this dataset exist". It lists the datasets
# inside a PROJECT called NAME, so it reports nothing for a dataset name and the
# script falls through to `mk`, which then dies on a dataset that is already
# there. That never shows up on a first run - it only bites on the second, which
# is exactly when you are re-running because something went wrong the first time.
# `show --dataset` with a fully qualified name is the question we actually mean.
dataset_exists() {
  bq --project_id="${PROJECT_ID}" show --dataset --format=none \
     "${PROJECT_ID}:${DATASET}" >/dev/null 2>&1
}

if dataset_exists; then
  info "${DATASET} already exists - reusing it"

  existing_loc="$(bq --project_id="${PROJECT_ID}" --format=json show --dataset \
                     "${PROJECT_ID}:${DATASET}" 2>/dev/null \
                  | tr ',' '\n' | grep -i '"location"' | head -1 \
                  | sed 's/.*: *"\([^"]*\)".*/\1/' || true)"
  if [[ -n "${existing_loc}" && "${existing_loc^^}" != "${LOCATION^^}" ]]; then
    fail "Dataset ${DATASET} already exists in '${existing_loc}', but this script loads into
       '${LOCATION}'. BigQuery cannot load across regions, and a property graph must live in
       the same location as its tables. Either delete the dataset
       (bq rm -r -d ${DATASET}) or edit LOCATION at the top of this script to match."
  fi
else
  # Belt and braces. If the check above ever misfires, or two teammates run this
  # in the same shared project at the same second, "already exists" is a fine
  # outcome and not an error. Anything else is.
  if mk_out="$(bq --project_id="${PROJECT_ID}" --location="${LOCATION}" \
                  mk --dataset "${PROJECT_ID}:${DATASET}" 2>&1)"; then
    info "created ${DATASET}"
  elif grep -qi "already exists" <<<"${mk_out}"; then
    info "${DATASET} already exists - reusing it"
  else
    fail "Could not create dataset ${DATASET}:
       ${mk_out}"
  fi
fi
echo

# --------------------------------------------------------------------------
# Load each table
# --------------------------------------------------------------------------
# Every load uses --replace, so re-running from scratch is always safe.
bold "2/3  Loading tables"
for table in "${TABLES[@]}"; do
  uri="${SRC}/${table}/*.parquet"

  if ! gcloud storage ls "${SRC}/${table}/" >/dev/null 2>&1; then
    if printf '%s\n' "${REQUIRED[@]}" | grep -qx "${table}"; then
      fail "Missing ${SRC}/${table}/. The snapshot for '${CORRIDOR}' looks incomplete - tell a coach."
    fi
    info "${table} not in this snapshot - skipping (optional)"
    continue
  fi

  info "loading ${table}..."
  bq --project_id="${PROJECT_ID}" --location="${LOCATION}" load \
     --source_format=PARQUET \
     --replace \
     "${DATASET}.${table}" \
     "${uri}" >/dev/null

  info "  done"
done
echo

# --------------------------------------------------------------------------
# Verify - never trust a load you did not check
# --------------------------------------------------------------------------
bold "3/3  Verifying"
FAILED=0
for table in "${TABLES[@]}"; do
  if ! bq --project_id="${PROJECT_ID}" show --format=none \
          "${PROJECT_ID}:${DATASET}.${table}" >/dev/null 2>&1; then
    printf '  %-22s %s\n' "${table}" "not loaded (optional)"
    continue
  fi

  rows="$(bq --project_id="${PROJECT_ID}" --location="${LOCATION}" \
            query --use_legacy_sql=false --format=csv \
            "SELECT COUNT(*) FROM \`${PROJECT_ID}.${DATASET}.${table}\`" \
          | tail -n 1)"

  if [[ "${rows}" == "0" ]] && printf '%s\n' "${REQUIRED[@]}" | grep -qx "${table}"; then
    printf '  %-22s %s\n' "${table}" "0 rows  <-- EMPTY"
    FAILED=1
  else
    printf '  %-22s %s rows\n' "${table}" "${rows}"
  fi
done
echo

# The one number that decides whether a multi-hop traversal finds anything at
# all. Every other check can pass on a graph where nothing connects to anything,
# which would load perfectly and traverse to nothing.
reach="$(bq --project_id="${PROJECT_ID}" --location="${LOCATION}" \
           query --use_legacy_sql=false --format=csv \
           "SELECT COUNT(DISTINCT a.supplier_id)
            FROM \`${PROJECT_ID}.${DATASET}.supplies\` a
            JOIN \`${PROJECT_ID}.${DATASET}.supplies\` b
              ON b.supplier_id = a.buyer_id
            WHERE b.buyer_id != a.supplier_id" \
         | tail -n 1 || echo "")"

if [[ -n "${reach}" ]]; then
  info "Businesses that reach someone two hops out: ${reach}"
  info "(If that were zero, your graph would load perfectly and your"
  info " cascade query would return nothing. It is the number to check.)"
  if [[ "${reach}" == "0" ]]; then
    FAILED=1
    info "  <-- ZERO. Tell a coach before you build on this."
  fi
fi
echo

if [[ "${FAILED}" -eq 1 ]]; then
  fail "One or more required tables loaded empty, or the graph has no depth. Tell a coach."
fi

bold "Ready."
echo
echo "  Your tables are in ${PROJECT_ID}.${DATASET}"
echo "  Safe to re-run at any time - each load replaces the whole table."
echo
echo "  IMPORTANT: the businesses are real and so are the loan relationships."
echo "  The supply and footfall edges are MODELED from published federal rates -"
echo "  the notebook explains exactly how, and judges look for it."
echo
echo "  Next: CREATE PROPERTY GRAPH over businesses + supplies, then traverse it."
echo "  See Section 13 of the notebook for the DDL shape and the seven traps."
echo
