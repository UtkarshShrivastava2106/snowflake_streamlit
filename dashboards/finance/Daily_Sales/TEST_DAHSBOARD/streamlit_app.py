import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import os
from datetime import date, timedelta

st.set_page_config(
    page_title="Daily Sales Dashboard",
    page_icon=":material/point_of_sale:",
    layout="wide",
)

# =============================================================================
# Snowflake Connection
# =============================================================================

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))

# =============================================================================
# Dummy Data Generation
# =============================================================================


@st.cache_data(ttl=3600, show_spinner="Generating sales data...")
def generate_sales_data() -> pd.DataFrame:
    np.random.seed(42)
    days = 365
    dates = pd.date_range(end=date.today() - timedelta(days=1), periods=days, freq="D")

    categories = ["Electronics", "Clothing", "Food & Beverages", "Home & Garden", "Sports"]
    regions = ["North", "South", "East", "West"]

    rows = []
    for d in dates:
        for cat in categories:
            for reg in regions:
                base = {"Electronics": 1200, "Clothing": 800, "Food & Beverages": 600, "Home & Garden": 500, "Sports": 400}[cat]
                seasonal = 1 + 0.3 * np.sin(2 * np.pi * d.dayofyear / 365)
                weekend_boost = 1.3 if d.dayofweek >= 5 else 1.0
                noise = np.random.uniform(0.7, 1.3)
                revenue = round(base * seasonal * weekend_boost * noise, 2)
                orders = int(revenue / np.random.uniform(30, 80))
                rows.append({
                    "date": d,
                    "category": cat,
                    "region": reg,
                    "revenue": revenue,
                    "orders": orders,
                    "avg_order_value": round(revenue / max(orders, 1), 2),
                })

    return pd.DataFrame(rows)


data = generate_sales_data()

# =============================================================================
# Sidebar Filters
# =============================================================================

