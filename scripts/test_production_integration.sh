#!/usr/bin/env bash
# ==============================================================================
# ATL8 Challenge 3 — End-to-End Production Integration Test Suite
# Verifies Member 1 (Data & BigQuery Graph) + Member 2 (ADK Multi-Agent, MCP &
# FastAPI Backend) + Member 3 (Dual UI Consoles) against a target URL.
#
# Usage:
#   bash scripts/test_production_integration.sh                           # defaults to http://localhost:8080
#   bash scripts/test_production_integration.sh https://your-run-url.app  # tests live Cloud Run production URL
# ==============================================================================
set -euo pipefail

TARGET_URL="${1:-${SERVICE_URL:-http://localhost:8080}}"
TARGET_URL="${TARGET_URL%/}"

PYTHON_BIN="python3"
if [[ -x "./.venv/bin/python" ]]; then
  PYTHON_BIN="./.venv/bin/python"
fi

echo "======================================================================================"
echo " ATL8 PRODUCTION INTEGRATION VERIFICATION (MEMBER 1 + MEMBER 2 + MEMBER 3)"
echo " Target Endpoint : ${TARGET_URL}"
echo " Timestamp       : $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "======================================================================================"

"${PYTHON_BIN}" - "${TARGET_URL}" << 'EOF'
import json
import sys
import urllib.request
import urllib.error

base_url = sys.argv[1]
passed = 0
failed = 0

def req_json(path, method="GET", payload=None):
    url = f"{base_url}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def req_text(path):
    url = f"{base_url}{path}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8")

def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {label}" + (f" -> {detail}" if detail else ""))
    else:
        failed += 1
        print(f"  [FAIL] {label}" + (f" -> {detail}" if detail else ""))

print("\n--- 1. MEMBER 1 <-> MEMBER 2 DATA & BIGQUERY GRAPH INTEGRATION ---")
status, health = req_json("/api/health")
m1 = health.get("member1_data_and_bigquery_ready", {})
m2 = health.get("member2_multi_agent_and_mcp_ready", {})
bq = health.get("bigquery", {})
check(
    "M1.1 Health & Graph Snapshot Contract (/api/health)",
    status == 200 and m1.get("businesses_loaded", 0) >= 300 and m1.get("supplies_edges_loaded", 0) >= 1000,
    f"businesses={m1.get('businesses_loaded')}, supplies={m1.get('supplies_edges_loaded')}, footfall={m1.get('draws_footfall_edges_loaded')}",
)
check(
    "M1.2 11-Char LPAD Tract GEOIDs & SQL DDL/GQL Scripts",
    m1.get("lpad_11char_tract_geoid_verified") is True and all(m1.get("sql_scripts_verified", {}).values()),
    f"tracts={m1.get('tract_demographics_loaded')}, sql_verified={m1.get('sql_scripts_verified')}",
)
check(
    "M1.3 BigQuery Dataset & Property Graph Status",
    "a4i_econ" in str(bq.get("dataset", "")) and "LocalEconomy" in str(bq.get("graph_name", "")),
    f"connected={bq.get('connected')}, mode={bq.get('mode')}, graph={bq.get('graph_name')}",
)
status, rel = req_json("/api/reload", method="POST")
check(
    "M1.4 Zero-Downtime Member 1 Graph Hot-Reload (POST /api/reload)",
    status == 200 and rel.get("status") == "reloaded" and rel.get("businesses_count", 0) >= 300,
    f"reloaded {rel.get('businesses_count')} businesses & {rel.get('supplies_edges_count')} Supplies edges",
)

