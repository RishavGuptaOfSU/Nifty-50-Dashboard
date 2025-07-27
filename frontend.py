import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
from dotenv import dotenv_values, set_key
from streamlit_autorefresh import st_autorefresh
from collections import defaultdict

# ========== Setup ==========
st.set_page_config(page_title="Multi-Strategy Options Dashboard", layout="wide")
st_autorefresh(interval=2000, key="refresh")

# ========== Constants ==========
DATA_DIR = "data"
STRATEGIES_CONFIG_FILE = os.path.join(DATA_DIR, "strategies_config.json")
TOKEN_REFRESH_FILE = os.path.join(DATA_DIR, "token_refresh_trigger.txt")

# ========== Helpers ==========
def read_jsonl(filepath):
    """Read JSONL file and return list of parsed JSON objects"""
    if not os.path.exists(filepath):
        return []
    with open(filepath) as f:
        return [json.loads(line) for line in f if line.strip()]

def write_json(filepath, data):
    """Write data to JSON file"""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

def load_strategies_config():
    """Load strategies configuration from JSON file"""
    if os.path.exists(STRATEGIES_CONFIG_FILE):
        with open(STRATEGIES_CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_strategies_config(config):
    """Save strategies configuration to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    write_json(STRATEGIES_CONFIG_FILE, config)

def get_strategy_status(strategy_id):
    """Get running status for a specific strategy"""
    status_file = os.path.join(DATA_DIR, f"status_{strategy_id}.json")
    if os.path.exists(status_file):
        with open(status_file) as f:
            return json.load(f).get("running", False)
    return False

def set_strategy_status(strategy_id, running: bool):
    """Set running status for a specific strategy"""
    status_file = os.path.join(DATA_DIR, f"status_{strategy_id}.json")
    write_json(status_file, {"running": running})

def trigger_token_refresh():
    """Trigger token refresh in backend by creating trigger file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOKEN_REFRESH_FILE, 'w') as f:
        f.write(str(datetime.now()))

def clear_strategy_logs(strategy_id):
    """Clear logs for a specific strategy"""
    spot_file = os.path.join(DATA_DIR, f"spot_{strategy_id}.jsonl")
    triggers_file = os.path.join(DATA_DIR, f"triggers_{strategy_id}.jsonl")
    for file in [spot_file, triggers_file]:
        if os.path.exists(file):
            open(file, "w").close()

def get_strategy_files(strategy_id):
    """Get file paths for a specific strategy"""
    return {
        'trades': os.path.join(DATA_DIR, f"trades_{strategy_id}.jsonl"),
        'triggers': os.path.join(DATA_DIR, f"triggers_{strategy_id}.jsonl"),
        'spot': os.path.join(DATA_DIR, f"spot_{strategy_id}.jsonl"),
        'status': os.path.join(DATA_DIR, f"status_{strategy_id}.json")
    }

# ========== Load Configuration ==========
strategies_config = load_strategies_config()
strategy_ids = list(strategies_config.keys())

# ========== Header ==========
st.title("📊 Multi-Strategy NIFTY Options Dashboard")

