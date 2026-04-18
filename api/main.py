"""FastAPI backend for humanitarian crisis neglect analysis."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated, Any, Optional

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

from api.chatbot import DEFAULT_PARAMS
from api.chatbot import chat as chatbot_chat
from api.scorer import compute_scores, create_aggregate_base, iso3_to_name

_df_base: pd.DataFrame | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _df_base
    print("Loading base data …")
    _df_base = create_aggregate_base()
    print(f"Loaded {len(_df_base):,} rows.")
    yield


app = FastAPI(
    title="Humanitarian Crisis Neglect API",
    description="Rank humanitarian crises by neglect index — severity vs funding coverage.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Response models ───────────────────────────────────────────────────────────

class CrisisRow(BaseModel):
    countryCode: str
    countryName: str
    year: int
    cluster: str
    people_in_need: float
    requirements_usd: Optional[float]
    funding_usd: Optional[float]
    coverage: float
    neglect_index: float
    need_rank: float
    coverage_rank: float
    ipc_severity_score: Optional[float]
    uncertainty: Optional[float]
    priority_label: str  # "critical" | "high" | "medium" | "low"

    model_config = {"from_attributes": True}


class RankingResponse(BaseModel):
    total_matches: int
    returned: int
    offset: int
    results: list[CrisisRow]


class MetadataResponse(BaseModel):
    countries: list[dict]
    clusters: list[str]
    years: list[int]


# ── Helpers ───────────────────────────────────────────────────────────────────

_VALID_SORT_FIELDS = {
    "neglect_index", "need_rank", "coverage_rank", "coverage",
    "people_in_need", "ipc_severity_score", "uncertainty",
    "countryCode", "cluster", "year",
}


def _priority_label(score: float, critical: float, high: float) -> str:
    if score >= critical:
        return "critical"
    if score >= high:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _row_to_model(row: pd.Series, critical: float, high: float) -> CrisisRow:
    def _opt(v):
        return None if pd.isna(v) else float(v)

    return CrisisRow(
        countryCode=row['countryCode'],
        countryName=iso3_to_name(row['countryCode']),
        year=int(row['year']),
        cluster=row['cluster'],
        people_in_need=float(row['People_In_Need']),
        requirements_usd=_opt(row.get('requirements_cluster_specific')),
        funding_usd=_opt(row.get('funding_cluster_specific')),
        coverage=float(row['coverage']),
        neglect_index=float(row['neglect_index']),
        need_rank=float(row['need_rank']),
        coverage_rank=float(row['coverage_rank']),
        ipc_severity_score=_opt(row.get('ipc_severity_score')),
        uncertainty=_opt(row.get('uncertainty')),
        priority_label=_priority_label(row['neglect_index'], critical, high),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/metadata", response_model=MetadataResponse, summary="Available filter values")
def get_metadata():
    """Return all valid country codes, cluster names, and years in the dataset."""
    df = _df_base
    countries = sorted(
        [{"code": c, "name": iso3_to_name(c)} for c in df['countryCode'].unique()],
        key=lambda x: x["name"],
    )
    clusters = sorted(df['cluster'].unique().tolist())
    years = sorted(int(y) for y in df['year'].unique())
    return MetadataResponse(countries=countries, clusters=clusters, years=years)


@app.get("/ranking", response_model=RankingResponse, summary="Ranked neglect index")
def get_ranking(
    # ── Filters ───────────────────────────────────────────────────────────────
    year: Annotated[
        Optional[list[int]], Query(description="Filter by year(s), e.g. year=2024&year=2025")
    ] = None,
    cluster: Annotated[
        Optional[list[str]], Query(description="Filter by humanitarian cluster name(s)")
    ] = None,
    country: Annotated[
        Optional[list[str]], Query(description="Filter by ISO-3 country code(s), e.g. AFG&country=SYR")
    ] = None,
    min_people_in_need: Annotated[
        Optional[int], Query(ge=0, description="Exclude rows with fewer people in need")
    ] = None,
    max_coverage: Annotated[
        Optional[float], Query(ge=0, le=1, description="Exclude rows where funding coverage exceeds this (remove well-funded crises)")
    ] = None,
    min_neglect_index: Annotated[
        Optional[float], Query(ge=0, le=1, description="Only return rows at or above this neglect index threshold")
    ] = None,
    # ── Scoring weights ───────────────────────────────────────────────────────
    severity_weight: Annotated[
        float, Query(ge=0, le=1, description="Weight of severity in the neglect index (auto-normalised with funding_gap_weight)")
    ] = 0.6,
    funding_gap_weight: Annotated[
        float, Query(ge=0, le=1, description="Weight of funding gap in the neglect index (auto-normalised with severity_weight)")
    ] = 0.4,
    need_weight: Annotated[
        float, Query(ge=0, le=1, description="Weight of people-in-need percentile within the severity component")
    ] = 0.5,
    ipc_weight: Annotated[
        float, Query(ge=0, le=1, description="Weight of IPC food-insecurity severity within the severity component (Food Security cluster only)")
    ] = 0.4,
    events_weight: Annotated[
        float, Query(ge=0, le=1, description="Weight of civilian conflict events within the severity component")
    ] = 0.1,
    # ── Threshold labels ──────────────────────────────────────────────────────
    critical_threshold: Annotated[
        float, Query(ge=0, le=1, description="Neglect index at or above which a crisis is labelled 'critical'")
    ] = 0.8,
    high_threshold: Annotated[
        float, Query(ge=0, le=1, description="Neglect index at or above which a crisis is labelled 'high'")
    ] = 0.6,
    # ── Pagination / sorting ──────────────────────────────────────────────────
    sort_by: Annotated[
        str, Query(description=f"Column to sort by. Valid: {', '.join(sorted(_VALID_SORT_FIELDS))}")
    ] = "neglect_index",
    sort_desc: Annotated[bool, Query(description="Sort descending")] = True,
    limit: Annotated[int, Query(ge=1, le=5000, description="Max rows to return")] = 25,
    offset: Annotated[int, Query(ge=0, description="Rows to skip (for pagination)")] = 0,
    # ── Bootstrap ─────────────────────────────────────────────────────────────
    n_bootstrap: Annotated[
        int, Query(ge=0, le=500, description="Bootstrap iterations for uncertainty. 0 = skip (faster)")
    ] = 50,
):
    if sort_by not in _VALID_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"sort_by must be one of: {', '.join(sorted(_VALID_SORT_FIELDS))}",
        )
    if critical_threshold <= high_threshold:
        raise HTTPException(
            status_code=422, detail="critical_threshold must be greater than high_threshold"
        )

    df = _df_base.copy()

    # Apply filters
    if year:
        df = df[df['year'].isin(year)]
    if cluster:
        df = df[df['cluster'].isin(cluster)]
    if country:
        df = df[df['countryCode'].isin(country)]
    if min_people_in_need is not None:
        df = df[df['People_In_Need'] >= min_people_in_need]

    if df.empty:
        return RankingResponse(total_matches=0, returned=0, offset=offset, results=[])

    # Score with requested weights
    df = compute_scores(
        df,
        severity_weight=severity_weight,
        funding_gap_weight=funding_gap_weight,
        need_weight=need_weight,
        ipc_weight=ipc_weight,
        events_weight=events_weight,
        n_bootstrap=n_bootstrap,
    )

    # Post-score filters (need computed columns)
    if max_coverage is not None:
        df = df[df['coverage'] <= max_coverage]
    if min_neglect_index is not None:
        df = df[df['neglect_index'] >= min_neglect_index]

    total = len(df)

    # Sort
    ascending = not sort_desc
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=ascending, na_position='last')

    # Paginate
    page = df.iloc[offset: offset + limit]

    results = [_row_to_model(row, critical_threshold, high_threshold) for _, row in page.iterrows()]
    return RankingResponse(total_matches=total, returned=len(results), offset=offset, results=results)


@app.get(
    "/crisis/{country_code}/{year}/{cluster}",
    response_model=CrisisRow,
    summary="Single crisis details",
)
def get_crisis(
    country_code: str,
    year: int,
    cluster: str,
    severity_weight: float = Query(0.6, ge=0, le=1),
    funding_gap_weight: float = Query(0.4, ge=0, le=1),
    need_weight: float = Query(0.5, ge=0, le=1),
    ipc_weight: float = Query(0.4, ge=0, le=1),
    events_weight: float = Query(0.1, ge=0, le=1),
    critical_threshold: float = Query(0.8, ge=0, le=1),
    high_threshold: float = Query(0.6, ge=0, le=1),
    n_bootstrap: int = Query(50, ge=0, le=500),
):
    """Return scored details for one country/year/cluster combination.

    Scores are computed in the context of all data (ranks are global within cluster).
    """
    df = _df_base
    if country_code not in df['countryCode'].values:
        raise HTTPException(status_code=404, detail=f"Country '{country_code}' not found")

    scored = compute_scores(
        df,
        severity_weight=severity_weight,
        funding_gap_weight=funding_gap_weight,
        need_weight=need_weight,
        ipc_weight=ipc_weight,
        events_weight=events_weight,
        n_bootstrap=n_bootstrap,
    )
    row = scored[
        (scored['countryCode'] == country_code)
        & (scored['year'] == year)
        & (scored['cluster'] == cluster)
    ]
    if row.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No entry for {country_code}/{year}/{cluster}",
        )
    return _row_to_model(row.iloc[0], critical_threshold, high_threshold)


# ── Chat endpoint ─────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Chat turn request.

    messages: full conversation history (alternating user/assistant).
    current_params: the ranking parameters currently active in the frontend.
      Only non-None values override the defaults. Omit keys you haven't changed.
    """
    messages: list[ChatMessage]
    current_params: dict[str, Any] = {}


