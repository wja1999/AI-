import streamlit as st
import yfinance as yf
from openai import OpenAI
import plotly.graph_objects as go
import pandas as pd
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import re
import html

# =========================================================
# 🔐 DeepSeek API Key
# =========================================================
# 本地运行：直接把你的 DeepSeek key 粘贴到这里
# Streamlit Cloud：也可以在 Secrets 里配置 DEEPSEEK_API_KEY
DEEPSEEK_API_KEY = "sk-34bde63deba4488c939677b2a93fbb01"

try:
    if DEEPSEEK_API_KEY == "在这里粘贴你的DeepSeek key":
        DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", "")
except Exception:
    pass

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

st.set_page_config(
    page_title="AI股票分析平台",
    layout="wide"
)

# =========================================================
# 🎨 页面样式
# =========================================================
st.markdown(
    """
<style>
.stApp {
    background:
        radial-gradient(circle at 8% 8%, rgba(59,130,246,0.14), transparent 28%),
        radial-gradient(circle at 88% 6%, rgba(14,165,233,0.12), transparent 30%),
        linear-gradient(135deg, #f7fbff 0%, #edf5ff 48%, #ffffff 100%);
    color: #0f172a;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

h1, h2, h3 {
    color: #0f172a;
}

[data-testid="stMarkdownContainer"] p {
    color: #334155;
}

.stButton > button {
    height: 48px;
    border-radius: 14px;
    font-weight: 800;
    background: linear-gradient(135deg, #2563eb, #06b6d4);
    color: white;
    border: none;
}

.stTextInput input {
    border-radius: 14px;
}

div[data-baseweb="select"] {
    border-radius: 14px;
}

.main-title {
    font-size: 36px;
    font-weight: 950;
    color: #0f172a;
    margin-bottom: 4px;
}

.sub-title {
    color: #64748b;
    font-size: 15px;
    margin-bottom: 20px;
}

.section-card {
    background: rgba(255,255,255,0.78);
    border: 1px solid rgba(255,255,255,0.9);
    box-shadow: 0 18px 45px rgba(15,23,42,0.08);
    backdrop-filter: blur(18px);
    border-radius: 22px;
    padding: 20px;
    margin-bottom: 16px;
}

.score-title {
    font-size: 20px;
    font-weight: 900;
    color: #0f172a;
    margin-bottom: 6px;
}

.score-desc {
    color: #475569;
    font-size: 15px;
    line-height: 1.7;
}

.news-box {
    background: rgba(239,246,255,0.72);
    border: 1px solid rgba(191,219,254,0.85);
    border-radius: 18px;
    padding: 16px 18px;
    margin: 10px 0;
}

.ai-card-title {
    font-size: 18px;
    font-weight: 900;
    margin-bottom: 8px;
}

.ai-card-body {
    font-size: 15px;
    line-height: 1.8;
}
</style>
""",
    unsafe_allow_html=True
)

# =========================================================
# 🔧 工具函数
# =========================================================
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


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def fmt_num(value):
    try:
        if pd.isna(value):
            return "暂无"
        return f"{float(value):.2f}"
    except Exception:
        return "暂无"


def clean_title(title):
    title = re.sub(r"\s+", " ", title or "").strip()
    title = title.replace(" - Google News", "")
    return title


def fetch_rss(url, max_items=5):
    items = []

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
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
        f"{query_base} 公告 业绩 订单 合作",
        f"{query_base} 研报 股东 减持 增持 回购"
    ]

    all_news = []

    for q in search_queries:
        encoded = urllib.parse.quote(q)

        google_url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        bing_url = f"https://www.bing.com/news/search?q={encoded}&format=rss"

        all_news.extend(fetch_rss(google_url, max_items=4))
        all_news.extend(fetch_rss(bing_url, max_items=4))

    seen = set()
    unique_news = []

    for item in all_news:
        title_key = item["title"][:48]

        if title_key not in seen:
            seen.add(title_key)
            unique_news.append(item)

        if len(unique_news) >= max_items:
            break

    return unique_news


def fetch_market_background(stock_name, max_items=4):
    query_base = stock_name.strip() if stock_name.strip() else "A股"

    search_queries = [
        f"{query_base} 行业 政策 最新",
        f"{query_base} 行业 监管 政策",
        "A股 证监会 央行 政策 资本市场"
    ]

    all_news = []

    for q in search_queries:
        encoded = urllib.parse.quote(q)

        google_url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        bing_url = f"https://www.bing.com/news/search?q={encoded}&format=rss"

        all_news.extend(fetch_rss(google_url, max_items=3))
        all_news.extend(fetch_rss(bing_url, max_items=3))

    seen = set()
    unique_news = []

    for item in all_news:
        title_key = item["title"][:48]

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

    df["vol_ma5"] = df["volume"].rolling(5).mean()
    df["vol_ma20"] = df["volume"].rolling(20).mean()

    return df


