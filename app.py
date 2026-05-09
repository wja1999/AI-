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

# ======================
# 🔐 DeepSeek API 配置
# ======================
# 只需要改这里：把下面这一行替换成你的 DeepSeek API Key
DEEPSEEK_API_KEY = "sk-34bde63deba4488c939677b2a93fbb01"

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

st.set_page_config(page_title="AI股票分析", layout="wide")

# ======================
# UI 样式
# ======================
st.markdown(
    """
<style>
.stApp {
    background:
        radial-gradient(circle at 10% 10%, rgba(66, 153, 225, 0.16), transparent 30%),
        radial-gradient(circle at 90% 15%, rgba(255, 99, 132, 0.12), transparent 28%),
        linear-gradient(135deg, #f7f9fc 0%, #eef3f8 48%, #f9fbff 100%);
    color: #172033;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

h1, h2, h3 {
    color: #111827;
}

[data-testid="stMarkdownContainer"] p {
    color: #334155;
}

.glass-card {
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.85);
    box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
    backdrop-filter: blur(18px);
    border-radius: 22px;
    padding: 20px;
    margin-bottom: 18px;
}

.ai-card {
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid rgba(226, 232, 240, 0.95);
    box-shadow: 0 14px 38px rgba(15, 23, 42, 0.08);
    border-radius: 22px;
    padding: 20px 22px;
    margin: 12px 0;
}

.ai-card-title {
    font-size: 20px;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.ai-card-body {
    font-size: 15.5px;
    line-height: 1.85;
    color: #334155;
}

.ai-bullet {
    margin: 7px 0;
    padding-left: 2px;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 14px 0 18px 0;
}

.summary-card {
    background: linear-gradient(135deg, rgba(255,255,255,0.9), rgba(248,250,252,0.78));
    border: 1px solid rgba(226,232,240,0.95);
    border-radius: 20px;
    padding: 18px;
    min-height: 118px;
    box-shadow: 0 12px 30px rgba(15,23,42,0.07);
}

.summary-label {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 10px;
}

.summary-value {
    font-size: 22px;
    font-weight: 850;
    color: #0f172a;
    margin-bottom: 8px;
}

.summary-desc {
    font-size: 14px;
    color: #475569;
    line-height: 1.6;
}

.score-big {
    font-size: 54px;
    font-weight: 900;
    line-height: 1;
}

.score-sub {
    font-size: 18px;
    color: #64748b;
}

.stButton > button {
    height: 48px;
    border-radius: 14px;
    font-weight: 800;
    background: linear-gradient(135deg, #2563eb, #06b6d4);
    color: white;
    border: none;
}

.stTextInput input, .stSelectbox div[data-baseweb="select"] {
    border-radius: 14px;
}

@media (max-width: 900px) {
    .summary-grid {
        grid-template-columns: 1fr;
    }
}
</style>
    """,
    unsafe_allow_html=True
)

st.title("📈 AI 股票分析平台")
st.caption("短线技术分析 · 消息面辅助 · 政策面参考 · AI科学评分 · 操作计划")

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

    df["vol_ma5"] = df["volume"].rolling(5).mean()
    df["vol_ma20"] = df["volume"].rolling(20).mean()

    return df


def fmt_num(value):
    try:
        if pd.isna(value):
            return "暂无"
        return f"{float(value):.2f}"
    except Exception:
        return "暂无"


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def score_news_titles(stock_news, policy_news):
    positive_words = [
        "利好", "增长", "突破", "中标", "签约", "回购", "增持", "盈利",
        "上调", "订单", "合作", "国产替代", "政策支持", "资金流入",
        "创新高", "扩产", "业绩预增", "超预期"
    ]

    negative_words = [
        "利空", "下滑", "亏损", "减持", "处罚", "调查", "风险",
        "终止", "违约", "暴跌", "业绩预减", "低于预期", "问询",
        "诉讼", "退市", "资金流出"
    ]

    text = " ".join([n["title"] for n in stock_news + policy_news])

    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)

    base = 8
    score = base + pos_count * 2 - neg_count * 3
    score = max(0, min(15, score))

    if not stock_news:
        score = min(score, 8)

    return score, pos_count, neg_count


