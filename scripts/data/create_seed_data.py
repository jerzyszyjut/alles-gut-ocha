import pandas as pd
import numpy as np

def build_llm_gold_table(datadir, years=[2024, 2025]):
    print("Initializing Gold Table Build...")
    yearly_dataframes = []
    
    for year in years:
        df_needs = pd.read_csv(f"{datadir}/hpc_hno_{year}.csv", low_memory=False)
        df_needs = df_needs[1:] 
        df_needs["In Need"] = df_needs["In Need"].astype(str).str.replace(',', '')
        df_needs["In Need"] = pd.to_numeric(df_needs["In Need"], errors='coerce').fillna(0)
        df_regional = df_needs[(df_needs['Admin 1 PCode'].notna()) & (df_needs['Admin 2 PCode'].isna())].copy()
        df_regional['Category'] = df_regional['Category'].fillna('Total')
        df_regional['Year'] = year
        yearly_dataframes.append(df_regional)
        
    df_history = pd.concat(yearly_dataframes, ignore_index=True)
    idx_cols = ['Country ISO3', 'Admin 1 PCode', 'Admin 1 Name', 'Category', 'Year']
    df_gold = pd.pivot_table(
        df_history, values='In Need', index=idx_cols, columns='Cluster', aggfunc='sum', fill_value=0
    ).reset_index()
    
    cluster_cols = [col for col in df_gold.columns if col not in idx_cols]
    df_gold = df_gold.rename(columns={col: f"Needs_Absolute_{col.replace(' ', '')}" for col in cluster_cols})
    
    df_pop = pd.read_csv(f"{datadir}/cod_population_admin1.csv", low_memory=False)
    df_pop["Population"] = df_pop["Population"].astype(str).str.replace(',', '')
    df_pop["Population"] = pd.to_numeric(df_pop["Population"], errors='coerce').fillna(0)
    df_pop_reg = df_pop[df_pop['Gender'].str.lower().isin(['all', 'total', 'both']) | df_pop['Gender'].isna()]
    df_pop_reg = df_pop_reg.groupby('ADM1_PCODE')['Population'].max().reset_index()
    df_pop_reg = df_pop_reg.rename(columns={'ADM1_PCODE': 'Admin 1 PCode', 'Population': 'Regional_Population_Total'})
    
    df_gold = pd.merge(df_gold, df_pop_reg, on='Admin 1 PCode', how='left')
    
    abs_cols = [col for col in df_gold.columns if col.startswith('Needs_Absolute_')]
    for col in abs_cols:
        sector_name = col.replace('Needs_Absolute_', '')
        pct_col = f"Needs_PercentOfPop_{sector_name}"
        df_gold[pct_col] = (df_gold[col] / df_gold['Regional_Population_Total']) * 100
        df_gold[pct_col] = df_gold[pct_col].replace([np.inf, -np.inf], np.nan).fillna(0).round(2)

    print("Computing Historical Neglect (<= 2023)...")
    df_funding = pd.read_csv(f"{datadir}/fts_requirements_funding_global.csv", low_memory=False)
    df_funding['year'] = pd.to_numeric(df_funding['year'], errors='coerce')
    df_funding['percentFunded'] = pd.to_numeric(df_funding['percentFunded'], errors='coerce').fillna(0)
    df_historical = df_funding[(df_funding['year'] >= 2019) & (df_funding['year'] <= 2023)].copy()
    
    historical_avg = df_historical.groupby('countryCode')['percentFunded'].mean().reset_index()
    historical_avg = historical_avg.rename(columns={
        'countryCode': 'Country ISO3', 
        'percentFunded': 'Historical_Avg_Funding_Pct_2019_2023'
    })
    
    # Count how many years in that window the country was severely neglected (< 30% funded)
    df_historical['Severe_Neglect_Flag'] = (df_historical['percentFunded'] < 30).astype(int)
    years_neglected = df_historical.groupby('countryCode')['Severe_Neglect_Flag'].sum().reset_index()
    years_neglected = years_neglected.rename(columns={
        'countryCode': 'Country ISO3',
        'Severe_Neglect_Flag': 'Years_Severely_Underfunded_Pre2024'
    })

    df_funding['requirements'] = pd.to_numeric(df_funding['requirements'], errors='coerce').fillna(0)
    df_funding['funding'] = pd.to_numeric(df_funding['funding'], errors='coerce').fillna(0)
    df_funding_current = df_funding[['countryCode', 'year', 'requirements', 'funding', 'percentFunded']].copy()
    df_funding_current = df_funding_current.rename(columns={
        'countryCode': 'Country ISO3', 'year': 'Year',
        'requirements': 'National_Funding_Required_USD',
        'funding': 'National_Funding_Received_USD',
        'percentFunded': 'National_Percent_Funded'
    })
    
    df_gold = pd.merge(df_gold, df_funding_current, on=['Country ISO3', 'Year'], how='left')
    df_gold = pd.merge(df_gold, historical_avg, on='Country ISO3', how='left')
    df_gold = pd.merge(df_gold, years_neglected, on='Country ISO3', how='left')
    
    funding_cols = [
        'National_Funding_Required_USD', 'National_Funding_Received_USD', 'National_Percent_Funded',
        'Historical_Avg_Funding_Pct_2019_2023', 'Years_Severely_Underfunded_Pre2024'
    ]
    df_gold[funding_cols] = df_gold[funding_cols].fillna(0).round(2)
    
    print("Gold Table Build Complete!")
    return df_gold

df_gold_master = build_llm_gold_table("data", [2024, 2025])
df_gold_master.to_csv("aggregate.csv")
print(df_gold_master['Historical_Avg_Funding_Pct_2019_2023'])