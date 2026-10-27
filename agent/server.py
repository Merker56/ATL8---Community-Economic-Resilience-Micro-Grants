"""
HTTP Server for the A4I 2026 Challenge 3 "Grant Officer Defense Console"
(Market/Castro Corridor, San Francisco).

Runs anywhere with zero external dependencies using Python's standard library
`ThreadingHTTPServer`, and also exposes a FastAPI `app` when `fastapi` is installed.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .agent import run_grant_officer_chat
from .tools import (
    ENGINE,
    add_verified_merchant_supplier,
    audit_corridor_equity_and_bias,
    compare_grant_candidates,
    discover_cascade_candidates,
    generate_friday_grant_memo,
    optimize_corridor_portfolio,
    simulate_anchor_closure,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _bool_param(params: dict[str, list[str]], key: str, default: bool = True) -> bool:
    val = params.get(key, [str(default)])[0].lower()
    return val in ("1", "true", "yes", "on")


def _float_param(params: dict[str, list[str]], key: str, default: float) -> float:
    try:
        return float(params.get(key, [str(default)])[0])
    except (ValueError, TypeError):
        return default


def _int_param(params: dict[str, list[str]], key: str, default: int) -> int:
    try:
        return int(params.get(key, [str(default)])[0])
    except (ValueError, TypeError):
        return default


def handle_api_get(path: str, query_string: str) -> tuple[int, dict[str, Any]]:
    params = parse_qs(query_string)

    if path == "/api/overview":
        discovery = discover_cascade_candidates(
            exclude_virtual_mailboxes=True,
            exclude_monopoly_artifacts=True,
            min_reach=3,
            max_reach=35,
            top_k=12,
        )
        default_memo = generate_friday_grant_memo(
            business_query="Theatre Rhinoceros",
            runner_up_query="Cafe Du Nord",
            grant_amount_usd=25000.0,
            budget_pool_usd=50000.0,
            p_fail_without_grant=0.65,
            p_fail_with_grant=0.15,
            substitutability_discount=0.20,
        )
        audit = audit_corridor_equity_and_bias()
        default_portfolio = optimize_corridor_portfolio(
            budget_pool_usd=50000.0,
            num_grantees=2,
            min_effective_grant_usd=15000.0,
            deduplicate_subgraphs=True,
        )
        return 200, {
            "summary": ENGINE.summary,
            "discovery": discovery,
            "default_memo": default_memo,
            "default_portfolio": default_portfolio,
            "employer_blocks": ENGINE.employer_blocks,
            "audit_highlights": {
                "virtual_mailbox_hubs": audit["virtual_mailbox_hub_audit"],
                "duplicate_dbas": audit["duplicate_dba_audit"],
                "sba_loans": audit["sba_7a_historical_loans"],
                "tracts": audit["tract_demographics_lpad11"],
            },
        }

    if path == "/api/portfolio":
        res = optimize_corridor_portfolio(
            budget_pool_usd=_float_param(params, "budget_pool", 50000.0),
            num_grantees=_int_param(params, "num_grantees", 2),
            min_effective_grant_usd=_float_param(params, "min_floor", 15000.0),
            deduplicate_subgraphs=_bool_param(params, "deduplicate", True),
        )
        return 200, res

    if path == "/api/candidates":
        res = discover_cascade_candidates(
            exclude_virtual_mailboxes=_bool_param(params, "exclude_vm", True),
            exclude_monopoly_artifacts=_bool_param(params, "exclude_monopoly", True),
            min_reach=_int_param(params, "min_reach", 3),
            max_reach=_int_param(params, "max_reach", 35),
            top_k=_int_param(params, "top_k", 15),
        )
        return 200, res

    if path == "/api/memo":
        biz_q = params.get("business", ["Theatre Rhinoceros"])[0]
        runner_q = params.get("runner_up", ["Cafe Du Nord"])[0]
        res = generate_friday_grant_memo(
            business_query=biz_q,
            runner_up_query=runner_q,
            grant_amount_usd=_float_param(params, "grant_amount", 25000.0),
            budget_pool_usd=_float_param(params, "budget_pool", 50000.0),
            p_fail_without_grant=_float_param(params, "p_fail_no_grant", 0.65),
            p_fail_with_grant=_float_param(params, "p_fail_grant", 0.15),
            substitutability_discount=_float_param(params, "sub_discount", 0.20),
        )
        return 200, res

    if path == "/api/compare":
        a_q = params.get("a", ["Theatre Rhinoceros"])[0]
        b_q = params.get("b", ["Cafe Du Nord"])[0]
        res = compare_grant_candidates(
            business_query_a=a_q,
            business_query_b=b_q,
            grant_amount_usd=_float_param(params, "grant_amount", 25000.0),
            p_fail_without_grant=_float_param(params, "p_fail_no_grant", 0.65),
            p_fail_with_grant=_float_param(params, "p_fail_grant", 0.15),
        )
        return 200, res

    if path == "/api/anchor-shock":
        anchor_q = params.get("anchor", ["200894"])[0]
        return 200, simulate_anchor_closure(anchor_q)

    if path == "/api/equity-audit":
        return 200, audit_corridor_equity_and_bias()

    return 404, {"error": f"Unknown endpoint {path}"}


def handle_api_post(path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if path == "/api/merchant-intake":
        res = add_verified_merchant_supplier(
            buyer_query=str(body.get("buyer_query", "The Castro")),
            supplier_query=str(body.get("supplier_query", "Theatre Rhinoceros")),
            reported_dependency_share=float(body.get("reported_dependency_share", 0.35)),
            invoice_note=str(
                body.get("invoice_note", "Merchant self-reported local supplier intake")
            ),
        )
        return 200, res

    if path == "/api/chat":
        msg = str(body.get("message", ""))
        return 200, run_grant_officer_chat(msg)

    return 404, {"error": f"Unknown POST endpoint {path}"}


class GrantConsoleHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Keep console output clean
        pass

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            status, payload = handle_api_get(parsed.path, parsed.query)
            self._send_json(status, payload)
            return

        # Serve index.html
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            content = index_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_json(404, {"error": "Static UI index.html not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            body = {}
        status, payload = handle_api_post(parsed.path, body)
        self._send_json(status, payload)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), GrantConsoleHTTPHandler)
    print(
        f"A4I 2026 Market/Castro Grant Officer Defense Console running at http://{host}:{port}"
    )
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    run_server(host=host, port=port)
