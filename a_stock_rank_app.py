import os
import pandas as pd
import streamlit as st
import plotly.express as px


st.set_page_config(
    page_title="A股AI高分榜",
    page_icon="📊",
    layout="wide"
)


# =========================
# UI 样式
# =========================
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
    max-width: 1450px;
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
    min-height: 122px;
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

.warn {
    background: linear-gradient(90deg, rgba(249,115,22,0.12), rgba(239,68,68,0.08));
    border: 1px solid rgba(249,115,22,0.22);
    border-radius: 16px;
    padding: 14px 16px;
    color: #9a3412;
    font-weight: 750;
    margin-bottom: 16px;
}

.stSlider label,
.stSelectbox label,
.stTextInput label {
    color: #334155 !important;
    font-weight: 850 !important;
}

div[data-baseweb="select"] > div {
    background: rgba(255,255,255,0.96) !important;
    color: #0f172a !important;
    border: 1px solid rgba(148,163,184,0.42) !important;
    border-radius: 14px !important;
}

.stTextInput input {
    background: rgba(255,255,255,0.96) !important;
    color: #0f172a !important;
    border: 1px solid rgba(148,163,184,0.42) !important;
    border-radius: 14px !important;
    font-weight: 750 !important;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span {
    color: #102033 !important;
}

a {
    color: #2563eb !important;
}

</style>
""",
    unsafe_allow_html=True
)


def metric_card(label, value, sub=""):
    st.markdown(
        f"""
<div class="metric-card">
    <div class="metric-label">{label}</div>
    <div class="metric-value">{value}</div>
    <div class="metric-sub">{sub}</div>
</div>
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


# =========================
# 页面头部
# =========================
st.markdown(
    """
<div class="hero">
    <div class="hero-title">📊 A股每日AI高分榜</div>
    <div class="hero-sub">后台遍历A股 · 前台秒开展示 · 支持自定义分数线 · 自动生成强势观察池</div>
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
        还没有找到 <b>a_stock_rank.csv</b>。<br>
        请先在 GitHub Actions 里运行 <b>Update A Stock Rank</b>，生成榜单文件。
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
    <div class="section-title">今日暂无扫描结果</div>
    <div class="warn">
        CSV 已生成，但没有任何股票数据。可能是扫描接口临时失败，建议重新运行 GitHub Actions。
    </div>
</div>
""",
        unsafe_allow_html=True
    )
    st.stop()


# =========================
# 数据清洗
# =========================
required_cols = ["代码", "名称", "AI分数"]

missing_cols = [col for col in required_cols if col not in df.columns]

if missing_cols:
    st.error(f"CSV 缺少必要字段：{missing_cols}")
    st.stop()


df["AI分数"] = pd.to_numeric(df["AI分数"], errors="coerce").fillna(0)

for col in ["近5日涨幅", "换手率", "最新价", "趋势", "动能", "资金", "风险", "消息"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)


scan_total = len(df)
max_score = int(df["AI分数"].max())
avg_score = float(df["AI分数"].mean())


# =========================
# 参数控制区
# =========================
left, right = st.columns([0.28, 0.72], gap="large")

with left:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">⚙️ 榜单筛选</div>', unsafe_allow_html=True)

    score_threshold = st.slider(
        "选择入榜分数线",
        min_value=50,
        max_value=100,
        value=85,
        step=1
    )

    sort_by = st.selectbox(
        "排序方式",
        ["AI分数", "近5日涨幅", "换手率", "趋势", "动能", "资金"],
        index=0
    )

    keyword = st.text_input(
        "搜索股票代码 / 名称",
        value="",
        placeholder="例如：中国长城 / 000066"
    )

    st.markdown(
        """
<div class="tip">
页面不会重新扫描市场，只读取后台生成的 CSV，所以打开速度更快、更稳定。<br><br>
调整分数线后，榜单会立即刷新。
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# 筛选逻辑
# =========================
filtered_df = df[df["AI分数"] >= score_threshold].copy()

if keyword.strip():
    kw = keyword.strip()
    filtered_df = filtered_df[
        filtered_df["代码"].astype(str).str.contains(kw, case=False, na=False)
        | filtered_df["名称"].astype(str).str.contains(kw, case=False, na=False)
    ]

if sort_by not in filtered_df.columns:
    sort_by = "AI分数"

if not filtered_df.empty:
    filtered_df = filtered_df.sort_values(
        by=[sort_by, "AI分数"],
        ascending=[False, False]
    ).reset_index(drop=True)

    filtered_df.insert(0, "排名", filtered_df.index + 1)


with right:
    # =========================
    # 扫描概览
    # =========================
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📌 今日扫描概览</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        metric_card("本次扫描股票数", scan_total, "保存到 CSV 的股票数量")

    with c2:
        metric_card("当前入选数量", len(filtered_df), f"AI分数 ≥ {score_threshold}")

    with c3:
        metric_card("最高分", max_score, "本次扫描最高AI分")

    with c4:
        metric_card("平均分", f"{avg_score:.1f}", "全部扫描股票平均分")

    st.markdown("</div>", unsafe_allow_html=True)

    # =========================
    # 高分榜
    # =========================
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🏆 今日AI高分榜</div>', unsafe_allow_html=True)

    if filtered_df.empty:
        st.markdown(
            f"""
<div class="warn">
当前分数线为 <b>{score_threshold}</b>，暂无符合条件的股票。<br>
可以把左侧分数线调低到 75 或 80，查看更大的观察池。
</div>
""",
            unsafe_allow_html=True
        )
    else:
        show_cols = [
            "排名", "代码", "名称", "最新价", "近5日涨幅", "AI分数",
            "评级", "操作", "换手率", "趋势", "动能", "资金", "风险", "消息",
            "观察买点", "突破确认点", "风险止损线"
        ]

        available_cols = [col for col in show_cols if col in filtered_df.columns]

        st.dataframe(
            filtered_df[available_cols],
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "下载当前筛选榜单 CSV",
            data=filtered_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"A股AI高分榜_{score_threshold}分以上.csv",
            mime="text/csv"
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # =========================
    # 分数分布
    # =========================
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📈 分数分布</div>', unsafe_allow_html=True)

    if filtered_df.empty:
        st.markdown(
            """
<div class="tip">
暂无可展示的分数分布。请调低分数线。
</div>
""",
            unsafe_allow_html=True
        )
    else:
        chart_df = filtered_df.head(30).copy()

        fig = px.bar(
            chart_df,
            x="名称",
            y="AI分数",
            text="AI分数",
            title=f"TOP {len(chart_df)} AI分数分布"
        )

        fig.update_layout(
            height=420,
            template="plotly_white",
            margin=dict(l=20, r=20, t=50, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(255,255,255,0.35)",
            xaxis_tickangle=-35
        )

        fig.update_traces(textposition="outside")

        st.plotly_chart(fig, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # =========================
    # 小白解读
    # =========================
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🧠 小白解读</div>', unsafe_allow_html=True)

    if filtered_df.empty:
        st.markdown(
            f"""
当前分数线为 **{score_threshold}**，没有股票入选。

这通常说明：

- 今日强势结构不明显；
- 分数线过高；
- 市场整体处于震荡或弱势状态；
- 可以调低到 **75分或80分** 查看观察池。
"""
        )
    else:
        top_rows = filtered_df.head(5)

        summary_lines = []
        for _, row in top_rows.iterrows():
            summary_lines.append(
                f"- **{row['名称']}（{row['代码']}）**：AI分数 **{int(row['AI分数'])}**，近5日涨幅 **{safe_float(row.get('近5日涨幅', 0)):.2f}%**。"
            )

        st.markdown(
            f"""
当前分数线为 **{score_threshold}**，本次共有 **{len(filtered_df)}** 只股票入选。

这批股票通常具备以下特征：

- 股价相对短期均线更强；
- MA5、MA10、MA20 趋势结构更好；
- 成交量相对近期均量有一定配合；
- 技术状态更适合加入观察池，而不是直接无脑买入。

### 今日前排个股

{chr(10).join(summary_lines)}

### 使用建议

这份榜单更适合作为 **选股观察池**：

1. 先看 AI分数和趋势/动能/资金分项；
2. 再用单股分析工具查看K线、买卖点和风险线；
3. 只在回踩企稳或放量突破时观察机会；
4. 如果跌破风险线，要优先控制风险。
"""
        )

    st.markdown("</div>", unsafe_allow_html=True)


st.caption("说明：本工具仅用于辅助观察，不构成投资建议。实际交易需结合风险承受能力、市场环境和交易纪律。")