def calc_ai_score(data, latest, prev, stock_news, policy_news):
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
        rise_5 = (safe_float(recent_5["close"].iloc[-1]) / safe_float(recent_5["close"].iloc[0]) - 1) * 100
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

    news_score, pos_count, neg_count = score_news_titles(stock_news, policy_news)

    total_score = trend_score + momentum_score + volume_score + risk_score + news_score
    total_score = int(max(0, min(100, round(total_score))))

    if total_score >= 80:
        level = "强势区"
        action = "可重点关注，适合趋势持有或回踩低吸，但不适合连续大涨后盲目追高。"
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
        "消息政策": news_score,
        "利好词命中": pos_count,
        "利空词命中": neg_count,
        "总分": total_score,
        "评级": level,
        "操作倾向": action,
        "用户动作": user_action,
        "近5日涨幅": rise_5,
        "近10日波动率": volatility_10
    }


def score_color(score):
    if score >= 80:
        return "#dc2626"
    if score >= 65:
        return "#f97316"
    if score >= 50:
        return "#2563eb"
    if score >= 35:
        return "#7c3aed"
    return "#475569"


def markdown_to_html(text):
    if not text:
        return ""

    lines = text.strip().splitlines()
    html_lines = []

    for line in lines:
        raw = line.strip()

        if not raw:
            html_lines.append("<br>")
            continue

        safe = html.escape(raw)
        safe = re.sub(r"\*\*(.*?)\*\*", r"<b>\\1</b>", safe)

        if re.match(r"^[-•]\s+", raw):
            safe = re.sub(r"^[-•]\s+", "", safe)
            html_lines.append(f"<div class='ai-bullet'>• {safe}</div>")
        elif re.match(r"^\d+[\.、]\s*", raw):
            safe = re.sub(r"^\d+[\.、]\s*", "", safe)
            html_lines.append(f"<div class='ai-bullet'>• {safe}</div>")
        else:
            html_lines.append(f"<div>{safe}</div>")

    return "\n".join(html_lines)


def split_ai_sections(text):
    section_pattern = r"(?m)^(一、[^\n]+|二、[^\n]+|三、[^\n]+|四、[^\n]+|五、[^\n]+|六、[^\n]+|七、[^\n]+)\s*$"
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


