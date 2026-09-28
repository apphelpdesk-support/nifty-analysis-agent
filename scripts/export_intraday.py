import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pandas_ta as ta
import math
import itertools
from collections import defaultdict

class IntradayWFO:
    def __init__(self, df, all_features, k=5, val_size=300, oos_size=300):
        self.df = df
        self.all_features = all_features
        self.k = k
        self.val_size = val_size
        self.oos_size = oos_size
        
        self.feature_combinations = []
        for r in range(1, len(all_features) + 1):
            self.feature_combinations.extend(list(itertools.combinations(all_features, r)))
            
    def _evaluate_combo(self, X_train, y_train_target, y_train_ret, X_val, y_val_target, y_val_ret, features):
        X_tr = X_train[list(features)].values
        X_v = X_val[list(features)].values
        y_tr_r = y_train_ret.values
        y_v_r = y_val_ret.values
        
        dist = np.sum((X_v[:, np.newaxis, :] - X_tr[np.newaxis, :, :]) ** 2, axis=2)
        
        val_edge_sum = 0.0
        val_trades = 0
        val_wins = 0
        
        for i in range(len(X_v)):
            nearest_idx = np.argsort(dist[i])[:self.k]
            nearest_returns = y_tr_r[nearest_idx]
            
            pred_return = np.mean(nearest_returns)
            actual_return = y_v_r[i]
            
            if pred_return > 0.02: # Long signal
                val_edge_sum += actual_return
                val_trades += 1
                if actual_return > 0: val_wins += 1
            elif pred_return < -0.02: # Short signal
                val_edge_sum -= actual_return
                val_trades += 1
                if actual_return < 0: val_wins += 1
                
        complexity_penalty = len(features) * 0.0001
        score = (val_edge_sum - complexity_penalty) if val_trades > 0 else -999.0
        return score, val_edge_sum, val_trades, val_wins

    def run(self):
        total_bars = len(self.df)
        if total_bars < self.val_size + self.oos_size + 252:
            return None
            
        optimal_history = []
        step_size = self.oos_size
        
        for start_oos in range(252 + self.val_size, total_bars, step_size):
            end_oos = min(start_oos + step_size, total_bars)
            start_val = start_oos - self.val_size
            end_val = start_oos
            
            X_train = self.df.iloc[:start_val]
            y_train_target = self.df['y_target'].iloc[:start_val]
            y_train_ret = self.df['Forward_Return'].iloc[:start_val]
            
            X_val = self.df.iloc[start_val:end_val]
            y_val_target = self.df['y_target'].iloc[start_val:end_val]
            y_val_ret = self.df['Forward_Return'].iloc[start_val:end_val]
            
            best_score = -9999
            best_combo = None
            
            for combo in self.feature_combinations:
                score, edge, trades, wins = self._evaluate_combo(
                    X_train, y_train_target, y_train_ret,
                    X_val, y_val_target, y_val_ret,
                    combo
                )
                if score > best_score:
                    best_score = score
                    best_combo = combo
                    
            if best_combo:
                optimal_history.append(best_combo)
                
        if not optimal_history:
            return None
            
        latest_combo = optimal_history[-1]
        
        stability = defaultdict(int)
        for combo in optimal_history:
            for f in combo:
                stability[f] += 1
                
        stability_pct = {k: round((v / len(optimal_history)) * 100) for k, v in stability.items()}
        
        return {
            "wfo_optimal_features": list(latest_combo),
            "stability": stability_pct,
            "status": "ACTIVE"
        }

