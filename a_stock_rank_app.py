import re
import time
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed


# =====================================================
# 🔐 这里填写你的 DeepSeek Key，重点只改这一行
# =====================================================
DEEPSEEK_API_KEY = "sk-34bde63deba4488c939677b2a93fbb01"

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


st.set_page_config(
    page_title="A股AI高分榜",
    page_icon="📊",
    layout="wide"
)


st.markdown(
    """
<style>
.stApp {
    background:
        radial-gradient(circle at 12% 8%, rgba(37,99,235,0.13), transparent 30%),
        radial-gradient(circle at 88% 10%, rgba(6,182,212,0.12), transparent 32%),
        linear-gradient(135deg, #eef7ff 0%, #f8fbff 52%, #ffffff 100%);
    color: #0f172a;
}

.block-container {
    max-width: 1500px;
    padding-top: 24px;
    padding-bottom: 36px;
}

h1, h2, h3, h4, p, span, li {
    color: #0f172a;
}

.hero {
    background: rgba(255,255,255,0.82);
    border: 1px solid rgba(148,163,184,0.24);
    border-radius: 26px;
    padding: 24px 28px;
    box-shadow: 0 18px 45px rgba(15,23,42,0.08);
    backdrop-filter: blur(18px);
    margin-bottom: 22px;
}

.hero-title {
    font-size: 34px;
    font-weight: 950;
    color: #0b1f3a;
}

.hero-sub {
    margin-top: 8px;
    color: #64748b;
    font-weight: 700;
    font-size: 15px;
}

.panel {
    background: rgba(255,255,255,0.78);
    border: 1px solid rgba(148,163,184,0.24);
    border-radius: 22px;
    padding: 22px;
    box-shadow: 0 16px 38px rgba(15,23,42,0.07);
    backdrop-filter: blur(18px);
    margin-bottom: 18px;
}

.section-title {
    font-size: 23px;
    font-weight: 950;
    color: #0f172a;
    margin-bottom: 16px;
}

.metric-card {
    background: rgba(255,255,255,0.90);
    border: 1px solid rgba(148,163,184,0.24);
    border-radius: 18px;
    padding: 18px;
    box-shadow: 0 12px 28px rgba(15,23,42,0.06);
}

.metric-label {
    font-size: 13px;
    color: #64748b;
    font-weight: 850;
    margin-bottom: 8px;
}

.metric-value {
    font-size: 30px;
    color: #0f172a;
    font-weight: 950;
}

.metric-sub {
    font-size: 12px;
    color: #64748b;
    margin-top: 6px;
    font-weight: 650;
}

.stButton button {
    width: 100%;
    height: 48px;
    border-radius: 14px;
    border: none;
    background: linear-gradient(90deg, #2563eb, #06b6d4);
    color: white !important;
    font-weight: 900;
    box-shadow: 0 14px 28px rgba(37,99,235,0.22);
}

.stTextInput input,
.stNumberInput input {
    background: rgba(255,255,255,0.96) !important;
    color: #0f172a !important;
    border: 1px solid rgba(148,163,184,0.42) !important;
    border-radius: 14px !important;
    font-weight: 750 !important;
}

div[data-baseweb="select"] > div {
    background: rgba(255,255,255,0.96) !important;
    color: #0f172a !important;
    border: 1px solid rgba(148,163,184,0.42) !important;
    border-radius: 14px !important;
}

.tip {
    background: linear-gradient(90deg, rgba(37,99,235,0.11), rgba(6,182,212,0.10));
    border: 1px solid rgba(37,99,235,0.16);
    border-radius: 16px;
    padding: 14px 16px;
    color: #1e3a8a;
    font-weight: 750;
    margin-bottom: 16px;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span {
    color: #102033 !important;
}
</style>
""",
    unsafe_allow_html=True
)


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def fmt_price(value):
    return f"{safe_float(value):.2f}"


def fmt_pct(value):
    return f"{safe_float(value):+.2f}%"


