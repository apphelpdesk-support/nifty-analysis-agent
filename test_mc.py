import requests
import json
import re

url = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/index.php"
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)
match = re.search(r'"fiiCM":"([^"]+)"', response.text)
if match:
    print("Most recent FII CM:", match.group(1))
else:
    print("Could not find FII data in HTML.")

# Let's extract the whole JSON array!
match_array = re.search(r'\{"date":"([^"]+)".*?"fiiCM":"([^"]+)"', response.text)
if match_array:
    print("Date:", match_array.group(1), "FII:", match_array.group(2))
