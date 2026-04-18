import pandas as pd
import numpy as np
import pycountry


def _country_name_to_iso3(name):
    manual = {
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
    if name in manual:
        return manual[name]
    pc = pycountry.countries.get(name=name)
    if pc:
        return pc.alpha_3
    try:
        return pycountry.countries.search_fuzzy(name)[0].alpha_3
    except LookupError:
        return None


def load_civilian_events():
    df = pd.read_csv(
        "data/number_of_events_targeting_civilians_by_country-year_as-of-03Apr2026.csv"
    )
    df['countryCode'] = df['COUNTRY'].map(_country_name_to_iso3)
    df = df.dropna(subset=['countryCode'])
    df = df.rename(columns={'YEAR': 'year', 'EVENTS': 'civilian_events'})
    return df[['countryCode', 'year', 'civilian_events']]


def load_ipc_data():
    df_ipc = pd.read_csv("data/ipc_global_area_wide.csv")

    df_ipc["year"] = pd.to_datetime(df_ipc["Date of analysis"], format="%b %Y").dt.year

    phase_cols = {
        "Phase 1 number current": "ipc_phase_1_people",
        "Phase 2 number current": "ipc_phase_2_people",
        "Phase 3 number current": "ipc_phase_3_people",
        "Phase 4 number current": "ipc_phase_4_people",
        "Phase 5 number current": "ipc_phase_5_people",
        "Phase 3+ number current": "ipc_phase_3plus_people",
    }

    df_ipc = df_ipc.rename(columns={"Country": "countryCode"})
    df_ipc = df_ipc[["countryCode", "year"] + list(phase_cols.keys())]

    for col in phase_cols:
        df_ipc[col] = pd.to_numeric(df_ipc[col], errors="coerce").fillna(0)

    df_ipc = (
        df_ipc.groupby(["countryCode", "year"])[list(phase_cols.keys())]
        .sum()
        .reset_index()
    )
    df_ipc = df_ipc.rename(columns=phase_cols)
    df_ipc["cluster"] = "Food Security"

    return df_ipc


def create_aggregate_base():
    df_funding = pd.read_csv("data/fts_requirements_funding_global.csv")
    df_funding_cluster = pd.read_csv("data/fts_requirements_funding_globalcluster_global.csv")

    merge_keys = ['id', 'code', 'countryCode', 'year', 'name']

    df_merged = pd.merge(
        df_funding, 
        df_funding_cluster, 
        on=merge_keys, 
        how='inner',
        suffixes=('_plan_total', '_cluster_specific')
    )

    numeric_cols = [
        'requirements_plan_total', 'funding_plan_total', 
        'requirements_cluster_specific', 'funding_cluster_specific'
    ]
    for col in numeric_cols:
        df_merged[col] = pd.to_numeric(df_merged[col], errors='coerce')

    needs_2024 = aggregate_needs("2024")
    needs_2025 = aggregate_needs("2025")
    all_needs = pd.concat([needs_2024, needs_2025], ignore_index=True)
    final_analysis = pd.merge(
        df_merged,
        all_needs,
        on=['countryCode', 'cluster', 'year'],
        how='inner'
    )

    df_ipc = load_ipc_data()
    final_analysis = pd.merge(
        final_analysis,
        df_ipc,
        on=['countryCode', 'year', 'cluster'],
        how='left'
    )

    df_events = load_civilian_events()
    final_analysis = pd.merge(
        final_analysis,
        df_events,
        on=['countryCode', 'year'],
        how='left'
    )

    return final_analysis

def _pct_rank_within_groups(values, group_codes):
    """Percentile rank of values within each integer-coded group. NaN input → NaN output."""
    out = np.full(len(values), np.nan)
    for g in np.unique(group_codes):
        mask = group_codes == g
        v = values[mask]
        finite = np.isfinite(v)
        if finite.sum() == 0:
            continue
        idx = np.where(mask)[0]
        # average-rank for ties, NaN rows stay NaN
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


def _neglect_score_on_sample(sample):
    """Compute neglect_index for a (possibly bootstrapped) dataframe. Returns a Series aligned to sample.index.
    All ranks are within-cluster so each sector is compared only to peer countries in the same sector."""
    orig_index = sample.index
    n = len(sample)

    coverage = (
        sample['funding_cluster_specific'].to_numpy(dtype=float)
        / np.where(sample['requirements_cluster_specific'].to_numpy(dtype=float) == 0,
                   np.nan,
                   sample['requirements_cluster_specific'].to_numpy(dtype=float))
    )
    coverage = np.nan_to_num(coverage, nan=0.0).clip(0, 1)

    cluster_codes = pd.Categorical(sample['cluster'].to_numpy()).codes

    need_rank     = _pct_rank_within_groups(sample['People_In_Need'].to_numpy(dtype=float), cluster_codes)
    coverage_rank = _pct_rank_within_groups(coverage, cluster_codes)

    ipc_phase_cols = [f'ipc_phase_{i}_people' for i in range(1, 6)]
    if all(c in sample.columns for c in ipc_phase_cols):
        total_ipc = sum(sample[c].fillna(0).to_numpy(dtype=float) for c in ipc_phase_cols)
        weighted_phase = sum(i * sample[f'ipc_phase_{i}_people'].fillna(0).to_numpy(dtype=float) for i in range(1, 6))
        with np.errstate(invalid='ignore', divide='ignore'):
            ipc_severity_norm = np.where(total_ipc > 0, (weighted_phase / total_ipc - 1) / 4, np.nan)
        ipc_severity_norm = np.clip(ipc_severity_norm, 0, 1)
        has_ipc = np.isfinite(ipc_severity_norm)
    else:
        ipc_severity_norm = np.full(n, np.nan)
        has_ipc = np.zeros(n, dtype=bool)

    if 'civilian_events' in sample.columns:
        year_codes = pd.Categorical(sample['year'].to_numpy()).codes
        combined_codes = cluster_codes * (year_codes.max() + 1) + year_codes
        events_rank = _pct_rank_within_groups(sample['civilian_events'].to_numpy(dtype=float), combined_codes)
    else:
        events_rank = np.full(n, np.nan)
    has_events = np.isfinite(events_rank)

    severity = need_rank.copy()
    has_both     = has_ipc & has_events
    has_ipc_only = has_ipc & ~has_events
    has_ev_only  = ~has_ipc & has_events

    severity[has_both]     = 0.5 * need_rank[has_both]     + 0.4 * ipc_severity_norm[has_both]     + 0.1 * events_rank[has_both]
    severity[has_ipc_only] = 0.5 * need_rank[has_ipc_only] + 0.5 * ipc_severity_norm[has_ipc_only]
    severity[has_ev_only]  = 0.9 * need_rank[has_ev_only]  + 0.1 * events_rank[has_ev_only]

    return pd.Series(severity * 0.6 + (1 - coverage_rank) * 0.4, index=orig_index)


def _bagging_uncertainty(df, n_bootstrap=200, seed=42):
    """Bootstrap the rank-based neglect score; return per-row std across resamples."""
    rng = np.random.default_rng(seed)
    n = len(df)
    # accumulate scores as a matrix: rows=bootstrap iterations, cols=original rows
    accumulator = np.full((n_bootstrap, n), np.nan)

    for b in range(n_bootstrap):
        boot_pos = rng.integers(0, n, size=n)
        scores = _neglect_score_on_sample(df.iloc[boot_pos]).to_numpy()
        # record one score per original row (first occurrence is fine)
        seen = np.zeros(n, dtype=bool)
        for pos, orig_i in enumerate(boot_pos):
            if not seen[orig_i]:
                accumulator[b, orig_i] = scores[pos]
                seen[orig_i] = True

    return pd.Series(np.nanstd(accumulator, axis=0), index=df.index)


def compute_indices(final_analysis):
    final_analysis['coverage'] = (
        final_analysis['funding_cluster_specific'] / final_analysis['requirements_cluster_specific']
    ).fillna(0).clip(upper=1.0)

    ipc_phase_cols = [f'ipc_phase_{i}_people' for i in range(1, 6)]
    if all(c in final_analysis.columns for c in ipc_phase_cols):
        total_ipc = sum(final_analysis[c].fillna(0) for c in ipc_phase_cols)
        weighted_phase = sum(i * final_analysis[f'ipc_phase_{i}_people'].fillna(0) for i in range(1, 6))
        ipc_severity_norm = ((weighted_phase / total_ipc.replace(0, float('nan'))) - 1) / 4
        final_analysis['ipc_severity_score'] = ipc_severity_norm.clip(0, 1).round(3)
    else:
        final_analysis['ipc_severity_score'] = float('nan')

    final_analysis['neglect_index'] = _neglect_score_on_sample(final_analysis)
    final_analysis['need_rank']     = final_analysis['People_In_Need'].rank(pct=True)
    final_analysis['coverage_rank'] = final_analysis['coverage'].rank(pct=True)

    print("Computing bagging uncertainty ...")
    final_analysis['uncertainty'] = _bagging_uncertainty(final_analysis).round(4)
    return final_analysis

def compute_neglect_index(df):
    """
    Only populated for Food Security rows that have IPC data.

    ipc_severity_score  – weighted average IPC phase (1–5) across all analyzed people.
                          Higher = more people in acute famine-level phases.
    funding_gap_ratio   – share of requirements that went unfunded (0 = fully funded, 1 = zero funding).
    neglect_index       – product of both components normalised to [0, 1].
                          High = severe food crisis AND badly underfunded.
    """
    fs = df['cluster'] == 'Food Security'

    total_ipc = sum(
        df[f'ipc_phase_{i}_people'].fillna(0) for i in range(1, 6)
    )
    weighted_phase = sum(
        i * df[f'ipc_phase_{i}_people'].fillna(0) for i in range(1, 6)
    )

    # average phase 1–5; normalise to [0, 1] so phase 1 → 0, phase 5 → 1
    ipc_severity_raw = weighted_phase / total_ipc.replace(0, float('nan'))
    ipc_severity_norm = (ipc_severity_raw - 1) / 4

    funding_gap = (
        1 - (df['funding_cluster_specific'] / df['requirements_cluster_specific']
             .replace(0, float('nan')))
    ).clip(0, 1)

    df['ipc_severity_score'] = float('nan')
    df['funding_gap_ratio'] = float('nan')
    df['neglect_index'] = float('nan')

    df.loc[fs, 'ipc_severity_score'] = ipc_severity_raw[fs].round(3)
    df.loc[fs, 'funding_gap_ratio'] = funding_gap[fs].round(3)
    df.loc[fs, 'neglect_index'] = (ipc_severity_norm * funding_gap)[fs].round(3)

    return df


def compute_global_neglect_index(df):
    """
    Computed for every row regardless of cluster.

    need_severity_score      – percentile rank of People_In_Need within each cluster (0–1).
                               Compares a country to peers facing the same type of need.
    combined_severity_score  – for Food Security rows: average of need_severity_score and
                               IPC-severity-norm (so both humanitarian signals contribute);
                               for all other rows: equals need_severity_score.
    global_funding_gap_ratio – share of cluster requirements that went unfunded (0–1).
    global_neglect_index     – combined_severity × global_funding_gap_ratio (0–1).
                               High = large unmet need AND badly underfunded.
    """
    df['need_severity_score'] = (
        df.groupby('cluster')['People_In_Need']
        .transform(lambda x: x.rank(pct=True, na_option='keep'))
        .round(3)
    )

    df['global_funding_gap_ratio'] = (
        1 - (df['funding_cluster_specific'] /
             df['requirements_cluster_specific'].replace(0, float('nan')))
    ).clip(0, 1).round(3)

    ipc_severity_norm = ((df['ipc_severity_score'] - 1) / 4).clip(0, 1)
    fs = (df['cluster'] == 'Food Security') & ipc_severity_norm.notna()

    df['combined_severity_score'] = df['need_severity_score']
    df.loc[fs, 'combined_severity_score'] = (
        (df.loc[fs, 'need_severity_score'] + ipc_severity_norm[fs]) / 2
    ).round(3)

    df['global_neglect_index'] = (
        df['combined_severity_score'] * df['global_funding_gap_ratio']
    ).round(3)

    return df


def aggregate_needs(year):
    pd.options.display.float_format = '{:,.0f}'.format
    df_needs = pd.read_csv(f"data/hpc_hno_{year}.csv", low_memory=False)
    df_needs = df_needs[1:] 

    df_needs["In Need"] = df_needs["In Need"].astype(str).str.replace(',', '')
    df_needs["In Need"] = pd.to_numeric(df_needs["In Need"], errors='coerce').fillna(0)

    df_clean = df_needs[df_needs['Admin 1 PCode'].isna() & df_needs['Category'].isna()]

    df_pivot = pd.pivot_table(
        df_clean, 
        values='In Need', 
        index='Country ISO3', 
        columns='Cluster', 
        aggfunc='sum', 
        fill_value=0
    ).reset_index()

    cluster_cols = [col for col in df_pivot.columns if col != 'Country ISO3']
    df_pivot = df_pivot.rename(columns={col: f"In Need - {col}" for col in cluster_cols})
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
        "Country ISO3": "countryCode"
    }

    df_pivot.rename(columns=cluster_mapping, inplace=True)
    df_pivot = pd.melt(
        df_pivot,
        id_vars=['countryCode'],
        value_vars=[c for c in df_pivot.columns if c != 'countryCode'],
        var_name='cluster',
        value_name='People_In_Need'
    )
    df_pivot["year"] = int(year)
    return df_pivot


