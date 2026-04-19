"""Claude-powered chatbot for humanitarian crisis analysis."""
from __future__ import annotations

import json
import logging
import math
from typing import Any

import anthropic
import pandas as pd
from pathlib import Path

from api.hdx_client import HDXClient, HDXClientError
from api.scorer import aggregate_by_country_cluster, compute_scores, iso3_to_name

logger = logging.getLogger(__name__)

# ── Static system prompt ──────────────────────────────────────────────────────
# Cached at the Anthropic level — changes here invalidate the cache.

_SCORER_PATH = Path(__file__).parent / "scorer.py"
_SCORER_CODE = ""
if _SCORER_PATH.exists():
    _SCORER_CODE = _SCORER_PATH.read_text(encoding="utf-8")

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

### Structural neglect signals (bonus layer — multi-year FTS history 2019-2025)
These signals distinguish *chronic* underfunding from *acute* gaps using 6 years of FTS cluster
funding data. They are precomputed and joined to every (country, cluster) row.

| Field | Definition |
|---|---|
| consecutive_years_underfunded | Current streak of years with coverage < 50 % (most recent first) |
| structural_neglect_score | 0–1: 0.6 × (consecutive/5) + 0.4 × (fraction of window underfunded) |
| coverage_trend | Linear slope of annual coverage over the window (negative = worsening) |
| neglect_type | Label: 'structural' \| 'worsening' \| 'acute' \| 'improving' \| 'adequate' |
| n_years_data | Number of years with FTS data available in the window |

**neglect_type rules:**
- `structural`: consecutive ≥ 3 years AND ≥ 60 % of window underfunded → *systemic failure*
- `worsening`: coverage_trend < −0.03 AND currently underfunded → *deteriorating fast*
- `acute`: currently underfunded but not yet structural → *new or one-off gap*
- `improving`: coverage_trend > +0.03 AND fewer than 2 consecutive recent underfunded years
- `adequate`: coverage ≥ 50 % and not worsening

**Why this matters:** A crisis labelled `structural` has failed to attract adequate funding for
3+ consecutive years — the gap is systemic, not situational, and unlikely to self-correct.
An `acute` crisis may respond to targeted advocacy. A `worsening` crisis is on the structural
path and requires urgent attention. Use these to go beyond today's snapshot and ask:
*"Is this crisis chronically overlooked or newly overlooked?"*

**How to use in queries:** Filter `neglect_type=['structural']` to find the most entrenched cases.
Sort by `structural_neglect_score` to surface chronic neglect alongside point-in-time rankings.

### Data sources
- FTS (OCHA Financial Tracking Service): funding and requirements per country/cluster/year (2000-2025)
- HPC (Humanitarian Programme Cycle): people in need per sector
- IPC (Integrated Food Security Phase Classification): food insecurity severity by phase
- ACLED: number of events targeting civilians per country/year

