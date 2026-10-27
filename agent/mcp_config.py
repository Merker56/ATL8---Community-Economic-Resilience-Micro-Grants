"""
Managed BigQuery MCP (`https://bigquery.googleapis.com/mcp`), MCP Toolbox, and
Live BigQuery Property Graph (`a4i_econ.LocalEconomy`) Bridge for Member 2.

Follows Section 9 of `notebooks/c3_01_load_explore.ipynb`:
- Uses Google Application Default Credentials (`google.auth.default`) with
  scope `https://www.googleapis.com/auth/bigquery`
- Injects `Authorization: Bearer <token>` and `x-goog-user-project: <PROJECT_ID>`
  into `StreamableHTTPConnectionParams` for `MCPToolset`.
- Also provides `execute_live_bigquery_gql()` for direct execution of Member 1's
  `GRAPH a4i_econ.LocalEconomy` queries when `USE_LIVE_BIGQUERY=true`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BIGQUERY_MCP_URL = "https://bigquery.googleapis.com/mcp"
TOOLS_YAML_PATH = Path(__file__).resolve().parent / "tools.yaml"


def load_mcp_tools_yaml_manifest() -> dict[str, Any]:
    """
    Parse `agent/tools.yaml` to list parameterized BigQuery GQL/SQL tools configured
    for MCP Toolbox for Databases without requiring external YAML packages when unavailable.
    """
    if not TOOLS_YAML_PATH.exists():
        return {"exists": False, "tools": []}
    raw = TOOLS_YAML_PATH.read_text(encoding="utf-8")
    tool_names: list[str] = []
    in_tools = False
    for line in raw.splitlines():
        if line.strip() == "tools:":
            in_tools = True
            continue
        if in_tools and line.startswith("  ") and not line.startswith("    "):
            name = line.strip().rstrip(":")
            if name and not name.startswith("#"):
                tool_names.append(name)
    return {
        "exists": True,
        "path": str(TOOLS_YAML_PATH),
        "tool_count": len(tool_names),
        "tools": tool_names,
    }


def get_mcp_and_bigquery_status() -> dict[str, Any]:
    """Return diagnostic readiness status for BigQuery MCP and live BigQuery GQL."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT_ID", "")
    enable_mcp = os.environ.get("ENABLE_BIGQUERY_MCP", "false").lower() in ("1", "true", "yes")
    use_live_bq = os.environ.get("USE_LIVE_BIGQUERY", "false").lower() in ("1", "true", "yes")

    has_adk = False
    has_bq_client = False
    has_google_auth = False

    try:
        import google.adk  # noqa: F401
        has_adk = True
    except ImportError:
        pass

    try:
        from google.cloud import bigquery  # noqa: F401
        has_bq_client = True
    except ImportError:
        pass

    try:
        import google.auth  # noqa: F401
        has_google_auth = True
    except ImportError:
        pass

    return {
        "bigquery_mcp_endpoint": BIGQUERY_MCP_URL,
        "tools_yaml_path": str(TOOLS_YAML_PATH),
        "tools_yaml_exists": TOOLS_YAML_PATH.exists(),
        "mcp_tools_manifest": load_mcp_tools_yaml_manifest(),
        "google_cloud_project": project_id or "(not set — using local graph engine)",
        "enable_bigquery_mcp_flag": enable_mcp,
        "use_live_bigquery_flag": use_live_bq,
        "packages_installed": {
            "google_adk": has_adk,
            "google_cloud_bigquery": has_bq_client,
            "google_auth": has_google_auth,
        },
        "active_execution_mode": (
            "LIVE_BIGQUERY_GQL"
            if (use_live_bq and bool(project_id) and has_bq_client)
            else "LOCAL_PROPERTY_GRAPH_ENGINE_WITH_BQ_FALLBACK"
        ),
    }


def build_bigquery_mcp_toolset(project_id: str | None = None) -> Any | None:
    """
    Build an ADK `MCPToolset` connected to Google's Managed BigQuery MCP server
    (`https://bigquery.googleapis.com/mcp`) if `google-adk` and `google-auth`
    are installed and `ENABLE_BIGQUERY_MCP=true`.
    """
    if os.environ.get("ENABLE_BIGQUERY_MCP", "false").lower() not in ("1", "true", "yes"):
        return None

    resolved_project = (
        project_id
        or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        or os.environ.get("GCP_PROJECT_ID", "")
    )
    if not resolved_project:
        return None

    try:
        import google.auth
        import google.auth.transport.requests
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StreamableHTTPConnectionParams,
        )
        from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/bigquery"]
        )
        creds.refresh(google.auth.transport.requests.Request())
        headers = {
            "Authorization": f"Bearer {creds.token}",
            "x-goog-user-project": resolved_project,
        }
        return MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=BIGQUERY_MCP_URL,
                headers=headers,
            )
        )
    except Exception:
        return None


def execute_live_bigquery_gql(
    gql_query: str,
    project_id: str | None = None,
    timeout_sec: float = 20.0,
) -> dict[str, Any]:
    """
    Execute a `GRAPH a4i_econ.LocalEconomy` GQL query against live BigQuery when
    Member 1's BigQuery dataset is active and `USE_LIVE_BIGQUERY=true`.
    Gracefully returns status=`skipped` or `fallback` if live BigQuery is disabled.
    """
    use_live = os.environ.get("USE_LIVE_BIGQUERY", "false").lower() in ("1", "true", "yes")
    resolved_project = (
        project_id
        or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        or os.environ.get("GCP_PROJECT_ID", "")
    )
    if not use_live or not resolved_project:
        return {
            "executed_on_bigquery": False,
            "mode": "LOCAL_ENGINE",
            "reason": "USE_LIVE_BIGQUERY is false or GOOGLE_CLOUD_PROJECT is not set.",
            "rows": [],
        }

    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=resolved_project)
        job = client.query(gql_query)
        result = job.result(timeout=timeout_sec)
        rows = [dict(row.items()) for row in result]
        return {
            "executed_on_bigquery": True,
            "mode": "LIVE_BIGQUERY",
            "project_id": resolved_project,
            "row_count": len(rows),
            "rows": rows,
        }
    except Exception as exc:
        return {
            "executed_on_bigquery": False,
            "mode": "LOCAL_ENGINE_FALLBACK",
            "reason": f"BigQuery execution fallback: {exc}",
            "rows": [],
        }