def score_news_titles(stock_news):
    positive_words = [
        "利好", "增长", "突破", "中标", "签约", "回购", "增持", "盈利",
        "上调", "订单", "合作", "国产替代", "政策支持", "资金流入",
        "创新高", "扩产", "业绩预增", "超预期", "涨停", "龙头"
    ]

    negative_words = [
        "利空", "下滑", "亏损", "减持", "处罚", "调查", "风险",
        "终止", "违约", "暴跌", "业绩预减", "低于预期", "问询",
        "诉讼", "退市", "资金流出", "监管函"
    ]

    text = " ".join([n["title"] for n in stock_news])

    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)

    if not stock_news:
        score = 6
    else:
        score = 8 + pos_count * 2 - neg_count * 3

    score = max(0, min(15, score))

    return score, pos_count, neg_count


def calc_ai_score(data, latest, prev, stock_news):
    close = safe_float(latest["close"])
    prev_close = safe_float(prev["close"], close)

    ma5 = safe_float(latest["ma5"])
    ma10 = safe_float(latest["ma10"])
    ma20 = safe_float(latest["ma20"])
    ma60 = safe_float(latest["ma60"])

    macd_dif = safe_float(latest["macd_dif"])
    macd_dea = safe_float(latest["macd_dea"])
    macd_hist = safe_float(latest["macd_hist"])

    kdj_j = safe_float(latest["kdj_j"])

    volume = safe_float(latest["volume"])
    vol_ma5 = safe_float(latest["vol_ma5"])
    vol_ma20 = safe_float(latest["vol_ma20"])

    pct_chg = ((close - prev_close) / prev_close * 100) if prev_close else 0

    trend_score = 0

    if ma5 and close > ma5:
        trend_score += 7
    if ma10 and close > ma10:
        trend_score += 6
    if ma20 and close > ma20:
        trend_score += 6
    if ma60 and close > ma60:
        trend_score += 4
    if ma5 and ma10 and ma20 and ma5 > ma10 > ma20:
        trend_score += 5
    if len(data) >= 6 and close > safe_float(data["close"].iloc[-6]):
        trend_score += 2

    trend_score = max(0, min(30, trend_score))

    momentum_score = 0

    if macd_dif > macd_dea:
        momentum_score += 7
    if macd_hist > 0:
        momentum_score += 5
    if len(data) >= 2 and macd_hist > safe_float(data["macd_hist"].iloc[-2]):
        momentum_score += 3

    if 50 <= kdj_j <= 90:
        momentum_score += 4
    elif 90 < kdj_j <= 110:
        momentum_score += 2
    elif kdj_j > 110:
        momentum_score -= 2
    elif kdj_j < 30:
        momentum_score += 1

    momentum_score = max(0, min(20, momentum_score))

    volume_score = 0

    if vol_ma5 and volume > vol_ma5:
        volume_score += 6
    if vol_ma20 and volume > vol_ma20:
        volume_score += 6
    if pct_chg > 0 and vol_ma5 and volume > vol_ma5:
        volume_score += 5
    if pct_chg < 0 and vol_ma5 and volume > vol_ma5:
        volume_score -= 4
    if vol_ma20 and volume > vol_ma20 * 2.5:
        volume_score -= 2

    volume_score = max(0, min(20, volume_score))

    risk_score = 15

    recent_5 = data.tail(5)
    recent_10 = data.tail(10)

    if len(recent_5) >= 5:
        first_close_5 = safe_float(recent_5["close"].iloc[0], close)
        rise_5 = (close / first_close_5 - 1) * 100 if first_close_5 else 0
    else:
        rise_5 = 0

    if len(recent_10) >= 10:
        volatility_10 = safe_float(recent_10["pct_chg"].std())
    else:
        volatility_10 = 0

    if rise_5 > 25:
        risk_score -= 6
    elif rise_5 > 15:
        risk_score -= 4
    elif rise_5 > 8:
        risk_score -= 2

    if volatility_10 > 8:
        risk_score -= 5
    elif volatility_10 > 5:
        risk_score -= 3
    elif volatility_10 > 3:
        risk_score -= 1

    if kdj_j > 110:
        risk_score -= 3

    risk_score = max(0, min(15, risk_score))

    news_score, pos_count, neg_count = score_news_titles(stock_news)

    total_score = trend_score + momentum_score + volume_score + risk_score + news_score
    total_score = int(max(0, min(100, round(total_score))))

    if total_score >= 80:
        level = "强势区"
        action = "可重点跟踪，适合趋势持有或回踩低吸，但连续急涨后不适合盲目追高。"
        user_action = "偏进攻"
    elif total_score >= 65:
        level = "偏强区"
        action = "可轻仓参与或等待回踩确认，适合短线跟踪，不宜重仓追涨。"
        user_action = "轻仓参与"
    elif total_score >= 50:
        level = "中性区"
        action = "适合观察或小仓试探，等待放量突破或回踩企稳信号。"
        user_action = "观察为主"
    elif total_score >= 35:
        level = "偏弱区"
        action = "以防守为主，暂不适合主动进攻，等待趋势修复。"
        user_action = "谨慎等待"
    else:
        level = "高风险区"
        action = "短线风险较高，建议先观察，不适合主动参与。"
        user_action = "暂不参与"

    return {
        "趋势结构": trend_score,
        "动能指标": momentum_score,
        "成交量资金": volume_score,
        "风险状态": risk_score,
        "消息面": news_score,
        "利好词命中": pos_count,
        "利空词命中": neg_count,
        "总分": total_score,
        "评级": level,
        "操作倾向": action,
        "用户动作": user_action,
        "近5日涨幅": rise_5,
        "近10日波动率": volatility_10
    }


