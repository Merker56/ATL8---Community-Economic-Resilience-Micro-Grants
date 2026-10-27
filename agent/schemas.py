"""
Structured data schemas for the A4I 2026 Challenge 3 Grant Defense Agent
(Market/Castro Corridor, San Francisco).

Maps directly to the 7 mandatory sections of the Friday Grant Committee Memo
and BigQuery Property Graph `TO_JSON(p)` path format.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DownstreamCascadeNode:
    business_id: str
    name: str
    address: str
    naics4: str
    naics_label: str
    hop: int
    via_business_id: str | None
    via_business_name: str | None
    edge_intensity: float
    compounded_intensity: float
    bottleneck_intensity: float
    metres: float
    is_verified_edge: bool = False
    is_virtual_mailbox: bool = False


@dataclass
class TractEquityContext:
    tract_geoid: str
    tract_name: str
    total_pop: float
    median_income: float
    poverty_rate: float
    no_vehicle_rate: float
    assistance_rate: float
    corridor_avg_poverty_rate: float
    corridor_avg_no_vehicle_rate: float
    relative_need_multiplier: float


@dataclass
class FridayGrantMemo:
    """The 7-Part Friday Grant Committee Defense Memo required by the rubric."""

    corridor: str
    budget_pool_usd: float
    # Part 1: Which business (by name & address) and how much
    recommended_business_id: str
    recommended_business_name: str
    recommended_address: str
    recommended_naics4: str
    recommended_naics_label: str
    grant_amount_usd: float
    allocation_split_note: str
    # Part 2: What it protects (the cascade in concrete terms)
    direct_1hop_count: int
    indirect_2hop_count: int
    total_2hop_exposed_count: int
    brick_and_mortar_exposed_count: int
    total_1hop_intensity: float
    total_compounded_cascade_score: float
    estimated_downstream_jobs_protected: float
    expected_jobs_saved_delta: float
    cost_per_expected_job_saved_usd: float
    # Part 3: Traversal shown (GQL query + TO_JSON(p) graph structure + named paths)
    gql_query_executed: str
    to_json_paths: list[dict[str, Any]]
    cascade_nodes: list[dict[str, Any]]
    # Part 4: Why this one and NOT the runner-up (or raw centrality hub)
    runner_up_business_id: str
    runner_up_business_name: str
    runner_up_address: str
    runner_up_naics_label: str
    why_not_runner_up: str
    why_not_biggest_hub: str
    duplicate_registration_note: str
    # Part 5: Explicit assumptions (grant changes a survival probability, not certainty)
    p_fail_without_grant: float
    p_fail_with_grant: float
    delta_survival_probability: float
    substitutability_discount: float
    assumptions_statement: str
    # Part 6: One honest line on which evidence is REAL vs. MODELED
    real_vs_modeled_statement: str
    sba_loan_validation_note: str
    # Part 7: Who lives around it (Census tract demographics with 11-char LPAD geo_id)
    tract_context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubAgentStepTrace:
    """Execution trace for one specialist sub-agent in the Multi-Agent workflow."""

    step_order: int
    sub_agent_name: str
    role_description: str
    tools_invoked: list[str]
    gql_queries_executed: list[str]
    execution_ms: float
    status: str
    key_findings_summary: str


@dataclass
class EndToEndWorkflowResult:
    """
    Unified End-to-End Multi-Agent Workflow output connecting:
      - Member 1 (Data & BigQuery Property Graph `a4i_econ.LocalEconomy`)
      - Member 2 (Google ADK Root Orchestrator + 3 Specialist Sub-Agents + MCP)
      - Member 3 (Grant Officer Defense Console UI)
    """

    workflow_id: str
    corridor: str
    execution_mode: str
    total_execution_ms: float
    sub_agent_traces: list[dict[str, Any]]
    graph_discovery: dict[str, Any]
    equity_and_bias_audit: dict[str, Any]
    portfolio_optimization: dict[str, Any]
    primary_friday_memo: dict[str, Any]
    runner_up_comparison: dict[str, Any]
    anchor_shock_simulation: dict[str, Any]
    executive_committee_brief: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

