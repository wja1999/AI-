import streamlit as st
import yfinance as yf
from openai import OpenAI

# ====== 在这里填你的 KEY ======
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

st.set_page_config(page_title="AI股票分析", layout="centered")

# ===== UI =====
st.markdown("""
<h2 style='text-align: center;'>📈 AI 股票分析</h2>
<p style='text-align: center; color: gray;'>智能趋势判断 · 风险提示 · 买卖建议</p>
""", unsafe_allow_html=True)

ticker = st.text_input("股票代码", "AAPL")

col1, col2 = st.columns(2)
period = col1.selectbox("周期", ["5d", "1mo", "3mo"])
risk = col2.selectbox("风险偏好", ["低", "中", "高"])

# ===== 按钮 =====
if st.button("🚀 开始分析", use_container_width=True):

    with st.spinner("AI正在分析中..."):

        try:
            df = yf.download(ticker, period=period)

            if df.empty:
                st.error("❌ 没获取到数据")
            else:
                st.line_chart(df["Close"])

                prompt = f"""
你是顶级股票分析师，请分析 {ticker}：

{df.tail().to_string()}

用户风险偏好：{risk}

请输出：
1. 趋势判断
2. 是否建议买入
3. 风险提示
"""

                res = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}]
                )

                st.success("分析完成")

                st.markdown("### 📊 AI分析结果")
                st.write(res.choices[0].message.content)

        except Exception as e:
            st.error(f"出错了：{str(e)}")