print("\n--- 2. MEMBER 2 GOOGLE ADK MULTI-AGENT, MCP & GQL WORKFLOW ENGINE ---")
status, info = req_json("/api/agent-info")
check(
    "M2.1 Google ADK Root Agent + 3 Sub-Agents (/api/agent-info)",
    status == 200 and info.get("agent_name") == "grant_officer_agent" and len(info.get("sub_agents", [])) == 3,
    f"sub_agents={info.get('sub_agents')}, tools={len(info.get('tools', []))}, corridors={len(info.get('corridors', {}))}",
)
status, hier = req_json("/api/hierarchy")
status_mcp, mcp_manifest = req_json("/api/mcp-status")
check(
    "M2.2 Managed BigQuery MCP & Sub-Agent Hierarchy (/api/hierarchy + /api/mcp-status)",
    status == 200 and status_mcp == 200 and hier.get("root_agent", {}).get("name") == "market_castro_grant_advisor" and mcp_manifest.get("mcp_tools_manifest", {}).get("tool_count") == 5,
    f"root={hier.get('root_agent', {}).get('name')}, mcp_tools={mcp_manifest.get('mcp_tools_manifest', {}).get('tool_count')}, mode={m2.get('active_execution_mode')}",
)
status, memo = req_json("/api/memo?business=Theatre+Rhinoceros&runner_up=Cafe+Du+Nord")
check(
    "M2.3 7-Part Friday Memo + Geo Cascade + TO_JSON(p) (/api/memo)",
    status == 200 and memo.get("recommended_business_name") == "Theatre Rhinoceros" and len(memo.get("cascade_nodes", [])) == 12,
    f"jobs_saved={memo.get('expected_jobs_saved_delta')}, cost_per_job=${memo.get('cost_per_expected_job_saved_usd')}, lat={memo['cascade_nodes'][0].get('latitude')}",
)
status, port = req_json("/api/portfolio?budget_pool=50000&num_grantees=2&deduplicate=true")
sel = port.get("selected_portfolio", [])
check(
    "M2.4 Subgraph-Deduplicated Portfolio Optimizer (/api/portfolio)",
    status == 200 and len(sel) == 2 and port.get("total_unique_2hop_nodes_protected") == 21,
    f"selected={[s['name'] for s in sel]}, unique_2hop={port.get('total_unique_2hop_nodes_protected')}, unique_physical={port.get('total_unique_physical_storefronts_protected')}",
)
status, shock = req_json("/api/anchor-shock?anchor=060750171011001")
check(
    "M2.5 Track 3 Bi-Directional Anchor Closure Shock (/api/anchor-shock)",
    status == 200 and shock.get("anchor_block", {}).get("total_jobs") == 785 and shock.get("upstream_suppliers_indirectly_impacted", 0) == 36,
    f"anchor_jobs={shock['anchor_block']['total_jobs']}, storefronts_hit={shock.get('direct_footfall_storefronts_impacted')}, upstream_suppliers_hurt={shock.get('upstream_suppliers_indirectly_impacted')}",
)
status, eq = req_json("/api/equity-audit")
check(
    "M2.6 3-Step Equity & BEA Mechanical Bias Audit (/api/equity-audit)",
    status == 200 and len(eq.get("tract_demographics_lpad11", [])) == 8 and len(eq.get("mechanical_bea_sector_bias", [])) > 0,
    f"tracts={len(eq.get('tract_demographics_lpad11', []))}, bea_sectors={len(eq.get('mechanical_bea_sector_bias', []))}, virtual_hubs={len(eq.get('virtual_mailbox_hub_audit', []))}",
)
status, intake = req_json(
    "/api/merchant-intake",
    method="POST",
    payload={
        "source_business": "Theatre Rhinoceros",
        "target_supplier": "Anchor Oyster Bar",
        "monthly_spend_usd": 4800,
        "note": "Production integration verification",
    },
)
check(
    "M2.7 +10 Bonus Merchant Supplier Intake & BQ MERGE DML (POST /api/merchant-intake)",
    status == 200 and intake.get("status") == "verified_edge_recorded" and "MERGE `a4i_econ.supplies`" in intake.get("bigquery_dml_statement", ""),
    f"verified_intensity={intake.get('verified_intensity')}, jobs_after={intake.get('cascade_impact_delta', {}).get('after_jobs_protected')}",
)
# Restore clean baseline after intake test
req_json("/api/reload", method="POST")

status, wf = req_json("/api/workflow?budget_pool=50000&num_grantees=2")
check(
    "M2.8 3-Sub-Agent Sequential Pipeline Trace (/api/workflow)",
    status == 200 and wf.get("execution_mode") == "ADK_3_SUBAGENT_SEQUENTIAL_PIPELINE" and len(wf.get("sub_agent_traces", [])) == 3,
    f"traces={[t.get('sub_agent_name') for t in wf.get('sub_agent_traces', [])]}, time={wf.get('total_execution_ms')}ms",
)
status, chat = req_json(
    "/api/chat",
    method="POST",
    payload={
        "message": "Compare Theatre Rhinoceros vs Cafe Du Nord for a $25,000 grant in Market/Castro.",
        "corridor": "Market/Castro",
    },
)
check(
    "M2.9 Grounded Multi-Agent Chat (POST /api/chat)",
    status == 200 and "Theatre Rhinoceros" in chat.get("reply", "") and "Cafe Du Nord" in chat.get("reply", ""),
    f"engine={chat.get('engine')}, tool={chat.get('tool_called')}",
)

print("\n--- 3. MEMBER 3 <-> MEMBER 2 DUAL UI CONSOLE INTEGRATION ---")
s1, html_go = req_text("/grant-officer")
check(
    "M3.1 10-Corridor Grant Officer UI (GET /grant-officer)",
    s1 == 200 and "/market-castro" in html_go and "Grant Officer" in html_go,
    f"HTTP {s1} ({len(html_go):,} bytes), switcher to /market-castro verified",
)
s2, html_mc = req_text("/market-castro")
check(
    "M3.2 Market/Castro Deep-Dive UI + Leaflet Map + Workflow Tab (GET /market-castro)",
    s2 == 200 and "/grant-officer" in html_mc and "leaflet" in html_mc.lower() and "/api/workflow" in html_mc,
    f"HTTP {s2} ({len(html_mc):,} bytes), Leaflet map + Tab 5 (/api/workflow) + switcher verified",
)

print("\n======================================================================================")
print(f" SUMMARY: {passed} PASSED, {failed} FAILED (out of {passed + failed} production integration checks)")
print("======================================================================================")
sys.exit(0 if failed == 0 else 1)
EOF
