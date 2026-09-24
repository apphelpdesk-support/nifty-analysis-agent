with open("index.html", "r") as f:
    content = f.read()

# Update loadDateData text logic
old_load = """            // 200 EMA
            const e200 = data.signals.ema200_signal;
            document.getElementById('val-ema200').innerHTML = 'Price is <span class="font-bold text-'+(e200=='bullish'?'green':'red')+'-600">' + (e200=='bullish'?'Above':'Below') + '</span>';
            
            // 20 EMA
            const e20 = data.signals.ema20_signal;
            document.getElementById('val-ema20').innerHTML = 'Price is <span class="font-bold text-'+(e20=='bullish'?'green':'red')+'-600">' + (e20=='bullish'?'Above':'Below') + '</span>';"""

new_load = """            // 200 EMA
            const e200 = data.signals.ema200_signal;
            const diff200 = data.signals.ema200_diff_pct;
            let diff200Text = diff200 !== undefined ? ` <span class="text-xs text-gray-500">(${diff200 > 0 ? '+' : ''}${diff200}% from EMA)</span>` : '';
            document.getElementById('val-ema200').innerHTML = 'Price is <span class="font-bold text-'+(e200=='bullish'?'green':'red')+'-600">' + (e200=='bullish'?'Above':'Below') + '</span>' + diff200Text;
            
            // 20 EMA
            const e20 = data.signals.ema20_signal;
            const diff20 = data.signals.ema20_diff_pct;
            let diff20Text = diff20 !== undefined ? ` <span class="text-xs text-gray-500">(${diff20 > 0 ? '+' : ''}${diff20}% from EMA)</span>` : '';
            document.getElementById('val-ema20').innerHTML = 'Price is <span class="font-bold text-'+(e20=='bullish'?'green':'red')+'-600">' + (e20=='bullish'?'Above':'Below') + '</span>' + diff20Text;"""

content = content.replace(old_load, new_load)


# Update calculateScore logic
old_calc = """        function calculateScore() {
            const date = document.getElementById('date-picker').value;
            if(!dashboardData[date]) return 0;
            const data = dashboardData[date];
            
            let score = 0;
            
            if(document.getElementById('chk-fii').checked) {
                if(data.fii === 'buying') score += 4;
                if(data.fii === 'selling') score -= 4;
            }
            if(data.signals) {
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
            }
            return score;
        }

        function renderPrediction() {
            const score = calculateScore();
            // What is the max score?
            // fii: 4, ema200: 3, ema20: 2, st: 3, rsi: 3, macd: 2 = 17
            const maxScore = 17;
            
            let probability = Math.round((Math.abs(score) / maxScore) * 100);
            if(probability > 99) probability = 99;
            
            let direction = "NEUTRAL";
            let color = "gray";
            
            if (score > 3) { direction = "UP"; color = "green"; }
            else if (score < -3) { direction = "DOWN"; color = "red"; }
            
            const pText = score === 0 ? '50%' : `${probability}%`;
            
            // Tomorrow
            document.getElementById('res-tomorrow').innerHTML = `
                <div class="text-${color}-600 font-black text-2xl mb-1">${direction}</div>
                <div class="text-sm font-medium text-gray-500">Probability: ${pText}</div>
            `;
            
            // Week (Slightly decayed score)
            let wDir = direction;
            let wProb = score === 0 ? '50%' : `${Math.max(50, probability - 10)}%`;
            if (Math.abs(score) < 5) wDir = "NEUTRAL";
            
            document.getElementById('res-week').innerHTML = `
                <div class="text-${wDir=='NEUTRAL'?'gray':color}-600 font-bold text-xl mb-1">${wDir}</div>
                <div class="text-sm text-gray-500">${wProb}</div>
            `;
            
            // Month
            document.getElementById('res-month').innerHTML = `
                <div class="text-gray-600 font-bold text-xl mb-1">DATA REQ</div>
                <div class="text-sm text-gray-500">More data needed</div>
            `;
        }"""