def split_ai_sections(text):
    section_pattern = r"(?m)^(一、[^\n]+|二、[^\n]+|三、[^\n]+|四、[^\n]+|五、[^\n]+|六、[^\n]+)\s*$"
    matches = list(re.finditer(section_pattern, text))

    if not matches:
        return {}

    sections = {}

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections[title] = body

    return sections


def find_section(sections, keyword):
    for title, body in sections.items():
        if keyword in title:
            return body
    return ""


def render_score_panel(score_detail):
    score = score_detail["总分"]

    if score >= 80:
        score_text = "强势区"
    elif score >= 65:
        score_text = "偏强区"
    elif score >= 50:
        score_text = "中性区"
    elif score >= 35:
        score_text = "偏弱区"
    else:
        score_text = "高风险区"

    with st.container(border=True):
        st.subheader("🧠 AI综合评分")

        c1, c2 = st.columns([0.22, 0.78])

        with c1:
            st.metric("AI分数", f"{score} / 100")

        with c2:
            st.markdown(f"### {score_text} · {score_detail['用户动作']}")
            st.write(score_detail["操作倾向"])
            st.progress(score / 100)

        st.divider()

        k1, k2, k3, k4, k5 = st.columns(5)

        k1.metric("趋势结构", f"{score_detail['趋势结构']} / 30")
        k2.metric("动能指标", f"{score_detail['动能指标']} / 20")
        k3.metric("成交量资金", f"{score_detail['成交量资金']} / 20")
        k4.metric("风险状态", f"{score_detail['风险状态']} / 15")
        k5.metric("消息面", f"{score_detail['消息面']} / 15")

        st.caption(
            f"近5日涨幅：{score_detail['近5日涨幅']:.2f}% ｜ "
            f"近10日波动率：{score_detail['近10日波动率']:.2f} ｜ "
            f"利好词命中：{score_detail['利好词命中']} 个 ｜ "
            f"利空词命中：{score_detail['利空词命中']} 个"
        )


def render_ai_result(result, score_detail):
    sections = split_ai_sections(result)

    conclusion = find_section(sections, "结论先看")
    score_explain = find_section(sections, "AI分数解读")
    trend = find_section(sections, "短线趋势")
    tech = find_section(sections, "技术面")
    funds = find_section(sections, "资金面")
    news = find_section(sections, "消息面")
    plan = find_section(sections, "观察计划")

    st.subheader("🧭 关键信息先看")

    with st.container(border=True):
        st.markdown("#### ✅ 结论")
        st.markdown(conclusion if conclusion else result)

    q1, q2, q3 = st.columns(3)

    with q1:
        with st.container(border=True):
            st.markdown("#### 当前状态")
            st.markdown(f"**{score_detail['评级']}**")
            st.write(f"AI分数：{score_detail['总分']} / 100")

    with q2:
        with st.container(border=True):
            st.markdown("#### 操作倾向")
            st.markdown(f"**{score_detail['用户动作']}**")
            st.write(score_detail["操作倾向"])

    with q3:
        with st.container(border=True):
            st.markdown("#### 核心提醒")
            st.markdown("**防追高 / 看量能 / 看均线**")
            st.write("若放量滞涨或跌破短期均线，需要降低仓位或转为观察。")

    st.subheader("📌 模块化AI解读")

    with st.container(border=True):
        st.markdown("#### 🧠 AI分数解读")
        st.markdown(score_explain)

    c1, c2 = st.columns(2)

    with c1:
        with st.container(border=True):
            st.markdown("#### 📈 短线趋势判断")
            st.markdown(trend)

        with st.container(border=True):
            st.markdown("#### 💰 资金面分析")
            st.markdown(funds)

    with c2:
        with st.container(border=True):
            st.markdown("#### 🛠️ 技术面分析")
            st.markdown(tech)

        with st.container(border=True):
            st.markdown("#### 📰 消息面分析")
            st.markdown(news)

    with st.container(border=True):
        st.markdown("#### 🧭 AI观察计划")
        st.markdown(plan)

    with st.expander("查看AI原始完整文本"):
        st.markdown(result)


