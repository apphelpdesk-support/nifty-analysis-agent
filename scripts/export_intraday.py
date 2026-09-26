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
                "volume": row["Volume"]
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
