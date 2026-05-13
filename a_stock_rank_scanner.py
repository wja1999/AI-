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

# 只保留正常A股
stock_list = stock_list[
    (~stock_list["代码"].astype(str).str.contains("BJ"))
]

# 前300只先测试
stock_list = stock_list.head(300)

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

        if df is None or df.empty or len(df) < 30:
            continue

        close = df["收盘"]

        ma5 = close.tail(5).mean()
        ma10 = close.tail(10).mean()
        ma20 = close.tail(20).mean()

        latest = close.iloc[-1]
        prev = close.iloc[-2]

        score = 0

        # 趋势
        if latest > ma5:
            score += 20

        if ma5 > ma10:
            score += 20

        if ma10 > ma20:
            score += 20

        # 涨幅
        pct = ((latest - prev) / prev) * 100

        if pct > 3:
            score += 15

        # 成交量
        vol = df["成交量"]
        if vol.iloc[-1] > vol.tail(5).mean():
            score += 15

        # 强势形态
        if latest >= close.tail(20).max() * 0.97:
            score += 10

        result.append({
            "代码": code,
            "名称": name,
            "AI评分": score,
            "最新价": round(latest, 2),
            "涨跌幅": round(pct, 2)
        })

        time.sleep(0.05)

    except Exception as e:
        print("错误:", e)
        continue

df_result = pd.DataFrame(result)

if not df_result.empty:
    df_result = df_result.sort_values(
        by="AI评分",
        ascending=False
    )

df_result.to_csv(
    "a_stock_rank.csv",
    index=False,
    encoding="utf-8-sig"
)

print("扫描完成")
print(df_result.head())
