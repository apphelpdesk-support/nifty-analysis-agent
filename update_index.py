path = 'index.html'
with open(path, 'r') as f:
    content = f.read()

html_block = '''                <div class="bg-purple-50 border border-purple-100 rounded-xl p-6 mb-6">
                    <h3 class="font-bold text-purple-900 mb-2 flex items-center gap-2">
                        <i class="fa-solid fa-clock-rotate-left text-purple-500"></i> Historical Pattern Match
                    </h3>
                    <p class="text-purple-800 text-sm leading-relaxed" id="res-analogue">
                        Loading...
                    </p>
                </div>

            </div>'''

content = content.replace('            </div>\n        </div>\n    </main>', html_block + '\n        </div>\n    </main>')

js_block = '''            // MACD
            const macd = data.signals.macd_signal;
            document.getElementById('val-macd').innerHTML = 'Signal is <span class="font-bold text-'+(macd=='bullish'?'green':'red')+'-600">' + (macd=='bullish'?'Bullish':'Bearish') + '</span>';
            
            // Analogue
            if (data.signals.analogue_match) {
                document.getElementById('res-analogue').innerHTML = "<strong>Closest match found in last 10 years:</strong> " + data.signals.analogue_match;
            } else {
                document.getElementById('res-analogue').innerHTML = "No historical match generated.";
            }
            
            renderPrediction();'''

content = content.replace('''            // MACD
            const macd = data.signals.macd_signal;
            document.getElementById('val-macd').innerHTML = 'Signal is <span class="font-bold text-'+(macd=='bullish'?'green':'red')+'-600">' + (macd=='bullish'?'Bullish':'Bearish') + '</span>';
            
            renderPrediction();''', js_block)

with open(path, 'w') as f:
    f.write(content)
print("Updated index.html")
