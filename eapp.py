import pandas as pd
import streamlit as st
import yfinance as yf
import requests
import io
from dhanhq import dhanhq, DhanContext
from zoneinfo import ZoneInfo
import logging
from streamlit_autorefresh import st_autorefresh
import pytz
from datetime import datetime
import yfinance.shared as shared # Import shared to access errors

ist_zone = ZoneInfo("Asia/Kolkata")
current_time = datetime.now(ist_zone).strftime("%d-%b-%Y %H:%M:%S IST")
st.markdown(f"<div style='padding-left: 2px; color: #666666; font-size: 0.85em; font-family: monospace; margin-top: 25px;'>Last Sync: {current_time}</div>", unsafe_allow_html=True)

# -------
# new section
# --------
NIFTY50_SYMBOLS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS",
    "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS",
    "BEL.NS", "BHARTIARTL.NS", "CIPLA.NS", "COALINDIA.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "ETERNAL.NS", "GRASIM.NS",
    "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS",
    "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "JIOFIN.NS",
    "KOTAKBANK.NS", "LT.NS", "M&M.NS", "MARUTI.NS",
    "NESTLEIND.NS", "NTPC.NS", "ONGC.NS", "POWERGRID.NS",
    "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS",
    "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TMPV.NS",
    "TATASTEEL.NS", "TECHM.NS", "TITAN.NS", "TRENT.NS",
    "ULTRACEMCO.NS", "WIPRO.NS"
]

#NIFTY50_SYMBOLS = [
#    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS",
#    "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS",
#    "BEL.NS", "BHARTIARTL.NS", "BPCL.NS", "BRITANNIA.NS",
#    "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS",
#    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS",
#    "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS",
#    "ICICIBANK.NS", "INDIGO.NS", "INDUSINDBK.NS", "INFY.NS",
#    "ITC.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
#    "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS",
#    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS",
#    "SBIN.NS", "SHRIRAMFIN.NS", "SUNPHARMA.NS", "TATACONSUM.NS",
#    "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", "TITAN.NS",
#    "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS"
#]


# ----------------------------------------------------
# 1. Global Page Configuration
# ----------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Dhan Monitor & Portfolio", layout="centered")

# --------------------------
# Condition for market hours 
# --------------------------
def is_market_open():
    # Define the timezone
    ist = pytz.timezone('Asia/Kolkata')
    
    # Get current time and immediately localize it to IST
    # This avoids the conflict between datetime and pytz
    now = datetime.now(ist)
    
    # Check if weekend (Saturday=5, Sunday=6)
    if now.weekday() >= 5:
        return False
    
    # Create start and end time objects for the current day in IST
    start_time = now.replace(hour=4, minute=55, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=35, second=0, microsecond=0)
    
    return start_time <= now <= end_time

# Refresh every 60 seconds
st_autorefresh(interval=60000, key="market_refresh")

# --- Early Exit Logic ---
if not is_market_open():
    st.info("Market is currently closed. Updates are paused.")
    st.stop()  # Everything below this line will not execute when market is closed

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
# 3. Stable Market Engine (With Percentage Logic)
# ----------------------------------------------------
@st.cache_data(ttl=5)
@st.fragment(run_every="30s")
def fetch_market_snapshot():
    # 1. Initialize master_data with all required keys
    master_data = {
        "NIFTY_SPOT": 0.0, "NIFTY_SPOT_PCT": 0.0,
        "NIFTY_FUTURE": 0.0, "NIFTY_FUTURE_PCT": 0.0,
        "BANKNIFTY_SPOT": 0.0, "BANKNIFTY_SPOT_PCT": 0.0,
        "SENSEX_SPOT": 0.0, "SENSEX_SPOT_PCT": 0.0
    }
    
    # 2. Define indices locally inside the function
    indices = {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "SENSEX": "^BSESN"
    }
    
    try:
        # Loop through each index
        for name, ticker_symbol in indices.items():
            ticker = yf.Ticker(ticker_symbol)
            history = ticker.history(period="2d")
            
            if len(history) >= 1:
                current_spot = float(history["Close"].iloc[-1])
                master_data[f"{name}_SPOT"] = current_spot
                
                # Fetch previous close for % calculation
                prev_close = ticker.info.get("previousClose")
                if not prev_close and len(history) >= 2:
                    prev_close = float(history["Close"].iloc[-2])
                
                if prev_close and prev_close > 0:
                    master_data[f"{name}_SPOT_PCT"] = ((current_spot - prev_close) / prev_close) * 100
        
        # Manual calculation for NIFTY_FUTURE (as per your original logic)
        implied_premium = 45.0
        master_data["NIFTY_FUTURE"] = master_data["NIFTY_SPOT"] + implied_premium
        master_data["NIFTY_FUTURE_PCT"] = master_data["NIFTY_SPOT_PCT"] # Simplified
        
        st.success("🟢 Market Feed via Yahoo Finance: 200 OK")       
    except Exception as e:
        st.error(f"🔴 Market Connection failed: {e}")
        
    return master_data

