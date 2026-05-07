import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from openai import OpenAI

# ========= 页面配置（手机友好） =========
st.set_page_config(
    page_title="AI股票分析",
    layout="centered"
)

# ========= DeepSeek =========
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",  # 👉 在这里填
    base_url="https://api.deepseek.com"
)

# ========= UI 样式 =========
st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
}
.stButton>button {
    width: 100%;
    height: 48px;
    font-size: 18px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ========= 标题 =========
st.title("📈 AI 股票分析")
st.caption("趋势判断 · 风险提示 · 买卖建议")

# ========= 输入 =========
ticker = st.text_input("📊 股票代码", "AAPL")

col1, col2 = st.columns(2)
period = col1.selectbox("📅 周期", ["1mo", "3mo", "6mo", "1y"])
risk = col2.selectbox("⚠️ 风险偏好", ["低", "中", "高"])

# ========= 按钮 =========
if st.button("🚀 开始分析"):

    # ===== 获取数据 =====
    df = yf.download(ticker, period=period)

    # 🚨 修复列问题（关键！！！）
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.columns = [str(col).strip() for col in df.columns]

    if df.empty:
        st.error("❌ 获取数据失败（检查代码或网络）")
        st.stop()

    # ===== 检查字段 =====
    required_cols = ["Open", "High", "Low", "Close"]
    if not all(col in df.columns for col in required_cols):
        st.error(f"❌ 数据字段缺失: {df.columns}")
        st.stop()

    # ===== K线图（核心修复）=====
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df["Open"].astype(float),
        high=df["High"].astype(float),
        low=df["Low"].astype(float),
        close=df["Close"].astype(float)
    )])

    fig.update_layout(
        height=400,
        margin=dict(l=10, r=10, t=20, b=20),
        xaxis_rangeslider_visible=False,
        template="plotly_dark"
    )

    st.plotly_chart(fig, use_container_width=True)

    # ===== AI 分析 =====
    with st.spinner("AI分析中..."):

        prompt = f"""
你是专业股票分析师，请分析股票 {ticker}

最近数据：
{df.tail().to_string()}

用户风险偏好：{risk}

请输出：
1. 趋势判断
2. 买卖建议
3. 风险提示

用简洁中文表达
"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content

    # ===== 输出 =====
    st.success("分析完成")

    st.subheader("📊 AI分析结果")
    st.write(result)
