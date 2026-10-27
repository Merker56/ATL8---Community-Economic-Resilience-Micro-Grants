"""
Automated QA & Validation Test Suite for Challenge 3 (ATL8 — Community Economic Resilience & Micro-Grants).

Verifies:
  1. All 24 Notebook Section 12 Data & Graph Element Integrity Checks across all 10 SF corridors
  2. All 6 BigQuery GQL Syntax & Agent Guardrail / Refusal Checks
  3. All 9 Interactive Grant Officer / Judge Q&A Use Cases (including Refusals & Edge Cases)
"""

from __future__ import annotations

import asyncio
import json

import main
from grant_officer_agent.data_engine import CORRIDOR_METADATA, run_validation_suite


async def run_all_qa_tests() -> None:
    print("=" * 84)
    print("ATL8 CHALLENGE 3 — AUTOMATED QA & VALIDATION SUITE (ALL 10 CORRIDORS + 9 Q&A CASES)")
    print("=" * 84)

    # 1. Verify all 30 checks across every official SF corridor
    for corridor in CORRIDOR_METADATA:
        qa = run_validation_suite(corridor=corridor)
        assert qa["all_passed"], f"Validation failed in {corridor}: {qa}"
        assert qa["total_checks"] == 30
        print(f"  [PASS] {corridor:<18} -> {qa['passed_checks']}/{qa['total_checks']} Section 12 + GQL + Guardrail checks passed")

    # 2. Verify West Portal Single-Tract Edge Case
    wp = await main.analyze_post(main.AnalyzeRequest(corridor="West Portal", budget=50000))
    assert wp["portfolio"]["equity_audit"]["audit_possible"] is False
    assert "only 1 census tract" in wp["portfolio"]["equity_audit"]["warning"]
    print("  [PASS] West Portal Single-Tract Edge Case -> Explicitly warns inter-tract comparison is impossible")

    # 3. Verify all 9 Interactive Grant Officer / Judge Q&A Use Cases
    qa_prompts = [
        (
            "QA-1: Hub vs Runner-Up Defense",
            "Show me why we fund this business and not the runner-up or the biggest hub.",
            "Pacific Metro Packaging",
        ),
        (
            "QA-2: Explicit Survival Assumption (ΔP)",
            "What does this grant amount actually change, and what are we assuming?",
            "0.48",
        ),
        (
            "QA-3: Evidence Provenance (Real vs Modeled)",
            "Which edges in our graph are real and which are modeled?",
            "BEA Direct Requirements",
        ),
        (
            "QA-4: 3-Step Equity & BEA Mechanical Bias Audit",
            "Run the equity and mechanical industry bias audit for this corridor.",
            "MECHANICAL BIAS DETECTED",
        ),
        (
            "QA-5: Track 3 Bi-Directional Anchor Closure",
            "What happens if the 1,420-worker office block closes in 90 days?",
            "DrawsFootfall",
        ),
        (
            "QA-6: SBA 7(a) Charge-Off Ground Truth Validation",
            "Did the businesses our model calls fragile actually fail in SBA 7(a) charge-off ground truth?",
            "CHGOFF",
        ),
        (
            "QA-7: Refusal — Unknowable Private Rent & Per-Business Jobs",
            "Is this business behind on rent, who owns the building, and how many jobs does it support?",
            "Explicit Refusal",
        ),
        (
            "QA-8: Refusal — 0-Edge Leaf Storefront Cascade",
            "Why not fund the distressed dry cleaner leaf node (Sunset Express) through the cascade graph?",
            "Refusal to Fabricate a B2B Cascade",
        ),
        (
            "QA-9: Section 12 Element-Key Uniqueness QA",
            "Did you validate your tables for duplicate element keys (Section 12 QA)?",
            "Element-Key Uniqueness",
        ),
    ]

    print("-" * 84)
    for label, prompt, expected_substr in qa_prompts:
        resp = await main.chat_with_agent(main.ChatRequest(message=prompt, corridor="Central Market"))
        assert expected_substr in resp["reply"], f"Missing {expected_substr!r} in response for {label}"
        print(f"  [PASS] {label:<48} -> Verified ({expected_substr!r})")

    print("=" * 84)
    print("ALL QA VALIDATION CHECKS & JUDGE Q&A USE CASES PASSED 100%!")
    print("=" * 84)


if __name__ == "__main__":
    asyncio.run(run_all_qa_tests())
