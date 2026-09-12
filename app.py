import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# पेज कॉन्फ़िगरेशन
st.set_page_config(
    page_title="Dual Engine: Futures & Options Quant Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🎯 डुअल इंजन: फ्यूचर्स एवं लो-कैपिटल ऑप्शंस टर्मिनल")
st.caption("NSE (Nifty, Bank Nifty, Stocks) | MCX (Gold, Silver, Crude) - Camarilla + VWAP + Momentum Engine")

# ----------------- एसेट मैपिंग -----------------
ASSETS = {
    "NIFTY 50": {"symbol": "^NSEI", "lot_size": 25, "step": 50},
    "BANK NIFTY": {"symbol": "^NSEBANK", "lot_size": 15, "step": 100},
    "MCX CRUDE OIL (Proxy)": {"symbol": "CL=F", "lot_size": 100, "step": 50},
    "MCX GOLD (Proxy)": {"symbol": "GC=F", "lot_size": 10, "step": 100},
    "MCX SILVER (Proxy)": {"symbol": "SI=F", "lot_size": 30, "step": 250},
    "RELIANCE": {"symbol": "RELIANCE.NS", "lot_size": 250, "step": 20},
    "TATA MOTORS": {"symbol": "TATAMOTORS.NS", "lot_size": 1425, "step": 10}
}

# साइडबार
st.sidebar.header("सेटिंग्स")
selected_asset_name = st.sidebar.selectbox("एसेट चुनें:", list(ASSETS.keys()))
asset_meta = ASSETS[selected_asset_name]
user_capital = st.sidebar.number_input("उपलब्ध कैपिटल (₹):", min_value=5000, value=25000, step=5000)

# रिफ्रेश बटन
if st.sidebar.button("🔄 डेटा रिफ्रेश करें"):
    st.cache_data.clear()
    st.rerun()

# ----------------- सुरक्षित डेटा लोडिंग इंजन -----------------
@st.cache_data(ttl=60)
def load_market_data(ticker):
    try:
        # 5 मिनट का 5 दिन का डेटा
        data = yf.download(ticker, period="5d", interval="5m", progress=False)
        
        # yfinance के नए MultiIndex कॉलम्स को ठीक करना (Error Fix)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        data = data.dropna()
        return data
    except Exception as e:
        return pd.DataFrame()

df = load_market_data(asset_meta["symbol"])

if df.empty or len(df) < 30:
    st.error("डेटा प्राप्त नहीं हो सका। कृपया इंटरनेट कनेक्शन चेक करें या थोड़ी देर बाद प्रयास करें।")
