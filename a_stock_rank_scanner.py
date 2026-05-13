import re
import time
import requests
import pandas as pd
import numpy as np


print("开始扫描A股市场...")


def safe_float(value, default=0.0):
    try:
        if value is None or value == "-" or value == "":
            return default
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def fmt_price(value):
    return f"{safe_float(value):.2f}"


def headers():
    return {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*"
    }


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
        "fields": "f12,f14,f13"
    }

    try:
        r = requests.get(url, params=params, headers=headers(), timeout=15)
        js = r.json()
        rows = js.get("data", {}).get("diff", [])

        stocks = []

        for row in rows:
            code = str(row.get("f12", "")).strip()
            name = str(row.get("f14", "")).strip()
            market = str(row.get("f13", "")).strip()

            if not code or not name or not market:
                continue

            if not re.fullmatch(r"\d{6}", code):
                continue

            if name.startswith(("ST", "*ST", "退")):
                continue

            stocks.append({
                "code": code,
                "name": name,
                "market": market,
                "secid": f"{market}.{code}"
            })

        return stocks

    except Exception as e:
        print("获取股票池失败：", e)
        return []


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
        r = requests.get(url, params=params, headers=headers(), timeout=12)
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

        if df.empty:
            return pd.DataFrame()

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
    pct = safe_float(latest.get("pct", 0))

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
        "pct": pct,
        "turnover": turnover,
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

    if score_info["score"] < 85:
        return None

    return {
        "代码": code,
        "名称": name,
        "最新价": round(score_info["close"], 2),
        "近5日涨幅": round(score_info["pct"], 2),
        "AI分数": score_info["score"],
        "评级": score_info["level"],
        "操作": score_info["action"],
        "换手率": round(score_info["turnover"], 2),
        "趋势": score_info["trend_score"],
        "动能": score_info["momentum_score"],
        "资金": score_info["volume_score"],
        "风险": score_info["risk_score"],
        "消息": score_info["news_score"],
        "观察买点": f'{fmt_price(score_info["watch_low"])} - {fmt_price(score_info["watch_high"])}',
        "突破确认点": fmt_price(score_info["breakout"]),
        "风险止损线": fmt_price(score_info["stop_loss"]),
    }


stocks = get_a_stock_list()

print(f"获取股票池：{len(stocks)} 只")

results = []

for i, stock in enumerate(stocks, start=1):
    item = scan_one(stock)

    if item:
        results.append(item)
        print(f"入选：{item['代码']} {item['名称']} {item['AI分数']}")

    if i % 100 == 0:
        print(f"已扫描 {i}/{len(stocks)}，当前入选 {len(results)} 只")

    time.sleep(0.03)


result_df = pd.DataFrame(results)

if result_df.empty:
    result_df = pd.DataFrame(columns=[
        "代码", "名称", "最新价", "近5日涨幅", "AI分数", "评级", "操作",
        "换手率", "趋势", "动能", "资金", "风险", "消息",
        "观察买点", "突破确认点", "风险止损线"
    ])
else:
    result_df = result_df.sort_values(
        by=["AI分数", "近5日涨幅", "换手率"],
        ascending=[False, False, False]
    ).reset_index(drop=True)

result_df.to_csv(
    "a_stock_rank.csv",
    index=False,
    encoding="utf-8-sig"
)

print("扫描完成，已生成 a_stock_rank.csv")
print(result_df.head(20))
