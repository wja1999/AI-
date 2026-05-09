import streamlit as st
import yfinance as yf
from openai import OpenAI
import plotly.graph_objects as go
import pandas as pd
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import re

st.set_page_config(page_title="AI股票分析平台", layout="wide")

# =========================================================
# 🔐 DeepSeek Key 位置：本地运行就填这里
# =========================================================
DEEPSEEK_API_KEY = "sk-34bde63deba4488c939677b2a93fbb01"

try:
    if DEEPSEEK_API_KEY == "在这里粘贴你的DeepSeek key":
        DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", "")
except Exception:
    pass

client = None
if DEEPSEEK_API_KEY:
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )

# =========================================================
# 🎨 UI 样式：修复顶部标题、输入框重色、运行中灰字问题
# =========================================================
st.markdown(
    """
<style>
/* 页面背景 */
.stApp {
    background:
      radial-gradient(circle at 12% 8%, rgba(37,99,235,0.13), transparent 28%),
      radial-gradient(circle at 88% 8%, rgba(14,165,233,0.13), transparent 28%),
      linear-gradient(135deg, #f6fbff 0%, #eef7ff 46%, #ffffff 100%);
    color: #0f172a;
}

/* 顶部安全间距，避免标题被系统栏压住 */
.block-container {
    padding-top: 2.2rem !important;
    padding-bottom: 2rem;
    max-width: 1480px;
}

/* Streamlit 顶栏弱化 */
header[data-testid="stHeader"] {
    background: rgba(255,255,255,0.75);
    backdrop-filter: blur(18px);
}

/* 标题区 */
.hero-card {
    background: rgba(255,255,255,0.72);
    border: 1px solid rgba(226,232,240,0.95);
    box-shadow: 0 18px 48px rgba(15,23,42,0.08);
    border-radius: 24px;
    padding: 22px 26px;
    margin-bottom: 18px;
    backdrop-filter: blur(18px);
}
.main-title {
    font-size: 34px;
    font-weight: 950;
    color: #0f172a;
    line-height: 1.15;
    margin-bottom: 8px;
}
.sub-title {
    color: #64748b;
    font-size: 15px;
}

/* 标题文字 */
h1, h2, h3 {
    color: #0f172a !important;
}
[data-testid="stMarkdownContainer"] p, li {
    color: #334155;
    line-height: 1.65;
}

/* 卡片 */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(255,255,255,0.70);
    border-radius: 22px;
    border: 1px solid rgba(226,232,240,0.95);
    box-shadow: 0 16px 38px rgba(15,23,42,0.06);
    backdrop-filter: blur(18px);
}

/* 输入框：重点修复背景与文字重合 */
.stTextInput input {
    background: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 14px !important;
    height: 44px !important;
    font-weight: 700 !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.9);
}
.stTextInput input::placeholder {
    color: #94a3b8 !important;
    opacity: 1 !important;
}

/* 运行中 Streamlit 会临时禁用控件，这里强制保持可读 */
.stTextInput input:disabled {
    background: #ffffff !important;
    color: #0f172a !important;
    opacity: 1 !important;
    -webkit-text-fill-color: #0f172a !important;
}

/* 下拉框：重点修复文字和背景 */
div[data-baseweb="select"] > div {
    background: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 14px !important;
    min-height: 44px !important;
}
div[data-baseweb="select"] span {
    color: #0f172a !important;
    font-weight: 700 !important;
}
div[data-baseweb="select"] svg {
    color: #334155 !important;
}

/* label */
label, .stTextInput label, .stSelectbox label {
    color: #334155 !important;
    font-weight: 800 !important;
}

/* 按钮 */
.stButton > button {
    height: 48px;
    border-radius: 15px;
    font-weight: 900;
    background: linear-gradient(135deg, #2563eb, #06b6d4);
    color: white !important;
    border: none;
    box-shadow: 0 12px 28px rgba(37,99,235,0.25);
}
.stButton > button:hover {
    filter: brightness(1.04);
    border: none;
}

/* 指标卡 */
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.82);
    border: 1px solid rgba(226,232,240,0.95);
    border-radius: 18px;
    padding: 14px 16px;
    box-shadow: 0 12px 30px rgba(15,23,42,0.06);
}

/* 信息提示 */
div[data-testid="stAlert"] {
    border-radius: 16px;
}

/* 小屏适配 */
@media (max-width: 900px) {
    .block-container {
        padding-top: 1.4rem !important;
    }
    .main-title {
        font-size: 28px;
    }
    .hero-card {
        padding: 18px 18px;
    }
}
</style>
""",
    unsafe_allow_html=True
)

