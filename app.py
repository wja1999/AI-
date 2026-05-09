import streamlit as st
import yfinance as yf
from openai import OpenAI
import plotly.graph_objects as go
import pandas as pd
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import re

# ======================
# 🔐 DeepSeek API 配置
# ======================
# 这里填你的 DeepSeek key
client = OpenAI(
    api_key="sk-34bde63deba4488c939677b2a93fbb01",
    base_url="https://api.deepseek.com"
)

st.set_page_config(page_title="AI股票分析", layout="centered")

st.title("📈 AI 股票分析")
st.caption("短线技术分析 · 消息面辅助 · 政策面参考 · 操作计划")

# ======================
# 工具函数
# ======================
def normalize_ticker(raw_code):
    code = raw_code.strip().upper()

    if code.endswith(".SH"):
        return code.replace(".SH", ".SS")

    if code.endswith(".SZ") or code.endswith(".SS"):
        return code

    if code.isdigit() and len(code) == 6:
        if code.startswith(("6", "9")):
            return code + ".SS"
        if code.startswith(("0", "3")):
            return code + ".SZ"

    return code


def clean_title(title):
    title = re.sub(r"\s+", " ", title or "").strip()
    title = title.replace(" - Google News", "")
    return title


def fetch_rss(url, max_items=6):
    items = []

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        with urllib.request.urlopen(req, timeout=8) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)

        for item in root.findall(".//item"):
            title = clean_title(item.findtext("title", default=""))
            link = item.findtext("link", default="")
            pub_date = item.findtext("pubDate", default="")

            if title and link:
                items.append({
                    "title": title,
                    "link": link,
                    "date": pub_date
                })

            if len(items) >= max_items:
                break

    except Exception:
        pass

    return items


def fetch_stock_news(stock_name, ticker_input, max_items=8):
    query_base = stock_name.strip() if stock_name.strip() else ticker_input.strip()

    search_queries = [
        f"{query_base} 股票 最新消息",
        f"{query_base} 财经 新闻 利好 利空",
        f"{query_base} 研报 股东 减持 增持 回购",
        f"{query_base} 公告 业绩 订单 合作"
    ]

    all_news = []

    for q in search_queries:
        encoded = urllib.parse.quote(q)

        google_url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        bing_url = f"https://www.bing.com/news/search?q={encoded}&format=rss"

        all_news.extend(fetch_rss(google_url, max_items=4))
        all_news.extend(fetch_rss(bing_url, max_items=4))

    # 去重
    seen = set()
    unique_news = []

    for item in all_news:
        title_key = item["title"][:40]

        if title_key not in seen:
            seen.add(title_key)
            unique_news.append(item)

        if len(unique_news) >= max_items:
            break

    return unique_news


def fetch_policy_news(max_items=5):
    queries = [
        "A股 政策 证监会 央行 最新",
        "资本市场 政策 利好 A股",
        "中国 股市 政策 面 资金面"
    ]

    all_news = []

    for q in queries:
        encoded = urllib.parse.quote(q)

        google_url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        bing_url = f"https://www.bing.com/news/search?q={encoded}&format=rss"

        all_news.extend(fetch_rss(google_url, max_items=3))
        all_news.extend(fetch_rss(bing_url, max_items=3))

    seen = set()
    unique_news = []

    for item in all_news:
        title_key = item["title"][:40]

        if title_key not in seen:
            seen.add(title_key)
            unique_news.append(item)

        if len(unique_news) >= max_items:
            break

    return unique_news


def calc_indicators(data):
    df = data.copy()

    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()

    df["pct_chg"] = df["close"].pct_change() * 100

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd_dif"] = ema12 - ema26
    df["macd_dea"] = df["macd_dif"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = (df["macd_dif"] - df["macd_dea"]) * 2

    low_min = df["low"].rolling(9).min()
    high_max = df["high"].rolling(9).max()
    rsv = (df["close"] - low_min) / (high_max - low_min) * 100
    df["kdj_k"] = rsv.ewm(com=2).mean()
    df["kdj_d"] = df["kdj_k"].ewm(com=2).mean()
    df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]

    return df


def fmt_num(value):
    try:
        if pd.isna(value):
            return "暂无"
        return f"{float(value):.2f}"
    except Exception:
        return "暂无"


# ======================
# 输入区
# ======================
ticker_input = st.text_input("股票代码", "000066")
stock_name = st.text_input("股票名称（建议填写中文名，用于抓取新闻）", "中国长城")
period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"])
risk = st.selectbox("风险偏好", ["低", "中", "高"], index=1)

