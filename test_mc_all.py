import requests
import re
url = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/index.php"
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)
matches = re.findall(r'\{"date":"([^"]+)".*?"fiiCM":"([^"]+)"', response.text)
print(f"Found {len(matches)} historical FII dates from Moneycontrol.")
