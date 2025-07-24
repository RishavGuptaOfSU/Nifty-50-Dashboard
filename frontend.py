import streamlit as st
import os
import json
from datetime import datetime
from dotenv import dotenv_values, set_key
import pandas as pd

# ========= Constants =========
DATA_DIR = "data"
STRATEGIES_CONFIG_FILE = os.path.join(DATA_DIR, "strategies_config.json")

# ========= Helpers =========
def read_jsonl(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath) as f:
        return [json.loads(line) for line in f if line.strip()]

def write_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

def load_config():
    if os.path.exists(STRATEGIES_CONFIG_FILE):
        with open(STRATEGIES_CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(config):
    os.makedirs(DATA_DIR, exist_ok=True)
    write_json(STRATEGIES_CONFIG_FILE, config)

def get_status(strategy_id):
    path = os.path.join(DATA_DIR, f"status_{strategy_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get("running", False)
    return False

def set_status(strategy_id, running):
    path = os.path.join(DATA_DIR, f"status_{strategy_id}.json")
    write_json(path, {"running": running})

# ========= App =========
st.set_page_config(layout="wide")
st.title("📊 Multi-Strategy NIFTY Options Dashboard")

configs = load_config()
strategy_ids = list(configs.keys())

if not strategy_ids:
    st.warning("No strategies found in configuration file.")
    st.stop()

# ========= Strategy Selector =========
selected_id = st.selectbox("Select Strategy", strategy_ids, format_func=lambda x: configs[x].get("STRATEGY_NAME", x))
strategy_config = configs[selected_id]

# ========= Status Control =========
status_col1, status_col2 = st.columns(2)
if status_col1.button("🚀 Start Strategy"):
    set_status(selected_id, True)
    st.success("Started strategy.")
if status_col2.button("🛑 Stop Strategy"):
    set_status(selected_id, False)
    st.warning("Stopped strategy.")

running_status = get_status(selected_id)
st.markdown(f"**Status:** {'🟢 Running' if running_status else '🔴 Stopped'}")

# ========= Configuration Panel =========
st.subheader("⚙️ Strategy Configuration")
with st.form("config_form"):
    updated_config = {}
    for key, val in strategy_config.items():
        if isinstance(val, int):
            updated_config[key] = st.number_input(key, value=val)
        elif isinstance(val, str) and "TIME" in key.upper():
            updated_config[key] = st.text_input(key, value=val)
        else:
            updated_config[key] = st.text_input(key, value=val)

    if st.form_submit_button("💾 Save Configuration"):
        configs[selected_id] = updated_config
        save_config(configs)
        st.success("Configuration updated. Restart strategy to apply.")

# ========= Spot Data =========
st.subheader("📍 Latest Spot Price")
spot_file = os.path.join(DATA_DIR, f"spot_{selected_id}.jsonl")
spot_data = read_jsonl(spot_file)
if spot_data:
    latest = spot_data[-1]
    st.markdown(f"`{round(latest['spot'])}` @ {latest['time'].split('.')[0]}")
else:
    st.info("No spot data available.")

# ========= Triggers =========
st.subheader("📶 Trigger Logs")
trigger_file = os.path.join(DATA_DIR, f"triggers_{selected_id}.jsonl")
triggers = read_jsonl(trigger_file)

if triggers:
    df_triggers = pd.DataFrame(triggers).sort_values("time")
    df_triggers["time"] = df_triggers["time"].str.split(".").str[0]
    latest = df_triggers.drop_duplicates("trigger", keep="last")

    st.markdown("### 🟡 Active")
    st.dataframe(latest[latest["status"] == "setup"], hide_index=True)

    st.markdown("### 🟢 Hit")
    st.dataframe(latest[latest["status"] == "hit"], hide_index=True)

    with st.expander("🔴 Disabled"):
        st.dataframe(latest[latest["status"].isin(["disabled", "cancelled", "failed"])], hide_index=True)
else:
    st.info("No trigger logs available.")

# ========= Open Trades =========
st.subheader("📈 Open Trades")
trades_file = os.path.join(DATA_DIR, f"trades_{selected_id}.jsonl")
trades = read_jsonl(trades_file)

# Group entries and filter closed
closed_keys = {(t["trigger"], t["entry_time"]) for t in trades if t.get("status") == "exit"}
entry_map = {}
for t in trades:
    if t.get("status") == "entry":
        key = (t["trigger"], t["entry_time"])
        entry_map.setdefault(key, []).append(t)

live_trades = []
for key, versions in entry_map.items():
    if key not in closed_keys:
        latest = max(versions, key=lambda x: x.get("time", x["entry_time"]))
        live_trades.append(latest)

if live_trades:
    table = []
    for t in live_trades:
        ce_live = t.get("live_ce", "❌")
        pe_live = t.get("live_pe", "❌")
        try:
            entry_sum = t["ce"] + t["pe"]
            pnl = "⏳"
            if isinstance(ce_live, (int, float)) and isinstance(pe_live, (int, float)):
                pnl_val = round((entry_sum - (ce_live + pe_live)) * 75, 2)
                pnl = f"🟢 {pnl_val}" if pnl_val >= 0 else f"🔴 {pnl_val}"
        except:
            pnl = "⏳"

        table.append({
            "Trigger": t["trigger"],
            "Spot": t["spot"],
            "CE Entry": t["ce"],
            "PE Entry": t["pe"],
            "CE Live": ce_live,
            "PE Live": pe_live,
            "PnL": pnl,
            "Exit Profit": t["EXIT_PROFIT"],
            "Exit Move": t["EXIT_MOVE"],
            "Expiry": t["EXPIRY_DATE"]
        })
    st.dataframe(pd.DataFrame(table), hide_index=True)
else:
    st.info("No open trades.")

# ========= Closed Trades =========
with st.expander("✅ Closed Trades"):
    closed = [t for t in trades if t.get("status") == "exit"]
    if closed:
        df_closed = pd.DataFrame(closed).sort_values("exit_time", ascending=False)
        df_closed["exit_time"] = df_closed["exit_time"].str.split(".").str[0]
        st.dataframe(df_closed.drop(columns=["KITE_API_KEY", "ACCESS_TOKEN"], errors='ignore'), hide_index=True)
        st.download_button("📥 Download Closed", df_closed.to_csv(index=False), "closed_trades.csv")
    else:
        st.info("No closed trades.")
