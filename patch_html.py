path = "index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Add Support/Resistance Box
html_block = """                <!-- Support and Resistance -->
                <div class="bg-indigo-50 border border-indigo-100 rounded-xl p-6 mb-6">
                    <h3 class="font-bold text-indigo-900 mb-2 flex items-center gap-2">
                        <i class="fa-solid fa-arrows-up-down text-indigo-500"></i> Next Day Targets
                    </h3>
                    <div class="grid grid-cols-2 gap-4 mt-3">
                        <div class="bg-white p-3 rounded-lg border border-indigo-100 shadow-sm">
                            <span class="block text-xs font-semibold text-gray-500 uppercase">Major Resistance</span>
                            <span class="block text-lg font-bold text-red-600" id="res-r1">Loading...</span>
                        </div>
                        <div class="bg-white p-3 rounded-lg border border-indigo-100 shadow-sm">
                            <span class="block text-xs font-semibold text-gray-500 uppercase">Major Support</span>
                            <span class="block text-lg font-bold text-green-600" id="res-s1">Loading...</span>
                        </div>
                    </div>
                </div>

                <div class="bg-purple-50 border border-purple-100 rounded-xl p-6 mb-6">"""

content = content.replace('                <div class="bg-purple-50 border border-purple-100 rounded-xl p-6 mb-6">', html_block)

js_block = """            // Support and Resistance Pivots (Next Day Targets)
            if (data.signals.high && data.signals.low) {
                const high = data.signals.high;
                const low = data.signals.low;
                const close = data.signals.close;
                const pivot = (high + low + close) / 3;
                const r1 = (2 * pivot) - low;
                const s1 = (2 * pivot) - high;
                document.getElementById('res-r1').innerText = r1.toFixed(2);
                document.getElementById('res-s1').innerText = s1.toFixed(2);
            } else {
                document.getElementById('res-r1').innerText = 'Data Syncing...';
                document.getElementById('res-s1').innerText = 'Data Syncing...';
            }
            
            // Analogue"""
            
content = content.replace('            // Analogue', js_block)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated index.html")
