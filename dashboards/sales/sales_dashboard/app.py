# Finance Budget Dashboard with filters, bar charts, line charts, and transaction tables
# Co-authored with CoCo
import streamlit as st
from snowflake.snowpark.context import get_active_session
import pandas as pd

try:
    import plotly.graph_objects as go
    import plotly.express as px
except ModuleNotFoundError:
    go = None
    px = None

try:
    import altair as alt
except ModuleNotFoundError:
    alt = None

session = get_active_session()

st.set_page_config(page_title="Finance Budget Dashboard", layout="wide")

st.title("Finance Budget Dashboard")

# ----------------------------
# Load Data
# ----------------------------
@st.cache_data(ttl=600)
def load_data():
    return session.sql("SELECT * FROM ANALYTICS_DEV.FINANCE.BUDGET_FACT").to_pandas()

df = load_data()
df["BUDGET_DATE"] = pd.to_datetime(df["BUDGET_DATE"])

# ----------------------------
# Sidebar Filters
# ----------------------------
st.sidebar.header("Filters")

departments = st.sidebar.multiselect(
    "Department",
    options=sorted(df["DEPARTMENT"].unique()),
    default=sorted(df["DEPARTMENT"].unique()),
)

regions = st.sidebar.multiselect(
    "Region",
    options=sorted(df["REGION"].unique()),
    default=sorted(df["REGION"].unique()),
)

projects = st.sidebar.multiselect(
    "Project",
    options=sorted(df["PROJECT"].unique()),
    default=sorted(df["PROJECT"].unique()),
)

statuses = st.sidebar.multiselect(
    "Status",
    options=sorted(df["STATUS"].unique()),
    default=sorted(df["STATUS"].unique()),
)

date_min = df["BUDGET_DATE"].min().date()
date_max = df["BUDGET_DATE"].max().date()
date_range = st.sidebar.date_input(
    "Date Range",
    value=(date_min, date_max),
    min_value=date_min,
    max_value=date_max,
)

# Apply filters
filtered = df[
    (df["DEPARTMENT"].isin(departments))
    & (df["REGION"].isin(regions))
    & (df["PROJECT"].isin(projects))
    & (df["STATUS"].isin(statuses))
]

if isinstance(date_range, tuple) and len(date_range) == 2:
    filtered = filtered[
        (filtered["BUDGET_DATE"].dt.date >= date_range[0])
        & (filtered["BUDGET_DATE"].dt.date <= date_range[1])
    ]

# ----------------------------
# KPI Metrics
# ----------------------------
total_budget = filtered["PLANNED_BUDGET"].sum()
actual_spend = filtered["ACTUAL_SPEND"].sum()
variance = filtered["VARIANCE"].sum()
utilization = (actual_spend / total_budget * 100) if total_budget > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Budget", f"${total_budget:,.0f}")
c2.metric("Actual Spend", f"${actual_spend:,.0f}")
c3.metric("Variance", f"${variance:,.0f}", delta=f"{variance:,.0f}", delta_color="inverse")
c4.metric("Budget Utilization", f"{utilization:.1f}%")

st.divider()

# ----------------------------
# Charts
# ----------------------------

