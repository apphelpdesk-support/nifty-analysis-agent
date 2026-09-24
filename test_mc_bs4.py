import requests
from bs4 import BeautifulSoup
import re

url = "https://www.moneycontrol.com/stocks/fno/view_option_chain.php?ind_id=9"
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

max_call_oi = 0
max_call_strike = 0
max_put_oi = 0
max_put_strike = 0

# Moneycontrol option chain table
tables = soup.find_all("table")
for table in tables:
    if "Strike Price" in table.text and "Open Int" in table.text:
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 8:
                try:
                    # Call OI is often in the first few cols, Strike is in the middle
                    # Let's just find the strike column
                    # typically: [0: call OI, 1: Call Vol, ... Strike (middle) ... Put Vol, Put OI]
                    strike_str = cols[4].text.replace(',', '').strip()
                    if "." in strike_str and float(strike_str) > 0:
                        strike = float(strike_str)
                        call_oi = float(cols[0].text.replace(',', '').replace('-', '0'))
                        put_oi = float(cols[8].text.replace(',', '').replace('-', '0'))
                        
                        if call_oi > max_call_oi:
                            max_call_oi = call_oi
                            max_call_strike = strike
                            
                        if put_oi > max_put_oi:
                            max_put_oi = put_oi
                            max_put_strike = strike
                except Exception as e:
                    pass

print("Max Call OI Strike:", max_call_strike)
print("Max Put OI Strike:", max_put_strike)
