import streamlit as st
import yfinance as yf
from openai import OpenAI
import plotly.graph_objects as go
import pandas as pd
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# 🔐 填你的 DeepSeek key
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

st.set_page_config(page_title="AI股票分析", layout="centered")

st.title("📈 AI 股票分析")
st.caption("短线技术分析 · 最新消息面 · 政策面辅助")

def normalize_ticker(raw):
    code = raw.strip().upper()

    if code.endswith(".SH"):
        return code.replace(".SH", ".SS")

    if code.endswith(".SZ") or code.endswith(".SS") or code.endswith(".HK"):
        return code

    if code.isdigit() and len(code) == 6:
        if code.startswith(("6", "9")):
            return code + ".SS"
        elif code.startswith(("0", "3")):
            return code + ".SZ"

    return code

def fetch_news(query, max_items=6):
    try:
        q = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(req, timeout=8) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = []

        for item in root.findall(".//item")[:max_items]:
            title = item.findtext("title", default="")
            link = item.findtext("link", default="")
            pub_date = item.findtext("pubDate", default="")

            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "date": pub_date
                })

        return items

    except Exception:
        return []

ticker_input = st.text_input("股票代码", "000066")
period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"])
risk = st.selectbox("风险偏好", ["低", "中", "高"], index=1)

if st.button("🚀 开始分析"):

    ticker = normalize_ticker(ticker_input)
    st.info(f"当前查询代码：{ticker}")

    data = yf.download(ticker, period=period, progress=False)

    if data is None or data.empty:
        st.error("❌ 没拿到数据。沪市用 600519 或 600519.SS；深市用 000001 或 000001.SZ。")
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

    # ======================
    # 📰 最新消息面 / 政策面
    # ======================
    news_query = f"{ticker_input} 股票 财经 新闻 利好 利空"
    policy_query = "A股 政策 证监会 央行 财经 市场"

    stock_news = fetch_news(news_query, max_items=5)
    policy_news = fetch_news(policy_query, max_items=4)

    st.subheader("📰 最新消息面")
    if stock_news:
        for n in stock_news:
            st.markdown(f"- [{n['title']}]({n['link']})")
    else:
        st.info("暂未抓取到该股相关新闻，可继续参考技术面。")

    st.subheader("🏛️ 政策面参考")
    if policy_news:
        for n in policy_news:
            st.markdown(f"- [{n['title']}]({n['link']})")
    else:
        st.info("暂未抓取到政策面新闻。")

    news_text = "\n".join([f"- {n['title']}" for n in stock_news])
    policy_text = "\n".join([f"- {n['title']}" for n in policy_news])

    prompt = f"""
你是专业A股股票分析师，请用中文分析股票 {ticker}。

最近行情：
{data.tail().to_string()}

最新个股消息面：
{news_text if news_text else "暂无抓取到相关新闻"}

最新政策面/市场环境：
{policy_text if policy_text else "暂无抓取到政策新闻"}

风险偏好：{risk}

请严格输出：
1. 趋势判断
2. 消息面影响
3. 政策面影响
4. 买卖建议
5. 风险提示

要求：
- 语言简洁
- 不要英文
- 不要承诺收益
- 给出偏短线视角
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content

        st.subheader("📊 AI综合分析结果")
        st.markdown(result)

    except Exception as e:
        st.error("❌ AI分析失败")
        st.text(e)