# ========== Strategy Management ==========
if not strategy_ids:
    st.warning("⚠️ No strategies found in configuration file. Please add strategies to get started.")
    
    # Create new strategy section
    with st.expander("➕ Create New Strategy"):
        st.subheader("Add New Strategy")
        new_strategy_name = st.text_input("Strategy Name", placeholder="e.g., Conservative Strategy")
        new_strategy_id = st.text_input("Strategy ID", placeholder="e.g., strategy_1")
        
        col1, col2 = st.columns(2)
        with col1:
            new_entry_threshold = st.number_input("CE + PE Entry Threshold", value=200, min_value=0)
            new_exit_profit = st.number_input("Exit Profit", value=3000, min_value=0)
            new_exit_move = st.number_input("Exit Spot Move", value=180, min_value=0)
            new_strike_offset = st.number_input("Strike Offset", value=100, min_value=0)
        with col2:
            new_initial_trigger_gap = st.number_input("Initial Trigger Gap", value=100, min_value=1)
            new_subsequent_trigger_gap = st.number_input("Subsequent Trigger Gap", value=100, min_value=1)
            new_expiry_date = st.text_input("Expiry Date (DD-MM-YYYY)", value="26-06-2025")
            new_cutoff_time = st.text_input("Cutoff Time (HH:MM)", value="15:30")
        
        if st.button("🎯 Create Strategy"):
            if new_strategy_id and new_strategy_name:
                new_config = {
                    "STRATEGY_NAME": new_strategy_name,
                    "ENTRY_THRESHOLD": new_entry_threshold,
                    "EXIT_PROFIT": new_exit_profit,
                    "EXIT_MOVE": new_exit_move,
                    "STRIKE_OFFSET": new_strike_offset,
                    "INITIAL_TRIGGER_GAP": new_initial_trigger_gap,
                    "SUBSEQUENT_TRIGGER_GAP": new_subsequent_trigger_gap,
                    "EXPIRY_DATE": new_expiry_date,
                    "CUTOFF_TIME": new_cutoff_time
                }
                strategies_config[new_strategy_id] = new_config
                save_strategies_config(strategies_config)
                st.success(f"✅ Strategy '{new_strategy_name}' created successfully!")
                st.rerun()
            else:
                st.error("❌ Please provide both Strategy Name and Strategy ID")
    
    st.stop()

# ========== Strategy Selection ==========
st.sidebar.header("🎯 Strategy Selection")
selected_strategy_id = st.sidebar.selectbox(
    "Select Strategy",
    strategy_ids,
    format_func=lambda x: f"{strategies_config[x].get('STRATEGY_NAME', x)} ({x})"
)

strategy_config = strategies_config[selected_strategy_id]
strategy_name = strategy_config.get('STRATEGY_NAME', selected_strategy_id)

# Display selected strategy info
st.sidebar.markdown(f"**Current Strategy:** `{strategy_name}`")
st.sidebar.markdown(f"**Strategy ID:** `{selected_strategy_id}`")

# ========== Strategy Configuration ==========
st.sidebar.header("⚙️ Strategy Configuration")

with st.sidebar.form("config_form"):
    st.markdown(f"**Configuring: {strategy_name}**")
    
    updated_config = {}
    updated_config["STRATEGY_NAME"] = st.text_input("Strategy Name", value=strategy_config.get("STRATEGY_NAME", ""))
    updated_config["ENTRY_THRESHOLD"] = st.number_input("CE + PE Entry Threshold", value=strategy_config.get("ENTRY_THRESHOLD", 200))
    updated_config["EXIT_PROFIT"] = st.number_input("Exit Profit", value=strategy_config.get("EXIT_PROFIT", 3000))
    updated_config["EXIT_MOVE"] = st.number_input("Exit Spot Move", value=strategy_config.get("EXIT_MOVE", 180))
    updated_config["STRIKE_OFFSET"] = st.number_input("Strike Offset", value=strategy_config.get("STRIKE_OFFSET", 100))
    updated_config["INITIAL_TRIGGER_GAP"] = st.number_input("Initial Trigger Gap", value=strategy_config.get("INITIAL_TRIGGER_GAP", 100))
    updated_config["SUBSEQUENT_TRIGGER_GAP"] = st.number_input("Subsequent Trigger Gap", value=strategy_config.get("SUBSEQUENT_TRIGGER_GAP", 100))
    updated_config["EXPIRY_DATE"] = st.text_input("Expiry Date (DD-MM-YYYY)", value=strategy_config.get("EXPIRY_DATE", "26-06-2025"))
    updated_config["CUTOFF_TIME"] = st.text_input("Cutoff Time (HH:MM)", value=strategy_config.get("CUTOFF_TIME", "15:30"))
    
    if st.form_submit_button("💾 Save Configuration"):
        strategies_config[selected_strategy_id] = updated_config
        save_strategies_config(strategies_config)
        st.success("✅ Configuration saved! Restart strategy to apply changes.")

# ========== Strategy Control Panel ==========
st.subheader(f"🎮 Control Panel - {strategy_name}")

