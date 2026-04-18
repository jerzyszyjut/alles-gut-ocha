import pandas as pd


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

    df_needs = aggregate_needs("2024")

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

    df_needs.rename(columns=cluster_mapping, inplace=True)
    df_needs = pd.melt(
        df_needs,
        id_vars=['countryCode'],
        value_vars=[c for c in df_needs.columns if c != 'countryCode'],
        var_name='cluster',
        value_name='People_In_Need'
    )
    df_needs["year"] = 2024
    df_needs

    final_analysis = pd.merge(
        df_merged,
        df_needs,
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

    final_analysis = compute_neglect_index(final_analysis)
    final_analysis = compute_global_neglect_index(final_analysis)

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

    return df_pivot


df = create_aggregate_base()

output_path = "data/big_analysis.csv"
df.to_csv(output_path, index=False)
print(f"Saved {len(df)} rows to {output_path}")
print(df.head())
