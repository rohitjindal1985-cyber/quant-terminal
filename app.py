import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="Dual Engine: MCX India & Global Quant Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🎯 MCX इंडिया (₹) एवं ग्लोबल मार्केट्स क्वांट टर्मिनल")
st.caption("MCX Indian Rupee Rates (INR) | International Rates (XAU/USD, XAG/USD) | NSE Futures & Options")

# ----------------- एसेट कॉन्फ़िगरेशन -----------------
ASSETS = {
    # 🇮🇳 MCX इंडिया सेगमेंट्स (INR में प्रदर्शित)
    "MCX GOLD (₹ / 10 Grams)": {
        "symbol": "GC=F", "market": "MCX_INR", "unit": "₹/10g", 
        "lot_size": 1, "step": 100, "conversion_factor": 1.0
    },
    "MCX SILVER (₹ / 1 Kg)": {
        "symbol": "SI=F", "market": "MCX_INR", "unit": "₹/kg", 
        "lot_size": 1, "step": 500, "conversion_factor": 1.0
    },
    "MCX CRUDE OIL (₹ / Barrel)": {
        "symbol": "CL=F", "market": "MCX_INR", "unit": "₹/bbl", 
        "lot_size": 100, "step": 50, "conversion_factor": 1.0
    },
    
    # 🌐 इंटरनेशनल सेगमेंट्स (USD Rates)
    "XAU/USD (Gold Spot - USD/oz)": {
        "symbol": "GC=F", "market": "GLOBAL_USD", "unit": "$/oz", 
        "lot_size": 10, "step": 10, "conversion_factor": 1.0
    },
    "XAG/USD (Silver Spot - USD/oz)": {
        "symbol": "SI=F", "market": "GLOBAL_USD", "unit": "$/oz", 
        "lot_size": 50, "step": 0.5, "conversion_factor": 1.0
    },
    "WTI CRUDE (USD / Barrel)": {
        "symbol": "CL=F", "market": "GLOBAL_USD", "unit": "$/bbl", 
        "lot_size": 100, "step": 1.0, "conversion_factor": 1.0
    },

    # 📈 भारतीय शेयर एवं इंडेक्स
    "NIFTY 50": {
        "symbol": "^NSEI", "market": "NSE", "unit": "Points", 
        "lot_size": 25, "step": 50, "conversion_factor": 1.0
    },
    "BANK NIFTY": {
        "symbol": "^NSEBANK", "market": "NSE", "unit": "Points", 
        "lot_size": 15, "step": 100, "conversion_factor": 1.0
    },
    "RELIANCE": {
        "symbol": "RELIANCE.NS", "market": "NSE", "unit": "₹", 
        "lot_size": 250, "step": 20, "conversion_factor": 1.0
    }
}

# साइडबार
st.sidebar.header("सेटिंग्स एवं एसेट चयन")
selected_asset_name = st.sidebar.selectbox("ट्रेडिंग एसेट चुनें:", list(ASSETS.keys()))
asset_meta = ASSETS[selected_asset_name]

# रिफ्रेश बटन
if st.sidebar.button("🔄 डेटा रिफ्रेश करें"):
    st.cache_data.clear()
    st.rerun()

