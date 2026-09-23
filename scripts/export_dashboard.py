import json
import random
import os
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
    if os.path.exists(data_file):
        try:
            with open(data_file, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    # Fetch last 5 days of Nifty to catch up
    nifty = yf.Ticker("^NSEI")
    df = nifty.history(period="10d")
    
    # Try fetching real FII data
    fii_df = None
    if NSELIB_AVAILABLE:
        try:
            fii_df = capital_market.fii_dii_trading_activity()
        except Exception as e:
            print(f"Warning: nselib FII fetch failed - {e}")
            
    trading_days = df.index[-5:]
    
    for date_obj in trading_days:
        date_str = date_obj.strftime("%Y-%m-%d")
        
        # Keep existing if it's there, but we can overwrite if we have better data
        existing = data.get(date_str, {})
        fii = existing.get("fii", "neutral")
        
        close = df.loc[date_obj, "Close"]
        open_price = df.loc[date_obj, "Open"]
        change_pct = ((close - open_price) / open_price) * 100
        
        if change_pct > 0.8: trend = "up_strong"
        elif change_pct < -0.8: trend = "down_strong"
        elif abs(change_pct) <= 0.3: trend = "flat"
        else: trend = "volatile"
            
        # Try exact FII match
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
            except Exception as e:
                pass
                
        # Proxy Fallback
        if fii == "neutral":
            try:
                # Use standard iloc instead of datetime index for previous close
                idx = df.index.get_loc(date_obj)
                if idx > 0:
                    prev_close = df["Close"].iloc[idx - 1]
                    gap_pct = ((open_price - prev_close) / prev_close) * 100
                    if gap_pct > 0.4 and change_pct > 0: fii = "buying"
                    elif gap_pct < -0.4 and change_pct < 0: fii = "selling"
            except:
                pass

        opt_opts = ["support", "resistance", "balanced"]
        opt = existing.get("options", random.choice(opt_opts))
        
        score = 0
        if trend == 'up_strong': score += 3
        elif trend == 'down_strong': score -= 3
        elif trend == 'volatile': score -= 1
        
        if fii == 'buying': score += 4
        elif fii == 'selling': score -= 4
        
        if opt == 'support': score += 3
        elif opt == 'resistance': score -= 3
        
        def gen_pred(b_score, tf):
            tf_mod = {"tomorrow": 1.0, "next_week": 1.5, "next_month": 2.5}[tf]
            adj_score = b_score * tf_mod
            prob = min(85, max(45, 50 + int(abs(adj_score) * 2.5)))
            
            if adj_score >= 5: return {"probability": prob, "direction": "UP", "expected_move": f"+{1.2 * tf_mod:.1f}%", "strategy": "Buy Call Options"}
            elif adj_score > 1: return {"probability": prob, "direction": "UP", "expected_move": f"+{0.4 * tf_mod:.1f}%", "strategy": "Wait for a dip, then Buy"}
            elif adj_score <= 1 and adj_score >= -1: return {"probability": prob, "direction": "FLAT", "expected_move": "~0.0%", "strategy": "Wait & Watch"}
            elif adj_score < -1 and adj_score > -5: return {"probability": prob, "direction": "DOWN", "expected_move": f"-{0.5 * tf_mod:.1f}%", "strategy": "Sell on rise"}
            else: return {"probability": prob, "direction": "DOWN", "expected_move": f"-{1.5 * tf_mod:.1f}%", "strategy": "Buy Put Options"}
                
        data[date_str] = {
            "trend": trend,
            "fii": fii,
            "options": opt,
            "predictions": {
                "tomorrow": gen_pred(score, "tomorrow"),
                "next_week": gen_pred(score, "next_week"),
                "next_month": gen_pred(score, "next_month")
            }
        }
        
    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Updated data successfully. Total entries: {len(data)}")

if __name__ == "__main__":
    main()
