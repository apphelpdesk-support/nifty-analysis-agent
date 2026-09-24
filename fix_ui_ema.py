with open("index.html", "r", encoding="utf8") as f:
    content = f.read()

# I will use replace with exact copy pasted lines
old_ema = """                // 200 EMA
                const e200 = data.signals.ema200_signal;
                document.getElementById('val-ema200').innerHTML = 'Price is <span class="font-bold text-'+(e200=='bullish'?'green':'red')+'-600">' + (e200=='bullish'?'Above':'Below') + '</span>';
                
                // 20 EMA
                const e20 = data.signals.ema20_signal;
                document.getElementById('val-ema20').innerHTML = 'Price is <span class="font-bold text-'+(e20=='bullish'?'green':'red')+'-600">' + (e20=='bullish'?'Above':'Below') + '</span>';"""

new_ema = """                // 200 EMA
                const e200 = data.signals.ema200_signal;
                const diff200 = data.signals.ema200_diff_pct;
                let diff200Text = diff200 !== undefined ? ` <span class="text-xs text-gray-500 font-bold">(${diff200 > 0 ? '+' : ''}${diff200}% from EMA)</span>` : '';
                document.getElementById('val-ema200').innerHTML = 'Price is <span class="font-bold text-'+(e200=='bullish'?'green':'red')+'-600">' + (e200=='bullish'?'Above':'Below') + '</span>' + diff200Text;
                
                // 20 EMA
                const e20 = data.signals.ema20_signal;
                const diff20 = data.signals.ema20_diff_pct;
                let diff20Text = diff20 !== undefined ? ` <span class="text-xs text-gray-500 font-bold">(${diff20 > 0 ? '+' : ''}${diff20}% from EMA)</span>` : '';
                document.getElementById('val-ema20').innerHTML = 'Price is <span class="font-bold text-'+(e20=='bullish'?'green':'red')+'-600">' + (e20=='bullish'?'Above':'Below') + '</span>' + diff20Text;"""

if old_ema in content:
    content = content.replace(old_ema, new_ema)
    with open("index.html", "w", encoding="utf8") as f:
        f.write(content)
    print("EMA distance text successfully added to index.html")
else:
    print("Failed to find exact block again.")
