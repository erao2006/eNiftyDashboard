import datetime
import pandas as pd
import streamlit as st
from dhanhq import dhanhq, DhanContext
from zoneinfo import ZoneInfo
import logging

# ----------------------------------------------------
# 1. Global Page Configuration
# ----------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Dhan Monitor & Portfolio", layout="centered")

# ----------------------------------------------------
# 2. Authentication Setup via Secrets
# ----------------------------------------------------
try:
    CLIENT_ID = st.secrets["DHAN_CLIENT_ID"]
    ACCESS_TOKEN = st.secrets["DHAN_ACCESS_TOKEN"]
except Exception:
    CLIENT_ID = "YOUR_DHAN_CLIENT_ID"
    ACCESS_TOKEN = "YOUR_DHAN_ACCESS_TOKEN"

try:
    dhan_context = DhanContext(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)
    dhan = dhanhq(dhan_context)
except Exception as init_err:
    st.error(f"🔴 System Configuration Error | Initialization Failed: {init_err}")
    st.stop()

# ----------------------------------------------------
# 3. Direct Native SDK Engine (Handles Headers Internally)
# ----------------------------------------------------
@st.cache_data(ttl=5)  # Keeps a 5-second cache window to guarantee no 429 rate limit resets
def fetch_market_snapshot():
    master_data = {"NIFTY_SPOT": 0.0, "NIFTY_FUTURE": 0.0}
    
    try:
        # Define target instruments as list of tuples: [(ExchangeSegment, SecurityId)]
        # This native format forces the SDK to structure headers correctly
        instruments = [
            ("IDX_I", "13"),      # Nifty 50 Spot
            ("NSE_FNO", "52175")  # Active Nifty Future Contract ID
        ]
        
        response = dhan.get_ltp(instruments)
        
        if isinstance(response, dict) and response.get("status") == "success":
            st.success("🟢 Market Feed Ticker API: 200 OK")
            data_map = response.get("data", {})
            
            # Extract data using the native library's index string format
            master_data["NIFTY_SPOT"] = float(data_map.get("IDX_I:13", {}).get("last_price", 0.0))
            master_data["NIFTY_FUTURE"] = float(data_map.get("NSE_FNO:52175", {}).get("last_price", 0.0))
        else:
            st.error(f"🔴 Ticker Feed Refusal: {response.get('remarks') if isinstance(response, dict) else 'Invalid response format'}")
    except Exception as e:
        st.error(f"🔴 Market Connection failed: {e}")
        
    return master_data

def fetch_orders():
    try:
        response = dhan.get_order_list()
        if isinstance(response, dict) and response.get("status") == "success":
            st.success("🟢 Dhan Orders API successful: 200 OK")
            orders = response.get("data", []) if response.get("data") else []
            df = pd.DataFrame(orders)
            columns_to_keep = ['tradingSymbol', 'transactionType', 'orderType', 'quantity', 'price', 'orderStatus']
            available_cols = [col for col in columns_to_keep if col in df.columns]
            return df[available_cols]
        else:
            remark = response.get("remarks") if isinstance(response, dict) else "Unauthorized Session"
            st.error(f"🔴 Dhan Orders API Failed: {remark}")
    except Exception as e:
        st.error(f"🔴 Dhan Orders API Failed: 500 Connection Error | {e}")
    return pd.DataFrame(columns=['tradingSymbol', 'transactionType', 'orderType', 'quantity', 'price', 'orderStatus'])

def fetch_positions():
    try:
        response = dhan.get_positions()
        if isinstance(response, dict) and response.get("status") == "success":
            st.success("🟢 Dhan Positions API successful: 200 OK")
            positions = response.get("data", []) if response.get("data") else []
            df = pd.DataFrame(positions)
            columns_to_keep = [
                'tradingSymbol', 'positionType', 'netQty', 'buyAvg', 'sellAvg', 
                'realizedProfit', 'unrealizedProfit'
            ]
            available_cols = [col for col in columns_to_keep if col in df.columns]
            return df[available_cols]
        else:
            remark = response.get("remarks") if isinstance(response, dict) else "Unauthorized Session"
            st.error(f"🔴 Dhan Positions API Failed: {remark}")
    except Exception as e:
        st.error(f"🔴 Dhan Positions API Failed: 500 Connection Error | {e}")
    return pd.DataFrame(columns=['tradingSymbol', 'positionType', 'netQty', 'buyAvg', 'sellAvg', 'realizedProfit', 'unrealizedProfit'])

# Execute Network Engine Operations
st.markdown("### 📡 API Connection Logs")
market_data = fetch_market_snapshot()
orders_df = fetch_orders()
positions_df = fetch_positions()

# ----------------------------------------------------
# 4. Market Metric Assignment
# ----------------------------------------------------
nifty_spot = market_data["NIFTY_SPOT"]
nifty_fut = market_data["NIFTY_FUTURE"]
vix = 0.0  

