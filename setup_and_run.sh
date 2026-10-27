#!/usr/bin/env bash
# ==============================================================================
# One-Click Team Setup & Launch Script — Agents for Impact 2026 (Challenge 03)
# Corridor: Market/Castro (San Francisco, CA) — Parameterizable via CORRIDOR_NAME
# ==============================================================================
set -euo pipefail

CORRIDOR_NAME="${CORRIDOR_NAME:-Market/Castro}"
GRAPH_JSON_PATH="${GRAPH_JSON_PATH:-data/market_castro_graph.json}"
PORT="${PORT:-8080}"

echo "=================================================================="
echo " A4I 2026 Challenge 03 — Grant Officer Defense Console"
echo " Corridor: ${CORRIDOR_NAME}"
echo " Graph Path: ${GRAPH_JSON_PATH}"
echo "=================================================================="

# 1. Build local property graph JSON if not already present
if [ ! -f "${GRAPH_JSON_PATH}" ]; then
  echo "[1/2] Building local Property Graph JSON (${GRAPH_JSON_PATH})..."
  python3 scripts/build_local_corridor.py
else
  echo "[1/2] Verified existing Property Graph JSON (${GRAPH_JSON_PATH})."
fi

# 2. Launch the Grant Officer Defense Console & REST API Server
echo "[2/2] Starting Grant Officer Defense Console at http://127.0.0.1:${PORT} ..."
python3 -m agent.server
