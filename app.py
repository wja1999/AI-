import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI
import pandas as pd

st.set_page_config(layout="wide")

# ===== API =====
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

# ===== UI =====
st.title("📊 AI股票分析平台")
st.caption("趋势判断 · 风险提示 · 投资建议")

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

        if data is None or data.empty:
            st.error("❌ 没有获取到数据")
        else:
            # ===== 彻底兜底处理 =====
            data = data.copy()

            # reset index
            if not isinstance(data.index, pd.RangeIndex):
                data = data.reset_index()

            # 展平列名（关键）
            data.columns = [
                "_".join(col) if isinstance(col, tuple) else str(col)
                for col in data.columns
            ]

            # 全部小写
            data.columns = [col.lower() for col in data.columns]

            # ===== 字段兼容 =====
            def pick(col_list):
                for c in col_list:
                    if c in data.columns:
                        return data[c]
                return None

            open_col = pick(["open"])
            high_col = pick(["high"])
            low_col = pick(["low"])
            close_col = pick(["close", "adj close"])
            volume_col = pick(["volume"])

            date_col = pick(["date", "datetime"])

            if date_col is None:
                date_col = data.index

            if close_col is None:
                st.error("❌ 数据缺少收盘价，无法绘制K线")
                st.stop()

            # ===== 判断市场 =====
            is_cn = ".SZ" in ticker or ".SH" in ticker

            # ===== K线 =====
            fig = go.Figure()

            fig.add_trace(go.Candlestick(
                x=date_col,
                open=open_col if open_col is not None else close_col,
                high=high_col if high_col is not None else close_col,
                low=low_col if low_col is not None else close_col,
                close=close_col,
                increasing_line_color="red" if is_cn else "green",
                decreasing_line_color="green" if is_cn else "red"
            ))

            fig.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=20, b=10),
                xaxis_rangeslider_visible=False
            )

            st.plotly_chart(fig, use_container_width=True)

            # ===== KPI（完全兜底）=====
            latest = data.iloc[-1]

            def safe_val(col):
                return float(latest[col]) if col in latest and pd.notna(latest[col]) else 0

            open_p = safe_val("open")
            close_p = safe_val("close") if "close" in data.columns else safe_val("adj close")
            volume = safe_val("volume")

            change = close_p - open_p
            pct = (change / open_p * 100) if open_p != 0 else 0

            c1, c2, c3, c4 = st.columns(4)

            c1.metric("最新价", f"{close_p:.2f}")
            c2.metric("涨跌", f"{change:.2f}")
            c3.metric("涨幅", f"{pct:.2f}%")
            c4.metric("成交量", f"{volume/1e6:.2f}M")

            # ===== AI =====
            prompt = f"""
请用中文分析股票 {ticker}：

{data.tail().to_string()}

输出：
1. 趋势（简短）
2. 建议（买/观望/卖）
3. 风险
"""

            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}]
                )

                st.markdown("---")
                st.subheader("🤖 AI分析")
                st.write(response.choices[0].message.content)

            except Exception as e:
                st.warning("⚠️ AI分析失败（可能是key或网络问题）")
