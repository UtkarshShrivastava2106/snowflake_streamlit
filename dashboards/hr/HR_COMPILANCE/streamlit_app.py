import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import os
from datetime import date, timedelta

st.set_page_config(page_title="HR Compliance Dashboard", page_icon=":material/verified_user:", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))

# =============================================================================
# Demo Data
# =============================================================================


@st.cache_data(ttl=3600)
def generate_compliance_data():
    np.random.seed(77)

    departments = ["Engineering", "Sales", "Marketing", "Finance", "Operations", "Legal", "HR"]
    training_modules = [
        "Anti-Harassment", "Data Privacy (GDPR)", "Workplace Safety",
        "Code of Conduct", "Cybersecurity Awareness", "Diversity & Inclusion",
    ]

    # Employee compliance records
    employees = []
    emp_id = 1000
    for dept in departments:
        n = np.random.randint(20, 50)
        for _ in range(n):
            emp_id += 1
            hire_date = date.today() - timedelta(days=np.random.randint(30, 1500))
            employees.append({
                "Employee ID": f"EMP-{emp_id}",
                "Department": dept,
                "Hire Date": hire_date,
                "Background Check": np.random.choice(["Completed", "Completed", "Completed", "Pending"], p=[0.7, 0.1, 0.1, 0.1]),
                "I-9 Verified": np.random.choice([True, True, True, False], p=[0.85, 0.05, 0.05, 0.05]),
                "Policy Acknowledged": np.random.choice([True, True, True, False], p=[0.9, 0.03, 0.03, 0.04]),
            })

    emp_df = pd.DataFrame(employees)

    # Training completion
    training_records = []
    for _, emp in emp_df.iterrows():
        for module in training_modules:
            completed = np.random.random() < 0.78
            due_date = date.today() - timedelta(days=np.random.randint(-60, 90))
            training_records.append({
                "Employee ID": emp["Employee ID"],
                "Department": emp["Department"],
                "Module": module,
                "Status": "Completed" if completed else ("Overdue" if due_date < date.today() else "Pending"),
                "Due Date": due_date,
                "Completion Date": due_date - timedelta(days=np.random.randint(1, 30)) if completed else None,
            })

    training_df = pd.DataFrame(training_records)

    # Incidents
    incidents = []
    for month_offset in range(12):
        month_date = date.today().replace(day=1) - timedelta(days=30 * month_offset)
        n_incidents = np.random.poisson(3)
        for _ in range(n_incidents):
            incidents.append({
                "Date": month_date + timedelta(days=np.random.randint(0, 28)),
                "Department": np.random.choice(departments),
                "Type": np.random.choice(["Policy Violation", "Safety Incident", "Harassment Complaint", "Data Breach Attempt", "Ethics Report"]),
                "Severity": np.random.choice(["Low", "Medium", "High"], p=[0.5, 0.35, 0.15]),
                "Status": np.random.choice(["Resolved", "Under Review", "Escalated"], p=[0.6, 0.25, 0.15]),
            })

    incidents_df = pd.DataFrame(incidents)

    return emp_df, training_df, incidents_df


emp_df, training_df, incidents_df = generate_compliance_data()

# =============================================================================
# Sidebar
# =============================================================================

with st.sidebar:
    st.header(":material/filter_list: Filters")

    selected_depts = st.multiselect(
        "Departments",
        options=emp_df["Department"].unique().tolist(),
        default=emp_df["Department"].unique().tolist(),
    )

    st.divider()
    st.markdown("**Quick Links**")
    st.markdown("""
    - :material/description: Policy Documents
    - :material/school: Training Portal
    - :material/report: Report an Issue
    """)

# Apply filter
emp_filtered = emp_df[emp_df["Department"].isin(selected_depts)]
training_filtered = training_df[training_df["Department"].isin(selected_depts)]
incidents_filtered = incidents_df[incidents_df["Department"].isin(selected_depts)]

