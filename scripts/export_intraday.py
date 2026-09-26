import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pandas_ta as ta
import math

def process_intraday_symbol(symbol_name, db_filename):
    data_file = f"intraday_data_{symbol_name}.json"
    data = {}
    
    # Load Base Daily Data for EOD context
    daily_csv = f"data/historical/{symbol_name}.csv"
    if not os.path.exists(daily_csv):
        print(f"[{symbol_name}] Daily DB missing. Skipping Intraday.")
        return
        
    daily_df = pd.read_csv(daily_csv, index_col=0, parse_dates=True)
    daily_df = daily_df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    
    # Load 5m data from Fyers Intraday DB
    csv_path = f"data/fyers_db/5/{db_filename}"
    if not os.path.exists(csv_path):
        print(f"[{symbol_name}] Intraday DB {csv_path} missing.")
        return
        
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    
    # We only process the last 3 unique trading days to keep the script fast and the UI clean
    unique_dates = np.unique(df.index.date)
    if len(unique_dates) < 1:
        return
        
    last_3_days = unique_dates[-3:]
    df = df[df.index.date >= last_3_days[0]]
    
    print(f"[{symbol_name}] Base 5m rows for last 3 days: {len(df)}")
    
    timeframes = {
        "5": "5min",
        "15": "15min",
        "30": "30min",
        "60": "60min"
    }
    
    for tf_str, pd_tf in timeframes.items():
        data_file = f"intraday_{tf_str}_{symbol_name}.json"
        
        # Resample logic
        if pd_tf == "5min":
            tf_df = df.copy()
        else:
            tf_df = df.resample(pd_tf).agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
            
        data = {}
        
        # Inject WFO metadata from historical run if available
        try:
            hist_json = f"dashboard_data.json" if symbol_name == "nifty" else f"dashboard_data_{symbol_name}.json"
            if os.path.exists(hist_json):
                with open(hist_json, 'r') as f:
                    hist_data = json.load(f)
                    if "_meta" in hist_data:
                        data["_meta"] = hist_data["_meta"]
        except Exception as e:
            pass
            
        # Iterate over each target intraday bar
        for dt, _ in tf_df.iterrows():
            trade_day = dt.date()
            
            # Daily data up to the PREVIOUS day
            daily_up_to_prev = daily_df[daily_df.index.date < trade_day].copy()
            if len(daily_up_to_prev) < 260:
                continue
                
            # Intraday bars exactly up to this timestamp for this day
            day_bars = df[(df.index.date == trade_day) & (df.index <= dt)]
            if len(day_bars) == 0:
                continue
                
            day_open = float(day_bars['Open'].iloc[0])
            day_high = float(day_bars['High'].max())
            day_low = float(day_bars['Low'].min())
            day_close = float(day_bars['Close'].iloc[-1])
            day_vol = float(day_bars['Volume'].sum())
            
            synth_row = pd.Series({
                'Open': day_open,
                'High': day_high,
                'Low': day_low,
                'Close': day_close,
                'Volume': day_vol
            }, name=dt)
            
            # Optimize: Only use the last 300 daily rows to calculate indicators quickly
            subset_daily = daily_up_to_prev.iloc[-300:].copy()
            subset_daily.loc[dt] = synth_row
            
            # Calculate TA
            subset_daily['Return'] = subset_daily['Close'].pct_change()
            subset_daily.ta.ema(length=20, append=True)
            subset_daily.ta.ema(length=5, append=True)
            subset_daily.ta.ema(length=9, append=True)
            subset_daily.ta.rsi(length=14, append=True)
            subset_daily.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
            subset_daily.ta.atr(length=14, append=True)
            
            subset_daily['EMA5_9_diff'] = subset_daily['EMA_5'] - subset_daily['EMA_9']
            subset_daily['Price_20EMA_diff'] = subset_daily['Close'] - subset_daily['EMA_20']
            subset_daily['Vol_Ratio'] = subset_daily['Volume'] / subset_daily['Volume'].rolling(20).mean().replace(0, 1)
            
            rolling_window = 252
            features_to_normalize = {
                'RSI_14': 'z_rsi',
                'STOCHRSIk_14_14_3_3': 'z_stochrsi',
                'EMA5_9_diff': 'z_ema_diff',
                'Price_20EMA_diff': 'z_price_ema',
                'ATRr_14': 'z_atr',
                'Vol_Ratio': 'z_vol'
            }
            
            for col, z_name in features_to_normalize.items():
                if col in subset_daily.columns:
                    r_mean = subset_daily[col].rolling(rolling_window).mean()
                    r_std = subset_daily[col].rolling(rolling_window).std().replace(0, 1e-5)
                    subset_daily[z_name] = (subset_daily[col] - r_mean) / r_std
                    
            final_state = subset_daily.iloc[-1]
            
            date_str = dt.isoformat()
            signals = {
                "open": round(float(final_state["Open"]), 2),
                "high": round(float(final_state["High"]), 2),
                "low": round(float(final_state["Low"]), 2),
                "close": round(float(final_state["Close"]), 2),
                "volume": float(final_state["Volume"]),
                "daily_return_pct": round(float(final_state.get("Return", 0.0) * 100), 2) if not math.isnan(final_state.get("Return", 0.0)) else 0.0,
                "z_rsi": round(float(final_state.get("z_rsi", 0.0)), 3) if not math.isnan(final_state.get("z_rsi", 0.0)) else 0.0,
                "z_stochrsi": round(float(final_state.get("z_stochrsi", 0.0)), 3) if not math.isnan(final_state.get("z_stochrsi", 0.0)) else 0.0,
                "z_ema_diff": round(float(final_state.get("z_ema_diff", 0.0)), 3) if not math.isnan(final_state.get("z_ema_diff", 0.0)) else 0.0,
                "z_price_ema": round(float(final_state.get("z_price_ema", 0.0)), 3) if not math.isnan(final_state.get("z_price_ema", 0.0)) else 0.0,
                "z_atr": round(float(final_state.get("z_atr", 0.0)), 3) if not math.isnan(final_state.get("z_atr", 0.0)) else 0.0,
                "z_vol": round(float(final_state.get("z_vol", 0.0)), 3) if not math.isnan(final_state.get("z_vol", 0.0)) else 0.0,
                "z_vix": 0.0,
                "z_bn_rel": 0.0
            }
            data[date_str] = {"signals": signals}
            
        with open(data_file, "w") as f:
            json.dump(data, f)
        print(f"[{symbol_name}] Successfully exported {data_file} ({tf_str}m) with Synthetic Daily matching.")
        
def main():
    instruments = [
        ("nifty", "NSE_NIFTY50-INDEX.csv"),
        ("banknifty", "NSE_NIFTYBANK-INDEX.csv"),
        ("reliance", "NSE_RELIANCE-EQ.csv")
    ]
    
    for sym, filename in instruments:
        process_intraday_symbol(sym, filename)

if __name__ == "__main__":
    main()
