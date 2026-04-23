import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.graph_objects as go
import openpyxl
import os

import db

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="UK ILR Absence Tracker", layout="wide")

# ── Constants ─────────────────────────────────────────────────────────────────
START_DATE   = "2022-10-22"
END_DATE     = "2027-11-24"
UKVI_LIMIT   = 180
EXCEL_FILE   = os.path.join(os.path.dirname(__file__), "ILR Vacation Tracker.xlsx")
EXCEL_SHEETS = ["2022", "2023", "2024", "2025", "2026"]
TODAY        = date.today()


# ── DB init + Excel seed (runs once per process) ──────────────────────────────
@st.cache_resource
def initialise_db():
    """Create schema and seed Excel trips into the DB. Runs once per server process."""
    db.init_db()
    excel_trips = _read_excel_trips(EXCEL_FILE)
    seeded = db.seed_excel_trips(excel_trips)
    return seeded


@st.cache_data
def _read_excel_trips(path: str) -> list[tuple[str, str, str]]:
    """
    Read (destination, date_out, date_in) triples from each year sheet.
    Row layout: row 1 = title, row 2 = headers, rows 3+ = data.
    Columns: A=Country, B=Date Out, C=Date In, D=Duration (formula, ignored).
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    trips: list[tuple[str, str, str]] = []
    for sheet_name in EXCEL_SHEETS:
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        for row in list(ws.iter_rows(values_only=True))[2:]:  # skip title + header
            dest, date_out, date_in = row[0], row[1], row[2]
            if isinstance(date_out, date) and isinstance(date_in, date):
                trips.append((
                    str(dest) if dest else "—",
                    date_out.strftime("%Y-%m-%d"),
                    date_in.strftime("%Y-%m-%d"),
                ))
    wb.close()
    return trips


initialise_db()


# ── Build absence dataframe ───────────────────────────────────────────────────
@st.cache_data
def build_dataframe(trips: tuple[tuple[str, str], ...]) -> pd.DataFrame:
    """
    Build a daily DataFrame with Absence and Rolling_365 columns.
    Accepts a tuple (hashable) so Streamlit can cache on it.
    UKVI whole-days rule: only days strictly between departure and return count.
    """
    df = pd.DataFrame({"Date": pd.date_range(start=START_DATE, end=END_DATE, freq="D")})
    df["Absence"] = 0

    for trip_start, trip_end in trips:
        ts = pd.Timestamp(trip_start)
        te = pd.Timestamp(trip_end)
        df.loc[(df["Date"] > ts) & (df["Date"] < te), "Absence"] = 1

    # Vectorised rolling 365-day sum
    df["Rolling_365"] = (
        df["Absence"]
        .rolling(window=365, min_periods=1)
        .sum()
        .astype(int)
    )
    return df


# ── Apply unplanned buffer days on top of a base dataframe ───────────────────
def apply_buffer_days(
    base_df: pd.DataFrame,
    extra_2026: int,
    extra_2027: int,
    start_2026: pd.Timestamp,
    start_2027: pd.Timestamp,
    end_2026: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Overlay slider buffer days onto a copy of base_df, then recompute Rolling_365.
    Days are added consecutively from the given start dates, skipping days already
    marked as absences. end_2026 caps the window for 2026 buffer days.
    """
    df = base_df.copy()

    def _fill(start: pd.Timestamp, n_days: int, end: pd.Timestamp | None = None) -> None:
        remaining = n_days
        for i in df.index:
            if remaining <= 0:
                break
            row_date = df.at[i, "Date"]
            if end is not None and row_date > end:
                break
            if row_date >= start and df.at[i, "Absence"] == 0:
                df.at[i, "Absence"] = 1
                remaining -= 1

    if extra_2026 > 0:
        _fill(start_2026, extra_2026, end_2026)
    if extra_2027 > 0:
        _fill(start_2027, extra_2027)

    df["Rolling_365"] = (
        df["Absence"].rolling(window=365, min_periods=1).sum().astype(int)
    )
    return df


