import json
import re

path = "scripts/export_dashboard.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Add requests and re
if "import requests" not in content:
    content = content.replace("import yfinance", "import yfinance\nimport requests\nimport re")

# Replace FII scraping logic
fii_logic = """
    # Fetch Moneycontrol FII data
    mc_fii_dict = {}
    try:
        url = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/index.php"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        matches = re.findall(r'\{"date":"([^"]+)".*?"fiiCM":"([^"]+)"', response.text)
        for d, val in matches:
            mc_fii_dict[d] = float(val.replace(',', ''))
    except:
        pass
"""

content = content.replace("    fii_df = None\n    if NSELIB_AVAILABLE:", fii_logic + "\n    fii_df = None\n    if NSELIB_AVAILABLE:")

fii_check_logic = """
        # MC FII logic
        if date_str in mc_fii_dict:
            net_val = mc_fii_dict[date_str]
            if net_val > 500: fii = "buying"
            elif net_val < -500: fii = "selling"
        elif fii == "neutral":
            # Fallback to tighter gap heuristic
            try:
                if idx_long > 0:
                    prev_close = df["Close"].iloc[idx_long - 1]
                    open_price = row["Open"]
                    gap_pct = ((open_price - prev_close) / prev_close) * 100
                    change_pct = ((close - open_price) / open_price) * 100
                    if gap_pct > 0.15 and change_pct > 0: fii = "buying"
                    elif gap_pct < -0.15 and change_pct < 0: fii = "selling"
            except:
                pass
"""

# We need to replace the old FII logic which starts at "# FII logic"
old_fii_logic_start = content.find("        # FII logic")
old_fii_logic_end = content.find("        data[date_str] = {")
old_fii_logic = content[old_fii_logic_start:old_fii_logic_end]

content = content.replace(old_fii_logic, fii_check_logic + "\n")

# Also we need to export High and Low
signals_logic = """        signals = {
            "close": close,
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),"""
            
content = content.replace('        signals = {\n            "close": close,', signals_logic)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated export_dashboard.py")