@st.fragment(run_every="10s")
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

@st.fragment(run_every="10s")
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
            st.error(f"🔴 Dhan Orders API Failed: {remark}")
    except Exception as e:
        st.error(f"🔴 Dhan Positions API Failed: 500 Connection Error | {e}")
    return pd.DataFrame(columns=['tradingSymbol', 'positionType', 'netQty', 'buyAvg', 'sellAvg', 'realizedProfit', 'unrealizedProfit'])

# new section
@st.fragment(run_every="30s")
def get_nifty50_ad(nifty50_symbols):
    # Using Tickers object is more robust for multi-symbol requests
    tickers = yf.Tickers(" ".join(nifty50_symbols))
    
    # download() on Tickers object handles the request properly
    data = tickers.download(period="2d", interval="1d", group_by="ticker", progress=False)
    
    advances = 0
    declines = 0
    unchanged = 0
    valid_stocks = 0
    failed_stocks = []

    for symbol in nifty50_symbols:
        # Check if the symbol exists in the downloaded data
        if symbol in data.columns.levels[0]:
            close_data = data[symbol]["Close"].dropna()
            
            if len(close_data) >= 2:
                prev_close = close_data.iloc[-2]
                curr_close = close_data.iloc[-1]
                
                if curr_close > prev_close:
                    advances += 1
                elif curr_close < prev_close:
                    declines += 1
                else:
                    unchanged += 1
                valid_stocks += 1
            else:
                failed_stocks.append(f"{symbol} (insufficient data)")
        else:
            failed_stocks.append(symbol)
    
    # Display the failures so you know exactly what is missing
    if failed_stocks:
        st.warning(f"Failed/Missing {len(failed_stocks)} stocks: {', '.join(failed_stocks)}")
        
    ratio = round(advances / declines, 2) if declines > 0 else float(advances)
    
    st.write(f"Advances: {advances}, Declines: {declines}, Unchanged: {unchanged}, Valid Stocks: {valid_stocks}")
    
    return advances, declines, unchanged, ratio

#    except Exception as e:
#        st.error(f"A/D Error: {e}")
#        return 0, 0, 0, 0.0
# -------
# ---- test to display nifty 50 security values

# NIFTY50_SYMBOLS = [
#    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
#    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
#    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "GRASIM",
#    "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO",
#    "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY", "ITC",
#    "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT", "M&M",
#    "MARUTI", "NESTLEIND", "NTPC", "ONGC", "POWERGRID",
#    "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN", "SUNPHARMA",
#    "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS", "TECHM",
#    "TITAN", "TRENT", "ULTRACEMCO", "WIPRO" ]

# ----------------------------------------------------
# 2. Data Engine
# ----------------------------------------------------
@st.cache_data(ttl=86400)
def load_security_ids():
    url = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
    response = requests.get(url)
    df = pd.read_csv(io.StringIO(response.text), low_memory=False)
    # Filter for NSE Equity
    df = df[(df["EXCH_ID"] == "NSE") & (df["SEGMENT"] == "E")]
    mapping = {}
    for sym in NIFTY50_SYMBOLS:
        row = df[df["SYMBOL_NAME"] == sym]
        if not row.empty:
            mapping[sym] = str(row.iloc[0]["SECURITY_ID"])
    return mapping

@st.cache_data(ttl=5)
def get_dhan_breadth():
    mapping = load_security_ids()
    try:
        quotes = dhan.ohlc_data(securities={"NSE_EQ": list(mapping.values())})
        if quotes.get("status") == "success":
            data = quotes["data"]["NSE_EQ"]
            adv = dec = unc = 0
            for sec_id in data:
                ltp = data[sec_id]["last_price"]
                prev = data[sec_id]["ohlc"]["close"]
                if ltp > prev: adv += 1
                elif ltp < prev: dec += 1
                else: unc += 1
            return adv, dec, unc
    except: pass
    return 0, 0, 50

# ----------------------------------------------------
# 3. Main Dashboard UI
# ----------------------------------------------------
# st.title("📊 Live Market Terminal")

# Fetch Data
# adv, dec, unc = get_dhan_breadth()

# Metrics
# st.markdown("### 📈 NIFTY 50 Advance / Decline")
# c1, c2, c3, c4 = st.columns(4)
# c1.metric("🟢 Adv", adv)
# c2.metric("🔴 Dec", dec)
# c3.metric("⚪ Unch", unc)
# c4.metric("📊 Ratio", round(adv/dec, 2) if dec > 0 else adv)

# P&L and other logic (Keep your original CSS and dataframe blocks below)
# st.caption(f"Last Updated: {datetime.datetime.now().strftime('%H:%M:%S')}")
# Sync Footer

# ---- test ends ----