# Get strategy status
is_running = get_strategy_status(selected_strategy_id)
status_emoji = "🟢" if is_running else "🔴"
status_text = "Running" if is_running else "Stopped"

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button(f"🚀 Start {strategy_name}"):
        # Trigger token refresh before starting strategy
        trigger_token_refresh()
        set_strategy_status(selected_strategy_id, True)
        st.success(f"✅ Strategy '{strategy_name}' started with fresh access token!")
        st.rerun()

with col2:
    if st.button(f"🛑 Stop {strategy_name}"):
        set_strategy_status(selected_strategy_id, False)
        st.warning(f"🛑 Strategy '{strategy_name}' stopped!")
        st.rerun()

with col3:
    if st.button(f"🧹 Clear Logs"):
        clear_strategy_logs(selected_strategy_id)
        st.success(f"✅ Logs cleared for '{strategy_name}'!")

with col4:
    st.markdown(f"**Status:** {status_emoji} {status_text}")

# ========== Strategy Files ==========
files = get_strategy_files(selected_strategy_id)

# ========== Current Spot Price ==========
st.subheader("📍 Latest Spot Price")
spot_logs = read_jsonl(files['spot'])
if spot_logs:
    latest_spot = spot_logs[-1]
    spot_time = latest_spot['time'].split(".")[0]
    col1, col2 = st.columns(2)
    with col1:
        st.metric("NIFTY Spot", f"{round(latest_spot['spot'])}")
    with col2:
        st.caption(f"Last updated: {spot_time}")
else:
    st.info(f"No spot data available for {strategy_name}")

# ========== Trigger Status ==========
st.subheader("📶 Trigger Status")
trigger_logs = read_jsonl(files['triggers'])

if trigger_logs:
    df_triggers = pd.DataFrame(trigger_logs).sort_values("time")
    df_triggers["time"] = df_triggers["time"].str.split(".").str[0]
    latest_triggers = df_triggers.drop_duplicates("trigger", keep="last")

    # Count different trigger statuses
    active_count = len(latest_triggers[latest_triggers["status"] == "setup"])
    hit_count = len(latest_triggers[latest_triggers["status"] == "hit"])
    disabled_count = len(latest_triggers[latest_triggers["status"].isin(["cancelled", "disabled", "failed"])])

    # Display counts in columns
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🟡 Active Triggers", active_count)
    with col2:
        st.metric("🟢 Hit Triggers", hit_count)
    with col3:
        st.metric("🔴 Disabled Triggers", disabled_count)

    # Show detailed trigger information
    active_triggers = latest_triggers[latest_triggers["status"] == "setup"]
    hit_triggers = latest_triggers[latest_triggers["status"] == "hit"]
    disabled_triggers = latest_triggers[latest_triggers["status"].isin(["cancelled", "disabled", "failed"])]

    tab1, tab2, tab3 = st.tabs(["🟡 Active", "🟢 Hit", "🔴 Disabled"])
    
    with tab1:
        if not active_triggers.empty:
            st.dataframe(active_triggers[["trigger", "time", "status"]], hide_index=True, use_container_width=True)
        else:
            st.info("No active triggers")

    with tab2:
        if not hit_triggers.empty:
            st.dataframe(hit_triggers[["trigger", "time", "status"]], hide_index=True, use_container_width=True)
        else:
            st.info("No hit triggers")

    with tab3:
        if not disabled_triggers.empty:
            st.dataframe(disabled_triggers[["trigger", "time", "status"]], hide_index=True, use_container_width=True)
        else:
            st.info("No disabled triggers")

else:
    st.info(f"No trigger data available for {strategy_name}")

# ========== Open Trades Management ==========
st.subheader("📈 Open Trades Management")
trades = read_jsonl(files['trades'])

# Identify open trades
closed_keys = {(t["trigger"], t["entry_time"]) for t in trades if t.get("status") == "exit"}
entry_map = defaultdict(list)
for t in trades:
    if t.get("status") == "entry":
        entry_map[(t["trigger"], t["entry_time"])].append(t)

live_trades = []
for key, versions in entry_map.items():
    if key not in closed_keys:
        latest = max(versions, key=lambda x: x.get("time", x.get("entry_time", "")))
        live_trades.append(latest)

