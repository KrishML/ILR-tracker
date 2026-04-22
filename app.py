import streamlit as st
import pandas as pd
from datetime import date
import plotly.graph_objects as go

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="UK ILR Absence Tracker", layout="wide")

# ── Constants ─────────────────────────────────────────────────────────────────
START_DATE = "2022-10-22"
END_DATE   = "2027-11-24"
UKVI_LIMIT = 180

# Base trips (each counted using the UKVI "whole days" rule:
# only dates strictly *between* departure and return are absence days)
BASE_TRIPS = [
    ("2022-10-22", "2022-11-23"), ("2022-11-29", "2022-12-10"),
    ("2023-01-28", "2023-02-05"), ("2023-03-06", "2023-03-11"),
    ("2023-05-11", "2023-05-29"), ("2023-06-16", "2023-06-19"),
    ("2023-07-08", "2023-07-11"), ("2023-08-03", "2023-08-07"),
    ("2023-08-18", "2023-08-21"), ("2023-09-01", "2023-09-05"),
    ("2023-09-14", "2023-09-16"), ("2023-10-06", "2023-10-09"),
    ("2023-10-13", "2023-10-29"), ("2023-11-11", "2023-11-15"),
    ("2024-01-12", "2024-01-14"), ("2024-01-21", "2024-01-23"),
    ("2024-01-31", "2024-02-07"), ("2024-03-19", "2024-04-08"),
    ("2024-07-26", "2024-07-28"), ("2024-08-16", "2024-08-18"),
    ("2024-08-29", "2024-09-02"), ("2024-09-28", "2024-10-01"),
    ("2024-11-08", "2024-11-11"), ("2024-11-29", "2024-12-09"),
    ("2024-12-20", "2024-12-30"), ("2025-01-09", "2025-01-27"),
    ("2025-02-07", "2025-02-10"), ("2025-03-01", "2025-03-03"),
    ("2025-03-06", "2025-03-16"), ("2025-04-16", "2025-04-22"),
    ("2025-05-02", "2025-05-06"), ("2025-05-31", "2025-06-04"),
    ("2025-06-13", "2025-06-16"), ("2025-06-27", "2025-07-06"),
    ("2025-07-13", "2025-07-21"), ("2025-07-30", "2025-08-04"),
    ("2025-08-11", "2025-08-17"), ("2025-08-22", "2025-08-25"),
    ("2025-09-04", "2025-09-09"), ("2025-09-11", "2025-09-16"),
    ("2025-11-07", "2025-11-10"), ("2025-11-21", "2025-11-24"),
    ("2025-12-02", "2025-12-29"), ("2026-01-16", "2026-01-19"),
    ("2026-01-23", "2026-01-26"), ("2026-02-05", "2026-02-18"),
    ("2026-02-20", "2026-02-23"), ("2026-03-06", "2026-03-09"),
    ("2026-03-14", "2026-03-16"), ("2026-03-28", "2026-03-30"),
    ("2026-04-01", "2026-04-07"), ("2026-04-10", "2026-04-13"),
    ("2026-04-17", "2026-04-20"), ("2026-05-01", "2026-05-10"),
    ("2026-11-21", "2026-12-31"),
]

# ── Title ─────────────────────────────────────────────────────────────────────
st.title("🇬🇧 UK ILR Absence Tracker")
st.caption(
    "Tracks absences from the UK against the UKVI limit of **180 days** "
    "in any rolling 365-day period."
)

# ── Sliders ───────────────────────────────────────────────────────────────────
st.subheader("Projected Future Travel")

col_s1, col_s2 = st.columns(2)
with col_s1:
    extra_2026_days = st.slider(
        "Extra 2026 Travel Days (Starts May 11, 2026)",
        min_value=0, max_value=100, value=20,
        key="slider_2026"
    )
with col_s2:
    travel_2027_days = st.slider(
        "2027 Travel Days (Starts Apr 25, 2027)",
        min_value=0, max_value=180, value=45,
        key="slider_2027"
    )

# ── Calculation ───────────────────────────────────────────────────────────────

@st.cache_data
def build_base_dataframe():
    """Build the base DataFrame with base trips (cached to avoid recalculation)."""
    df = pd.DataFrame({"Date": pd.date_range(start=START_DATE, end=END_DATE, freq="D")})
    df["Absence"] = 0
    
    # Apply base trips using the UKVI "whole days" rule:
    # A day is an absence only when it is STRICTLY between departure and return dates.
    for trip_start, trip_end in BASE_TRIPS:
        ts = pd.Timestamp(trip_start)
        te = pd.Timestamp(trip_end)
        mask = (df["Date"] > ts) & (df["Date"] < te)
        df.loc[mask, "Absence"] = 1
    
    return df

