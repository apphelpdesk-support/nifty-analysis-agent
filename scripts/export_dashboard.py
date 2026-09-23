import json
import os
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
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

    # --- NEW: Fetch missing recent dates from NSE directly if yfinance is lagging ---
    if NSELIB_AVAILABLE and not df.empty:
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
                        df = pd.concat([df, ns]).sort_index()
                        print(f"Appended {len(ns)} missing days from nselib.")
            except Exception as e:
                print("Fallback nselib fetch failed:", e)

    df["Return"] = df["Close"].pct_change()
    
    df.ta.ema(length=20, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.supertrend(length=7, multiplier=3.0, append=True)
    
    fii_df = None
    if NSELIB_AVAILABLE:
        try:
            fii_df = capital_market.fii_dii_trading_activity()
        except Exception as e:
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
        
        signals = {
            "close": round(close, 2),
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

        # FII logic
        if fii_df is not None:
            try:
                date_formatted = date_obj.strftime("%d-%b-%Y")
                fii_row = fii_df[(fii_df['Date'] == date_formatted) & (fii_df['Category'].str.contains('FII', na=False))]
                if not fii_row.empty:
                    net_val_str = str(fii_row['Net Value'].iloc[0]).replace(',', '')
                    net_value = float(net_val_str)
                    if net_value > 500: fii = "buying"
                    elif net_value < -500: fii = "selling"
            except:
                pass
                
        if fii == "neutral":
            try:
                if idx_long > 0:
                    prev_close = df["Close"].iloc[idx_long - 1]
                    open_price = row["Open"]
                    gap_pct = ((open_price - prev_close) / prev_close) * 100
                    change_pct = ((close - open_price) / open_price) * 100
                    if gap_pct > 0.4 and change_pct > 0: fii = "buying"
                    elif gap_pct < -0.4 and change_pct < 0: fii = "selling"
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
