import pandas as pd
import numpy as np

def emb(df_2024_normalized):
    from sklearn.manifold import TSNE
    from sklearn.preprocessing import StandardScaler
    import plotly.express as px
    import pandas as pd
    crisis_mapping = {
        # Active & Protracted Geopolitical Conflicts
        'SDN': 'Active Armed Conflict',
        'UKR': 'Conventional Interstate War',
        'SYR': 'Protracted Conflict',
        'YEM': 'Protracted Conflict & Blockade',
        'PSE': 'Protracted Geopolitical Conflict',
        'CAF': 'Protracted Armed Conflict',
        
        # Climate & Insurgency (The Sahel / Horn of Africa)
        'SOM': 'Climate & Insurgency',
        'BFA': 'Climate & Insurgency',
        'MLI': 'Climate & Insurgency',
        'NER': 'Climate & Insurgency',
        'NGA': 'Climate & Insurgency',
        'MOZ': 'Climate & Insurgency',
        'CMR': 'Regional Insurgency',
        'TCD': 'Climate & Spillover',

        # Internal / Resource / Non-State Conflicts
        'COD': 'Resource & Non-State Conflict',
        'MMR': 'Internal Armed Conflict',
        'ETH': 'Internal Conflict & Climate',
        'SSD': 'Internal Conflict & Climate',
        
        # Urban Violence & Economic Crises
        'HTI': 'Urban Armed Violence',
        'SLV': 'Urban Violence & Migration',
        'HND': 'Urban Violence & Migration',
        'GTM': 'Urban Violence & Migration',
        'COL': 'Armed Violence & Migration',
        'AFG': 'Economic/Regime Transition',
        'VEN': 'Economic/Political Crisis',
        'BDI': 'Climate & Displacement'
    }

    print("\nPreparing vectors for 3D t-SNE...")
    pct_cols = [col for col in df_2024_normalized.columns if col.startswith('Needs_PercentOfPop_')]

    df_plot = df_2024_normalized.copy()
    df_plot = df_plot[df_plot['Regional_Population'] > 0].copy()
    df_plot['Country ISO3'] = df_plot['Country ISO3'].astype(str).str.strip()

    df_plot['Crisis_Type'] = df_plot['Country ISO3'].map(crisis_mapping).fillna('Other / Unmapped')
    
    # unmapped = df_plot[df_plot['Crisis_Type'] == 'Other / Unmapped']['Country ISO3'].unique()
    # if len(unmapped) > 0:
        # print(f"Warning: These ISO3 codes were not mapped: {unmapped}")
    X = df_plot[pct_cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 2. Upgrade to 3 Components (3D)
    print("Running 3D t-SNE calculation...")
    tsne = TSNE(n_components=3, perplexity=30, random_state=42, init='pca', learning_rate='auto')
    tsne_results = tsne.fit_transform(X_scaled)

    # Add the 3D coordinates back to the dataframe
    df_plot['tsne_3d_one'] = tsne_results[:,0]
    df_plot['tsne_3d_two'] = tsne_results[:,1]
    df_plot['tsne_3d_three'] = tsne_results[:,2]

    # 3. Plot using Plotly Express for interactivity
    print("Generating Interactive 3D Plot...")
    fig = px.scatter_3d(
        df_plot, 
        x='tsne_3d_one', 
        y='tsne_3d_two', 
        z='tsne_3d_three',
        color='Crisis_Type',          # This is the new Hue!
        hover_name='Admin 1 Name',    # When you hover, it shows the Province Name
        hover_data=['Country ISO3', 'Category'], # Extra data shown on hover
        title='3D t-SNE Projection: Humanitarian Need Signatures by Conflict Type',
        opacity=0.8,
        size_max=10
    )

    # Make the dots a bit smaller for better 3D visibility
    fig.update_traces(marker=dict(size=4))
    
    # Make the background dark for better contrast (optional)
    fig.update_layout(template="plotly_dark", margin=dict(l=0, r=0, b=0, t=40))

    # This will open the interactive plot in your browser or notebook output
    fig.show()

    # Optional: Save as an interactive HTML file instead of a static PNG
    fig.write_html("tsne_3d_crisis_signatures.html")
    print("Saved interactive plot to 'tsne_3d_crisis_signatures.html'")

pd.options.display.float_format = '{:,.2f}'.format

df_needs = pd.read_csv("data/hpc_hno_2024.csv", low_memory=False)
df_needs = df_needs.iloc[1:].copy()

df_needs["In Need"] = df_needs["In Need"].astype(str).str.replace(',', '')
df_needs["In Need"] = pd.to_numeric(df_needs["In Need"], errors='coerce').fillna(0)

df_regional = df_needs[(df_needs['Admin 1 PCode'].notna()) & (df_needs['Admin 2 PCode'].isna())].copy()
df_regional['Category'] = df_regional['Category'].fillna('Total')

idx_cols = ['Country ISO3', 'Admin 1 PCode', 'Admin 1 Name', 'Category']
df_pivot = pd.pivot_table(
    df_regional, values='In Need', index=idx_cols, columns='Cluster', aggfunc='sum', fill_value=0
).reset_index()

cluster_cols = [col for col in df_pivot.columns if col not in idx_cols]
df_pivot = df_pivot.rename(columns={col: f"Needs_Absolute_{col.replace(' ', '')}" for col in cluster_cols})

df_pop = pd.read_csv("data/cod_population_admin1.csv", low_memory=False)
df_pop["Population"] = df_pop["Population"].astype(str).str.replace(',', '')
df_pop["Population"] = pd.to_numeric(df_pop["Population"], errors='coerce').fillna(0)

df_pop_reg = df_pop[df_pop['Gender'].str.lower().isin(['all', 'total', 'both']) | df_pop['Gender'].isna()]
df_pop_reg = df_pop_reg.groupby('ADM1_PCODE')['Population'].max().reset_index()
df_pop_reg = df_pop_reg.rename(columns={'ADM1_PCODE': 'Admin 1 PCode', 'Population': 'Regional_Population'})

df_2024_normalized = pd.merge(df_pivot, df_pop_reg, on='Admin 1 PCode', how='left')

print("4. Normalizing Needs by Population Size...")
abs_cols = [col for col in df_2024_normalized.columns if col.startswith('Needs_Absolute_')]

for col in abs_cols:
    sector_name = col.replace('Needs_Absolute_', '')
    pct_col = f"Needs_PercentOfPop_{sector_name}"
    print(sector_name)
    df_2024_normalized[pct_col] = (df_2024_normalized[col] / df_2024_normalized['Regional_Population']) * 100
    df_2024_normalized[pct_col] = df_2024_normalized[pct_col].replace([np.inf, -np.inf], np.nan).fillna(0)


print(df_2024_normalized)
df_2024_normalized.to_csv("aggregate.csv")
emb(df_2024_normalized)
# view_cols = ['Country ISO3', 'Admin 1 Name', 'Regional_Population', 'Needs_Absolute_WASH', 'Needs_PercentOfPop_WASH']
# if 'Needs_Absolute_WASH' in df_2024_normalized.columns:
#     df_top_wash_crises = df_2024_normalized.sort_values(by='Needs_PercentOfPop_WASH', ascending=False)
#     print(df_top_wash_crises[view_cols].head(10))
