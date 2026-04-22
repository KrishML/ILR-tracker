import React, { useState, useMemo, useRef, useEffect } from 'react';

// ── Constants ────────────────────────────────────────────────────────────────
const START_DATE = '2022-10-22';
const END_DATE = '2028-11-24';
const UKVI_LIMIT = 180;

// ILR slider start dates
const SLIDER_2026_START = '2026-05-11';
const SLIDER_2027_START = '2027-04-25';

// Citizenship slider start dates (independent)
const CIT_SLIDER_2026_START = '2026-05-11';
const CIT_SLIDER_2027_START = '2027-04-25';
const CIT_SLIDER_2028_START = '2028-01-01';

// Citizenship eligibility window constants
const CITIZENSHIP_5YR_START = '2023-10-24';
const CITIZENSHIP_5YR_END   = '2028-10-24';
const CITIZENSHIP_12M_START = '2027-10-24';
const CITIZENSHIP_12M_END   = '2028-10-24';
const CITIZENSHIP_5YR_LIMIT = 450;
const CITIZENSHIP_12M_LIMIT = 90;

const BASE_TRIPS = [
  ['2022-10-22', '2022-11-23'], ['2022-11-29', '2022-12-10'],
  ['2023-01-28', '2023-02-05'], ['2023-03-06', '2023-03-11'],
  ['2023-05-11', '2023-05-29'], ['2023-06-16', '2023-06-19'],
  ['2023-07-08', '2023-07-11'], ['2023-08-03', '2023-08-07'],
  ['2023-08-18', '2023-08-21'], ['2023-09-01', '2023-09-05'],
  ['2023-09-14', '2023-09-16'], ['2023-10-06', '2023-10-09'],
  ['2023-10-13', '2023-10-29'], ['2023-11-11', '2023-11-15'],
  ['2024-01-12', '2024-01-14'], ['2024-01-21', '2024-01-23'],
  ['2024-01-31', '2024-02-07'], ['2024-03-19', '2024-04-08'],
  ['2024-07-26', '2024-07-28'], ['2024-08-16', '2024-08-18'],
  ['2024-08-29', '2024-09-02'], ['2024-09-28', '2024-10-01'],
  ['2024-11-08', '2024-11-11'], ['2024-11-29', '2024-12-09'],
  ['2024-12-20', '2024-12-30'], ['2025-01-09', '2025-01-27'],
  ['2025-02-07', '2025-02-10'], ['2025-03-01', '2025-03-03'],
  ['2025-03-06', '2025-03-16'], ['2025-04-16', '2025-04-22'],
  ['2025-05-02', '2025-05-06'], ['2025-05-31', '2025-06-04'],
  ['2025-06-13', '2025-06-16'], ['2025-06-27', '2025-07-06'],
  ['2025-07-13', '2025-07-21'], ['2025-07-30', '2025-08-04'],
  ['2025-08-11', '2025-08-17'], ['2025-08-22', '2025-08-25'],
  ['2025-09-04', '2025-09-09'], ['2025-09-11', '2025-09-16'],
  ['2025-11-07', '2025-11-10'], ['2025-11-21', '2025-11-24'],
  ['2025-12-02', '2025-12-29'], ['2026-01-16', '2026-01-19'],
  ['2026-01-23', '2026-01-26'], ['2026-02-05', '2026-02-18'],
  ['2026-02-20', '2026-02-23'], ['2026-03-06', '2026-03-09'],
  ['2026-03-14', '2026-03-16'], ['2026-03-28', '2026-03-30'],
  ['2026-04-01', '2026-04-07'], ['2026-04-10', '2026-04-13'],
  ['2026-04-17', '2026-04-20'], ['2026-05-01', '2026-05-10'],
  ['2026-11-21', '2026-12-31'],
];

// ── Helper: generate daily date strings ──────────────────────────────────────
function generateTimeline(start, end) {
  const dates = [];
  const d = new Date(start + 'T00:00:00');
  const endD = new Date(end + 'T00:00:00');
  while (d <= endD) {
    dates.push(new Date(d));
    d.setDate(d.getDate() + 1);
  }
  return dates;
}

