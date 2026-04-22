# 🇬🇧 UK ILR Absence Tracker

A React + Flask app to track UK absences and ensure compliance with UKVI limits for ILR and Citizenship eligibility.

## Running the App

### Quick Start

```bash
cd /Users/krish-mac/VSCode-Projects/ILR-tracker
./start.sh
```

Then open **http://localhost:5001** in your browser.

### Manual Start

**1. Build the frontend (only needed once, or after code changes):**
```bash
cd frontend && npm run build
```

**2. Start the backend:**
```bash
cd backend && python app.py
```

---

## Troubleshooting

### App stuck / not loading

Multiple zombie Flask processes may be piling up on port 5001. Kill them all before restarting:

```bash
lsof -ti:5001 | xargs kill -9 2>/dev/null; true
cd backend && python app.py
```

### Terminal stuck / commands not running

If a previous command left the terminal in a stuck heredoc state (waiting for `EOF`), open a **new terminal** and run the restart commands there.

---

## Tech Stack

- **Frontend:** React 18 + Vite + Plotly.js (loaded from CDN)
- **Backend:** Flask (serves the React build + `/api/config`)

## Limits

| Rule | Limit |
|------|-------|
| ILR – Rolling 365-day window | 180 days |
| Citizenship – 5-year window (Oct 2023 – Oct 2028) | 450 days |
| Citizenship – Final 12 months (Oct 2027 – Oct 2028) | 90 days |
