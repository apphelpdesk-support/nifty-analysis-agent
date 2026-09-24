import requests
import pandas as pd

url = "https://www.moneycontrol.com/stocks/fno/view_option_chain.php?ind_id=9"
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)
dfs = pd.read_html(response.text)
for i, df in enumerate(dfs):
    if "Strike Price" in df.to_string():
        print(f"Found Option Chain in table {i}")
        print(df.head(2))
        break
