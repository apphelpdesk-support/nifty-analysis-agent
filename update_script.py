import json

path = 'scripts/export_dashboard.py'
with open(path, 'r') as f:
    content = f.read()

content = content.replace(
    'df = nifty.history(period="300d")',
    'df = nifty.history(period="10y")\n    df[\"Return\"] = df[\"Close\"].pct_change()'
)
content = content.replace(
    'period="300d"',
    'period="10y"'
)
content = content.replace(
    '# Fetch last 300 days for 200 EMA calculation',
    '# Fetch last 10 years for historical analogue matching and 200 EMA calculation'
)

new_code = '''            "macd_signal": "bullish" if macd > macd_signal else "bearish",
            "supertrend_signal": "bullish" if st_dir == 1 else "bearish"
        }

        # Historical Analogue Match (closest 5-day return sequence)
        idx_long = df.index.get_loc(date_obj)
        analogue_val = "Not enough data"
        if idx_long >= 5:
            current_returns = df['Return'].iloc[idx_long-4:idx_long+1].values
            best_dist = float('inf')
            best_match_idx = -1
            
            # Loop over all history, excluding the immediate surrounding of the current date
            for i in range(5, idx_long - 5):
                hist_returns = df['Return'].iloc[i-4:i+1].values
                dist = sum((current_returns - hist_returns) ** 2)
                if dist < best_dist:
                    best_dist = dist
                    best_match_idx = i
                    
            if best_match_idx != -1:
                analogue_date_obj = df.index[best_match_idx]
                analogue_date_str = analogue_date_obj.strftime("%d %b %Y")
                # Find what happened the day AFTER the analogue
                next_day_ret = df['Return'].iloc[best_match_idx + 1]
                next_day_dir = "UP" if next_day_ret > 0 else "DOWN"
                
                signals["analogue_match"] = f"Similar to {analogue_date_str} (Next day went {next_day_dir})"
            else:
                signals["analogue_match"] = "No match found"
'''

content = content.replace(
    '            \"macd_signal\": \"bullish\" if macd > macd_signal else \"bearish\",\n            \"supertrend_signal\": \"bullish\" if st_dir == 1 else \"bearish\"\n        }',
    new_code
)

with open(path, 'w') as f:
    f.write(content)
print("Updated export_dashboard.py")
