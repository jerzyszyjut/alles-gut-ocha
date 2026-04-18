"""Claude-powered chatbot for humanitarian crisis analysis."""
from __future__ import annotations

import json
import math
from typing import Any

import anthropic
import pandas as pd

from api.scorer import compute_scores, iso3_to_name

# ── Static system prompt ──────────────────────────────────────────────────────
# Cached at the Anthropic level — changes here invalidate the cache.

_METHODOLOGY = """
## Neglect Index — Full Methodology

### What it measures
The neglect_index (0–1) identifies humanitarian crises that are simultaneously
*severe* (many people in dire need) and *underfunded* (little money reaching them).
A score near 1 = maximally overlooked. Higher score → more urgent political attention needed.

### Core formula
  neglect_index = Sw × severity_score + Gw × (1 − coverage_rank)

Default weights: Sw = 0.6 (severity), Gw = 0.4 (funding gap)
Both weights are auto-normalised, so only their ratio matters.

### Severity score (computed within-cluster percentile ranks)
All ranks compare a country ONLY to peer countries in the SAME humanitarian cluster.
This prevents Food Security from being unfairly compared to Logistics.

Case A — IPC food data AND conflict events both available:
  severity = Nw×need_rank + Iw×ipc_severity + Ew×events_rank
  (defaults Nw=0.5, Iw=0.4, Ew=0.1; normalised to sum to 1)

Case B — only IPC food data (Food Security cluster, no events):
  severity = normalised(Nw×need_rank + Iw×ipc_severity)

Case C — only conflict events (no IPC data):
  severity = normalised(Nw×need_rank + Ew×events_rank)

Case D — neither auxiliary dataset:
  severity = need_rank

### Metric definitions
| Metric | Definition |
|---|---|
| need_rank | Percentile of People_In_Need within same cluster (0=least, 1=most) |
| coverage | funding_cluster_specific / requirements_cluster_specific, clipped [0,1] |
| coverage_rank | Percentile of coverage ratio within same cluster (0=least funded, 1=most) |
| ipc_severity_score | Weighted avg IPC phase 1–5, normalised: (avg_phase − 1) / 4 → [0,1] |
| uncertainty | Std dev of neglect_index across 200 bootstrap resamples |

### IPC phases (Food Security severity)
Phase 1 = Minimal food insecurity → ipc_severity_score ≈ 0
Phase 2 = Stressed
Phase 3 = Crisis
Phase 4 = Emergency
Phase 5 = Famine → ipc_severity_score ≈ 1

### Priority labels (default thresholds, adjustable)
critical → neglect_index ≥ 0.8
high     → neglect_index ≥ 0.6
medium   → neglect_index ≥ 0.4
low      → neglect_index < 0.4

### Data sources
- FTS (OCHA Financial Tracking Service): funding and requirements per country/cluster/year
- HPC (Humanitarian Programme Cycle): people in need per sector
- IPC (Integrated Food Security Phase Classification): food insecurity severity by phase
- ACLED: number of events targeting civilians per country/year

### Available data
Years: 2024, 2025
Clusters: Agriculture · Camp Coordination / Management · Coordination and support services ·
  Early Recovery · Education · Emergency Shelter and NFI · Food Security · Health ·
  Logistics · Multi-sector · Nutrition · Protection · Protection - Child Protection ·
  Protection - Gender-Based Violence · Protection - Housing Land and Property ·
  Protection - Mine Action · Water Sanitation Hygiene
"""

_SYSTEM_STATIC = (
    "You are an expert humanitarian crisis analyst for the OCHA UN Datathon project. "
    "You help analysts understand which humanitarian crises are most overlooked by "
    "explaining the Neglect Index ranking — a data-driven score combining crisis "
    "severity with funding coverage gaps.\n\n"
    "## Your responsibilities\n"
    "1. **Explain rankings**: Why is country X ranked high? Cite exact metric values "
    "(neglect_index, coverage %, people in need, IPC phase, events rank).\n"
    "2. **Explore the data**: Help users filter by country, sector, year and adjust "
    "scoring weights to reflect their priorities.\n"
    "3. **Compare crises**: Compare across dimensions — need vs funding vs food insecurity "
    "vs conflict.\n"
    "4. **Change the view**: When users want to focus on something different, call "
    "`update_ranking_parameters` to update the frontend visualisation.\n\n"
    "## Behavioural rules\n"
    "- Always be specific: cite actual neglect_index values, coverage percentages, "
    "people in need counts.\n"
    "- Before explaining a ranking, call `query_ranking` to get fresh data with "
    "the exact numbers.\n"
    "- When you adjust weights (e.g. 'prioritise food insecurity'), explain what the "
    "weight change means mathematically.\n"
    "- If a user asks 'why is X ranked high', query X's data first, then explain "
    "each contributing metric.\n"
    "- Keep responses concise and decision-focused — this is a triage tool.\n\n"
    "## Output format rules — CRITICAL\n"
    "The frontend displays structured data separately from your text reply. "
    "Your text reply must NEVER duplicate data that is already delivered via tools:\n"
    "- When you call `update_ranking_parameters`, do NOT include a markdown table of "
    "results and do NOT list the changed parameters with before/after values. "
    "The frontend renders the updated ranking automatically. "
    "Just write 1–3 sentences explaining *why* the change matters analytically.\n"
    "- When you call `query_ranking`, do NOT reproduce the results as a markdown table. "
    "Reference specific values inline (e.g. 'Sudan Food Security has 0.3% coverage') "
    "but do not reprint the full dataset.\n"
    "- Never output sections titled '### New top 5', '### What changed', "
    "'### Parameters updated', or any table that mirrors tool output.\n\n"
    + _METHODOLOGY
)

