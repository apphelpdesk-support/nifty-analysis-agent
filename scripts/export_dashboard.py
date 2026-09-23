import json
import os
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import yfinance as yf

try:
    from nselib import capital_market
    NSELIB_AVAILABLE = True
except ImportError:
    NSELIB_AVAILABLE = False

def main():
    data_file = "dashboard_data.json"
    data = {}
    if os.path.exists(data_file):
        try:
            with open(data_file, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    # Fetch last 300 days for 200 EMA calculation
    nifty = yf.Ticker("^NSEI")
    df = nifty.history(period="300d")
    
    # Calculate Indicators
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
            print(f"Warning: nselib fetch failed - {e}")

    # Process the last 5 days
    trading_days = df.index[-5:]
    
    for date_obj in trading_days:
        date_str = date_obj.strftime("%Y-%m-%d")
        existing = data.get(date_str, {})
        fii = existing.get("fii", "neutral")
        
        row = df.loc[date_obj]
        
        # Indicator Values
        close = float(row["Close"])
        ema20 = float(row.get("EMA_20", close))
        ema200 = float(row.get("EMA_200", close))
        rsi = float(row.get("RSI_14", 50))
        
        macd = float(row.get("MACD_12_26_9", 0))
        macd_signal = float(row.get("MACDs_12_26_9", 0))
        macd_hist = float(row.get("MACDh_12_26_9", 0))
        
        st_dir = row.get("SUPERTd_7_3.0", 0)
        
        # Determine signals for frontend
        signals = {
            "close": round(close, 2),
            "ema20_signal": "bullish" if close > ema20 else "bearish",
            "ema200_signal": "bullish" if close > ema200 else "bearish",
            "rsi_value": round(rsi, 2),
            "rsi_signal": "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral"),
            "macd_signal": "bullish" if macd > macd_signal else "bearish",
            "supertrend_signal": "bullish" if st_dir == 1 else "bearish"
        }

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
                    else: fii = "neutral"
            except:
                pass
                
        # Proxy Fallback
        if fii == "neutral":
            try:
                idx = df.index.get_loc(date_obj)
                if idx > 0:
                    prev_close = df["Close"].iloc[idx - 1]
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
