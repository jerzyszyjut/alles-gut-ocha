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
    df = pd.read_csv(DATA_DIR / "ipc_global_area_wide.csv", low_memory=False)
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
        columns='Cluster', aggfunc='max', fill_value=0,
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

    # Pull out the deduplicated country total before melting so it doesn't
    # become a fake cluster row and pollute downstream joins.
    country_total = None
    if 'Total In Need' in df_pivot.columns:
        country_total = df_pivot[['countryCode', 'Total In Need']].rename(
            columns={'Total In Need': 'country_total_pin'}
        )

    df_melted = pd.melt(
        df_pivot,
        id_vars=['countryCode'],
        value_vars=[c for c in df_pivot.columns if c not in ('countryCode', 'Total In Need')],
        var_name='cluster',
        value_name='People_In_Need',
    )
    df_melted["year"] = int(year)

    if country_total is not None:
        df_melted = df_melted.merge(country_total, on='countryCode', how='left')

    return df_melted


_STRUCTURAL_NEGLECT_COLS = frozenset([
    'consecutive_years_underfunded',
    'structural_neglect_score',
    'coverage_trend',
    'n_years_data',
])


def aggregate_by_country_cluster(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse a multi-year dataframe to one row per (countryCode, cluster).

    Numeric columns are averaged across years; structural neglect signals and
    country_total_pin are preserved via max/first since they are invariant
    across year-rows for the same (country, cluster) pair.
    The year column is dropped entirely.
    """
    group_keys = ['countryCode', 'cluster']
    skip_from_avg = {'year', 'country_total_pin'} | _STRUCTURAL_NEGLECT_COLS
    avg_cols = [
        c for c in df.select_dtypes(include='number').columns
        if c not in skip_from_avg
    ]
    result = df.groupby(group_keys, as_index=False)[avg_cols].mean()

    if 'country_total_pin' in df.columns:
        totals = df.groupby(group_keys, as_index=False)['country_total_pin'].max()
        result = result.merge(totals, on=group_keys, how='left')

    # Structural signals are identical across year-rows: preserve via max
    struct_num = [c for c in _STRUCTURAL_NEGLECT_COLS if c in df.columns]
    if struct_num:
        struct_agg = df.groupby(group_keys, as_index=False)[struct_num].max()
        result = result.merge(struct_agg, on=group_keys, how='left')

    # Preserve string/categorical columns that don't vary by year (e.g. neglect_type)
    str_cols = [
        c for c in df.select_dtypes(include='object').columns
        if c not in group_keys
    ]
    if str_cols:
        first_strs = df.groupby(group_keys)[str_cols].first().reset_index()
        result = result.merge(first_strs, on=group_keys, how='left')

    return result


_EXCLUDE_STRUCTURAL_CLUSTERS = frozenset([
    'Not specified', 'Multiple clusters/sectors (shared)', 'Other',
    'COVID-19', 'Emergency Telecommunications',
    'Protection - Human Trafficking & Smuggling',
])


def load_structural_neglect_signals(
    years_back: int = 6,
    underfunded_threshold: float = 0.5,
) -> pd.DataFrame:
    """Compute structural neglect signals from the full FTS cluster funding history.

    For each (countryCode, cluster) uses up to *years_back* years of data to compute:
    - consecutive_years_underfunded: current streak of underfunded years (most recent first)
    - structural_neglect_score: 0-1 composite (higher = more chronic neglect)
    - coverage_trend: linear slope of annual coverage (negative = worsening)
    - neglect_type: 'structural' | 'worsening' | 'acute' | 'improving' | 'adequate'
    - n_years_data: number of years with coverage data in the window

    Methodology: a crisis is *structural* when ≥3 consecutive recent years are underfunded
    AND the overall underfunding rate in the window is ≥60 %.
    A crisis is *worsening* when the coverage trend is strongly negative.
    This lets analysts separate chronic systemic failure from one-off gaps.
    """
    df = pd.read_csv(DATA_DIR / "fts_requirements_funding_globalcluster_global.csv")
    df['requirements'] = pd.to_numeric(df['requirements'], errors='coerce')
    df['funding'] = pd.to_numeric(df['funding'], errors='coerce')
    df['coverage'] = (
        df['funding'] / df['requirements'].replace(0, np.nan)
    ).clip(0, 1).fillna(0)

    # Cap at 2025: 2026 FTS data is partial (only a few months) and distorts trend signals
    max_year = min(int(df['year'].max()), 2025)
    min_year = max_year - years_back + 1
    df = df[df['year'].between(min_year, max_year)].copy()
    df = df[~df['cluster'].isin(_EXCLUDE_STRUCTURAL_CLUSTERS)]

    rows: list[dict] = []
    for (country, cluster), grp in df.groupby(['countryCode', 'cluster']):
        grp = grp.sort_values('year', ascending=False)
        coverages = grp['coverage'].tolist()
        years = grp['year'].tolist()
        n = len(years)
        if n == 0:
            continue

        # Current consecutive underfunded streak (counting from most recent year)
        consecutive = 0
        for cov in coverages:
            if cov < underfunded_threshold:
                consecutive += 1
            else:
                break

        n_underfunded = sum(1 for c in coverages if c < underfunded_threshold)
        pct_underfunded = n_underfunded / n

        # Linear coverage trend over window
        if n >= 3:
            xs = np.array(years, dtype=float) - np.mean(years)
            ys = np.array(coverages, dtype=float)
            slope = float(np.polyfit(xs, ys, 1)[0])
        else:
            slope = 0.0

        # Structural score: consecutive streak (saturates at 5 years) + frequency
        structural_neglect_score = round(
            0.6 * min(consecutive, 5) / 5 + 0.4 * pct_underfunded, 4
        )

        latest = coverages[0]
        if consecutive >= 3 and pct_underfunded >= 0.6:
            neglect_type = 'structural'
        elif slope < -0.03 and latest < underfunded_threshold:
            neglect_type = 'worsening'
        elif latest < underfunded_threshold:
            neglect_type = 'acute'
        elif slope > 0.03 and consecutive < 2:
            neglect_type = 'improving'
        else:
            neglect_type = 'adequate'

        rows.append({
            'countryCode': country,
            'cluster': cluster,
            'consecutive_years_underfunded': consecutive,
            'structural_neglect_score': structural_neglect_score,
            'coverage_trend': round(slope, 4),
            'neglect_type': neglect_type,
            'n_years_data': n,
        })

    return pd.DataFrame(rows)


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

    # Enrich with structural neglect signals derived from the full FTS history
    structural = load_structural_neglect_signals()
    df = pd.merge(df, structural, on=['countryCode', 'cluster'], how='left')

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
            avg_phase = np.where(total_ipc > 0, weighted_phase / total_ipc, np.nan)
            # Exponential doubling per IPC phase: each level ~2x more severe than previous.
            # (2^(phase-1) - 1) / 15  maps [1,5] → [0,1] with jumps 0.07, 0.13, 0.27, 0.53
            ipc_sev = np.where(
                total_ipc > 0,
                (np.power(2.0, avg_phase - 1.0) - 1.0) / 15.0,
                np.nan,
            )
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


def _bootstrap_stats(
    df: pd.DataFrame,
    n_bootstrap: int = 200,
    seed: int = 42,
    **score_kwargs,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bootstrap uncertainty + 90% rank confidence intervals in one pass.

    Returns (uncertainty_std, rank_ci_low, rank_ci_high).
    Rows absent from a bootstrap draw use baseline scores for rank computation.
    """
    rng = np.random.default_rng(seed)
    n = len(df)
    baseline = _neglect_score_on_sample(df, **score_kwargs).to_numpy()

    score_acc = np.full((n_bootstrap, n), np.nan)
    rank_acc  = np.full((n_bootstrap, n), np.nan)

    for b in range(n_bootstrap):
        boot_pos = rng.integers(0, n, size=n)
        boot_s   = _neglect_score_on_sample(df.iloc[boot_pos], **score_kwargs).to_numpy()

        iter_scores = baseline.copy()
        seen = np.zeros(n, dtype=bool)
        for pos, orig_i in enumerate(boot_pos):
            if not seen[orig_i]:
                iter_scores[orig_i] = boot_s[pos]
                score_acc[b, orig_i] = boot_s[pos]
                seen[orig_i] = True

        # Rank all rows by this iteration (rank 1 = highest neglect)
        valid = np.isfinite(iter_scores)
        if valid.sum() < 2:
            continue
        vi    = np.where(valid)[0]
        order = np.argsort(-iter_scores[valid], kind='stable')
        temp  = np.full(n, np.nan)
        for rpos, oi in enumerate(order):
            temp[vi[oi]] = rpos + 1
        rank_acc[b] = temp

    idx          = df.index
    uncertainty  = pd.Series(np.nanstd(score_acc, axis=0), index=idx).round(4)
    rank_ci_low  = pd.Series(np.nanpercentile(rank_acc,  5, axis=0), index=idx).round(0)
    rank_ci_high = pd.Series(np.nanpercentile(rank_acc, 95, axis=0), index=idx).round(0)
    return uncertainty, rank_ci_low, rank_ci_high


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
        avg_phase = weighted_phase / total_ipc.replace(0, float('nan'))
        ipc_sev = (np.power(2.0, avg_phase - 1.0) - 1.0) / 15.0
        out['ipc_severity_score'] = ipc_sev.clip(0, 1).round(3)
    else:
        out['ipc_severity_score'] = float('nan')

    # Severity case: which sub-metrics are available for each row
    _has_ipc = out['ipc_severity_score'].notna()
    _has_ev  = out['civilian_events'].notna() if 'civilian_events' in out.columns else pd.Series(False, index=out.index)
    out['severity_case'] = 'D'
    out.loc[_has_ev & ~_has_ipc, 'severity_case'] = 'C'
    out.loc[_has_ipc & ~_has_ev,  'severity_case'] = 'B'
    out.loc[_has_ipc & _has_ev,   'severity_case'] = 'A'

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
        unc, rci_lo, rci_hi = _bootstrap_stats(out, n_bootstrap=n_bootstrap, **score_kwargs)
        out['uncertainty']  = unc
        out['rank_ci_low']  = rci_lo.astype('Int64')
        out['rank_ci_high'] = rci_hi.astype('Int64')
    else:
        out['uncertainty']  = float('nan')
        out['rank_ci_low']  = pd.NA
        out['rank_ci_high'] = pd.NA

    return out
