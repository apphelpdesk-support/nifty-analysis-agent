import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core.settings as st

def merge_and_replace():
    settings = st.load_settings()
    
    historical_path = Path("data/historical/nifty.csv")
    fyers_path = Path("data/fyers_db/1D/NSE_NIFTY50-INDEX.csv")
    
    if not historical_path.exists() or not fyers_path.exists():
        print("Missing required DB files for merge.")
        return
        
    yahoo_df = pd.read_csv(historical_path, index_col=0, parse_dates=True)
    fyers_df = pd.read_csv(fyers_path, index_col=0, parse_dates=True)
    
    # Strip timezone from Fyers data to match standard Yahoo index (YYYY-MM-DD)
    fyers_df.index = pd.to_datetime([d.strftime("%Y-%m-%d") for d in fyers_df.index])
    
    # We slice Yahoo to keep only the dates BEFORE Fyers data begins
    fyers_start_date = fyers_df.index[0]
    old_yahoo_df = yahoo_df[yahoo_df.index < fyers_start_date]
    
    print(f"Keeping Yahoo history from {old_yahoo_df.index[0].date()} to {old_yahoo_df.index[-1].date()} ({len(old_yahoo_df)} days)")
    print(f"Appending Fyers history from {fyers_df.index[0].date()} to {fyers_df.index[-1].date()} ({len(fyers_df)} days)")
    
    merged_df = pd.concat([old_yahoo_df, fyers_df])
    
    # Ensure there are no duplicate dates, keeping Fyers (the last)
    merged_df = merged_df[~merged_df.index.duplicated(keep="last")].sort_index()
    
    print(f"Successfully merged! Total History: {len(merged_df)} trading days.")
    print("Overwriting data/historical/nifty.csv with the new master dataset...")
    
    merged_df.to_csv(historical_path)
    print("Done! Your entire dashboard is now powered by Fyers.")

if __name__ == "__main__":
    merge_and_replace()