### Available data
HNO years: 2024, 2025 (use last_years=1 for latest year only, last_years=2 for both)
Structural signals: up to 6 years of FTS history (2019–2025)
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
    "2. **Explore the data**: Help users filter by country, sector, or recency (last_years) and adjust "
    "scoring weights to reflect their priorities.\n"
    "3. **Compare crises**: Compare across dimensions — need vs funding vs food insecurity "
    "vs conflict.\n"
    "4. **Change the view**: When users want to focus on something different, call "
    "`update_ranking_parameters` to update the frontend visualisation.\n\n"
    "5. **Use live HDX data**: When users ask about specific countries, call the appropriate "
    "HDX live-data tools to supplement the pre-computed CSV rankings:\n"
    "   - People in need / sector breakdowns → `hdx_get_humanitarian_needs`\n"
    "   - Refugees, IDPs, displaced people → `hdx_get_affected_populations`\n"
    "   - Food insecurity / IPC phases → `hdx_get_food_security`\n"
    "   - Armed conflict / ACLED events → `hdx_get_conflict_events`\n"
    "   - Funding flows / FTS data → `hdx_get_funding`\n"
    "   - Active organizations / response coverage → `hdx_get_operational_presence`\n"
    "   - Location/dataset metadata → `hdx_search_locations`, `hdx_get_dataset_info`\n\n"
    "## Behavioural rules\n"
    "- Always be specific: cite actual neglect_index values, coverage percentages, "
    "people in need counts.\n"
    "- Before explaining a ranking, call `query_ranking` to get fresh data with "
    "the exact numbers.\n"
    "- When you adjust weights (e.g. 'prioritise food insecurity'), explain what the "
    "weight change means mathematically.\n"
    "- If a user asks 'why is X ranked high', query X's data first, then explain "
    "each contributing metric.\n"
    "- Keep responses concise and decision-focused — this is a triage tool.\n"
    "- When you use data from any HDX tool, always end your response with a brief "
    "'**Sources:**' line that names the specific datasets used "
    "(e.g. 'HDX HAPI — Refugees & Persons of Concern', 'HDX HAPI — FTS Funding'). "
    "For pre-computed CSV data cite 'FTS / HPC / IPC / ACLED via Neglect Index dataset'.\n\n"
    "## Writing style — CRITICAL\n"
    "Write for a human reader, not a data analyst. Your reply is a conversation, not a report.\n\n"
    "**Narrative over tables**: Weave numbers into prose. "
    "Write 'Syria has 15 million people in need of food assistance — less than 0.3% of that is funded' "
    "rather than a markdown table of metrics. Use a table only if you are comparing 3+ countries side-by-side "
    "and the comparison genuinely requires it.\n\n"
    "**No raw data dumps**: Do not list every row from a tool result. Pick 2–4 striking figures "
    "that tell the story and leave the rest. The frontend shows the full data.\n\n"
    "**No monthly chronologies unless asked**: If you fetched time-series data (e.g. ACLED events "
    "by month), synthesise it into a sentence or two — 'violence peaked in early 2018 then fell to "
    "near-zero through 2023 before resurging in late 2024' — rather than listing every data point.\n\n"
    "**No capability menus**: Never end a response with a bullet list of things you *could* do next "
    "('I can pull X, show Y, re-weight Z'). If a follow-up is natural, suggest one thing in one sentence.\n\n"
    "**No technical caveats in the body**: API limits, row caps, and data-availability notes belong in "
    "a short italic footnote at the bottom, not inline warnings that interrupt the narrative.\n\n"
    "**Tool output rules**: The frontend renders structured data from tools separately.\n"
    "- After `update_ranking_parameters`: 1–2 sentences on *why* the change matters analytically — nothing else.\n"
    "- After `query_ranking`: reference 1–3 specific values inline; never reproduce the full result set.\n"
    "- Never output sections titled '### New top 5', '### What changed', '### Parameters updated'.\n\n"
    + _METHODOLOGY +
    "\n\n## Scorer Implementation (`scorer.py`)\n"
    "Below is the exact Python code used to calculate the indices. Reference this if the user "
    "asks highly technical questions about NumPy normalizations, bootstrapping, or NaN handling:\n\n"
    "```python\n"
    f"{_SCORER_CODE}\n"
    "```\n"
)

# ── Tool definitions ──────────────────────────────────────────────────────────

