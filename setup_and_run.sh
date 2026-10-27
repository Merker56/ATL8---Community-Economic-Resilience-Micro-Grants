#!/usr/bin/env bash
# ==============================================================================
# One-Click Team Setup & Launch Script — Agents for Impact 2026 (Challenge 03)
# Corridor: Market/Castro (San Francisco, CA) — Parameterizable via CORRIDOR_NAME
# ==============================================================================
set -euo pipefail

CORRIDOR_NAME="${CORRIDOR_NAME:-Market/Castro}"
GRAPH_JSON_PATH="${GRAPH_JSON_PATH:-data/market_castro_graph.json}"
PORT="${PORT:-8080}"

if [ -x "./.venv/bin/python" ]; then
  PYTHON_BIN="./.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

echo "=================================================================="
echo " A4I 2026 Challenge 03 — Grant Officer Defense Console"
echo " Corridor:   ${CORRIDOR_NAME}"
echo " Graph Path: ${GRAPH_JSON_PATH}"
echo " Python Bin: ${PYTHON_BIN}"
echo "=================================================================="

# 1. Build local property graph JSON if not already present
if [ ! -f "${GRAPH_JSON_PATH}" ]; then
  echo "[1/3] Building local Property Graph JSON (${GRAPH_JSON_PATH})..."
  "${PYTHON_BIN}" scripts/build_local_corridor.py
else
  echo "[1/3] Verified existing Property Graph JSON (${GRAPH_JSON_PATH})."
fi

# 2. Run automated Member 1 + Member 2 + Member 3 cross-validation suite
echo "[2/3] Running End-to-End Multi-Agent & API Cross-Validation Suite..."
"${PYTHON_BIN}" tests/test_member2_e2e.py

# 3. Launch the Grant Officer Defense Console & REST API Server
echo "[3/3] Starting Grant Officer Defense Console at http://127.0.0.1:${PORT} ..."
"${PYTHON_BIN}" -m agent.server
