import os
import pandas as pd
import streamlit as st
import plotly.express as px

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
    max-width: 1400px;
    padding-top: 24px;
    padding-bottom: 36px;
}

h1, h2, h3, h4, p, span, li {
    color: #0f172a;
}

.hero {
    background: rgba(255,255,255,0.84);
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
    background: rgba(255,255,255,0.80);
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
    background: rgba(255,255,255,0.92);
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

.tip {
    background: linear-gradient(90deg, rgba(37,99,235,0.11), rgba(6,182,212,0.10));
    border: 1px solid rgba(37,99,235,0.16);
    border-radius: 16px;
    padding: 14px 16px;
    color: #1e3a8a;
    font-weight: 750;
    margin-bottom: 16px;
}

.rank-tag {
    display:inline-block;
    padding:4px 10px;
    border-radius:999px;
    background:rgba(239,68,68,0.12);
    color:#b91c1c;
    font-weight:850;
    font-size:12px;
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


st.markdown(
    """
<div class="hero">
    <div class="hero-title">📊 A股每日AI高分榜</div>
    <div class="hero-sub">后台遍历A股 · 前台秒开展示 · 自动筛选85分以上强势个股</div>
</div>
""",
    unsafe_allow_html=True
)


csv_path = "a_stock_rank.csv"

if not os.path.exists(csv_path):
    st.markdown(
        """
<div class="panel">
    <div class="section-title">⚠️ 暂未生成今日榜单</div>
    <div class="tip">
        还没有找到 a_stock_rank.csv。<br>
        下一步需要让扫描程序 a_stock_rank_scanner.py 先运行一次，生成榜单文件。
    </div>
</div>
""",
        unsafe_allow_html=True
    )

    st.stop()


df = pd.read_csv(csv_path)

if df.empty:
    st.markdown(
        """
<div class="panel">
    <div class="section-title">今日暂无高分股</div>
    <div class="tip">
        今日没有筛选到85分以上个股。可以等下一次扫描，或后续调整分数线。
    </div>
</div>
""",
        unsafe_allow_html=True
    )
    st.stop()


df = df.sort_values(by="AI分数", ascending=False).reset_index(drop=True)
df.insert(0, "排名", df.index + 1)

top_score = df["AI分数"].max()
avg_score = df["AI分数"].mean()
stock_count = len(df)


st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📌 今日榜单概览</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(
        f"""
<div class="metric-card">
    <div class="metric-label">入选个股</div>
    <div class="metric-value">{stock_count}</div>
    <div class="metric-sub">AI分数 ≥ 85</div>
</div>
""",
        unsafe_allow_html=True
    )

with c2:
    st.markdown(
        f"""
<div class="metric-card">
    <div class="metric-label">最高分</div>
    <div class="metric-value">{top_score:.0f}</div>
    <div class="metric-sub">今日最强评分</div>
</div>
""",
        unsafe_allow_html=True
    )

with c3:
    st.markdown(
        f"""
<div class="metric-card">
    <div class="metric-label">平均分</div>
    <div class="metric-value">{avg_score:.1f}</div>
    <div class="metric-sub">入选股票平均AI分</div>
</div>
""",
        unsafe_allow_html=True
    )

st.markdown("</div>", unsafe_allow_html=True)


st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🏆 今日AI高分榜</div>', unsafe_allow_html=True)

show_cols = [
    "排名",
    "代码",
    "名称",
    "最新价",
    "近5日涨幅",
    "AI分数"
]

available_cols = [col for col in show_cols if col in df.columns]

st.dataframe(
    df[available_cols],
    use_container_width=True,
    hide_index=True
)

st.download_button(
    "下载今日高分榜 CSV",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name="A股AI高分榜.csv",
    mime="text/csv"
)

st.markdown("</div>", unsafe_allow_html=True)


st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📈 分数分布</div>', unsafe_allow_html=True)

fig = px.bar(
    df.head(20),
    x="名称",
    y="AI分数",
    text="AI分数",
    title="TOP 20 AI分数分布"
)

fig.update_layout(
    height=420,
    template="plotly_white",
    margin=dict(l=20, r=20, t=50, b=40),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(255,255,255,0.35)"
)

fig.update_traces(textposition="outside")

st.plotly_chart(fig, use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)


st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🧠 小白解读</div>', unsafe_allow_html=True)

top_rows = df.head(5)

summary_lines = []
for _, row in top_rows.iterrows():
    summary_lines.append(
        f"- **{row['名称']}（{row['代码']}）**：AI分数 **{row['AI分数']}**，近5日涨幅 **{row['近5日涨幅']}%**。"
    )

st.markdown(
    f"""
今日系统筛选出 **{stock_count}** 只 85 分以上个股。

这些股票短线特征通常包括：

- 股价站上短期均线；
- MA5、MA10、MA20 呈现较好的趋势结构；
- 成交量相对近期均量有所放大；
- 近5日涨幅具备一定强度。

### 今日前排个股

{chr(10).join(summary_lines)}

### 使用建议

这份榜单不是直接买入清单，而是 **观察池**。

更适合用来做三件事：

1. 找到当天技术形态较强的股票；
2. 观察是否有回踩低吸机会；
3. 配合单股分析工具进一步查看K线、买卖点和风险线。
""")

st.markdown("</div>", unsafe_allow_html=True)


st.caption("说明：本工具仅用于辅助观察，不构成投资建议。实际交易需结合风险承受能力、市场环境和交易纪律。")
