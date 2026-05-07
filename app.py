import streamlit as st
import yfinance as yf
from openai import OpenAI
import plotly.graph_objects as go

# ======================
# 🔐 在这里填你的 key
# ======================
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

# ======================
# 🎨 页面配置（手机友好）
# ======================
st.set_page_config(
    page_title="AI股票分析",
    page_icon="📈",
    layout="centered"
)

st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
}
.stButton>button {
    width: 100%;
    height: 48px;
    border-radius: 10px;
    font-size: 16px;
}
</style>
""", unsafe_allow_html=True)

# ======================
# 🧠 UI
# ======================
st.title("📈 AI 股票分析")
st.caption("趋势判断 · 风险提示 · 买卖建议")

ticker = st.text_input("📊 股票代码", "000001.SZ")

col1, col2 = st.columns(2)
with col1:
    period = st.selectbox("📅 周期", ["1mo", "3mo", "6mo", "1y"], index=0)
with col2:
    risk = st.selectbox("⚠️ 风险偏好", ["低", "中", "高"], index=1)

# ======================
# 🚀 开始分析
# ======================
if st.button("🚀 开始分析"):

    data = yf.download(ticker, period=period)

    if data.empty:
        st.error("❌ 没获取到数据，请检查代码")
    else:
        # ======================
        # 📈 K线图（优化版）
        # ======================
        df = data.reset_index()
        df["x"] = range(len(df))  # 👉 关键：连续坐标（去掉周末）

        fig = go.Figure(data=[go.Candlestick(
            x=df["x"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            increasing_line_color="#00C853",
            decreasing_line_color="#FF3D00"
        )])

        fig.update_layout(
            xaxis=dict(
                tickmode='array',
                tickvals=df["x"][::max(1, len(df)//6)],
                ticktext=df["Date"].dt.strftime('%m-%d')[::max(1, len(df)//6)]
            ),
            yaxis=dict(title="价格"),
            margin=dict(l=10, r=10, t=10, b=10),
            height=400,
            template="plotly_dark"
        )

        st.plotly_chart(fig, use_container_width=True)

        st.success("✅ 数据加载完成")

        # ======================
        # 🤖 AI 分析
        # ======================
        prompt = f"""
你是专业股票分析师，请分析股票 {ticker}：

最近数据：
{data.tail().to_string()}

风险偏好：{risk}

请给出：
1. 趋势判断
2. 是否值得买入
3. 风险提示
"""

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )

            result = response.choices[0].message.content

            st.subheader("📊 AI分析结果")
            st.markdown(result)

        except Exception as e:
            st.error("❌ AI分析失败，请检查Key")
            st.text(e)
