#!/usr/bin/env bash
# ==============================================================================
# ATL8 - Challenge 3: Community Economic Resilience & Micro-Grants
# Early Cloud Run Deployment Script (--min-instances=1 to prevent cold starts)
# Pre-configured with values from qwiklabs-gcp-03-46ba9aeed89b (187574395280)
# ==============================================================================
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-qwiklabs-gcp-03-46ba9aeed89b}"
PROJECT_NUMBER="${PROJECT_NUMBER:-187574395280}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-east1}"
SERVICE_NAME="${SERVICE_NAME:-atl8-grant-officer-agent}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"
VPC_CONNECTOR="projects/${PROJECT_ID}/locations/${REGION}/connectors/shared-cloudrun-connector"
BQ_DATASET="${BQ_DATASET:-a4i_econ}"
BQ_LOCATION="${BQ_LOCATION:-US}"
BQ_GRAPH="${BQ_GRAPH:-LocalEconomy}"

# Locate repo root so build includes both data/ and agent/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(basename "${SCRIPT_DIR}")" == "agent" || "$(basename "${SCRIPT_DIR}")" == "scripts" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
else
  REPO_ROOT="${SCRIPT_DIR}"
fi

echo "======================================================================"
echo " Deploying ADK Agent + Grant Officer UI to Cloud Run"
echo "----------------------------------------------------------------------"
echo " Project ID      : ${PROJECT_ID}"
echo " Project Number  : ${PROJECT_NUMBER}"
echo " Region          : ${REGION}"
echo " Service Name    : ${SERVICE_NAME}"
echo " Service Account : ${SERVICE_ACCOUNT}"
echo " Min Instances   : 1 (warm container - zero cold starts for demo)"
echo " Max Instances   : 2"
echo "======================================================================"

gcloud config set project "${PROJECT_ID}"

# Enable required services idempotently
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  bigqueryreservation.googleapis.com \
  --project="${PROJECT_ID}" --quiet || true

# Check if VPC connector exists in this project/region; include it if present
VPC_FLAGS=()
if gcloud compute networks vpc-access connectors describe shared-cloudrun-connector \
     --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Found VPC connector: ${VPC_CONNECTOR}"
  VPC_FLAGS=(
    "--vpc-connector=${VPC_CONNECTOR}"
    "--vpc-egress=private-ranges-only"
  )
fi

cd "${REPO_ROOT}"

# Step 1: Ensure Member 1's BigQuery dataset & Property Graph exist in production
if command -v bq >/dev/null 2>&1; then
  echo "----------------------------------------------------------------------"
  echo " Verifying Member 1 BigQuery Dataset (${PROJECT_ID}:${BQ_DATASET}) & Property Graph..."
  echo "----------------------------------------------------------------------"
  bq --project_id="${PROJECT_ID}" mk --dataset --force "${BQ_DATASET}" >/dev/null 2>&1 || true
  if [[ -d "${REPO_ROOT}/data/bq_export" ]]; then
    echo "Loading Member 1 enriched JSONL tables (data/bq_export/*.jsonl) into ${PROJECT_ID}:${BQ_DATASET}..."
    for tbl in businesses employer_blocks supplies draws_footfall_from borrowed_from tract_demographics; do
      if [[ -f "${REPO_ROOT}/data/bq_export/${tbl}.jsonl" ]]; then
        bq --project_id="${PROJECT_ID}" load --replace --autodetect \
          --source_format=NEWLINE_DELIMITED_JSON \
          "${BQ_DATASET}.${tbl}" "${REPO_ROOT}/data/bq_export/${tbl}.jsonl" || true
      fi
    done
  elif ! bq show "${PROJECT_ID}:${BQ_DATASET}.businesses" >/dev/null 2>&1; then
    echo "Loading Member 1 corridor tables into ${PROJECT_ID}:${BQ_DATASET}..."
    bash "${REPO_ROOT}/scripts/load.sh" market-castro || true
  fi
  if [[ -f "${REPO_ROOT}/sql/01_create_property_graph.sql" ]]; then
    echo "Provisioning ISO/GQL Property Graph (${BQ_DATASET}.${BQ_GRAPH})..."
    bq query --project_id="${PROJECT_ID}" --use_legacy_sql=false < "${REPO_ROOT}/sql/01_create_property_graph.sql" || true
  fi
fi

# Step 2: Deploy Unified Member 1 + Member 2 + Member 3 Service to Cloud Run
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --service-account="${SERVICE_ACCOUNT}" \
  --allow-unauthenticated \
  --min-instances=1 \
  --max-instances=2 \
  --concurrency=20 \
  --timeout=300 \
  --memory=1Gi \
  --cpu=1 \
  --port=8080 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=TRUE,BQ_DATASET=${BQ_DATASET},BQ_LOCATION=${BQ_LOCATION},BQ_GRAPH=${BQ_GRAPH},USE_LIVE_BIGQUERY=true,ENABLE_BIGQUERY_MCP=true" \
  "${VPC_FLAGS[@]}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
echo ""
echo "======================================================================"
echo " Deployed Successfully!"
echo " 10-Corridor Grant Officer UI : ${SERVICE_URL}/grant-officer"
echo " Market/Castro Deep-Dive UI   : ${SERVICE_URL}/market-castro"
echo " 3-Sub-Agent Workflow API     : ${SERVICE_URL}/api/workflow"
echo " Health & MCP/BQ Status       : ${SERVICE_URL}/api/health"
echo " ADK Agent Info               : ${SERVICE_URL}/api/agent-info"
echo "======================================================================"

# Step 3: Run automated post-deploy production integration suite against live URL
if [[ -f "${REPO_ROOT}/scripts/test_production_integration.sh" ]]; then
  echo ""
  bash "${REPO_ROOT}/scripts/test_production_integration.sh" "${SERVICE_URL}"
fi
