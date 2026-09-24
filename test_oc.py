import requests
import json

url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

# Usually requires a session to hit the main page first to get cookies
session = requests.Session()
session.get("https://www.nseindia.com", headers=headers, timeout=10)
res = session.get(url, headers=headers, timeout=10)

if res.status_code == 200:
    data = res.json()
    expiryDates = data['records']['expiryDates']
    print("Found Expiry Dates:", expiryDates[:3])
else:
    print("Failed to fetch. Status:", res.status_code)
