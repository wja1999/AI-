import streamlit as st
import yfinance as yf
from openai import OpenAI
import plotly.graph_objects as go
import pandas as pd

# 🔐 填你的 DeepSeek key
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

st.set_page_config(page_title="AI股票分析", layout="centered")

st.title("📈 AI 股票分析")
st.caption("趋势判断 · 风险提示 · 买卖建议")

def normalize_ticker(raw):
    code = raw.strip().upper()

    # 沪市常见错误：.SH 改成 .SS
    if code.endswith(".SH"):
        return code.replace(".SH", ".SS")

    # 已经是标准格式
    if code.endswith(".SZ") or code.endswith(".SS") or code.endswith(".HK"):
        return code

    # 纯6位A股代码自动识别
    if code.isdigit() and len(code) == 6:
        if code.startswith(("6", "9")):
            return code + ".SS"   # 沪市
        elif code.startswith(("0", "3")):
            return code + ".SZ"   # 深市/创业板

    # 美股直接返回，例如 AAPL / TSLA / NVDA
    return code

ticker_input = st.text_input("股票代码", "000066")
period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"])
risk = st.selectbox("风险偏好", ["低", "中", "高"], index=1)

if st.button("🚀 开始分析"):

    ticker = normalize_ticker(ticker_input)

    st.info(f"当前查询代码：{ticker}")

    data = yf.download(ticker, period=period, progress=False)

    if data is None or data.empty:
        st.error("❌ 没拿到数据。沪市请用 600519 或 600519.SS；深市用 000001 或 000001.SZ。")
        st.stop()

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

    need_cols = ["open", "high", "low", "close"]
    if not all(col in data.columns for col in need_cols):
        st.error(f"❌ 数据字段异常：{list(data.columns)}")
        st.stop()

    data = data[need_cols].dropna()

    if data.empty:
        st.error("❌ 数据为空")
        st.stop()

    # A股：涨红跌绿；美股：涨绿跌红
    if ticker.endswith(".SZ") or ticker.endswith(".SS"):
        up_color = "#FF3B30"
        down_color = "#00C853"
    else:
        up_color = "#00C853"
        down_color = "#FF3B30"

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
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            tickmode="array",
            tickvals=df["x"][::max(1, len(df)//6)],
            ticktext=df.iloc[:, 0].dt.strftime("%m-%d")[::max(1, len(df)//6)]
        ),
        yaxis=dict(title="价格"),
        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(fig, use_container_width=True)
    st.success("✅ K线加载完成")

    prompt = f"""
你是专业股票分析师，请用中文分析股票 {ticker}：

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
