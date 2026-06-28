import datetime
import pandas as pd
import streamlit as st
from dhanhq import dhanhq, DhanContext
from zoneinfo import ZoneInfo
import logging

# Set up logging to your Streamlit Cloud logs console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CRITICAL FIX: Page config must happen FIRST, and only ONCE
st.set_page_config(page_title="Dhan Monitor", layout="centered")

# ----------------------------------------------------
# 1. API Configuration (Using Secrets for Security)
# ----------------------------------------------------
try:
    CLIENT_ID = st.secrets["DHAN_CLIENT_ID"]
    ACCESS_TOKEN = st.secrets["DHAN_ACCESS_TOKEN"]
except Exception:
    CLIENT_ID = "YOUR_DHAN_CLIENT_ID"
    ACCESS_TOKEN = "YOUR_DHAN_ACCESS_TOKEN"

# Context Initialization
try:
    dhan_context = DhanContext(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)
    dhan = dhanhq(dhan_context)
except Exception as init_err:
    st.error(f"Initialization Failed: {init_err}")
    st.stop()

# Instrument Security IDs (Nifty 50 Spot index = 13)
SECURITIES = {
    "NSE_EQ": [13],          
    "NSE_FNO": [40001, 35002] 
}

# ----------------------------------------------------
# 2. Fetch Data (Market Snapshots & Orders with Active Errors)
# ----------------------------------------------------
@st.cache_data(ttl=5)  
def fetch_market_snapshot():
    try:
        response = dhan.quote_data(securities=SECURITIES)
        if response.get("status") == "success":
            return response.get("data", {})
        else:
            # Display API warnings directly on your phone interface
            st.error(f"Dhan API Error: {response.get('remarks', 'Unknown Error')}")
    except Exception as e:
        st.error(f"Network Connection Error: {e}")
    return {}

def fetch_orders():
    try:
        response = dhan.get_order_list()
        if response.get("status") == "success" and response.get("data"):
            orders = response.get("data", [])
            df = pd.DataFrame(orders)
            columns_to_keep = ['tradingSymbol', 'transactionType', 'orderType', 'quantity', 'price', 'orderStatus']
            available_cols = [col for col in columns_to_keep if col in df.columns]
            return df[available_cols]
    except Exception as e:
        logger.error(f"Orders retrieval error: {e}")
    return pd.DataFrame(columns=['tradingSymbol', 'transactionType', 'quantity', 'price', 'orderStatus'])

# Trigger live fetches
data = fetch_market_snapshot()
orders_df = fetch_orders()

# Extract live values from Dhan JSON response structure safely
nifty_spot = data.get("NSE_EQ", {}).get("13", {}).get("last_price", 0.0)
nifty_fut = data.get("NSE_FNO", {}).get("40001", {}).get("last_price", 0.0)
vix = data.get("NSE_FNO", {}).get("35002", {}).get("last_price", 0.0)

# If API fails or is empty, use temporary structural stand-ins
if nifty_spot == 0.0:
    nifty_spot = 23450.00  # Visual mock indicators to know if data is dead
    nifty_fut = 23510.00
    vix = 12.5

# Calculation Placeholders
pcr = 0.95
advances, declines = 32, 18
support, resistance = int((nifty_spot // 100) * 100), int(((nifty_spot // 100) + 1) * 100)
expiry_range = f"{support} – {resistance}"
breadth = "BULLISH" if advances > declines else "BEARISH"

# ----------------------------------------------------
# 3. Mobile UI Layout Construction
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

# Orders Section
st.markdown("### 📦 Today's Orders")
if not orders_df.empty:
    st.dataframe(orders_df, use_container_width=True, hide_index=True)
else:
    st.info("No active orders found for today.")

# Singular updated timestamp banner at base
st.markdown(f"<div style='padding-left: 5px; color: #666666; font-size: 0.85em; font-family: monospace;'>Updated :<br>{current_time}</div>", unsafe_allow_html=True)
