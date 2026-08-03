# HR Hiring Analytics Dashboard with recruitment funnel, trends, and candidate insights
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

st.set_page_config(page_title="HR Hiring Dashboard", layout="wide")

st.title("HR Hiring Analytics Dashboard")

# ----------------------------
# Load Data
# ----------------------------
@st.cache_data(ttl=600)
def load_data():
    return session.sql("SELECT * FROM ANALYTICS_DEV.HR.HR_HIRING_DATA").to_pandas()

df = load_data()
df["APPLICATION_DATE"] = pd.to_datetime(df["APPLICATION_DATE"])
df["INTERVIEW_DATE"] = pd.to_datetime(df["INTERVIEW_DATE"])
df["OFFER_DATE"] = pd.to_datetime(df["OFFER_DATE"])
df["JOINING_DATE"] = pd.to_datetime(df["JOINING_DATE"])

# ----------------------------
# Sidebar Filters
# ----------------------------
st.sidebar.header("Filters")

departments = st.sidebar.multiselect(
    "Department",
    options=sorted(df["DEPARTMENT"].unique()),
    default=sorted(df["DEPARTMENT"].unique()),
)

locations = st.sidebar.multiselect(
    "Location",
    options=sorted(df["LOCATION"].unique()),
    default=sorted(df["LOCATION"].unique()),
)

sources = st.sidebar.multiselect(
    "Source",
    options=sorted(df["SOURCE"].unique()),
    default=sorted(df["SOURCE"].unique()),
)

statuses = st.sidebar.multiselect(
    "Application Status",
    options=sorted(df["APPLICATION_STATUS"].unique()),
    default=sorted(df["APPLICATION_STATUS"].unique()),
)

priorities = st.sidebar.multiselect(
    "Hiring Priority",
    options=sorted(df["HIRING_PRIORITY"].unique()),
    default=sorted(df["HIRING_PRIORITY"].unique()),
)

date_min = df["APPLICATION_DATE"].min().date()
date_max = df["APPLICATION_DATE"].max().date()
date_range = st.sidebar.date_input(
    "Application Date Range",
    value=(date_min, date_max),
    min_value=date_min,
    max_value=date_max,
)

# Apply filters
filtered = df[
    (df["DEPARTMENT"].isin(departments))
    & (df["LOCATION"].isin(locations))
    & (df["SOURCE"].isin(sources))
    & (df["APPLICATION_STATUS"].isin(statuses))
    & (df["HIRING_PRIORITY"].isin(priorities))
]

if isinstance(date_range, tuple) and len(date_range) == 2:
    filtered = filtered[
        (filtered["APPLICATION_DATE"].dt.date >= date_range[0])
        & (filtered["APPLICATION_DATE"].dt.date <= date_range[1])
    ]

# ----------------------------
# KPI Metrics
# ----------------------------
total_applications = len(filtered)
total_offers = filtered[filtered["APPLICATION_STATUS"] == "Offered"].shape[0]
total_hired = filtered[filtered["APPLICATION_STATUS"] == "Hired"].shape[0]
avg_salary = filtered["OFFERED_SALARY"].mean()
avg_experience = filtered["EXPERIENCE_YEARS"].mean()
offer_rate = (total_offers + total_hired) / total_applications * 100 if total_applications > 0 else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Applications", f"{total_applications:,}")
c2.metric("Offers Made", f"{total_offers + total_hired:,}")
c3.metric("Hired", f"{total_hired:,}")
c4.metric("Avg Salary Offered", f"${avg_salary:,.0f}")
c5.metric("Offer Rate", f"{offer_rate:.1f}%")

st.divider()

