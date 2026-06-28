import datetime
import streamlit as st
from dhanhq import dhanhq

import datetime
import streamlit as st
from dhanhq import dhanhq, DhanContext  # Added DhanContext here

# ----------------------------------------------------
# 1. API Configuration (Using Secrets for Security)
# ----------------------------------------------------
try:
    CLIENT_ID = st.secrets["DHAN_CLIENT_ID"]
    ACCESS_TOKEN = st.secrets["DHAN_ACCESS_TOKEN"]
except Exception:
    # Fallback to empty strings if secrets are not set up yet
    CLIENT_ID = "YOUR_DHAN_CLIENT_ID"
    ACCESS_TOKEN = "YOUR_DHAN_ACCESS_TOKEN"

# Fix: Wrap the credentials inside DhanContext first
dhan_context = DhanContext(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)
dhan = dhanhq(dhan_context)


# Instrument Security IDs
SECURITIES = {
    "NSE_EQ": [13],          
    "NSE_FNO": [40001, 35002]
}

# ----------------------------------------------------
# 2. Fetch Data via Market Quotes API (Option 2)
# ----------------------------------------------------
@st.cache_data(ttl=5)  
def fetch_market_snapshot():
    try:
        response = dhan.quote_data(securities=SECURITIES)
        if response.get("status") == "success":
            return response.get("data", {})
    except Exception as e:
        st.error(f"Error fetching data: {e}")
    return {}

data = fetch_market_snapshot()

# Extract API values
nifty_spot = data.get("NSE_EQ", {}).get("13", {}).get("last_price", 25120.00)
nifty_fut = data.get("NSE_FNO", {}).get("40001", {}).get("last_price", 25135.00)
vix = data.get("NSE_FNO", {}).get("35002", {}).get("last_price", 13.20)

# Derivative metrics placeholders
pcr = 0.91 
advances, declines = 34, 16
support, resistance = 25000, 25200
expiry_range = f"{support} – {resistance}"
breadth = "BULLISH"

# ----------------------------------------------------
# 3. Mobile UI Layout Construction
# ----------------------------------------------------
st.set_page_config(page_title="Dhan Monitor", layout="centered")

# Custom CSS injected cleanly
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

st.title("Final Screen Layout")

current_time = datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S IST")

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

<div style='padding-left: 5px; color: #666666; font-size: 0.85em; font-family: monospace;'>
    Updated :<br>{current_time}
</div>
"""

st.markdown(terminal_html, unsafe_allow_html=True)  # Fixed here too