// ── Pre-compute timeline and base absences (runs once) ───────────────────────
const TIMELINE = generateTimeline(START_DATE, END_DATE);
const TOTAL_DAYS = TIMELINE.length;

// Date strings for Plotly x-axis (YYYY-MM-DD format)
const DATE_STRINGS = TIMELINE.map(
  (d) => d.toISOString().slice(0, 10)
);

// Base daily absences from historical trips (computed once)
const BASE_ABSENCES = new Int8Array(TOTAL_DAYS);
BASE_TRIPS.forEach(([tripStart, tripEnd]) => {
  const start = new Date(tripStart + 'T00:00:00');
  const end = new Date(tripEnd + 'T00:00:00');
  for (let i = 0; i < TOTAL_DAYS; i++) {
    if (TIMELINE[i] > start && TIMELINE[i] < end) {
      BASE_ABSENCES[i] = 1;
    }
  }
});

// Pre-compute ILR slider start indices
const IDX_2026 = TIMELINE.findIndex(
  (d) => d >= new Date(SLIDER_2026_START + 'T00:00:00')
);
const IDX_2027 = TIMELINE.findIndex(
  (d) => d >= new Date(SLIDER_2027_START + 'T00:00:00')
);

// Pre-compute Citizenship slider start indices (independent)
const CIT_IDX_2026 = TIMELINE.findIndex(
  (d) => d >= new Date(CIT_SLIDER_2026_START + 'T00:00:00')
);
const CIT_IDX_2027 = TIMELINE.findIndex(
  (d) => d >= new Date(CIT_SLIDER_2027_START + 'T00:00:00')
);
const CIT_IDX_2028 = TIMELINE.findIndex(
  (d) => d >= new Date(CIT_SLIDER_2028_START + 'T00:00:00')
);

// ── Pre-compute prefix sums for the base absences ────────────────────────────
// prefix[i] = sum of BASE_ABSENCES[0..i-1], prefix[0] = 0
const BASE_PREFIX = new Int32Array(TOTAL_DAYS + 1);
for (let i = 0; i < TOTAL_DAYS; i++) {
  BASE_PREFIX[i + 1] = BASE_PREFIX[i] + BASE_ABSENCES[i];
}

