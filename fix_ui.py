import re

with open("index.html", "r") as f:
    content = f.read()

content = content.replace(
    "const dates = Object.keys(dashboardData).sort().reverse();",
    "const dates = Object.keys(dashboardData).filter(d => dashboardData[d].signals).sort().reverse();"
)

with open("index.html", "w") as f:
    f.write(content)

print("Updated index.html to filter out old dates.")
