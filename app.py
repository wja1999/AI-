import streamlit as st
import yfinance as yf
from openai import OpenAI
import plotly.graph_objects as go
import pandas as pd

client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

st.set_page_config(layout="wide")

# ======================
# 🎨 真正的浅色科技UI
# ======================
st.markdown("""
<style>

body {
    background: linear-gradient(120deg,#f7f9fc,#eef3f8);
}

/* 主容器压缩高度（关键） */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 0rem;
}

/* 标题 */
.title {
    font-size: 26px;
    font-weight: 700;
    margin-bottom: 4px;
}
.subtitle {
    color: #666;
    font-size: 13px;
    margin-bottom: 10px;
}

/* 卡片（玻璃） */
.card {
    background: rgba(255,255,255,0.7);
    backdrop-filter: blur(18px);
    border-radius: 14px;
    padding: 14px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.06);
    margin-bottom: 10px;
}

/* 输入 */
.stTextInput input {
    border-radius: 8px;
}

/* 按钮 */
.stButton button {
    border-radius: 10px;
    height: 38px;
    font-weight: 600;
}

/* 图表压缩 */
.element-container {
    margin-bottom: 0px !important;
}

</style>
""", unsafe_allow_html=True)

# ======================
# 标题
# ======================
st.markdown('<div class="title">📈 AI 股票分析</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">趋势判断 · 风险提示 · 投资建议</div>', unsafe_allow_html=True)

# ======================
# 布局（核心：一屏）
# ======================
left, right = st.columns([1, 3])

# ======================
# 左侧参数
# ======================
with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    ticker = st.text_input("股票代码", "000066.SZ")
    period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"])
    risk = st.selectbox("风险偏好", ["低", "中", "高"])

    run = st.button("🚀 分析")

    st.markdown('</div>', unsafe_allow_html=True)

# ======================
# 右侧主区域
# ======================
with right:

    st.markdown('<div class="card">', unsafe_allow_html=True)

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

        # A股红涨
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
            height=340,  # 👈 压缩高度实现一屏
            margin=dict(l=5, r=5, t=5, b=5),
            xaxis=dict(
                tickmode='array',
                tickvals=df["x"][::max(1,len(df)//5)],
                ticktext=df.iloc[:,0].dt.strftime('%m-%d')[::max(1,len(df)//5)]
            )
        )

        st.plotly_chart(fig, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ======================
    # AI 卡片（压缩版）
    # ======================
    if run:

        st.markdown('<div class="card">', unsafe_allow_html=True)

        prompt = f"""
你是专业A股分析师，请用中文输出，简洁专业：

股票：{ticker}
数据：
{data.tail().to_string()}

要求：
1. 趋势（一句话）
2. 建议（买/观望/减仓）
3. 风险（一句话）
"""

        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"user","content":prompt}]
        )

        st.markdown("### 🤖 AI分析")
        st.write(res.choices[0].message.content)

        st.markdown('</div>', unsafe_allow_html=True)