# =============================================================================
# Header
# =============================================================================

st.markdown("# :material/verified_user: HR Compliance Dashboard")
st.caption(f"Organization-wide compliance status | **{len(emp_filtered)}** employees across **{len(selected_depts)}** departments")

st.divider()

# =============================================================================
# KPIs
# =============================================================================

total_emp = len(emp_filtered)
bg_check_rate = (emp_filtered["Background Check"] == "Completed").mean() * 100
i9_rate = emp_filtered["I-9 Verified"].mean() * 100
policy_ack_rate = emp_filtered["Policy Acknowledged"].mean() * 100
training_completion = (training_filtered["Status"] == "Completed").mean() * 100
overdue_trainings = (training_filtered["Status"] == "Overdue").sum()
open_incidents = len(incidents_filtered[incidents_filtered["Status"] != "Resolved"])

with st.container(horizontal=True):
    st.metric("Overall Compliance", f"{(bg_check_rate + i9_rate + policy_ack_rate + training_completion) / 4:.1f}%", border=True)
    st.metric("Training Completion", f"{training_completion:.1f}%", f"{overdue_trainings} overdue", delta_color="inverse", border=True)
    st.metric("Background Checks", f"{bg_check_rate:.1f}%", border=True)
    st.metric("Open Incidents", f"{open_incidents}", delta_color="off", border=True)

st.divider()

