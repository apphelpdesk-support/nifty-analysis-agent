with open("index.html", "r") as f:
    content = f.read()

# Revert the filter
content = content.replace(
    "const dates = Object.keys(dashboardData).filter(d => dashboardData[d].signals).sort().reverse();",
    "const dates = Object.keys(dashboardData).sort().reverse();"
)

# Replace the data.signals assignments in loadDateData
old_load = """            // 200 EMA
            const e200 = data.signals.ema200_signal;
            document.getElementById('val-ema200').innerHTML = 'Price is <span class="font-bold text-'+(e200=='bullish'?'green':'red')+'-600">' + (e200=='bullish'?'Above':'Below') + '</span>';
            
            // 20 EMA
            const e20 = data.signals.ema20_signal;
            document.getElementById('val-ema20').innerHTML = 'Price is <span class="font-bold text-'+(e20=='bullish'?'green':'red')+'-600">' + (e20=='bullish'?'Above':'Below') + '</span>';
            
            // Supertrend
            const st = data.signals.supertrend_signal;
            document.getElementById('val-supertrend').innerHTML = 'Signal is <span class="font-bold text-'+(st=='bullish'?'green':'red')+'-600">' + (st=='bullish'?'Buy (Bullish)':'Sell (Bearish)') + '</span>';
            
            // RSI
            const rsi_val = data.signals.rsi_value;
            const rsi_sig = data.signals.rsi_signal;
            let rsi_text = rsi_val + ' (Neutral)';
            if(rsi_sig == 'overbought') rsi_text = rsi_val + ' <span class="text-red-600 font-bold">(Overbought)</span>';
            if(rsi_sig == 'oversold') rsi_text = rsi_val + ' <span class="text-green-600 font-bold">(Oversold)</span>';
            document.getElementById('val-rsi').innerHTML = rsi_text;

            // MACD
            const macd = data.signals.macd_signal;
            document.getElementById('val-macd').innerHTML = 'Signal is <span class="font-bold text-'+(macd=='bullish'?'green':'red')+'-600">' + (macd=='bullish'?'Bullish':'Bearish') + '</span>';
            
            // Analogue
            if (data.signals.analogue_match) {
                document.getElementById('res-analogue').innerHTML = "<strong>Closest match found in last 10 years:</strong> " + data.signals.analogue_match;
            } else {
                document.getElementById('res-analogue').innerHTML = "No historical match generated.";
            }"""

new_load = """            if (!data.signals) {
                const msg = "<span class='text-gray-400 italic'>Not available for legacy dates</span>";
                document.getElementById('val-ema200').innerHTML = msg;
                document.getElementById('val-ema20').innerHTML = msg;
                document.getElementById('val-supertrend').innerHTML = msg;
                document.getElementById('val-rsi').innerHTML = msg;
                document.getElementById('val-macd').innerHTML = msg;
                document.getElementById('res-analogue').innerHTML = msg;
            } else {
                // 200 EMA
                const e200 = data.signals.ema200_signal;
                document.getElementById('val-ema200').innerHTML = 'Price is <span class="font-bold text-'+(e200=='bullish'?'green':'red')+'-600">' + (e200=='bullish'?'Above':'Below') + '</span>';
                
                // 20 EMA
                const e20 = data.signals.ema20_signal;
                document.getElementById('val-ema20').innerHTML = 'Price is <span class="font-bold text-'+(e20=='bullish'?'green':'red')+'-600">' + (e20=='bullish'?'Above':'Below') + '</span>';
                
                // Supertrend
                const st = data.signals.supertrend_signal;
                document.getElementById('val-supertrend').innerHTML = 'Signal is <span class="font-bold text-'+(st=='bullish'?'green':'red')+'-600">' + (st=='bullish'?'Buy (Bullish)':'Sell (Bearish)') + '</span>';
                
                // RSI
                const rsi_val = data.signals.rsi_value;
                const rsi_sig = data.signals.rsi_signal;
                let rsi_text = rsi_val + ' (Neutral)';
                if(rsi_sig == 'overbought') rsi_text = rsi_val + ' <span class="text-red-600 font-bold">(Overbought)</span>';
                if(rsi_sig == 'oversold') rsi_text = rsi_val + ' <span class="text-green-600 font-bold">(Oversold)</span>';
                document.getElementById('val-rsi').innerHTML = rsi_text;

                // MACD
                const macd = data.signals.macd_signal;
                document.getElementById('val-macd').innerHTML = 'Signal is <span class="font-bold text-'+(macd=='bullish'?'green':'red')+'-600">' + (macd=='bullish'?'Bullish':'Bearish') + '</span>';
                
                // Analogue
                if (data.signals.analogue_match) {
                    document.getElementById('res-analogue').innerHTML = "<strong>Closest match found in last 10 years:</strong> " + data.signals.analogue_match;
                } else {
                    document.getElementById('res-analogue').innerHTML = "No historical match generated.";
                }
            }"""

content = content.replace(old_load, new_load)

old_score = """            if(document.getElementById('chk-ema200').checked) {
                if(data.signals.ema200_signal === 'bullish') score += 3;
                else score -= 3;
            }
            if(document.getElementById('chk-ema20').checked) {
                if(data.signals.ema20_signal === 'bullish') score += 2;
                else score -= 2;
            }
            if(document.getElementById('chk-supertrend').checked) {
                if(data.signals.supertrend_signal === 'bullish') score += 3;
                else score -= 3;
            }
            if(document.getElementById('chk-rsi').checked) {
                // Contrarian indicator (if overbought, bearish signal)
                if(data.signals.rsi_signal === 'overbought') score -= 3;
                else if(data.signals.rsi_signal === 'oversold') score += 3;
            }
            if(document.getElementById('chk-macd').checked) {
                if(data.signals.macd_signal === 'bullish') score += 2;
                else score -= 2;
            }"""

new_score = """            if(data.signals) {
                if(document.getElementById('chk-ema200').checked) {
                    if(data.signals.ema200_signal === 'bullish') score += 3;
                    else score -= 3;
                }
                if(document.getElementById('chk-ema20').checked) {
                    if(data.signals.ema20_signal === 'bullish') score += 2;
                    else score -= 2;
                }
                if(document.getElementById('chk-supertrend').checked) {
                    if(data.signals.supertrend_signal === 'bullish') score += 3;
                    else score -= 3;
                }
                if(document.getElementById('chk-rsi').checked) {
                    // Contrarian indicator (if overbought, bearish signal)
                    if(data.signals.rsi_signal === 'overbought') score -= 3;
                    else if(data.signals.rsi_signal === 'oversold') score += 3;
                }
                if(document.getElementById('chk-macd').checked) {
                    if(data.signals.macd_signal === 'bullish') score += 2;
                    else score -= 2;
                }
            }"""
            
content = content.replace(old_score, new_score)

with open("index.html", "w") as f:
    f.write(content)
print("Updated index.html safely.")
