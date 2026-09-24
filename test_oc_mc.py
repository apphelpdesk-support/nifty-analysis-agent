import requests
import re
url = "https://www.moneycontrol.com/stocks/fno/view_option_chain.php?ind_id=9"
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers)
if "Open Interest" in response.text:
    print("Moneycontrol Options page accessible!")
else:
    print("Not accessible or format changed.")
