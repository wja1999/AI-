import os
import re
import html
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from openai import OpenAI


# =====================================================
# 1. DeepSeek Key：只改这里
# =====================================================
DEEPSEEK_API_KEY = "sk-34bde63deba4488c939677b2a93fbb01"


# =====================================================
# 2. 页面配置
# =====================================================
st.set_page_config(
    page_title="AI股票分析平台",
    page_icon="📊",
    layout="wide"
)


# =====================================================
# 3. 基础工具函数
# =====================================================
def safe_html(text):
    return html.escape(str(text))


def get_api_key():
    if DEEPSEEK_API_KEY.strip() and DEEPSEEK_API_KEY.strip() != "在这里粘贴你的DeepSeek Key":
        return DEEPSEEK_API_KEY.strip()

    try:
        if "DEEPSEEK_API_KEY" in st.secrets:
            return str(st.secrets["DEEPSEEK_API_KEY"]).strip()
    except Exception:
        pass

    env_key = os.getenv("DEEPSEEK_API_KEY", "")
    if env_key:
        return env_key.strip()

    return ""


def normalize_ticker(raw):
    ticker = str(raw).strip().upper().replace(" ", "")

    if ticker.endswith(".SH"):
        ticker = ticker.replace(".SH", ".SS")

    if re.fullmatch(r"\d{6}", ticker):
        if ticker.startswith(("6", "5", "9")):
            ticker = ticker + ".SS"
        else:
            ticker = ticker + ".SZ"

    return ticker


def is_a_stock(ticker):
    ticker = ticker.upper()
    return ticker.endswith(".SZ") or ticker.endswith(".SS")


def fmt_price(value):
    try:
        if pd.isna(value):
            return "--"
        return f"{float(value):.2f}"
    except Exception:
        return "--"


def fmt_percent(value):
    try:
        if pd.isna(value):
            return "--"
        return f"{float(value):+.2f}%"
    except Exception:
        return "--"


def fmt_int(value):
    try:
        if pd.isna(value):
            return "--"
        return f"{int(float(value)):,}"
    except Exception:
        return "--"


def to_float(value, default=np.nan):
    try:
        if isinstance(value, pd.Series):
            value = value.iloc[-1]
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


