import json
import os
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
import yfinance
import requests
import re
import yfinance as yf

try:
    from nselib import capital_market
    NSELIB_AVAILABLE = True
except ImportError:
    NSELIB_AVAILABLE = False

def main():
    data_file = "dashboard_data.json"
    data = {}

    nifty = yf.Ticker("^NSEI")
    df = nifty.history(period="10y")

    # --- NEW: Fetch missing recent dates using jugaad-data (more reliable) ---
    try:
        from jugaad_data.nse import index_df
        from datetime import datetime, timedelta
        import pandas as pd
        
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=30)
        ns = index_df(symbol="NIFTY 50", from_date=from_date, to_date=to_date)
        
        if not ns.empty:
            ns['Date'] = pd.to_datetime(ns['HistoricalDate'])
            ns = ns.set_index('Date')
            ns = ns.sort_index()
            ns.index = ns.index.tz_localize('Asia/Kolkata')
            
            ns['Open'] = pd.to_numeric(ns['OPEN'])
            ns['High'] = pd.to_numeric(ns['HIGH'])
            ns['Low'] = pd.to_numeric(ns['LOW'])
            ns['Close'] = pd.to_numeric(ns['CLOSE'])
            ns = ns[['Open', 'High', 'Low', 'Close']]
            
            # Find which dates from ns are missing in df
            missing = ns[~ns.index.isin(df.index)]
            if not missing.empty:
                df = pd.concat([df, missing]).sort_index()
                print(f"Appended {len(missing)} missing days from jugaad_data.")
    except Exception as e:
        print("Fallback jugaad_data fetch failed:", e)


    df["Return"] = df["Close"].pct_change()
    
    df.ta.ema(length=20, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.supertrend(length=7, multiplier=3.0, append=True)
    

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

    fii_df = None
    if NSELIB_AVAILABLE:
        try:
            fii_df = capital_market.fii_dii_trading_activity()
        except Exception as e:
            pass

    # Fetch Options Data for Support and Resistance globally (only valid for current time)
    global_options_support = None
    global_options_resistance = None
    try:
        from jugaad_data.nse import NSELive
        n = NSELive()
        oc = n.index_option_chain("NIFTY")

        # Get current price
        current_price = oc['records']['underlyingValue']

        # Calculate Support and Resistance from Option Chain (Max OI)
        pe_data = []
        ce_data = []
        for item in oc['records']['data']:
            if 'PE' in item:
                pe_data.append(item['PE'])
            if 'CE' in item:
                ce_data.append(item['CE'])

        # Find Support (Max Put OI below current price)
        puts_below = [x for x in pe_data if x['strikePrice'] < current_price]
        if puts_below:
            max_put = max(puts_below, key=lambda x: x['openInterest'])
            global_options_support = max_put['strikePrice']

        # Find Resistance (Max Call OI above current price)
        calls_above = [x for x in ce_data if x['strikePrice'] > current_price]
        if calls_above:
            max_call = max(calls_above, key=lambda x: x['openInterest'])
            global_options_resistance = max_call['strikePrice']
    except Exception as e:
        print(f"Option Chain fetch failed: {e}")
        pass

    # Process all dates where we have at least 200 days of history
    trading_days = df.index[200:]
    returns_arr = df['Return'].values
    
    for date_obj in trading_days:
        date_str = date_obj.strftime("%Y-%m-%d")
        fii = "neutral"
        row = df.loc[date_obj]
        
        close = float(row["Close"])
        ema20 = float(row.get("EMA_20", close))
        ema200 = float(row.get("EMA_200", close))
        rsi = float(row.get("RSI_14", 50))
        macd = float(row.get("MACD_12_26_9", 0))
        macd_signal = float(row.get("MACDs_12_26_9", 0))
        st_dir = row.get("SUPERTd_7_3.0", 0)
        
        import math

        
        high_val = float(row.get("High", close))

        
        if math.isnan(high_val): high_val = close

        
        low_val = float(row.get("Low", close))

        
        if math.isnan(low_val): low_val = close

        
        

        
        # For historical dates, we don't have historical option chain, so we apply the live one (or None).
        # A more advanced script would only use this for the latest day.
        options_support = global_options_support if date_obj == trading_days[-1] else None
        options_resistance = global_options_resistance if date_obj == trading_days[-1] else None
        signals = {

        
            "close": round(close, 2),

        
            "high": round(high_val, 2),

        
            "low": round(low_val, 2),
        "options_support": options_support,
        "options_resistance": options_resistance,

        
            "ema20_signal": "bullish" if close > ema20 else "bearish",
            "ema200_signal": "bullish" if close > ema200 else "bearish",
            "ema20_diff_pct": round(((close - ema20) / ema20) * 100, 2),
            "ema200_diff_pct": round(((close - ema200) / ema200) * 100, 2),
            "rsi_value": round(rsi, 2),
            "rsi_signal": "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral"),
            "macd_signal": "bullish" if macd > macd_signal else "bearish",
            "supertrend_signal": "bullish" if st_dir == 1 else "bearish"
        }

        


        idx_long = df.index.get_loc(date_obj)
        if idx_long >= 15:
            current_returns = returns_arr[idx_long-4:idx_long+1]
            search_space = returns_arr[:idx_long - 5]
            if len(search_space) >= 5:
                hist_windows = np.lib.stride_tricks.sliding_window_view(search_space, window_shape=5)
                diffs = hist_windows - current_returns
                dists = np.sum(diffs**2, axis=1)
                best_window_idx = np.argmin(dists)
                best_match_idx = best_window_idx + 4 # because window ends at index + 4
                
                analogue_date_obj = df.index[best_match_idx]
                analogue_date_str = analogue_date_obj.strftime("%d %b %Y")
                next_day_ret = returns_arr[best_match_idx + 1]
                next_day_dir = "UP" if next_day_ret > 0 else "DOWN"
                signals["analogue_match"] = f"Similar to {analogue_date_str} (Next day went {next_day_dir})"
            else:
                signals["analogue_match"] = "No match found"
        else:
            signals["analogue_match"] = "Not enough data"


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
                    if gap_pct > 0.15 and change_pct > -0.2: fii = "buying"
                    elif gap_pct < -0.15 and change_pct < 0.2: fii = "selling"
            except:
                pass

        data[date_str] = {
            "fii": fii,
            "signals": signals
        }
        
    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