# =========================================================
# 页面标题
# =========================================================
st.markdown('<div class="main-title">📊 AI股票分析平台</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">趋势判断 · 消息面辅助 · AI科学评分 · 小白可读操作计划</div>',
    unsafe_allow_html=True
)

left, right = st.columns([0.33, 0.67], gap="large")

with left:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("⚙️ 参数设置")

    ticker_input = st.text_input("股票代码", "000066")
    stock_name = st.text_input("股票名称，建议填写中文名", "中国长城")
    period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"])
    risk = st.selectbox("风险偏好", ["低", "中", "高"], index=1)

    start = st.button("🚀 开始分析", use_container_width=True)

    st.caption("A股可输入：000066、000066.SZ、600519、600519.SS。")
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("📈 分析结果")
    st.caption("点击开始分析后，将展示K线图、AI评分、消息面、技术指标和AI观察计划。")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# 主流程
# =========================================================
if start:

    if not DEEPSEEK_API_KEY:
        st.error("❌ 没有配置 DeepSeek API Key。请在代码顶部 DEEPSEEK_API_KEY 里填写。")
        st.stop()

    ticker = normalize_ticker(ticker_input)

    data = yf.download(
        ticker,
        period=period,
        progress=False,
        auto_adjust=False
    )

    if data is None or data.empty:
        st.error("❌ 没拿到行情数据。沪市示例：600519 或 600519.SS；深市示例：000001 或 000001.SZ。")
        st.stop()

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume"
        },
        inplace=True
    )

    need_cols = ["open", "high", "low", "close", "volume"]

    if not all(col in data.columns for col in need_cols):
        st.error(f"❌ 行情字段异常：{list(data.columns)}")
        st.stop()

    data = data[need_cols].dropna()

    if data.empty:
        st.error("❌ 数据为空，无法分析。")
        st.stop()

    data = calc_indicators(data)

    latest = data.iloc[-1]
    prev = data.iloc[-2] if len(data) >= 2 else latest

    latest_close = safe_float(latest["close"])
    prev_close = safe_float(prev["close"], latest_close)
    day_pct = ((latest_close - prev_close) / prev_close * 100) if prev_close else 0

    # A股：红涨绿跌；美股：绿涨红跌
    if ticker.endswith(".SZ") or ticker.endswith(".SS"):
        up_color = "#ef4444"
        down_color = "#22c55e"
    else:
        up_color = "#22c55e"
        down_color = "#ef4444"

    df_plot = data.reset_index()
    date_col = df_plot.columns[0]
    df_plot["date_text"] = pd.to_datetime(df_plot[date_col]).dt.strftime("%m-%d")
    df_plot["x"] = range(len(df_plot))

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df_plot["x"],
                open=df_plot["open"],
                high=df_plot["high"],
                low=df_plot["low"],
                close=df_plot["close"],
                increasing_line_color=up_color,
                increasing_fillcolor=up_color,
                decreasing_line_color=down_color,
                decreasing_fillcolor=down_color
            )
        ]
    )

    tick_step = max(1, len(df_plot) // 6)

    fig.update_layout(
        template="plotly_white",
        height=430,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            tickmode="array",
            tickvals=df_plot["x"][::tick_step],
            ticktext=df_plot["date_text"][::tick_step],
            showgrid=False,
            rangeslider=dict(visible=False)
        ),
        yaxis=dict(
            title="价格",
            gridcolor="rgba(148,163,184,0.25)"
        ),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)"
    )

    stock_news = fetch_stock_news(stock_name, ticker_input, max_items=8)
    market_background = fetch_market_background(stock_name, max_items=4)

    score_detail = calc_ai_score(data, latest, prev, stock_news)

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader(f"📈 {ticker} K线走势")
        st.plotly_chart(fig, use_container_width=True)
        st.success("✅ K线加载完成")
        st.markdown('</div>', unsafe_allow_html=True)

        render_score_panel(score_detail)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("📰 个股最新消息面")

        if stock_news:
            st.info("优先展示与个股相关的新闻，用于辅助判断短线情绪和事件驱动。")
            for n in stock_news:
                st.markdown(f"- [{n['title']}]({n['link']})")
        else:
            st.warning("暂未抓取到该股相关新闻。建议股票名称填写中文名，例如：中国长城、贵州茅台、宁德时代。")

        with st.expander("查看市场背景参考，不作为核心判断"):
            if market_background:
                for n in market_background:
                    st.markdown(f"- [{n['title']}]({n['link']})")
            else:
                st.write("暂无可用市场背景信息。")

        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("📌 技术指标摘要")

        m1, m2, m3 = st.columns(3)
        m1.metric("最新收盘", fmt_num(latest_close), f"{day_pct:.2f}%")
        m2.metric("MA5", fmt_num(latest["ma5"]))
        m3.metric("MA20", fmt_num(latest["ma20"]))

        m4, m5, m6 = st.columns(3)
        m4.metric("MACD DIF", fmt_num(latest["macd_dif"]))
        m5.metric("KDJ-J", fmt_num(latest["kdj_j"]))
        m6.metric("成交量", f"{int(safe_float(latest['volume'])):,}")

        st.markdown('</div>', unsafe_allow_html=True)

    stock_news_text = "\n".join([f"- {n['title']}" for n in stock_news])
    market_background_text = "\n".join([f"- {n['title']}" for n in market_background])

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
- 最新成交量：{int(safe_float(latest["volume"]))}

