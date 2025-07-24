import os
import json
import time
from datetime import datetime
from kiteconnect import KiteConnect
from dotenv import load_dotenv, dotenv_values

# ========== PATHS ========== 
DATA_DIR = "data"
SPOT_FILE = os.path.join(DATA_DIR, "spot.jsonl")
ENV_FILE = ".env"
INDEX_NAME = "NSE:NIFTY 50"

# ========== GLOBALS ========== 
last_logged_spot = None
last_logged_time = 0

# ========== HELPERS ========== 
def now():
    return datetime.now().isoformat()

def log(file, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(file, "a") as f:
        f.write(json.dumps(data, default=str) + "\n")

def load_env():
    load_dotenv(ENV_FILE)
    config = dotenv_values(ENV_FILE)
    return {
        "KITE_API_KEY": config.get("KITE_API_KEY"),
        "ACCESS_TOKEN": config.get("ACCESS_TOKEN"),
    }

def get_live_spot(kite):
    global last_logged_spot, last_logged_time
    try:
        data = kite.ltp([INDEX_NAME])
        spot_price = data[INDEX_NAME]["last_price"]
        
        # Fetch current time and check if 1 second has passed since the last log
        current_time = time.time()
        
        # Log the spot value only if it has been 1 second since the last log
        if current_time - last_logged_time >= 1:  # 1 second interval
            log(SPOT_FILE, {"time": now(), "spot": spot_price})  # Log the new spot value
            last_logged_spot = spot_price  # Update the last logged spot value
            last_logged_time = current_time  # Update the last logged time

        return spot_price
    except Exception as e:
        print(f"❌ Could not fetch spot price: {e}")
        return None

def main():
    config = load_env()
    kite = KiteConnect(api_key=config["KITE_API_KEY"])
    kite.set_access_token(config["ACCESS_TOKEN"])

    print("🎯 Spot Logger initialized. Logging spot every second...")

    while True:
        spot_price = get_live_spot(kite)
        if spot_price is not None:
            print(f"📍 Latest Spot: {spot_price}")
        time.sleep(1)  # Wait for 1 second before fetching the spot again

if __name__ == "__main__":
    main()
