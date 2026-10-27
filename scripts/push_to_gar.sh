#!/usr/bin/env bash
# ==============================================================================
# ATL8 Challenge 3 — Build & Push Docker Image to Google Artifact Registry (GAR)
# Target Project : qwiklabs-gcp-03-46ba9aeed89b
# Target Region  : us-east1
# Target GAR URI : us-east1-docker.pkg.dev/qwiklabs-gcp-03-46ba9aeed89b/atl8/atl8-grant-officer-agent:latest
# ==============================================================================
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-qwiklabs-gcp-03-46ba9aeed89b}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-east1}"
GAR_REPO="${GAR_REPO:-atl8}"
IMAGE_NAME="${IMAGE_NAME:-atl8-grant-officer-agent}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

GAR_HOST="${REGION}-docker.pkg.dev"
GAR_IMAGE_URI="${GAR_HOST}/${PROJECT_ID}/${GAR_REPO}/${IMAGE_NAME}:${IMAGE_TAG}"
CLOUD_RUN_SOURCE_URI="${GAR_HOST}/${PROJECT_ID}/cloud-run-source-deploy/${IMAGE_NAME}:${IMAGE_TAG}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "======================================================================"
echo " Building & Pushing Docker Image to Google Artifact Registry (GAR)"
echo "----------------------------------------------------------------------"
echo " Project ID  : ${PROJECT_ID}"
echo " Region      : ${REGION}"
echo " GAR Repo    : ${GAR_REPO}"
echo " Image URI   : ${GAR_IMAGE_URI}"
echo "======================================================================"

# Step 1: Build linux/amd64 production image locally if Docker is available
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "[1/3] Building linux/amd64 Docker image (includes 13-test E2E build gate)..."
  docker build --platform linux/amd64 \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -t "${GAR_IMAGE_URI}" \
    -t "${CLOUD_RUN_SOURCE_URI}" \
    .
fi

# Step 2: Ensure Artifact Registry repository exists & push via gcloud / docker
if command -v gcloud >/dev/null 2>&1; then
  echo "[2/3] Ensuring Artifact Registry repository '${GAR_REPO}' exists in ${PROJECT_ID} (${REGION})..."
  gcloud services enable artifactregistry.googleapis.com cloudbuild.googleapis.com run.googleapis.com \
    --project="${PROJECT_ID}" --quiet || true

  if ! gcloud artifacts repositories describe "${GAR_REPO}" \
       --project="${PROJECT_ID}" --location="${REGION}" >/dev/null 2>&1; then
    gcloud artifacts repositories create "${GAR_REPO}" \
      --project="${PROJECT_ID}" \
      --repository-format=docker \
      --location="${REGION}" \
      --description="ATL8 Community Economic Resilience & Micro-Grants Docker Repository"
  fi

  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "[3/3] Authenticating Docker with ${GAR_HOST} and pushing ${GAR_IMAGE_URI}..."
    gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin "https://${GAR_HOST}"
    docker push "${GAR_IMAGE_URI}"
  else
    echo "[3/3] Submitting Cloud Build directly to Artifact Registry (${GAR_IMAGE_URI})..."
    gcloud builds submit --project="${PROJECT_ID}" --region="${REGION}" --tag "${GAR_IMAGE_URI}" .
  fi

  echo "======================================================================"
  echo " SUCCESS! Image pushed to Google Artifact Registry:"
  echo "   ${GAR_IMAGE_URI}"
  echo "======================================================================"
elif [[ -n "${GCP_ACCESS_TOKEN:-}" ]]; then
  echo "[2/3] Authenticating Docker with GCP_ACCESS_TOKEN and pushing to ${GAR_IMAGE_URI}..."
  echo "${GCP_ACCESS_TOKEN}" | docker login -u oauth2accesstoken --password-stdin "https://${GAR_HOST}"
  docker push "${GAR_IMAGE_URI}"
  echo "======================================================================"
  echo " SUCCESS! Image pushed to Google Artifact Registry:"
  echo "   ${GAR_IMAGE_URI}"
  echo "======================================================================"
else
  echo "----------------------------------------------------------------------"
  echo " Local Docker image built & tagged for GAR:"
  echo "   - ${GAR_IMAGE_URI}"
  echo "   - ${CLOUD_RUN_SOURCE_URI}"
  echo ""
  echo " To push from your local machine using an access token from Cloud Shell:"
  echo "   GCP_ACCESS_TOKEN=\"\$(gcloud auth print-access-token)\" bash scripts/push_to_gar.sh"
  echo ""
  echo " Or run inside Qwiklabs Cloud Shell / Vertex AI Workbench (${PROJECT_ID}):"
  echo "   bash scripts/push_to_gar.sh"
  echo "----------------------------------------------------------------------"
fi
