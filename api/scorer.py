"""Core scoring logic — refactored from scripts/data/create_big_csv.py."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pycountry

DATA_DIR = Path(__file__).parent.parent / "data"


# ── Country helpers ──────────────────────────────────────────────────────────

_MANUAL_ISO3 = {
    'Bolivia': 'BOL', 'Bosnia and Herzegovina': 'BIH', 'Brunei': 'BRN',
    'Cape Verde': 'CPV', 'Democratic Republic of the Congo': 'COD',
    'Democratic Republic of Congo': 'COD', 'Republic of Congo': 'COG',
    'Republic of the Congo': 'COG', 'Eswatini': 'SWZ', 'eSwatini': 'SWZ',
    'Iran': 'IRN', 'Kosovo': 'XKX', 'Laos': 'LAO', 'Moldova': 'MDA',
    'North Korea': 'PRK', 'Palestine': 'PSE', 'Russia': 'RUS',
    'South Korea': 'KOR', 'Syria': 'SYR', 'Taiwan': 'TWN',
    'Tanzania': 'TZA', 'Turkey': 'TUR', 'Venezuela': 'VEN',
    'Vietnam': 'VNM', "Côte d'Ivoire": 'CIV', 'Ivory Coast': 'CIV',
    'Micronesia': 'FSM', 'East Timor': 'TLS',
    'Bailiwick of Guernsey': 'GGY', 'Bailiwick of Jersey': 'JEY',
    'Caribbean Netherlands': 'BES',
    'French Southern and Antarctic Lands': 'ATF',
}


def _country_name_to_iso3(name: str) -> str | None:
    if name in _MANUAL_ISO3:
        return _MANUAL_ISO3[name]
    pc = pycountry.countries.get(name=name)
    if pc:
        return pc.alpha_3
    try:
        return pycountry.countries.search_fuzzy(name)[0].alpha_3
    except LookupError:
        return None


def iso3_to_name(code: str) -> str:
    pc = pycountry.countries.get(alpha_3=code)
    return pc.name if pc else code


# ── Data loading ─────────────────────────────────────────────────────────────

def load_civilian_events() -> pd.DataFrame:
    df = pd.read_csv(
        DATA_DIR / "number_of_events_targeting_civilians_by_country-year_as-of-03Apr2026.csv"
    )
    df['countryCode'] = df['COUNTRY'].map(_country_name_to_iso3)
    df = df.dropna(subset=['countryCode'])
    df = df.rename(columns={'YEAR': 'year', 'EVENTS': 'civilian_events'})
    return df[['countryCode', 'year', 'civilian_events']]


def load_ipc_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "ipc_global_area_wide.csv")
    df["year"] = pd.to_datetime(df["Date of analysis"], format="%b %Y").dt.year
    phase_cols = {
        "Phase 1 number current": "ipc_phase_1_people",
        "Phase 2 number current": "ipc_phase_2_people",
        "Phase 3 number current": "ipc_phase_3_people",
        "Phase 4 number current": "ipc_phase_4_people",
        "Phase 5 number current": "ipc_phase_5_people",
        "Phase 3+ number current": "ipc_phase_3plus_people",
    }
    df = df.rename(columns={"Country": "countryCode"})
    df = df[["countryCode", "year"] + list(phase_cols.keys())]
    for col in phase_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df = df.groupby(["countryCode", "year"])[list(phase_cols.keys())].sum().reset_index()
    df = df.rename(columns=phase_cols)
    df["cluster"] = "Food Security"
    return df


def _aggregate_needs_year(year: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"hpc_hno_{year}.csv", low_memory=False)
    df = df[1:]
    df["In Need"] = pd.to_numeric(
        df["In Need"].astype(str).str.replace(',', ''), errors='coerce'
    ).fillna(0)
    df_clean = df[df['Admin 1 PCode'].isna() & df['Category'].isna()]
    df_pivot = pd.pivot_table(
        df_clean, values='In Need', index='Country ISO3',
        columns='Cluster', aggfunc='sum', fill_value=0,
    ).reset_index()
    cluster_cols = [c for c in df_pivot.columns if c != 'Country ISO3']
    df_pivot = df_pivot.rename(columns={c: f"In Need - {c}" for c in cluster_cols})
    cluster_mapping = {
        'In Need - AGR': 'Agriculture',
        'In Need - CCM': 'Camp Coordination / Management',
        'In Need - CSS': 'Coordination and support services',
        'In Need - EDU': 'Education',
        'In Need - ERY': 'Early Recovery',
        'In Need - FSC': 'Food Security',
        'In Need - HEA': 'Health',
        'In Need - LOG': 'Logistics',
        'In Need - MS':  'Multi-sector',
        'In Need - NUT': 'Nutrition',
        'In Need - PRO': 'Protection',
        'In Need - PRO-CPN': 'Protection - Child Protection',
        'In Need - PRO-GBV': 'Protection - Gender-Based Violence',
        'In Need - PRO-HLP': 'Protection - Housing, Land and Property',
        'In Need - PRO-MIN': 'Protection - Mine Action',
        'In Need - SHL': 'Emergency Shelter and NFI',
        'In Need - WSH': 'Water Sanitation Hygiene',
        'In Need - ALL': 'Total In Need',
        "Country ISO3": "countryCode",
    }
    df_pivot.rename(columns=cluster_mapping, inplace=True)
    df_melted = pd.melt(
        df_pivot,
        id_vars=['countryCode'],
        value_vars=[c for c in df_pivot.columns if c != 'countryCode'],
        var_name='cluster',
        value_name='People_In_Need',
    )
    df_melted["year"] = int(year)
    return df_melted


def aggregate_by_country_cluster(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse a multi-year dataframe to one row per (countryCode, cluster).

    All numeric columns (requirements, funding, people in need, IPC phases,
    conflict events) are averaged across the years present in df.
    The year column is dropped entirely.
    """
    group_keys = ['countryCode', 'cluster']
    numeric_cols = [
        c for c in df.select_dtypes(include='number').columns
        if c != 'year'
    ]
    return df.groupby(group_keys, as_index=False)[numeric_cols].mean()


