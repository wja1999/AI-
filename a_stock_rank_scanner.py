import akshare as ak
import yfinance as yf
import pandas as pd
import time

print("开始扫描A股市场...")

# =========================
# 获取A股列表
# =========================
stock_df = ak.stock_info_a_code_name()

# 去掉北交所
stock_df = stock_df[
    ~stock_df["code"].str.startswith(("4", "8"))
]

# =========================
# 转换代码格式
# =========================
def convert_ticker(code):
    if code.startswith("6"):
        return code + ".SS"
    else:
        return code + ".SZ"

stock_df["ticker"] = stock_df["code"].apply(convert_ticker)

# =========================
# AI评分逻辑
# =========================
results = []

for index, row in stock_df.iterrows():

    code = row["code"]
    name = row["name"]
    ticker = row["ticker"]

    try:

        data = yf.download(
            ticker,
            period="3mo",
            progress=False,
            auto_adjust=True
        )

        if data is None or data.empty:
            continue

        if len(data) < 30:
            continue

        close = data["Close"]
        volume = data["Volume"]

        latest_price = float(close.iloc[-1])

        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]

        latest_volume = volume.iloc[-1]
        volume_ma5 = volume.rolling(5).mean().iloc[-1]

        score = 0

        # =========================
        # 趋势评分
        # =========================
        if latest_price > ma5:
            score += 20

        if ma5 > ma10:
            score += 20

        if ma10 > ma20:
            score += 20

        # =========================
        # 放量评分
        # =========================
        if latest_volume > volume_ma5:
            score += 20

        # =========================
        # 近期涨幅评分
        # =========================
        pct = (
            (close.iloc[-1] - close.iloc[-5])
            / close.iloc[-5]
        ) * 100

        if pct > 5:
            score += 20

        # =========================
        # 只保留85分以上
        # =========================
        if score >= 85:

            results.append({
                "代码": code,
                "名称": name,
                "最新价": round(latest_price, 2),
                "近5日涨幅": round(pct, 2),
                "AI分数": score
            })

            print(f"发现高分股: {code} {name} {score}")

        time.sleep(0.05)

    except Exception as e:
        print(f"{code} 扫描失败")
        continue

# =========================
# 保存排行榜
# =========================
result_df = pd.DataFrame(results)

result_df = result_df.sort_values(
    by="AI分数",
    ascending=False
)

result_df.to_csv(
    "a_stock_rank.csv",
    index=False,
    encoding="utf-8-sig"
)

print("扫描完成")
print(result_df.head(20))