# =========================================================
# 🔧 工具函数
# =========================================================
def normalize_ticker(raw_code):
    code = str(raw_code).strip().upper()

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
    return title.replace(" - Google News", "")


def fetch_rss(url, max_items=5):
    items = []

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req, timeout=8) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)

        for item in root.findall(".//item"):
            title = clean_title(item.findtext("title", default=""))
            link = item.findtext("link", default="")
            date = item.findtext("pubDate", default="")

            if title and link:
                items.append({
                    "title": title,
                    "link": link,
                    "date": date
                })

            if len(items) >= max_items:
                break

    except Exception:
        pass

    return items


def fetch_news(stock_name, ticker_text, max_items=8):
    query_base = stock_name.strip() if stock_name.strip() else ticker_text.strip()

    queries = [
        f"{query_base} 股票 最新消息",
        f"{query_base} 公告 业绩 订单 合作",
        f"{query_base} 研报 股东 减持 增持 回购",
        f"{query_base} 财经 新闻 利好 利空",
    ]

    all_items = []

    for q in queries:
        encoded = urllib.parse.quote(q)

        google_url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        bing_url = f"https://www.bing.com/news/search?q={encoded}&format=rss"

        all_items.extend(fetch_rss(google_url, 4))
        all_items.extend(fetch_rss(bing_url, 4))

    seen = set()
    unique = []

    for item in all_items:
        key = item["title"][:48]

        if key not in seen:
            seen.add(key)
            unique.append(item)

        if len(unique) >= max_items:
            break

    return unique


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


def calc_trade_levels(data, latest):
    close = safe_float(latest["close"])

    ma5 = safe_float(latest["ma5"])
    ma10 = safe_float(latest["ma10"])
    ma20 = safe_float(latest["ma20"])

    recent_10 = data.tail(10)
    recent_20 = data.tail(20)

    recent_low_10 = safe_float(recent_10["low"].min(), close * 0.95)
    recent_high_10 = safe_float(recent_10["high"].max(), close * 1.05)
    recent_high_20 = safe_float(recent_20["high"].max(), close * 1.08)

    support_candidates = [x for x in [ma5, ma10, ma20, recent_low_10] if x > 0]

    buy_low = min(support_candidates) if support_candidates else close * 0.95
    buy_high = max([x for x in [ma5, ma10] if x > 0], default=close)

    if buy_low > buy_high:
        buy_low, buy_high = buy_high, buy_low

    stop_loss = min(recent_low_10, ma20 if ma20 > 0 else recent_low_10) * 0.985
    breakout = max(recent_high_10, recent_high_20)
    pressure = max(recent_high_10, close * 1.03)

    return {
        "当前价": close,
        "观察低吸区下沿": buy_low,
        "观察低吸区上沿": buy_high,
        "突破确认价": breakout,
        "压力位": pressure,
        "风险止损线": stop_loss,
    }


def calc_news_score(news_list):
    positive_words = [
        "利好", "增长", "突破", "中标", "签约", "回购", "增持", "盈利",
        "上调", "订单", "合作", "国产替代", "政策支持", "创新高", "预增"
    ]

    negative_words = [
        "利空", "下滑", "亏损", "减持", "处罚", "调查", "风险", "终止",
        "违约", "暴跌", "预减", "问询", "诉讼", "退市", "监管函"
    ]

    text = " ".join([n["title"] for n in news_list])

    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)

    if not news_list:
        score = 6
    else:
        score = 8 + pos_count * 2 - neg_count * 3

    return max(0, min(15, score)), pos_count, neg_count


