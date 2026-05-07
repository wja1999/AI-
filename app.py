import streamlit as st
import yfinance as yf
from openai import OpenAI
import plotly.graph_objects as go
import pandas as pd

# ======================
# 🔐 填你的 key
# ======================
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

st.set_page_config(page_title="AI股票分析", layout="centered")

st.title("📈 AI 股票分析")
st.caption("趋势判断 · 风险提示 · 买卖建议")

ticker = st.text_input("股票代码", "000066.SZ")

period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"])
risk = st.selectbox("风险偏好", ["低", "中", "高"], index=1)

# ======================
# 🚀 开始分析
# ======================
if st.button("🚀 开始分析"):

    # 👉 关键：关闭progress，否则可能卡
    data = yf.download(ticker, period=period, progress=False)

    # ========= 核心修复1：空数据 =========
    if data is None or data.empty:
        st.error("❌ 没拿到数据（A股有时不稳定）")
        st.stop()

    # ========= 核心修复2：清洗数据 =========
    data = data.dropna()

    if len(data) < 2:
        st.error("❌ 数据不足，无法画K线")
        st.write(data)
        st.stop()

    # ========= 核心修复3：列名统一 =========
    data.columns = [col.lower() for col in data.columns]

    # ========= 核心修复4：索引问题 =========
    df = data.reset_index()

    if "date" not in df.columns:
        df.rename(columns={df.columns[0]: "date"}, inplace=True)

    # ========= 核心修复5：连续坐标 =========
    df["x"] = range(len(df))

    # ========= 核心修复6：数值类型 =========
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna()

    # ========= 关键：确保有数据 =========
    if df.empty:
        st.error("❌ 数据清洗后为空")
        st.write(data.tail())
        st.stop()

    # ======================
    # 📈 K线图
    # ======================
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
            ticktext=df["date"].dt.strftime('%m-%d')[::max(1, len(df)//6)]
        ),
        yaxis=dict(title="价格")
    )

    st.plotly_chart(fig, use_container_width=True)

    st.success("✅ 数据加载完成")

    # ======================
    # 🤖 AI分析
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
        st.error("❌ AI分析失败")
        st.text(e)
