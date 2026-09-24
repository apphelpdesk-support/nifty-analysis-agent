with open("scripts/export_dashboard.py", "r") as f:
    content = f.read()

old_signals = """        signals = {
            "close": round(close, 2),
            "ema20_signal": "bullish" if close > ema20 else "bearish",
            "ema200_signal": "bullish" if close > ema200 else "bearish",
            "rsi_value": round(rsi, 2),
            "rsi_signal": "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral"),
            "macd_signal": "bullish" if macd > macd_signal else "bearish",
            "supertrend_signal": "bullish" if st_dir == 1 else "bearish"
        }"""

new_signals = """        signals = {
            "close": round(close, 2),
            "ema20_signal": "bullish" if close > ema20 else "bearish",
            "ema200_signal": "bullish" if close > ema200 else "bearish",
            "ema20_diff_pct": round(((close - ema20) / ema20) * 100, 2),
            "ema200_diff_pct": round(((close - ema200) / ema200) * 100, 2),
            "rsi_value": round(rsi, 2),
            "rsi_signal": "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral"),
            "macd_signal": "bullish" if macd > macd_signal else "bearish",
            "supertrend_signal": "bullish" if st_dir == 1 else "bearish"
        }"""

content = content.replace(old_signals, new_signals)

with open("scripts/export_dashboard.py", "w") as f:
    f.write(content)
print("Updated export_dashboard.py with EMA diff percentages")