# ── ILR eligibility assessment ────────────────────────────────────────────────
def assess_ilr(
    application_date: date,
    all_trips_full: list[dict],
    extra_2026: int,
    extra_2027: int,
    buf_start_2026: pd.Timestamp,
    buf_end_2026: pd.Timestamp,
    buf_start_2027: pd.Timestamp,
) -> dict:
    """
    Assess ILR eligibility under Appendix Continuous Residence (5-year Skilled Worker route).

    Rules checked:
      1. Qualifying period: 5 years immediately before application_date
         (application_date - 5 years → application_date)
      2. No rolling 12-month window within that period may exceed 180 absence days
         (UKVI whole-days rule: departure and arrival days are NOT counted)
      3. No single trip may exceed 180 consecutive absence days

    Buffer days from sliders are included as synthetic absence days.
    Returns a dict with keys: eligible, breaches, worst_window, total_absences,
    qualifying_start, qualifying_end, checked_windows.
    """
    q_end   = pd.Timestamp(application_date)
    q_start = q_end - pd.DateOffset(years=5)

    # Build a daily absence series for the qualifying period
    date_range = pd.date_range(start=q_start, end=q_end, freq="D")
    absence = pd.Series(0, index=date_range)

    for t in all_trips_full:
        ts = pd.Timestamp(t["date_out"])
        te = pd.Timestamp(t["date_in"])
        # UKVI whole-days: strictly between departure and return
        mask = (date_range > ts) & (date_range < te)
        absence[mask] = 1

    # Apply slider buffer days (2026 window)
    def _apply_buffer(start: pd.Timestamp, end_cap: pd.Timestamp | None, n: int) -> None:
        remaining = n
        for d in date_range:
            if remaining <= 0:
                break
            if end_cap is not None and d > end_cap:
                break
            if d >= start and absence[d] == 0:
                absence[d] = 1
                remaining -= 1

    if extra_2026 > 0:
        _apply_buffer(buf_start_2026, buf_end_2026, extra_2026)
    if extra_2027 > 0:
        _apply_buffer(buf_start_2027, None, extra_2027)

    total_absences = int(absence.sum())

    # Check every rolling 12-month window (slide day by day)
    breaches: list[dict] = []
    worst_days = 0
    worst_window: dict | None = None

    window_days = 365
    for i in range(len(date_range) - window_days + 1):
        window = absence.iloc[i : i + window_days]
        days_absent = int(window.sum())
        if days_absent > worst_days:
            worst_days = days_absent
            worst_window = {
                "start": date_range[i].date(),
                "end":   date_range[i + window_days - 1].date(),
                "days":  days_absent,
            }
        if days_absent > UKVI_LIMIT:
            breaches.append({
                "start": date_range[i].date(),
                "end":   date_range[i + window_days - 1].date(),
                "days":  days_absent,
            })

    # Check for any single trip > 180 consecutive absence days
    long_trips: list[dict] = []
    for t in all_trips_full:
        ts = pd.Timestamp(t["date_out"])
        te = pd.Timestamp(t["date_in"])
        # Only trips that overlap the qualifying period
        if te < q_start or ts > q_end:
            continue
        consecutive = max((te - ts).days - 1, 0)
        if consecutive > UKVI_LIMIT:
            long_trips.append({
                "destination": t["destination"],
                "date_out": t["date_out"],
                "date_in":  t["date_in"],
                "days":     consecutive,
            })

    eligible = len(breaches) == 0 and len(long_trips) == 0

    return {
        "eligible":        eligible,
        "breaches":        breaches,
        "long_trips":      long_trips,
        "worst_window":    worst_window,
        "worst_days":      worst_days,
        "total_absences":  total_absences,
        "qualifying_start": q_start.date(),
        "qualifying_end":   q_end.date(),
    }


# ── Session state ─────────────────────────────────────────────────────────────
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None   # DB id of the trip being edited


# ── Title ─────────────────────────────────────────────────────────────────────
st.title("🇬🇧 UK ILR Absence Tracker")
st.caption(
    "Tracks absences from the UK against the UKVI limit of **180 days** "
    "in any rolling 365-day period."
)