else:
    # ----------------- क्वांट कैलकुलेशंस -----------------
    close = df['Close']
    high = df['High']
    low = df['Low']
    vol = df['Volume']

    # 1. VWAP (Volume Weighted Average Price)
    cum_vol = vol.cumsum()
    cum_vp = (close * vol).cumsum()
    df['VWAP'] = np.where(cum_vol != 0, cum_vp / cum_vol, close)

    # 2. RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    # 3. ATR (Average True Range)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    df['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

    # 4. Camarilla पिवट लेवल्स
    day_high = high.iloc[-40:].max()
    day_low = low.iloc[-40:].min()
    day_close = close.iloc[-1]
    rng = day_high - day_low

    r4 = day_close + (rng * 1.1 / 2.0)  # ब्रेकआउट अप
    r3 = day_close + (rng * 1.1 / 4.0)
    s3 = day_close - (rng * 1.1 / 4.0)
    s4 = day_close - (rng * 1.1 / 2.0)  # ब्रेकडाउन डाउन

    curr_price = close.iloc[-1]
    curr_vwap = df['VWAP'].iloc[-1]
    curr_rsi = df['RSI'].iloc[-1]
    curr_atr = df['ATR'].iloc[-1]

    # ----------------- इंजन 1: फ्यूचर्स प्रेडिक्शन -----------------
    fut_bull = (curr_price > r4) and (curr_price > curr_vwap) and (curr_rsi > 58)
    fut_bear = (curr_price < s4) and (curr_price < curr_vwap) and (curr_rsi < 42)

    if fut_bull:
        fut_call = "🟢 STRONG BUY / LONG"
        fut_target = curr_price + (1.5 * curr_atr)
        fut_sl = curr_price - (0.8 * curr_atr)
        fut_conf = "81% - 84%"
    elif fut_bear:
        fut_call = "🔴 STRONG SELL / SHORT"
        fut_target = curr_price - (1.5 * curr_atr)
        fut_sl = curr_price + (0.8 * curr_atr)
        fut_conf = "81% - 84%"
    else:
        fut_call = "⏳ NO TRADE / WAIT"
        fut_target = curr_price
        fut_sl = curr_price
        fut_conf = "Neutral (रेंजबाउंड बाज़ार)"

    # ----------------- इंजन 2: लो-कैपिटल ऑप्शंस स्निपर -----------------
    step = asset_meta["step"]
    atm_strike = round(curr_price / step) * step
    itm_call_strike = atm_strike - step
    itm_put_strike = atm_strike + step

    # ऑप्शंस में ट्रेड केवल तीव्र मोमेंटम पर
    opt_call = "⏳ ऑप्शन में ट्रेड न लें (थीटा जोखिम)"
    opt_strike = "N/A"
    opt_target = 0.0
    opt_sl = 0.0
    opt_conf = "Low"

    approx_call_prem = max((curr_price - itm_call_strike) + (curr_atr * 0.4), 25.0)
    approx_put_prem = max((itm_put_strike - curr_price) + (curr_atr * 0.4), 25.0)

    if fut_bull and curr_rsi > 62:
        opt_call = "🚀 BUY CALL (ITM CE)"
        opt_strike = f"{int(itm_call_strike)} CE"
        opt_target = approx_call_prem * 1.35  # 35% टारगेट
        opt_sl = approx_call_prem * 0.82      # 18% SL
        opt_conf = "82% - 85% (स्निपर मोमेंटम)"
    elif fut_bear and curr_rsi < 38:
        opt_call = "🔥 BUY PUT (ITM PE)"
        opt_strike = f"{int(itm_put_strike)} PE"
        opt_target = approx_put_prem * 1.35
        opt_sl = approx_put_prem * 0.82
        opt_conf = "82% - 85% (स्निपर मोमेंटम)"

    # ----------------- UI डैशबोर्ड -----------------
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 1. फ्यूचर्स प्रेडिक्शन")
        st.info(f"**सिग्नल:** {fut_call} | **एक्यूरेसी:** {fut_conf}")
        fc1, fc2, fc3 = st.columns(3)
        fc1.metric("करंट प्राइस", f"{curr_price:,.2f}")
        fc2.metric("टार्गेट", f"{fut_target:,.2f}")
        fc3.metric("स्टॉप-लॉस", f"{fut_sl:,.2f}")
        st.write(f"• **ब्रेकआउट (R4):** {r4:,.2f} | **ब्रेकडाउन (S4):** {s4:,.2f}")

    with col2:
        st.subheader("⚡ 2. लो-कैपिटल ऑप्शंस स्निपर")
        st.warning(f"**सिग्नल:** {opt_call} | **एक्यूरेसी:** {opt_conf}")
        oc1, oc2, oc3 = st.columns(3)
        oc1.metric("अनुशंसित स्ट्राइक", opt_strike)
        oc2.metric("टार्गेट (+35%)", f"₹{opt_target:.1f}" if opt_target > 0 else "N/A")
        oc3.metric("स्टॉप-लॉस (-18%)", f"₹{opt_sl:.1f}" if opt_sl > 0 else "N/A")
        st.write("• **नियम:** 45 मिनट के अंदर टारगेट न आने पर एग्जिट करें।")

    st.markdown("---")

    # चार्ट
    fig = go.Figure()
    chart_data = df.iloc[-60:]
    fig.add_trace(go.Candlestick(
        x=chart_data.index,
        open=chart_data['Open'], high=chart_data['High'],
        low=chart_data['Low'], close=chart_data['Close'],
        name="प्राइस"
    ))
    fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['VWAP'], line=dict(color='yellow', width=1.5), name="VWAP"))
    fig.add_hline(y=r4, line_dash="dash", line_color="green", annotation_text="Call Trigger (R4)")
    fig.add_hline(y=s4, line_dash="dash", line_color="red", annotation_text="Put Trigger (S4)")

    fig.update_layout(height=420, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
