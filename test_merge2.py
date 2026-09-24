from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from nselib import capital_market

df = yf.Ticker("^NSEI").history(period="10y")
last_date = df.index[-1].date()
today = datetime.now().date()

if today > last_date:
    from_str = (last_date + timedelta(days=1)).strftime("%d-%m-%Y")
    to_str = today.strftime("%d-%m-%Y")
    try:
        ns = capital_market.index_data(index="Nifty 50", from_date=from_str, to_date=to_str)
        if not ns.empty:
            ns['Date'] = pd.to_datetime(ns['TIMESTAMP'], format='%d-%b-%Y')
            ns = ns.set_index('Date')
            ns.index = ns.index.tz_localize('Asia/Kolkata')
            
            ns['Open'] = pd.to_numeric(ns['OPEN_INDEX_VAL'])
            ns['High'] = pd.to_numeric(ns['HIGH_INDEX_VAL'])
            ns['Low'] = pd.to_numeric(ns['LOW_INDEX_VAL'])
            ns['Close'] = pd.to_numeric(ns['CLOSE_INDEX_VAL'])
            
            ns = ns[['Open', 'High', 'Low', 'Close']]
            ns = ns[~ns.index.isin(df.index)]
            
            if not ns.empty:
                print("Missing rows added:")
                print(ns)
                df = pd.concat([df, ns]).sort_index()
    except Exception as e:
        print("fetch failed:", e)

print(df.tail(3))
