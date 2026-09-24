import pandas as pd
import requests

url = 'https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/index.php'
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)
dfs = pd.read_html(response.text)
print("Found tables:", len(dfs))
for i, df in enumerate(dfs):
    print(f"Table {i}:")
    print(df.head(2))
