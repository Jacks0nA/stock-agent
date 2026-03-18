import streamlit as st
import time
from datetime import datetime, timezone, timedelta
from fetcher import fetch_stock_data, fetch_historical_data
from agent import analyse_stocks
from news import fetch_stock_news
from earnings import get_earnings_calendar, get_earnings_summary
from sectors import get_market_context, get_market_summary
from screener import run_screen
from insider import get_insider_summary
from options import get_options_summary
from logger import save_daily_log, get_todays_log, list_recent_logs
import json
import os

SCHEDULE_FILE = "schedule_state.json"

GMT = timezone.utc

DAILY_WINDOWS = [
    {"name": "US Market Open", "hour": 14, "minute": 30},
    {"name": "US Midday", "hour": 18, "minute": 30},
    {"name": "US Pre-Close", "hour": 20, "minute": 30},
]

def load_schedule_state():
    if not os.path.exists(SCHEDULE_FILE):
        return {"last_run_windows": {}}
    with open(SCHEDULE_FILE, "r") as f:
        return json.load(f)

def save_schedule_state(state):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_window_key(window, date=None):
    if date is None:
        date = datetime.now(GMT).strftime("%Y-%m-%d")
    return f"{date}_{window['name'].replace(' ', '_')}"

def get_missed_window():
    now = datetime.now(GMT)
    today = now.strftime("%Y-%m-%d")
    state = load_schedule_state()
    last_run = state.get("last_run_windows", {})

    passed_windows = []
    for window in DAILY_WINDOWS:
        window_time = now.replace(hour=window["hour"], minute=window["minute"], second=0, microsecond=0)
        if now >= window_time:
            passed_windows.append((window, window_time))

    passed_windows.sort(key=lambda x: x[1], reverse=True)

    for window, window_time in passed_windows:
        key = get_window_key(window, today)
        if key not in last_run:
            return window, window_time

    return None, None

def get_next_window():
    now = datetime.now(GMT)
    for window in DAILY_WINDOWS:
        window_time = now.replace(hour=window["hour"], minute=window["minute"], second=0, microsecond=0)
        if window_time > now:
            return window, window_time
    tomorrow = (now + timedelta(days=1)).replace(hour=DAILY_WINDOWS[0]["hour"], minute=DAILY_WINDOWS[0]["minute"], second=0, microsecond=0)
    return DAILY_WINDOWS[0], tomorrow

def mark_window_complete(window):
    state = load_schedule_state()
    today = datetime.now(GMT).strftime("%Y-%m-%d")
    key = get_window_key(window, today)
    state.setdefault("last_run_windows", {})[key] = datetime.now(GMT).strftime("%Y-%m-%d %H:%M")
    save_schedule_state(state)

def run_full_analysis(mode="Manual"):
    with st.spinner("Stage 1 — Screening 125+ assets..."):
        shortlist = run_screen()

    tickers = [r["ticker"] for r in shortlist]

    buy_signals = [r for r in shortlist if r["signal"] == "BUY"]
    avoid_signals = [r for r in shortlist if r["signal"] == "AVOID"]
    watch_signals = [r for r in shortlist if r["signal"] == "WATCH"]

    col1, col2, col3 = st.columns(3)
    col1.metric("🟢 Buy", len(buy_signals))
    col2.metric("🔴 Avoid", len(avoid_signals))
    col3.metric("⚪ Watch", len(watch_signals))

    st.subheader("Shortlisted Assets")
    for r in shortlist:
        emoji = "🟢" if r["signal"] == "BUY" else "🔴" if r["signal"] == "AVOID" else "⚪"
        st.write(f"{emoji} **{r['ticker']}** — ${r['price']} — Score: {r['score']} — {', '.join(r['reasons'])}")

    with st.spinner("Fetching market context..."):
        market_context = get_market_context()

    spy = market_context.get("SPY")
    qqq = market_context.get("QQQ")
    xle = market_context.get("XLE")
    col1, col2, col3 = st.columns(3)
    if spy:
        col1.metric("S&P 500", f"${spy['price']}", f"{spy['change_percent']}%")
    if qqq:
        col2.metric("NASDAQ", f"${qqq['price']}", f"{qqq['change_percent']}%")
    if xle:
        col3.metric("Energy", f"${xle['price']}", f"{xle['change_percent']}%")

    with st.spinner("Fetching live prices..."):
        df = fetch_stock_data(tickers)
    st.dataframe(df)

    with st.spinner("Fetching technical indicators..."):
        historical = fetch_historical_data(tickers)

    with st.spinner("Checking earnings..."):
        earnings = get_earnings_calendar(tickers)
    earnings_summary = get_earnings_summary(earnings)
    if "No earnings" not in earnings_summary:
        st.warning(earnings_summary)

    with st.spinner("Fetching options flow..."):
        options_summary = get_options_summary(tickers)

    with st.spinner("Checking insider activity..."):
        insider_summary = get_insider_summary(tickers)

    with st.spinner("Fetching news..."):
        news = fetch_stock_news(tickers)

    with st.spinner(f"Claude analysing — {mode} mode..."):
        analysis = analyse_stocks(df, news, historical, earnings, market_context, insider_summary, options_summary)

    st.subheader("Claude's Analysis")
    st.write(analysis)

    log_file = save_daily_log(analysis, mode=mode, tickers=tickers)
    st.success(f"Saved to {log_file}")

    return analysis, tickers

st.title("AI Stock Market Agent")
st.caption("Manual and Daily modes — Active mode coming when you start trading")

st.sidebar.title("Mode")

mode = st.sidebar.radio(
    "Select mode",
    ["Manual", "Daily"],
    help="Manual: run on demand. Daily: auto-runs at US market windows."
)

st.sidebar.divider()

now_gmt = datetime.now(GMT)
st.sidebar.caption(f"Current time: {now_gmt.strftime('%H:%M GMT')}")

next_window, next_time = get_next_window()
time_until = next_time - now_gmt
hours_until = int(time_until.total_seconds() // 3600)
mins_until = int((time_until.total_seconds() % 3600) // 60)
st.sidebar.info(f"Next window: {next_window['name']}\n{next_time.strftime('%H:%M GMT')} — in {hours_until}h {mins_until}m")

tab1, tab2 = st.tabs(["Analysis", "Today's Log"])

with tab1:
    if mode == "Manual":
        st.info("Manual mode — press the button to run one analysis.")
        if st.button("Run Analysis Now", type="primary"):
            run_full_analysis(mode="Manual")

    elif mode == "Daily":
        st.info("Daily mode — auto-runs at US market open (14:30), midday (18:30), and pre-close (20:30) GMT.")

        missed_window, missed_time = get_missed_window()

        if missed_window:
            mins_ago = int((now_gmt - missed_time).total_seconds() / 60)
            st.warning(f"Missed window detected: {missed_window['name']} ({missed_time.strftime('%H:%M GMT')} — {mins_ago} mins ago). Running now...")
            analysis, tickers = run_full_analysis(mode=f"Daily — {missed_window['name']}")
            mark_window_complete(missed_window)
            st.rerun()

        else:
            st.success("All windows for today are complete or not yet due.")
            st.write("The app will auto-run when you open it during a scheduled window.")

            if st.button("Run Manual Check Now", type="secondary"):
                run_full_analysis(mode="Manual")

with tab2:
    st.subheader("Today's Analysis Log")
    log_content = get_todays_log()
    st.text(log_content)

    st.subheader("Recent Log Files")
    recent_logs = list_recent_logs()
    for log_file in recent_logs:
        st.write(f"📄 logs/{log_file}")