def calc_ai_score(data, latest, prev, news_list):
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

    day_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0

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
    if day_pct > 0 and vol_ma5 and volume > vol_ma5:
        volume_score += 5
    if day_pct < 0 and vol_ma5 and volume > vol_ma5:
        volume_score -= 4
    if vol_ma20 and volume > vol_ma20 * 2.5:
        volume_score -= 2

    volume_score = max(0, min(20, volume_score))

    risk_score = 15

    recent_5 = data.tail(5)
    recent_10 = data.tail(10)

    if len(recent_5) >= 5:
        first_5 = safe_float(recent_5["close"].iloc[0], close)
        rise_5 = (close / first_5 - 1) * 100 if first_5 else 0
    else:
        rise_5 = 0

    volatility_10 = safe_float(recent_10["pct_chg"].std()) if len(recent_10) >= 5 else 0

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

    news_score, pos_count, neg_count = calc_news_score(news_list)

    total_score = int(max(0, min(100, round(
        trend_score + momentum_score + volume_score + risk_score + news_score
    ))))

    if total_score >= 80:
        level = "强势区"
        action = "可重点跟踪；适合趋势持有或回踩低吸，但连续急涨后不宜盲目追高。"
        short_action = "偏进攻"
    elif total_score >= 65:
        level = "偏强区"
        action = "可轻仓参与或等待回踩确认；适合短线跟踪，不宜重仓追涨。"
        short_action = "轻仓参与"
    elif total_score >= 50:
        level = "中性区"
        action = "适合观察或小仓试探；等待放量突破或回踩企稳信号。"
        short_action = "观察为主"
    elif total_score >= 35:
        level = "偏弱区"
        action = "以防守为主；暂不适合主动进攻，等待趋势修复。"
        short_action = "谨慎等待"
    else:
        level = "高风险区"
        action = "短线风险较高；建议先观察，不适合主动参与。"
        short_action = "暂不参与"

    return {
        "总分": total_score,
        "评级": level,
        "操作倾向": action,
        "动作": short_action,
        "趋势结构": trend_score,
        "动能指标": momentum_score,
        "成交量资金": volume_score,
        "风险状态": risk_score,
        "消息面": news_score,
        "利好词命中": pos_count,
        "利空词命中": neg_count,
        "近5日涨幅": rise_5,
        "近10日波动率": volatility_10,
    }


def section_text(text, keyword):
    pattern = r"(?m)^(一、[^\n]+|二、[^\n]+|三、[^\n]+|四、[^\n]+|五、[^\n]+|六、[^\n]+|七、[^\n]+)\s*$"
    matches = list(re.finditer(pattern, text))

    if not matches:
        return ""

    for i, match in enumerate(matches):
        title = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        if keyword in title:
            return text[start:end].strip()

    return ""


def render_score_panel(score_detail):
    with st.container(border=True):
        st.subheader("🧠 AI综合评分")

        c1, c2 = st.columns([0.22, 0.78])

        with c1:
            st.metric("AI分数", f"{score_detail['总分']} / 100")

        with c2:
            st.markdown(f"### {score_detail['评级']} · {score_detail['动作']}")
            st.write(score_detail["操作倾向"])
            st.progress(score_detail["总分"] / 100)

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


def render_beginner_panel(score_detail, trade_levels, risk):
    st.subheader("🎯 小白决策看板")

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)

        c1.metric("当前价", fmt_num(trade_levels["当前价"]))
        c2.metric("AI分数", f"{score_detail['总分']}/100", score_detail["评级"])
        c3.metric("适合操作", score_detail["动作"])
        c4.metric("风险偏好", risk)

        st.progress(score_detail["总分"] / 100)
        st.write(score_detail["操作倾向"])

    b1, b2, b3 = st.columns(3)

    with b1:
        with st.container(border=True):
            st.markdown("### 🟢 观察买点")
            st.markdown(
                f"**{fmt_num(trade_levels['观察低吸区下沿'])} - "
                f"{fmt_num(trade_levels['观察低吸区上沿'])}**"
            )
            st.write("回踩到短期均线附近，并且没有放量跌破时，再观察低吸。")
            st.caption("核心：不追高，等确认。")

    with b2:
        with st.container(border=True):
            st.markdown("### 🚀 突破确认点")
            st.markdown(f"**{fmt_num(trade_levels['突破确认价'])}**")
            st.write("放量突破近期高点，说明短线资金仍在进攻。突破失败则警惕冲高回落。")
            st.caption(f"附近压力位：{fmt_num(trade_levels['压力位'])}")

    with b3:
        with st.container(border=True):
            st.markdown("### 🔴 风险止损线")
            st.markdown(f"**{fmt_num(trade_levels['风险止损线'])}**")
            st.write("跌破该位置且成交量放大，说明短线结构可能转弱。")
            st.caption("核心：先控制亏损，再看机会。")