# ── Future trips manager ──────────────────────────────────────────────────────
st.subheader("Planned Future Travel")

# ── Add / Edit form ───────────────────────────────────────────────────────────
editing    = st.session_state.edit_id is not None
form_title = "✏️ Edit Trip" if editing else "➕ Add a Future Trip"

with st.expander(form_title, expanded=editing):
    if editing:
        # Load the trip being edited from the DB
        edit_trip = next(
            (t for t in db.get_manual_trips() if t["id"] == st.session_state.edit_id),
            None,
        )
        if edit_trip is None:
            st.session_state.edit_id = None
            st.rerun()
        default_dest     = edit_trip["destination"]
        default_date_out = date.fromisoformat(edit_trip["date_out"])
        default_date_in  = date.fromisoformat(edit_trip["date_in"])
    else:
        default_dest     = ""
        default_date_out = TODAY + timedelta(days=1)
        default_date_in  = TODAY + timedelta(days=8)

    with st.form("trip_form", clear_on_submit=True):
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        with fc1:
            dest  = st.text_input("Destination", value=default_dest)
        with fc2:
            d_out = st.date_input("Date Out", value=default_date_out, key="form_out")
        with fc3:
            d_in  = st.date_input("Date In",  value=default_date_in,  key="form_in")

        fb1, fb2 = st.columns([1, 5])
        with fb1:
            submitted = st.form_submit_button("💾 Save" if editing else "➕ Add")
        with fb2:
            cancelled = st.form_submit_button("✖ Cancel") if editing else False

    if cancelled:
        st.session_state.edit_id = None
        st.rerun()

    if submitted:
        if d_out >= d_in:
            st.error("Date Out must be before Date In.")
        else:
            clean_dest = dest.strip() or "—"
            if editing:
                db.update_trip(st.session_state.edit_id, clean_dest, d_out.isoformat(), d_in.isoformat())
                st.session_state.edit_id = None
                st.success("Trip updated.")
            else:
                db.add_trip(clean_dest, d_out.isoformat(), d_in.isoformat())
                st.success(f"Trip to {clean_dest} added.")
            build_dataframe.clear()   # invalidate chart cache
            st.rerun()

# ── Manual trip list ──────────────────────────────────────────────────────────
manual_trips = db.get_manual_trips()

if manual_trips:
    header = st.columns([2, 1, 1, 1, 1, 1])
    for col, label in zip(header, ["Destination", "Date Out", "Date In", "Days Away", "", ""]):
        col.markdown(f"**{label}**")

    for trip in manual_trips:
        d_out_dt     = date.fromisoformat(trip["date_out"])
        d_in_dt      = date.fromisoformat(trip["date_in"])
        absence_days = max((d_in_dt - d_out_dt).days - 1, 0)

        row = st.columns([2, 1, 1, 1, 1, 1])
        row[0].write(trip["destination"])
        row[1].write(trip["date_out"])
        row[2].write(trip["date_in"])
        row[3].write(f"{absence_days}d")
        if row[4].button("✏️", key=f"edit_{trip['id']}", help="Edit"):
            st.session_state.edit_id = trip["id"]
            st.rerun()
        if row[5].button("🗑️", key=f"del_{trip['id']}", help="Delete"):
            db.delete_trip(trip["id"])
            build_dataframe.clear()
            st.rerun()
else:
    st.info("No future trips added yet. Use the form above to plan ahead.")

st.divider()

# ── Build base dataframe from all DB trips ────────────────────────────────────
all_trips = tuple(
    (t["date_out"], t["date_in"]) for t in db.get_all_trips()
)
df_base = build_dataframe(all_trips)

# ── Unplanned travel buffer sliders ──────────────────────────────────────────
st.subheader("Unplanned Travel Buffer")
st.caption(
    "Simulate extra unplanned days away to see how much flexibility remains "
    "before hitting the 180-day rolling limit."
)

