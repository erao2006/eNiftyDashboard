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

st.set_page_config(page_title="Dhan Monitor", layout="centered")

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
# 3. Data Fetching Architecture (Pure API)
# ----------------------------------------------------
@st.cache_data(ttl=1)  
def fetch_market_snapshot():
    master_data = {"NSE_INDEX": {}, "NSE_FNO": {}}
    index_payload = {"NSE_INDEX": [13]}
    fno_payload = {"NSE_FNO": [40001, 35002]}
    
    # Fetch Index Spot
    try:
        idx_resp = dhan.ohlc_data(securities=index_payload)
        if isinstance(idx_resp, dict) and idx_resp.get("status") == "success":
            st.success("🟢 Dhan Index API successful: 200 OK")
            master_data["NSE_INDEX"] = idx_resp.get("data", {}).get("NSE_INDEX", {})
        else:
            remark = idx_resp.get("remarks") if isinstance(idx_resp, dict) else "Market Closed / Feed Locked"
            st.error(f"🔴 Dhan Index API Status: 400 | {remark}")
    except Exception as e:
        st.error(f"🔴 Dhan Index API Crash: 500 | {e}")
        
    # Fetch Futures and Options Data
    try:
        fno_resp = dhan.quote_data(securities=fno_payload)
        if isinstance(fno_resp, dict) and fno_resp.get("status") == "success":
            st.success("🟢 Dhan FNO API successful: 200 OK")
            master_data["NSE_FNO"] = fno_resp.get("data", {}).get("NSE_FNO", {})
        else:
            remark = fno_resp.get("remarks") if isinstance(fno_resp, dict) else "Market Closed / Offline"
            st.error(f"🔴 Dhan FNO API Status: 400 | {remark}")
    except Exception as e:
        st.error(f"🔴 Dhan FNO API Crash: 500 | {e}")
        
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
            remark = response.get("remarks") if isinstance(response, dict) else "Unauthorized"
            st.error(f"🔴 Dhan Orders API Failed: 401 | {remark}")
    except Exception as e:
        st.error(f"🔴 Dhan Orders API Failed: 500 Connection Error | {e}")
    return pd.DataFrame(columns=['tradingSymbol', 'transactionType', 'quantity', 'price', 'orderStatus'])

# Execute Engine Queries
st.markdown("### 📡 API Connection Logs")
data = fetch_market_snapshot()
orders_df = fetch_orders()

# ----------------------------------------------------
# 4. Real-Time Variable Extraction (No fallbacks)
# ----------------------------------------------------
nifty_spot = data.get("NSE_INDEX", {}).get("13", {}).get("last_price", 0.0)
nifty_fut = data.get("NSE_FNO", {}).get("40001", {}).get("last_price", 0.0)
vix = data.get("NSE_FNO", {}).get("35002", {}).get("last_price", 0.0)

# Calculate levels dynamically if data exists, else default to clean zero bounds
if nifty_spot > 0:
    support = int((nifty_spot // 100) * 100)
    resistance = support + 200
    expiry_range = f"{support} - {resistance}"
else:
    support, resistance = 0, 0
    expiry_range = "0 - 0"

# Set structural tracking values 
pcr = 0.00
advances, declines = 0, 0
breadth = "NEUTRAL"

# ----------------------------------------------------
# 5. UI Custom CSS & Terminal Render Engineering
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
    </style>
    """, 
    unsafe_allow_html=True
)

st.markdown("---")
st.markdown("### 📊 Live Terminal Snapshot")

ist_zone = ZoneInfo("Asia/Kolkata")
current_time = datetime.datetime.now(ist_zone).strftime("%d-%b-%Y %H:%M:%S IST")

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
# 6. Orders Ledger Layout Window
# ----------------------------------------------------
st.markdown("### 📦 Today's Orders")
if not orders_df.empty:
    st.dataframe(orders_df, use_container_width=True, hide_index=True)
else:
    st.info("No active orders found for today.")

st.markdown(f"<div style='padding-left: 5px; color: #666666; font-size: 0.85em; font-family: monospace;'>Updated :<br>{current_time}</div>", unsafe_allow_html=True)
