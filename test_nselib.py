from nselib import capital_market
try:
    df = capital_market.index_data(index="Nifty 50", from_date="17-09-2026", to_date="24-09-2026")
    print(df)
except Exception as e:
    print("Error:", e)