new_calc = """        function calculateScore() {
            const date = document.getElementById('date-picker').value;
            if(!dashboardData[date]) return {score: 0, maxScore: 17, isReversal: false};
            const data = dashboardData[date];
            
            let score = 0;
            let maxScore = 0;
            
            if(document.getElementById('chk-fii').checked) {
                maxScore += 4;
                if(data.fii === 'buying') score += 4;
                if(data.fii === 'selling') score -= 4;
            }
            
            let isReversal = false;
            
            if(data.signals) {
                // Historical Analogue Match Scoring (always included, implicit +4 weight)
                if(data.signals.analogue_match && data.signals.analogue_match.includes('UP')) {
                    score += 4;
                    maxScore += 4;
                } else if(data.signals.analogue_match && data.signals.analogue_match.includes('DOWN')) {
                    score -= 4;
                    maxScore += 4;
                }
            
                if(document.getElementById('chk-ema200').checked) {
                    maxScore += 3;
                    if(data.signals.ema200_signal === 'bullish') score += 3;
                    else score -= 3;
                }
                if(document.getElementById('chk-ema20').checked) {
                    maxScore += 2;
                    if(data.signals.ema20_signal === 'bullish') score += 2;
                    else score -= 2;
                }
                if(document.getElementById('chk-supertrend').checked) {
                    maxScore += 3;
                    if(data.signals.supertrend_signal === 'bullish') score += 3;
                    else score -= 3;
                }
                if(document.getElementById('chk-rsi').checked) {
                    maxScore += 4; // RSI is weighted heavily for mean reversion
                    const rsi = data.signals.rsi_value;
                    if(rsi < 35) {
                        score += 4; // Heavily oversold
                        isReversal = (score < 0); // If overall score is still negative but RSI is extremely low, it's a contrarian reversal
                    } else if(rsi < 45) {
                        score += 2; // Approaching oversold
                    } else if(rsi > 70) {
                        score -= 4; // Overbought
                        isReversal = (score > 0);
                    } else if(rsi > 60) {
                        score -= 2; // Approaching overbought
                    }
                }
                if(document.getElementById('chk-macd').checked) {
                    maxScore += 2;
                    if(data.signals.macd_signal === 'bullish') score += 2;
                    else score -= 2;
                }
            }
            
            // Prevent division by zero
            if (maxScore === 0) maxScore = 1;
            return {score, maxScore, isReversal};
        }

        function renderPrediction() {
            const result = calculateScore();
            const score = result.score;
            const maxScore = result.maxScore;
            
            let probability = Math.round((Math.abs(score) / maxScore) * 100);
            if(probability > 99) probability = 99;
            
            let direction = "NEUTRAL";
            let color = "gray";
            
            if (score > 3) { direction = "UP"; color = "green"; }
            else if (score < -3) { direction = "DOWN"; color = "red"; }
            
            // Apply Contrarian Logic (Mean Reversion)
            let pText = score === 0 ? '50%' : `${probability}%`;
            let warningText = "";
            
            if (result.isReversal) {
                direction = "CAUTION";
                color = "orange";
                pText = "Mean Reversion Imminent";
                warningText = `<div class="text-xs text-orange-600 font-bold mt-1">Trend is exhausted. Watch for bounce.</div>`;
            }
            
            // Tomorrow
            document.getElementById('res-tomorrow').innerHTML = `
                <div class="text-${color}-600 font-black text-2xl mb-1">${direction}</div>
                <div class="text-sm font-medium text-gray-500">Probability: ${pText}</div>
                ${warningText}
            `;
            
            // Week (Slightly decayed score)
            let wDir = direction;
            let wProb = score === 0 ? '50%' : `${Math.max(50, probability - 10)}%`;
            if (Math.abs(score) < 5 || result.isReversal) wDir = "NEUTRAL";
            
            document.getElementById('res-week').innerHTML = `
                <div class="text-${wDir=='NEUTRAL'?'gray':color}-600 font-bold text-xl mb-1">${wDir}</div>
                <div class="text-sm text-gray-500">${wProb}</div>
            `;
            
            // Month
            document.getElementById('res-month').innerHTML = `
                <div class="text-gray-600 font-bold text-xl mb-1">DATA REQ</div>
                <div class="text-sm text-gray-500">More data needed</div>
            `;
        }"""

content = content.replace(old_calc, new_calc)

with open("index.html", "w") as f:
    f.write(content)
print("Updated index.html to include Smart Scoring logic and EMA distances")
