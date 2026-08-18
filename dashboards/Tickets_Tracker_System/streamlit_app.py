import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import os
from datetime import date, timedelta

st.set_page_config(page_title="Ticket Tracker", page_icon=":material/bug_report:", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))

# =============================================================================
# Demo Data
# =============================================================================


@st.cache_data(ttl=3600)
def generate_ticket_data() -> pd.DataFrame:
    np.random.seed(2024)
    n_tickets = 1200
    start = date.today() - timedelta(days=365)

    categories = ["Bug", "Feature Request", "Error", "Performance", "Security", "Documentation"]
    priorities = ["Critical", "High", "Medium", "Low"]
    statuses = ["Open", "In Progress", "In Review", "Resolved", "Closed"]
    teams = ["Backend", "Frontend", "DevOps", "QA", "Data Engineering", "Mobile"]
    reporters = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]

    tickets = []
    for i in range(n_tickets):
        created = start + timedelta(days=np.random.randint(0, 365))
        category = np.random.choice(categories, p=[0.30, 0.20, 0.20, 0.12, 0.08, 0.10])
        priority = np.random.choice(priorities, p=[0.10, 0.25, 0.40, 0.25])
        status = np.random.choice(statuses, p=[0.12, 0.18, 0.10, 0.35, 0.25])

        resolution_days = None
        if status in ("Resolved", "Closed"):
            resolution_days = int(np.random.exponential(5) + 1)

        tickets.append({
            "Ticket ID": f"TKT-{1000 + i}",
            "Created": created,
            "Category": category,
            "Priority": priority,
            "Status": status,
            "Team": np.random.choice(teams),
            "Reporter": np.random.choice(reporters),
            "Resolution Days": resolution_days,
        })

    return pd.DataFrame(tickets)


data = generate_ticket_data()
data["Created"] = pd.to_datetime(data["Created"])
data["Week"] = data["Created"].dt.to_period("W").dt.start_time
data["Month"] = data["Created"].dt.to_period("M").dt.start_time
data["Year"] = data["Created"].dt.year

# =============================================================================
# Sidebar Filters
# =============================================================================

