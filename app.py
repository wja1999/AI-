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

st.set_page_config(page_title="AI股票分析", layout="centered")

st.title("📈 AI 股票分析")
st.caption("趋势判断 · 风险提示 · 买卖建议")

ticker = st.text_input("股票代码", "AAPL")
period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"])
risk = st.selectbox("风险偏好", ["低", "中", "高"], index=1)

if st.button("🚀 开始分析"):

    data = yf.download(ticker, period=period, progress=False)

    # ========= 1. 数据检查 =========
    if data is None or data.empty:
        st.error("❌ 没拿到数据，建议先试 AAPL")
        st.stop()

    # ========= 2. 修复列结构 =========
    # 有些情况是 MultiIndex
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    # ========= 3. 标准列名 =========
    data.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume"
    }, inplace=True)

    # ========= 4. 清洗 =========
    data = data[["open", "high", "low", "close"]].dropna()

    if data.empty:
        st.error("❌ 数据清洗后为空")
        st.write(data)
        st.stop()

    # ========= 5. 重建坐标 =========
    df = data.reset_index()
    df["x"] = range(len(df))

    # ========= 6. K线 =========
    fig = go.Figure(data=[go.Candlestick(
        x=df["x"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        increasing_line_color="#00C853",
        decreasing_line_color="#FF3D00"
    )])

    fig.update_layout(
        template="plotly_dark",
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            tickmode='array',
            tickvals=df["x"][::max(1, len(df)//6)],
            ticktext=df.iloc[:,0].dt.strftime('%m-%d')[::max(1, len(df)//6)]
        ),
        yaxis=dict(title="价格")
    )

    st.plotly_chart(fig, use_container_width=True)
    st.success("✅ K线加载完成")

    # ========= 7. AI分析 =========
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

        st.subheader("📊 AI分析结果")
        st.markdown(result)

    except Exception as e:
        st.error("❌ AI分析失败")
        st.text(e)