# 2026 buffer: fixed window May 11 – Nov 12 2026 (gap between known trips)
# 2027 buffer: from day after the last known 2027 departure
BUFFER_2026_START = pd.Timestamp("2026-05-11")
BUFFER_2026_END   = pd.Timestamp("2026-11-20")   # inclusive upper bound for filling

def _last_departure_after(trips_tuple, year: int) -> pd.Timestamp:
    """Day after the latest departure date for trips departing in the given year."""
    outs = [
        pd.Timestamp(t[0])
        for t in trips_tuple
        if pd.Timestamp(t[0]).year == year
    ]
    return (max(outs) + pd.Timedelta(days=1)) if outs else pd.Timestamp(f"{year}-01-01")

start_2027 = _last_departure_after(all_trips, 2027)

col_s1, col_s2 = st.columns(2)
with col_s1:
    extra_2026 = st.slider(
        "Extra 2026 days (11 May – 20 Nov 2026)",
        min_value=0, max_value=120, value=0,
        key="slider_2026",
    )
with col_s2:
    extra_2027 = st.slider(
        f"Extra 2027 days (from {start_2027.strftime('%d %b %Y')})",
        min_value=0, max_value=180, value=0,
        key="slider_2027",
    )

# Apply buffer on top of the cached base (not persisted, purely for display)
df = apply_buffer_days(df_base, extra_2026, extra_2027, BUFFER_2026_START, start_2027, BUFFER_2026_END)

st.divider()

# ── Derived metrics ───────────────────────────────────────────────────────────
max_peak = int(df["Rolling_365"].max())

if max_peak < 150:
    status_label       = "✅ Safe"
    status_delta_color = "normal"
elif max_peak <= UKVI_LIMIT:
    status_label       = "⚠️ Warning Zone"
    status_delta_color = "off"
else:
    status_label       = "🚨 LIMIT EXCEEDED"
    status_delta_color = "inverse"

# ── Summary metrics ───────────────────────────────────────────────────────────
st.subheader("Summary")
m1, m2, m3 = st.columns(3)
m1.metric("UKVI Limit", f"{UKVI_LIMIT} Days")
m2.metric(
    "Max Rolling Peak",
    f"{max_peak} Days",
    delta=f"{max_peak - UKVI_LIMIT:+d} vs limit",
    delta_color=status_delta_color,
)
m3.metric("Status", status_label)

st.divider()

# ── Plotly chart ──────────────────────────────────────────────────────────────
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df["Date"],
    y=df["Rolling_365"],
    mode="lines",
    name="Rolling 365-day absences",
    line=dict(color="royalblue", width=2),
    fill="tozeroy",
    fillcolor="rgba(65, 105, 225, 0.15)",
))

fig.add_hline(
    y=UKVI_LIMIT,
    line_dash="dash",
    line_color="red",
    line_width=2,
    annotation_text="UKVI 180-day limit",
    annotation_position="top left",
    annotation_font_color="red",
)

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
        rangeselector=dict(buttons=[
            dict(count=1,  label="1m",  step="month"),
            dict(count=3,  label="3m",  step="month"),
            dict(count=6,  label="6m",  step="month"),
            dict(count=1,  label="YTD", step="year", stepmode="todate"),
            dict(step="all", label="All"),
        ]),
    ),
)

st.plotly_chart(fig, use_container_width=True)

# ── Trip history by year ──────────────────────────────────────────────────────
st.subheader("Trip History")

all_trips_full = db.get_all_trips()   # full dicts with destination + source

# Group by departure year
from collections import defaultdict
trips_by_year: dict[int, list[dict]] = defaultdict(list)
for t in all_trips_full:
    year = int(t["date_out"][:4])
    trips_by_year[year].append(t)

YEAR_COLORS = {
    2022: "#6366f1",   # indigo
    2023: "#0ea5e9",   # sky blue
    2024: "#10b981",   # emerald
    2025: "#f59e0b",   # amber
    2026: "#ef4444",   # red
    2027: "#8b5cf6",   # violet
}