def render_ai_cards(ai_text, score_detail, trade_levels, risk):
    conclusion = section_text(ai_text, "结论先看")
    buy_sell = section_text(ai_text, "买卖点地图")
    score_text = section_text(ai_text, "AI分数解读")
    trend = section_text(ai_text, "短线趋势")
    tech = section_text(ai_text, "技术面")
    fund = section_text(ai_text, "资金面")
    news = section_text(ai_text, "消息面")

    render_beginner_panel(score_detail, trade_levels, risk)

    st.subheader("✅ 关键信息先看")
    with st.container(border=True):
        st.markdown(conclusion if conclusion else ai_text)

    st.subheader("🗺️ 买卖点地图")
    with st.container(border=True):
        st.markdown(buy_sell if buy_sell else "暂无买卖点地图。")

    st.subheader("📦 模块化解读")

    a, b = st.columns(2)

    with a:
        with st.container(border=True):
            st.markdown("### 🧠 分数为什么这么打")
            st.markdown(score_text if score_text else "暂无分数解读。")

    with b:
        with st.container(border=True):
            st.markdown("### 📈 短线趋势怎么判断")
            st.markdown(trend if trend else "暂无趋势解读。")

    c, d = st.columns(2)

    with c:
        with st.container(border=True):
            st.markdown("### 🛠️ 技术面看什么")
            st.markdown(tech if tech else "暂无技术面解读。")

    with d:
        with st.container(border=True):
            st.markdown("### 💰 资金面看什么")
            st.markdown(fund if fund else "暂无资金面解读。")

    with st.container(border=True):
        st.markdown("### 📰 消息面是否有影响")
        st.markdown(news if news else "暂无消息面解读。")

    with st.expander("查看AI原始完整文本"):
        st.markdown(ai_text)


# =========================================================
# 页面主体
# =========================================================
st.markdown(
    """
<div class="hero-card">
    <div class="main-title">📊 AI股票分析平台</div>
    <div class="sub-title">趋势判断 · 消息面辅助 · AI评分 · 买卖点地图 · 小白可读</div>
</div>
""",
    unsafe_allow_html=True
)

left, right = st.columns([0.32, 0.68], gap="large")

with left:
    with st.container(border=True):
        st.subheader("⚙️ 参数设置")

        ticker_input = st.text_input("股票代码", "000066")
        stock_name = st.text_input("股票名称，建议填写中文名", "中国长城")
        period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y"], index=0)
        risk = st.selectbox("风险偏好", ["低", "中", "高"], index=1)

        start = st.button("🚀 开始分析", use_container_width=True)

        st.caption("A股支持：000066、000066.SZ、600519、600519.SS。")

with right:
    st.info("点击左侧开始分析后，将展示K线、AI评分、买卖点地图、消息面和小白解读。")


