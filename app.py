import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI

st.set_page_config(layout="wide")

# ===== API =====
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

# ===== UI =====
st.title("📊 AI股票分析平台")
st.caption("趋势判断 · 风险提示 · 投资建议")

# ===== 布局 =====
left, right = st.columns([1, 2])

with left:
    st.subheader("⚙️ 参数设置")

    ticker = st.text_input("股票代码", "000066.SZ")
    period = st.selectbox("周期", ["5d", "1mo", "3mo"])
    risk = st.selectbox("风险偏好", ["低", "中", "高"])

    run = st.button("🚀 开始分析", use_container_width=True)

with right:
    if run:

        data = yf.download(ticker, period=period)

        if data.empty:
            st.error("❌ 没有数据")
        else:
            data = data.reset_index()

            # ===== 统一列名（关键修复）=====
            data.columns = [col.lower() for col in data.columns]

            # ===== 判断市场 =====
            is_cn = ".SZ" in ticker or ".SH" in ticker

            # ===== K线 =====
            fig = go.Figure()

            fig.add_trace(go.Candlestick(
                x=data["date"],
                open=data["open"],
                high=data["high"],
                low=data["low"],
                close=data["close"],
                increasing_line_color="red" if is_cn else "green",
                decreasing_line_color="green" if is_cn else "red"
            ))

            fig.update_layout(
                height=400,
                margin=dict(l=10, r=10, t=20, b=10),
                xaxis_rangeslider_visible=False
            )

            st.plotly_chart(fig, use_container_width=True)

            # ===== KPI（不会再报错）=====
            latest = data.iloc[-1]

            change = latest["close"] - latest["open"]
            pct = (change / latest["open"]) * 100

            c1, c2, c3, c4 = st.columns(4)

            c1.metric("最新价", f"{latest['close']:.2f}")
            c2.metric("涨跌", f"{change:.2f}")
            c3.metric("涨幅", f"{pct:.2f}%")
            c4.metric("成交量", f"{latest['volume']/1e6:.2f}M")

            # ===== AI =====
            prompt = f"""
请用中文分析股票 {ticker}：

{data.tail().to_string()}

输出：
1. 趋势（简短）
2. 建议（买/观望/卖）
3. 风险
"""

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )

            st.markdown("---")
            st.subheader("🤖 AI分析")

            st.write(response.choices[0].message.content)
