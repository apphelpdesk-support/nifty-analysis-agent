import requests
import re

url = "https://www.moneycontrol.com/stocks/fno/view_option_chain.php?ind_id=9"
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)

# Find strikes. Moneycontrol table has columns for Call OI and Put OI.
# Let's see if we can extract via regex:
# Typically: <td ...>Open Int</td>... <td ...>Strike Price</td>...
# Let's extract all rows containing strike prices.
# A strike price on MC looks like <b><a href="...">24000.00</a></b>
strikes = re.findall(r'<b><a href="[^"]+">([0-9\.]+)</a></b>', response.text)
if strikes:
    print(f"Found {len(strikes)} strike prices. Example: {strikes[len(strikes)//2]}")
else:
    print("Could not find strikes.")
