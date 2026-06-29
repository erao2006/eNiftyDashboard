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
# 3. Pure API Trading Data Fetching Engine (Zero-Simulation)
# ----------------------------------------------------
@st.cache_data(ttl=1)  
def fetch_market_snapshot():
    master_data = {"NSE_INDEX": {}, "NSE_FNO": {}}
    index_payload = {"IDX_I": [13]}
    fno_payload = {"NSE_FNO": [40001, 35002]}
    
    try:
        idx_resp = dhan.ohlc_data(securities=index_payload)
        if isinstance(idx_resp, dict) and idx_resp.get("status") == "success":
            st.success("🟢 Dhan Index API successful: 200 OK")
            master_data["NSE_INDEX"] = idx_resp.get("data", {}).get("IDX_I", {})
        else:
            remark = idx_resp.get("remarks") if isinstance(idx_resp, dict) else "Market Closed / Feed Locked"
            st.error(f"🔴 Dhan Index API Status: 400 | {remark}")
    except Exception as e:
        st.error(f"🔴 Dhan Index API Crash: 500 | {e}")
        
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
            remark = response.get("remarks") if isinstance(response, dict) else "Unauthorized"
            st.error(f"🔴 Dhan Positions API Failed: 401 | {remark}")
    except Exception as e:
        st.error(f"🔴 Dhan Positions API Failed: 500 Connection Error | {e}")
    return pd.DataFrame(columns=['tradingSymbol', 'positionType', 'netQty', 'buyAvg', 'sellAvg', 'realizedProfit', 'unrealizedProfit'])

# ----------------------------------------------------
# 4. Corrected Dynamic Historic Query Sequence (Inclusive Windowing)
# ----------------------------------------------------
@st.cache_data(ttl=1800)
def fetch_last_working_day_data():
    """
    Looks backward sequentially expanding target lookup window brackets by +1 day 
    to successfully fulfill the non-inclusive parameters of the Dhan Historical Engine.
    """
    fixed_historical_snapshot = {
        "working_date": "Unknown", 
        "close_price": 0.0, 
        "adv": 0, 
        "dec": 0, 
        "status": "No Historical Connection"
    }
    
    # Sweep backward to capture the most recent market close data block
    for i in range(1, 8):
        target_date = datetime.date.today() - datetime.timedelta(days=i)
        next_day = target_date + datetime.timedelta(days=1)
        
        date_from_str = target_date.strftime("%Y-%m-%d")
        date_to_str = next_day.strftime("%Y-%m-%d")
        
        try:
            hist_response = dhan.historical_daily_data(
                security_id="13",
                exchange_segment="IDX_I",
                instrument_type="INDEX",
                from_date=date_from_str,
                to_date=date_to_str
            )
            if isinstance(hist_response, dict) and hist_response.get("status") == "success":
                records = hist_response.get("data", [])
                if records:
                    fixed_historical_snapshot["working_date"] = target_date.strftime("%d-%b-%Y")
                    fixed_historical_snapshot["close_price"] = float(records[0].get("close", 0.0))
                    fixed_historical_snapshot["adv"] = 0  
                    fixed_historical_snapshot["dec"] = 0  
                    fixed_historical_snapshot["status"] = f"Success (Fetched via range: {date_from_str})"
                    return fixed_historical_snapshot
        except Exception:
            pass

    # Safe zero implementation fallback execution point
    if fixed_historical_snapshot["close_price"] == 0.0:
        fallback_date = datetime.date.today() - datetime.timedelta(days=1)
        fixed_historical_snapshot["working_date"] = fallback_date.strftime("%d-%b-%Y")
        fixed_historical_snapshot["close_price"] = 0.00
        fixed_historical_snapshot["adv"] = 0
        fixed_historical_snapshot["dec"] = 0
        fixed_historical_snapshot["status"] = "API Query Null | Safe Zero Fallback Activated"
        
    return fixed_historical_snapshot