AI科学评分：
- 综合分数：{score_detail["总分"]}/100
- 评级：{score_detail["评级"]}
- 操作倾向：{score_detail["操作倾向"]}
- 趋势结构：{score_detail["趋势结构"]}/30
- 动能指标：{score_detail["动能指标"]}/20
- 成交量资金：{score_detail["成交量资金"]}/20
- 风险状态：{score_detail["风险状态"]}/15
- 消息面：{score_detail["消息面"]}/15
- 近5日涨幅：{score_detail["近5日涨幅"]:.2f}%
- 近10日波动率：{score_detail["近10日波动率"]:.2f}

个股最新消息面：
{stock_news_text if stock_news_text else "暂无抓取到明确的个股新闻"}

市场背景参考：
{market_background_text if market_background_text else "暂无抓取到明确市场背景信息"}

要求：
1. 必须严格用中文输出。
2. 不要输出英文。
3. 不要空泛，要结合数据、技术指标和新闻。
4. 让普通小白也能看懂。
5. 政策面和市场背景只作为辅助，不要喧宾夺主。
6. 重点解释AI分数为什么是这个分数，以及这个分数对应什么操作。
7. 不要承诺收益。
8. 不要写绝对买入或绝对卖出，但要给出清晰短线操作倾向。

请严格按照以下标题输出，每个标题必须单独占一行：

一、结论先看
用3到5句话说明：
- 这只股票现在处于什么状态。
- 当前AI分数意味着什么。
- 适合什么操作。
- 最大机会是什么。
- 最大风险是什么。

二、AI分数解读
解释为什么当前分数是 {score_detail["总分"]} 分。
分别解释趋势、动能、资金、风险、消息面对分数的影响。
说明这个分数适合进攻、低吸、持有、减仓，还是观察。

三、短线趋势判断
结合K线位置、涨跌幅、均线、MACD、KDJ判断当前短线趋势。
判断当前是强势上攻、震荡整理、缩量回调、放量下跌，还是情绪冲顶。
说明判断依据。

四、技术面分析
分析5日、10日、20日、60日均线。
分析MACD是否转强或转弱。
分析KDJ是否存在超买、钝化或回落风险。
给出关键支撑位和压力位。

五、资金面分析
结合成交量判断是否有资金异动。
判断当前更像短线炒作还是趋势资金配置。
判断是否存在追高风险。

六、消息面与观察计划
总结个股新闻对股价的潜在影响。
如果个股新闻不足，请明确说明消息面证据不足，不要硬编。
说明市场背景是否真正影响该股。
最后给出：
- 什么情况下可以考虑低吸。
- 什么情况下可以继续持有。
- 什么情况下应减仓或止损。
- 不同风险偏好下的操作建议。
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content

        with right:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("🤖 AI解读")
            render_ai_result(result, score_detail)
            st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        with right:
            st.error("❌ AI分析失败")
            st.text(e)
