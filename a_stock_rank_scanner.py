import akshare as ak
import pandas as pd
import time

result = []

print("开始获取A股列表...")

try:
    stock_list = ak.stock_zh_a_spot_em()
except Exception as e:
    print("获取股票列表失败:", e)
    exit()

print(f"获取到 {len(stock_list)} 只股票")

# 去掉北交所
stock_list = stock_list[
    (~stock_list["代码"].astype(str).str.contains("BJ"))
]

# 扫描1000只股票（稳定版）
stock_list = stock_list.head(1000)

for idx, row in stock_list.iterrows():

    try:
        code = row["代码"]
        name = row["名称"]

        print(f"扫描 {code} {name}")

        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            adjust="qfq"
        )

        # 数据不足跳过
        if df is None or df.empty or len(df) < 30:
            continue

        close = df["收盘"]

        ma5 = close.tail(5).mean()
        ma10 = close.tail(10).mean()
        ma20 = close.tail(20).mean()

        latest = close.iloc[-1]
        prev = close.iloc[-2]

        score = 0

        # =====================
        # 趋势评分
        # =====================
        if latest > ma5:
            score += 15

        if ma5 > ma10:
            score += 15

        if ma10 > ma20:
            score += 15

        # =====================
        # 涨幅评分
        # =====================
        pct = ((latest - prev) / prev) * 100

        if pct > 0:
            score += 10

        if pct > 3:
            score += 10

        # =====================
        # 成交量评分
        # =====================
        vol = df["成交量"]

        if vol.iloc[-1] > vol.tail(5).mean() * 0.8:
            score += 15

        # =====================
        # 强势形态评分
        # =====================
        if latest >= close.tail(20).max() * 0.95:
            score += 20

        result.append({
            "代码": code,
            "名称": name,
            "AI评分": score,
            "最新价": round(latest, 2),
            "涨跌幅": round(pct, 2)
        })

        time.sleep(0.03)

    except Exception as e:
        print("错误:", e)
        continue

# =====================
# 输出CSV
# =====================
df_result = pd.DataFrame(result)

if not df_result.empty:

    df_result = df_result.sort_values(
        by="AI评分",
        ascending=False
    )

    # 只保留高分股
    df_result = df_result[df_result["AI评分"] >= 70]

df_result.to_csv(
    "a_stock_rank.csv",
    index=False,
    encoding="utf-8-sig"
)

print("扫描完成")
print(df_result.head())