# =====================================================
# 4. 数据清洗
# =====================================================
def clean_price_data(raw_data):
    if raw_data is None or raw_data.empty:
        return pd.DataFrame()

    data = raw_data.copy()

    if isinstance(data.columns, pd.MultiIndex):
        level0 = [str(x).lower() for x in data.columns.get_level_values(0)]
        level1 = [str(x).lower() for x in data.columns.get_level_values(1)]

        base_cols = {"open", "high", "low", "close", "adj close", "volume"}

        if any(x in base_cols for x in level0):
            data.columns = data.columns.get_level_values(0)
        elif any(x in base_cols for x in level1):
            data.columns = data.columns.get_level_values(1)
        else:
            data.columns = [str(x[0]) for x in data.columns]

    data = data.loc[:, ~data.columns.duplicated()].copy()
    data.columns = [str(c).strip().lower().replace(" ", "_") for c in data.columns]

    rename_map = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "adj_close": "adj_close",
        "volume": "volume"
    }

    data.rename(columns=rename_map, inplace=True)

    for col in ["open", "high", "low", "close"]:
        if col not in data.columns:
            return pd.DataFrame()

    if "volume" not in data.columns:
        data["volume"] = 0

    data = data[["open", "high", "low", "close", "volume"]].copy()

    for col in ["open", "high", "low", "close", "volume"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(subset=["open", "high", "low", "close"])

    if data.empty:
        return pd.DataFrame()

    data.index = pd.to_datetime(data.index)

    return data


# =====================================================
# 5. 技术指标
# =====================================================
def add_indicators(data):
    df = data.copy()

    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()

    df["macd_dif"] = ema12 - ema26
    df["macd_dea"] = df["macd_dif"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = 2 * (df["macd_dif"] - df["macd_dea"])

    low9 = df["low"].rolling(9).min()
    high9 = df["high"].rolling(9).max()

    rsv = (df["close"] - low9) / (high9 - low9) * 100
    rsv = rsv.replace([np.inf, -np.inf], np.nan).fillna(50)

    df["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
    df["kdj_d"] = df["kdj_k"].ewm(com=2, adjust=False).mean()
    df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]

    df["vol_ma5"] = df["volume"].rolling(5).mean()
    df["ret_5"] = df["close"].pct_change(5) * 100
    df["ret_10"] = df["close"].pct_change(10) * 100

    return df


# =====================================================
# 6. 新闻抓取
# =====================================================
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_news(stock_name, ticker):
    keyword = str(stock_name).strip()
    code = ticker.replace(".SZ", "").replace(".SS", "")

    if keyword:
        query = f"{keyword} {code} 股票 最新 财经 消息"
    else:
        query = f"{code} 股票 最新 财经 消息"

    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    )

    try:
        response = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        if response.status_code != 200:
            return []

        root = ET.fromstring(response.content)
        items = []

        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            source_node = item.find("source")
            source = source_node.text.strip() if source_node is not None and source_node.text else "新闻来源"

            if not title:
                continue

            items.append({
                "title": title,
                "link": link,
                "source": source
            })

            if len(items) >= 6:
                break

        return items

    except Exception:
        return []


def judge_news(title):
    title = str(title)

    good_words = [
        "增长", "大增", "盈利", "净利", "回购", "增持", "中标", "突破",
        "创新高", "订单", "签约", "获批", "利好", "上涨", "涨停", "超预期"
    ]

    bad_words = [
        "减持", "亏损", "下滑", "处罚", "监管", "问询", "立案", "退市",
        "下跌", "暴跌", "利空", "债务", "风险", "警示"
    ]

    good = sum(1 for word in good_words if word in title)
    bad = sum(1 for word in bad_words if word in title)

    if good > bad:
        return "利好", "good"
    if bad > good:
        return "利空", "bad"
    return "中性", "mid"


# =====================================================
# 7. AI评分
# =====================================================
def calc_ai_score(df, news_items):
    latest = df.iloc[-1]

    close = to_float(latest["close"])
    open_price = to_float(latest["open"])
    ma5 = to_float(latest["ma5"])
    ma10 = to_float(latest["ma10"])
    ma20 = to_float(latest["ma20"])
    ma60 = to_float(latest["ma60"])

    dif = to_float(latest["macd_dif"])
    dea = to_float(latest["macd_dea"])
    hist = to_float(latest["macd_hist"])

    k = to_float(latest["kdj_k"])
    d = to_float(latest["kdj_d"])
    j = to_float(latest["kdj_j"])

    volume = to_float(latest["volume"], 0)
    vol_ma5 = to_float(latest["vol_ma5"], 0)

    trend_score = 0

    if not np.isnan(ma5) and close > ma5:
        trend_score += 7
    if not np.isnan(ma10) and close > ma10:
        trend_score += 6
    if not np.isnan(ma20) and close > ma20:
        trend_score += 6
    if not np.isnan(ma60) and close > ma60:
        trend_score += 5
    if not np.isnan(ma5) and not np.isnan(ma10) and not np.isnan(ma20):
        if ma5 >= ma10 >= ma20:
            trend_score += 6

    trend_score = min(trend_score, 30)

    momentum_score = 0

    if not np.isnan(dif) and not np.isnan(dea) and dif > dea:
        momentum_score += 8
    if not np.isnan(hist) and hist > 0:
        momentum_score += 5
    if not np.isnan(k) and not np.isnan(d) and k > d:
        momentum_score += 4
    if not np.isnan(j):
        if 20 <= j <= 80:
            momentum_score += 3
        elif j > 100:
            momentum_score -= 2

    momentum_score = max(0, min(momentum_score, 20))

    volume_score = 0

    if volume > 0 and vol_ma5 > 0:
        ratio = volume / vol_ma5

        if ratio >= 1.5 and close >= open_price:
            volume_score += 14
        elif ratio >= 1.1:
            volume_score += 10
        elif ratio >= 0.8:
            volume_score += 6
        else:
            volume_score += 3
    else:
        volume_score += 5

    if len(df) >= 2:
        prev_close = to_float(df["close"].iloc[-2])
        if close > prev_close and volume > vol_ma5:
            volume_score += 4

    volume_score = min(volume_score, 20)

    risk_score = 15

    if len(df) >= 10:
        recent = df.tail(10)
        volatility = (recent["high"].max() - recent["low"].min()) / close

        if volatility > 0.18:
            risk_score -= 5
        elif volatility > 0.12:
            risk_score -= 3

    if not np.isnan(j) and j > 100:
        risk_score -= 3

    if not np.isnan(ma20) and close < ma20:
        risk_score -= 3

    risk_score = max(0, min(risk_score, 15))

    news_score = 8

    for item in news_items[:5]:
        label, _ = judge_news(item["title"])

        if label == "利好":
            news_score += 2
        elif label == "利空":
            news_score -= 2

    news_score = max(0, min(news_score, 15))

    total = int(round(trend_score + momentum_score + volume_score + risk_score + news_score))

    if total >= 80:
        zone = "强势区"
        action = "可积极关注"
        desc = "趋势、动能和资金配合较强，适合等待回踩或突破确认。"
    elif total >= 65:
        zone = "偏强区"
        action = "低吸或持有观察"
        desc = "结构偏强，但仍需要成交量配合，不适合盲目追高。"
    elif total >= 50:
        zone = "中性区"
        action = "观察为主"
        desc = "多空力量相对均衡，适合等待放量突破或回踩企稳。"
    elif total >= 35:
        zone = "偏弱区"
        action = "谨慎试错"
        desc = "趋势和动能不足，除非出现明确反转，否则不宜追高。"
    else:
        zone = "风险区"
        action = "回避为主"
        desc = "短线结构偏弱，风险收益比不佳，优先等待趋势修复。"

    return {
        "total": total,
        "zone": zone,
        "action": action,
        "desc": desc,
        "trend": int(trend_score),
        "momentum": int(momentum_score),
        "volume": int(volume_score),
        "risk": int(risk_score),
        "news": int(news_score)
    }


# =====================================================
# 8. 买卖点
# =====================================================
def calc_trade_points(df):
    latest = df.iloc[-1]

    close = to_float(latest["close"])
    ma5 = to_float(latest["ma5"])
    ma10 = to_float(latest["ma10"])
    ma20 = to_float(latest["ma20"])

    recent_20 = df.tail(min(20, len(df)))
    recent_10 = df.tail(min(10, len(df)))

    recent_high = to_float(recent_20["high"].max())
    recent_low = to_float(recent_10["low"].min())

    supports = []

    for value in [ma5, ma10, ma20]:
        if not np.isnan(value):
            supports.append(value)

    if supports:
        below = [x for x in supports if x <= close]
        if below:
            buy_low = min(below)
            buy_high = max(below)
        else:
            buy_low = min(supports)
            buy_high = max(supports)
    else:
        buy_low = close * 0.96
        buy_high = close * 0.99

    breakout = max(recent_high, close) * 1.01
    stop_loss = min(recent_low, close * 0.94)

    return {
        "buy_low": buy_low,
        "buy_high": buy_high,
        "breakout": breakout,
        "stop_loss": stop_loss
    }


# =====================================================
# 9. K线图
# =====================================================
def make_kline_chart(df, ticker):
    china = is_a_stock(ticker)

    if china:
        up_color = "#ef4444"
        down_color = "#22c55e"
    else:
        up_color = "#22c55e"
        down_color = "#ef4444"

    chart_df = df.copy().reset_index()
    chart_df["x"] = list(range(len(chart_df)))
    chart_df["date_label"] = pd.to_datetime(chart_df.iloc[:, 0]).dt.strftime("%m-%d")

    volume_colors = []

    for _, row in chart_df.iterrows():
        if row["close"] >= row["open"]:
            volume_colors.append(up_color)
        else:
            volume_colors.append(down_color)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.75, 0.25]
    )

    fig.add_trace(
        go.Candlestick(
            x=chart_df["x"],
            open=chart_df["open"],
            high=chart_df["high"],
            low=chart_df["low"],
            close=chart_df["close"],
            increasing_line_color=up_color,
            increasing_fillcolor=up_color,
            decreasing_line_color=down_color,
            decreasing_fillcolor=down_color,
            name="K线"
        ),
        row=1,
        col=1
    )

    fig.add_trace(
        go.Bar(
            x=chart_df["x"],
            y=chart_df["volume"],
            marker_color=volume_colors,
            opacity=0.45,
            name="成交量"
        ),
        row=2,
        col=1
    )

    tick_step = max(1, len(chart_df) // 6)

    fig.update_layout(
        height=430,
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.20)",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        hovermode="x unified",
        font=dict(size=12, color="#1e293b")
    )

    fig.update_xaxes(
        rangeslider_visible=False,
        showgrid=False,
        tickmode="array",
        tickvals=chart_df["x"][::tick_step],
        ticktext=chart_df["date_label"][::tick_step],
        tickfont=dict(color="#64748b")
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(15,23,42,0.08)",
        zeroline=False,
        title_text="价格",
        row=1,
        col=1
    )

    fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        title_text="量",
        row=2,
        col=1
    )

    return fig


