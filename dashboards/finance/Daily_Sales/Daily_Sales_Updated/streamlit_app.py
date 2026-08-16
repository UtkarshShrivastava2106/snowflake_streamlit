import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import os
from datetime import date, timedelta

st.set_page_config(page_title="Daily Revenue Dashboard", page_icon=":material/trending_up:", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))

# =============================================================================
# Demo Data
# =============================================================================


@st.cache_data(ttl=3600)
def generate_revenue_data() -> pd.DataFrame:
    np.random.seed(101)
    days = 90
    dates = pd.date_range(end=date.today() - timedelta(days=1), periods=days, freq="D")

    revenue = []
    base = 5000
    for i, d in enumerate(dates):
        trend = base + i * 30
        seasonal = 1 + 0.2 * np.sin(2 * np.pi * d.dayofyear / 365)
        weekend = 1.25 if d.dayofweek >= 5 else 1.0
        noise = np.random.uniform(0.85, 1.15)
        rev = round(trend * seasonal * weekend * noise, 2)
        orders = int(rev / np.random.uniform(40, 70))
        revenue.append({
            "Date": d,
            "Revenue": rev,
            "Orders": orders,
            "Avg Order Value": round(rev / max(orders, 1), 2),
        })

    return pd.DataFrame(revenue)


data = generate_revenue_data()

# =============================================================================
# Header
# =============================================================================

st.markdown("# :material/trending_up: Daily Revenue Dashboard")
st.caption(f"Last 90 days | Updated through **{data['Date'].max().strftime('%b %d, %Y')}**")

st.divider()

# =============================================================================
# KPIs
# =============================================================================

total_rev = data["Revenue"].sum()
total_orders = data["Orders"].sum()
avg_order = data["Avg Order Value"].mean()
peak_day_rev = data.loc[data["Revenue"].idxmax()]

last_7 = data.tail(7)["Revenue"].sum()
prev_7 = data.iloc[-14:-7]["Revenue"].sum()
wow_change = ((last_7 - prev_7) / prev_7 * 100) if prev_7 > 0 else 0

rev_sparkline = data["Revenue"].tolist()[-14:]
orders_sparkline = data["Orders"].tolist()[-14:]

with st.container(horizontal=True):
    st.metric(
        "Total Revenue (90d)",
        f"${total_rev:,.0f}",
        f"{wow_change:+.1f}% WoW",
        border=True,
        chart_data=rev_sparkline,
        chart_type="line",
    )
    st.metric(
        "Total Orders",
        f"{total_orders:,}",
        f"~{total_orders // 90}/day avg",
        border=True,
        chart_data=orders_sparkline,
        chart_type="bar",
    )
    st.metric(
        "Avg Order Value",
        f"${avg_order:.2f}",
        border=True,
    )
    st.metric(
        "Peak Revenue Day",
        f"${peak_day_rev['Revenue']:,.0f}",
        peak_day_rev["Date"].strftime("%b %d"),
        border=True,
    )

st.divider()

# =============================================================================
# Line Chart — Daily Revenue Trend
# =============================================================================

with st.container(border=True):
    st.markdown("### :material/show_chart: Daily Revenue Trend")

    chart_data = data.copy()
    chart_data["7-Day Moving Avg"] = chart_data["Revenue"].rolling(7, min_periods=1).mean()

    melted = chart_data.melt(
        id_vars=["Date"],
        value_vars=["Revenue", "7-Day Moving Avg"],
        var_name="Series",
        value_name="Amount",
    )

    line_chart = (
        alt.Chart(melted)
        .mark_line()
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Amount:Q", title="Revenue ($)"),
            color=alt.Color("Series:N", title=None, legend=alt.Legend(orient="bottom")),
            strokeDash=alt.condition(
                alt.datum.Series == "7-Day Moving Avg",
                alt.value([5, 5]),
                alt.value([0]),
            ),
            tooltip=[
                alt.Tooltip("Date:T", format="%Y-%m-%d"),
                alt.Tooltip("Series:N"),
                alt.Tooltip("Amount:Q", title="Revenue", format="$,.0f"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(line_chart, use_container_width=True)

# =============================================================================
# Bar Chart — Revenue by Day of Week
# =============================================================================

with st.container(border=True):
    st.markdown("### :material/bar_chart: Revenue by Day of Week")

    data["Day"] = data["Date"].dt.day_name()
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_day = data.groupby("Day")["Revenue"].mean().reindex(day_order).reset_index()
    by_day.columns = ["Day", "Avg Revenue"]

    bar_chart = (
        alt.Chart(by_day)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Day:N", sort=day_order, title=None),
            y=alt.Y("Avg Revenue:Q", title="Avg Daily Revenue ($)"),
            color=alt.condition(
                alt.FieldOneOfPredicate(field="Day", oneOf=["Saturday", "Sunday"]),
                alt.value("#ff6b6b"),
                alt.value("#4dabf7"),
            ),
            tooltip=[
                alt.Tooltip("Day:N"),
                alt.Tooltip("Avg Revenue:Q", format="$,.0f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(bar_chart, use_container_width=True)
    st.caption(":red[Red] = Weekend | :blue[Blue] = Weekday")

# =============================================================================
# Data Table
# =============================================================================

with st.container(border=True):
    st.markdown("### :material/table_chart: Revenue Data")

    display_data = data[["Date", "Revenue", "Orders", "Avg Order Value"]].sort_values("Date", ascending=False)

    st.dataframe(
        display_data,
        use_container_width=True,
        hide_index=True,
        height=400,
        column_config={
            "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "Revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
            "Avg Order Value": st.column_config.NumberColumn("Avg Order Value", format="$%.2f"),
        },
    )