def eastmoney_headers():
    return {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*"
    }


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_a_stock_list():
    url = "https://push2.eastmoney.com/api/qt/clist/get"

    params = {
        "pn": 1,
        "pz": 6000,
        "po": 1,
        "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": "m:0+t:6,m:0+t:80,m:0+t:81,m:1+t:2,m:1+t:23",
        "fields": "f12,f14,f13,f2,f3,f6"
    }

    try:
        r = requests.get(url, params=params, headers=eastmoney_headers(), timeout=12)
        data = r.json()
        rows = data.get("data", {}).get("diff", [])

        stocks = []

        for row in rows:
            code = str(row.get("f12", "")).strip()
            name = str(row.get("f14", "")).strip()
            market = str(row.get("f13", "")).strip()

            if not code or not name or not market:
                continue

            if name.startswith(("ST", "*ST", "退")):
                continue

            if not re.fullmatch(r"\d{6}", code):
                continue

            stocks.append({
                "code": code,
                "name": name,
                "market": market,
                "secid": f"{market}.{code}"
            })

        return stocks

    except Exception:
        return []


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_kline(secid, limit=120):
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

    params = {
        "secid": secid,
        "klt": 101,
        "fqt": 1,
        "lmt": limit,
        "end": 20500101,
        "iscca": 1,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    }

    try:
        r = requests.get(url, params=params, headers=eastmoney_headers(), timeout=8)
        js = r.json()
        klines = js.get("data", {}).get("klines", [])

        if not klines:
            return pd.DataFrame()

        records = []

        for item in klines:
            parts = item.split(",")

            if len(parts) < 7:
                continue

            records.append({
                "date": parts[0],
                "open": safe_float(parts[1]),
                "close": safe_float(parts[2]),
                "high": safe_float(parts[3]),
                "low": safe_float(parts[4]),
                "volume": safe_float(parts[5]),
                "amount": safe_float(parts[6]),
                "pct": safe_float(parts[8]) if len(parts) > 8 else 0.0,
                "turnover": safe_float(parts[10]) if len(parts) > 10 else 0.0
            })

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")

        return df

    except Exception:
        return pd.DataFrame()


