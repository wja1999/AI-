import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI

# ===== 页面配置 =====
st.set_page_config(layout="wide")

# ===== API =====
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

# ===== 轻量高级UI（玻璃感，不会炸）=====
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #eef2f7, #f8fbff);
}

.block-container {
    padding-top: 2rem;
}

.stMetric {
    background: rgba(255,255,255,0.6);
    border-radius: 12px;
    padding: 10px;
    backdrop-filter: blur(10px);
}

.stButton>button {
    border-radius: 10px;
    height: 45px;
    font-size: 16px;
    background: linear-gradient(90deg, #4facfe, #00f2fe);
    color: white;
    border: none;
}

.stSelectbox, .stTextInput {
    background: rgba(255,255,255,0.6);
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ===== 标题 =====
st.title("📊 AI股票分析平台")
st.caption("趋势判断 · 风险提示 · 投资建议")

# ===== 布局 =====
left, right = st.columns([1, 2])

# ================= 左侧 =================
with left:
    st.subheader("⚙️ 参数设置")

    ticker = st.text_input("股票代码", "000066.SZ")
    period = st.selectbox("周期", ["5d", "1mo", "3mo", "6mo"])
    risk = st.selectbox("风险偏好", ["低", "中", "高"])

    run = st.button("🚀 开始分析", use_container_width=True)

# ================= 右侧 =================
with right:

    if run:

        data = yf.download(ticker, period=period)

        if data.empty:
            st.error("❌ 没有获取到数据")
        else:
            data = data.reset_index()

            # ===== 判断A股 / 美股 =====
            is_cn = ".SZ" in ticker or ".SH" in ticker

            # ===== K线图 =====
            fig = go.Figure()

            fig.add_trace(go.Candlestick(
                x=data["Date"],
                open=data["Open"],
                high=data["High"],
                low=data["Low"],
                close=data["Close"],
                increasing_line_color="red" if is_cn else "green",
                decreasing_line_color="green" if is_cn else "red"
            ))

            fig.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=30, b=10),
                xaxis_rangeslider_visible=False,
                plot_bgcolor='rgba(255,255,255,0.4)',
                paper_bgcolor='rgba(0,0,0,0)'
            )

            st.plotly_chart(fig, use_container_width=True)

            # ===== KPI指标 =====
            latest = data.iloc[-1]
            change = latest["Close"] - latest["Open"]
            pct = (change / latest["Open"]) * 100

            k1, k2, k3, k4 = st.columns(4)

            k1.metric("💰 最新价", f"{latest['Close']:.2f}")
            k2.metric("📈 涨跌", f"{change:.2f}")
            k3.metric("📊 涨幅", f"{pct:.2f}%")
            k4.metric("🔊 成交量", f"{latest['Volume']/1e6:.2f}M")

            # ===== AI分析 =====
            prompt = f"""
请用中文分析股票 {ticker}：

{data.tail().to_string()}

要求：
1. 趋势判断（一句话）
2. 买卖建议（明确）
3. 风险提示（简洁）
"""

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )

            st.markdown("---")
            st.subheader("🤖 AI分析结果")

            st.write(response.choices[0].message.content)