import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

CLUSTER_COLORS = {
    'Food Security':                          '#d62728',
    'Nutrition':                              '#e377c2',
    'Health':                                 '#2ca02c',
    'Water Sanitation Hygiene':               '#17becf',
    'Protection':                             '#9467bd',
    'Protection - Child Protection':          '#7f7f7f',
    'Protection - Gender-Based Violence':     '#bcbd22',
    'Protection - Housing, Land and Property':'#8c564b',
    'Protection - Mine Action':               '#c49c94',
    'Education':                              '#1f77b4',
    'Emergency Shelter and NFI':              '#ff7f0e',
    'Early Recovery':                         '#aec7e8',
    'Logistics':                              '#ffbb78',
    'Camp Coordination / Management':         '#98df8a',
    'Coordination and support services':      '#c5b0d5',
    'Multi-sector':                           '#f7b6d2',
    'Agriculture':                            '#c7c7c7',
}

def plot_neglect_ranking(df, top_n=25):
    plot_df = df.sort_values('neglect_index', ascending=True).tail(top_n).copy()
    plot_df['country_label'] = plot_df['countryCode'] + ' – ' + plot_df['cluster']
    ys = range(len(plot_df))

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, (ax_main, ax_scatter) = plt.subplots(
        1, 2, figsize=(18, 11),
        gridspec_kw={'width_ratios': [2.2, 1]}
    )

    # ── Left: ranked dot plot ────────────────────────────────────────────────
    ax_main.axvspan(0.8, 1.05, alpha=0.07, color='red')
    ax_main.axvspan(0.6, 0.8,  alpha=0.07, color='orange')
    ax_main.axvline(df['neglect_index'].mean(), color='steelblue',
                    linestyle='--', linewidth=1.2, alpha=0.6, label='Global avg')

    dot_colors = [CLUSTER_COLORS.get(c, '#444444') for c in plot_df['cluster']]
    people_sizes = 40 + 120 * (plot_df['People_In_Need'] / plot_df['People_In_Need'].max()).fillna(0)

    ax_main.errorbar(
        plot_df['neglect_index'], ys,
        xerr=plot_df['uncertainty'],
        fmt='none', ecolor='#bbbbbb', elinewidth=1.5, capsize=3, zorder=2,
    )
    sc = ax_main.scatter(
        plot_df['neglect_index'], ys,
        c=dot_colors, s=people_sizes,
        zorder=3, edgecolors='white', linewidths=0.6,
    )

    ax_main.set_yticks(ys)
    ax_main.set_yticklabels(plot_df['country_label'], fontsize=9)
    ax_main.set_xlabel('Neglect Index  (higher = more overlooked)', fontsize=11)
    ax_main.set_title(
        f'Top {top_n} Most Overlooked Country–Cluster Pairs\n'
        'dot size ~ people in need',
        fontsize=13, pad=12,
    )
    ax_main.set_xlim(0.4, 1.05)

    ax_main.axvspan(0.8, 1.05, alpha=0, color='none')  # dummy for legend
    legend_handles = [
        mpatches.Patch(color='red',    alpha=0.2, label='Critical  (>0.8)'),
        mpatches.Patch(color='orange', alpha=0.2, label='High  (0.6–0.8)'),
        plt.Line2D([0], [0], color='steelblue', linestyle='--', linewidth=1.2,
                   alpha=0.8, label='Global avg'),
    ]
    ax_main.legend(handles=legend_handles, loc='lower right', fontsize=9, frameon=True)

    # ── Right: severity vs funding-gap scatter for top entries ───────────────
    funding_gap = (1 - plot_df['coverage']).clip(0, 1)
    need_score  = plot_df['need_rank']
    neglect_norm = Normalize(vmin=plot_df['neglect_index'].min(), vmax=plot_df['neglect_index'].max())
    dot_colors_scatter = plt.cm.Reds(neglect_norm(plot_df['neglect_index']))

    ax_scatter.scatter(
        funding_gap, need_score,
        c=dot_colors_scatter, s=70, edgecolors='white', linewidths=0.5, zorder=3,
    )
    for _, row in plot_df.iterrows():
        ax_scatter.annotate(
            row['countryCode'],
            xy=(1 - row['coverage'], row['need_rank']),
            xytext=(3, 2), textcoords='offset points',
            fontsize=7, color='#333333',
        )

    ax_scatter.set_xlabel('Funding Gap  (1 − coverage)', fontsize=10)
    ax_scatter.set_ylabel('Severity Score  (need + IPC)', fontsize=10)
    ax_scatter.set_title('Gap vs Severity\n(colour = neglect index)', fontsize=11, pad=10)
    ax_scatter.set_xlim(-0.05, 1.1)
    ax_scatter.set_ylim(-0.05, 1.1)
    ax_scatter.plot([0, 1], [0, 1], color='grey', linestyle=':', linewidth=1, alpha=0.5)

    sm = ScalarMappable(cmap='Reds', norm=neglect_norm)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax_scatter, fraction=0.046, pad=0.04)
    cb.set_label('Neglect index', fontsize=9)

    plt.tight_layout()
    plt.savefig('crisis_neglect_ranking.png', dpi=150, bbox_inches='tight')
    print("Ranking visualization saved as 'crisis_neglect_ranking.png'")

# Execute

df = create_aggregate_base()

output_path = "data/big_analysis.csv"
df = compute_indices(df)

df.to_csv("aggregate.csv")

plot_neglect_ranking(df)