for year in sorted(trips_by_year.keys(), reverse=True):
    year_trips = sorted(trips_by_year[year], key=lambda t: t["date_out"])
    total_absence = sum(
        max((date.fromisoformat(t["date_in"]) - date.fromisoformat(t["date_out"])).days - 1, 0)
        for t in year_trips
    )
    color = YEAR_COLORS.get(year, "#64748b")

    # Year header with total
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:12px; margin: 20px 0 8px 0;">
            <div style="background:{color}; color:white; font-weight:700; font-size:1.1rem;
                        padding:4px 16px; border-radius:20px;">{year}</div>
            <div style="color:#64748b; font-size:0.9rem;">
                {len(year_trips)} trip{"s" if len(year_trips) != 1 else ""} &nbsp;·&nbsp;
                <strong>{total_absence}</strong> absence days
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Trip cards — 3 per row
    cols_per_row = 3
    for row_start in range(0, len(year_trips), cols_per_row):
        row_trips = year_trips[row_start : row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, trip in zip(cols, row_trips):
            d_out = date.fromisoformat(trip["date_out"])
            d_in  = date.fromisoformat(trip["date_in"])
            absence_days = max((d_in - d_out).days - 1, 0)
            total_days   = (d_in - d_out).days

            source_badge = (
                f'<span style="background:#e0f2fe; color:#0369a1; font-size:0.7rem; '
                f'padding:2px 8px; border-radius:10px; font-weight:600;">PLANNED</span>'
                if trip["source"] == "manual"
                else f'<span style="background:#f0fdf4; color:#166534; font-size:0.7rem; '
                f'padding:2px 8px; border-radius:10px; font-weight:600;">EXCEL</span>'
            )

            col.markdown(
                f"""
                <div style="border:1px solid #e2e8f0; border-radius:12px; padding:14px 16px;
                            border-left:4px solid {color}; background:#fafafa;
                            margin-bottom:8px; min-height:110px;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
                        <div style="font-weight:600; font-size:0.95rem; color:#1e293b;
                                    flex:1; margin-right:8px;">{trip["destination"]}</div>
                        {source_badge}
                    </div>
                    <div style="color:#475569; font-size:0.82rem; margin-bottom:8px;">
                        📅 {d_out.strftime("%d %b")} → {d_in.strftime("%d %b %Y")}
                    </div>
                    <div style="display:flex; gap:8px;">
                        <span style="background:{color}22; color:{color}; font-size:0.78rem;
                                     padding:2px 10px; border-radius:10px; font-weight:600;">
                            {absence_days}d absent
                        </span>
                        <span style="background:#f1f5f9; color:#64748b; font-size:0.78rem;
                                     padding:2px 10px; border-radius:10px;">
                            {total_days}d total
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='margin-bottom:4px'></div>", unsafe_allow_html=True)

st.divider()

# ── ILR Eligibility Assessment ────────────────────────────────────────────────
st.subheader("🏛️ ILR Eligibility Assessment")
st.caption(
    "Assesses eligibility under the **5-year Skilled Worker route** "
    "(Appendix Continuous Residence). The qualifying period is the 5 years "
    "immediately before your chosen application date. "
    "The 180-day rule is checked across every rolling 12-month window in that period."
)

ILR_MIN_DATE = date(2027, 9, 1)
ILR_MAX_DATE = date(2027, 11, 24)

ilr_date = st.date_input(
    "Select ILR application date",
    value=date(2027, 11, 24),
    min_value=ILR_MIN_DATE,
    max_value=ILR_MAX_DATE,
    format="DD/MM/YYYY",
    key="ilr_date",
)

if ilr_date < ILR_MIN_DATE:
    st.error(f"ILR application date must be on or after {ILR_MIN_DATE.strftime('%d %b %Y')}.")
else:
    result = assess_ilr(
        application_date=ilr_date,
        all_trips_full=all_trips_full,
        extra_2026=extra_2026,
        extra_2027=extra_2027,
        buf_start_2026=BUFFER_2026_START,
        buf_end_2026=BUFFER_2026_END,
        buf_start_2027=start_2027,
    )

    # ── Verdict banner ────────────────────────────────────────────────────────
    if result["eligible"]:
        st.markdown(
            """
            <div style="background:#f0fdf4; border:1.5px solid #86efac; border-radius:12px;
                        padding:20px 24px; margin-bottom:16px;">
                <div style="font-size:1.5rem; font-weight:700; color:#15803d; margin-bottom:4px;">
                    ✅ Eligible for ILR
                </div>
                <div style="color:#166534; font-size:0.95rem;">
                    No rolling 12-month window exceeds 180 absence days during the qualifying period.
                    You appear to meet the continuous residence requirement.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="background:#fef2f2; border:1.5px solid #fca5a5; border-radius:12px;
                        padding:20px 24px; margin-bottom:16px;">
                <div style="font-size:1.5rem; font-weight:700; color:#dc2626; margin-bottom:4px;">
                    ❌ Not Eligible — Continuous Residence Broken
                </div>
                <div style="color:#991b1b; font-size:0.95rem;">
                    One or more rolling 12-month windows exceed the 180-day absence limit.
                    Continuous residence is considered broken under Appendix Continuous Residence.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Key figures ───────────────────────────────────────────────────────────
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Qualifying Period Start", result["qualifying_start"].strftime("%d %b %Y"))
    a2.metric("Qualifying Period End",   result["qualifying_end"].strftime("%d %b %Y"))
    a3.metric("Total Absence Days",      f"{result['total_absences']}d")
    a4.metric(
        "Worst Rolling Window",
        f"{result['worst_days']}d",
        delta=f"{result['worst_days'] - UKVI_LIMIT:+d} vs 180-day limit",
        delta_color="inverse" if result["worst_days"] > UKVI_LIMIT else "normal",
    )

    # ── Worst window detail ───────────────────────────────────────────────────
    if result["worst_window"]:
        ww = result["worst_window"]
        status_color = "#dc2626" if ww["days"] > UKVI_LIMIT else "#15803d"
        st.markdown(
            f"""
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px;
                        padding:14px 18px; margin-top:12px;">
                <span style="font-weight:600; color:#334155;">Peak absence window: </span>
                <span style="color:#475569;">
                    {ww["start"].strftime("%d %b %Y")} → {ww["end"].strftime("%d %b %Y")}
                </span>
                &nbsp;·&nbsp;
                <span style="font-weight:700; color:{status_color};">{ww["days"]} days absent</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Breach details ────────────────────────────────────────────────────────
    if result["breaches"]:
        with st.expander(f"⚠️ {len(result['breaches'])} breach window(s) — click to expand"):
            st.markdown(
                "<div style='color:#64748b; font-size:0.85rem; margin-bottom:8px;'>"
                "Each row is a 365-day window where absences exceeded 180 days.</div>",
                unsafe_allow_html=True,
            )
            breach_df = pd.DataFrame(result["breaches"])
            breach_df.columns = ["Window Start", "Window End", "Days Absent"]
            breach_df["Over Limit By"] = breach_df["Days Absent"] - UKVI_LIMIT
            st.dataframe(breach_df, use_container_width=True, hide_index=True)

    # ── Long single-trip warnings ─────────────────────────────────────────────
    if result["long_trips"]:
        with st.expander(f"⚠️ {len(result['long_trips'])} trip(s) exceeding 180 consecutive days"):
            for lt in result["long_trips"]:
                st.markdown(
                    f"- **{lt['destination']}** &nbsp; {lt['date_out']} → {lt['date_in']} "
                    f"&nbsp; ({lt['days']} consecutive absence days)",
                    unsafe_allow_html=True,
                )

    # ── Disclaimer ────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='color:#94a3b8; font-size:0.78rem; margin-top:16px;'>"
        "⚠️ This assessment is for informational purposes only and does not constitute legal advice. "
        "Always consult a qualified immigration solicitor before submitting an ILR application."
        "</div>",
        unsafe_allow_html=True,
    )