with st.sidebar:
    st.header(":material/filter_list: Filters")

    time_view = st.radio("Time Granularity", ["Daily", "Weekly", "Monthly", "Yearly"], index=1)

    selected_categories = st.multiselect(
        "Category",
        options=data["Category"].unique().tolist(),
        default=data["Category"].unique().tolist(),
    )

    selected_priorities = st.multiselect(
        "Priority",
        options=["Critical", "High", "Medium", "Low"],
        default=["Critical", "High", "Medium", "Low"],
    )

    selected_teams = st.multiselect(
        "Team",
        options=data["Team"].unique().tolist(),
        default=data["Team"].unique().tolist(),
    )

    st.divider()
    if st.button(":material/restart_alt: Reset Filters", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# Apply filters
mask = (
    data["Category"].isin(selected_categories)
    & data["Priority"].isin(selected_priorities)
    & data["Team"].isin(selected_teams)
)
filtered = data[mask]

# =============================================================================
# Header
# =============================================================================

st.markdown("# :material/bug_report: Ticket Tracker Dashboard")
st.caption(f"Development issues, bugs & feature requests | **{len(filtered):,}** tickets | Last 12 months")

st.divider()

# =============================================================================
# KPIs
# =============================================================================

total_tickets = len(filtered)
open_tickets = len(filtered[filtered["Status"].isin(["Open", "In Progress", "In Review"])])
resolved_tickets = len(filtered[filtered["Status"].isin(["Resolved", "Closed"])])
critical_open = len(filtered[(filtered["Priority"] == "Critical") & (filtered["Status"].isin(["Open", "In Progress"]))])
avg_resolution = filtered["Resolution Days"].dropna().mean()

# Sparklines
daily_counts = filtered.groupby(filtered["Created"].dt.date).size().tolist()

with st.container(horizontal=True):
    st.metric(
        "Total Tickets",
        f"{total_tickets:,}",
        border=True,
        chart_data=daily_counts[-21:],
        chart_type="bar",
    )
    st.metric(
        "Open / In Progress",
        f"{open_tickets}",
        f"{open_tickets / max(total_tickets, 1) * 100:.0f}% of total",
        border=True,
    )
    st.metric(
        "Resolved / Closed",
        f"{resolved_tickets}",
        f"{resolved_tickets / max(total_tickets, 1) * 100:.0f}% resolution rate",
        border=True,
    )
    st.metric(
        "Critical (Open)",
        f"{critical_open}",
        delta_color="inverse",
        border=True,
    )
    st.metric(
        "Avg Resolution Time",
        f"{avg_resolution:.1f} days" if not np.isnan(avg_resolution) else "N/A",
        border=True,
    )

st.divider()

# =============================================================================
# Time aggregation helper
# =============================================================================


def aggregate_by_time(df: pd.DataFrame, granularity: str) -> pd.DataFrame:
    if granularity == "Daily":
        df = df.copy()
        df["Period"] = df["Created"].dt.date
    elif granularity == "Weekly":
        df = df.copy()
        df["Period"] = df["Week"]
    elif granularity == "Monthly":
        df = df.copy()
        df["Period"] = df["Month"]
    else:
        df = df.copy()
        df["Period"] = df["Year"]
    return df


filtered_time = aggregate_by_time(filtered, time_view)

# =============================================================================
# Row 1: Ticket Trend (Line) + Tickets by Category (Bar)
# =============================================================================

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.markdown(f"### :material/show_chart: Ticket Volume ({time_view})")

        trend = filtered_time.groupby("Period").size().reset_index(name="Tickets")
        trend["Period"] = pd.to_datetime(trend["Period"])

        line_chart = (
            alt.Chart(trend)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=alt.X("Period:T", title=None),
                y=alt.Y("Tickets:Q", title="Tickets Created"),
                tooltip=[
                    alt.Tooltip("Period:T", title="Period", format="%Y-%m-%d"),
                    alt.Tooltip("Tickets:Q"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(line_chart, use_container_width=True)

with col2:
    with st.container(border=True):
        st.markdown(f"### :material/bar_chart: Tickets by Category ({time_view})")

        cat_counts = filtered.groupby("Category").size().reset_index(name="Count").sort_values("Count", ascending=False)

        bar_chart = (
            alt.Chart(cat_counts)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("Category:N", sort="-y", title=None),
                y=alt.Y("Count:Q", title="Tickets"),
                color=alt.Color("Category:N", legend=None),
                tooltip=[
                    alt.Tooltip("Category:N"),
                    alt.Tooltip("Count:Q"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(bar_chart, use_container_width=True)

# =============================================================================
# Row 2: Priority Breakdown (Stacked Bar) + Status Distribution (Donut)
# =============================================================================

col3, col4 = st.columns(2)

with col3:
    with st.container(border=True):
        st.markdown(f"### :material/priority_high: Priority Breakdown ({time_view})")

        priority_time = filtered_time.groupby(["Period", "Priority"]).size().reset_index(name="Count")
        priority_time["Period"] = pd.to_datetime(priority_time["Period"])

        stacked_bar = (
            alt.Chart(priority_time)
            .mark_bar()
            .encode(
                x=alt.X("Period:T", title=None),
                y=alt.Y("Count:Q", title="Tickets", stack="zero"),
                color=alt.Color("Priority:N", title=None, scale=alt.Scale(
                    domain=["Critical", "High", "Medium", "Low"],
                    range=["#e03131", "#fd7e14", "#fcc419", "#51cf66"],
                ), legend=alt.Legend(orient="bottom")),
                tooltip=[
                    alt.Tooltip("Period:T", format="%Y-%m-%d"),
                    alt.Tooltip("Priority:N"),
                    alt.Tooltip("Count:Q"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(stacked_bar, use_container_width=True)

with col4:
    with st.container(border=True):
        st.markdown("### :material/pie_chart: Status Distribution")

        status_counts = filtered.groupby("Status").size().reset_index(name="Count")
        status_counts["Pct"] = (status_counts["Count"] / status_counts["Count"].sum() * 100).round(1)

        donut = (
            alt.Chart(status_counts)
            .mark_arc(innerRadius=55, outerRadius=115, cornerRadius=4)
            .encode(
                theta=alt.Theta("Count:Q"),
                color=alt.Color("Status:N", title=None, scale=alt.Scale(
                    domain=["Open", "In Progress", "In Review", "Resolved", "Closed"],
                    range=["#e03131", "#fd7e14", "#4dabf7", "#51cf66", "#868e96"],
                ), legend=alt.Legend(orient="bottom")),
                tooltip=[
                    alt.Tooltip("Status:N"),
                    alt.Tooltip("Count:Q"),
                    alt.Tooltip("Pct:Q", title="Share %", format=".1f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(donut, use_container_width=True)

# =============================================================================
# Row 3: Team Workload (Horizontal Bar) + Resolution Time by Priority (Box-like)
# =============================================================================

col5, col6 = st.columns(2)

with col5:
    with st.container(border=True):
        st.markdown("### :material/groups: Tickets by Team")

        team_status = filtered.groupby(["Team", "Status"]).size().reset_index(name="Count")

        team_bar = (
            alt.Chart(team_status)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                y=alt.Y("Team:N", title=None, sort="-x"),
                x=alt.X("Count:Q", title="Tickets", stack="zero"),
                color=alt.Color("Status:N", title=None, scale=alt.Scale(
                    domain=["Open", "In Progress", "In Review", "Resolved", "Closed"],
                    range=["#e03131", "#fd7e14", "#4dabf7", "#51cf66", "#868e96"],
                ), legend=alt.Legend(orient="bottom")),
                tooltip=[
                    alt.Tooltip("Team:N"),
                    alt.Tooltip("Status:N"),
                    alt.Tooltip("Count:Q"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(team_bar, use_container_width=True)

with col6:
    with st.container(border=True):
        st.markdown("### :material/timer: Resolution Time by Priority")

        resolved = filtered[filtered["Resolution Days"].notna()].copy()

        if len(resolved) > 0:
            box_chart = (
                alt.Chart(resolved)
                .mark_boxplot(extent="min-max")
                .encode(
                    x=alt.X("Priority:N", title=None, sort=["Critical", "High", "Medium", "Low"]),
                    y=alt.Y("Resolution Days:Q", title="Days to Resolve"),
                    color=alt.Color("Priority:N", legend=None, scale=alt.Scale(
                        domain=["Critical", "High", "Medium", "Low"],
                        range=["#e03131", "#fd7e14", "#fcc419", "#51cf66"],
                    )),
                )
                .properties(height=300)
            )
            st.altair_chart(box_chart, use_container_width=True)
        else:
            st.info("No resolved tickets in current filter.")

# =============================================================================
# Data Tables
# =============================================================================

with st.container(border=True):
    st.markdown("### :material/table_chart: Ticket Details")

    tab1, tab2, tab3 = st.tabs([
        ":material/bug_report: All Tickets",
        ":material/error: Open & Critical",
        ":material/analytics: Summary Stats",
    ])

    with tab1:
        st.dataframe(
            filtered[["Ticket ID", "Created", "Category", "Priority", "Status", "Team", "Reporter", "Resolution Days"]]
            .sort_values("Created", ascending=False),
            use_container_width=True,
            hide_index=True,
            height=350,
            column_config={
                "Created": st.column_config.DateColumn("Created", format="YYYY-MM-DD"),
                "Resolution Days": st.column_config.NumberColumn("Resolution (days)"),
            },
        )

    with tab2:
        critical_open_df = filtered[
            (filtered["Priority"].isin(["Critical", "High"]))
            & (filtered["Status"].isin(["Open", "In Progress"]))
        ].sort_values(["Priority", "Created"], ascending=[True, False])

        st.warning(f"**{len(critical_open_df)}** high/critical tickets still open")
        st.dataframe(
            critical_open_df[["Ticket ID", "Created", "Category", "Priority", "Status", "Team", "Reporter"]],
            use_container_width=True,
            hide_index=True,
            height=300,
            column_config={
                "Created": st.column_config.DateColumn("Created", format="YYYY-MM-DD"),
            },
        )

    with tab3:
        summary = filtered.groupby(["Category", "Priority"]).agg(
            Total=("Ticket ID", "count"),
            Open=("Status", lambda x: (x.isin(["Open", "In Progress"])).sum()),
            Avg_Resolution=("Resolution Days", "mean"),
        ).reset_index()
        summary["Avg_Resolution"] = summary["Avg_Resolution"].round(1)
        summary.columns = ["Category", "Priority", "Total", "Open", "Avg Resolution (days)"]

        st.dataframe(
            summary.sort_values(["Category", "Priority"]),
            use_container_width=True,
            hide_index=True,
            height=350,
        )