def apply_sliders(df, extra_2026_days, travel_2027_days):
    """Apply slider values to a copy of the DataFrame."""
    df = df.copy()
    
    # Apply Slider 1 — extra 2026 travel beginning 2026-05-11
    date_2026 = pd.Timestamp("2026-05-11")
    applied_2026 = 0
    for i in range(len(df)):
        if applied_2026 >= extra_2026_days:
            break
        if df.iloc[i]["Date"] >= date_2026:
            df.iloc[i, df.columns.get_loc("Absence")] = 1
            applied_2026 += 1
    
    # Apply Slider 2 — 2027 travel beginning 2027-04-25
    date_2027 = pd.Timestamp("2027-04-25")
    applied_2027 = 0
    for i in range(len(df)):
        if applied_2027 >= travel_2027_days:
            break
        if df.iloc[i]["Date"] >= date_2027:
            df.iloc[i, df.columns.get_loc("Absence")] = 1
            applied_2027 += 1
    
    # Calculate the rolling 365-day sum
    # For each date, count absences in the window [date - 365 days : date]
    rolling_365_values = []
    for i in range(len(df)):
        window_sum = 0
        window_start = max(0, i - 364)  # 365 rows including current day
        for j in range(window_start, i + 1):
            window_sum += df.iloc[j]["Absence"]
        rolling_365_values.append(window_sum)
    
    df["Rolling_365"] = rolling_365_values
    return df

# Build base and apply sliders
df_base = build_base_dataframe()
df = apply_sliders(df_base, extra_2026_days, travel_2027_days)

# ── Derived metrics ───────────────────────────────────────────────────────────
max_peak = int(df["Rolling_365"].max())

if max_peak < 150:
    status_label = "✅ Safe"
    status_delta_color = "normal"
elif max_peak <= UKVI_LIMIT:
    status_label = "⚠️ Warning Zone"
    status_delta_color = "off"
else:
    status_label = "🚨 LIMIT EXCEEDED"
    status_delta_color = "inverse"

# ── Top metrics row ───────────────────────────────────────────────────────────
st.subheader("Summary")
m1, m2, m3 = st.columns(3)

m1.metric(
    label="UKVI Limit",
    value=f"{UKVI_LIMIT} Days",
)
m2.metric(
    label="Max Rolling Peak",
    value=f"{max_peak} Days",
    delta=f"{max_peak - UKVI_LIMIT:+d} vs limit",
    delta_color=status_delta_color,
)
m3.metric(
    label="Status",
    value=status_label,
)

st.divider()

# ── Plotly chart ──────────────────────────────────────────────────────────────
fig = go.Figure()

# Blue line with filled area underneath
fig.add_trace(
    go.Scatter(
        x=df["Date"],
        y=df["Rolling_365"],
        mode="lines",
        name="Rolling 365-day absences",
        line=dict(color="royalblue", width=2),
        fill="tozeroy",
        fillcolor="rgba(65, 105, 225, 0.15)",
    )
)

# Red dashed limit line at y=180
fig.add_hline(
    y=UKVI_LIMIT,
    line_dash="dash",
    line_color="red",
    line_width=2,
    annotation_text="UKVI 180-day limit",
    annotation_position="top left",
    annotation_font_color="red",
)

# Note: Today marker removed due to Plotly datetime handling issues
# The 180-day limit line is sufficient for tracking

fig.update_layout(
    title="Rolling 365-Day UK Absences",
    xaxis_title="Date",
    yaxis_title="Days Absent (rolling 365-day window)",
    yaxis=dict(range=[0, 200]),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=40, r=40, t=60, b=80),
    template="plotly_white",
    height=600,
    xaxis=dict(
        rangeslider=dict(visible=True, thickness=0.05),
        type="date",
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1m", step="month"),
                dict(count=3, label="3m", step="month"),
                dict(count=6, label="6m", step="month"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(step="all", label="All"),
            ])
        ),
    ),
)

st.plotly_chart(fig, width="stretch")

# ── Raw data expander ─────────────────────────────────────────────────────────
with st.expander("View Raw Data"):
    st.dataframe(
        df[df["Absence"] == 1][["Date", "Absence", "Rolling_365"]].reset_index(drop=True),
        width="stretch",
    )