if st.button("🚀 开始分析"):

    ticker = normalize_ticker(ticker_input)

    # ======================
    # 获取行情数据
    # ======================
    data = yf.download(ticker, period=period, progress=False)

    if data is None or data.empty:
        st.error("❌ 没拿到数据。沪市示例：600519 或 600519.SS；深市示例：000001 或 000001.SZ。")
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

    need_cols = ["open", "high", "low", "close", "volume"]
    if not all(col in data.columns for col in need_cols):
        st.error(f"❌ 数据字段异常：{list(data.columns)}")
        st.stop()

    data = data[need_cols].dropna()

    if data.empty:
        st.error("❌ 数据为空")
        st.stop()

    data = calc_indicators(data)

    latest = data.iloc[-1]
    prev = data.iloc[-2] if len(data) >= 2 else latest

    latest_close = latest["close"]
    day_pct = ((latest["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] else 0

    # ======================
    # A股 / 美股颜色
    # ======================
    if ticker.endswith(".SZ") or ticker.endswith(".SS"):
        up_color = "#FF3B30"
        down_color = "#00C853"
    else:
        up_color = "#00C853"
        down_color = "#FF3B30"

    # ======================
    # K线图
    # ======================
    df_plot = data.reset_index()
    df_plot["x"] = range(len(df_plot))

    fig = go.Figure(data=[go.Candlestick(
        x=df_plot["x"],
        open=df_plot["open"],
        high=df_plot["high"],
        low=df_plot["low"],
        close=df_plot["close"],
        increasing_line_color=up_color,
        increasing_fillcolor=up_color,
        decreasing_line_color=down_color,
        decreasing_fillcolor=down_color
    )])

    tick_step = max(1, len(df_plot) // 6)

    fig.update_layout(
        template="plotly_dark",
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            tickmode="array",
            tickvals=df_plot["x"][::tick_step],
            ticktext=df_plot.iloc[:, 0].dt.strftime("%m-%d")[::tick_step]
        ),
        yaxis=dict(title="价格"),
        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(fig, use_container_width=True)
    st.success("✅ K线加载完成")

    # ======================
    # 技术指标摘要
    # ======================
    st.subheader("📌 技术指标摘要")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("最新收盘", fmt_num(latest_close), f"{day_pct:.2f}%")

    with col2:
        st.metric("MA5", fmt_num(latest["ma5"]))

    with col3:
        st.metric("MA20", fmt_num(latest["ma20"]))

    col4, col5, col6 = st.columns(3)

    with col4:
        st.metric("MACD DIF", fmt_num(latest["macd_dif"]))

    with col5:
        st.metric("KDJ-J", fmt_num(latest["kdj_j"]))

    with col6:
        st.metric("成交量", f"{int(latest['volume']):,}")

    # ======================
    # 新闻数据
    # ======================
    st.subheader("📰 最新消息面")

    stock_news = fetch_stock_news(stock_name, ticker_input, max_items=8)

    if stock_news:
        for n in stock_news:
            st.markdown(f"- [{n['title']}]({n['link']})")
    else:
        st.info("暂未抓取到该股相关新闻。建议股票名称填写中文名，例如：中国长城、贵州茅台、宁德时代。")

    st.subheader("🏛️ 政策面参考")

    policy_news = fetch_policy_news(max_items=5)

    if policy_news:
        for n in policy_news:
            st.markdown(f"- [{n['title']}]({n['link']})")
    else:
        st.info("暂未抓取到政策面新闻。")

    news_text = "\n".join([f"- {n['title']}" for n in stock_news])
    policy_text = "\n".join([f"- {n['title']}" for n in policy_news])

    # ======================
    # AI分析
    # ======================
    prompt = f"""
你是一个专业A股短线投资分析助手，请基于A股交易逻辑分析以下个股。

股票名称/代码：{stock_name if stock_name else ticker} / {ticker}
分析周期：{period}
我的风险偏好：{risk}

最近行情数据：
{data.tail(12).to_string()}

关键技术指标：
- 最新收盘价：{fmt_num(latest_close)}
- 单日涨跌幅：{day_pct:.2f}%
- MA5：{fmt_num(latest["ma5"])}
- MA10：{fmt_num(latest["ma10"])}
- MA20：{fmt_num(latest["ma20"])}
- MA60：{fmt_num(latest["ma60"])}
- MACD DIF：{fmt_num(latest["macd_dif"])}
- MACD DEA：{fmt_num(latest["macd_dea"])}
- MACD柱：{fmt_num(latest["macd_hist"])}
- KDJ K：{fmt_num(latest["kdj_k"])}
- KDJ D：{fmt_num(latest["kdj_d"])}
- KDJ J：{fmt_num(latest["kdj_j"])}
- 最新成交量：{int(latest["volume"])}

最新个股消息面：
{news_text if news_text else "暂无抓取到明确的个股新闻"}

最新政策面/市场环境：
{policy_text if policy_text else "暂无抓取到明确政策新闻"}

请严格用中文输出，内容不要太短，要有论据，不要只写结论。

请按照以下结构输出：

一、短线趋势判断
1. 结合K线位置、涨跌幅、均线、MACD、KDJ判断当前短线趋势。
2. 判断当前是强势上攻、震荡整理、缩量回调、放量下跌，还是情绪冲顶。
3. 说明判断依据。

二、技术面分析
1. 分析5日、10日、20日、60日均线。
2. 分析MACD是否转强或转弱。
3. 分析KDJ是否存在超买、钝化或回落风险。
4. 给出关键支撑位和压力位。

三、资金面分析
1. 结合成交量判断是否有资金异动。
2. 判断当前更像短线炒作还是趋势资金配置。
3. 判断是否存在追高风险。

四、消息面与政策面分析
1. 总结个股新闻对股价的潜在影响。
2. 总结政策面和市场环境对短线交易的影响。
3. 判断消息面对该股是偏利好、偏利空，还是中性。

五、综合结论
1. 个股一句话结论。
2. 适合短线、中线、中长线，还是只适合观察。
3. 核心机会。
4. 核心风险。

六、AI观察计划
请直接给出偏交易计划的表达：
1. 什么情况下可以考虑低吸。
2. 什么情况下可以考虑继续持有。
3. 什么情况下应考虑减仓或止损。
4. 不同风险偏好下的操作建议。

注意：
- 不要承诺收益。
- 不要写成绝对买入或绝对卖出。
- 但要给出清晰的短线操作倾向。
- 结论要有依据。
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