# =====================================================
# 10. CSS
# =====================================================
st.markdown(
    """
<style>
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 12% 8%, rgba(96,165,250,0.24), transparent 32%),
        radial-gradient(circle at 88% 12%, rgba(34,211,238,0.18), transparent 30%),
        linear-gradient(135deg, #edf6ff 0%, #f8fbff 45%, #ecf8ff 100%);
}

[data-testid="stHeader"] {
    background: rgba(255,255,255,0);
}

.block-container {
    max-width: 1480px;
    padding-top: 1.2rem;
    padding-bottom: 2.5rem;
}

h1, h2, h3, h4, h5, h6, p, span, label {
    color: #102033;
}

.app-header {
    background: rgba(255,255,255,0.82);
    border: 1px solid rgba(255,255,255,0.95);
    border-radius: 26px;
    padding: 22px 28px;
    box-shadow: 0 18px 50px rgba(37,99,235,0.10);
    backdrop-filter: blur(18px);
    margin-bottom: 20px;
}

.app-title {
    font-size: 32px;
    font-weight: 950;
    letter-spacing: -0.8px;
    color: #0b1f3a;
}

.app-subtitle {
    margin-top: 6px;
    font-size: 14px;
    color: #64748b;
    font-weight: 700;
}

.glass-card {
    background: rgba(255,255,255,0.78);
    border: 1px solid rgba(255,255,255,0.95);
    border-radius: 24px;
    padding: 22px;
    box-shadow: 0 18px 45px rgba(43,78,124,0.10);
    backdrop-filter: blur(18px);
    margin-bottom: 18px;
}

.section-title {
    font-size: 23px;
    font-weight: 950;
    color: #0b1f3a;
    margin-bottom: 15px;
}

.hint-box {
    background: linear-gradient(135deg, rgba(37,99,235,0.12), rgba(6,182,212,0.12));
    border: 1px solid rgba(37,99,235,0.16);
    color: #1e4d88;
    border-radius: 16px;
    padding: 14px 16px;
    font-weight: 700;
    margin-bottom: 14px;
}

.stTextInput input {
    background: rgba(255,255,255,0.96) !important;
    color: #0f172a !important;
    border: 1px solid rgba(83,113,165,0.28) !important;
    border-radius: 13px !important;
    height: 42px !important;
    font-weight: 750 !important;
}

div[data-baseweb="select"] > div {
    background: rgba(255,255,255,0.96) !important;
    color: #0f172a !important;
    border: 1px solid rgba(83,113,165,0.28) !important;
    border-radius: 13px !important;
    min-height: 42px !important;
    font-weight: 750 !important;
}

div.stButton > button {
    width: 100%;
    height: 46px;
    border-radius: 15px;
    border: 0;
    color: white;
    font-weight: 900;
    background: linear-gradient(135deg, #2563eb, #06b6d4);
    box-shadow: 0 12px 26px rgba(37,99,235,0.22);
}

div.stButton > button:hover {
    color: white;
    border: 0;
    filter: brightness(1.04);
}

.kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-top: 12px;
}

.kpi-box {
    padding: 15px;
    border-radius: 18px;
    background: rgba(255,255,255,0.88);
    border: 1px solid rgba(87,120,174,0.16);
    box-shadow: 0 10px 26px rgba(43,78,124,0.08);
}

.kpi-label {
    font-size: 12px;
    color: #64748b;
    font-weight: 850;
    margin-bottom: 8px;
}

.kpi-value {
    font-size: 24px;
    color: #102033;
    font-weight: 950;
    line-height: 1.1;
}

.score-card {
    padding: 20px;
    border-radius: 24px;
    background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(239,247,255,0.90));
    border: 1px solid rgba(92,143,230,0.20);
    box-shadow: 0 18px 45px rgba(37,99,235,0.10);
    margin-bottom: 16px;
}

.score-row {
    display: flex;
    align-items: center;
    gap: 18px;
    margin-bottom: 14px;
}

.score-number {
    width: 110px;
    height: 110px;
    border-radius: 24px;
    background: #ffffff;
    border: 1px solid rgba(37,99,235,0.15);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.7);
    flex-shrink: 0;
}

.score-number strong {
    font-size: 36px;
    color: #2563eb;
    line-height: 1;
}

.score-number span {
    font-size: 13px;
    color: #64748b;
    font-weight: 850;
    margin-top: 6px;
}

.score-title {
    font-size: 22px;
    font-weight: 950;
    color: #0b1f3a;
    margin-bottom: 8px;
}

.score-desc {
    color: #334155;
    font-size: 14px;
    line-height: 1.7;
    font-weight: 650;
}

.score-bar {
    height: 12px;
    width: 100%;
    background: rgba(15,23,42,0.12);
    border-radius: 99px;
    overflow: hidden;
    margin-top: 12px;
}

.score-fill {
    height: 100%;
    border-radius: 99px;
    background: linear-gradient(90deg, #3b82f6, #06b6d4);
}

.point-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
}

.point-card {
    padding: 17px;
    border-radius: 20px;
    background: rgba(255,255,255,0.88);
    border: 1px solid rgba(87,120,174,0.16);
    box-shadow: 0 12px 30px rgba(43,78,124,0.08);
}

.point-name {
    font-size: 16px;
    font-weight: 950;
    margin-bottom: 10px;
    color: #0b1f3a;
}

.point-price {
    font-size: 21px;
    font-weight: 950;
    color: #111827;
    margin-bottom: 8px;
}

.point-desc {
    font-size: 13px;
    color: #475569;
    line-height: 1.65;
    font-weight: 650;
}

.news-card {
    padding: 14px 16px;
    border-radius: 18px;
    background: rgba(255,255,255,0.86);
    border: 1px solid rgba(87,120,174,0.15);
    margin-bottom: 10px;
    box-shadow: 0 10px 24px rgba(43,78,124,0.06);
}

.news-title {
    font-size: 14px;
    line-height: 1.55;
    font-weight: 850;
    margin-top: 6px;
}

.news-title a {
    color: #1d4ed8;
    text-decoration: none;
}

.tag {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 850;
    margin-right: 6px;
}

.tag-good {
    background: rgba(22,163,74,0.12);
    color: #15803d;
}

.tag-bad {
    background: rgba(239,68,68,0.12);
    color: #dc2626;
}

.tag-mid {
    background: rgba(100,116,139,0.12);
    color: #475569;
}

.explain-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.explain-card {
    padding: 18px;
    border-radius: 20px;
    background: rgba(255,255,255,0.88);
    border: 1px solid rgba(87,120,174,0.15);
    box-shadow: 0 12px 28px rgba(43,78,124,0.07);
}

.explain-card h4 {
    margin: 0 0 10px 0;
    font-size: 17px;
    font-weight: 950;
}

.explain-card p {
    font-size: 14px;
    color: #334155;
    line-height: 1.75;
    font-weight: 650;
}

.notice {
    color: #64748b;
    font-size: 12px;
    line-height: 1.6;
    font-weight: 650;
    margin-top: 12px;
}

@media (max-width: 900px) {
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .app-title {
        font-size: 26px;
    }

    .kpi-grid,
    .explain-grid {
        grid-template-columns: 1fr;
    }

    .score-row {
        flex-direction: column;
        align-items: flex-start;
    }
}
</style>
""",
    unsafe_allow_html=True
)


