import streamlit as st
import yfinance as yf
from openai import OpenAI
import plotly.graph_objects as go
import pandas as pd

# 🔐 填你的 key
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

# 页面设置（关键：wide）
st.set_page_config(page_title="AI股票分析", layout="wide")

st.title("📈 AI 股票分析")
st.caption("趋势判断 · 风险提示 · 买卖建议")

# ======================
# 🎯 左右布局
# ======================
left, right = st.columns([1, 2])

with left:
    st.subheader("⚙️ 参数设置")

    ticker = st.text_input("股票代码", "AAPL")
    period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"])
    risk = st.selectbox("风险偏好", ["低", "中", "高"], index=1)

    run = st.button("🚀 开始分析")

with right:
    st.subheader("📊 分析结果区域")

# ======================
# 🚀 执行逻辑
# ======================
if run:

    data = yf.download(ticker, period=period, progress=False)

    if data is None or data.empty:
        right.error("❌ 没拿到数据，建议先试 AAPL")
        st.stop()

    # 修复列结构
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume"
    }, inplace=True)

    data = data[["open", "high", "low", "close"]].dropna()

    if data.empty:
        right.error("❌ 数据为空")
        st.stop()

    # ======================
    # 🎯 判断市场颜色
    # ======================
    if ticker.endswith(".SZ") or ticker.endswith(".SS"):
        up_color = "#FF3B30"     # A股涨红
        down_color = "#00C853"
    else:
        up_color = "#00C853"     # 美股涨绿
        down_color = "#FF3B30"

    # ======================
    # 📈 K线
    # ======================
    df = data.reset_index()
    df["x"] = range(len(df))

    fig = go.Figure(data=[go.Candlestick(
        x=df["x"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        increasing_line_color=up_color,
        increasing_fillcolor=up_color,
        decreasing_line_color=down_color,
        decreasing_fillcolor=down_color
    )])

    fig.update_layout(
        template="plotly_dark",
        height=500,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            tickmode='array',
            tickvals=df["x"][::max(1, len(df)//6)],
            ticktext=df.iloc[:, 0].dt.strftime('%m-%d')[::max(1, len(df)//6)]
        ),
        yaxis=dict(title="价格")
    )

    right.plotly_chart(fig, use_container_width=True)
    right.success("✅ K线加载完成")

    # ======================
    # 🤖 AI分析
    # ======================
    prompt = f"""
你是专业股票分析师，请分析股票 {ticker}：

最近行情：
{data.tail().to_string()}

风险偏好：{risk}

请给出：
1. 趋势判断
2. 买卖建议
3. 风险提示
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content

        right.subheader("🤖 AI分析")
        right.markdown(result)

    except Exception as e:
        right.error("❌ AI分析失败")
        right.text(e)