# =========================================================
# 主流程
# =========================================================
if start:
    if not DEEPSEEK_API_KEY:
        st.error("❌ 没有配置 DeepSeek API Key。请在代码顶部 DEEPSEEK_API_KEY 里填写，或在 Streamlit Secrets 里配置 DEEPSEEK_API_KEY。")
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
            "Volume": "volume",
        },
        inplace=True
    )

    required_cols = ["open", "high", "low", "close", "volume"]

    if not all(col in data.columns for col in required_cols):
        st.error(f"❌ 行情字段异常：{list(data.columns)}")
        st.stop()

    data = data[required_cols].dropna()

    if data.empty:
        st.error("❌ 数据为空，无法分析。")
        st.stop()

    data = calc_indicators(data)

    latest = data.iloc[-1]
    prev = data.iloc[-2] if len(data) >= 2 else latest

    latest_close = safe_float(latest["close"])
    prev_close = safe_float(prev["close"], latest_close)
    day_pct = ((latest_close - prev_close) / prev_close * 100) if prev_close else 0

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
                decreasing_fillcolor=down_color,
            )
        ]
    )

    tick_step = max(1, len(df_plot) // 6)

    fig.update_layout(
        template="plotly_white",
        height=390,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis=dict(
            tickmode="array",
            tickvals=df_plot["x"][::tick_step],
            ticktext=df_plot["date_text"][::tick_step],
            showgrid=False,
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(
            title="价格",
            gridcolor="rgba(148,163,184,0.25)",
        ),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
    )

    with right:
        with st.container(border=True):
            st.subheader(f"📈 {ticker} K线走势")
            st.plotly_chart(fig, use_container_width=True)
            st.success("✅ K线加载完成")

    news_list = fetch_news(stock_name, ticker_input, max_items=8)
    score_detail = calc_ai_score(data, latest, prev, news_list)
    trade_levels = calc_trade_levels(data, latest)

    with right:
        render_score_panel(score_detail)

        with st.container(border=True):
            st.subheader("📰 个股最新消息面")

            if news_list:
                for n in news_list:
                    st.markdown(f"- [{n['title']}]({n['link']})")
            else:
                st.warning("暂未抓取到该股相关新闻。建议股票名称填写中文名，例如：中国长城、贵州茅台、宁德时代。")

        with st.container(border=True):
            st.subheader("📌 技术指标摘要")

            m1, m2, m3 = st.columns(3)
            m1.metric("最新收盘", fmt_num(latest_close), f"{day_pct:.2f}%")
            m2.metric("MA5", fmt_num(latest["ma5"]))
            m3.metric("MA20", fmt_num(latest["ma20"]))

            m4, m5, m6 = st.columns(3)
            m4.metric("MACD DIF", fmt_num(latest["macd_dif"]))
            m5.metric("KDJ-J", fmt_num(latest["kdj_j"]))
            m6.metric("成交量", f"{int(safe_float(latest['volume'])):,}")

    news_text = "\n".join([f"- {n['title']}" for n in news_list])

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

AI评分：
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

关键观察位：
- 当前价：{fmt_num(trade_levels["当前价"])}
- 观察低吸区：{fmt_num(trade_levels["观察低吸区下沿"])} - {fmt_num(trade_levels["观察低吸区上沿"])}
- 突破确认价：{fmt_num(trade_levels["突破确认价"])}
- 压力位：{fmt_num(trade_levels["压力位"])}
- 风险止损线：{fmt_num(trade_levels["风险止损线"])}

个股最新消息：
{news_text if news_text else "暂无抓取到明确的个股新闻"}

要求：
1. 必须严格用中文输出，不要英文。
2. 面向小白用户，少用术语，每段短一点。
3. 必须讲清楚：现在适不适合追、买点在哪里、卖点在哪里、风险线在哪里。
4. 不要承诺收益，不要写绝对买入或绝对卖出。
5. 每个标题必须单独占一行，便于程序分模块展示。

请严格按以下标题输出：

一、结论先看
用3到5句话说明当前最重要的判断：现在是否适合追、AI分数意味着什么、适合什么操作、最大机会和最大风险。

二、买卖点地图
用小白能看懂的话写：
- 观察买点：什么价位附近可以观察，什么条件成立才算更安全。
- 突破确认点：突破什么位置说明短线继续变强。
- 减仓卖点：冲高到哪里或出现什么信号需要减仓。
- 风险止损线：跌破哪里说明短线走弱。

三、AI分数解读
解释为什么当前分数是 {score_detail["总分"]} 分。
分别解释趋势、动能、资金、风险、消息面对分数的影响。
说明这个分数适合进攻、低吸、持有、减仓，还是观察。

四、短线趋势判断
结合K线、涨跌幅、均线、MACD、KDJ判断当前是强势上攻、震荡整理、缩量回调、放量下跌，还是情绪冲顶。

五、技术面分析
分析5日、10日、20日、60日均线。
分析MACD和KDJ。
给出关键支撑位和压力位。

六、资金面分析
结合成交量判断是否有资金异动。
判断当前更像短线炒作还是趋势资金配置。
判断是否存在追高风险。

七、消息面与风险纪律
总结个股新闻对股价的潜在影响。
如果个股新闻不足，请明确说明消息面证据不足，不要硬编。
最后用3条规则说明：什么情况可以继续看、什么情况必须谨慎、什么情况转为观察。
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
        )

        result = response.choices[0].message.content

        with right:
            st.subheader("🤖 AI小白解读")
            render_ai_cards(result, score_detail, trade_levels, risk)

    except Exception as e:
        with right:
            st.error("❌ AI分析失败")
            st.text(e)
