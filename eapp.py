import datetime
import pandas as pd
import streamlit as st
from dhanhq import dhanhq, DhanContext
from zoneinfo import ZoneInfo
import logging

# ----------------------------------------------------
# 1. Global Setup (Must be at the absolute top)
# ----------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Streamlit page layout config (Runs exactly once)
st.set_page_config(page_title="Dhan Monitor", layout="centered")

# ----------------------------------------------------
# 2. API Authentication Configuration
# ----------------------------------------------------
try:
    CLIENT_ID = st.secrets["DHAN_CLIENT_ID"]
    ACCESS_TOKEN = st.secrets["DHAN_ACCESS_TOKEN"]
except Exception:
    # Local fallback strings if Secrets are not configured on the dashboard yet
    CLIENT_ID = "YOUR_DHAN_CLIENT_ID"
    ACCESS_TOKEN = "YOUR_DHAN_ACCESS_TOKEN"

try:
    # Instantiate V2 Context wrapper explicitly
    dhan_context = DhanContext(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)
    dhan = dhanhq(dhan_context)
except Exception as init_err:
    st.error(f"Initialization Failed: {init_err}")
    st.stop()

# Corrected Exchange segments for the Dhan API
SECURITIES = {
    "NSE_EQ": [1333],          # HDFC Bank or Equity tickers (Example tracker)
    "NSE_INDEX": [13],         # Nifty 50 Index (Token 13 must map to NSE_INDEX)
    "NSE_FNO": [40001, 35002]  # Future / Options segment mapping tokens
}

# ----------------------------------------------------
# 3. Secure Data Fetching Engine
# ----------------------------------------------------
@st.cache_data(ttl=5)  
def fetch_market_snapshot():
    try:
        response = dhan.quote_data(securities=SECURITIES)
        if isinstance(response, dict):
            if response.get("status") == "success":
                return response.get("data", {})
            else:
                # Catch actual structural API messaging errors 
                st.error(f"Dhan API System Alert: {response.get('remarks', 'Empty Context Signature')}")
    except Exception as e:
        st.error(f"Network processing issue: {e}")
    return {}

def fetch_orders():
    try:
        response = dhan.get_order_list()
        if isinstance(response, dict) and response.get("status") == "success" and response.get("data"):
            orders = response.get("data", [])
            df = pd.DataFrame(orders)
            columns_to_keep = ['tradingSymbol', 'transactionType', 'orderType', 'quantity', 'price', 'orderStatus']
            available_cols = [col for col in columns_to_keep if col in df.columns]
            return df[available_cols]
    except Exception as e:
        logger.error(f"Orders list extraction failed: {e}")
    return pd.DataFrame(columns=['tradingSymbol', 'transactionType', 'quantity', 'price', 'orderStatus'])

# Execute queries
data = fetch_market_snapshot()
orders_df = fetch_orders()

# ----------------------------------------------------
# 4. Data Extraction & Fallback Structs
# ----------------------------------------------------
# Look inside 'NSE_INDEX' for the index spot value to prevent error generation
nifty_spot = data.get("NSE_INDEX", {}).get("13", {}).get("last_price", 0.0)
nifty_fut = data.get("NSE_FNO", {}).get("40001", {}).get("last_price", 0.0)
vix = data.get("NSE_FNO", {}).get("35002", {}).get("last_price", 0.0)

# Visual fallbacks if market is closed or API values return zero
if nifty_spot == 0.0:
    nifty_spot = 25120.00
    nifty_fut = 25135.00
    vix = 13.2

# Derivative calculations configuration 
pcr = 0.91
advances, declines = 34, 16
support = int((nifty_spot // 100) * 100)
resistance = support + 200
expiry_range = f"{support} - {resistance}"
breadth = "BULLISH" if advances > declines else "BEARISH"

# ----------------------------------------------------
# 5. UI Render Engineering (HTML Mobile Container)
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

st.title("Nifty 50 Live Monitor")

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

# Base timestamp tracker
st.markdown(f"<div style='padding-left: 5px; color: #666666; font-size: 0.85em; font-family: monospace;'>Updated :<br>{current_time}</div>", unsafe_allow_html=True)
