import pandas as pd


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
    return final_analysis


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

print(df.head())
