with open("index.html", "r") as f:
    content = f.read()

old_html = """                <select id="date-picker" class="w-full bg-gray-50 border border-gray-200 text-gray-900 font-semibold py-3 px-4 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 transition-shadow cursor-pointer mb-6" onchange="loadDateData()">
                    <option value="">Loading live data...</option>
                </select>"""

new_html = """                <input type="date" id="date-picker" class="w-full bg-gray-50 border border-gray-200 text-gray-900 font-semibold py-3 px-4 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 transition-shadow cursor-pointer" onchange="loadDateData()">
                <div id="date-error" class="text-sm font-semibold text-red-500 mt-1 mb-5 hidden">Market Closed / No Data for this date</div>"""
content = content.replace(old_html, new_html)

old_fetch = """                const select = document.getElementById('date-picker');
                select.innerHTML = ''; 
                
                const dates = Object.keys(dashboardData).sort().reverse();
                
                dates.forEach((date, i) => {
                    const opt = document.createElement('option');
                    opt.value = date;
                    let label = new Date(date).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'short', day: 'numeric' });
                    if (i === 0) label = "Most Recent: " + label;
                    opt.innerText = label;
                    select.appendChild(opt);
                });

                if (dates.length > 0) {
                    loadDateData();
                }"""

new_fetch = """                const select = document.getElementById('date-picker');
                const dates = Object.keys(dashboardData).sort().reverse();
                
                if (dates.length > 0) {
                    select.value = dates[0]; // Most recent date
                    select.min = dates[dates.length - 1]; // Oldest date
                    select.max = dates[0]; // Newest date
                    loadDateData();
                }"""
content = content.replace(old_fetch, new_fetch)

old_error_catch = """document.getElementById('date-picker').innerHTML = '<option>Error loading automated data.</option>';"""
new_error_catch = """document.getElementById('date-error').innerText = 'Error loading automated data.'; document.getElementById('date-error').classList.remove('hidden');"""
content = content.replace(old_error_catch, new_error_catch)

old_load = """        function loadDateData() {
            const date = document.getElementById('date-picker').value;
            if(!dashboardData[date]) return;
            const data = dashboardData[date];"""

new_load = """        function loadDateData() {
            const date = document.getElementById('date-picker').value;
            const errEl = document.getElementById('date-error');
            if(!dashboardData[date]) {
                errEl.innerText = "Market Closed or No Data Available for " + date;
                errEl.classList.remove('hidden');
                document.getElementById('res-tomorrow').innerHTML = "N/A";
                document.getElementById('res-week').innerHTML = "N/A";
                document.getElementById('res-month').innerHTML = "N/A";
                return;
            }
            errEl.classList.add('hidden');
            const data = dashboardData[date];"""
content = content.replace(old_load, new_load)

with open("index.html", "w") as f:
    f.write(content)
print("Updated index.html to use a native date picker")
