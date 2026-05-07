import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from openai import OpenAI

# ========= 页面配置 =========
st.set_page_config(layout="wide")

# ========= API =========
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

# ========= UI样式（核心优化）=========
st.markdown("""
<style>

body {
    background: linear-gradient(135deg, #f6f9fc, #eef3f8);
}

/* 标题 */
.title {
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 5px;
}

/* 卡片（磨砂玻璃） */
.card {
    background: rgba(255,255,255,0.7);
    backdrop-filter: blur(12px);
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.05);
}

/* 左侧区域 */
.sidebar-card {
    height: 100%;
}

/* 右侧布局 */
.right-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

/* 分析文字 */
.analysis-box {
    font-size: 14px;
    line-height: 1.6;
}

/* KPI区域 */
.kpi {
    display: flex;
    gap: 12px;
}

.kpi-box {
    flex: 1;
    padding: 10px;
    border-radius: 10px;
    background: #ffffff;
    text-align: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}

</style>
""", unsafe_allow_html=True)

# ========= 主布局 =========
left, right = st.columns([1, 2])

# ========= 左侧 =========
with left:
    st.markdown('<div class="card sidebar-card">', unsafe_allow_html=True)

    st.markdown('<div class="title">📊 参数设置</div>', unsafe_allow_html=True)

    ticker = st.text_input("股票代码", "000066.SZ")

    period = st.selectbox(
        "周期",
        ["5d", "1mo", "3mo", "6mo"]
    )

    risk = st.selectbox(
        "风险偏好",
        ["低", "中", "高"]
    )

    run = st.button("🚀 开始分析")

    st.markdown('</div>', unsafe_allow_html=True)

# ========= 右侧 =========
with right:
    st.markdown('<div class="right-container">', unsafe_allow_html=True)

    if run:

        data = yf.download(ticker, period=period)

        if data.empty:
            st.error("❌ 无数据")
        else:

            # ===== 数据处理 =====
            data = data.reset_index()

            # ===== K线图 =====
            fig = go.Figure()

            # 判断A股（红涨绿跌）
            is_cn = ".SZ" in ticker or ".SH" in ticker

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
                plot_bgcolor="white",
                paper_bgcolor="white"
            )

            # ===== KPI =====
            latest = data.iloc[-1]
            change = latest["Close"] - latest["Open"]

            st.markdown('<div class="kpi">', unsafe_allow_html=True)
            st.markdown(f'<div class="kpi-box">价格<br><b>{latest["Close"]:.2f}</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="kpi-box">涨跌<br><b>{change:.2f}</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="kpi-box">成交量<br><b>{latest["Volume"]/1000000:.2f}M</b></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # ===== 图表卡片 =====
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # ===== AI分析 =====
            prompt = f"""
你是专业股票分析师，用中文分析股票 {ticker}：

数据：
{data.tail().to_string()}

请输出：
1. 趋势
2. 建议
3. 风险
（控制在200字内，专业一点）
"""

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )

            result = response.choices[0].message.content

            st.markdown('<div class="card analysis-box">', unsafe_allow_html=True)
            st.markdown("### 🤖 AI投资分析")
            st.write(result)
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
