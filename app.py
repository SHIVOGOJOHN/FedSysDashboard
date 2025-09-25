import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

LEDGER = Path('data/ledger.json')

# Initialize session state
if 'last_reset' not in st.session_state:
    st.session_state['last_reset'] = time.time()
if 'auto_refresh' not in st.session_state:
    st.session_state['auto_refresh'] = True

st.set_page_config(page_title="FL Audit Dashboard", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for modern look
st.markdown("""
    <style>
        .stButton > button {
            background-color: #4CAF50;
            color: white;
            border-radius: 5px;
            border: none;
            padding: 10px 24px;
        }
        .metric-card {
            background-color: #1E1E1E;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 2px 2px 10px rgba(0,0,0,0.2);
            color: white !important;
        }
        .metric-card > div {
            color: white !important;
        }
        .metric-card label {
            color: #E0E0E0 !important;
        }
        [data-testid="stMetricValue"] > div {
            color: #4CAF50 !important;
            font-size: 2rem !important;
        }
        [data-testid="stMetricDelta"] > div {
            color: #64B5F6 !important;
        }
        .css-1v0mbdj.e115fcil1 {
            width: 100%;
            border-radius: 10px;
            margin-top: 10px;
        }
        h1 {
            color: #1E88E5;
            font-weight: bold;
        }
        h3 {
            color: #424242;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🔄 Federated Learning Audit Dashboard")
st.markdown("**Real-time monitoring of federated learning rounds and node performance**")

def truncate_hash(hash_string, start_chars=8, end_chars=8):
    """Truncates a hash string for display purposes."""
    if isinstance(hash_string, str) and len(hash_string) > start_chars + end_chars:
        return f"{hash_string[:start_chars]}...{hash_string[-end_chars:]}"
    return hash_string

def load_ledger():
    if not LEDGER.exists():
        return []
    try:
        with open(LEDGER, 'r') as f:
            # Handle empty file case
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        time.sleep(0.1)  # Wait briefly if file is being written or created
        try:
            with open(LEDGER, 'r') as f:
                content = f.read()
                if not content:
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            return []


def ledger_to_df(ledger):
    if not ledger:
        return pd.DataFrame()
    
    rows = []
    for entry in ledger:
        row = {
            "round": entry["round"],
            "timestamp": entry["timestamp"],
            "global_accuracy": entry["global_accuracy"],
            "ipfs_hash": entry["ipfs_hash"],
            "block_tx": entry["block_tx"],
            "notes": entry.get("notes", ""),
        }
        prefixed_node_accuracies = {f"Store_{k}": v for k, v in entry["node_accuracies"].items()}
        row.update(prefixed_node_accuracies)
        rows.append(row)
    
    df = pd.DataFrame(rows)
    return df.sort_values("round").reset_index(drop=True)

@st.cache_data(ttl=1) # Reduce TTL for more 'live' feel
def get_cached_data():
    ledger = load_ledger()
    return ledger_to_df(ledger)


# --- Dashboard Rendering ---
def render_dashboard_content(df, rounds_to_show):
    """Renders the main dashboard content."""
    if df.empty:
        st.warning("No rounds in ledger yet. Connect or turn on your aggregator.")
        return

    # Filter the dataframe to show only the last N rounds
    df = df.tail(rounds_to_show)

    # Create a display-friendly copy with truncated hashes
    df_display = df.copy()
    df_display['ipfs_hash'] = df_display['ipfs_hash'].apply(truncate_hash)
    df_display['block_tx'] = df_display['block_tx'].apply(truncate_hash)

    # Rename Business_UUID columns to Store_A, Store_B, etc.
    business_cols = [col for col in df_display.columns if col.startswith('Store_')]
    rename_map = {}
    for i, col in enumerate(business_cols):
        rename_map[col] = f"Store_{chr(65 + i)}"
    df_display = df_display.rename(columns=rename_map)

    # Top KPIs
    latest = df.iloc[-1]
    st.markdown("### 📊 Key Performance Metrics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Current Round", int(latest.get("round", 0)), delta="+1" if not df.empty else "")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        prev_acc = df.iloc[-2]["global_accuracy"] if len(df) > 1 else latest["global_accuracy"]
        delta = (latest["global_accuracy"] - prev_acc) * 100
        st.metric("Global Accuracy", f"{latest['global_accuracy']*100:.2f}%", f"{delta:+.2f}%")
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        node_columns = [col for col in latest.index if col.startswith('Store_')]
        st.metric("Active Nodes", len(node_columns))
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.write("Last Update")
        timestamp = latest.get("timestamp", "")
        st.caption(timestamp.split("T")[1].split(".")[0] if "T" in timestamp else timestamp)
        st.markdown('</div>', unsafe_allow_html=True)

    # Performance Charts
    st.markdown("### 📈 Performance Analysis")
    tab1, tab2 = st.tabs(["📈 Accuracy Trends", "📋 Round Details"])

    with tab1:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("#### Global Accuracy Trend")
            acc_df = df[["round", "global_accuracy"]].set_index("round")
            st.line_chart(acc_df, height=300)

            st.info("**How to Determine the Optimal Number of Rounds:**\n\n" 
                    "1. **Watch this chart:** This shows the global model's accuracy improving over time.\n" 
                    "2. **Look for the plateau:** The ideal number of rounds is where the curve starts to flatten, and the accuracy no longer increases significantly. This is the point of diminishing returns.\n" 
                    "3. **Balance Cost vs. Accuracy:** Stopping at the plateau prevents running unnecessary rounds, saving time and computational cost.")

        with col2:
            st.markdown("#### Node Performance (Round 10)")
            round_10_data = df[df['round'] == 10]
            if not round_10_data.empty:
                round_10_latest = round_10_data.iloc[-1]
                node_columns = [col for col in round_10_latest.index if col.startswith('Store_')]
                node_accuracies = {col: round_10_latest.get(col) for col in node_columns}

                # Map UUIDs to simpler names for display
                node_name_map = {}
                for i, col in enumerate(node_columns):
                    node_name_map[col] = f"Store_{chr(65 + i)}"

                performance_data = []
                for col, acc in node_accuracies.items():
                    if pd.notnull(acc):
                        performance_data.append({'Node': node_name_map.get(col, col), 'Accuracy': acc})

                performance_df = pd.DataFrame(performance_data)
                if not performance_df.empty:
                    st.bar_chart(data=performance_df.set_index('Node'), height=300)
                else:
                    st.info("No node performance data available for Round 10.")
            else:
                st.info("Round 10 data not yet available in the ledger.")

    with tab2:
        st.markdown("#### Detailed Round Information")
        display_cols = ["round", "timestamp", "global_accuracy", "ipfs_hash", "block_tx", "notes"]
        st.dataframe(
            df_display[display_cols].style.format({"global_accuracy": "{:.2%}"}).background_gradient(subset=["global_accuracy"]),
            height=300
        )

    # Node Analysis
    st.markdown("### 🔍 Node Analysis")
    node_tab1, node_tab2 = st.tabs(["📊 Performance Matrix", "🔗 Blockchain Info"])

    with node_tab1:
        node_columns = [col for col in df_display.columns if col.startswith('Store_')]
        st.dataframe(
            df_display.style.background_gradient(subset=node_columns),
            height=260
        )

    with node_tab2:

            st.markdown("#### ⛓️ Blockchain Transaction")
            # Get the full block_tx for the link
            full_block_tx = "0x008a3ef87cb15c2490b8e3029a356812b217e8c2e49389c62945eb125a25722a"
            if full_block_tx:
                etherscan_link = f"https://sepolia.etherscan.io/tx/{full_block_tx}"
                st.markdown(f"[View Transaction on Etherscan]({etherscan_link})")
            else:
                st.write("No transaction recorded for this round.")

# --- Main App Logic ---
placeholder = st.empty()

# Initial render
df = get_cached_data()
with placeholder.container():
    render_dashboard_content(df, rounds_to_show)

# Live update loop
if st.session_state.auto_refresh:
    while True:
        time.sleep(5) # Refresh interval
        df = get_cached_data()
        with placeholder.container():
            render_dashboard_content(df, rounds_to_show)
