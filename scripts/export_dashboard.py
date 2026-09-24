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
    df.ta.ema(length=5, append=True)
    df.ta.ema(length=9, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.supertrend(length=7, multiplier=3.0, append=True)
    

    # Fetch Moneycontrol FII data
    mc_fii_dict = {}
    try:
        url = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/index.php"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Moneycontrol FII fetch status: {response.status_code}")
        matches = re.findall(r'\{"date":"([^"]+)".*?"fiiCM":"([^"]+)"', response.text)
        if not matches:
            print("No matches found in FII data!")
        for d, val in matches:
            mc_fii_dict[d] = float(val.replace(',', ''))
    except Exception as e:
        print(f"Moneycontrol FII fetch failed: {e}")
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
    global_options_max_pain = None
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

        # Find Intraday Support (Max Put OI strictly within 300 pts below current price)
        puts_below = [x for x in pe_data if (current_price - 300) <= x['strikePrice'] < current_price]
        if puts_below:
            max_put = max(puts_below, key=lambda x: x['openInterest'])
            global_options_support = max_put['strikePrice']

        # Find Intraday Resistance (Max Call OI strictly within 300 pts above current price)
        calls_above = [x for x in ce_data if current_price < x['strikePrice'] <= (current_price + 300)]
        if calls_above:
            max_call = max(calls_above, key=lambda x: x['openInterest'])
            global_options_resistance = max_call['strikePrice']

        # Calculate Intraday Option Momentum (Delta OI)
        # Sum of changeinOpenInterest for strikes within +/- 500 points
        put_delta = sum([x.get('changeinOpenInterest', 0) for x in pe_data if abs(x['strikePrice'] - current_price) <= 500])
        call_delta = sum([x.get('changeinOpenInterest', 0) for x in ce_data if abs(x['strikePrice'] - current_price) <= 500])
        
        global_options_momentum = None
        if call_delta > 0 or put_delta > 0:
            if put_delta > call_delta:
                global_options_momentum = "bullish"
            else:
                global_options_momentum = "bearish"

        # Calculate Max Pain
        all_strikes = sorted(list(set([x['strikePrice'] for x in pe_data + ce_data])))
        check_strikes = [s for s in all_strikes if current_price - 1000 <= s <= current_price + 1000]
        
        min_loss = float('inf')
        for expiry_price in check_strikes:
            total_loss = 0
            for ce in ce_data:
                if expiry_price > ce['strikePrice']:
                    total_loss += (expiry_price - ce['strikePrice']) * ce['openInterest']
            for pe in pe_data:
                if expiry_price < pe['strikePrice']:
                    total_loss += (pe['strikePrice'] - expiry_price) * pe['openInterest']
            if total_loss < min_loss:
                min_loss = total_loss
                global_options_max_pain = expiry_price
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
        ema5 = float(row.get("EMA_5", close))
        ema9 = float(row.get("EMA_9", close))
        rsi = float(row.get("RSI_14", 50))
        stochrsi_k = float(row.get("STOCHRSIk_14_14_3_3", 50))
        stochrsi_d = float(row.get("STOCHRSId_14_14_3_3", 50))
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
        options_max_pain = global_options_max_pain if date_obj == trading_days[-1] else None
        options_momentum = global_options_momentum if date_obj == trading_days[-1] else None
        signals = {

        
            "close": round(close, 2),

        
            "high": round(high_val, 2),

        
            "low": round(low_val, 2),
            "daily_return_pct": round(row.get("Return", 0) * 100, 2),
        "options_support": options_support,
        "options_resistance": options_resistance,
        "options_max_pain": options_max_pain,
        "options_momentum": options_momentum,

        
            "ema20_signal": "bullish" if close > ema20 else "bearish",
            "ema200_signal": "bullish" if close > ema200 else "bearish",
            "ema20_diff_pct": round(((close - ema20) / ema20) * 100, 2),
            "ema200_diff_pct": round(((close - ema200) / ema200) * 100, 2),
            "ema5_signal": "bullish" if ema5 > ema9 else "bearish",
            "rsi_value": round(rsi, 2),
            "stochrsi_k": round(stochrsi_k, 2),
            "stochrsi_d": round(stochrsi_d, 2),
            "stochrsi_signal": "overbought" if stochrsi_k > 80 else ("oversold" if stochrsi_k < 20 else ("bullish crossover" if stochrsi_k > stochrsi_d else "bearish crossover")),
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
        fii_value = None
        if date_str in mc_fii_dict:
            net_val = mc_fii_dict[date_str]
            fii_value = net_val
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
            "fii_value": fii_value,
            "signals": signals
        }
        
    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
