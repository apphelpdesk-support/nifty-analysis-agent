import json
import os
import pandas as pd
from datetime import datetime, timedelta

def process_intraday_symbol(symbol_name, db_filename):
    data_file = f"intraday_data_{symbol_name}.json"
    data = {}
    
    # Load 5m data from Fyers Intraday DB
    csv_path = f"data/fyers_db/5/{db_filename}"
    if not os.path.exists(csv_path):
        print(f"Intraday DB {csv_path} missing.")
        return
        
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    
    # Keep up to 1 year of 5m data to balance depth and JSON payload size
    one_year_ago = df.index[-1] - timedelta(days=365)
    df = df[df.index >= one_year_ago]
    
    print(f"[{symbol_name}] Base 5m rows: {len(df)}")
    
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
            
        import pandas_ta as ta
        import math
        tf_df['Return'] = tf_df['Close'].pct_change()
        tf_df.ta.ema(length=20, append=True)
        tf_df.ta.ema(length=5, append=True)
        tf_df.ta.ema(length=9, append=True)
        tf_df.ta.rsi(length=14, append=True)
        tf_df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
        tf_df.ta.atr(length=14, append=True)
        
        # Calculate continuous differentials
        tf_df['EMA5_9_diff'] = tf_df['EMA_5'] - tf_df['EMA_9']
        tf_df['Price_20EMA_diff'] = tf_df['Close'] - tf_df['EMA_20']
        tf_df['Vol_Ratio'] = tf_df['Volume'] / tf_df['Volume'].rolling(20).mean().replace(0, 1)

        # Apply Rolling Z-Score Normalization (prevent lookahead bias)
        rolling_window = 252 # ~ 3 days of 5-min bars
        features_to_normalize = {
            'RSI_14': 'z_rsi',
            'STOCHRSIk_14_14_3_3': 'z_stochrsi',
            'EMA5_9_diff': 'z_ema_diff',
            'Price_20EMA_diff': 'z_price_ema',
            'ATRr_14': 'z_atr',
            'Vol_Ratio': 'z_vol'
        }
        
        for col, z_name in features_to_normalize.items():
            if col in tf_df.columns:
                r_mean = tf_df[col].rolling(rolling_window).mean()
                r_std = tf_df[col].rolling(rolling_window).std().replace(0, 1e-5)
                tf_df[z_name] = (tf_df[col] - r_mean) / r_std
            
            # Keep up to 1 year for higher timeframes too
            one_year_ago = tf_df.index[-1] - timedelta(days=365)
            tf_df = tf_df[tf_df.index >= one_year_ago]
        
        data = {}
        for dt, row in tf_df.iterrows():
            date_str = dt.isoformat()
            signals = {
                "open": row["Open"],
                "high": row["High"],
                "low": row["Low"],
                "close": row["Close"],
                "volume": row["Volume"],
                "daily_return_pct": row.get("Return", 0.0) * 100 if not math.isnan(row.get("Return", 0.0)) else 0.0,
                "z_rsi": round(row.get("z_rsi", 0.0), 3) if not math.isnan(row.get("z_rsi", 0.0)) else 0.0,
                "z_stochrsi": round(row.get("z_stochrsi", 0.0), 3) if not math.isnan(row.get("z_stochrsi", 0.0)) else 0.0,
                "z_ema_diff": round(row.get("z_ema_diff", 0.0), 3) if not math.isnan(row.get("z_ema_diff", 0.0)) else 0.0,
                "z_price_ema": round(row.get("z_price_ema", 0.0), 3) if not math.isnan(row.get("z_price_ema", 0.0)) else 0.0,
                "z_atr": round(row.get("z_atr", 0.0), 3) if not math.isnan(row.get("z_atr", 0.0)) else 0.0,
                "z_vol": round(row.get("z_vol", 0.0), 3) if not math.isnan(row.get("z_vol", 0.0)) else 0.0,
                "z_vix": 0.0,
                "z_bn_rel": 0.0
            }
            data[date_str] = {"signals": signals}
            
        with open(data_file, "w") as f:
            json.dump(data, f)
        print(f"[{symbol_name}] Successfully exported {data_file} ({tf_str}m)")

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