with st.sidebar:
    st.header(":material/filter_list: Filters")

    date_range = st.date_input(
        "Date Range",
        value=(data["date"].max() - timedelta(days=30), data["date"].max()),
        min_value=data["date"].min().date(),
        max_value=data["date"].max().date(),
    )

    selected_categories = st.multiselect(
        "Categories",
        options=data["category"].unique().tolist(),
        default=data["category"].unique().tolist(),
    )

    selected_regions = st.multiselect(
        "Regions",
        options=data["region"].unique().tolist(),
        default=data["region"].unique().tolist(),
    )

    st.divider()
    if st.button(":material/restart_alt: Reset Filters", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# Apply filters
mask = (
    (data["date"] >= pd.Timestamp(date_range[0]))
    & (data["date"] <= pd.Timestamp(date_range[1]))
    & (data["category"].isin(selected_categories))
    & (data["region"].isin(selected_regions))
)
filtered = data[mask]

# =============================================================================
# Page Header
# =============================================================================

st.markdown("# :material/point_of_sale: Daily Sales Dashboard")
st.caption(f"Showing data from **{date_range[0]}** to **{date_range[1]}** | {len(filtered):,} records")

# =============================================================================
# KPI Row
# =============================================================================

total_revenue = filtered["revenue"].sum()
total_orders = filtered["orders"].sum()
avg_order_val = filtered["avg_order_value"].mean()
daily_avg_revenue = filtered.groupby("date")["revenue"].sum().mean()

# Sparkline data
daily_rev = filtered.groupby("date")["revenue"].sum().tolist()
daily_ord = filtered.groupby("date")["orders"].sum().tolist()

with st.container(horizontal=True):
    st.metric(
        "Total Revenue",
        f"${total_revenue:,.0f}",
        f"Daily avg: ${daily_avg_revenue:,.0f}",
        border=True,
        chart_data=daily_rev[-14:],
        chart_type="line",
    )
    st.metric(
        "Total Orders",
        f"{total_orders:,}",
        f"{total_orders // max(len(set(filtered['date'])), 1)} / day",
        border=True,
        chart_data=daily_ord[-14:],
        chart_type="bar",
    )
    st.metric(
        "Avg Order Value",
        f"${avg_order_val:.2f}",
        border=True,
    )
    st.metric(
        "Categories Active",
        f"{filtered['category'].nunique()}",
        f"across {filtered['region'].nunique()} regions",
        border=True,
    )

# =============================================================================
# Row 1: Revenue Trend (Line) + Revenue by Category (Bar)
# =============================================================================

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.markdown("**Revenue Trend (Line Chart)**")
        daily_revenue = filtered.groupby("date")["revenue"].sum().reset_index()
        daily_revenue["7d_ma"] = daily_revenue["revenue"].rolling(7, min_periods=1).mean()

        melted = daily_revenue.melt(
            id_vars=["date"],
            value_vars=["revenue", "7d_ma"],
            var_name="series",
            value_name="value",
        )
        melted["series"] = melted["series"].map({"revenue": "Daily Revenue", "7d_ma": "7-Day Moving Avg"})

        line_chart = (
            alt.Chart(melted)
            .mark_line()
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("value:Q", title="Revenue ($)"),
                color=alt.Color("series:N", title=None, legend=alt.Legend(orient="bottom")),
                strokeDash=alt.condition(
                    alt.datum.series == "7-Day Moving Avg",
                    alt.value([5, 5]),
                    alt.value([0]),
                ),
                tooltip=[
                    alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"),
                    alt.Tooltip("series:N", title="Series"),
                    alt.Tooltip("value:Q", title="Revenue", format="$,.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(line_chart, use_container_width=True)

with col2:
    with st.container(border=True):
        st.markdown("**Revenue by Category (Bar Chart)**")
        cat_revenue = filtered.groupby("category")["revenue"].sum().reset_index().sort_values("revenue", ascending=False)

        bar_chart = (
            alt.Chart(cat_revenue)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("category:N", title=None, sort="-y"),
                y=alt.Y("revenue:Q", title="Revenue ($)"),
                color=alt.Color("category:N", title=None, legend=None),
                tooltip=[
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(bar_chart, use_container_width=True)

# =============================================================================
# Row 2: Area Chart (Stacked by Region) + Heatmap (Category x Region)
# =============================================================================

col3, col4 = st.columns(2)

with col3:
    with st.container(border=True):
        st.markdown("**Revenue by Region (Stacked Area)**")
        region_daily = filtered.groupby(["date", "region"])["revenue"].sum().reset_index()

        area_chart = (
            alt.Chart(region_daily)
            .mark_area(opacity=0.7, line=True)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("revenue:Q", title="Revenue ($)", stack="zero"),
                color=alt.Color("region:N", title=None, legend=alt.Legend(orient="bottom")),
                tooltip=[
                    alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"),
                    alt.Tooltip("region:N", title="Region"),
                    alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(area_chart, use_container_width=True)

with col4:
    with st.container(border=True):
        st.markdown("**Sales Heatmap (Category x Region)**")
        heatmap_data = filtered.groupby(["category", "region"])["revenue"].sum().reset_index()

        heatmap = (
            alt.Chart(heatmap_data)
            .mark_rect(cornerRadius=4)
            .encode(
                x=alt.X("region:N", title=None),
                y=alt.Y("category:N", title=None),
                color=alt.Color("revenue:Q", title="Revenue", scale=alt.Scale(scheme="blues")),
                tooltip=[
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("region:N", title="Region"),
                    alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(heatmap, use_container_width=True)

# =============================================================================
# Row 3: Scatter Plot + Donut Chart
# =============================================================================

col5, col6 = st.columns(2)

with col5:
    with st.container(border=True):
        st.markdown("**Orders vs Revenue (Scatter Plot)**")
        scatter_data = filtered.groupby(["date", "category"]).agg(
            revenue=("revenue", "sum"),
            orders=("orders", "sum"),
        ).reset_index()

        scatter = (
            alt.Chart(scatter_data)
            .mark_circle(opacity=0.6)
            .encode(
                x=alt.X("orders:Q", title="Orders"),
                y=alt.Y("revenue:Q", title="Revenue ($)"),
                color=alt.Color("category:N", title=None, legend=alt.Legend(orient="bottom")),
                size=alt.Size("revenue:Q", legend=None, scale=alt.Scale(range=[30, 200])),
                tooltip=[
                    alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"),
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("orders:Q", title="Orders"),
                    alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(scatter, use_container_width=True)

with col6:
    with st.container(border=True):
        st.markdown("**Revenue Share (Donut Chart)**")
        donut_data = filtered.groupby("category")["revenue"].sum().reset_index()
        donut_data["percentage"] = (donut_data["revenue"] / donut_data["revenue"].sum() * 100).round(1)

        donut = (
            alt.Chart(donut_data)
            .mark_arc(innerRadius=60, outerRadius=120, cornerRadius=4)
            .encode(
                theta=alt.Theta("revenue:Q"),
                color=alt.Color("category:N", title=None, legend=alt.Legend(orient="bottom")),
                tooltip=[
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                    alt.Tooltip("percentage:Q", title="Share %", format=".1f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(donut, use_container_width=True)

# =============================================================================
# Row 4: Data Table
# =============================================================================

with st.container(border=True):
    st.markdown("**Detailed Sales Data**")

    tab1, tab2 = st.tabs([":material/calendar_view_day: Daily Summary", ":material/table: Raw Data"])

    with tab1:
        daily_summary = (
            filtered.groupby("date")
            .agg(revenue=("revenue", "sum"), orders=("orders", "sum"), avg_order_value=("avg_order_value", "mean"))
            .reset_index()
            .sort_values("date", ascending=False)
        )
        daily_summary.columns = ["Date", "Revenue", "Orders", "Avg Order Value"]
        st.dataframe(
            daily_summary,
            use_container_width=True,
            hide_index=True,
            height=300,
            column_config={
                "Revenue": st.column_config.NumberColumn(format="$%.2f"),
                "Avg Order Value": st.column_config.NumberColumn(format="$%.2f"),
            },
        )

    with tab2:
        st.dataframe(
            filtered.sort_values("date", ascending=False),
            use_container_width=True,
            hide_index=True,
            height=300,
            column_config={
                "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                "avg_order_value": st.column_config.NumberColumn("Avg Order Value", format="$%.2f"),
            },
        )
