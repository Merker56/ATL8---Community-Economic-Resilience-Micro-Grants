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
    get_multi_agent_hierarchy,
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
        hierarchy = get_multi_agent_hierarchy()
        self.assertEqual(hierarchy["root_agent"]["name"], "market_castro_grant_advisor")
        self.assertEqual(len(hierarchy["sub_agents"]), 3)
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
        self.assertEqual(mcp_status["mcp_tools_manifest"]["tool_count"], 5)
        tools_yaml = (ROOT_DIR / "agent" / "tools.yaml").read_text(encoding="utf-8")
        for tool_name in (
            "gql_keystone_band",
            "gql_cascade_paths_to_json",
            "gql_compounded_cascade_score",
            "gql_track3_anchor_closure",
            "sql_equity_and_mailbox_audit",
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
            "/api/hierarchy",
            "/api/mcp-status",
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
            ("/api/chat", {"message": "Why not Primo? Audit the virtual mailbox bias"}),
            ("/api/chat", {"message": "Simulate anchor shock on block 200894"}),
            ("/api/reload", {}),
        ]
        for path, body in post_tests:
            status, payload = handle_api_post(path, body)
            self.assertEqual(status, 200, f"POST {path} failed with {status}")
            self.assertIsInstance(payload, dict)
            if path == "/api/chat":
                self.assertIn("sub_agent_routed", payload)
                self.assertEqual(payload["root_orchestrator"], "market_castro_grant_advisor")

        # Verify FastAPI app object is initialized when fastapi is installed
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main(verbosity=2)
