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


def calc_score(df):
    if df.empty or len(df) < 30:
        return None

    close = df["close"]
    volume = df["volume"]

    latest = safe_float(close.iloc[-1])
    prev = safe_float(close.iloc[-2])

    ma5 = safe_float(close.tail(5).mean())
    ma10 = safe_float(close.tail(10).mean())
    ma20 = safe_float(close.tail(20).mean())
    ma60 = safe_float(close.tail(60).mean())

    vol_latest = safe_float(volume.iloc[-1])
    vol_ma5 = safe_float(volume.tail(5).mean())

    score = 0

    # 趋势结构 45分
    if latest > ma5:
        score += 15

    if ma5 > ma10:
        score += 15

    if ma10 > ma20:
        score += 15

    # 中期趋势 10分
    if latest > ma60:
        score += 10

    # 当日表现 15分
    pct = 0
    if prev > 0:
        pct = ((latest - prev) / prev) * 100

    if pct > 0:
        score += 8

    if pct > 3:
        score += 7

    # 成交量 15分
    if vol_ma5 > 0 and vol_latest > vol_ma5 * 0.8:
        score += 8

    if vol_ma5 > 0 and vol_latest > vol_ma5 * 1.2:
        score += 7

    # 强势形态 15分
    high20 = safe_float(close.tail(20).max())

    if high20 > 0 and latest >= high20 * 0.95:
        score += 15

    score = min(100, int(score))

    return {
        "AI分数": score,
        "最新价": round(latest, 2),
        "近5日涨幅": round(pct, 2)
    }


stocks = get_a_stock_list()

print(f"获取股票池：{len(stocks)} 只")

results = []

for i, stock in enumerate(stocks, start=1):
    code = stock["code"]
    name = stock["name"]
    secid = stock["secid"]

    df = get_kline(secid, limit=120)

    score_info = calc_score(df)

    if score_info:
        results.append({
            "代码": code,
            "名称": name,
            "最新价": score_info["最新价"],
            "近5日涨幅": score_info["近5日涨幅"],
            "AI分数": score_info["AI分数"]
        })

    if i % 100 == 0:
        print(f"已扫描 {i}/{len(stocks)}，当前有效评分 {len(results)} 只")

    time.sleep(0.02)


df_result = pd.DataFrame(results)

if df_result.empty:
    df_result = pd.DataFrame(columns=[
        "代码",
        "名称",
        "最新价",
        "近5日涨幅",
        "AI分数"
    ])
else:
    df_result = df_result.sort_values(
        by=["AI分数", "近5日涨幅"],
        ascending=[False, False]
    ).reset_index(drop=True)

df_result.to_csv(
    "a_stock_rank.csv",
    index=False,
    encoding="utf-8-sig"
)

print("扫描完成，已生成 a_stock_rank.csv")
print(f"有效评分股票数：{len(df_result)}")
print(df_result.head(30))