# Execute Network Engine Operations
st.markdown("### 📡 API Connection Logs")
# market_data = fetch_market_snapshot()
orders_df = fetch_orders()
positions_df = fetch_positions()

# Example usage to display in Streamlit
market_data = fetch_market_snapshot()
# st.write(data)

# ----------------------------------------------------
# 4. Market Metric Assignment
# ----------------------------------------------------
nifty_spot = market_data["NIFTY_SPOT"]
nifty_spot_pct = market_data["NIFTY_SPOT_PCT"]
nifty_fut = market_data["NIFTY_FUTURE"]
nifty_fut_pct = market_data["NIFTY_FUTURE_PCT"]

vix = 12.4  # Assigned baseline trading volatility floor reference

if nifty_spot > 0:
    support = int((nifty_spot // 100) * 100)
    resistance = support + 200
    expiry_range = f"{support} - {resistance}"
else:
    support, resistance = 0, 0
    expiry_range = "0 - 0"

# Determine formatting colors based on market movement flags
spot_color = "#00FF66" if nifty_spot_pct >= 0 else "#FF4D4D"
spot_sign = "+" if nifty_spot_pct >= 0 else ""

fut_color = "#00FF66" if nifty_fut_pct >= 0 else "#FF4D4D"
fut_sign = "+" if nifty_fut_pct >= 0 else ""

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
# 6. Live Market Terminal Block (Color-coded Updates)
# ----------------------------------------------------

# Assuming you have already fetched the data and it is stored in 'data'
# e.g., data = fetch_market_snapshot()

def get_color(pct):
    return "green" if pct >= 0 else "red"

def get_sign(pct):
    return "+" if pct >= 0 else ""

# Extracting values for clarity
nifty_spot = market_data.get("NIFTY_SPOT", 0)
nifty_spot_pct = market_data.get("NIFTY_SPOT_PCT", 0)

bn_spot = market_data.get("BANKNIFTY_SPOT", 0)
bn_spot_pct = market_data.get("BANKNIFTY_SPOT_PCT", 0)

sensex_spot = market_data.get("SENSEX_SPOT", 0)
sensex_spot_pct = market_data.get("SENSEX_SPOT_PCT", 0)

# Build the HTML
# Ensure these variables are defined before the f-string
# Using f-string syntax correctly without spaces before the colon
# 1. Prepare formatted strings separately to avoid f-string syntax confusion
nifty_fmt = f"{nifty_spot:,.2f} ({get_sign(nifty_spot_pct)}{nifty_spot_pct:.2f}%)"
fut_fmt = f"{nifty_fut:,.2f} ({get_sign(nifty_fut_pct)}{nifty_fut_pct:.2f}%)"
bn_fmt = f"{bn_spot:,.2f} ({get_sign(bn_spot_pct)}{bn_spot_pct:.2f}%)"
sensex_fmt = f"{sensex_spot:,.0f} ({get_sign(sensex_spot_pct)}{sensex_spot_pct:.2f}%)"

# 2. Use double braces {{ }} for CSS to escape them, single for variables
terminal_html = f"""
<div style="background:#1a1a1a; padding:15px; border-radius:8px; color:white; font-family:monospace;">
    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
        <span style="color:#aaa;">NIFTY</span>
        <span style="font-weight:bold; color:{get_color(nifty_spot_pct)};">{nifty_fmt}</span>
    </div>
    <!--
    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
        <span style="color:#aaa;">FUTURE</span>
        <span style="font-weight:bold; color:{get_color(nifty_fut_pct)};">{fut_fmt}</span>
    </div>
    -->
    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
        <span style="color:#aaa;">BANKNIFTY</span>
        <span style="font-weight:bold; color:{get_color(bn_spot_pct)};">{bn_fmt}</span>
    </div>
    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
        <span style="color:#aaa;">SENSEX</span>
        <span style="font-weight:bold; color:{get_color(sensex_spot_pct)};">{sensex_fmt}</span>
    </div>
</div>
"""

st.markdown("### 📊 Live Terminal Snapshot")
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

# ------- new section
# -------- NIFTY 50 ADVANCE / DECLINE --------
adv, dec, unc, ad_ratio = get_nifty50_ad()

st.markdown("### 📈 NIFTY 50 Advance / Decline")

# c1, c2, c3, c4 = st.columns(4)

# Prepare data for a horizontal table
ad_data = {
    "Advance": [adv],
    "Decline": [dec],
    "Unchanged": [unc],
    "A/D Ratio": [f"{ad_ratio:.2f}"]
}

df_ad = pd.DataFrame(ad_data)

# Display as a clean horizontal table
# 'hide_index' removes the 0, 1, 2 row numbers for a cleaner look
st.table(df_ad.style.hide(axis="index"))

# st.caption(f"Updated: {datetime.datetime.now().strftime('%d-%b-%Y %I:%M:%S %p')}")
# ------