def render_grouped_bar(data, x_col, y_cols, colors, title, x_title, y_title):
    if go is not None:
        fig = go.Figure()
        for i, col in enumerate(y_cols):
            fig.add_trace(go.Bar(
                x=data[x_col],
                y=data[col],
                name=col.replace("_", " ").title(),
                marker_color=colors[i],
            ))
        fig.update_layout(
            template="plotly_white",
            barmode="group",
            title=title,
            xaxis_title=x_title,
            yaxis_title=y_title,
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif alt is not None:
        melted = data.melt(id_vars=[x_col], value_vars=y_cols, var_name="Metric", value_name="Amount")
        chart = (
            alt.Chart(melted)
            .mark_bar()
            .encode(
                x=alt.X(f"{x_col}:N", title=x_title),
                y=alt.Y("Amount:Q", title=y_title),
                color=alt.Color("Metric:N", scale=alt.Scale(range=colors)),
                xOffset="Metric:N",
            )
            .properties(title=title)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(data.set_index(x_col)[y_cols])


def render_line_chart(data, x_col, y_cols, colors, title, x_title, y_title):
    if go is not None:
        fig = go.Figure()
        for i, col in enumerate(y_cols):
            fig.add_trace(go.Scatter(
                x=data[x_col],
                y=data[col],
                mode="lines+markers",
                name=col.replace("_", " ").title(),
                line=dict(color=colors[i], width=2),
            ))
        fig.update_layout(
            template="plotly_white",
            title=title,
            xaxis_title=x_title,
            yaxis_title=y_title,
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif alt is not None:
        melted = data.melt(id_vars=[x_col], value_vars=y_cols, var_name="Metric", value_name="Amount")
        chart = (
            alt.Chart(melted)
            .mark_line(point=True)
            .encode(
                x=alt.X(f"{x_col}:N", title=x_title),
                y=alt.Y("Amount:Q", title=y_title),
                color=alt.Color("Metric:N", scale=alt.Scale(range=colors)),
            )
            .properties(title=title)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.line_chart(data.set_index(x_col)[y_cols])


# Row 1: Department bar + Monthly trend line
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Budget vs Actual by Department")
    dept_agg = (
        filtered.groupby("DEPARTMENT", as_index=False)
        .agg(PLANNED_BUDGET=("PLANNED_BUDGET", "sum"), ACTUAL_SPEND=("ACTUAL_SPEND", "sum"))
    )
    render_grouped_bar(
        dept_agg, "DEPARTMENT",
        ["PLANNED_BUDGET", "ACTUAL_SPEND"],
        ["#4C78A8", "#F58518"],
        "", "Department", "Amount ($)"
    )

with col_right:
    st.subheader("Monthly Budget Trend")
    monthly_df = filtered.copy()
    monthly_df["MONTH"] = monthly_df["BUDGET_DATE"].dt.to_period("M").astype(str)
    monthly = (
        monthly_df.groupby("MONTH", as_index=False)
        .agg(PLANNED_BUDGET=("PLANNED_BUDGET", "sum"), ACTUAL_SPEND=("ACTUAL_SPEND", "sum"))
    )
    render_line_chart(
        monthly, "MONTH",
        ["PLANNED_BUDGET", "ACTUAL_SPEND"],
        ["#4C78A8", "#F58518"],
        "", "Month", "Amount ($)"
    )

st.divider()

# Row 2: Region spend + Project allocation
col_left2, col_right2 = st.columns(2)

with col_left2:
    st.subheader("Region-wise Spend")
    region_agg = (
        filtered.groupby("REGION", as_index=False)
        .agg(ACTUAL_SPEND=("ACTUAL_SPEND", "sum"))
        .sort_values("ACTUAL_SPEND", ascending=False)
    )
    if go is not None:
        fig = go.Figure(go.Bar(
            x=region_agg["ACTUAL_SPEND"],
            y=region_agg["REGION"],
            orientation="h",
            marker_color="#54A24B",
        ))
        fig.update_layout(
            template="plotly_white",
            xaxis_title="Actual Spend ($)",
            yaxis_title="Region",
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif alt is not None:
        chart = (
            alt.Chart(region_agg)
            .mark_bar(color="#54A24B")
            .encode(
                x=alt.X("ACTUAL_SPEND:Q", title="Actual Spend ($)"),
                y=alt.Y("REGION:N", sort="-x", title="Region"),
            )
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(region_agg.set_index("REGION"))

with col_right2:
    st.subheader("Project Budget Allocation")
    proj_agg = (
        filtered.groupby("PROJECT", as_index=False)
        .agg(PLANNED_BUDGET=("PLANNED_BUDGET", "sum"), ACTUAL_SPEND=("ACTUAL_SPEND", "sum"))
    )
    render_grouped_bar(
        proj_agg, "PROJECT",
        ["PLANNED_BUDGET", "ACTUAL_SPEND"],
        ["#72B7B2", "#E45756"],
        "", "Project", "Amount ($)"
    )

st.divider()

# ----------------------------
# Variance Trend (Line)
# ----------------------------
st.subheader("Monthly Variance Trend")
var_df = filtered.copy()
var_df["MONTH"] = var_df["BUDGET_DATE"].dt.to_period("M").astype(str)
variance_monthly = (
    var_df.groupby("MONTH", as_index=False)
    .agg(VARIANCE=("VARIANCE", "sum"))
)

if go is not None:
    fig = go.Figure(go.Scatter(
        x=variance_monthly["MONTH"],
        y=variance_monthly["VARIANCE"],
        mode="lines+markers",
        line=dict(color="#E45756", width=2),
        fill="tozeroy",
        fillcolor="rgba(228, 87, 86, 0.1)",
    ))
    fig.update_layout(
        template="plotly_white",
        xaxis_title="Month",
        yaxis_title="Variance ($)",
        margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)
elif alt is not None:
    chart = (
        alt.Chart(variance_monthly)
        .mark_area(opacity=0.3, color="#E45756")
        .encode(
            x=alt.X("MONTH:N", title="Month"),
            y=alt.Y("VARIANCE:Q", title="Variance ($)"),
        )
    ) + (
        alt.Chart(variance_monthly)
        .mark_line(color="#E45756", point=True)
        .encode(
            x="MONTH:N",
            y="VARIANCE:Q",
        )
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.line_chart(variance_monthly.set_index("MONTH"))

st.divider()

# ----------------------------
# Transactions Table
# ----------------------------
st.subheader("Transaction Details")

display_cols = ["TRANSACTION_ID", "BUDGET_DATE", "DEPARTMENT", "REGION", "PROJECT",
                "PLANNED_BUDGET", "ACTUAL_SPEND", "VARIANCE", "STATUS"]

st.dataframe(
    filtered[display_cols].sort_values("BUDGET_DATE", ascending=False),
    use_container_width=True,
    hide_index=True,
    column_config={
        "PLANNED_BUDGET": st.column_config.NumberColumn(format="$%d"),
        "ACTUAL_SPEND": st.column_config.NumberColumn(format="$%d"),
        "VARIANCE": st.column_config.NumberColumn(format="$%d"),
        "BUDGET_DATE": st.column_config.DateColumn(format="YYYY-MM-DD"),
    },
)

st.caption(f"Showing {len(filtered):,} of {len(df):,} transactions")