def create_aggregate_base() -> pd.DataFrame:
    df_funding = pd.read_csv(DATA_DIR / "fts_requirements_funding_global.csv")
    df_funding_cluster = pd.read_csv(
        DATA_DIR / "fts_requirements_funding_globalcluster_global.csv"
    )
    merge_keys = ['id', 'code', 'countryCode', 'year', 'name']
    df_merged = pd.merge(
        df_funding, df_funding_cluster, on=merge_keys, how='inner',
        suffixes=('_plan_total', '_cluster_specific'),
    )
    for col in ['requirements_plan_total', 'funding_plan_total',
                'requirements_cluster_specific', 'funding_cluster_specific']:
        df_merged[col] = pd.to_numeric(df_merged[col], errors='coerce')

    all_needs = pd.concat(
        [_aggregate_needs_year("2024"), _aggregate_needs_year("2025")], ignore_index=True
    )
    df = pd.merge(df_merged, all_needs, on=['countryCode', 'cluster', 'year'], how='inner')
    df = pd.merge(df, load_ipc_data(), on=['countryCode', 'year', 'cluster'], how='left')
    df = pd.merge(df, load_civilian_events(), on=['countryCode', 'year'], how='left')
    return df


# ── Scoring ──────────────────────────────────────────────────────────────────

def _pct_rank_within_groups(values: np.ndarray, group_codes: np.ndarray) -> np.ndarray:
    out = np.full(len(values), np.nan)
    for g in np.unique(group_codes):
        mask = group_codes == g
        v = values[mask]
        finite = np.isfinite(v)
        if finite.sum() == 0:
            continue
        idx = np.where(mask)[0]
        order = np.argsort(v[finite], kind='stable')
        sv = v[finite][order]
        ranks = np.empty(finite.sum())
        i = 0
        while i < len(sv):
            j = i + 1
            while j < len(sv) and sv[j] == sv[i]:
                j += 1
            ranks[order[i:j]] = (i + j + 1) / 2.0
            i = j
        pct = ranks / finite.sum()
        out[idx[finite]] = pct
    return out