# =====================================================
# 11. 页面头部
# =====================================================
st.markdown(
    """
<div class="app-header">
    <div class="app-title">📊 AI股票分析平台</div>
    <div class="app-subtitle">趋势判断 · 消息面辅助 · AI评分 · 买卖点地图 · 小白可读</div>
</div>
""",
    unsafe_allow_html=True
)


# =====================================================
# 12. 输入区域
# =====================================================
left_col, mid_col, right_col = st.columns([0.9, 1.65, 1.05], gap="large")

with left_col:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">⚙️ 参数设置</div>', unsafe_allow_html=True)

    ticker_input = st.text_input("股票代码", "000066.SZ")
    stock_name = st.text_input("股票名称，建议填写中文", "中国长城")
    period = st.selectbox("周期", ["5d", "1mo", "3mo", "6mo", "1y"], index=1)
    risk = st.selectbox("风险偏好", ["低", "中", "高"], index=2)

    run = st.button("🚀 开始分析")

    st.markdown(
        """
<div class="notice">
A股支持：000066、000066.SZ、600519、600519.SS。<br>
只输入6位代码时，系统会自动识别深市/沪市。
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# 13. 未点击按钮时的默认展示
# =====================================================
if not run:
    with mid_col:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📈 市场走势</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="hint-box">点击左侧开始分析后，将展示K线图、成交量、AI评分和买卖点地图。</div>',
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with right_col:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🧠 AI综合评分</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="hint-box">评分会综合趋势结构、动能指标、成交量资金、风险状态和消息面。</div>',
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()


# =====================================================
# 14. 获取行情
# =====================================================
ticker = normalize_ticker(ticker_input)

with st.spinner("正在获取行情数据..."):
    raw_data = yf.download(
        ticker,
        period=period,
        auto_adjust=False,
        progress=False
    )

data = clean_price_data(raw_data)

if data.empty:
    st.error("❌ 没有获取到有效行情数据。请检查股票代码，例如：000066.SZ、601881.SS、AAPL。")
    st.stop()

data = add_indicators(data)

if len(data) < 5:
    st.error("❌ 数据量太少，无法进行稳定技术分析。建议周期选择 1mo 或 3mo。")
    st.stop()


# =====================================================
# 15. 计算分析数据
# =====================================================
news_items = fetch_news(stock_name, ticker)
score = calc_ai_score(data, news_items)
trade_points = calc_trade_points(data)

latest = data.iloc[-1]
latest_close = to_float(latest["close"])
prev_close = to_float(data["close"].iloc[-2]) if len(data) >= 2 else latest_close
change_pct = (latest_close / prev_close - 1) * 100 if prev_close and not np.isnan(prev_close) else np.nan

ma5 = to_float(latest["ma5"])
ma10 = to_float(latest["ma10"])
ma20 = to_float(latest["ma20"])
macd_dif = to_float(latest["macd_dif"])
kdj_j = to_float(latest["kdj_j"])
volume = to_float(latest["volume"], 0)


# =====================================================
# 16. 中间区域：K线与指标
# =====================================================
with mid_col:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="section-title">📈 {safe_html(ticker)} K线趋势</div>',
        unsafe_allow_html=True
    )

    fig = make_kline_chart(data, ticker)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.success("✅ K线加载完成")

    st.markdown(
        f"""
<div class="kpi-grid">
    <div class="kpi-box">
        <div class="kpi-label">最新收盘</div>
        <div class="kpi-value">{fmt_price(latest_close)}</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">日涨跌幅</div>
        <div class="kpi-value">{fmt_percent(change_pct)}</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">成交量</div>
        <div class="kpi-value">{fmt_int(volume)}</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">MA5</div>
        <div class="kpi-value">{fmt_price(ma5)}</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">MA20</div>
        <div class="kpi-value">{fmt_price(ma20)}</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">KDJ-J</div>
        <div class="kpi-value">{fmt_price(kdj_j)}</div>
    </div>
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# 17. 右侧区域：评分与买卖点
# =====================================================
with right_col:
    score_width = max(0, min(100, score["total"]))

    st.markdown(
        f"""
<div class="score-card">
    <div class="score-row">
        <div class="score-number">
            <strong>{score["total"]}</strong>
            <span>/ 100</span>
        </div>
        <div>
            <div class="score-title">{safe_html(score["zone"])} · {safe_html(score["action"])}</div>
            <div class="score-desc">{safe_html(score["desc"])}</div>
        </div>
    </div>
    <div class="score-bar">
        <div class="score-fill" style="width:{score_width}%;"></div>
    </div>
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🧭 买卖点地图</div>', unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="point-grid">
    <div class="point-card">
        <div class="point-name">🟢 观察买点</div>
        <div class="point-price">{fmt_price(trade_points["buy_low"])} - {fmt_price(trade_points["buy_high"])}</div>
        <div class="point-desc">回踩到短期均线附近，并且没有放量跌破时，再观察低吸机会。</div>
    </div>
    <div class="point-card">
        <div class="point-name">🚀 突破确认点</div>
        <div class="point-price">{fmt_price(trade_points["breakout"])}</div>
        <div class="point-desc">放量突破近期高点，说明短线资金可能继续进攻。</div>
    </div>
    <div class="point-card">
        <div class="point-name">🔴 风险止损线</div>
        <div class="point-price">{fmt_price(trade_points["stop_loss"])}</div>
        <div class="point-desc">跌破该位置且成交量放大，说明短线结构可能转弱。</div>
    </div>
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# 18. 评分拆解与新闻
# =====================================================
score_col, news_col = st.columns([1.05, 1.15], gap="large")

with score_col:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🧠 AI评分拆解</div>', unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="kpi-grid">
    <div class="kpi-box">
        <div class="kpi-label">趋势结构</div>
        <div class="kpi-value">{score["trend"]} / 30</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">动能指标</div>
        <div class="kpi-value">{score["momentum"]} / 20</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">成交量资金</div>
        <div class="kpi-value">{score["volume"]} / 20</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">风险状态</div>
        <div class="kpi-value">{score["risk"]} / 15</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">消息面</div>
        <div class="kpi-value">{score["news"]} / 15</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-label">适合操作</div>
        <div class="kpi-value" style="font-size:20px;">{safe_html(score["action"])}</div>
    </div>
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown('</div>', unsafe_allow_html=True)


with news_col:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📰 个股最新消息面</div>', unsafe_allow_html=True)

    if news_items:
        for item in news_items[:5]:
            label, tag_class = judge_news(item["title"])

            st.markdown(
                f"""
<div class="news-card">
    <div>
        <span class="tag tag-{tag_class}">{safe_html(label)}</span>
        <span class="tag tag-mid">{safe_html(item["source"])}</span>
    </div>
    <div class="news-title">
        <a href="{safe_html(item["link"])}" target="_blank">{safe_html(item["title"])}</a>
    </div>
</div>
""",
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            '<div class="hint-box">暂未抓取到高相关个股新闻。可以继续参考K线、成交量和AI技术分析。</div>',
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# 19. 小白决策看板
# =====================================================
technical_text = "短线结构还不够明确，需要等待更清晰的放量信号。"

if not np.isnan(ma5) and latest_close > ma5:
    technical_text = "股价站上5日均线，短线有一定承接。"

if not np.isnan(ma5) and not np.isnan(ma20) and latest_close > ma5 > ma20:
    technical_text = "股价在短期均线之上，短线结构偏强。"

if not np.isnan(ma20) and latest_close < ma20:
    technical_text = "股价低于20日均线，短线仍偏弱，需要等待趋势修复。"

momentum_text = "动能信号一般，需要观察是否放量。"

if not np.isnan(macd_dif) and macd_dif > 0:
    momentum_text = "MACD处于相对积极状态，说明短线动能有所改善。"

if not np.isnan(kdj_j) and kdj_j > 100:
    momentum_text = "KDJ-J偏高，短线可能存在冲高回落风险。"

st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🎯 小白决策看板</div>', unsafe_allow_html=True)

st.markdown(
    f"""
<div class="explain-grid">
    <div class="explain-card">
        <h4>✅ 先看结论</h4>
        <p>当前AI分数为 <b>{score["total"]}/100</b>，属于 <b>{safe_html(score["zone"])}</b>。更适合：<b>{safe_html(score["action"])}</b>。</p>
    </div>
    <div class="explain-card">
        <h4>📈 技术面怎么看</h4>
        <p>{safe_html(technical_text)}</p>
    </div>
    <div class="explain-card">
        <h4>💰 资金面怎么看</h4>
        <p>成交量资金得分为 <b>{score["volume"]}/20</b>。分数越高，说明量价配合越好；分数偏低时，不宜只看价格追高。</p>
    </div>
    <div class="explain-card">
        <h4>🛡️ 风险怎么看</h4>
        <p>{safe_html(momentum_text)} 风险止损线参考 <b>{fmt_price(trade_points["stop_loss"])}</b>。</p>
    </div>
</div>
""",
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# 20. AI完整解读
# =====================================================
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🤖 AI完整解读</div>', unsafe_allow_html=True)

api_key = get_api_key()

if not api_key:
    st.warning("⚠️ 未配置 DeepSeek API Key。请在 app.py 顶部 DEEPSEEK_API_KEY 位置填写你的 Key。")
else:
    try:
        news_text = "暂无抓取到高相关个股新闻。"

        if news_items:
            news_lines = []
            for index, item in enumerate(news_items[:6], start=1):
                label, _ = judge_news(item["title"])
                news_lines.append(f"{index}. 【{label}】{item['title']} - {item['source']}")
            news_text = "\n".join(news_lines)

        prompt = f"""
你是A股短线技术分析助手。请只用简体中文回答，内容要让股票小白也能看懂。

股票代码：{ticker}
股票名称：{stock_name}
分析周期：{period}
用户风险偏好：{risk}

最新技术数据：
最新收盘价：{fmt_price(latest_close)}
日涨跌幅：{fmt_percent(change_pct)}
MA5：{fmt_price(ma5)}
MA10：{fmt_price(ma10)}
MA20：{fmt_price(ma20)}
MACD DIF：{fmt_price(macd_dif)}
KDJ-J：{fmt_price(kdj_j)}
成交量：{fmt_int(volume)}

AI综合评分：
总分：{score["total"]}/100
分区：{score["zone"]}
当前适合操作：{score["action"]}
趋势结构：{score["trend"]}/30
动能指标：{score["momentum"]}/20
成交量资金：{score["volume"]}/20
风险状态：{score["risk"]}/15
消息面：{score["news"]}/15

买卖点地图：
观察买点：{fmt_price(trade_points["buy_low"])} - {fmt_price(trade_points["buy_high"])}
突破确认点：{fmt_price(trade_points["breakout"])}
风险止损线：{fmt_price(trade_points["stop_loss"])}

相关新闻：
{news_text}

请按以下结构输出：

一、先给小白看的结论
用3句话说明当前更适合观察、低吸、突破跟随、减仓还是回避。

二、为什么这么判断
分别从趋势、成交量、MACD/KDJ、消息面解释。

三、买卖点地图
明确说明：
1. 什么条件可以观察低吸
2. 什么条件可以确认突破
3. 什么情况必须止损或离场

四、核心机会
列3条。

五、核心风险
列3条。

六、AI观察计划
给出普通用户能执行的观察计划。不要保证收益，不要使用绝对化表达。
"""

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是A股投资分析助手，只用简体中文回答，重点突出买卖点、风险和执行条件。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.35
        )

        result = response.choices[0].message.content
        st.markdown(result)

    except Exception as e:
        st.error("❌ AI分析失败，但K线、评分和买卖点地图已正常生成。")
        st.text(str(e))

st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# 21. 底部提示
# =====================================================
st.caption("说明：本工具仅用于辅助观察，不保证收益。实际交易需结合账户风险承受能力、市场环境和交易纪律。")
