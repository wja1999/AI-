import streamlit as st
import yfinance as yf
from openai import OpenAI
import plotly.graph_objects as go
import pandas as pd

# 🔐 key
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

# 页面
st.set_page_config(layout="wide")

# ======================
# 🎨 UI 样式（重点）
# ======================
st.markdown("""
<style>
body {
    background: linear-gradient(135deg,#f5f7fa,#e4ecf7);
}

.block-container {
    padding-top: 2rem;
}

/* 标题 */
h1 {
    font-weight: 700;
    letter-spacing: 1px;
}

/* 卡片（磨砂玻璃） */
.glass {
    background: rgba(255,255,255,0.65);
    backdrop-filter: blur(14px);
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.05);
}

/* 输入框 */
.stTextInput>div>div>input {
    border-radius: 10px;
}

/* 按钮 */
.stButton>button {
    border-radius: 12px;
    height: 44px;
    width: 100%;
    font-weight: 600;
}

/* 标题区 */
.title-box {
    font-size: 26px;
    font-weight: 700;
    margin-bottom: 10px;
}

/* 子标题 */
.sub {
    color: #666;
    font-size: 14px;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# ======================
# 🧠 标题
# ======================
st.markdown('<div class="title-box">📈 AI 股票分析平台</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">趋势判断 · 风险提示 · 投资建议</div>', unsafe_allow_html=True)

# ======================
# 🧱 布局
# ======================
col1, col2 = st.columns([1, 3])

# ======================
# 左侧：参数卡片
# ======================
with col1:
    st.markdown('<div class="glass">', unsafe_allow_html=True)

    st.subheader("⚙️ 参数设置")

    ticker = st.text_input("股票代码", "000066.SZ")
    period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"])
    risk = st.selectbox("风险偏好", ["低", "中", "高"])

    run = st.button("🚀 开始分析")

    st.markdown('</div>', unsafe_allow_html=True)

# ======================
# 右侧：主内容
# ======================
with col2:

    st.markdown('<div class="glass">', unsafe_allow_html=True)

    st.subheader("📊 市场走势")

    if run:

        data = yf.download(ticker, period=period, progress=False)

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close"
        }, inplace=True)

        data = data[["open", "high", "low", "close"]].dropna()

        df = data.reset_index()
        df["x"] = range(len(df))

        # 🎯 A股 / 美股颜色
        if ticker.endswith(".SZ") or ticker.endswith(".SS"):
            up = "#ff3b30"
            down = "#00c853"
        else:
            up = "#00c853"
            down = "#ff3b30"

        fig = go.Figure(data=[go.Candlestick(
            x=df["x"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            increasing_fillcolor=up,
            increasing_line_color=up,
            decreasing_fillcolor=down,
            decreasing_line_color=down
        )])

        fig.update_layout(
            template="plotly_white",
            height=420,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(
                tickmode='array',
                tickvals=df["x"][::max(1,len(df)//6)],
                ticktext=df.iloc[:,0].dt.strftime('%m-%d')[::max(1,len(df)//6)]
            )
        )

        st.plotly_chart(fig, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ======================
    # 🤖 AI 分析卡片
    # ======================
    if run:
        st.markdown('<div class="glass">', unsafe_allow_html=True)

        st.subheader("🤖 AI 投资分析")

        prompt = f"""
分析股票 {ticker}：

{data.tail().to_string()}

风险偏好：{risk}

输出：
1. 趋势
2. 买卖建议
3. 风险
"""

        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"user","content":prompt}]
        )

        st.write(res.choices[0].message.content)

        st.markdown('</div>', unsafe_allow_html=True)
