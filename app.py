import streamlit as st
import yfinance as yf
from openai import OpenAI

# ===== 页面配置（关键：移动端适配）=====
st.set_page_config(
    page_title="AI股票助手",
    page_icon="📈",
    layout="centered"  # 👈 手机必须用这个
)

# ===== 移动端 UI 样式 =====
st.markdown("""
<style>

/* 整体 */
.stApp {
    background-color: #0e1117;
    color: white;
    font-size: 16px;
}

/* 标题 */
.title {
    text-align: center;
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 5px;
}

.subtitle {
    text-align: center;
    font-size: 13px;
    color: #aaa;
    margin-bottom: 20px;
}

/* 卡片 */
.card {
    background: #161b22;
    padding: 18px;
    border-radius: 14px;
    margin-bottom: 15px;
}

/* 输入框 */
input {
    font-size: 16px !important;
}

/* 按钮（大按钮） */
.stButton>button {
    width: 100%;
    padding: 14px;
    font-size: 16px;
    border-radius: 12px;
    background: linear-gradient(90deg,#ff4b2b,#ff416c);
    color: white;
    font-weight: bold;
}

/* 数据表 */
[data-testid="stDataFrame"] {
    font-size: 12px;
}

</style>
""", unsafe_allow_html=True)

# ===== DeepSeek =====
client = OpenAI(
    api_key=st.secrets["sk-34bde63deba4488c939677b2a93fbb01"],
    base_url="https://api.deepseek.com"
)

# ===== 顶部 =====
st.markdown('<div class="title">📱 AI股票分析助手</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">趋势判断 · 买卖建议 · 风险分析</div>', unsafe_allow_html=True)

# ===== 输入卡片 =====
st.markdown('<div class="card">', unsafe_allow_html=True)

ticker = st.text_input("股票代码", "AAPL")

run = st.button("🚀 开始分析")

st.markdown('</div>', unsafe_allow_html=True)

# ===== 分析 =====
if run:

    with st.spinner("📊 获取行情中..."):
        data = yf.download(ticker, period="5d")

    if data.empty:
        st.error("❌ 股票代码错误")
    else:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        st.markdown("### 📈 最新行情")
        st.dataframe(data.tail(), use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

        prompt = f"""
你是A股投资分析助手，请基于A股交易逻辑分析以下个股：

股票：{ticker}

数据：
{data.tail().to_string()}

请输出：
1. 趋势判断
2. 是否建议买入
3. 核心风险
"""

        with st.spinner("🤖 AI分析中..."):
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )

        result = response.choices[0].message.content

        st.markdown('<div class="card">', unsafe_allow_html=True)

        st.markdown("### 🤖 AI分析")
        st.write(result)

        st.markdown('</div>', unsafe_allow_html=True)
