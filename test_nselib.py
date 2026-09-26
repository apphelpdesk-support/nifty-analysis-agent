try:
    from nselib import capital_market
    df = capital_market.fii_dii_trading_activity()
    print("FII/DII DATA FROM NSELIB:")
    print(df)
except Exception as e:
    print(e)