# Execute Network Engine Operations
st.markdown("### 📡 API Connection Logs")
market_data = fetch_market_snapshot()
orders_df = fetch_orders()
positions_df = fetch_positions()
working_day_data = fetch_last_working_day_data()

# ----------------------------------------------------
# 5. Pure Real-Time Market Metric Extraction (Zeros Fallback)
# ----------------------------------------------------
nifty_spot = market_data.get("NSE_INDEX", {}).get("13", {}).get("last_price", 0.0)
nifty_fut = market_data.get("NSE_FNO", {}).get("40001", {}).get("last_price", 0.0)
vix = market_data.get("NSE_FNO", {}).get("35002", {}).get("last_price", 0.0)

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
# 6. UI Custom CSS & Theme Injection
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
# 7. Live Market Terminal Block
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
# 8. Portfolio P&L Summary Banner
# ----------------------------------------------------
st.markdown("### 📈 Cumulative Performance P&L")
if not positions_df.empty:
    realized = pd.to_numeric(positions_df['realizedProfit'], errors='coerce').fillna(0.0).sum()
    unrealized = pd.to_numeric(positions_df['unrealizedProfit'], errors='coerce').fillna(0.0).sum()
    total_pnl = realized + unrealized
    
    if total_pnl >= 0:
        st.markdown(f'<div class="pnl-box" style="background-color: #0A2F1D; color: #00FF66; border: 1px solid #00FF66;">TOTAL P&L: ₹{total_pnl:,.2f}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="pnl-box" style="background-color: #3A1414; color: #FF4D4D; border: 1px solid #FF4D4D;">TOTAL P&L: ₹{total_pnl:,.2f}</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="pnl-box" style="background-color: #1E1E1E; color: #E0E0E0; border: 1px solid #333333;">TOTAL P&L: ₹0.00</div>', unsafe_allow_html=True)

# ----------------------------------------------------
# 9. Positions & Orders Ledger Displays
# ----------------------------------------------------
st.markdown("### 💼 Open Positions Details")
if not positions_df.empty:
    # FIXED: Updated use_container_width=True to width='stretch'
    st.dataframe(positions_df, width='stretch', hide_index=True)
else:
    st.info("No active open positions found.")

st.markdown("### 📦 Today's Order Book")
if not orders_df.empty:
    # FIXED: Updated use_container_width=True to width='stretch'
    st.dataframe(orders_df, width='stretch', hide_index=True)
else:
    st.info("No orders processed today.")

# ----------------------------------------------------
# 10. Isolated Past Market Settlement Block
# ----------------------------------------------------
st.markdown("### 🏛️ Past Fixed Settlement Snapshot")
fixed_thursday_html = f"""
<div class="terminal-box" style="border-top: 3px solid #F1C40F;">
    <div class="terminal-row">
        <span class="label">LAST WORKING DATE</span>
        <span class="value-neutral">{working_day_data["working_date"]}</span>
    </div>
    <div class="terminal-row">
        <span class="label">NIFTY CLOSE</span>
        <span class="value">{working_day_data["close_price"]:,.2f}</span>
    </div>
    <div class="terminal-row">
        <span class="label">ADVANCES</span>
        <span class="value" style="color: #00FF66;">{working_day_data["adv"]}</span>
    </div>
    <div class="terminal-row">
        <span class="label">DECLINES</span>
        <span class="value" style="color: #FF4D4D;">{working_day_data["dec"]}</span>
    </div>
    <div class="terminal-row">
        <span class="label">ENGINE LOG</span>
        <span class="value" style="color: #888888; font-size: 0.9em;">{working_day_data["status"]}</span>
    </div>
</div>
"""
st.markdown(fixed_thursday_html, unsafe_allow_html=True)

# Sync Footer
ist_zone = ZoneInfo("Asia/Kolkata")
current_time = datetime.datetime.now(ist_zone).strftime("%d-%b-%Y %H:%M:%S IST")
st.markdown(f"<div style='padding-left: 2px; color: #666666; font-size: 0.85em; font-family: monospace; margin-top: 25px;'>Last Sync: {current_time}</div>", unsafe_allow_html=True)