def _neglect_score_on_sample(
    sample: pd.DataFrame,
    severity_weight: float = 0.6,
    funding_gap_weight: float = 0.4,
    need_weight: float = 0.5,
    ipc_weight: float = 0.4,
    events_weight: float = 0.1,
) -> pd.Series:
    """Rank-based neglect index with fully parameterized weights.

    All weights are auto-normalised so they always sum to 1.
    Ranks are computed within-cluster so each sector is compared only to peers.
    """
    orig_index = sample.index
    n = len(sample)

    # Normalise top-level weights
    top_total = severity_weight + funding_gap_weight
    if top_total == 0:
        top_total = 1.0
    sw = severity_weight / top_total
    gw = funding_gap_weight / top_total

    coverage = (
        sample['funding_cluster_specific'].to_numpy(dtype=float)
        / np.where(
            sample['requirements_cluster_specific'].to_numpy(dtype=float) == 0,
            np.nan,
            sample['requirements_cluster_specific'].to_numpy(dtype=float),
        )
    )
    coverage = np.nan_to_num(coverage, nan=0.0).clip(0, 1)

    cluster_codes = pd.Categorical(sample['cluster'].to_numpy()).codes
    need_rank     = _pct_rank_within_groups(sample['People_In_Need'].to_numpy(dtype=float), cluster_codes)
    coverage_rank = _pct_rank_within_groups(coverage, cluster_codes)

    ipc_phase_cols = [f'ipc_phase_{i}_people' for i in range(1, 6)]
    if all(c in sample.columns for c in ipc_phase_cols):
        total_ipc = sum(sample[c].fillna(0).to_numpy(dtype=float) for c in ipc_phase_cols)
        weighted_phase = sum(
            i * sample[f'ipc_phase_{i}_people'].fillna(0).to_numpy(dtype=float)
            for i in range(1, 6)
        )
        with np.errstate(invalid='ignore', divide='ignore'):
            ipc_sev = np.where(total_ipc > 0, (weighted_phase / total_ipc - 1) / 4, np.nan)
        ipc_sev = np.clip(ipc_sev, 0, 1)
        has_ipc = np.isfinite(ipc_sev)
    else:
        ipc_sev = np.full(n, np.nan)
        has_ipc = np.zeros(n, dtype=bool)

    if 'civilian_events' in sample.columns:
        if 'year' in sample.columns:
            year_codes = pd.Categorical(sample['year'].to_numpy()).codes
            event_groups = cluster_codes * (year_codes.max() + 1) + year_codes
        else:
            event_groups = cluster_codes
        events_rank = _pct_rank_within_groups(
            sample['civilian_events'].to_numpy(dtype=float), event_groups
        )
    else:
        events_rank = np.full(n, np.nan)
    has_events = np.isfinite(events_rank)

    # Build severity using normalised sub-weights
    severity = need_rank.copy()
    has_both     = has_ipc & has_events
    has_ipc_only = has_ipc & ~has_events
    has_ev_only  = ~has_ipc & has_events

    def _norm3(a, b, c):
        t = a + b + c
        return (a / t, b / t, c / t) if t > 0 else (1.0, 0.0, 0.0)

    def _norm2(a, b):
        t = a + b
        return (a / t, b / t) if t > 0 else (1.0, 0.0)

    if has_both.any():
        nw, iw, ew = _norm3(need_weight, ipc_weight, events_weight)
        severity[has_both] = (
            nw * need_rank[has_both]
            + iw * ipc_sev[has_both]
            + ew * events_rank[has_both]
        )
    if has_ipc_only.any():
        nw, iw = _norm2(need_weight, ipc_weight)
        severity[has_ipc_only] = nw * need_rank[has_ipc_only] + iw * ipc_sev[has_ipc_only]
    if has_ev_only.any():
        nw, ew = _norm2(need_weight, events_weight)
        severity[has_ev_only] = nw * need_rank[has_ev_only] + ew * events_rank[has_ev_only]

    return pd.Series(sw * severity + gw * (1 - coverage_rank), index=orig_index)


def _bagging_uncertainty(
    df: pd.DataFrame,
    n_bootstrap: int = 200,
    seed: int = 42,
    **score_kwargs,
) -> pd.Series:
    rng = np.random.default_rng(seed)
    n = len(df)
    accumulator = np.full((n_bootstrap, n), np.nan)
    for b in range(n_bootstrap):
        boot_pos = rng.integers(0, n, size=n)
        scores = _neglect_score_on_sample(df.iloc[boot_pos], **score_kwargs).to_numpy()
        seen = np.zeros(n, dtype=bool)
        for pos, orig_i in enumerate(boot_pos):
            if not seen[orig_i]:
                accumulator[b, orig_i] = scores[pos]
                seen[orig_i] = True
    return pd.Series(np.nanstd(accumulator, axis=0), index=df.index)


def compute_scores(
    df: pd.DataFrame,
    severity_weight: float = 0.6,
    funding_gap_weight: float = 0.4,
    need_weight: float = 0.5,
    ipc_weight: float = 0.4,
    events_weight: float = 0.1,
    n_bootstrap: int = 50,
) -> pd.DataFrame:
    """Score a (filtered) dataframe and return it with computed columns."""
    out = df.copy()
    out['coverage'] = (
        out['funding_cluster_specific'] / out['requirements_cluster_specific']
    ).fillna(0).clip(upper=1.0)

    ipc_phase_cols = [f'ipc_phase_{i}_people' for i in range(1, 6)]
    if all(c in out.columns for c in ipc_phase_cols):
        total_ipc = sum(out[c].fillna(0) for c in ipc_phase_cols)
        weighted_phase = sum(i * out[f'ipc_phase_{i}_people'].fillna(0) for i in range(1, 6))
        ipc_sev = ((weighted_phase / total_ipc.replace(0, float('nan'))) - 1) / 4
        out['ipc_severity_score'] = ipc_sev.clip(0, 1).round(3)
    else:
        out['ipc_severity_score'] = float('nan')

    score_kwargs = dict(
        severity_weight=severity_weight,
        funding_gap_weight=funding_gap_weight,
        need_weight=need_weight,
        ipc_weight=ipc_weight,
        events_weight=events_weight,
    )
    out['neglect_index'] = _neglect_score_on_sample(out, **score_kwargs).round(4)
    out['need_rank']     = out['People_In_Need'].rank(pct=True).round(4)
    out['coverage_rank'] = out['coverage'].rank(pct=True).round(4)

    if n_bootstrap > 0:
        out['uncertainty'] = _bagging_uncertainty(out, n_bootstrap=n_bootstrap, **score_kwargs).round(4)
    else:
        out['uncertainty'] = float('nan')

    return out