// ── Main App component ───────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState('ilr');

  // Chart DOM refs — Plotly.react() updates in-place, no re-mount
  const ilrChartRef = useRef(null);
  const citChartRef = useRef(null);

  // ── ILR tab: independent sliders ─────────────────────────────────────────
  const [ilr2026, setIlr2026] = useState(20);
  const [ilr2027, setIlr2027] = useState(45);

  // ── Citizenship tab: independent sliders ─────────────────────────────────
  const [cit2026, setCit2026] = useState(20);
  const [cit2027, setCit2027] = useState(45);
  const [cit2028, setCit2028] = useState(30);

  // ── ILR calculation ───────────────────────────────────────────────────────
  const { rolling365, peak, peakDate } = useMemo(() => {
    const absences = new Int8Array(BASE_ABSENCES);

    let applied = 0;
    for (let i = IDX_2026; i < TOTAL_DAYS && applied < ilr2026; i++) {
      absences[i] = 1; applied++;
    }
    applied = 0;
    for (let i = IDX_2027; i < TOTAL_DAYS && applied < ilr2027; i++) {
      absences[i] = 1; applied++;
    }

    const prefix = new Int32Array(TOTAL_DAYS + 1);
    for (let i = 0; i < TOTAL_DAYS; i++) prefix[i + 1] = prefix[i] + absences[i];

    const rolling = new Int32Array(TOTAL_DAYS);
    let maxPeak = 0;
    let peakIdx = 0;
    for (let i = 0; i < TOTAL_DAYS; i++) {
      const ws = Math.max(0, i - 364);
      rolling[i] = prefix[i + 1] - prefix[ws];
      if (rolling[i] > maxPeak) { maxPeak = rolling[i]; peakIdx = i; }
    }

    return { rolling365: Array.from(rolling), peak: maxPeak, peakDate: DATE_STRINGS[peakIdx] };
  }, [ilr2026, ilr2027]);

  // ── Citizenship calculation ───────────────────────────────────────────────
  const { citRolling365, citMetricA, citMetricB } = useMemo(() => {
    const absences = new Int8Array(BASE_ABSENCES);

    let applied = 0;
    for (let i = CIT_IDX_2026; i < TOTAL_DAYS && applied < cit2026; i++) {
      absences[i] = 1; applied++;
    }
    applied = 0;
    for (let i = CIT_IDX_2027; i < TOTAL_DAYS && applied < cit2027; i++) {
      absences[i] = 1; applied++;
    }
    applied = 0;
    for (let i = CIT_IDX_2028; i < TOTAL_DAYS && applied < cit2028; i++) {
      absences[i] = 1; applied++;
    }

    const prefix = new Int32Array(TOTAL_DAYS + 1);
    for (let i = 0; i < TOTAL_DAYS; i++) prefix[i + 1] = prefix[i] + absences[i];

    const rolling = new Int32Array(TOTAL_DAYS);
    for (let i = 0; i < TOTAL_DAYS; i++) {
      const ws = Math.max(0, i - 364);
      rolling[i] = prefix[i + 1] - prefix[ws];
    }

    const cit5yrStart = new Date(CITIZENSHIP_5YR_START + 'T00:00:00');
    const cit5yrEnd   = new Date(CITIZENSHIP_5YR_END   + 'T00:00:00');
    const cit12mStart = new Date(CITIZENSHIP_12M_START + 'T00:00:00');
    const cit12mEnd   = new Date(CITIZENSHIP_12M_END   + 'T00:00:00');

    let metricA = 0, metricB = 0;
    for (let i = 0; i < TOTAL_DAYS; i++) {
      if (TIMELINE[i] > cit5yrStart && TIMELINE[i] < cit5yrEnd) metricA += absences[i];
      if (TIMELINE[i] > cit12mStart && TIMELINE[i] < cit12mEnd) metricB += absences[i];
    }

    return { citRolling365: Array.from(rolling), citMetricA: metricA, citMetricB: metricB };
  }, [cit2026, cit2027, cit2028]);

  // ILR status logic
  let statusLabel, statusClass, deltaClass;
  const delta = peak - UKVI_LIMIT;
  if (peak >= UKVI_LIMIT) {
    statusLabel = '🚨 LIMIT EXCEEDED';
    statusClass = 'status-danger';
    deltaClass = 'delta-danger';
  } else if (peak >= 150) {
    statusLabel = '⚠️ Warning Zone';
    statusClass = 'status-warning';
    deltaClass = 'delta-warning';
  } else {
    statusLabel = '✅ Safe';
    statusClass = 'status-safe';
    deltaClass = 'delta-safe';
  }

  // Citizenship status
  const citAStatus = citMetricA > CITIZENSHIP_5YR_LIMIT ? 'exceeded' : citMetricA > 400 ? 'warning' : 'safe';
  const citBStatus = citMetricB > CITIZENSHIP_12M_LIMIT ? 'exceeded' : citMetricB > 75 ? 'warning' : 'safe';

  // Today marker
  const todayStr = new Date().toISOString().slice(0, 10);

  // ── ILR Chart (Plotly via CDN) ────────────────────────────────────────────
  useEffect(() => {
    if (!ilrChartRef.current || !window.Plotly) return;
    window.Plotly.react(
      ilrChartRef.current,
      [
        {
          x: DATE_STRINGS, y: rolling365, type: 'scatter', mode: 'lines',
          name: 'Rolling 365-Day Absences',
          line: { color: '#2b6cb0', width: 2 },
          fill: 'tozeroy', fillcolor: 'rgba(43, 108, 176, 0.15)',
        },
        {
          x: [DATE_STRINGS[0], DATE_STRINGS[DATE_STRINGS.length - 1]],
          y: [UKVI_LIMIT, UKVI_LIMIT], type: 'scatter', mode: 'lines',
          name: 'UKVI Limit (180)',
          line: { color: '#e53e3e', width: 2, dash: 'dash' },
        },
      ],
      {
        title: 'Rolling 365-Day UK Absences — ILR',
        xaxis: {
          title: 'Date', rangeslider: { visible: true },
          rangeselector: { buttons: [
            { count: 1, label: '1m', step: 'month', stepmode: 'backward' },
            { count: 6, label: '6m', step: 'month', stepmode: 'backward' },
            { count: 1, label: '1y', step: 'year', stepmode: 'backward' },
            { step: 'all', label: 'All' },
          ]},
        },
        yaxis: { title: 'Days Absent (rolling 365-day window)', range: [0, 200] },
        shapes: [
          { type: 'line', x0: todayStr, x1: todayStr, y0: 0, y1: 200,
            line: { color: '#a0aec0', width: 1.5, dash: 'dot' } },
          { type: 'rect',
            x0: new Date(new Date(peakDate + 'T00:00:00').getTime() - 4 * 86400000).toISOString().slice(0, 10),
            x1: new Date(new Date(peakDate + 'T00:00:00').getTime() + 4 * 86400000).toISOString().slice(0, 10),
            y0: 0, y1: 200,
            fillcolor: 'rgba(229, 62, 62, 0.18)',
            line: { color: 'rgba(229, 62, 62, 0.6)', width: 1 } },
        ],
        annotations: [
          { x: todayStr, y: 195, text: 'Today', showarrow: false,
            font: { color: '#718096', size: 11 } },
          { x: peakDate, y: 205, text: `Peak: ${peak}d`, showarrow: true,
            arrowhead: 2, arrowcolor: '#e53e3e', arrowsize: 1,
            font: { color: '#e53e3e', size: 11, weight: 'bold' },
            ax: 0, ay: -28 },
        ],
        hovermode: 'x unified',
        legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'right', x: 1 },
        margin: { t: 60, b: 40, l: 60, r: 20 },
        autosize: true,
      },
      { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] }
    );
  }, [rolling365, peakDate, activeTab]);

  // ── Citizenship Chart (Plotly via CDN) ────────────────────────────────────
  useEffect(() => {
    if (!citChartRef.current || !window.Plotly) return;
    window.Plotly.react(
      citChartRef.current,
      [
        {
          x: DATE_STRINGS, y: citRolling365, type: 'scatter', mode: 'lines',
          name: 'Rolling 365-Day Absences',
          line: { color: '#6b46c1', width: 2 },
          fill: 'tozeroy', fillcolor: 'rgba(107, 70, 193, 0.15)',
        },
        {
          x: [DATE_STRINGS[0], DATE_STRINGS[DATE_STRINGS.length - 1]],
          y: [UKVI_LIMIT, UKVI_LIMIT], type: 'scatter', mode: 'lines',
          name: 'ILR Limit (180)',
          line: { color: '#e53e3e', width: 1.5, dash: 'dash' },
        },
      ],
      {
        title: 'Rolling 365-Day UK Absences — Citizenship',
        xaxis: {
          title: 'Date', rangeslider: { visible: true },
          rangeselector: { buttons: [
            { count: 1, label: '1m', step: 'month', stepmode: 'backward' },
            { count: 6, label: '6m', step: 'month', stepmode: 'backward' },
            { count: 1, label: '1y', step: 'year', stepmode: 'backward' },
            { step: 'all', label: 'All' },
          ]},
        },
        yaxis: { title: 'Days Absent (rolling 365-day window)', range: [0, 200] },
        shapes: [{ type: 'line', x0: todayStr, x1: todayStr, y0: 0, y1: 200,
          line: { color: '#a0aec0', width: 1.5, dash: 'dot' } }],
        annotations: [{ x: todayStr, y: 195, text: 'Today', showarrow: false,
          font: { color: '#718096', size: 11 } }],
        hovermode: 'x unified',
        legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'right', x: 1 },
        margin: { t: 60, b: 40, l: 60, r: 20 },
        autosize: true,
      },
      { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] }
    );
  }, [citRolling365, activeTab]);

  return (
    <div className="container">
      <h1>🇬🇧 UK ILR Absence Tracker</h1>
      <p className="subtitle">
        Tracks absences from the UK against the UKVI limit of <strong>180 days</strong> in any
        rolling 365-day period.
      </p>

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab ${activeTab === 'ilr' ? 'tab-active' : ''}`} onClick={() => setActiveTab('ilr')}>
          📊 ILR Tracker
        </button>
        <button className={`tab ${activeTab === 'citizenship' ? 'tab-active' : ''}`} onClick={() => setActiveTab('citizenship')}>
          🏛️ Citizenship Check
        </button>
      </div>

      {/* Tab 1: ILR Tracker */}
      {activeTab === 'ilr' && (
        <>
          {/* ILR Sliders */}
          <div className="controls">
            <h2>Projected Future Travel</h2>
            <div className="control-group">
              <div className="control-label">
                <span>Extra 2026 Travel Days (Starts May 11, 2026)</span>
                <span className="slider-value">{ilr2026} Days</span>
              </div>
              <input type="range" min={0} max={100} value={ilr2026}
                onChange={(e) => setIlr2026(Number(e.target.value))} />
            </div>
            <div className="control-group">
              <div className="control-label">
                <span>2027 Travel Days (Starts Apr 25, 2027)</span>
                <span className="slider-value">{ilr2027} Days</span>
              </div>
              <input type="range" min={0} max={180} value={ilr2027}
                onChange={(e) => setIlr2027(Number(e.target.value))} />
            </div>
          </div>

          {/* Dashboard cards */}
          <div className="dashboard">
            <div className="card">
              <h3>UKVI Limit</h3>
              <div className="value">180 Days</div>
            </div>
            <div className="card">
              <h3>Max Rolling Peak</h3>
              <div className={`value ${peak >= UKVI_LIMIT ? 'status-danger' : ''}`}>
                {peak} Days
              </div>
              <div className={`delta ${deltaClass}`}>
                {delta >= 0 ? '+' : ''}{delta} vs limit
              </div>
              <div className="peak-date">📅 {peakDate}</div>
            </div>
            <div className="card">
              <h3>Status</h3>
              <div className={`value ${statusClass}`} style={{ fontSize: 24 }}>
                {statusLabel}
              </div>
            </div>
          </div>

          {/* ILR Chart */}
          <div className="chart-container">
            <div ref={ilrChartRef} style={{ width: '100%', height: '550px' }} />
          </div>
        </>
      )}

      {/* Tab 2: Citizenship Check */}
      {activeTab === 'citizenship' && (
        <>
          {/* Citizenship Sliders — independent from ILR */}
          <div className="controls">
            <h2>Projected Future Travel</h2>
            <div className="control-group">
              <div className="control-label">
                <span>Extra 2026 Travel Days (Starts May 11, 2026)</span>
                <span className="slider-value">{cit2026} Days</span>
              </div>
              <input type="range" min={0} max={100} value={cit2026}
                onChange={(e) => setCit2026(Number(e.target.value))} />
            </div>
            <div className="control-group">
              <div className="control-label">
                <span>2027 Travel Days (Starts Apr 25, 2027)</span>
                <span className="slider-value">{cit2027} Days</span>
              </div>
              <input type="range" min={0} max={180} value={cit2027}
                onChange={(e) => setCit2027(Number(e.target.value))} />
            </div>
            <div className="control-group">
              <div className="control-label">
                <span>2028 Travel Days (Starts Jan 1, 2028)</span>
                <span className="slider-value">{cit2028} Days</span>
              </div>
              <input type="range" min={0} max={180} value={cit2028}
                onChange={(e) => setCit2028(Number(e.target.value))} />
            </div>
          </div>

          <div className="citizenship-section">
            <p className="citizenship-note">
              UK citizenship requires no more than <strong>450 days</strong> absence in the 5-year
              qualifying period (24 Oct 2023 – 24 Oct 2028) and no more than <strong>90 days</strong> absence
              in the final 12 months (24 Oct 2027 – 24 Oct 2028).
            </p>

            {/* Metric A: 5-Year Window */}
            <div className="cit-card">
              <div className="cit-header">
                <h3>Total Absences — 5-Year Window</h3>
                <span className="cit-period">24 Oct 2023 → 24 Oct 2028</span>
              </div>
              <div className="cit-metrics">
                <div className={`cit-value ${citAStatus === 'exceeded' ? 'status-danger' : citAStatus === 'warning' ? 'status-warning' : 'status-safe'}`}>
                  {citMetricA} <span className="cit-unit">/ 450 days</span>
                </div>
                <div className={`cit-delta ${citAStatus === 'exceeded' ? 'delta-danger' : citAStatus === 'warning' ? 'delta-warning' : 'delta-safe'}`}>
                  {citMetricA <= CITIZENSHIP_5YR_LIMIT
                    ? `${CITIZENSHIP_5YR_LIMIT - citMetricA} days remaining`
                    : `${citMetricA - CITIZENSHIP_5YR_LIMIT} days over limit`}
                </div>
              </div>
              <div className="progress-bar-container">
                <div
                  className={`progress-bar ${citAStatus === 'exceeded' ? 'progress-danger' : citAStatus === 'warning' ? 'progress-warning' : 'progress-safe'}`}
                  style={{ width: `${Math.min((citMetricA / CITIZENSHIP_5YR_LIMIT) * 100, 100)}%` }}
                />
              </div>
            </div>

            {/* Metric B: Final 12 Months */}
            <div className="cit-card">
              <div className="cit-header">
                <h3>Total Absences — Final 12 Months</h3>
                <span className="cit-period">24 Oct 2027 → 24 Oct 2028</span>
              </div>
              <div className="cit-metrics">
                <div className={`cit-value ${citBStatus === 'exceeded' ? 'status-danger' : citBStatus === 'warning' ? 'status-warning' : 'status-safe'}`}>
                  {citMetricB} <span className="cit-unit">/ 90 days</span>
                </div>
                <div className={`cit-delta ${citBStatus === 'exceeded' ? 'delta-danger' : citBStatus === 'warning' ? 'delta-warning' : 'delta-safe'}`}>
                  {citMetricB <= CITIZENSHIP_12M_LIMIT
                    ? `${CITIZENSHIP_12M_LIMIT - citMetricB} days remaining`
                    : `${citMetricB - CITIZENSHIP_12M_LIMIT} days over limit`}
                </div>
              </div>
              <div className="progress-bar-container">
                <div
                  className={`progress-bar ${citBStatus === 'exceeded' ? 'progress-danger' : citBStatus === 'warning' ? 'progress-warning' : 'progress-safe'}`}
                  style={{ width: `${Math.min((citMetricB / CITIZENSHIP_12M_LIMIT) * 100, 100)}%` }}
                />
              </div>
            </div>

            {/* Overall Citizenship Status */}
            <div className={`cit-status-banner ${
              citAStatus === 'exceeded' || citBStatus === 'exceeded' ? 'banner-danger'
              : citAStatus === 'warning' || citBStatus === 'warning' ? 'banner-warning'
              : 'banner-safe'
            }`}>
              {citAStatus === 'exceeded' || citBStatus === 'exceeded'
                ? '🚨 CITIZENSHIP ELIGIBILITY AT RISK — Absence limit exceeded'
                : citAStatus === 'warning' || citBStatus === 'warning'
                ? '⚠️ WARNING — Approaching absence limit'
                : '✅ ON TRACK — Within citizenship absence limits'}
            </div>

            {/* Citizenship Chart */}
            <div className="chart-container">
              <div ref={citChartRef} style={{ width: '100%', height: '550px' }} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