if live_trades:
    st.markdown(f"**{len(live_trades)} Open Trade(s) for {strategy_name}**")
    
    # Trade modification section
    with st.expander("✏️ Modify Trade Exit Parameters"):
        for i, trade in enumerate(live_trades):
            st.markdown(f"**Trade #{i+1}: Trigger `{trade['trigger']}` (Entry: {trade['entry_time'].split('.')[0]})**")
            
            col1, col2, col3 = st.columns([2, 2, 2])
            with col1:
                new_exit_profit = st.number_input(
                    "Exit Profit", 
                    value=int(trade.get("EXIT_PROFIT", 3000)), 
                    key=f"ep_{selected_strategy_id}_{i}"
                )
            with col2:
                new_exit_move = st.number_input(
                    "Exit Move", 
                    value=int(trade.get("EXIT_MOVE", 180)), 
                    key=f"em_{selected_strategy_id}_{i}"
                )
            with col3:
                if st.button(f"💾 Update Trade", key=f"up_{selected_strategy_id}_{i}"):
                    # Update trade parameters
                    updated_trade = trade.copy()
                    updated_trade["EXIT_PROFIT"] = new_exit_profit
                    updated_trade["EXIT_MOVE"] = new_exit_move
                    updated_trade["time"] = datetime.now().isoformat()
                    
                    # Append updated trade to file
                    with open(files['trades'], "a") as f:
                        f.write(json.dumps(updated_trade) + "\n")
                    
                    st.success(f"✅ Trade parameters updated for trigger {trade['trigger']}")
                    st.rerun()
            
            st.divider()

    # Live trades overview
    display_rows = []
    total_pnl = 0
    profitable_trades = 0
    
    for trade in live_trades:
        ce_live = trade.get("live_ce", "❌")
        pe_live = trade.get("live_pe", "❌")
        
        # Calculate PnL
        try:
            entry_sum = trade["ce"] + trade["pe"]
            if isinstance(ce_live, (int, float)) and isinstance(pe_live, (int, float)):
                live_sum = ce_live + pe_live
                pnl = round((entry_sum - live_sum) * 75, 2)
                pnl_display = f"🟢 ₹{pnl}" if pnl >= 0 else f"🔴 ₹{pnl}"
                total_pnl += pnl
                if pnl >= 0:
                    profitable_trades += 1
            else:
                pnl_display = "⏳ Calculating..."
        except:
            pnl_display = "⏳ Calculating..."

        display_rows.append({
            "Trigger": trade["trigger"],
            "Entry Spot": trade["spot"],
            "CE Entry": f"₹{trade['ce']}",
            "PE Entry": f"₹{trade['pe']}",
            "CE Live": f"₹{ce_live}" if isinstance(ce_live, (int, float)) else ce_live,
            "PE Live": f"₹{pe_live}" if isinstance(pe_live, (int, float)) else pe_live,
            "P&L": pnl_display,
            "Exit Profit": f"₹{trade.get('EXIT_PROFIT', 'N/A')}",
            "Exit Move": f"{trade.get('EXIT_MOVE', 'N/A')} pts",
            "Expiry": trade.get("EXPIRY_DATE", "N/A")
        })

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Open Trades", len(live_trades))
    with col2:
        st.metric("Profitable Trades", profitable_trades)
    with col3:
        if total_pnl != 0:
            st.metric("Total P&L", f"₹{total_pnl:,.2f}", delta=f"₹{total_pnl:,.2f}")
        else:
            st.metric("Total P&L", "Calculating...")
    with col4:
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # Trades table
    st.markdown("#### 📋 Live Trades Overview")
    st.dataframe(pd.DataFrame(display_rows), hide_index=True, use_container_width=True)

else:
    st.info(f"No open trades for {strategy_name}")

