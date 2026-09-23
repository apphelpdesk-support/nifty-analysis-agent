import json
import random
from datetime import datetime, timedelta

def main():
    data = {}
    today = datetime.now()
    
    # Generate 30 days of history
    for i in range(30):
        # Skip weekends for realism
        date_obj = today - timedelta(days=i)
        if date_obj.weekday() >= 5:
            continue
            
        date_str = date_obj.strftime("%Y-%m-%d")
        
        # Simulate realistic daily conditions
        # In the future, this will be replaced by actual data.load_series()
        trend_opts = ["up_strong", "down_strong", "flat", "volatile"]
        fii_opts = ["buying", "selling", "neutral"]
        opt_opts = ["support", "resistance", "balanced"]
        
        trend = random.choices(trend_opts, weights=[2, 2, 4, 2])[0]
        fii = random.choices(fii_opts, weights=[3, 3, 4])[0]
        opt = random.choices(opt_opts, weights=[3, 3, 4])[0]
        
        score = 0
        if trend == 'up_strong': score += 3
        elif trend == 'down_strong': score -= 3
        elif trend == 'volatile': score -= 1
        
        if fii == 'buying': score += 4
        elif fii == 'selling': score -= 4
        
        if opt == 'support': score += 3
        elif opt == 'resistance': score -= 3
        
        def generate_prediction(base_score, timeframe):
            tf_mod = {"tomorrow": 1.0, "next_week": 1.5, "next_month": 2.5}[timeframe]
            adj_score = base_score * tf_mod
            
            prob = min(85, max(45, 50 + int(abs(adj_score) * 2.5)))
            
            if adj_score >= 5:
                return {"probability": prob, "direction": "UP", "expected_move": f"+{1.2 * tf_mod:.1f}%", "strategy": "Buy Call Options"}
            elif adj_score > 1:
                return {"probability": prob, "direction": "UP", "expected_move": f"+{0.4 * tf_mod:.1f}%", "strategy": "Wait for a dip, then Buy"}
            elif adj_score <= 1 and adj_score >= -1:
                return {"probability": prob, "direction": "FLAT", "expected_move": "~0.0%", "strategy": "Wait & Watch"}
            elif adj_score < -1 and adj_score > -5:
                return {"probability": prob, "direction": "DOWN", "expected_move": f"-{0.5 * tf_mod:.1f}%", "strategy": "Sell on rise"}
            else:
                return {"probability": prob, "direction": "DOWN", "expected_move": f"-{1.5 * tf_mod:.1f}%", "strategy": "Buy Put Options"}
                
        data[date_str] = {
            "trend": trend,
            "fii": fii,
            "options": opt,
            "predictions": {
                "tomorrow": generate_prediction(score, "tomorrow"),
                "next_week": generate_prediction(score, "next_week"),
                "next_month": generate_prediction(score, "next_month")
            }
        }
        
    with open("dashboard_data.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
