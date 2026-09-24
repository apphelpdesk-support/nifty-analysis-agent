with open("index.html", "r", encoding="utf8") as f:
    content = f.read()

# Add the UI for Dynamic Pattern Scanner right below the indicator list
new_ui = """                </div>
                
                <!-- Dynamic Pattern Scanner -->
                <div class="mt-8 border-t pt-6">
                    <h2 class="text-lg font-bold mb-2 flex items-center gap-2">
                        <i class="fa-solid fa-microscope text-brand-500"></i> Dynamic Pattern Scanner
                    </h2>
                    <p class="text-xs text-gray-500 mb-4">Select a custom date range to scan 10 years of history for the exact same pattern.</p>
                    
                    <div class="grid grid-cols-2 gap-3 mb-4">
                        <div>
                            <label class="text-xs font-semibold text-gray-600 block mb-1">Start Date</label>
                            <input type="date" id="scan-start" class="w-full bg-gray-50 border border-gray-200 text-gray-900 text-sm py-2 px-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500">
                        </div>
                        <div>
                            <label class="text-xs font-semibold text-gray-600 block mb-1">End Date</label>
                            <input type="date" id="scan-end" class="w-full bg-gray-50 border border-gray-200 text-gray-900 text-sm py-2 px-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500">
                        </div>
                    </div>
                    <button onclick="runPatternScanner()" class="w-full bg-brand-600 hover:bg-brand-700 text-white font-bold py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 mb-4 shadow-sm">
                        <i class="fa-solid fa-bolt"></i> Scan History
                    </button>
                    
                    <!-- Scanner Results -->
                    <div id="scan-results" class="hidden bg-gray-50 border border-gray-200 rounded-xl p-4">
                        <h4 class="font-bold text-gray-900 text-sm mb-2">Top 3 Historical Matches:</h4>
                        <div id="scan-matches" class="space-y-3 mb-3">
                            <!-- Matches injected here -->
                        </div>
                        <div class="border-t pt-2">
                            <h4 class="text-xs text-gray-500 font-semibold uppercase mb-1">Aggregate Projection</h4>
                            <div id="scan-projection" class="font-black text-lg"></div>
                        </div>
                    </div>
                </div>

            </div>"""

content = content.replace("                </div>\n\n            </div>", new_ui)

js_logic = """
        function runPatternScanner() {
            const startStr = document.getElementById('scan-start').value;
            const endStr = document.getElementById('scan-end').value;
            
            if (!startStr || !endStr) {
                alert("Please select both a Start Date and an End Date.");
                return;
            }
            if (new Date(startStr) >= new Date(endStr)) {
                alert("Start Date must be before End Date.");
                return;
            }
            
            // Extract dates from dashboardData
            const allDates = Object.keys(dashboardData).sort(); // ascending order
            
            const startIndex = allDates.indexOf(startStr);
            const endIndex = allDates.indexOf(endStr);
            
            if (startIndex === -1 || endIndex === -1) {
                alert("One or both dates fall on a weekend/holiday with no trading data. Please select valid trading days.");
                return;
            }
            
            const rangeLength = endIndex - startIndex + 1;
            if (rangeLength > 30) {
                alert("Maximum range limit is 30 trading days. Please select a shorter range.");
                return;
            }
            if (rangeLength < 2) {
                alert("Range must be at least 2 days to form a pattern.");
                return;
            }
            
            // Extract the target sequence percent changes
            const targetSequence = [];
            for (let i = startIndex + 1; i <= endIndex; i++) {
                const prevClose = dashboardData[allDates[i-1]].signals.close;
                const currClose = dashboardData[allDates[i]].signals.close;
                targetSequence.push((currClose - prevClose) / prevClose);
            }
            
            const results = [];
            
            // Scan through history
            // We need a window of length (rangeLength). So it requires (rangeLength) days of data, 
            // and we also need the day AFTER the window to see the outcome.
            for (let i = 0; i < allDates.length - rangeLength; i++) {
                // Skip if this window overlaps with the selected target window
                if ((i <= endIndex) && (i + rangeLength - 1 >= startIndex)) continue;
                
                const windowSeq = [];
                for (let j = 1; j < rangeLength; j++) {
                    const prevClose = dashboardData[allDates[i + j - 1]].signals.close;
                    const currClose = dashboardData[allDates[i + j]].signals.close;
                    windowSeq.push((currClose - prevClose) / prevClose);
                }
                
                // Calculate Euclidean distance
                let sumSq = 0;
                for (let k = 0; k < targetSequence.length; k++) {
                    sumSq += Math.pow(targetSequence[k] - windowSeq[k], 2);
                }
                const distance = Math.sqrt(sumSq);
                
                // Get Outcome on the day AFTER the window
                const lastDayClose = dashboardData[allDates[i + rangeLength - 1]].signals.close;
                const nextDayClose = dashboardData[allDates[i + rangeLength]].signals.close;
                const nextDayPct = ((nextDayClose - lastDayClose) / lastDayClose) * 100;
                
                results.push({
                    startDate: allDates[i],
                    endDate: allDates[i + rangeLength - 1],
                    distance: distance,
                    nextDayPct: nextDayPct
                });
            }
            
            // Sort by lowest distance
            results.sort((a, b) => a.distance - b.distance);
            const top3 = results.slice(0, 3);
            
            // Display Results
            document.getElementById('scan-results').classList.remove('hidden');
            const matchesContainer = document.getElementById('scan-matches');
            matchesContainer.innerHTML = '';
            
            let totalPct = 0;
            
            top3.forEach((match, idx) => {
                totalPct += match.nextDayPct;
                const isUp = match.nextDayPct > 0;
                const color = isUp ? 'green' : 'red';
                const sign = isUp ? '+' : '';
                
                matchesContainer.innerHTML += `
                    <div class="flex justify-between items-center text-sm border-b border-gray-100 pb-2 last:border-0 last:pb-0">
                        <div class="text-gray-700">
                            <span class="font-bold">#${idx+1}</span>: ${match.startDate} to ${match.endDate}
                        </div>
                        <div class="font-bold text-${color}-600">
                            ${sign}${match.nextDayPct.toFixed(2)}%
                        </div>
                    </div>
                `;
            });
            
            const avgPct = totalPct / 3;
            const avgUp = avgPct > 0;
            const pColor = avgUp ? 'green' : 'red';
            const pSign = avgUp ? '+' : '';
            const pText = avgUp ? 'UP' : 'DOWN';
            
            document.getElementById('scan-projection').innerHTML = `<span class="text-${pColor}-600">${pText} (${pSign}${avgPct.toFixed(2)}%)</span>`;
        }
</script>"""

content = content.replace("</script>", js_logic)

with open("index.html", "w", encoding="utf8") as f:
    f.write(content)
print("Pattern scanner added to index.html")
