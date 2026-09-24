import re

with open("index.html", "r", encoding="utf8") as f:
    content = f.read()

# Update loadDateData
# Find the exact lines for EMA 200 and EMA 20
e200_old = """            // 200 EMA
            const e200 = data.signals.ema200_signal;
            document.getElementById('val-ema200').innerHTML = 'Price is <span class="font-bold text-'+(e200=='bullish'?'green':'red')+'-600">' + (e200=='bullish'?'Above':'Below') + '</span>';
            
            // 20 EMA
            const e20 = data.signals.ema20_signal;
            document.getElementById('val-ema20').innerHTML = 'Price is <span class="font-bold text-'+(e20=='bullish'?'green':'red')+'-600">' + (e20=='bullish'?'Above':'Below') + '</span>';"""

e200_new = """            // 200 EMA
            const e200 = data.signals.ema200_signal;
            const diff200 = data.signals.ema200_diff_pct;
            let diff200Text = diff200 !== undefined ? ` <span class="text-xs text-gray-500 font-bold">(${diff200 > 0 ? '+' : ''}${diff200}% from EMA)</span>` : '';
            document.getElementById('val-ema200').innerHTML = 'Price is <span class="font-bold text-'+(e200=='bullish'?'green':'red')+'-600">' + (e200=='bullish'?'Above':'Below') + '</span>' + diff200Text;
            
            // 20 EMA
            const e20 = data.signals.ema20_signal;
            const diff20 = data.signals.ema20_diff_pct;
            let diff20Text = diff20 !== undefined ? ` <span class="text-xs text-gray-500 font-bold">(${diff20 > 0 ? '+' : ''}${diff20}% from EMA)</span>` : '';
            document.getElementById('val-ema20').innerHTML = 'Price is <span class="font-bold text-'+(e20=='bullish'?'green':'red')+'-600">' + (e20=='bullish'?'Above':'Below') + '</span>' + diff20Text;"""

if e200_old in content:
    content = content.replace(e200_old, e200_new)
else:
    print("Failed to replace EMA block")

# CalculateScore and RenderPrediction
score_regex = re.compile(r"function calculateScore\(\).*?return score;\n        }", re.DOTALL)

calc_new = """function calculateScore() {
            const date = document.getElementById('date-picker').value;
            if(!dashboardData[date]) return {score: 0, isReversal: false};
            const data = dashboardData[date];
            
            let score = 0;
            let isReversal = false;
            
            if(document.getElementById('chk-fii').checked) {
                if(data.fii === 'buying') score += 4;
                if(data.fii === 'selling') score -= 4;
            }
            if(data.signals) {
                // Historical Analogue Match Score (+4 or -4 implicit weight)
                if(data.signals.analogue_match && data.signals.analogue_match.includes('UP')) {
                    score += 4;
                } else if(data.signals.analogue_match && data.signals.analogue_match.includes('DOWN')) {
                    score -= 4;
                }

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
                    const rsi = data.signals.rsi_value;
                    if(rsi < 35) {
                        score += 4; // heavily oversold
                        isReversal = (score < 0);
                    } else if(rsi < 45) {
                        score += 2; 
                    } else if(rsi > 70) {
                        score -= 4; // overbought
                        isReversal = (score > 0);
                    } else if(rsi > 60) {
                        score -= 2;
                    }
                }
                if(document.getElementById('chk-macd').checked) {
                    if(data.signals.macd_signal === 'bullish') score += 2;
                    else score -= 2;
                }
            }
            
            return {score: score, isReversal: isReversal};
        }"""

content = re.sub(score_regex, calc_new, content)

render_regex = re.compile(r"function renderPrediction\(\) \{.*?const base_score = calculateScore\(\);", re.DOTALL)
render_new = """function renderPrediction() {
            const scoreData = calculateScore();
            const base_score = scoreData.score;
            const isReversal = scoreData.isReversal;"""

content = re.sub(render_regex, render_new, content)

# Modify renderPrediction inner logic
strategy_old = """                } else {
                    dir = "DOWN"; exp_move = "-" + (1.5 * tf_mod).toFixed(1) + "%"; strategy = "Strong bearish conviction. Buy Put Options / Short Sell."; color = "red";
                }
            }"""

strategy_new = """                } else {
                    dir = "DOWN"; exp_move = "-" + (1.5 * tf_mod).toFixed(1) + "%"; strategy = "Strong bearish conviction. Buy Put Options / Short Sell."; color = "red";
                }
            }
            
            if (isReversal) {
                dir = "CAUTION";
                exp_move = "Mean Reversion";
                strategy = "Trend is exhausted. High probability of a sharp bounce/reversal. Do NOT trend-follow here.";
                color = "orange";
            }"""

content = content.replace(strategy_old, strategy_new)

with open("index.html", "w", encoding="utf8") as f:
    f.write(content)

print("Updated JS logic correctly!")