def add_indicators(df):
    data = df.copy()

    data["ma5"] = data["close"].rolling(5, min_periods=1).mean()
    data["ma10"] = data["close"].rolling(10, min_periods=1).mean()
    data["ma20"] = data["close"].rolling(20, min_periods=1).mean()
    data["ma60"] = data["close"].rolling(60, min_periods=1).mean()

    ema12 = data["close"].ewm(span=12, adjust=False).mean()
    ema26 = data["close"].ewm(span=26, adjust=False).mean()

    data["macd_dif"] = ema12 - ema26
    data["macd_dea"] = data["macd_dif"].ewm(span=9, adjust=False).mean()
    data["macd_hist"] = (data["macd_dif"] - data["macd_dea"]) * 2

    low_min = data["low"].rolling(9, min_periods=1).min()
    high_max = data["high"].rolling(9, min_periods=1).max()
    spread = (high_max - low_min).replace(0, np.nan)

    rsv = ((data["close"] - low_min) / spread * 100).fillna(50)

    data["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
    data["kdj_d"] = data["kdj_k"].ewm(com=2, adjust=False).mean()
    data["kdj_j"] = 3 * data["kdj_k"] - 2 * data["kdj_d"]

    data["volume_ma5"] = data["volume"].rolling(5, min_periods=1).mean()

    return data


def calculate_trade_map(df):
    latest = df.iloc[-1]

    close = safe_float(latest["close"])
    ma5 = safe_float(latest["ma5"])
    ma10 = safe_float(latest["ma10"])
    ma20 = safe_float(latest["ma20"])

    recent = df.tail(20)

    recent_high = safe_float(recent["high"].max())
    recent_low = safe_float(recent["low"].min())

    support_values = [x for x in [ma5, ma10, ma20] if x > 0]

    if support_values:
        watch_low = min(support_values)
        watch_high = max(support_values)
    else:
        watch_low = close * 0.96
        watch_high = close * 0.99

    breakout = max(recent_high, close)
    stop_loss = min(recent_low, close * 0.95)

    return {
        "watch_low": watch_low,
        "watch_high": watch_high,
        "breakout": breakout,
        "stop_loss": stop_loss
    }


def calculate_score(df):
    latest = df.iloc[-1]

    close = safe_float(latest["close"])
    open_price = safe_float(latest["open"])
    ma5 = safe_float(latest["ma5"])
    ma10 = safe_float(latest["ma10"])
    ma20 = safe_float(latest["ma20"])
    ma60 = safe_float(latest["ma60"])
    macd_dif = safe_float(latest["macd_dif"])
    macd_dea = safe_float(latest["macd_dea"])
    macd_hist = safe_float(latest["macd_hist"])
    kdj_j = safe_float(latest["kdj_j"])
    volume = safe_float(latest["volume"])
    volume_ma5 = safe_float(latest["volume_ma5"])
    turnover = safe_float(latest.get("turnover", 0))

    trend_score = 0

    if close >= ma5:
        trend_score += 6
    if close >= ma10:
        trend_score += 6
    if close >= ma20:
        trend_score += 6
    if close >= ma60:
        trend_score += 4
    if ma5 >= ma10:
        trend_score += 4
    if ma10 >= ma20:
        trend_score += 4

    trend_score = min(30, trend_score)

    momentum_score = 0

    if macd_dif >= macd_dea:
        momentum_score += 7
    if macd_hist >= 0:
        momentum_score += 5
    if 45 <= kdj_j <= 85:
        momentum_score += 6
    elif 20 <= kdj_j < 45:
        momentum_score += 4
    elif kdj_j > 85:
        momentum_score += 2
    if close >= open_price:
        momentum_score += 2

    momentum_score = min(20, momentum_score)

    volume_score = 8

    if volume > 0 and volume_ma5 > 0:
        ratio = volume / volume_ma5

        if ratio >= 1.5 and close >= open_price:
            volume_score = 18
        elif ratio >= 1.1 and close >= open_price:
            volume_score = 15
        elif ratio >= 1.3 and close < open_price:
            volume_score = 7
        elif ratio < 0.75:
            volume_score = 6
        else:
            volume_score = 10

    if turnover >= 5 and close >= open_price:
        volume_score = min(20, volume_score + 2)

    risk_score = 15

    recent = df.tail(20)
    ret = recent["close"].pct_change().dropna()
    volatility = safe_float(ret.std())
    recent_high = safe_float(recent["high"].max())

    drawdown = 0

    if recent_high > 0:
        drawdown = (close - recent_high) / recent_high

    if volatility > 0.05:
        risk_score -= 5
    elif volatility > 0.035:
        risk_score -= 3

    if drawdown < -0.12:
        risk_score -= 5
    elif drawdown < -0.07:
        risk_score -= 3

    if kdj_j > 100:
        risk_score -= 3

    risk_score = max(0, min(15, risk_score))

    news_score = 10

    total = int(round(
        trend_score +
        momentum_score +
        volume_score +
        risk_score +
        news_score
    ))

    total = max(0, min(100, total))

    if total >= 85:
        level = "强势高分"
        action = "重点观察"
    elif total >= 75:
        level = "偏强"
        action = "加入观察池"
    elif total >= 65:
        level = "中性偏强"
        action = "等待确认"
    else:
        level = "普通"
        action = "暂不优先"

    trade_map = calculate_trade_map(df)

    return {
        "score": total,
        "level": level,
        "action": action,
        "trend_score": trend_score,
        "momentum_score": momentum_score,
        "volume_score": volume_score,
        "risk_score": risk_score,
        "news_score": news_score,
        "close": close,
        "pct": safe_float(latest.get("pct", 0)),
        "turnover": turnover,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "macd_dif": macd_dif,
        "macd_dea": macd_dea,
        "kdj_j": kdj_j,
        "volume": volume,
        "watch_low": trade_map["watch_low"],
        "watch_high": trade_map["watch_high"],
        "breakout": trade_map["breakout"],
        "stop_loss": trade_map["stop_loss"],
    }


def scan_one(stock):
    code = stock["code"]
    name = stock["name"]
    secid = stock["secid"]

    df = get_kline(secid, limit=120)

    if df.empty or len(df) < 30:
        return None

    df = add_indicators(df)
    score_info = calculate_score(df)

    return {
        "代码": code,
        "名称": name,
        "AI分数": score_info["score"],
        "评级": score_info["level"],
        "操作": score_info["action"],
        "最新价": score_info["close"],
        "涨跌幅": score_info["pct"],
        "换手率": score_info["turnover"],
        "趋势": score_info["trend_score"],
        "动能": score_info["momentum_score"],
        "资金": score_info["volume_score"],
        "风险": score_info["risk_score"],
        "消息": score_info["news_score"],
        "观察买点": f'{fmt_price(score_info["watch_low"])} - {fmt_price(score_info["watch_high"])}',
        "突破确认点": fmt_price(score_info["breakout"]),
        "风险止损线": fmt_price(score_info["stop_loss"]),
    }


def scan_all_stocks(stocks, threshold=85, max_workers=20):
    results = []

    total = len(stocks)
    progress = st.progress(0)
    status = st.empty()

    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(scan_one, stock) for stock in stocks]

        for future in as_completed(futures):
            completed += 1

            try:
                item = future.result()
                if item and item["AI分数"] >= threshold:
                    results.append(item)
            except Exception:
                pass

            if completed % 20 == 0 or completed == total:
                progress.progress(completed / total)
                status.write(f"正在扫描：{completed} / {total}，当前入选：{len(results)} 只")

    progress.empty()
    status.empty()

    df = pd.DataFrame(results)

    if df.empty:
        return df

    df = df.sort_values(
        by=["AI分数", "涨跌幅", "换手率"],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    df.insert(0, "排名", df.index + 1)

    return df


def build_kline_chart(secid, title):
    df = get_kline(secid, limit=90)

    if df.empty:
        return None

    df = add_indicators(df)

    plot_df = df.reset_index()
    plot_df["x"] = list(range(len(plot_df)))
    plot_df["date_label"] = plot_df["date"].dt.strftime("%m-%d")

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=plot_df["x"],
            open=plot_df["open"],
            high=plot_df["high"],
            low=plot_df["low"],
            close=plot_df["close"],
            increasing_line_color="#ef4444",
            increasing_fillcolor="#ef4444",
            decreasing_line_color="#16a34a",
            decreasing_fillcolor="#16a34a",
            name="K线"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=plot_df["x"],
            y=plot_df["ma5"],
            mode="lines",
            line=dict(width=1.5),
            name="MA5"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=plot_df["x"],
            y=plot_df["ma20"],
            mode="lines",
            line=dict(width=1.5),
            name="MA20"
        )
    )

    step = max(1, len(plot_df) // 6)

    fig.update_xaxes(
        tickmode="array",
        tickvals=plot_df["x"][::step],
        ticktext=plot_df["date_label"][::step],
        rangeslider_visible=False
    )

    fig.update_layout(
        title=title,
        height=420,
        template="plotly_white",
        margin=dict(l=20, r=20, t=42, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.35)"
    )

    return fig


def deepseek_summary(result_df):
    if result_df.empty:
        return "今日没有筛选到高分个股。"

    top_df = result_df.head(10)

    prompt = f"""
你是A股短线选股助手，请基于以下AI评分榜单，用中文生成一段简洁复盘。

要求：
1. 总结今日高分股整体特征。
2. 点出前3名值得关注的原因。
3. 提醒风险，不要承诺收益。
4. 语言让普通用户能看懂。

榜单数据：
{top_df.to_string(index=False)}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是专业A股短线选股助手，只用简体中文回答。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.35
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"DeepSeek解读生成失败，但榜单已正常生成。错误：{e}"


st.markdown(
    """
<div class="hero">
    <div class="hero-title">📊 A股每日AI高分榜</div>
    <div class="hero-sub">每日遍历A股 · 技术指标评分 · 自动筛选85分以上强势个股 · 生成观察榜单</div>
</div>
""",
    unsafe_allow_html=True
)


left, right = st.columns([0.28, 0.72], gap="large")

with left:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">⚙️ 扫描设置</div>', unsafe_allow_html=True)

    threshold = st.number_input(
        "入榜分数线",
        min_value=50,
        max_value=100,
        value=85,
        step=1
    )

    max_workers = st.selectbox(
        "扫描速度",
        [8, 12, 16, 20],
        index=2,
        help="数字越大扫描越快，但线上环境压力也更大。默认16较稳。"
    )

    start_scan = st.button("🚀 开始扫描今日高分榜")

    st.markdown(
        """
<div style="margin-top:14px;color:#64748b;font-size:12px;font-weight:650;line-height:1.7;">
说明：首次扫描会较慢，后续会使用缓存。<br>
评分主要基于K线、均线、MACD、KDJ、成交量、风险状态。<br><br>
🔐 DeepSeek Key 已在代码顶部配置。
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown("</div>", unsafe_allow_html=True)


with right:
    stocks = get_a_stock_list()

    if not stocks:
        st.error("❌ 未获取到A股股票池，请稍后重试。")
        st.stop()

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📌 今日扫描概览</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"""
<div class="metric-card">
    <div class="metric-label">股票池数量</div>
    <div class="metric-value">{len(stocks)}</div>
    <div class="metric-sub">已剔除ST/退市标识</div>
</div>
""",
            unsafe_allow_html=True
        )

    with c2:
        st.markdown(
            f"""
<div class="metric-card">
    <div class="metric-label">入榜分数线</div>
    <div class="metric-value">{threshold}+</div>
    <div class="metric-sub">AI综合评分</div>
</div>
""",
            unsafe_allow_html=True
        )

    with c3:
        st.markdown(
            f"""
<div class="metric-card">
    <div class="metric-label">扫描模式</div>
    <div class="metric-value">每日榜</div>
    <div class="metric-sub">行情缓存6小时，股票池缓存24小时</div>
</div>
""",
            unsafe_allow_html=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

    if not start_scan:
        st.markdown(
            """
<div class="tip">
点击左侧“开始扫描今日高分榜”，系统会遍历A股股票池，筛选AI分数达到85分以上的个股。
</div>
""",
            unsafe_allow_html=True
        )
        st.stop()

    start_time = time.time()

    with st.spinner("正在遍历A股股票池，生成今日AI高分榜..."):
        result_df = scan_all_stocks(
            stocks=stocks,
            threshold=threshold,
            max_workers=max_workers
        )

    cost = time.time() - start_time

    if result_df.empty:
        st.warning(f"今日暂无 {threshold} 分以上个股。可以将分数线调低到 75 或 80 观察。")
        st.stop()

    st.success(f"✅ 扫描完成：入选 {len(result_df)} 只，用时 {cost:.1f} 秒")

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🏆 今日AI高分榜</div>', unsafe_allow_html=True)

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True
    )

    csv = result_df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "下载今日高分榜 CSV",
        data=csv,
        file_name="A股AI高分榜.csv",
        mime="text/csv"
    )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🤖 DeepSeek榜单解读</div>', unsafe_allow_html=True)

    summary = deepseek_summary(result_df)
    st.markdown(summary)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📈 入榜个股K线预览</div>', unsafe_allow_html=True)

    options = [
        f'{row["代码"]} {row["名称"]}｜{row["AI分数"]}分'
        for _, row in result_df.head(50).iterrows()
    ]

    selected = st.selectbox("选择个股查看K线", options)

    selected_code = selected.split(" ")[0]
    selected_row = result_df[result_df["代码"] == selected_code].iloc[0]

    stock_info = next(
        s for s in stocks
        if s["code"] == selected_code
    )

    fig = build_kline_chart(
        stock_info["secid"],
        f'{selected_row["代码"]} {selected_row["名称"]}｜AI分数 {selected_row["AI分数"]}'
    )

    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("该股K线暂时无法展示。")

    st.markdown("</div>", unsafe_allow_html=True)