# ----------------------------
# Row 1: Hiring Funnel + Monthly Trend
# ----------------------------
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Recruitment Funnel")
    funnel_data = filtered["APPLICATION_STATUS"].value_counts().reset_index()
    funnel_data.columns = ["Status", "Count"]
    funnel_order = ["Applied", "Screened", "Interviewed", "Offered", "Hired", "Rejected"]
    funnel_data["Status"] = pd.Categorical(funnel_data["Status"], categories=funnel_order, ordered=True)
    funnel_data = funnel_data.sort_values("Status").dropna(subset=["Status"])

    if go is not None:
        fig = go.Figure(go.Funnel(
            y=funnel_data["Status"],
            x=funnel_data["Count"],
            textinfo="value+percent initial",
            marker=dict(color=["#4C78A8", "#72B7B2", "#F58518", "#E45756", "#54A24B", "#B07AA1"]),
        ))
        fig.update_layout(margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(funnel_data.set_index("Status"))

with col_right:
    st.subheader("Monthly Application Trend")
    monthly_df = filtered.copy()
    monthly_df["MONTH"] = monthly_df["APPLICATION_DATE"].dt.to_period("M").astype(str)
    monthly = monthly_df.groupby("MONTH", as_index=False).agg(
        Applications=("CANDIDATE_ID", "count")
    )
    if go is not None:
        fig = go.Figure(go.Scatter(
            x=monthly["MONTH"],
            y=monthly["Applications"],
            mode="lines+markers",
            line=dict(color="#4C78A8", width=2),
            fill="tozeroy",
            fillcolor="rgba(76, 120, 168, 0.1)",
        ))
        fig.update_layout(
            template="plotly_white",
            xaxis_title="Month",
            yaxis_title="Applications",
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif alt is not None:
        chart = alt.Chart(monthly).mark_line(point=True, color="#4C78A8").encode(
            x=alt.X("MONTH:N", title="Month"),
            y=alt.Y("Applications:Q", title="Applications"),
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.line_chart(monthly.set_index("MONTH"))

st.divider()

# ----------------------------
# Row 2: Department Hiring + Source Effectiveness
# ----------------------------
col_left2, col_right2 = st.columns(2)

with col_left2:
    st.subheader("Applications by Department")
    dept_agg = (
        filtered.groupby("DEPARTMENT", as_index=False)
        .agg(Applications=("CANDIDATE_ID", "count"), Hired=("APPLICATION_STATUS", lambda x: (x == "Hired").sum()))
    )
    if go is not None:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dept_agg["DEPARTMENT"], y=dept_agg["Applications"],
            name="Applications", marker_color="#4C78A8"
        ))
        fig.add_trace(go.Bar(
            x=dept_agg["DEPARTMENT"], y=dept_agg["Hired"],
            name="Hired", marker_color="#54A24B"
        ))
        fig.update_layout(
            template="plotly_white", barmode="group",
            xaxis_title="Department", yaxis_title="Count",
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif alt is not None:
        melted = dept_agg.melt(id_vars=["DEPARTMENT"], value_vars=["Applications", "Hired"],
                               var_name="Metric", value_name="Count")
        chart = alt.Chart(melted).mark_bar().encode(
            x=alt.X("DEPARTMENT:N", title="Department"),
            y=alt.Y("Count:Q"), color="Metric:N", xOffset="Metric:N"
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(dept_agg.set_index("DEPARTMENT")[["Applications", "Hired"]])

with col_right2:
    st.subheader("Hiring by Source")
    source_agg = (
        filtered.groupby("SOURCE", as_index=False)
        .agg(Count=("CANDIDATE_ID", "count"))
        .sort_values("Count", ascending=False)
    )
    if go is not None:
        fig = go.Figure(go.Bar(
            x=source_agg["Count"], y=source_agg["SOURCE"],
            orientation="h", marker_color="#F58518"
        ))
        fig.update_layout(
            template="plotly_white",
            xaxis_title="Applications", yaxis_title="Source",
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif alt is not None:
        chart = alt.Chart(source_agg).mark_bar(color="#F58518").encode(
            x=alt.X("Count:Q", title="Applications"),
            y=alt.Y("SOURCE:N", sort="-x", title="Source"),
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(source_agg.set_index("SOURCE"))

st.divider()

# ----------------------------
# Row 3: Gender Distribution + Salary by Department
# ----------------------------
col_left3, col_right3 = st.columns(2)

with col_left3:
    st.subheader("Gender Distribution")
    gender_agg = filtered["GENDER"].value_counts().reset_index()
    gender_agg.columns = ["Gender", "Count"]
    if go is not None:
        fig = go.Figure(go.Pie(
            labels=gender_agg["Gender"], values=gender_agg["Count"],
            hole=0.4, marker=dict(colors=["#4C78A8", "#F58518", "#54A24B"])
        ))
        fig.update_layout(margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(gender_agg.set_index("Gender"))

with col_right3:
    st.subheader("Avg Salary by Department")
    salary_dept = (
        filtered.groupby("DEPARTMENT", as_index=False)
        .agg(Avg_Salary=("OFFERED_SALARY", "mean"))
        .sort_values("Avg_Salary", ascending=False)
    )
    if go is not None:
        fig = go.Figure(go.Bar(
            x=salary_dept["DEPARTMENT"], y=salary_dept["Avg_Salary"],
            marker_color="#72B7B2"
        ))
        fig.update_layout(
            template="plotly_white",
            xaxis_title="Department", yaxis_title="Avg Salary ($)",
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif alt is not None:
        chart = alt.Chart(salary_dept).mark_bar(color="#72B7B2").encode(
            x=alt.X("DEPARTMENT:N", sort="-y", title="Department"),
            y=alt.Y("Avg_Salary:Q", title="Avg Salary ($)"),
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(salary_dept.set_index("DEPARTMENT"))

st.divider()

# ----------------------------
# Row 4: Experience Distribution + Location Hiring
# ----------------------------
col_left4, col_right4 = st.columns(2)

with col_left4:
    st.subheader("Experience Distribution")
    if go is not None:
        fig = go.Figure(go.Histogram(
            x=filtered["EXPERIENCE_YEARS"], nbinsx=20,
            marker_color="#B07AA1"
        ))
        fig.update_layout(
            template="plotly_white",
            xaxis_title="Years of Experience", yaxis_title="Count",
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif alt is not None:
        chart = alt.Chart(filtered).mark_bar(color="#B07AA1").encode(
            alt.X("EXPERIENCE_YEARS:Q", bin=alt.Bin(maxbins=20), title="Years of Experience"),
            y="count()",
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(filtered["EXPERIENCE_YEARS"].value_counts().sort_index())

with col_right4:
    st.subheader("Hiring by Location")
    loc_agg = (
        filtered.groupby("LOCATION", as_index=False)
        .agg(Applications=("CANDIDATE_ID", "count"))
        .sort_values("Applications", ascending=False)
    )
    if go is not None:
        fig = go.Figure(go.Bar(
            x=loc_agg["Applications"], y=loc_agg["LOCATION"],
            orientation="h", marker_color="#E45756"
        ))
        fig.update_layout(
            template="plotly_white",
            xaxis_title="Applications", yaxis_title="Location",
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif alt is not None:
        chart = alt.Chart(loc_agg).mark_bar(color="#E45756").encode(
            x=alt.X("Applications:Q", title="Applications"),
            y=alt.Y("LOCATION:N", sort="-x", title="Location"),
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(loc_agg.set_index("LOCATION"))

st.divider()

# ----------------------------
# Candidate Details Table
# ----------------------------
st.subheader("Candidate Details")

display_cols = ["CANDIDATE_ID", "APPLICATION_DATE", "DEPARTMENT", "JOB_ROLE", "LOCATION",
                "SOURCE", "GENDER", "AGE", "EXPERIENCE_YEARS", "OFFERED_SALARY",
                "APPLICATION_STATUS", "HIRING_PRIORITY"]

st.dataframe(
    filtered[display_cols].sort_values("APPLICATION_DATE", ascending=False),
    use_container_width=True,
    hide_index=True,
    column_config={
        "OFFERED_SALARY": st.column_config.NumberColumn(format="$%d"),
        "APPLICATION_DATE": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "EXPERIENCE_YEARS": st.column_config.NumberColumn(format="%.1f yrs"),
    },
)

st.caption(f"Showing {len(filtered):,} of {len(df):,} candidates")