# ── Tool definitions ──────────────────────────────────────────────────────────

_FILTER_PROPS: dict[str, Any] = {
    "year": {
        "type": "array", "items": {"type": "integer"},
        "description": "Filter by year(s). Available: 2024, 2025. Omit for all years.",
    },
    "cluster": {
        "type": "array", "items": {"type": "string"},
        "description": "Filter by humanitarian cluster name(s). Must match exactly.",
    },
    "country": {
        "type": "array", "items": {"type": "string"},
        "description": "Filter by ISO-3 country code(s), e.g. ['AFG', 'SYR', 'SDN'].",
    },
    "min_people_in_need": {
        "type": "integer",
        "description": "Exclude rows where people in need is below this threshold.",
    },
    "max_coverage": {
        "type": "number",
        "description": "Exclude crises where funding coverage exceeds this ratio [0-1]. "
                       "Use e.g. 0.5 to exclude crises that are more than 50% funded.",
    },
    "min_neglect_index": {
        "type": "number",
        "description": "Only include crises at or above this neglect score [0-1].",
    },
}

_WEIGHT_PROPS: dict[str, Any] = {
    "severity_weight": {
        "type": "number",
        "description": "Weight of severity in the neglect index (default 0.6). "
                       "Increase to prioritise more severe crises regardless of funding.",
    },
    "funding_gap_weight": {
        "type": "number",
        "description": "Weight of funding gap in the neglect index (default 0.4). "
                       "Increase to prioritise the most underfunded crises.",
    },
    "need_weight": {
        "type": "number",
        "description": "Weight of people-in-need percentile within severity (default 0.5).",
    },
    "ipc_weight": {
        "type": "number",
        "description": "Weight of IPC food insecurity severity within severity (default 0.4). "
                       "Only affects Food Security cluster rows.",
    },
    "events_weight": {
        "type": "number",
        "description": "Weight of civilian conflict events within severity (default 0.1).",
    },
}

_DISPLAY_PROPS: dict[str, Any] = {
    "critical_threshold": {
        "type": "number",
        "description": "Neglect index at or above which a crisis is labelled 'critical' (default 0.8).",
    },
    "high_threshold": {
        "type": "number",
        "description": "Neglect index at or above which a crisis is labelled 'high' (default 0.6).",
    },
    "sort_by": {
        "type": "string",
        "description": "Column to sort by. Default: 'neglect_index'.",
    },
    "sort_desc": {
        "type": "boolean",
        "description": "Sort descending (default true).",
    },
    "limit": {
        "type": "integer",
        "description": "Maximum results to return.",
    },
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "query_ranking",
        "description": (
            "Query the neglect ranking to get data that supports your explanation. "
            "Call this before explaining why a country ranks high — you need the numbers. "
            "All parameters are optional; omit to use current frontend parameters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **_FILTER_PROPS,
                **_WEIGHT_PROPS,
                **_DISPLAY_PROPS,
            },
        },
    },
    {
        "name": "update_ranking_parameters",
        "description": (
            "Update the ranking parameters shown in the frontend visualisation. "
            "Call this when the user asks to: focus on specific countries/clusters/years, "
            "change scoring weights (e.g. 'prioritise food insecurity'), apply filters "
            "(e.g. 'only show crises below 30% funded'), or adjust threshold labels. "
            "Specify ONLY the parameters you want to change — everything else keeps its "
            "current value. After calling this, explain what changed and why it matters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **_FILTER_PROPS,
                **_WEIGHT_PROPS,
                **_DISPLAY_PROPS,
            },
        },
    },
]

# ── Default parameters ────────────────────────────────────────────────────────

DEFAULT_PARAMS: dict[str, Any] = {
    "year": None,
    "cluster": None,
    "country": None,
    "min_people_in_need": None,
    "max_coverage": None,
    "min_neglect_index": None,
    "severity_weight": 0.6,
    "funding_gap_weight": 0.4,
    "need_weight": 0.5,
    "ipc_weight": 0.4,
    "events_weight": 0.1,
    "critical_threshold": 0.8,
    "high_threshold": 0.6,
    "sort_by": "neglect_index",
    "sort_desc": True,
    "limit": None,
}

# ── Execution helpers ─────────────────────────────────────────────────────────

