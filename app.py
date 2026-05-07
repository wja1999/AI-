import streamlit as st
import yfinance as yf
from openai import OpenAI

# ===== 页面配置 =====
st.set_page_config(
    page_title="AI股票分析",
    page_icon="📈",
    layout="wide"
)

# ===== UI样式（高级暗黑风）=====
st.markdown("""
<style>
.stApp {
    background-color: #0e1117;
    color: #ffffff;
}

h1 {
    text-align: center;
    font-weight: 700;
}

.card {
    background-color: #161b22;
    padding: 25px;
    border-radius: 16px;
    box-shadow: 0 0 20px rgba(0,0,0,0.4);
    margin-bottom: 20px;
}

.stButton>button {
    background: linear-gradient(90deg,#ff4b2b,#ff416c);
    color: white;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: bold;
}

.stTextInput>div>div>input {
    background-color: #1e2228;
    color: white;
}

</style>
""", unsafe_allow_html=True)

# ===== DeepSeek =====
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

# ===== 标题 =====
st.markdown("""
<h1>📱 AI股票分析助手</h1>
<p style='text-align:center;color:#aaa;'>智能分析 · 趋势判断 · 风险提示</p>
""", unsafe_allow_html=True)

# ===== 输入卡片 =====
st.markdown('<div class="card">', unsafe_allow_html=True)

ticker = st.text_input("输入股票代码（A股示例：000001.SZ）", "AAPL")

run = st.button("🚀 开始分析")

st.markdown('</div>', unsafe_allow_html=True)

# ===== 分析逻辑 =====
if run:

    with st.spinner("📊 正在获取数据..."):
        data = yf.download(ticker, period="5d")

    if data.empty:
        st.error("❌ 没获取到数据，检查代码是否正确")
    else:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        st.subheader("📈 最新数据")
        st.dataframe(data.tail())

        st.markdown('</div>', unsafe_allow_html=True)

        prompt = f"""
你是专业股票分析师，请分析股票 {ticker}：

{data.tail().to_string()}

请给出：
1. 趋势判断
2. 是否值得买入
3. 风险提示
"""

        with st.spinner("🤖 AI分析中..."):
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )

        result = response.choices[0].message.content

        st.markdown('<div class="card">', unsafe_allow_html=True)

        st.subheader("📊 AI分析结果")
        st.write(result)

        st.markdown('</div>', unsafe_allow_html=True)
