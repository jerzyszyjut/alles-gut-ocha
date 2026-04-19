"""FastAPI backend for humanitarian crisis neglect analysis."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated, Any, Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler

load_dotenv()

from api.chatbot import DEFAULT_PARAMS
from api.chatbot import chat as chatbot_chat
from api.hdx_client import HDXClient, HDXClientError, create_hdx_client_from_env
from api.scorer import aggregate_by_country_cluster, compute_scores, create_aggregate_base, iso3_to_name

_df_base: pd.DataFrame | None = None
_hdx_client: HDXClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _df_base, _hdx_client
    print("Loading base data …")
    _df_base = create_aggregate_base()
    print(f"Loaded {len(_df_base):,} rows.")
    _hdx_client = create_hdx_client_from_env()
    if _hdx_client is None:
        print("HDX integration disabled (HDX_APP_IDENTIFIER not set).")
    else:
        print("HDX integration enabled.")
    try:
        yield
    finally:
        if _hdx_client is not None:
            _hdx_client.close()


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
    cluster: str
    people_in_need: float
    country_total_pin: Optional[float]  # deduplicated ALL-cluster country total from HNO data
    requirements_usd: Optional[float]
    funding_usd: Optional[float]
    coverage: float
    neglect_index: float
    rank: Optional[int]
    rank_ci_low: Optional[int]
    rank_ci_high: Optional[int]
    need_rank: float
    coverage_rank: float
    ipc_severity_score: Optional[float]
    uncertainty: Optional[float]
    severity_case: Optional[str]  # 'A' | 'B' | 'C' | 'D'
    priority_label: str  # "critical" | "high" | "medium" | "low"
    # ── Structural neglect signals (from multi-year FTS history) ───────────────
    consecutive_years_underfunded: Optional[int]
    structural_neglect_score: Optional[float]  # 0-1, higher = more chronic neglect
    coverage_trend: Optional[float]  # linear slope per year (negative = worsening)
    neglect_type: Optional[str]  # 'structural' | 'worsening' | 'acute' | 'improving' | 'adequate'
    n_years_data: Optional[int]  # years of FTS history used for structural signal

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
    "structural_neglect_score", "consecutive_years_underfunded", "coverage_trend",
    "countryCode", "cluster",
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

    def _opt_int(v):
        try:
            return None if pd.isna(v) else int(v)
        except (TypeError, ValueError):
            return None

    def _opt_str(v: Any) -> str | None:
        return None if (v is None or (isinstance(v, float) and np.isnan(v))) else str(v)

    return CrisisRow(
        countryCode=row['countryCode'],
        countryName=iso3_to_name(row['countryCode']),
        cluster=row['cluster'],
        people_in_need=float(row['People_In_Need']),
        country_total_pin=_opt(row.get('country_total_pin')),
        requirements_usd=_opt(row.get('requirements_cluster_specific')),
        funding_usd=_opt(row.get('funding_cluster_specific')),
        coverage=float(row['coverage']),
        neglect_index=float(row['neglect_index']),
        rank=_opt_int(row.get('rank')),
        rank_ci_low=_opt_int(row.get('rank_ci_low')),
        rank_ci_high=_opt_int(row.get('rank_ci_high')),
        need_rank=float(row['need_rank']),
        coverage_rank=float(row['coverage_rank']),
        ipc_severity_score=_opt(row.get('ipc_severity_score')),
        uncertainty=_opt(row.get('uncertainty')),
        severity_case=_opt_str(row.get('severity_case')),
        priority_label=_priority_label(row['neglect_index'], critical, high),
        consecutive_years_underfunded=_opt_int(row.get('consecutive_years_underfunded')),
        structural_neglect_score=_opt(row.get('structural_neglect_score')),
        coverage_trend=_opt(row.get('coverage_trend')),
        neglect_type=_opt_str(row.get('neglect_type')),
        n_years_data=_opt_int(row.get('n_years_data')),
    )


def _require_hdx_client() -> HDXClient:
    if _hdx_client is None:
        raise HTTPException(
            status_code=503,
            detail="HDX integration not configured. Set HDX_APP_IDENTIFIER and restart API.",
        )
    return _hdx_client


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
    last_years: Annotated[
        Optional[int], Query(ge=1, description="Include only the N most recent years of data (e.g. 1 = latest year only)")
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
    neglect_type: Annotated[
        Optional[list[str]], Query(description="Filter by neglect type(s): structural, worsening, acute, improving, adequate")
    ] = None,
    min_consecutive_years: Annotated[
        Optional[int], Query(ge=0, description="Only include crises underfunded for at least this many consecutive years")
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
    limit: Annotated[int | None, Query(ge=1, description="Max rows to return (omit for all)")] = None,
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
    if last_years is not None:
        max_year = int(df['year'].max())
        df = df[df['year'] >= max_year - last_years + 1]
    if cluster:
        df = df[df['cluster'].isin(cluster)]
    if country:
        df = df[df['countryCode'].isin(country)]

    # Aggregate across years into one row per (country, cluster)
    df = aggregate_by_country_cluster(df)

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
    if neglect_type and 'neglect_type' in df.columns:
        df = df[df['neglect_type'].isin(neglect_type)]
    if min_consecutive_years is not None and 'consecutive_years_underfunded' in df.columns:
        df = df[df['consecutive_years_underfunded'] >= min_consecutive_years]

    total = len(df)

    # Sort
    ascending = not sort_desc
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=ascending, na_position='last')
    df = df.reset_index(drop=True)

    # Assign rank by neglect_index (rank 1 = most neglected) across full result set
    df['rank'] = df['neglect_index'].rank(ascending=False, method='min').astype(int)

    # Paginate
    page = df.iloc[offset:] if limit is None else df.iloc[offset: offset + limit]

    results = [_row_to_model(row, critical_threshold, high_threshold) for _, row in page.iterrows()]
    return RankingResponse(total_matches=total, returned=len(results), offset=offset, results=results)


@app.get("/tsne", summary="t-SNE projection of crisis data with outlier flags")
def get_tsne(
    last_years: Annotated[Optional[int], Query(ge=1)] = None,
    cluster: Annotated[Optional[list[str]], Query()] = None,
    country: Annotated[Optional[list[str]], Query()] = None,
    severity_weight: float = Query(0.6, ge=0, le=1),
    funding_gap_weight: float = Query(0.4, ge=0, le=1),
    need_weight: float = Query(0.5, ge=0, le=1),
    ipc_weight: float = Query(0.4, ge=0, le=1),
    events_weight: float = Query(0.1, ge=0, le=1),
    perplexity: int = Query(30, ge=5, le=100),
):
    df = _df_base.copy()

    if last_years is not None:
        max_year = int(df['year'].max())
        df = df[df['year'] >= max_year - last_years + 1]
    if cluster:
        df = df[df['cluster'].isin(cluster)]
    if country:
        df = df[df['countryCode'].isin(country)]

    df = aggregate_by_country_cluster(df)

    if len(df) < 5:
        return []

    df = compute_scores(
        df,
        severity_weight=severity_weight,
        funding_gap_weight=funding_gap_weight,
        need_weight=need_weight,
        ipc_weight=ipc_weight,
        events_weight=events_weight,
        n_bootstrap=0,
    )

    feature_cols = ['neglect_index', 'coverage', 'need_rank', 'coverage_rank']
    if 'ipc_severity_score' in df.columns:
        feature_cols.append('ipc_severity_score')
    if 'structural_neglect_score' in df.columns:
        feature_cols.append('structural_neglect_score')

    X = df[feature_cols].fillna(df[feature_cols].mean())
    X_scaled = StandardScaler().fit_transform(X)

    perp = min(perplexity, len(df) - 1)
    coords = TSNE(n_components=2, perplexity=perp, random_state=42, max_iter=1000).fit_transform(X_scaled)

    df = df.copy()
    df['_x'] = coords[:, 0]
    df['_y'] = coords[:, 1]

    # KMeans on t-SNE coordinates to find support clusters
    n_clusters = max(2, min(6, len(df) // 5))
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df['kmeans_cluster'] = km.fit_predict(coords)

    # Outlier = distance to own KMeans centroid > mean + 1.5 * std (within each cluster)
    df['is_outlier'] = False
    for cid, grp in df.groupby('kmeans_cluster'):
        if len(grp) < 2:
            continue
        pts = coords[grp.index]
        centroid = km.cluster_centers_[cid]
        dists = np.linalg.norm(pts - centroid, axis=1)
        threshold = dists.mean() + 1.5 * dists.std()
        df.loc[grp.index[dists > threshold], 'is_outlier'] = True

    def _tsne_opt(v: Any) -> float | None:
        try:
            f = float(v)
            return None if np.isnan(f) else round(f, 4)
        except (TypeError, ValueError):
            return None

    return [
        {
            'countryCode': row['countryCode'],
            'countryName': iso3_to_name(row['countryCode']),
            'cluster': row['cluster'],
            'kmeans_cluster': int(row['kmeans_cluster']),
            'x': round(float(row['_x']), 3),
            'y': round(float(row['_y']), 3),
            'neglect_index': round(float(row['neglect_index']), 4),
            'coverage': round(float(row['coverage']), 4),
            'people_in_need': float(row['People_In_Need']),
            'is_outlier': bool(row['is_outlier']),
            'neglect_type': str(row['neglect_type']) if pd.notna(row.get('neglect_type')) else None,
            'structural_neglect_score': _tsne_opt(row.get('structural_neglect_score')),
            'consecutive_years_underfunded': int(row['consecutive_years_underfunded']) if pd.notna(row.get('consecutive_years_underfunded')) else None,
        }
        for _, row in df.iterrows()
    ]


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


@app.get("/hdx/server-info", summary="HDX client configuration status")
def get_hdx_server_info() -> dict[str, Any]:
    client = _require_hdx_client()
    return {
        "server_name": "HDX API Client",
        "base_url": client.base_url,
        "rate_limit_requests": client.rate_limit_requests,
        "rate_limit_period_seconds": client.rate_limit_period,
        "status": "enabled",
    }


@app.get("/hdx/version", summary="HDX API version")
def get_hdx_version() -> dict[str, Any]:
    client = _require_hdx_client()
    try:
        return client.get_version()
    except HDXClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/hdx/locations", summary="Search HDX locations metadata")
def get_hdx_locations(
    name_pattern: str | None = Query(None, description="Optional location name substring"),
    has_hrp: bool | None = Query(None, description="Filter by HRP availability"),
    limit: int = Query(25, ge=1, le=500, description="Max locations to return"),
) -> dict[str, Any]:
    client = _require_hdx_client()
    try:
        return client.search_locations(name_pattern=name_pattern, has_hrp=has_hrp, limit=limit)
    except HDXClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/hdx/dataset/{dataset_hdx_id}", summary="Get HDX dataset metadata")
def get_hdx_dataset(dataset_hdx_id: str) -> dict[str, Any]:
    client = _require_hdx_client()
    try:
        return client.get_dataset_info(dataset_hdx_id)
    except HDXClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
        result = chatbot_chat(api_messages, request.current_params, _df_base, _hdx_client)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}") from exc
    return ChatResponse(**result)


@app.get("/chat/defaults", summary="Default ranking parameters")
def get_chat_defaults() -> dict[str, Any]:
    """Return the default ranking parameter values used when none are supplied."""
    return DEFAULT_PARAMS


# ── Counterfactual endpoint ───────────────────────────────────────────────────

class CounterfactualResponse(BaseModel):
    country_code: str
    country_name: str
    cluster: str
    requirements_usd: Optional[float]
    current_funding_usd: Optional[float]
    additional_funding: float
    current_coverage: float
    new_coverage: float
    current_neglect_index: float
    new_neglect_index: float
    current_rank: int
    new_rank: int
    total_in_cluster: int


@app.get("/counterfactual", response_model=CounterfactualResponse, summary="Counterfactual funding scenario")
def get_counterfactual(
    country_code: str = Query(..., description="ISO-3 country code"),
    cluster: str = Query(..., description="Humanitarian cluster name"),
    additional_funding: float = Query(0, ge=0, description="Hypothetical additional funding in USD"),
    severity_weight: float = Query(0.6, ge=0, le=1),
    funding_gap_weight: float = Query(0.4, ge=0, le=1),
    need_weight: float = Query(0.5, ge=0, le=1),
    ipc_weight: float = Query(0.4, ge=0, le=1),
    events_weight: float = Query(0.1, ge=0, le=1),
):
    """Recompute neglect index and within-cluster rank after hypothetically adding funds."""
    df = aggregate_by_country_cluster(_df_base.copy())

    mask = (df['countryCode'] == country_code) & (df['cluster'] == cluster)
    if not mask.any():
        raise HTTPException(status_code=404, detail=f"No entry for {country_code}/{cluster}")

    score_kwargs = dict(
        severity_weight=severity_weight,
        funding_gap_weight=funding_gap_weight,
        need_weight=need_weight,
        ipc_weight=ipc_weight,
        events_weight=events_weight,
        n_bootstrap=0,
    )

    scored = compute_scores(df, **score_kwargs)
    target = scored[mask].iloc[0]

    cluster_ranked = scored[scored['cluster'] == cluster].sort_values('neglect_index', ascending=False)
    codes_list = cluster_ranked['countryCode'].tolist()
    current_rank = codes_list.index(country_code) + 1 if country_code in codes_list else 1
    total_in_cluster = len(cluster_ranked)

    df_adj = df.copy()
    idx = df_adj[mask].index[0]
    raw = df_adj.loc[idx, 'funding_cluster_specific']
    orig_funding = 0.0 if pd.isna(raw) else float(raw)
    df_adj.loc[idx, 'funding_cluster_specific'] = orig_funding + additional_funding

    scored_adj = compute_scores(df_adj, **score_kwargs)
    target_adj = scored_adj[mask].iloc[0]

    cluster_ranked_adj = scored_adj[scored_adj['cluster'] == cluster].sort_values('neglect_index', ascending=False)
    codes_adj = cluster_ranked_adj['countryCode'].tolist()
    new_rank = codes_adj.index(country_code) + 1 if country_code in codes_adj else 1

    def _opt(v):
        return None if pd.isna(v) else float(v)

    return CounterfactualResponse(
        country_code=country_code,
        country_name=iso3_to_name(country_code),
        cluster=cluster,
        requirements_usd=_opt(target.get('requirements_cluster_specific')),
        current_funding_usd=_opt(target.get('funding_cluster_specific')),
        additional_funding=additional_funding,
        current_coverage=float(target['coverage']),
        new_coverage=float(target_adj['coverage']),
        current_neglect_index=float(target['neglect_index']),
        new_neglect_index=float(target_adj['neglect_index']),
        current_rank=current_rank,
        new_rank=new_rank,
        total_in_cluster=total_in_cluster,
    )