def _opt(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _apply_filters(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    if params.get("year"):
        df = df[df["year"].isin(params["year"])]
    if params.get("cluster"):
        df = df[df["cluster"].isin(params["cluster"])]
    if params.get("country"):
        df = df[df["countryCode"].isin(params["country"])]
    if params.get("min_people_in_need") is not None:
        df = df[df["People_In_Need"] >= params["min_people_in_need"]]
    return df


def _execute_query(params: dict, df_base: pd.DataFrame) -> list[dict]:
    df = _apply_filters(df_base.copy(), params)
    if df.empty:
        return []

    df = compute_scores(
        df,
        severity_weight=params.get("severity_weight", 0.6),
        funding_gap_weight=params.get("funding_gap_weight", 0.4),
        need_weight=params.get("need_weight", 0.5),
        ipc_weight=params.get("ipc_weight", 0.4),
        events_weight=params.get("events_weight", 0.1),
        n_bootstrap=0,
    )

    if params.get("max_coverage") is not None:
        df = df[df["coverage"] <= params["max_coverage"]]
    if params.get("min_neglect_index") is not None:
        df = df[df["neglect_index"] >= params["min_neglect_index"]]

    sort_by = params.get("sort_by", "neglect_index")
    sort_desc = params.get("sort_desc", True)
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=not sort_desc, na_position="last")

    limit = params.get("limit", None)
    rows = []
    for _, row in (df.head(limit) if limit is not None else df).iterrows():
        rows.append({
            "countryCode": row["countryCode"],
            "countryName": iso3_to_name(row["countryCode"]),
            "year": int(row["year"]),
            "cluster": row["cluster"],
            "people_in_need": float(row["People_In_Need"]),
            "requirements_usd": _opt(row.get("requirements_cluster_specific")),
            "funding_usd": _opt(row.get("funding_cluster_specific")),
            "coverage": round(float(row["coverage"]), 4),
            "neglect_index": round(float(row["neglect_index"]), 4),
            "need_rank": round(float(row["need_rank"]), 4),
            "coverage_rank": round(float(row["coverage_rank"]), 4),
            "ipc_severity_score": _opt(row.get("ipc_severity_score")),
        })
    return rows


# ── Main chat function ────────────────────────────────────────────────────────

_client = anthropic.Anthropic()


def chat(
    messages: list[dict[str, str]],
    current_params: dict[str, Any],
    df_base: pd.DataFrame,
) -> dict[str, Any]:
    """Run one chat turn.

    Returns:
        reply: the assistant's text response
        parameter_update: merged params dict if Claude updated them, else None
        ranking_snapshot: top results under the new params, or None
    """
    # Merge user-supplied params over defaults (skip None values from frontend)
    effective_params = {
        **DEFAULT_PARAMS,
        **{k: v for k, v in current_params.items() if v is not None},
    }

    # Per-request dynamic context (not cached — changes each turn)
    dynamic_block = {
        "type": "text",
        "text": (
            "\n\n## Current frontend ranking parameters\n"
            f"```json\n{json.dumps(effective_params, indent=2)}\n```\n"
            "These are the parameters currently controlling the visualisation "
            "the user is looking at. Use them as defaults for any queries."
        ),
    }

    system = [
        # Large static methodology — cached at Anthropic for ~5 min
        {
            "type": "text",
            "text": _SYSTEM_STATIC,
            "cache_control": {"type": "ephemeral"},
        },
        # Dynamic context (current params) — not cached
        dynamic_block,
    ]

    # Convert simple {role, content} messages to API format
    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

    parameter_update: dict | None = None
    ranking_snapshot: list | None = None
    reply = ""

    # Agentic loop — keep going while Claude uses tools
    while True:
        response = _client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=system,
            tools=TOOLS,
            messages=api_messages,
        )

        if response.stop_reason == "end_turn":
            reply = next(
                (b.text for b in response.content if b.type == "text"), ""
            )
            break

        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "query_ranking":
                    # Merge tool params over current effective params
                    query_params = {**effective_params, **block.input}
                    query_params.setdefault("limit", None)
                    data = _execute_query(query_params, df_base)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(
                            {"total_results": len(data), "results": data},
                            default=str,
                        ),
                    })

                elif block.name == "update_ranking_parameters":
                    # Merge requested changes with current effective params
                    new_params = {**effective_params, **block.input}
                    parameter_update = new_params
                    effective_params = new_params  # affects subsequent queries this turn
                    # Compute a fresh snapshot under the new params for the frontend
                    snapshot = _execute_query({**new_params, "limit": None}, df_base)
                    ranking_snapshot = snapshot
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({
                            "status": "parameters_updated",
                            "applied_changes": block.input,
                            "top5_preview": snapshot[:5],
                        }, default=str),
                    })

            # Append assistant turn + tool results and continue the loop
            api_messages = api_messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results},
            ]

        else:
            # Unexpected stop reason — surface any text and exit
            reply = next(
                (b.text for b in response.content if b.type == "text"),
                "An unexpected issue occurred. Please try again.",
            )
            break

    return {
        "reply": reply,
        "parameter_update": parameter_update,
        "ranking_snapshot": ranking_snapshot,
    }
