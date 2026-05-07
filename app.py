import streamlit as st
import yfinance as yf
from openai import OpenAI

# 👉 填你的 DeepSeek key
client = OpenAI(
    api_key="你的DeepSeek key",
    base_url="https://api.deepseek.com"
)

st.title("📈 AI 股票分析工具")

ticker = st.text_input("输入股票代码（A股示例：000001.SZ）", "AAPL")

if st.button("开始分析"):

    data = yf.download(ticker, period="5d")

    if data.empty:
        st.error("❌ 没获取到数据，检查代码是否正确")
    else:
        st.write(data.tail())

        prompt = f"""
你是专业股票分析师，请分析股票 {ticker}：

{data.tail().to_string()}

请给出：
1. 趋势判断
2. 是否值得买入
3. 风险提示
"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content

        st.subheader("📊 AI分析结果")
        st.write(result)
