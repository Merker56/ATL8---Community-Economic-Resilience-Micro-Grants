"""
agent/test_offline_tracks.py
Smoke-test & verification runner for the Development Track.
Exercises all 6 agent tools in holistic all-applicant mode.

Usage (from repo root):
  A4I_MODE=mock python3 -m agent.test_offline_tracks
"""

import json
import os

os.environ.setdefault("A4I_MODE", "mock")

try:
    from .holistic_engine import (
        analyze_anchor_closure_shock,
        analyze_main_street_applicants,
        find_vulnerable_micro_producers,
        list_corridor_demo_candidates,
        record_verified_supplier_edge,
        run_equity_and_fragility_audit,
    )
except ImportError:
    from holistic_engine import (  # type: ignore
        analyze_anchor_closure_shock,
        analyze_main_street_applicants,
        find_vulnerable_micro_producers,
        list_corridor_demo_candidates,
        record_verified_supplier_edge,
        run_equity_and_fragility_audit,
    )


def main() -> None:
    print("=" * 76)
    print(f" A4I Challenge 3 Holistic Portfolio Verification (A4I_MODE={os.environ.get('A4I_MODE')})")
    print("=" * 76)

    # 0. Demo overview
    seeds = list_corridor_demo_candidates("Central Market")
    print(f"\n[0] Corridor: {seeds['corridor']} | Core Named Applicants: {seeds['core_named_corridor_applicants_count']}")

    # 1. Track 1: Holistic evaluation of ALL corridor applicants with $150,000 budget
    t1 = analyze_main_street_applicants(corridor="Central Market", budget=150000.0, applicant_ids="all")
    print(
        f"\n[1] Track 1 Holistic Evaluation — Budget=${t1['total_budget_usd']:,.0f} | "
        f"Evaluated={t1['total_applicants_evaluated']} | "
        f"Funded={t1['total_applicants_funded']} | "
        f"Held/Excluded/Waitlisted={t1['total_applicants_held_excluded_or_waitlisted']}"
    )
    print("  Recommended Multi-Bucket Portfolio Grants:")
    for g in t1["recommended_portfolio_grants"]:
        print(
            f"    + ${g['recommended_grant_usd']:>8,.0f} ({g['share_of_total_budget_pct']:>4.1f}%) -> "
            f"{g['applicant_id']} {g['applicant_name']} [{g['advisor_tier']}] "
            f"(2-hop={g['total_exposed_2hop_businesses']}, poverty={g['tract_poverty_rate_pct']}%)"
        )
    print("  Non-Funded Applicants (Every Applicant Accounted For):")
    for u in t1["non_funded_holds_exclusions_and_waitlist"]:
        print(
            f"    - $       0 -> {u['applicant_id']} {u['applicant_name']}: {u['decision_status']}"
        )

    # 2. Track 2: Proactive Micro-Producer Cohort Discovery ($100,000 budget)
    t2 = find_vulnerable_micro_producers(corridor="Central Market", budget=100000.0, min_reach=5, max_reach=25)
    print(f"\n[2] Track 2 Cohort Discovery — {t2['discovered_producers_count']} sweet-spot producers funded:")
    for p in t2["holistic_producer_portfolio_allocations"]:
        print(
            f"    + ${p['recommended_grant_usd']:>8,.0f} -> {p['producer_id']} ({p['producer_name']}): "
            f"2-hop={p['total_2hop_exposed']}, sole_supplier={p['is_sole_corridor_supplier']}"
        )

    # 3. Track 3: Anchor Closure Dual-Horizon Portfolio ($150,000 budget)
    t3 = analyze_anchor_closure_shock(block_id="060750125021004", corridor="Central Market", budget=150000.0)
    h1 = t3["holistic_dual_horizon_portfolio"]["horizon_1_upstream_supply_stabilization_55pct"]
    h2 = t3["holistic_dual_horizon_portfolio"]["horizon_2_frontline_footfall_pivot_45pct"]
    print(
        f"\n[3] Track 3 Anchor Closure — {len(h1)} Upstream Suppliers (55% Pool) + "
        f"{len(h2)} Frontline Storefronts (45% Pool) funded."
    )

    # 4. Equity, Bias & SBA Fragility Audit
    audit = run_equity_and_fragility_audit(corridor="Central Market")
    print(
        f"\n[4] Equity, Bias & SBA Audit — Duplicate Registrations Flagged: "
        f"{len(audit['3_near_duplicate_registrations_detected'])}"
    )

    # 5. Field Verification Loop
    ver = record_verified_supplier_edge(
        supplier_name="Bayside Roasters",
        buyer_name="Sixth St Bakery & Cafe",
        input_share=0.12,
        is_replaceable=False,
        notes="Invoice verified during grant officer walk-through",
    )
    print(
        f"\n[5] Field Verification Loop — {ver['status']}: "
        f"New priority score={ver['updated_supplier_cascade_summary']['holistic_priority_score']}"
    )


if __name__ == "__main__":
    main()
