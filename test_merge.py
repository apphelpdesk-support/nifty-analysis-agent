from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from nselib import capital_market

df = yf.Ticker("^NSEI").history(period="10y")
last_date = df.index[-1].date()
today = datetime.now().date()

if today > last_date:
    print(f"yfinance missing data between {last_date} and {today}. Fetching from nselib...")
    from_str = (last_date + timedelta(days=1)).strftime("%d-%m-%Y")
    to_str = today.strftime("%d-%m-%Y")
    
    try:
        ns = capital_market.index_data(index="Nifty 50", from_date=from_str, to_date=to_str)
        if not ns.empty:
            # Map columns
            ns['Date'] = pd.to_datetime(ns['TIMESTAMP'], format='%d-%b-%Y')
            ns = ns.set_index('Date')
            
            # Localize to Asia/Kolkata since yfinance uses that timezone
            ns.index = ns.index.tz_localize('Asia/Kolkata')
            
            ns['Open'] = pd.to_numeric(ns['OPEN_INDEX_VAL'])
            ns['High'] = pd.to_numeric(ns['HIGH_INDEX_VAL'])
            ns['Low'] = pd.to_numeric(ns['LOW_INDEX_VAL'])
            ns['Close'] = pd.to_numeric(ns['CLOSING_INDEX_VAL'])
            
            # Keep only standard columns
            ns = ns[['Open', 'High', 'Low', 'Close']]
            
            # Drop duplicates if any overlap
            ns = ns[~ns.index.isin(df.index)]
            
            if not ns.empty:
                print("Found missing rows in nselib:")
                print(ns)
                
                df = pd.concat([df, ns]).sort_index()
                
    except Exception as e:
        print("nselib fetch failed:", e)

print("\nFinal df tail:")
print(df.tail())