if nifty_spot > 0:
    support = int((nifty_spot // 100) * 100)
    resistance = support + 200
    expiry_range = f"{support} - {resistance}"
else:
    support, resistance = 0, 0
    expiry_range = "0 - 0"

pcr = 0.00
advances, declines = 0, 0
breadth = "NEUTRAL"

# ----------------------------------------------------
# 5. UI Custom CSS & Theme Injection
# ----------------------------------------------------
st.markdown(
    """
    <style>
    .reportview-container { background: #121212; }
    .terminal-box {
        background-color: #1E1E1E;
        font-family: 'Courier New', Courier, monospace;
        color: #E0E0E0;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #333333;
        line-height: 1.6;
        margin-bottom: 10px;
    }
    .terminal-row {
        display: flex;
        justify-content: space-between;
        border-bottom: 1px dashed #444444;
        padding: 6px 0;
    }
    .terminal-row:last-child { border-bottom: none; }
    .label { font-weight: bold; color: #888888; }
    .value { font-weight: bold; color: #00FF66; }
    .value-neutral { font-weight: bold; color: #F1C40F; }
    .pnl-box {
        padding: 16px;
        border-radius: 12px;
        font-family: monospace;
        font-weight: bold;
        font-size: 1.2em;
        margin-bottom: 20px;
        text-align: center;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.3);
    }
    </style>
    """, 
    unsafe_allow_html=True
)

st.markdown("---")

# ----------------------------------------------------
# 6. Live Market Terminal Block
# ----------------------------------------------------
st.markdown("### 📊 Live Terminal Snapshot")
terminal_html = f"""
<div class="terminal-box">
    <div class="terminal-row">
        <span class="label">NIFTY</span>
        <span class="value">{nifty_spot:,.2f}</span>
    </div>
    <div class="terminal-row">
        <span class="label">FUTURE</span>
        <span class="value">{nifty_fut:,.2f}</span>
    </div>
</div>

<div class="terminal-box">
    <div class="terminal-row">
        <span class="label">ADV / DEC</span>
        <span class="value-neutral">{advances} / {declines}</span>
    </div>
</div>

<div class="terminal-box">
    <div class="terminal-row">
        <span class="label">PCR</span>
        <span class="value-neutral">{pcr:.2f}</span>
    </div>
    <div class="terminal-row">
        <span class="label">VIX</span>
        <span class="value-neutral">{vix:.1f}</span>
    </div>
</div>

<div class="terminal-box">
    <div class="terminal-row">
        <span class="label">SUPPORT</span>
        <span class="value">{support}</span>
    </div>
    <div class="terminal-row">
        <span class="label">RESISTANCE</span>
        <span class="value">{resistance}</span>
    </div>
</div>

<div class="terminal-box">
    <div class="terminal-row">
        <span class="label">EXPIRY RANGE</span>
        <span class="value-neutral">{expiry_range}</span>
    </div>
</div>

<div class="terminal-box">
    <div class="terminal-row">
        <span class="label">BREADTH</span>
        <span class="value" style="color: #00FF66;">: {breadth}</span>
    </div>
</div>
"""
st.markdown(terminal_html, unsafe_allow_html=True)

# ----------------------------------------------------
# 7. Portfolio P&L Summary Banner
# ----------------------------------------------------
st.markdown("### 📈 Cumulative Performance P&L")
if not orders_df.empty or not positions_df.empty:
    realized = pd.to_numeric(positions_df['realizedProfit'], errors='coerce').fillna(0.0).sum() if not positions_df.empty else 0.0
    unrealized = pd.to_numeric(positions_df['unrealizedProfit'], errors='coerce').fillna(0.0).sum() if not positions_df.empty else 0.0
    total_pnl = realized + unrealized
    
    if total_pnl >= 0:
        st.markdown(f'<div class="pnl-box" style="background-color: #0A2F1D; color: #00FF66; border: 1px solid #00FF66;">TOTAL P&L: ₹{total_pnl:,.2f}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="pnl-box" style="background-color: #3A1414; color: #FF4D4D; border: 1px solid #FF4D4D;">TOTAL P&L: ₹{total_pnl:,.2f}</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="pnl-box" style="background-color: #1E1E1E; color: #E0E0E0; border: 1px solid #333333;">TOTAL P&L: ₹0.00</div>', unsafe_allow_html=True)

# ----------------------------------------------------
# 8. Positions & Orders Ledger Displays
# ----------------------------------------------------
st.markdown("### 💼 Open Positions Details")
if not positions_df.empty:
    st.dataframe(positions_df, width='stretch', hide_index=True)
else:
    st.info("No active open positions found.")

st.markdown("### 📦 Today's Order Book")
if not orders_df.empty:
    st.dataframe(orders_df, width='stretch', hide_index=True)
else:
    st.info("No orders processed today.")

# Sync Footer
ist_zone = ZoneInfo("Asia/Kolkata")
current_time = datetime.datetime.now(ist_zone).strftime("%d-%b-%Y %H:%M:%S IST")
st.markdown(f"<div style='padding-left: 2px; color: #666666; font-size: 0.85em; font-family: monospace; margin-top: 25px;'>Last Sync: {current_time}</div>", unsafe_allow_html=True)