class ChatResponse(BaseModel):
    """Chat turn response.

    reply: the assistant's text response to display in the chat UI.
    parameter_update: present when Claude changed the ranking parameters.
      Apply these to the frontend's ranking view — this is the complete merged
      parameter dict (not a diff), ready to pass directly to GET /ranking.
    ranking_snapshot: the top results computed with the updated parameters.
      Use this to immediately refresh the visualisation without a second request.
    """
    reply: str
    parameter_update: Optional[dict[str, Any]] = None
    ranking_snapshot: Optional[list[dict[str, Any]]] = None


@app.post("/chat", response_model=ChatResponse, summary="Chat with the crisis analyst")
def post_chat(request: ChatRequest):
    """Send a message to the Claude-powered analyst.

    Claude can:
    - Explain why countries/clusters rank high, citing exact metric values
    - Compare crises across dimensions (need, funding, food insecurity, conflict)
    - Change the ranking parameters shown in the frontend visualisation
    - Adjust scoring weights to reflect different humanitarian priorities

    When Claude changes parameters, `parameter_update` contains the full merged
    parameter dict. Pass it to `GET /ranking` (or apply directly to the frontend
    state) to update the visualisation. `ranking_snapshot` gives you the
    pre-computed top results so you don't need a second request.
    """
    if not request.messages:
        raise HTTPException(status_code=422, detail="messages must not be empty")
    if request.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="Last message must be from 'user'")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not set. Add it to .env or the environment.",
        )

    api_messages = [{"role": m.role, "content": m.content} for m in request.messages]
    try:
        result = chatbot_chat(api_messages, request.current_params, _df_base)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}") from exc
    return ChatResponse(**result)


@app.get("/chat/defaults", summary="Default ranking parameters")
def get_chat_defaults() -> dict[str, Any]:
    """Return the default ranking parameter values used when none are supplied."""
    return DEFAULT_PARAMS