# ========== Closed Trades Analysis ==========
with st.expander("✅ Closed Trades Analysis"):
    closed_trades = [t for t in trades if t.get("status") == "exit"]
    
    if closed_trades:
        df_closed = pd.DataFrame(closed_trades).sort_values("exit_time", ascending=False)
        df_closed["exit_time"] = df_closed["exit_time"].str.split(".").str[0]
        df_closed["entry_time"] = df_closed["entry_time"].str.split(".").str[0]
        
        # Remove sensitive columns
        display_columns = [col for col in df_closed.columns if col not in ["KITE_API_KEY", "ACCESS_TOKEN"]]
        df_display = df_closed[display_columns]
        
        # Summary statistics
        total_closed = len(closed_trades)
        profitable_closed = len([t for t in closed_trades if t.get("pnl", 0) >= 0])
        total_pnl_closed = sum([t.get("pnl", 0) for t in closed_trades])
        avg_pnl = total_pnl_closed / total_closed if total_closed > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Closed", total_closed)
        with col2:
            st.metric("Profitable", profitable_closed)
        with col3:
            st.metric("Win Rate", f"{(profitable_closed/total_closed)*100:.1f}%" if total_closed > 0 else "0%")
        with col4:
            st.metric("Avg P&L", f"₹{avg_pnl:,.2f}")
        
        st.metric("Total P&L (Closed)", f"₹{total_pnl_closed:,.2f}")
        
        st.dataframe(df_display, hide_index=True, use_container_width=True)
        
        # Download option
        csv = df_display.to_csv(index=False)
        st.download_button(
            "📥 Download Closed Trades CSV",
            csv,
            f"closed_trades_{selected_strategy_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv"
        )
    else:
        st.info(f"No closed trades for {strategy_name}")

# ========== Strategy Management ==========
with st.expander("🛠️ Strategy Management"):
    st.subheader("Manage Strategies")
    
    # Add new strategy
    st.markdown("#### ➕ Add New Strategy")
    col1, col2 = st.columns(2)
    
    with col1:
        new_strategy_name = st.text_input("New Strategy Name", placeholder="e.g., Aggressive Strategy")
        new_strategy_id = st.text_input("New Strategy ID", placeholder="e.g., strategy_2")
    
    with col2:
        copy_from = st.selectbox("Copy settings from", ["Create blank"] + strategy_ids)
        
    if st.button("🎯 Create New Strategy"):
        if new_strategy_id and new_strategy_name and new_strategy_id not in strategies_config:
            if copy_from == "Create blank":
                new_config = {
                    "STRATEGY_NAME": new_strategy_name,
                    "ENTRY_THRESHOLD": 200,
                    "EXIT_PROFIT": 3000,
                    "EXIT_MOVE": 180,
                    "STRIKE_OFFSET": 100,
                    "INITIAL_TRIGGER_GAP": 100,
                    "SUBSEQUENT_TRIGGER_GAP": 100,
                    "EXPIRY_DATE": "26-06-2025",
                    "CUTOFF_TIME": "15:30"
                }
            else:
                new_config = strategies_config[copy_from].copy()
                new_config["STRATEGY_NAME"] = new_strategy_name
            
            strategies_config[new_strategy_id] = new_config
            save_strategies_config(strategies_config)
            st.success(f"✅ Strategy '{new_strategy_name}' created successfully!")
            st.rerun()
        else:
            if not new_strategy_id or not new_strategy_name:
                st.error("❌ Please provide both Strategy Name and Strategy ID")
            elif new_strategy_id in strategies_config:
                st.error("❌ Strategy ID already exists")
    
    # Delete strategy
    st.markdown("#### 🗑️ Delete Strategy")
    delete_strategy = st.selectbox("Select strategy to delete", ["Select strategy..."] + strategy_ids)
    
    if delete_strategy != "Select strategy...":
        st.warning(f"⚠️ This will permanently delete strategy '{strategies_config[delete_strategy]['STRATEGY_NAME']}' and all its data!")
        
        if st.button(f"🗑️ Confirm Delete '{strategies_config[delete_strategy]['STRATEGY_NAME']}'", type="primary"):
            # Remove from config
            del strategies_config[delete_strategy]
            save_strategies_config(strategies_config)
            
            # Clean up files
            files_to_delete = get_strategy_files(delete_strategy)
            for file_path in files_to_delete.values():
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            st.success(f"✅ Strategy deleted successfully!")
            st.rerun()

# ========== Footer ==========
st.markdown("---")
st.markdown(f"**Dashboard for Strategy:** `{strategy_name}` | **Strategy ID:** `{selected_strategy_id}` | **Last Refresh:** {datetime.now().strftime('%H:%M:%S')}")