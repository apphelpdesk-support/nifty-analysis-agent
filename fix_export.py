with open("scripts/export_dashboard.py", "r") as f:
    content = f.read()

content = content.replace('''    if os.path.exists(data_file):
        try:
            with open(data_file, "r") as f:
                data = json.load(f)
        except Exception:
            pass''', '')

content = content.replace('trading_days = df.index[-5:]', 'trading_days = df.index[200:]')

with open("scripts/export_dashboard.py", "w") as f:
    f.write(content)
print("Updated export_dashboard.py")
