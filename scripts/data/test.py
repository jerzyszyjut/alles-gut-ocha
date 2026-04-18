import pandas as pd

# Load the financial data
df_funding = pd.read_csv("data/fts_requirements_funding_global.csv", low_memory=False)

# Filter for the most recent complete year (e.g., 2025)
df_funding['year'] = pd.to_numeric(df_funding['year'], errors='coerce')
df_current = df_funding[df_funding['year'] == 2025].copy()

# Clean financial columns
df_current['requirements'] = pd.to_numeric(df_current['requirements'], errors='coerce').fillna(0)
df_current['funding'] = pd.to_numeric(df_current['funding'], errors='coerce').fillna(0)
df_current['percentFunded'] = pd.to_numeric(df_current['percentFunded'], errors='coerce').fillna(0)

# Filter for significant crises (Requirements > $10M) to remove noise
df_significant = df_current[df_current['requirements'] > 10000000].copy()

# Calculate the raw dollar gap
df_significant['Funding Gap (USD)'] = df_significant['requirements'] - df_significant['funding']

# Rank them by lowest percentage funded
df_ranked = df_significant.sort_values(by='percentFunded', ascending=True)

# Select the necessary columns
top_underfunded = df_ranked[['name', 'countryCode', 'requirements', 'funding', 'Funding Gap (USD)', 'percentFunded']].head(15)

# Print beautifully
pd.options.display.float_format = '{:,.0f}'.format
print(top_underfunded.to_string(index=False))