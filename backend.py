import os
import json
import time
from datetime import datetime
from kiteconnect import KiteConnect
from dotenv import load_dotenv, dotenv_values
import threading
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any
import uuid
import requests

# ========== PATHS ==========
DATA_DIR = "data"
ENV_FILE = ".env"
STRATEGIES_CONFIG_FILE = os.path.join(DATA_DIR, "strategies_config.json")
TOKEN_REFRESH_FILE = os.path.join(DATA_DIR, "token_refresh_trigger.txt")
INDEX_NAME = "NSE:NIFTY 50"

# ========== GLOBALS ==========
strategy_instances = {}  # Dict to store all strategy instances
strategy_threads = {}    # Dict to store strategy threads
cached_instruments = None
LOT_SIZE = 75
refresh_token_flag = False  # Flag to trigger token refresh

# ========== STRATEGY CLASS ==========
class StrategyInstance:
    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        self.strategy_id = strategy_id
        self.config = config
        self.strategy_name = config.get("STRATEGY_NAME", f"Strategy_{strategy_id}")
        
        # File paths specific to this strategy
        self.trades_file = os.path.join(DATA_DIR, f"trades_{strategy_id}.jsonl")
        self.triggers_file = os.path.join(DATA_DIR, f"triggers_{strategy_id}.jsonl")
        self.spot_file = os.path.join(DATA_DIR, f"spot_{strategy_id}.jsonl")
        self.status_file = os.path.join(DATA_DIR, f"status_{strategy_id}.json")
        
        # Strategy state
        self.state = {
            "trigger_up": None,
            "trigger_down": None,
            "open_trades": []
        }
        
        # Live values tracking
        self.live_values = {}
        
        # Thread control
        self.running = False
        self.strategy_thread = None
        self.monitor_thread = None
        
    def log(self, file_type: str, data: Dict):
        """Log data to strategy-specific files"""
        os.makedirs(DATA_DIR, exist_ok=True)
        file_map = {
            "trades": self.trades_file,
            "triggers": self.triggers_file,
            "spot": self.spot_file
        }
        
        file_path = file_map.get(file_type)
        if file_path:
            with open(file_path, "a") as f:
                f.write(json.dumps(data, default=str) + "\n")
    
    def read_jsonl(self, file_type: str) -> List[Dict]:
        """Read JSONL data from strategy-specific files"""
        file_map = {
            "trades": self.trades_file,
            "triggers": self.triggers_file,
            "spot": self.spot_file
        }
        
        file_path = file_map.get(file_type)
        if not file_path or not os.path.exists(file_path):
            return []
        
        with open(file_path) as f:
            return [json.loads(line) for line in f if line.strip()]
    
    def get_status(self) -> bool:
        """Get strategy running status"""
        try:
            with open(self.status_file) as f:
                return json.load(f).get("running", False)
        except:
            return False
    
    def set_status(self, running: bool):
        """Set strategy running status"""
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self.status_file, "w") as f:
            json.dump({"running": running}, f)
    
    def disable_old_triggers(self):
        """Disable old triggers for this strategy"""
        triggers = self.read_jsonl("triggers")
        df = pd.DataFrame(triggers)
        if df.empty or "time" not in df.columns:
            return
        df["time"] = pd.to_datetime(df["time"], errors='coerce')
        df = df.dropna(subset=["time"]).sort_values("time")
        latest_status = df.drop_duplicates("trigger", keep="last")
        for _, row in latest_status.iterrows():
            if row["status"] == "setup":
                self.log("triggers", {"time": now(), "status": "disabled", "trigger": row["trigger"]})
    
    def setup_initial_triggers(self, kite):
        """Setup initial triggers for this strategy"""
        spot = get_live_spot(kite)
        if spot is None:
            return False

        self.disable_old_triggers()
        gap = self.config["INITIAL_TRIGGER_GAP"]
        base = (spot // gap) * gap
        trigger_down = base
        trigger_up = base + gap

        recent = self.read_jsonl("triggers")
        df = pd.DataFrame(recent)
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"], errors='coerce')
            latest_status = df.dropna().sort_values("time").drop_duplicates("trigger", keep="last").set_index("trigger")["status"].to_dict()
        else:
            latest_status = {}

        if latest_status.get(trigger_down) != "setup":
            self.log("triggers", {"time": now(), "status": "setup", "trigger": trigger_down})
        if latest_status.get(trigger_up) != "setup":
            self.log("triggers", {"time": now(), "status": "setup", "trigger": trigger_up})

        self.state["trigger_down"] = trigger_down
        self.state["trigger_up"] = trigger_up
        return True
    
    def recover_open_trades(self):
        """Recover open trades for this strategy"""
        trades = self.read_jsonl("trades")
        entries = [t for t in trades if t.get("status") == "entry"]
        exits = {(t["trigger"], t["entry_time"]) for t in trades if t.get("status") == "exit"}

        deduped = {}
        for t in entries:
            key = (t["trigger"], t["entry_time"])
            if key not in exits:
                existing = deduped.get(key)
                if not existing or t.get("time", t["entry_time"]) > existing.get("time", existing["entry_time"]):
                    deduped[key] = t

        self.state["open_trades"] = list(deduped.values())
    
    def monitor_open_trades(self, kite):
        """Monitor open trades for this strategy"""
        while self.running:
            spot = get_live_spot(kite)
            if not spot:
                time.sleep(2)
                continue

            spot = round(spot)
            self.log("spot", {"time": now(), "spot": spot})

            for trade in self.state["open_trades"][:]:
                # Get the live LTP for CE and PE
                live_ce = get_option_ltp(kite, trade["trigger"] + trade["STRIKE_OFFSET"], "CE", trade["EXPIRY_DATE"])
                live_pe = get_option_ltp(kite, trade["trigger"] - trade["STRIKE_OFFSET"], "PE", trade["EXPIRY_DATE"])

                if live_ce == 0 or live_pe == 0:
                    continue

                # Initialize live values if they are not already present
                if trade["trigger"] not in self.live_values:
                    self.live_values[trade["trigger"]] = {"live_ce": None, "live_pe": None}

                # Only update and log if the live values have changed
                if self.live_values[trade["trigger"]]["live_ce"] != live_ce or self.live_values[trade["trigger"]]["live_pe"] != live_pe:
                    self.live_values[trade["trigger"]]["live_ce"] = live_ce
                    self.live_values[trade["trigger"]]["live_pe"] = live_pe

                    # Update the trade entry with the new live values
                    trade["live_ce"] = live_ce
                    trade["live_pe"] = live_pe

                    # Log the updated trade entry
                    self.log("trades", {**trade, "status": "entry", "time": now()})

                # Calculate P&L and check if exit conditions are met
                entry_sum = trade["ce"] + trade["pe"]
                live_sum = live_ce + live_pe
                pnl = (entry_sum - live_sum) * LOT_SIZE
                move = abs(spot - trade["spot"])

                if pnl >= trade["EXIT_PROFIT"] or move >= trade["EXIT_MOVE"]:
                    # Remove live_ce/live_pe before logging exit
                    trade.pop("live_ce", None)
                    trade.pop("live_pe", None)

                    self.log("trades", {
                        **trade,
                        "exit_time": now(),
                        "status": "exit",
                        "exit_ce": live_ce,
                        "exit_pe": live_pe,
                        "exit_spot": spot,
                        "pnl": round(pnl, 2)
                    })
                    self.state["open_trades"].remove(trade)

            time.sleep(2)
    
    def run_strategy(self, kite):
        """Main strategy execution loop"""
        if not self.setup_initial_triggers(kite):
            return

        self.recover_open_trades()

        while self.running and self.get_status():
            spot_price = get_live_spot(kite)
            if not spot_price:
                time.sleep(2)
                continue

            spot = round(spot_price)
            self.log("spot", {"time": now(), "spot": spot})
            hit = None

            if self.state["trigger_up"] and spot >= self.state["trigger_up"]:
                hit = self.state["trigger_up"]
            elif self.state["trigger_down"] and spot <= self.state["trigger_down"]:
                hit = self.state["trigger_down"]

            cutoff = datetime.strptime(self.config["CUTOFF_TIME"], "%H:%M").time()
            if datetime.now().time() > cutoff:
                hit = None

            if hit:
                already_open = any(t["trigger"] == hit for t in self.state["open_trades"])
                if not already_open:
                    ce = get_option_ltp(kite, hit + self.config["STRIKE_OFFSET"], "CE", self.config["EXPIRY_DATE"])
                    pe = get_option_ltp(kite, hit - self.config["STRIKE_OFFSET"], "PE", self.config["EXPIRY_DATE"])
                    if ce + pe >= self.config["ENTRY_THRESHOLD"]:
                        trade = {
                            "entry_time": now(),
                            "trigger": hit,
                            "spot": spot,
                            "ce": ce,
                            "pe": pe,
                            **self.config
                        }
                        self.state["open_trades"].append(trade)
                        self.log("trades", {**trade, "status": "entry"})

                        self.log("triggers", {"time": now(), "status": "hit", "trigger": hit})
                        other = self.state["trigger_down"] if hit == self.state["trigger_up"] else self.state["trigger_up"]
                        if other:
                            self.log("triggers", {"time": now(), "status": "disabled", "trigger": other})
                        self.state["trigger_up"] = hit + self.config["SUBSEQUENT_TRIGGER_GAP"]
                        self.state["trigger_down"] = hit - self.config["SUBSEQUENT_TRIGGER_GAP"]
                        self.log("triggers", {"time": now(), "status": "setup", "trigger": self.state["trigger_up"]})
                        self.log("triggers", {"time": now(), "status": "setup", "trigger": self.state["trigger_down"]})

            time.sleep(2)
    
    def start(self, kite):
        """Start strategy threads"""
        if self.running:
            return False
        
        self.running = True
        self.set_status(True)
        
        # Start strategy thread
        self.strategy_thread = threading.Thread(target=self.run_strategy, args=(kite,), name=f"strategy_{self.strategy_id}")
        self.strategy_thread.start()
        
        # Start monitor thread
        self.monitor_thread = threading.Thread(target=self.monitor_open_trades, args=(kite,), name=f"monitor_{self.strategy_id}")
        self.monitor_thread.start()
        
        return True
    
    def stop(self):
        """Stop strategy threads"""
        self.running = False
        self.set_status(False)
        
        if self.strategy_thread and self.strategy_thread.is_alive():
            self.strategy_thread.join(timeout=5)
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        return True

# ========== HELPERS ==========
def now():
    return datetime.now().isoformat()

def get_live_spot(kite):
    try:
        data = kite.ltp(["NSE:NIFTY 50"])
        return data["NSE:NIFTY 50"]["last_price"]
    except Exception as e:
        print(f"❌ Could not fetch spot price: {e}")
        return None

def load_nifty_options(kite):
    """Cache NIFTY options at the start of the script."""
    global cached_instruments
    try:
        cached_instruments = [i for i in kite.instruments("NFO") if i["name"] == "NIFTY"]
        print("✅ Cached NIFTY options successfully.")
    except Exception as e:
        print(f"⚠️ Error caching NIFTY options: {e}")
        cached_instruments = []

def convert_to_zerodha_expiry_format(expiry_str):
    try:
        expiry_date = datetime.strptime(expiry_str, "%d-%m-%Y").date()
        return expiry_date.strftime("%d%b%y").upper()
    except ValueError as e:
        print(f"❌ Error converting expiry date: {e}")
        return None

def get_matching_option_symbol(kite, strike, opt_type, expiry_str):
    global cached_instruments

    if cached_instruments is None:
        print("⚠️ NIFTY options are not cached, loading them now...")
        load_nifty_options(kite)

    if cached_instruments is None or len(cached_instruments) == 0:
        print("❌ No NIFTY options found in cache. Exiting.")
        return None

    expiry_zerodha = convert_to_zerodha_expiry_format(expiry_str)
    if not expiry_zerodha:
        return None

    candidates = [
        i for i in cached_instruments
        if i["strike"] == strike and i["instrument_type"] == opt_type
    ]

    for i in candidates:
        if isinstance(i["expiry"], datetime):
            expiry_date = i["expiry"].date()
        else:
            expiry_date = i["expiry"]

        expiry_date_str = expiry_date.strftime("%d%b%y").upper()

        if expiry_date_str == expiry_zerodha:
            return f"NFO:{i['tradingsymbol']}"

    print(f"❌ No match for {strike} {opt_type} {expiry_str}")
    return None

def get_option_ltp(kite, strike, opt_type, expiry_str, retries=3):
    try:
        symbol = get_matching_option_symbol(kite, strike, opt_type, expiry_str)
        if not symbol:
            return 0

        for attempt in range(retries):
            try:
                ltp_data = kite.ltp([symbol])
                return ltp_data[symbol]["last_price"]
            except Exception as e:
                if "Too many requests" in str(e):
                    time.sleep(1.5)
                    continue
                print(f"❌ Error fetching LTP: {e}")
                break
        return 0
    except Exception as e:
        print(f"❌ Critical error in get_option_ltp: {e}")
        return 0

def load_strategies_config():
    """Load strategies configuration from JSON file"""
    if not os.path.exists(STRATEGIES_CONFIG_FILE):
        # Create default configuration if file doesn't exist
        default_config = {
            "strategy_1": {
                "STRATEGY_NAME": "Default Strategy",
                "ENTRY_THRESHOLD": 200,
                "EXIT_PROFIT": 3000,
                "EXIT_MOVE": 180,
                "STRIKE_OFFSET": 100,
                "INITIAL_TRIGGER_GAP": 100,
                "SUBSEQUENT_TRIGGER_GAP": 100,
                "EXPIRY_DATE": "26-06-2025",
                "CUTOFF_TIME": "15:30"
            }
        }
        save_strategies_config(default_config)
        return default_config
    
    try:
        with open(STRATEGIES_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading strategies config: {e}")
        return {}

def save_strategies_config(config):
    """Save strategies configuration to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STRATEGIES_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def trigger_token_refresh():
    """Trigger a token refresh by setting the global flag"""
    global refresh_token_flag
    refresh_token_flag = True
    print("🔄 Token refresh triggered")

def check_token_refresh_trigger():
    """Check if token refresh has been triggered via file"""
    if os.path.exists(TOKEN_REFRESH_FILE):
        try:
            os.remove(TOKEN_REFRESH_FILE)
            print("🔄 Token refresh triggered via file from frontend")
            return True
        except Exception as e:
            print(f"⚠️ Error removing token refresh trigger file: {e}")
    return False

def create_token_refresh_trigger():
    """Create token refresh trigger file (called from frontend)"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOKEN_REFRESH_FILE, 'w') as f:
        f.write(str(datetime.now()))

def initialize_strategies():
    """Initialize all strategy instances"""
    global strategy_instances
    
    strategies_config = load_strategies_config()
    
    for strategy_id, config in strategies_config.items():
        if strategy_id not in strategy_instances:
            strategy_instances[strategy_id] = StrategyInstance(strategy_id, config)
            print(f"✅ Initialized strategy: {strategy_id} - {config.get('STRATEGY_NAME', 'Unnamed')}")

def get_kite_instance():
    """Get KiteConnect instance with credentials from .env"""
    load_dotenv(ENV_FILE)
    config = dotenv_values(ENV_FILE)
    
    api_key ="7l5srg7i4h2lfflb"
    try:
        print("🔄 Refreshing access token from server...")
        response = requests.get("http://hft.administrations.in:9969/token.txt")
        token_response = response.text.strip()
        # Extract token after the "=" sign
        if "KITE_ACCESS_TOKEN=" in token_response:
            access_token = token_response.split("KITE_ACCESS_TOKEN=")[1]
        else:
            access_token = token_response  # Fallback if format is different
        print(f"✅ Access token refreshed successfully: {access_token[:10]}...")
    except Exception as e:
        print(f"❌ Error fetching access token from URL: {e}")
        access_token = config.get("KITE_ACCESS_TOKEN")  # Fallback to .env
    
    if not api_key or not access_token:
        raise ValueError("Missing KITE_API_KEY or KITE_ACCESS_TOKEN in .env file")
    
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite

def initialize_kite_data():
    """Initialize Kite data (instruments, lot size)"""
    global LOT_SIZE, cached_instruments
    
    try:
        kite = get_kite_instance()
        
        # Load instruments and get lot size
        cached_instruments = kite.instruments("NFO")
        for i in cached_instruments:
            if i["tradingsymbol"].startswith("NIFTY") and i["instrument_type"] == "FUT":
                LOT_SIZE = i["lot_size"]
                break
        
        # Filter NIFTY options
        cached_instruments = [i for i in cached_instruments if i["name"] == "NIFTY"]
        print(f"✅ Initialized Kite data. LOT_SIZE: {LOT_SIZE}")
        
    except Exception as e:
        print(f"⚠️ Error initializing Kite data: {e}")
        LOT_SIZE = 75

def strategy_manager():
    """Main strategy manager that monitors and manages all strategies"""
    global refresh_token_flag
    
    kite = get_kite_instance()
    initialize_kite_data()
    
    while True:
        try:
            # Check if token refresh is needed via file trigger or flag
            if refresh_token_flag or check_token_refresh_trigger():
                print("🔄 Refreshing Kite instance due to token refresh request...")
                kite = get_kite_instance()
                initialize_kite_data()
                refresh_token_flag = False
                print("✅ Kite instance refreshed successfully")
            
            # Check each strategy instance
            for strategy_id, strategy in strategy_instances.items():
                current_status = strategy.get_status()
                
                # Start strategy if it should be running but isn't
                if current_status and not strategy.running:
                    print(f"🔁 Starting strategy: {strategy_id}")
                    # Refresh token when starting a strategy
                    print("🔄 Refreshing access token before starting strategy...")
                    kite = get_kite_instance()
                    initialize_kite_data()
                    strategy.start(kite)
                
                # Stop strategy if it shouldn't be running but is
                elif not current_status and strategy.running:
                    print(f"🛑 Stopping strategy: {strategy_id}")
                    strategy.stop()
                
                # Restart dead threads if strategy should be running
                elif current_status and strategy.running:
                    if strategy.strategy_thread and not strategy.strategy_thread.is_alive():
                        print(f"🔄 Restarting strategy thread: {strategy_id}")
                        strategy.strategy_thread = threading.Thread(
                            target=strategy.run_strategy, 
                            args=(kite,), 
                            name=f"strategy_{strategy_id}"
                        )
                        strategy.strategy_thread.start()
                    
                    if strategy.monitor_thread and not strategy.monitor_thread.is_alive():
                        print(f"🔄 Restarting monitor thread: {strategy_id}")
                        strategy.monitor_thread = threading.Thread(
                            target=strategy.monitor_open_trades, 
                            args=(kite,), 
                            name=f"monitor_{strategy_id}"
                        )
                        strategy.monitor_thread.start()
            
            time.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            print(f"❌ Error in strategy manager: {e}")
            time.sleep(10)

# ========== MAIN ==========
if __name__ == "__main__":
    print("🎯 Multi-Strategy Backend initialized.")
    
    # Initialize strategies
    initialize_strategies()
    
    # Start strategy manager
    manager_thread = threading.Thread(target=strategy_manager, name="strategy_manager")
    manager_thread.daemon = True
    manager_thread.start()
    
    print("🚀 Strategy manager started. All systems operational.")
    
    try:
        while True:
            time.sleep(60)  # Keep main thread alive
    except KeyboardInterrupt:
        print("🛑 Shutting down...")
        for strategy in strategy_instances.values():
            strategy.stop()
        print("✅ Shutdown complete.")