def render_ai_card(title, body, icon="🧩"):
    st.markdown(
        f"""
        <div class="ai-card">
            <div class="ai-card-title">{icon} {html.escape(title)}</div>
            <div class="ai-card-body">{markdown_to_html(body)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_ai_visual_result(result, score_detail):
    sections = split_ai_sections(result)
    score = score_detail["总分"]
    color = score_color(score)

    if score >= 80:
        risk_text = "趋势较强，但要防止高位加速后的回撤。"
    elif score >= 65:
        risk_text = "结构偏强，但需要等待量价继续确认。"
    elif score >= 50:
        risk_text = "趋势不够极致，适合边观察边验证。"
    elif score >= 35:
        risk_text = "短线偏弱，贸然追涨的性价比较低。"
    else:
        risk_text = "风险较高，优先保护本金。"

    st.subheader("🧭 小白版AI解读")

    st.markdown(
        f"""
        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-label">当前状态</div>
                <div class="summary-value">{html.escape(score_detail["评级"])}</div>
                <div class="summary-desc">AI综合分数为 <b style="color:{color};">{score}</b> 分，代表当前交易环境。</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">适合动作</div>
                <div class="summary-value">{html.escape(score_detail["用户动作"])}</div>
                <div class="summary-desc">{html.escape(score_detail["操作倾向"])}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">主要风险</div>
                <div class="summary-value">风险提醒</div>
                <div class="summary-desc">{html.escape(risk_text)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "评分解读", "短线趋势", "技术面", "资金面", "消息政策", "综合结论", "观察计划"
    ])

    section_map = {
        "评分解读": "一、AI评分解读",
        "短线趋势": "二、短线趋势判断",
        "技术面": "三、技术面分析",
        "资金面": "四、资金面分析",
        "消息政策": "五、消息面与政策面分析",
        "综合结论": "六、综合结论",
        "观察计划": "七、AI观察计划"
    }

    with tab1:
        render_ai_card("AI评分解读", sections.get(section_map["评分解读"], "暂无评分解读内容。"), "🧠")

    with tab2:
        render_ai_card("短线趋势判断", sections.get(section_map["短线趋势"], "暂无短线趋势内容。"), "📈")

    with tab3:
        render_ai_card("技术面分析", sections.get(section_map["技术面"], "暂无技术面内容。"), "🛠️")

    with tab4:
        render_ai_card("资金面分析", sections.get(section_map["资金面"], "暂无资金面内容。"), "💰")

    with tab5:
        render_ai_card("消息面与政策面", sections.get(section_map["消息政策"], "暂无消息政策内容。"), "📰")

    with tab6:
        render_ai_card("综合结论", sections.get(section_map["综合结论"], "暂无综合结论内容。"), "✅")

    with tab7:
        render_ai_card("AI观察计划", sections.get(section_map["观察计划"], "暂无观察计划内容。"), "🧭")

    with st.expander("查看原始AI完整文本"):
        st.markdown(result)


# ======================
# 页面布局
# ======================
left, right = st.columns([0.34, 0.66], gap="large")

