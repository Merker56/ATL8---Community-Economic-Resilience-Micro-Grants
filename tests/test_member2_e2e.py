"""
Comprehensive Cross-Validation & End-to-End Test Suite for Member 2 Deliverables
(Workflow Process, Backend REST API, MCP/BigQuery Bridge, Multi-Agent ADK Hierarchy,
Member 1 Data Hot-Reload, and Member 3 UI Contract).

Run with:
    ./.venv/bin/python tests/test_member2_e2e.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.agent import (
    AGENT_TOOLS,
    equity_bias_auditor_agent,
    grant_portfolio_defense_agent,
    graph_cascade_agent,
    root_agent,
    run_end_to_end_workflow,
    run_grant_officer_chat,
)
from agent.mcp_config import get_mcp_and_bigquery_status
from agent.server import app, handle_api_get, handle_api_post
from agent.tools import (
    add_verified_merchant_supplier,
    audit_corridor_equity_and_bias,
    compare_grant_candidates,
    discover_cascade_candidates,
    generate_friday_grant_memo,
    get_system_integration_status,
    optimize_corridor_portfolio,
    reload_corridor_graph,
    simulate_anchor_closure,
)


class TestMember2Deliverables(unittest.TestCase):
    """Cross-validates all Member 2 deliverables and team integration contracts."""

    def setUp(self) -> None:
        # Ensure clean graph state before each test
        reload_corridor_graph()

    def test_01_adk_multi_agent_hierarchy(self) -> None:
        """Verify Google ADK root_agent + 3 specialist sub-agents and 9 tools."""
        self.assertEqual(len(AGENT_TOOLS), 9)
        if root_agent is not None:
            self.assertEqual(root_agent.name, "market_castro_grant_advisor")
            self.assertEqual(len(root_agent.sub_agents), 3)
            sub_names = [sa.name for sa in root_agent.sub_agents]
            self.assertEqual(
                sub_names,
                [
                    "graph_cascade_analyst",
                    "equity_bias_auditor",
                    "grant_portfolio_defender",
                ],
            )
            self.assertIsNotNone(graph_cascade_agent)
            self.assertIsNotNone(equity_bias_auditor_agent)
            self.assertIsNotNone(grant_portfolio_defense_agent)

    def test_02_mcp_and_bigquery_bridge_config(self) -> None:
        """Verify tools.yaml parameterized GQL queries and MCP/BigQuery bridge status."""
        mcp_status = get_mcp_and_bigquery_status()
        self.assertTrue(mcp_status["tools_yaml_exists"])
        tools_yaml = (ROOT_DIR / "agent" / "tools.yaml").read_text(encoding="utf-8")
        for tool_name in (
            "gql_keystone_band",
            "gql_cascade_paths_to_json",
            "gql_compounded_cascade_score",
            "gql_track3_anchor_closure",
        ):
            self.assertIn(tool_name, tools_yaml)

    def test_03_member1_data_contract_and_hot_reload(self) -> None:
        """Verify Member 1 -> Member 2 data contract and zero-downtime hot reload."""
        status = get_system_integration_status()
        self.assertEqual(status["status"], "ok")
        m1 = status["member1_data_and_bigquery_ready"]
        self.assertTrue(m1["graph_json_exists"])
        self.assertEqual(m1["businesses_loaded"], 327)
        self.assertEqual(m1["supplies_edges_loaded"], 1199)
        self.assertEqual(m1["draws_footfall_edges_loaded"], 677)
        self.assertEqual(m1["employer_blocks_loaded"], 10)
        self.assertEqual(m1["tract_demographics_loaded"], 8)
        self.assertEqual(m1["borrowed_from_loans_loaded"], 9)
        self.assertTrue(m1["lpad_11char_tract_geoid_verified"])

        reload_res = reload_corridor_graph()
        self.assertEqual(reload_res["status"], "reloaded")
        self.assertEqual(reload_res["businesses_count"], 327)

    def test_04_discover_cascade_candidates_and_bias_filters(self) -> None:
        """Verify Keystone Band discovery ranks Theatre Rhinoceros #1 and flags Primo."""
        res = discover_cascade_candidates(
            exclude_virtual_mailboxes=True,
            exclude_monopoly_artifacts=True,
            min_reach=3,
            max_reach=35,
            top_k=10,
        )
        cands = res["actionable_keystone_candidates"]
        self.assertGreaterEqual(len(cands), 5)
        self.assertEqual(cands[0]["name"], "Theatre Rhinoceros")
        self.assertEqual(cands[0]["business_id"], "1328524-03-231")
        self.assertEqual(cands[0]["total_2hop_exposed_count"], 12)
        self.assertEqual(cands[1]["name"], "Canela")
        traps = res["disqualified_naive_centrality_traps"]
        trap_names = [t["name"] for t in traps]
        self.assertIn("Primo", trap_names)

    def test_05_portfolio_optimizer_subgraph_dedup_and_15k_floor(self) -> None:
        """Verify Subgraph-Deduplicated Portfolio Optimizer and $15,000 minimum floor."""
        # Case A: $50,000 pool, K=2 -> Theatre Rhinoceros + Canela, 0% overlap, 13 unique physical
        p2 = optimize_corridor_portfolio(
            budget_pool_usd=50000.0,
            num_grantees=2,
            min_effective_grant_usd=15000.0,
            deduplicate_subgraphs=True,
        )
        self.assertEqual(p2["requested_grantees"], 2)
        self.assertEqual(p2["recommended_grantees_for_pool"], 2)
        self.assertEqual(len(p2["dilution_warnings"]), 0)
        self.assertEqual(p2["selected_portfolio"][0]["name"], "Theatre Rhinoceros")
        self.assertEqual(p2["selected_portfolio"][1]["name"], "Canela")
        self.assertEqual(p2["selected_portfolio"][1]["subgraph_redundancy_pct"], 0.0)
        self.assertEqual(p2["total_unique_physical_storefronts_protected"], 13)

        # Case B: $50,000 pool, K=4 -> Dilution warning triggers because $50K across 4 grantees < $15K floor
        p4_warn = optimize_corridor_portfolio(
            budget_pool_usd=50000.0,
            num_grantees=4,
            min_effective_grant_usd=15000.0,
            deduplicate_subgraphs=True,
        )
        self.assertGreater(len(p4_warn["dilution_warnings"]), 0)
        self.assertEqual(p4_warn["recommended_grantees_for_pool"], 2)

        # Case C: $60,000 pool, K=4 -> Skips redundant #3 The Castro (91.7% overlap) & #4 Hi Tops (100% overlap)
        p4_60k = optimize_corridor_portfolio(
            budget_pool_usd=60000.0,
            num_grantees=4,
            min_effective_grant_usd=15000.0,
            deduplicate_subgraphs=True,
        )
        selected_names = [s["name"] for s in p4_60k["selected_portfolio"]]
        self.assertNotIn("The Castro", selected_names)
        self.assertNotIn("Hi Tops", selected_names)

        # Verify naive_top4_overlap_audit proves #3 The Castro (91.7%) and #4 Hi Tops (100.0%) redundancy
        naive_by_name = {n["name"]: n for n in p4_60k["naive_top4_overlap_audit"]}
        self.assertEqual(naive_by_name["The Castro"]["subgraph_redundancy_pct"], 91.7)
        self.assertEqual(naive_by_name["Hi Tops"]["subgraph_redundancy_pct"], 100.0)

    def test_06_friday_memo_and_head_to_head_and_anchor_shock(self) -> None:
        """Verify 7-Part Friday Memo, Head-to-Head comparison, and Track 3 Anchor Shock."""
        memo = generate_friday_grant_memo(
            business_query="Theatre Rhinoceros",
            runner_up_query="Cafe Du Nord",
            grant_amount_usd=25000.0,
        )
        self.assertEqual(memo["recommended_business_name"], "Theatre Rhinoceros")
        self.assertEqual(memo["direct_1hop_count"], 7)
        self.assertEqual(memo["indirect_2hop_count"], 5)
        self.assertEqual(memo["total_2hop_exposed_count"], 12)
        self.assertGreater(len(memo["to_json_paths"]), 0)
        self.assertEqual(memo["tract_context"]["tract_geoid"], "06075017102")

        cmp_res = compare_grant_candidates("Theatre Rhinoceros", "Cafe Du Nord")
        self.assertEqual(cmp_res["candidate_a"]["name"], "Theatre Rhinoceros")
        self.assertEqual(cmp_res["candidate_b"]["name"], "Cafe Du Nord")
        self.assertIn("directly supplies", cmp_res["direct_supply_link"])

        shock = simulate_anchor_closure("060750171011001")
        self.assertEqual(shock["anchor_block"]["block_geoid"], "060750171011001")
        self.assertEqual(shock["anchor_block"]["total_jobs"], 785)
        self.assertGreater(len(shock["top_footfall_dependent_storefronts"]), 0)
        self.assertGreater(len(shock["top_upstream_suppliers_at_risk"]), 0)

    def test_07_merchant_intake_and_equity_audit(self) -> None:
        """Verify +10 Bonus Merchant Supplier Intake and Equity/Bias Audit."""
        audit = audit_corridor_equity_and_bias()
        self.assertEqual(len(audit["virtual_mailbox_hub_audit"]), 2)
        self.assertEqual(len(audit["duplicate_dba_audit"]), 13)
        self.assertEqual(audit["sba_7a_historical_loans"]["total_matched_loans"], 9)
        self.assertEqual(len(audit["sba_7a_historical_loans"]["chargeoff_loans"]), 2)

        intake = add_verified_merchant_supplier(
            buyer_query="The Castro",
            supplier_query="Theatre Rhinoceros",
            reported_dependency_share=0.40,
            invoice_note="Unit test invoice verification",
        )
        self.assertEqual(intake["status"], "verified_edge_recorded")
        self.assertEqual(intake["verified_intensity"], 0.4)
        self.assertGreater(
            intake["cascade_impact_delta"]["after_1hop_intensity"],
            intake["cascade_impact_delta"]["before_1hop_intensity"],
        )

    def test_08_end_to_end_multi_agent_workflow(self) -> None:
        """Verify end-to-end 3-sub-agent workflow orchestration and telemetry."""
        wf = run_end_to_end_workflow(
            budget_pool_usd=50000.0,
            num_grantees=2,
        )
        self.assertTrue(wf["workflow_id"].startswith("wf-"))
        self.assertEqual(len(wf["sub_agent_traces"]), 3)
        trace_names = [t["sub_agent_name"] for t in wf["sub_agent_traces"]]
        self.assertEqual(
            trace_names,
            [
                "graph_cascade_analyst",
                "equity_bias_auditor",
                "grant_portfolio_defender",
            ],
        )
        self.assertEqual(
            wf["portfolio_optimization"]["total_unique_physical_storefronts_protected"],
            13,
        )

    def test_09_rest_api_and_member3_ui_contract(self) -> None:
        """Verify all GET and POST REST API endpoints for Member 3's frontend."""
        get_endpoints = [
            "/api/health",
            "/api/workflow?budget_pool=50000&num_grantees=2",
            "/api/overview",
            "/api/portfolio?budget_pool=50000&num_grantees=2",
            "/api/candidates?exclude_vm=true&exclude_monopoly=true",
            "/api/memo?business=Theatre+Rhinoceros&runner_up=Cafe+Du+Nord",
            "/api/compare?a=Theatre+Rhinoceros&b=Cafe+Du+Nord",
            "/api/anchor-shock?anchor=200894",
            "/api/equity-audit",
        ]
        for ep in get_endpoints:
            path, _, qs = ep.partition("?")
            status, payload = handle_api_get(path, qs)
            self.assertEqual(status, 200, f"GET {ep} failed with {status}")
            self.assertIsInstance(payload, dict)

        post_tests = [
            ("/api/workflow", {"budget_pool_usd": 50000, "num_grantees": 2}),
            (
                "/api/merchant-intake",
                {
                    "buyer_query": "The Castro",
                    "supplier_query": "Theatre Rhinoceros",
                    "reported_dependency_share": 0.35,
                },
            ),
            ("/api/chat", {"message": "Run the end-to-end multi-agent workflow"}),
            ("/api/reload", {}),
        ]
        for path, body in post_tests:
            status, payload = handle_api_post(path, body)
            self.assertEqual(status, 200, f"POST {path} failed with {status}")
            self.assertIsInstance(payload, dict)

        # Verify FastAPI app object is initialized when fastapi is installed
        self.assertIsNotNone(app)

    def test_10_member1_raw_unenriched_schema_resilience(self) -> None:
        """
        Simulate Member 1 dropping a raw, un-enriched JSON file (missing derived fields
        like is_virtual_mailbox_hub, corridor_naics4_peers, has_duplicate_dba, and using
        unpadded 10-char tract '6075017102') to verify Member 2 auto-normalizes it.
        """
        import asyncio
        import json
        import tempfile

        raw_mock = {
            "metadata": {"corridor": "Mock-Corridor"},
            "businesses": [
                {
                    "business_id": "B1",
                    "name": "Anchor Bakery",
                    "address": "100 Main St",
                    "naics4": "3118",
                    "tract": "6075017102",  # 10-char unpadded!
                    "latitude": 37.76,
                    "longitude": -122.43,
                },
                {
                    "business_id": "B2",
                    "name": "Corner Cafe",
                    "address": "102 Main St",
                    "naics4": "7225",
                    "tract": "6075017102",
                    "latitude": 37.7605,
                    "longitude": -122.4305,
                },
                {
                    "business_id": "B3",
                    "name": "The Corner Cafe",  # Duplicate DBA test
                    "address": "104 Main St",
                    "naics4": "7225",
                    "tract": "6075017102",
                    "latitude": 37.761,
                    "longitude": -122.431,
                },
            ],
            "employer_blocks": [
                {
                    "block_geoid": "060750171011001",
                    "tract_geoid": "6075017101",
                    "jobs": 500,
                }
            ],
            "supplies": [
                {
                    "edge_id": "B1|B2",
                    "supplier_id": "B1",
                    "buyer_id": "B2",
                    "intensity": 0.12,
                    "metres": 80.0,
                },
                {
                    "edge_id": "B2|B3",
                    "supplier_id": "B2",
                    "buyer_id": "B3",
                    "intensity": 0.08,
                    "metres": 60.0,
                },
            ],
            "draws_footfall_from": [
                {
                    "edge_id": "060750171011001|B1",
                    "block_geoid": "060750171011001",
                    "business_id": "B1",
                    "share": 0.45,
                    "metres": 120.0,
                }
            ],
            "borrowed_from": [],
            "tract_demographics": [
                {
                    "tract": "6075017102",
                    "total_pop": 4000,
                    "median_income": 95000,
                    "poverty_rate": 0.14,
                    "no_vehicle_rate": 0.35,
                    "assistance_rate": 0.08,
                }
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tf:
            json.dump(raw_mock, tf)
            tmp_path = tf.name

        try:
            reload_res = reload_corridor_graph(tmp_path)
            self.assertEqual(reload_res["status"], "reloaded")
            self.assertEqual(reload_res["businesses_count"], 3)

            status = get_system_integration_status()
            self.assertTrue(
                status["member1_data_and_bigquery_ready"]["lpad_11char_tract_geoid_verified"]
            )

            # Verify end-to-end workflow executes cleanly even on raw Member 1 data
            wf = run_end_to_end_workflow(
                corridor_name="Mock-Corridor",
                budget_pool_usd=30000.0,
                num_grantees=1,
                primary_candidate_query="Anchor Bakery",
                runner_up_query="Corner Cafe",
                anchor_block_query="060750171011001",
            )
            self.assertEqual(len(wf["sub_agent_traces"]), 3)
            self.assertEqual(
                wf["primary_friday_memo"]["tract_context"]["tract_geoid"],
                "06075017102",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
            # Restore production Market/Castro graph
            reload_corridor_graph(str(ROOT_DIR / "data" / "market_castro_graph.json"))

    def test_11_member3_cloud_run_fastapi_main_contract(self) -> None:
        """
        Verify that Cloud Run `agent/main.py` FastAPI endpoints and Member 2's
        endpoints work seamlessly together with zero stderr errors.
        """
        import asyncio
        from agent.main import (
            ChatRequest,
            analyze_get,
            chat_with_agent,
            health,
            qa_validate,
        )

        async def _run_checks() -> None:
            h = await health()
            self.assertEqual(h["status"], "ok")
            self.assertIn("member1_data_and_bigquery_ready", h)
            self.assertIn("member2_multi_agent_and_mcp_ready", h)
            self.assertIn("member3_ui_console_ready", h)

            qa = await qa_validate("Market/Castro")
            self.assertEqual(qa["passed_checks"], 30)

            an = await analyze_get(
                corridor="Market/Castro",
                budget=50000.0,
                track="main_street",
                split_mode="split_two",
                seed_id=None,
            )
            self.assertEqual(an["corridor"], "Market/Castro")

            chat_mc = await chat_with_agent(
                ChatRequest(
                    message="Run the end-to-end multi-agent workflow for Theatre Rhinoceros",
                    corridor="Market/Castro",
                )
            )
            self.assertIn("reply", chat_mc)
            self.assertEqual(chat_mc["tool_called"], "run_end_to_end_workflow")

        asyncio.run(_run_checks())

    def test_12_dual_ui_switcher_leaflet_map_and_workflow_trace(self) -> None:
        """
        Verify Recommendation 1, 2 & 3:
          - Dual UI navigation switcher between /grant-officer and /market-castro
          - 3-Sub-Agent Pipeline Trace tab (tabWorkflow) in market_castro_console.html
          - Interactive Leaflet Street Map (leafletMap) + lat/lon on DownstreamCascadeNode
          - /api/agent-info exposing sub_agents and mcp_tools_yaml
        """
        import asyncio
        from agent.main import agent_info, serve_market_castro_ui, serve_ui

        async def _verify_ui_and_agent_info() -> None:
            info = await agent_info()
            self.assertIn("sub_agents", info)
            self.assertEqual(
                info["sub_agents"],
                [
                    "graph_cascade_analyst",
                    "equity_bias_auditor",
                    "grant_portfolio_defender",
                ],
            )
            self.assertEqual(info["mcp_tools_yaml"], "agent/tools.yaml")

            resp_go = await serve_ui()
            self.assertIsNotNone(resp_go)
            resp_mc = await serve_market_castro_ui()
            self.assertIsNotNone(resp_mc)

        asyncio.run(_verify_ui_and_agent_info())

        index_html = (ROOT_DIR / "agent" / "static" / "index.html").read_text(encoding="utf-8")
        mc_html = (ROOT_DIR / "agent" / "static" / "market_castro_console.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('href="/market-castro"', index_html)
        self.assertIn('href="/grant-officer"', mc_html)
        self.assertIn('id="tabWorkflow"', mc_html)
        self.assertIn('id="leafletMap"', mc_html)
        self.assertIn("runWorkflowPipeline()", mc_html)
        self.assertIn("triggerGraphReload()", mc_html)

        memo = generate_friday_grant_memo(business_query="Theatre Rhinoceros")
        first_node = memo["cascade_nodes"][0]
        self.assertIn("latitude", first_node)
        self.assertIn("longitude", first_node)
        self.assertGreater(first_node["latitude"], 37.7)
        self.assertLess(first_node["longitude"], -122.4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