# =============================================================================
# Row 1: Training Completion by Module (Bar) + Compliance by Department (Bar)
# =============================================================================

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.markdown("### :material/school: Training Completion by Module")

        module_stats = training_filtered.groupby("Module")["Status"].apply(
            lambda x: (x == "Completed").mean() * 100
        ).reset_index()
        module_stats.columns = ["Module", "Completion %"]
        module_stats = module_stats.sort_values("Completion %", ascending=False)

        bar_chart = (
            alt.Chart(module_stats)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("Completion %:Q", title="Completion Rate (%)", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("Module:N", sort="-x", title=None),
                color=alt.condition(
                    alt.datum["Completion %"] >= 80,
                    alt.value("#51cf66"),
                    alt.value("#ff6b6b"),
                ),
                tooltip=[
                    alt.Tooltip("Module:N"),
                    alt.Tooltip("Completion %:Q", format=".1f"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(bar_chart, use_container_width=True)
        st.caption(":green[Green] = 80%+ compliant | :red[Red] = Below threshold")

with col2:
    with st.container(border=True):
        st.markdown("### :material/apartment: Compliance by Department")

        dept_compliance = emp_filtered.groupby("Department").apply(
            lambda g: pd.Series({
                "Background Check": (g["Background Check"] == "Completed").mean() * 100,
                "I-9 Verified": g["I-9 Verified"].mean() * 100,
                "Policy Acknowledged": g["Policy Acknowledged"].mean() * 100,
            })
        ).reset_index()

        dept_melted = dept_compliance.melt(id_vars=["Department"], var_name="Metric", value_name="Rate (%)")

        grouped_bar = (
            alt.Chart(dept_melted)
            .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("Department:N", title=None),
                y=alt.Y("Rate (%):Q", title="Compliance Rate (%)"),
                color=alt.Color("Metric:N", title=None, legend=alt.Legend(orient="bottom")),
                xOffset="Metric:N",
                tooltip=[
                    alt.Tooltip("Department:N"),
                    alt.Tooltip("Metric:N"),
                    alt.Tooltip("Rate (%):Q", format=".1f"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(grouped_bar, use_container_width=True)

# =============================================================================
# Row 2: Incidents Over Time (Line) + Incident Severity (Donut)
# =============================================================================

col3, col4 = st.columns(2)

with col3:
    with st.container(border=True):
        st.markdown("### :material/warning: Incidents Over Time")

        incidents_monthly = incidents_filtered.copy()
        incidents_monthly["Month"] = pd.to_datetime(incidents_monthly["Date"]).dt.to_period("M").dt.to_timestamp()
        monthly_counts = incidents_monthly.groupby(["Month", "Severity"]).size().reset_index(name="Count")

        line_chart = (
            alt.Chart(monthly_counts)
            .mark_line(point=True)
            .encode(
                x=alt.X("Month:T", title=None),
                y=alt.Y("Count:Q", title="Incidents"),
                color=alt.Color("Severity:N", title=None, scale=alt.Scale(
                    domain=["Low", "Medium", "High"],
                    range=["#fcc419", "#fd7e14", "#e03131"],
                ), legend=alt.Legend(orient="bottom")),
                tooltip=[
                    alt.Tooltip("Month:T", format="%b %Y"),
                    alt.Tooltip("Severity:N"),
                    alt.Tooltip("Count:Q"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(line_chart, use_container_width=True)

with col4:
    with st.container(border=True):
        st.markdown("### :material/pie_chart: Incidents by Type")

        type_counts = incidents_filtered.groupby("Type").size().reset_index(name="Count")
        type_counts["Percentage"] = (type_counts["Count"] / type_counts["Count"].sum() * 100).round(1)

        donut = (
            alt.Chart(type_counts)
            .mark_arc(innerRadius=55, outerRadius=110, cornerRadius=4)
            .encode(
                theta=alt.Theta("Count:Q"),
                color=alt.Color("Type:N", title=None, legend=alt.Legend(orient="bottom")),
                tooltip=[
                    alt.Tooltip("Type:N"),
                    alt.Tooltip("Count:Q"),
                    alt.Tooltip("Percentage:Q", title="Share %", format=".1f"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(donut, use_container_width=True)

# =============================================================================
# Row 3: Training Status Heatmap
# =============================================================================

with st.container(border=True):
    st.markdown("### :material/grid_on: Training Status Heatmap (Department x Module)")

    heatmap_data = training_filtered.groupby(["Department", "Module"]).apply(
        lambda x: (x["Status"] == "Completed").mean() * 100
    ).reset_index(name="Completion %")

    heatmap = (
        alt.Chart(heatmap_data)
        .mark_rect(cornerRadius=3)
        .encode(
            x=alt.X("Module:N", title=None),
            y=alt.Y("Department:N", title=None),
            color=alt.Color("Completion %:Q", title="Completion %", scale=alt.Scale(scheme="redyellowgreen", domain=[0, 100])),
            tooltip=[
                alt.Tooltip("Department:N"),
                alt.Tooltip("Module:N"),
                alt.Tooltip("Completion %:Q", format=".1f"),
            ],
        )
        .properties(height=250)
    )
    st.altair_chart(heatmap, use_container_width=True)

# =============================================================================
# Data Tables
# =============================================================================

with st.container(border=True):
    st.markdown("### :material/table_chart: Detailed Records")

    tab1, tab2, tab3 = st.tabs([
        ":material/people: Employee Compliance",
        ":material/school: Training Records",
        ":material/report: Incidents",
    ])

    with tab1:
        st.dataframe(
            emp_filtered.sort_values("Department"),
            use_container_width=True,
            hide_index=True,
            height=300,
            column_config={
                "I-9 Verified": st.column_config.CheckboxColumn("I-9 Verified"),
                "Policy Acknowledged": st.column_config.CheckboxColumn("Policy Acknowledged"),
            },
        )

    with tab2:
        overdue_only = st.toggle("Show overdue only", value=False)
        display_training = training_filtered[training_filtered["Status"] == "Overdue"] if overdue_only else training_filtered
        st.dataframe(
            display_training.sort_values("Due Date"),
            use_container_width=True,
            hide_index=True,
            height=300,
        )

    with tab3:
        st.dataframe(
            incidents_filtered.sort_values("Date", ascending=False),
            use_container_width=True,
            hide_index=True,
            height=300,
        )