_FILTER_PROPS: dict[str, Any] = {
    "last_years": {
        "type": "integer",
        "description": "Include only the N most recent years of data (e.g. 1 = latest year only, 2 = last two years). Omit for all years.",
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
    "neglect_type": {
        "type": "array", "items": {"type": "string"},
        "description": (
            "Filter by structural neglect classification. "
            "Values: 'structural' (≥3 consecutive underfunded years), "
            "'worsening' (coverage trend strongly negative), "
            "'acute' (currently underfunded but not chronic), "
            "'improving' (coverage recovering), 'adequate' (≥50% funded). "
            "Use ['structural'] to surface the most entrenched crises."
        ),
    },
    "min_consecutive_years": {
        "type": "integer",
        "description": "Only include crises underfunded for at least this many consecutive years. E.g. 3 = structural neglect threshold.",
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
        "description": (
            "Column to sort by. Default: 'neglect_index'. "
            "Also available: 'structural_neglect_score' (sort by chronic underfunding), "
            "'consecutive_years_underfunded', 'coverage_trend' (most worsening first when desc)."
        ),
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
            "Call this when the user asks to: focus on specific countries/clusters, restrict to recent years (last_years), "
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
    {
        "name": "hdx_search_locations",
        "description": (
            "Search HDX locations metadata. Use when users ask for available "
            "countries/locations or to find locations matching a name pattern."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name_pattern": {
                    "type": "string",
                    "description": "Optional substring pattern for location names.",
                },
                "has_hrp": {
                    "type": "boolean",
                    "description": "Optional filter for locations with HRP coverage.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum locations to return (default 25).",
                },
            },
        },
    },
    {
        "name": "hdx_get_dataset_info",
        "description": (
            "Get details for a specific HDX dataset by its dataset_hdx_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_hdx_id": {
                    "type": "string",
                    "description": "HDX dataset identifier.",
                },
            },
            "required": ["dataset_hdx_id"],
        },
    },
    {
        "name": "hdx_get_humanitarian_needs",
        "description": (
            "Fetch live people-in-need figures from HDX HAPI by country and cluster. "
            "Use when the user asks for current humanitarian needs data beyond what the "
            "pre-computed CSV ranking already shows."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location_code": {
                    "type": "string",
                    "description": "ISO-3 country code, e.g. 'AFG', 'SYR', 'SDN'.",
                },
                "year": {"type": "integer", "description": "4-digit year, e.g. 2024."},
                "cluster_code": {
                    "type": "string",
                    "description": "Cluster/sector code to filter results.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max records to return (default 100).",
                },
            },
        },
    },
    {
        "name": "hdx_get_affected_populations",
        "description": (
            "Fetch live refugee, IDP, and displaced population counts from HDX HAPI. "
            "Use when the user asks about forced displacement, refugee numbers, or IDPs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location_code": {
                    "type": "string",
                    "description": "ISO-3 country code.",
                },
                "year": {"type": "integer", "description": "4-digit year."},
                "population_group_code": {
                    "type": "string",
                    "description": (
                        "Population group: 'REF' (refugees), 'IDP' (internally displaced), "
                        "'STA' (stateless), 'OOC' (others of concern). Omit for all groups."
                    ),
                },
                "limit": {"type": "integer", "description": "Max records to return."},
            },
        },
    },
    {
        "name": "hdx_get_food_security",
        "description": (
            "Fetch live IPC food security phase data from HDX HAPI. "
            "Use when the user asks about food insecurity severity, famine risk, or IPC phases."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location_code": {
                    "type": "string",
                    "description": "ISO-3 country code.",
                },
                "year": {"type": "integer", "description": "4-digit year."},
                "ipc_phase": {
                    "type": "integer",
                    "description": "Filter by IPC phase: 1=Minimal, 2=Stressed, 3=Crisis, 4=Emergency, 5=Famine.",
                },
                "limit": {"type": "integer", "description": "Max records to return."},
            },
        },
    },
    {
        "name": "hdx_get_conflict_events",
        "description": (
            "Fetch live ACLED conflict event counts from HDX HAPI. "
            "Use when the user asks about violence, armed conflict, or security situations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location_code": {
                    "type": "string",
                    "description": "ISO-3 country code.",
                },
                "year": {"type": "integer", "description": "4-digit year."},
                "event_type": {
                    "type": "string",
                    "description": "Type of conflict event to filter by (e.g. 'battles', 'explosions').",
                },
                "limit": {"type": "integer", "description": "Max records to return."},
            },
        },
    },
    {
        "name": "hdx_get_funding",
        "description": (
            "Fetch live FTS funding flow data from HDX HAPI. "
            "Use when the user asks about aid funding, donor contributions, or financial gaps "
            "beyond what the pre-computed CSV already provides."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location_code": {
                    "type": "string",
                    "description": "ISO-3 country code.",
                },
                "year": {"type": "integer", "description": "4-digit year."},
                "cluster_code": {
                    "type": "string",
                    "description": "Cluster/sector code to filter by.",
                },
                "limit": {"type": "integer", "description": "Max records to return."},
            },
        },
    },
    {
        "name": "hdx_get_operational_presence",
        "description": (
            "Fetch live organizational presence data from HDX HAPI. "
            "Use when the user asks which NGOs or UN agencies are active in a country, "
            "or wants to know response coverage by cluster."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location_code": {
                    "type": "string",
                    "description": "ISO-3 country code.",
                },
                "year": {"type": "integer", "description": "4-digit year."},
                "cluster_code": {
                    "type": "string",
                    "description": "Cluster/sector code to filter by.",
                },
                "org_acronym": {
                    "type": "string",
                    "description": "Filter by organization acronym, e.g. 'UNHCR', 'WFP'.",
                },
                "limit": {"type": "integer", "description": "Max records to return."},
            },
        },
    },
]

