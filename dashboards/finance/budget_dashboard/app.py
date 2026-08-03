import streamlit as st
from snowflake.snowpark import Session
import pandas as pd

try:
    import plotly.graph_objects as go
except ModuleNotFoundError:
    go = None

try:
    import altair as alt
except ModuleNotFoundError:
    alt = None

# ----------------------------
# Snowflake Connection
# ----------------------------
connection_parameters = {
    "account": "TTBOWQB-XD65735",
    "user": "UTKARSH2106001",
    "password": "UtkarshShri@2106",          # Replace with your password or use SSO later
    "warehouse": "WH_CRYPTO",
    "database": "ANALYTICS_DEV",
    "schema": "FINANCE",
    "role": "SYSADMIN"       # Use a role you already have
}

session = Session.builder.configs(connection_parameters).create()

st.set_page_config(
    page_title="Finance Budget Dashboard",
    layout="wide"
)

st.title("💰 Finance Budget Dashboard")

# ----------------------------
# Load Data
# ----------------------------
query = """
SELECT *
FROM BUDGET_FACT
"""

df = session.sql(query).to_pandas()

# ----------------------------
# KPIs
# ----------------------------
total_budget = df["PLANNED_BUDGET"].sum()
actual_spend = df["ACTUAL_SPEND"].sum()
variance = df["VARIANCE"].sum()

utilization = (actual_spend / total_budget) * 100

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Budget", f"{total_budget:,.0f}")

c2.metric("Actual Spend", f"{actual_spend:,.0f}")

c3.metric("Variance", f"{variance:,.0f}")

c4.metric("Budget Utilization", f"{utilization:.2f}%")

st.divider()

# ----------------------------
# Department Summary
# ----------------------------
dep = (
    df.groupby("DEPARTMENT")
    .agg(
        {
            "PLANNED_BUDGET": "sum",
            "ACTUAL_SPEND": "sum",
            "VARIANCE": "sum"
        }
    )
)

st.subheader("Budget vs Actual by Department")


def render_bar_chart(dataframe, colors, title=None):
    if go is not None:
        fig = go.Figure()

        for index, column in enumerate(dataframe.columns):
            fig.add_trace(
                go.Bar(
                    x=dataframe.index,
                    y=dataframe[column],
                    name=column,
                    marker_color=colors[index],
                )
            )

        fig.update_layout(
            template="plotly_white",
            barmode="group",
            title=title,
            xaxis_title="Department",
            yaxis_title="Amount",
            legend_title="Metric",
            margin=dict(l=20, r=20, t=50, b=20),
        )

        st.plotly_chart(fig, use_container_width=True)
        return

    if alt is not None:
        plot_df = dataframe.reset_index()

        if "Category" not in plot_df.columns:
            category_col = plot_df.columns[0]
            plot_df = plot_df.rename(columns={category_col: "Category"})

        melted = plot_df.melt(id_vars=["Category"], var_name="Metric", value_name="Amount")

        chart = (
            alt.Chart(melted)
            .mark_bar()
            .encode(
                x=alt.X("Category:N", title="Category"),
                y=alt.Y("Amount:Q", title="Amount"),
                color=alt.Color(
                    "Metric:N",
                    legend=alt.Legend(title="Metric"),
                    scale=alt.Scale(domain=list(dataframe.columns), range=colors),
                ),
            )
        )
        st.altair_chart(chart, use_container_width=True)
        return

    st.bar_chart(dataframe)


render_bar_chart(
    dep[["PLANNED_BUDGET", "ACTUAL_SPEND"]],
    colors=["#4C78A8", "#F58518"],
    title="Budget vs Actual by Department"
)

st.divider()

# ----------------------------
# Monthly Trend
# ----------------------------
df["BUDGET_DATE"] = pd.to_datetime(df["BUDGET_DATE"])

monthly = (
    df.groupby(df["BUDGET_DATE"].dt.to_period("M"))
    .agg(
        {
            "PLANNED_BUDGET": "sum",
            "ACTUAL_SPEND": "sum"
        }
    )
)

monthly.index = monthly.index.astype(str)

st.subheader("Monthly Budget Trend")

st.line_chart(monthly)

st.divider()

# ----------------------------
# Region Spend
# ----------------------------
region = (
    df.groupby("REGION")
    .agg(
        {
            "ACTUAL_SPEND": "sum"
        }
    )
)

st.subheader("Region Wise Spend")

render_bar_chart(
    region,
    colors=["#54A24B"],
    title="Region Wise Spend"
)

st.divider()

# ----------------------------
# Department Filter
# ----------------------------
department = st.selectbox(
    "Select Department",
    sorted(df["DEPARTMENT"].unique())
)

filtered = df[df["DEPARTMENT"] == department]

st.subheader(f"{department} Transactions")

st.dataframe(
    filtered,
    use_container_width=True,
    hide_index=True
)

session.close()