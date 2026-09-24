import requests

url = "https://webapi.niftytrader.in/webapi/option/oi-data?symbol=NIFTY"
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)
print(response.status_code)
print(response.text[:200])
