"""
Managed BigQuery MCP (`https://bigquery.googleapis.com/mcp`) & MCP Toolbox
configuration for the Market/Castro Grant Defense ADK Agent.

Follows Section 9 of `notebooks/c3_01_load_explore.ipynb`:
- Uses Google Application Default Credentials (`google.auth.default`) with
  scope `https://www.googleapis.com/auth/bigquery`
- Injects `Authorization: Bearer <token>` and `x-goog-user-project: <PROJECT_ID>`
  into `StreamableHTTPConnectionParams` for `MCPToolset`.
"""

from __future__ import annotations

import os
from typing import Any

BIGQUERY_MCP_URL = "https://bigquery.googleapis.com/mcp"


def build_bigquery_mcp_toolset(project_id: str | None = None) -> Any | None:
    """
    Build an ADK `MCPToolset` connected to Google's Managed BigQuery MCP server
    (`https://bigquery.googleapis.com/mcp`) if `google-adk` and `google-auth`
    are installed and `ENABLE_BIGQUERY_MCP=true`.
    """
    if os.environ.get("ENABLE_BIGQUERY_MCP", "false").lower() not in ("1", "true", "yes"):
        return None

    resolved_project = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
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