# ── Default parameters ────────────────────────────────────────────────────────

DEFAULT_PARAMS: dict[str, Any] = {
    "last_years": None,
    "cluster": None,
    "country": None,
    "min_people_in_need": None,
    "max_coverage": None,
    "min_neglect_index": None,
    "neglect_type": None,
    "min_consecutive_years": None,
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


def _priority_label(score: float, critical: float = 0.8, high: float = 0.6) -> str:
    if score >= critical:
        return "critical"
    if score >= high:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _apply_filters(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    if params.get("last_years") is not None:
        max_year = int(df["year"].max())
        df = df[df["year"] >= max_year - params["last_years"] + 1]
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

    df = aggregate_by_country_cluster(df)

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
    if params.get("neglect_type") and "neglect_type" in df.columns:
        df = df[df["neglect_type"].isin(params["neglect_type"])]
    if params.get("min_consecutive_years") is not None and "consecutive_years_underfunded" in df.columns:
        df = df[df["consecutive_years_underfunded"] >= params["min_consecutive_years"]]

    sort_by = params.get("sort_by", "neglect_index")
    sort_desc = params.get("sort_desc", True)
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=not sort_desc, na_position="last")

    def _opt_str(v: Any) -> str | None:
        if v is None:
            return None
        try:
            if isinstance(v, float) and math.isnan(v):
                return None
        except TypeError:
            pass
        return str(v)

    limit = params.get("limit", None)
    rows = []
    for _, row in (df.head(limit) if limit is not None else df).iterrows():
        rows.append({
            "countryCode": row["countryCode"],
            "countryName": iso3_to_name(row["countryCode"]),
            "cluster": row["cluster"],
            "people_in_need": float(row["People_In_Need"]),
            "country_total_pin": _opt(row.get("country_total_pin")),
            "requirements_usd": _opt(row.get("requirements_cluster_specific")),
            "funding_usd": _opt(row.get("funding_cluster_specific")),
            "coverage": round(float(row["coverage"]), 4),
            "neglect_index": round(float(row["neglect_index"]), 4),
            "need_rank": round(float(row["need_rank"]), 4),
            "coverage_rank": round(float(row["coverage_rank"]), 4),
            "ipc_severity_score": _opt(row.get("ipc_severity_score")),
            "priority_label": _priority_label(float(row["neglect_index"])),
            # Structural neglect signals
            "consecutive_years_underfunded": _opt(row.get("consecutive_years_underfunded")),
            "structural_neglect_score": _opt(row.get("structural_neglect_score")),
            "coverage_trend": _opt(row.get("coverage_trend")),
            "neglect_type": _opt_str(row.get("neglect_type")),
        })
    return rows


# ── Main chat function ────────────────────────────────────────────────────────

_client = anthropic.Anthropic()


def chat(
    messages: list[dict[str, str]],
    current_params: dict[str, Any],
    df_base: pd.DataFrame,
    hdx_client: HDXClient | None = None,
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

        tool_names = [
            b.name for b in response.content
            if getattr(b, "type", None) == "tool_use"
        ]
        logger.info(
            "Claude response: stop_reason=%s tool_names=%s",
            response.stop_reason,
            tool_names,
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


                elif block.name == "hdx_search_locations":
                    logger.info("Entered branch: hdx_search_locations")
                    if hdx_client is None:
                        content = {
                            "status": "error",
                            "message": "HDX integration is not configured. Set HDX_APP_IDENTIFIER.",
                        }
                    else:
                        try:
                            name_pattern = block.input.get("name_pattern")
                            has_hrp = block.input.get("has_hrp")
                            limit = int(block.input.get("limit", 25))
                            logger.warning(
                                "Chat tool hdx_search_locations called: name_pattern=%s has_hrp=%s limit=%s",
                                name_pattern,
                                has_hrp,
                                limit,
                            )

                            content = hdx_client.search_locations(
                                name_pattern=name_pattern,
                                has_hrp=has_hrp,
                                limit=limit,
                            )

                            logger.info(
                                "Chat tool hdx_search_locations succeeded: count=%s",
                                content.get("count") if isinstance(content, dict) else None,
                            )
                        except (HDXClientError, ValueError) as exc:
                            logger.exception("Chat tool hdx_search_locations failed")
                            content = {"status": "error", "message": str(exc)}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(content, default=str),
                    })

                elif block.name == "hdx_get_dataset_info":
                    if hdx_client is None:
                        content = {
                            "status": "error",
                            "message": "HDX integration is not configured. Set HDX_APP_IDENTIFIER.",
                        }
                    else:
                        try:
                            content = hdx_client.get_dataset_info(
                                dataset_hdx_id=str(block.input.get("dataset_hdx_id", ""))
                            )
                        except HDXClientError as exc:
                            content = {"status": "error", "message": str(exc)}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(content, default=str),
                    })

                elif block.name in {
                    "hdx_get_humanitarian_needs",
                    "hdx_get_affected_populations",
                    "hdx_get_food_security",
                    "hdx_get_conflict_events",
                    "hdx_get_funding",
                    "hdx_get_operational_presence",
                }:
                    if hdx_client is None:
                        content = {
                            "status": "error",
                            "message": "HDX integration is not configured. Set HDX_APP_IDENTIFIER.",
                        }
                    else:
                        try:
                            inp = block.input
                            loc = inp.get("location_code")
                            year_v = inp.get("year")
                            limit_v = int(inp.get("limit", 100))

                            if block.name == "hdx_get_humanitarian_needs":
                                content = hdx_client.get_humanitarian_needs(
                                    location_code=loc,
                                    year=year_v,
                                    cluster_code=inp.get("cluster_code"),
                                    limit=limit_v,
                                )
                            elif block.name == "hdx_get_affected_populations":
                                content = hdx_client.get_affected_populations(
                                    location_code=loc,
                                    year=year_v,
                                    population_group_code=inp.get("population_group_code"),
                                    limit=limit_v,
                                )
                            elif block.name == "hdx_get_food_security":
                                content = hdx_client.get_food_security(
                                    location_code=loc,
                                    year=year_v,
                                    ipc_phase=inp.get("ipc_phase"),
                                    limit=limit_v,
                                )
                            elif block.name == "hdx_get_conflict_events":
                                content = hdx_client.get_conflict_events(
                                    location_code=loc,
                                    year=year_v,
                                    event_type=inp.get("event_type"),
                                    limit=limit_v,
                                )
                            elif block.name == "hdx_get_funding":
                                content = hdx_client.get_funding(
                                    location_code=loc,
                                    year=year_v,
                                    cluster_code=inp.get("cluster_code"),
                                    limit=limit_v,
                                )
                            else:  # hdx_get_operational_presence
                                content = hdx_client.get_operational_presence(
                                    location_code=loc,
                                    year=year_v,
                                    cluster_code=inp.get("cluster_code"),
                                    org_acronym=inp.get("org_acronym"),
                                    limit=limit_v,
                                )
                        except HDXClientError as exc:
                            logger.exception("Chat tool %s failed", block.name)
                            content = {"status": "error", "message": str(exc)}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(content, default=str),
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