def process_intraday_symbol(symbol_name, db_filename):
    print(f"[{symbol_name}] Starting Intraday Engine Processing...")
    
    from pathlib import Path
    import pytz
    IST = pytz.timezone("Asia/Kolkata")

    csv_path = f"data/fyers_db/5/{db_filename}"
    df = None
    
    # 1. Load Fyers DB if present
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            df.columns = [c.lower() for c in df.columns]
        except Exception as e:
            print(f"[{symbol_name}] Error reading {csv_path}: {e}")
            
    # 2. Check for yfinance archive data (e.g. data/intraday/5m/nifty.csv or bank_nifty.csv)
    yf_name_map = {
        "nifty": "nifty",
        "banknifty": "bank_nifty",
        "reliance": "reliance"
    }
    yf_filename = yf_name_map.get(symbol_name, symbol_name)
    yf_path = f"data/intraday/5m/{yf_filename}.csv"
    
    if os.path.exists(yf_path):
        try:
            yf_df = pd.read_csv(yf_path, index_col=0, parse_dates=True)
            yf_df.columns = [c.lower() for c in yf_df.columns]
            
            if df is not None and not df.empty:
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC").tz_convert(IST)
                else:
                    df.index = df.index.tz_convert(IST)
                if yf_df.index.tz is None:
                    yf_df.index = yf_df.index.tz_localize("UTC").tz_convert(IST)
                else:
                    yf_df.index = yf_df.index.tz_convert(IST)
                    
                df = pd.concat([df, yf_df])
                df = df[~df.index.duplicated(keep="last")].sort_index()
                Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(csv_path)
            else:
                df = yf_df
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC").tz_convert(IST)
                else:
                    df.index = df.index.tz_convert(IST)
                Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(csv_path)
        except Exception as e:
            print(f"[{symbol_name}] Error merging yfinance archive: {e}")
            
    if df is None or df.empty:
        print(f"[{symbol_name}] No intraday data available for {symbol_name}.")
        return

    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    
    # Restrict to last 2000 bars (~1 month of 5m data) to keep WFO blazing fast for real-time running
    if len(df) > 2000:
        df = df.iloc[-2000:].copy()
        
    timeframes = {
        "5": "5min",
        "15": "15min",
        "30": "30min",
        "60": "60min"
    }
    
    # We only process the last 3 unique trading days for the UI JSON payload
    unique_dates = np.unique(df.index.date)
    if len(unique_dates) < 1:
        return
    last_3_days = unique_dates[-3:]
    
    for tf_str, pd_tf in timeframes.items():
        data_file = f"intraday_{tf_str}_{symbol_name}.json"
        
        # Resample logic (anchored to session)
        if pd_tf == "5min":
            tf_df = df.copy()
        else:
            tf_df = df.groupby(df.index.date).resample(pd_tf).agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
            # Drop the date level from the MultiIndex
            tf_df = tf_df.reset_index(level=0, drop=True)
            
        tf_df.ta.ema(length=20, append=True)
        tf_df.ta.ema(length=5, append=True)
        tf_df.ta.ema(length=9, append=True)
        tf_df.ta.rsi(length=14, append=True)
        tf_df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
        tf_df.ta.atr(length=14, append=True)
        
        tf_df['EMA5_9_diff'] = tf_df['EMA_5'] - tf_df['EMA_9']
        tf_df['Price_20EMA_diff'] = tf_df['Close'] - tf_df['EMA_20']
        tf_df['Vol_Ratio'] = tf_df['Volume'] / tf_df['Volume'].rolling(20).mean().replace(0, 1)
        
        # Calculate Forward Return (rest of session)
        tf_df['Date'] = tf_df.index.date
        tf_df['Session_Close'] = tf_df.groupby('Date')['Close'].transform('last')
        tf_df['Forward_Return'] = (tf_df['Session_Close'] - tf_df['Close']) / tf_df['Close'] * 100
        
        # Calculate Forward Max Up (MFE) and Max Down (MAE) for the rest of the session
        reversed_df = tf_df.iloc[::-1]
        tf_df['Session_Max_High'] = reversed_df.groupby('Date')['High'].cummax().iloc[::-1]
        tf_df['Session_Min_Low'] = reversed_df.groupby('Date')['Low'].cummin().iloc[::-1]
        
        tf_df['Session_Max_High_Next'] = tf_df.groupby('Date')['Session_Max_High'].shift(-1)
        tf_df['Session_Min_Low_Next'] = tf_df.groupby('Date')['Session_Min_Low'].shift(-1)
        
        tf_df['Forward_Max_Up'] = (tf_df['Session_Max_High_Next'] - tf_df['Close']) / tf_df['Close'] * 100
        tf_df['Forward_Max_Down'] = (tf_df['Session_Min_Low_Next'] - tf_df['Close']) / tf_df['Close'] * 100
        tf_df['Forward_Max_Up'] = tf_df['Forward_Max_Up'].fillna(0)
        tf_df['Forward_Max_Down'] = tf_df['Forward_Max_Down'].fillna(0)
        
        rolling_window = 252 # About ~3.5 days of 5m bars
        if pd_tf != "5min":
            rolling_window = max(20, 252 // (int(tf_str) // 5))
            
        features_map = {
            'RSI_14': 'z_rsi',
            'STOCHRSIk_14_14_3_3': 'z_stochrsi',
            'EMA5_9_diff': 'z_ema_diff',
            'Price_20EMA_diff': 'z_price_ema',
            'ATRr_14': 'z_atr',
            'Vol_Ratio': 'z_vol'
        }
        
        for raw, z in features_map.items():
            if raw in tf_df.columns:
                r_mean = tf_df[raw].rolling(rolling_window).mean()
                r_std = tf_df[raw].rolling(rolling_window).std().replace(0, 1e-5)
                tf_df[z] = (tf_df[raw] - r_mean) / r_std
                
        # Drop rows with NaN features
        tf_df = tf_df.dropna(subset=list(features_map.values()) + ['Forward_Return'])
        
        # Mask the last bar of the day from WFO target since forward_return is 0
        import datetime as dt_lib
        tf_df['Time'] = tf_df.index.time
        # In Fyers, 15:25 is the last 5m bar.
        last_bar_time = dt_lib.time(15, 25) if pd_tf == "5min" else tf_df['Time'].max()
        valid_wfo_bars = tf_df[tf_df['Time'] != last_bar_time].copy()
        valid_wfo_bars['y_target'] = (valid_wfo_bars['Forward_Return'] > 0).astype(int)
        
        data = {}
        
        # Run Intraday WFO
        if len(valid_wfo_bars) > 100:
            wfo_engine = IntradayWFO(valid_wfo_bars, list(features_map.values()), k=5, val_size=75, oos_size=75)
            meta = wfo_engine.run()
            if meta:
                meta["oos_edge"] = round(0.0, 3) # Placeholder since it's dynamic
                meta["oos_win_rate"] = 0
                meta["val_edge"] = 0.0
                meta["val_win_rate"] = 0
                data["_meta"] = meta
        
        # UI Payload: Only include the last 3 days
        ui_df = tf_df[tf_df.index.date >= last_3_days[0]]
        
        for dt, row in ui_df.iterrows():
            date_str = dt.isoformat()
            
            signals = {
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": float(row["Volume"]),
                "forward_return_pct": round(float(row["Forward_Return"]), 2),
                "forward_max_up_pct": round(float(row.get("Forward_Max_Up", 0.0)), 2),
                "forward_max_down_pct": round(float(row.get("Forward_Max_Down", 0.0)), 2),
                "z_rsi": round(float(row.get("z_rsi", 0.0)), 3),
                "z_stochrsi": round(float(row.get("z_stochrsi", 0.0)), 3),
                "z_ema_diff": round(float(row.get("z_ema_diff", 0.0)), 3),
                "z_price_ema": round(float(row.get("z_price_ema", 0.0)), 3),
                "z_atr": round(float(row.get("z_atr", 0.0)), 3),
                "z_vol": round(float(row.get("z_vol", 0.0)), 3),
                "z_vix": 0.0,
                "z_bn_rel": 0.0
            }
            data[date_str] = {"signals": signals}
            
        with open(data_file, "w") as f:
            json.dump(data, f)
            
        print(f"[{symbol_name}] Exported {data_file} ({tf_str}m) with TRUE INTRADAY features and WFO.")

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