with left:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("⚙️ 参数设置")

    ticker_input = st.text_input("股票代码", "000066")
    stock_name = st.text_input("股票名称（建议填写中文名，用于抓取新闻）", "中国长城")
    period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"])
    risk = st.selectbox("风险偏好", ["低", "中", "高"], index=1)

    start = st.button("🚀 开始分析", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("📊 分析结果区域")
    placeholder = st.empty()
    st.markdown('</div>', unsafe_allow_html=True)

if start:

    ticker = normalize_ticker(ticker_input)

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

    if ticker.endswith(".SZ") or ticker.endswith(".SS"):
        up_color = "#FF3B30"
        down_color = "#00C853"
    else:
        up_color = "#00C853"
        down_color = "#FF3B30"

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
        template="plotly_white",
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            tickmode="array",
            tickvals=df_plot["x"][::tick_step],
            ticktext=df_plot.iloc[:, 0].dt.strftime("%m-%d")[::tick_step],
            showgrid=False
        ),
        yaxis=dict(title="价格", gridcolor="rgba(148,163,184,0.25)"),
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)"
    )

    with right:
        st.plotly_chart(fig, use_container_width=True)
        st.success("✅ K线加载完成")

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

    stock_news = fetch_stock_news(stock_name, ticker_input, max_items=8)
    policy_news = fetch_policy_news(max_items=5)

    score_detail = calc_ai_score(data, latest, prev, stock_news, policy_news)
    ai_score = score_detail["总分"]
    color = score_color(ai_score)

    with right:
        st.subheader("🧠 AI科学评分")

        st.markdown(
            f"""
            <div class="ai-card">
                <div class="ai-card-title">🧠 AI综合评分</div>
                <div class="ai-card-body">
                    <div class="score-big" style="color:{color};">{ai_score}<span class="score-sub"> / 100</span></div>
                    <div style="font-size:20px;font-weight:800;margin-top:8px;">{html.escape(score_detail["评级"])}</div>
                    <div style="margin-top:10px;">{html.escape(score_detail["操作倾向"])}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.progress(ai_score / 100)

        s1, s2, s3, s4, s5 = st.columns(5)

        with s1:
            st.metric("趋势", f'{score_detail["趋势结构"]}/30')
        with s2:
            st.metric("动能", f'{score_detail["动能指标"]}/20')
        with s3:
            st.metric("资金", f'{score_detail["成交量资金"]}/20')
        with s4:
            st.metric("风险", f'{score_detail["风险状态"]}/15')
        with s5:
            st.metric("消息", f'{score_detail["消息政策"]}/15')

        st.caption(
            f"近5日涨幅 {score_detail['近5日涨幅']:.2f}%；"
            f"近10日波动率 {score_detail['近10日波动率']:.2f}；"
            f"消息面利好词命中 {score_detail['利好词命中']} 个，利空词命中 {score_detail['利空词命中']} 个。"
        )

        st.subheader("📰 最新消息面")

        if stock_news:
            for n in stock_news:
                st.markdown(f"- [{n['title']}]({n['link']})")
        else:
            st.info("暂未抓取到该股相关新闻。建议股票名称填写中文名，例如：中国长城、贵州茅台、宁德时代。")

        st.subheader("🏛️ 政策面参考")

        if policy_news:
            for n in policy_news:
                st.markdown(f"- [{n['title']}]({n['link']})")
        else:
            st.info("暂未抓取到政策面新闻。")

    news_text = "\n".join([f"- {n['title']}" for n in stock_news])
    policy_text = "\n".join([f"- {n['title']}" for n in policy_news])

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

AI科学评分：
- 综合分数：{score_detail["总分"]}/100
- 评级：{score_detail["评级"]}
- 操作倾向：{score_detail["操作倾向"]}
- 趋势结构：{score_detail["趋势结构"]}/30
- 动能指标：{score_detail["动能指标"]}/20
- 成交量资金：{score_detail["成交量资金"]}/20
- 风险状态：{score_detail["风险状态"]}/15
- 消息政策：{score_detail["消息政策"]}/15
- 近5日涨幅：{score_detail["近5日涨幅"]:.2f}%
- 近10日波动率：{score_detail["近10日波动率"]:.2f}

最新个股消息面：
{news_text if news_text else "暂无抓取到明确的个股新闻"}

最新政策面/市场环境：
{policy_text if policy_text else "暂无抓取到明确政策新闻"}

请严格用中文输出。
请不要输出英文。
请不要写空泛内容。
请让普通小白用户也能看懂。
请用短句、清晰判断、明确依据。

请严格按照以下标题输出，每个标题必须单独占一行：

一、AI评分解读
说明为什么当前分数是 {score_detail["总分"]} 分。
说明这个分数代表什么交易状态。
说明当前更适合进攻、低吸、持有、减仓，还是观察。

二、短线趋势判断
结合K线位置、涨跌幅、均线、MACD、KDJ判断当前短线趋势。
判断当前是强势上攻、震荡整理、缩量回调、放量下跌，还是情绪冲顶。
说明判断依据。

三、技术面分析
分析5日、10日、20日、60日均线。
分析MACD是否转强或转弱。
分析KDJ是否存在超买、钝化或回落风险。
给出关键支撑位和压力位。

四、资金面分析
结合成交量判断是否有资金异动。
判断当前更像短线炒作还是趋势资金配置。
判断是否存在追高风险。

五、消息面与政策面分析
总结个股新闻对股价的潜在影响。
总结政策面和市场环境对短线交易的影响。
判断消息面对该股是偏利好、偏利空，还是中性。

六、综合结论
给出个股一句话结论。
说明适合短线、中线、中长线，还是只适合观察。
列出核心机会。
列出核心风险。

七、AI观察计划
请直接给出偏交易计划的表达：
什么情况下可以考虑低吸。
什么情况下可以考虑继续持有。
什么情况下可以考虑减仓或止损。
不同风险偏好下的操作建议。

注意：
- 不要承诺收益。
- 不要写绝对买入或绝对卖出。
- 但要给出清晰的短线操作倾向。
- 结论必须有依据。
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content

        with right:
            render_ai_visual_result(result, score_detail)

    except Exception as e:
        with right:
            st.error("❌ AI分析失败")
            st.text(e)
