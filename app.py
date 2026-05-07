import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from openai import OpenAI

# ========= 🔑 在这里填 KEY =========
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",   # ← 就填这里
    base_url="https://api.deepseek.com"
)

# ========= 🎨 页面设置 =========
st.set_page_config(
    page_title="AI股票分析",
    layout="centered"
)

st.markdown("""
<style>
.stApp {
    background-color: #0e1117;
    color: white;
}
.big-title {
    font-size:28px;
    font-weight:700;
    text-align:center;
    margin-bottom:10px;
}
.sub-text {
    text-align:center;
    color:#aaa;
    margin-bottom:20px;
}
</style>
""", unsafe_allow_html=True)

# ========= 标题 =========
st.markdown('<div class="big-title">📈 AI 股票分析</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">趋势判断 · 风险提示 · 买卖建议</div>', unsafe_allow_html=True)

# ========= 输入区 =========
ticker = st.text_input("📊 股票代码", "000062.SZ")

col1, col2 = st.columns(2)
with col1:
    period = st.selectbox("📅 周期", ["1mo", "3mo", "6mo"])
with col2:
    risk = st.selectbox("⚠️ 风险偏好", ["低", "中", "高"])

# ========= 按钮 =========
if st.button("🚀 开始分析"):

    with st.spinner("正在分析中..."):

        df = yf.download(ticker, period=period)

        if df.empty:
            st.error("❌ 没获取到数据")
        else:

            # ========= 📈 K线图 =========
            fig = go.Figure()

            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='K线'
            ))

            fig.update_layout(
                height=400,
                template="plotly_dark",
                xaxis_rangeslider_visible=False
            )

            st.plotly_chart(fig, use_container_width=True)

            # ========= AI分析 =========
            prompt = f"""
你是专业股票分析师，请分析股票 {ticker}：

{df.tail().to_string()}

请给出：
1. 趋势判断
2. 是否值得买入
3. 风险提示（结合{risk}风险偏好）
"""

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )

            result = response.choices[0].message.content

            # ========= 结果展示 =========
            st.success("✅ 分析完成")

            st.subheader("📊 AI分析结果")
            st.write(result)