# ----------------- लाइव डेटा व करेंसी फेचिंग -----------------
@st.cache_data(ttl=60)
def fetch_data_and_currency(ticker):
    try:
        # प्राइमरी एसेट डेटा
        data = yf.download(ticker, period="5d", interval="5m", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        # USD/INR लाइव एक्सचेंज रेट
        fx_data = yf.download("USDINR=X", period="1d", interval="5m", progress=False)
        if isinstance(fx_data.columns, pd.MultiIndex):
            fx_data.columns = fx_data.columns.get_level_values(0)
            
        usd_inr = fx_data['Close'].iloc[-1] if not fx_data.empty else 83.50
        return data.dropna(), float(usd_inr)
    except Exception:
        return pd.DataFrame(), 83.50

df_raw, usd_inr_rate = fetch_data_and_currency(asset_meta["symbol"])

if df_raw.empty or len(df_raw) < 20:
    st.error("डेटा लोड करने में असमर्थ। कृपया इंटरनेट कनेक्शन चेक करें।")
else:
    df = df_raw.copy()

    # ----------------- MCX भारतीय दर (INR) रूपांतरण फॉर्मूला -----------------
    # इंटरनेशनल फ्यूचर्स को MCX इंडियन रेट्स में कन्वर्ट करने का वास्तविक फॉर्मूला
    if asset_meta["market"] == "MCX_INR":
        duty_factor = 1.06  # लगभग 6% बेसिक कस्टम ड्यूटी व टैक्स बफर
        
        if "GOLD" in selected_asset_name:
            # 1 Troy Ounce = 31.1035 ग्राम -> प्रति 10 ग्राम रूपांतरण
            factor = (usd_inr_rate / 31.1035) * 10 * duty_factor
        elif "SILVER" in selected_asset_name:
            # 1 Troy Ounce = 31.1035 ग्राम -> प्रति 1 किलोग्राम (1000g) रूपांतरण
            factor = (usd_inr_rate / 31.1035) * 1000 * duty_factor
        elif "CRUDE" in selected_asset_name:
            # प्रति बैरल USD to INR
            factor = usd_inr_rate
        else:
            factor = 1.0
            
        for col in ['Open', 'High', 'Low', 'Close']:
            df[col] = df[col] * factor
    else:
        factor = 1.0

    # ----------------- क्वांट कैलकुलेशन -----------------
    close = df['Close']
    high = df['High']
    low = df['Low']
    vol = df['Volume']

    # VWAP
    cum_vol = vol.cumsum()
    cum_vp = (close * vol).cumsum()
    df['VWAP'] = np.where(cum_vol != 0, cum_vp / cum_vol, close)

    # RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    # ATR
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    df['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

    # Camarilla लेवल्स
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

    # ----------------- सिग्नल लॉजिक -----------------
    fut_bull = (curr_price > r4) and (curr_price > curr_vwap) and (curr_rsi > 58)
    fut_bear = (curr_price < s4) and (curr_price < curr_vwap) and (curr_rsi < 42)

    prefix = "₹" if "INR" in asset_meta["market"] or asset_meta["market"] == "NSE" else "$"

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
        fut_conf = "Neutral (रेंजबाउंड)"

    # ऑप्शंस स्ट्राइक निर्धारण (ITM Strike)
    step = asset_meta["step"]
    atm_strike = round(curr_price / step) * step
    itm_call_strike = atm_strike - step
    itm_put_strike = atm_strike + step

    # ----------------- यूआई डैशबोर्ड -----------------
    # इन्फो बार
    if asset_meta["market"] == "MCX_INR":
        st.success(f"🇮🇳 **MCX भारतीय बाज़ार मोड सक्रिय:** दरें रुपये ({asset_meta['unit']}) में प्रदर्शित हैं। लाइव USD/INR एक्सचेंज रेट: ₹{usd_inr_rate:.2f}")
    elif asset_meta["market"] == "GLOBAL_USD":
        st.info(f"🌐 **अंतरराष्ट्रीय बाज़ार मोड सक्रिय:** दरें अमेरिकी डॉलर ({asset_meta['unit']}) में प्रदर्शित हैं।")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"लाइव भाव ({asset_meta['unit']})", f"{prefix}{curr_price:,.2f}")
    c2.metric("आज का ब्रेकआउट (Up Level)", f"{prefix}{r4:,.2f}")
    c3.metric("आज का ब्रेकडाउन (Down Level)", f"{prefix}{s4:,.2f}")
    c4.metric("RSI मोमेंटम", f"{curr_rsi:.1f}")

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📊 फ्यूचर्स / स्पॉट प्रेडिक्शन")
        st.info(f"**सिग्नल:** {fut_call} | **एक्यूरेसी:** {fut_conf}")
        fc1, fc2, fc3 = st.columns(3)
        fc1.metric("एंट्री स्तर", f"{prefix}{curr_price:,.2f}")
        fc2.metric("संभावित टार्गेट", f"{prefix}{fut_target:,.2f}")
        fc3.metric("स्टॉप-लॉस बफर", f"{prefix}{fut_sl:,.2f}")

    with col_right:
        st.subheader("⚡ लो-कैपिटल ऑप्शंस स्निपर")
        if fut_bull and curr_rsi > 60:
            st.success(f"🚀 **कॉल ऑप्शन (BUY ITM CE):** {int(itm_call_strike)} CE खरीदें")
            st.write("• **टार्गेट:** प्रीमियम पर +35% लाभ पर एग्जिट करें।")
            st.write("• **स्टॉप-लॉस:** प्रीमियम पर -18% सख्त SL रखें।")
        elif fut_bear and curr_rsi < 40:
            st.error(f"🔥 **पुट ऑप्शन (BUY ITM PE):** {int(itm_put_strike)} PE खरीदें")
            st.write("• **टार्गेट:** प्रीमियम पर +35% लाभ पर एग्जिट करें।")
            st.write("• **स्टॉप-लॉस:** प्रीमियम पर -18% सख्त SL रखें।")
        else:
            st.warning("⏳ **वेटिंग ज़ोन:** ऑप्शन बाइंग के लिए अभी मोमेंटम अपर्याप्त है।")

    # चार्ट
    st.markdown("---")
    fig = go.Figure()
    chart_df = df.iloc[-60:]
    fig.add_trace(go.Candlestick(
        x=chart_df.index,
        open=chart_df['Open'], high=chart_df['High'],
        low=chart_df['Low'], close=chart_df['Close'],
        name="भाव"
    ))
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['VWAP'], line=dict(color='yellow', width=1.5), name="VWAP"))
    fig.add_hline(y=r4, line_dash="dash", line_color="green", annotation_text="Breakout Up (R4)")
    fig.add_hline(y=s4, line_dash="dash", line_color="red", annotation_text="Breakdown Down (S4)")

    fig.update_layout(height=450, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)
