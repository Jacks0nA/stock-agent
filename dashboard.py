import streamlit as st
import time
import os
import json
import httpx
from datetime import datetime, timezone, timedelta
from fetcher import fetch_stock_data, fetch_historical_data
from agent import analyse_stocks
from news import fetch_stock_news
from earnings import get_earnings_calendar, get_earnings_summary
from sectors import get_market_context, get_market_summary
from screener import run_screen
from insider import get_insider_summary
from options import get_options_summary
from logger import save_daily_log, get_all_dates, get_log_for_date_window, read_log_file, delete_date_logs
from portfolio import (
    get_portfolio_balance, get_open_positions, get_closed_positions,
    get_current_prices, STARTING_BALANCE
)
from dotenv import load_dotenv
import subprocess

load_dotenv()

GMT = timezone.utc

DAILY_WINDOWS = [
    {"name": "US Market Open", "hour": 14, "minute": 30},
    {"name": "US Midday", "hour": 18, "minute": 30},
    {"name": "US Pre-Close", "hour": 20, "minute": 30},
]

def get_headers():
    return {
        "apikey": os.getenv("SUPABASE_KEY"),
        "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def get_base_url():
    return os.getenv("SUPABASE_URL")

def load_schedule_state():
    try:
        url = f"{get_base_url()}/rest/v1/schedule_state?select=*"
        response = httpx.get(url, headers=get_headers())
        state = {"last_run_windows": {}}
        for row in response.json():
            if row["key"].startswith("window_"):
                state["last_run_windows"][row["key"][7:]] = row["value"]
        return state
    except Exception:
        return {"last_run_windows": {}}

def save_schedule_state(state):
    try:
        url = f"{get_base_url()}/rest/v1/schedule_state"
        for key, value in state.get("last_run_windows", {}).items():
            httpx.post(url, headers=get_headers(), json={
                "key": f"window_{key}",
                "value": value
            })
    except Exception as e:
        print(f"Schedule state save error: {e}")
def get_enhanced_news_setting():
    try:
        url = f"{get_base_url()}/rest/v1/portfolio_state?key=eq.enhanced_news"
        response = httpx.get(url, headers=get_headers())
        data = response.json()
        if data:
            return data[0]["value"] == "true"
        return False
    except Exception:
        return False

def set_enhanced_news_setting(enabled):
    try:
        url = f"{get_base_url()}/rest/v1/portfolio_state"
        httpx.post(url, headers=get_headers(), json={
            "key": "enhanced_news",
            "value": "true" if enabled else "false"
        })
    except Exception as e:
        print(f"Enhanced news setting error: {e}")

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
    tomorrow = (now + timedelta(days=1)).replace(
        hour=DAILY_WINDOWS[0]["hour"],
        minute=DAILY_WINDOWS[0]["minute"],
        second=0, microsecond=0
    )
    return DAILY_WINDOWS[0], tomorrow

def mark_window_complete(missed_window):
    state = load_schedule_state()
    today = datetime.now(GMT).strftime("%Y-%m-%d")
    for window in DAILY_WINDOWS:
        key = get_window_key(window, today)
        if key not in state.get("last_run_windows", {}):
            state.setdefault("last_run_windows", {})[key] = "skipped"
    save_schedule_state(state)

def mark_window_complete(window):
    state = load_schedule_state()
    today = datetime.now(GMT).strftime("%Y-%m-%d")
    key = get_window_key(window, today)
    state.setdefault("last_run_windows", {})[key] = datetime.now(GMT).strftime("%Y-%m-%d %H:%M")
    save_schedule_state(state)

def is_market_open():
    now = datetime.now(GMT)
    market_open = now.replace(hour=13, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=20, minute=0, second=0, microsecond=0)
    is_weekend = now.weekday() >= 5
    return not is_weekend and market_open <= now <= market_close

def run_full_analysis(mode="Manual", market_is_open=True):
    with st.spinner("Stage 1 — Screening assets..."):
        shortlist, market_regime = run_screen()

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
        if get_enhanced_news_setting():
            from news_enhanced import fetch_stock_news_enhanced
            news = fetch_stock_news_enhanced(tickers)
            st.sidebar.caption("Enhanced news active")
        else:
            news = fetch_stock_news(tickers)

    if not market_is_open:
        st.info("Markets are currently closed — analysis running but no new positions will be opened.")

    with st.spinner(f"Claude analysing — {mode} mode..."):
        analysis = analyse_stocks(
            df, news, historical, earnings,
            market_context, insider_summary, options_summary,
            market_is_open=market_is_open
        )

    st.subheader("Claude's Analysis")
    st.write(analysis)

    log_file = save_daily_log(analysis, mode=mode, tickers=tickers)
    st.success(f"Saved to {log_file}")

    return analysis, tickers

# Version
try:
    git_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
except Exception:
    git_hash = "unknown"

st.title("AI Stock Market Agent")
st.caption(f"Build {git_hash} — Manual and Daily modes — Active mode coming when you start trading")

st.sidebar.title("Mode")
mode = st.sidebar.radio(
    "Select mode",
    ["Manual", "Daily"],
    help="Manual: run on demand. Daily: auto-runs at US market windows."
)

st.sidebar.divider()
enhanced_news_enabled = get_enhanced_news_setting()
enhanced_toggle = st.sidebar.toggle(
    "Enhanced News",
    value=enhanced_news_enabled,
    help="Adds Reuters RSS, article summaries, recency weighting and earnings context. Increases cost by ~4p per analysis."
)
if enhanced_toggle != enhanced_news_enabled:
    set_enhanced_news_setting(enhanced_toggle)
    st.rerun()
now_gmt = datetime.now(GMT)
st.sidebar.caption(f"Current time: {now_gmt.strftime('%H:%M GMT')}")

next_window, next_time = get_next_window()
time_until = next_time - now_gmt
hours_until = int(time_until.total_seconds() // 3600)
mins_until = int((time_until.total_seconds() % 3600) // 60)
st.sidebar.info(f"Next window: {next_window['name']}\n{next_time.strftime('%H:%M GMT')} — in {hours_until}h {mins_until}m")

tab1, tab2, tab3 = st.tabs(["Analysis", "Portfolio", "Logs"])

with tab1:
    if mode == "Manual":
        st.info("Manual mode — press the button to run one analysis.")
        if st.button("Run Analysis Now", type="primary"):
            now = datetime.now(GMT)
            market_open = now.replace(hour=13, minute=30, second=0, microsecond=0)
            market_close = now.replace(hour=20, minute=0, second=0, microsecond=0)
            is_weekend = now.weekday() >= 5
            market_open_flag = not is_weekend and market_open <= now <= market_close
            if is_weekend:
                st.warning("Markets are closed — it's the weekend. Analysis will run but no new positions will be opened.")
            elif now < market_open or now > market_close:
                st.warning("US markets are currently closed. Analysis will run but no new positions will be opened.")
            run_full_analysis(mode="Manual", market_is_open=market_open_flag)

    elif mode == "Daily":
        st.info("Daily mode — auto-runs at US market open (14:30), midday (18:30), and pre-close (20:30) GMT.")

        missed_window, missed_time = get_missed_window()

        if missed_window:
            mins_ago = int((now_gmt - missed_time).total_seconds() / 60)
            st.warning(f"Missed window detected: {missed_window['name']} ({missed_time.strftime('%H:%M GMT')} — {mins_ago} mins ago). Running now...")
            now_check = datetime.now(GMT)
            market_open_check = now_check.replace(hour=13, minute=30, second=0, microsecond=0)
            market_close_check = now_check.replace(hour=20, minute=0, second=0, microsecond=0)
            is_weekend_check = now_check.weekday() >= 5
            market_open_flag = not is_weekend_check and market_open_check <= now_check <= market_close_check
            run_full_analysis(mode=f"Daily — {missed_window['name']}", market_is_open=market_open_flag)
            mark_window_complete(missed_window)
            st.rerun()
        else:
            st.success("All windows for today are complete or not yet due.")
            st.write("The app will auto-run when you open it during a scheduled window.")
            if st.button("Run Manual Check Now", type="secondary"):
                run_full_analysis(mode="Manual", market_is_open=is_market_open())

with tab2:
    st.subheader("Paper Trading Portfolio")

    balance = get_portfolio_balance()
    open_positions = get_open_positions()
    closed_positions = get_closed_positions()

    total_invested = sum(float(p["position_size"]) for p in open_positions)
    total_pnl = sum(float(p["pnl"]) for p in closed_positions if p["pnl"])
    total_value = balance + total_invested
    total_return_pct = round(((total_value - STARTING_BALANCE) / STARTING_BALANCE) * 100, 2)
    total_trades = len(closed_positions)
    winning_trades = len([p for p in closed_positions if p["pnl"] and float(p["pnl"]) > 0])
    win_rate = round(winning_trades / total_trades * 100, 1) if total_trades > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Portfolio Value", f"£{round(total_value, 2)}", f"{total_return_pct}%")
    col2.metric("Cash Available", f"£{round(balance, 2)}")
    col3.metric("Invested", f"£{round(total_invested, 2)}")
    col4.metric("Win Rate", f"{win_rate}%", f"{total_trades} trades")

    st.divider()

    st.subheader(f"Open Positions ({len(open_positions)}/5)")
    if not open_positions:
        st.info("No open positions — Claude will open positions when high quality setups appear.")
    else:
        tickers = [p["ticker"] for p in open_positions]
        current_prices = get_current_prices(tickers)
        for p in open_positions:
            ticker = p["ticker"]
            current = current_prices.get(ticker, float(p["entry_price"]))
            entry = float(p["entry_price"])
            target = float(p["target_price"])
            stop = float(p["stop_loss"])
            size = float(p["position_size"])
            unrealised_pct = round(((current - entry) / entry) * 100, 2)
            unrealised_gbp = round(size * (unrealised_pct / 100), 2)
            colour = "🟢" if unrealised_pct >= 0 else "🔴"

            with st.expander(f"{colour} {ticker} — {unrealised_pct}% (£{unrealised_gbp}) — {p['confidence']}"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Entry", f"${entry}")
                col1.metric("Current", f"${current}")
                col2.metric("Target", f"${target}")
                col2.metric("Stop Loss", f"${stop}")
                col3.metric("Size", f"£{size}")
                col3.metric("Opened", p["opened_at"])
                st.caption(f"Reasoning: {p['claude_reasoning']}")

    st.divider()

    st.subheader("Closed Trades")
    if not closed_positions:
        st.info("No closed trades yet.")
    else:
        total_gain = sum(float(p["pnl"]) for p in closed_positions if p["pnl"] and float(p["pnl"]) > 0)
        total_loss = sum(float(p["pnl"]) for p in closed_positions if p["pnl"] and float(p["pnl"]) < 0)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total P&L", f"£{round(total_pnl, 2)}")
        col2.metric("Total Gains", f"£{round(total_gain, 2)}")
        col3.metric("Total Losses", f"£{round(total_loss, 2)}")

        for p in closed_positions[:20]:
            pnl = float(p["pnl"]) if p["pnl"] else 0
            pnl_pct = float(p["pnl_pct"]) if p["pnl_pct"] else 0
            colour = "🟢" if pnl >= 0 else "🔴"
            with st.expander(f"{colour} {p['ticker']} — £{round(pnl, 2)} ({round(pnl_pct, 2)}%) — {p['closed_at']}"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Entry", f"${p['entry_price']}")
                col1.metric("Exit", f"${p['exit_price']}")
                col2.metric("P&L", f"£{round(pnl, 2)}")
                col2.metric("Return", f"{round(pnl_pct, 2)}%")
                col3.metric("Size", f"£{p['position_size']}")
                col3.metric("Confidence", p["confidence"])
                st.caption(f"Reasoning: {p['claude_reasoning']}")

with tab3:
    st.subheader("Analysis Logs")

    all_dates = get_all_dates()

    if not all_dates:
        st.info("No logs yet — run your first analysis to get started.")
    else:
        for date in all_dates:
            col_date, col_delete = st.columns([5, 1])

            with col_date:
                st.markdown(f"### 📅 {date}")

            with col_delete:
                if st.button("🗑️ Delete", key=f"delete_{date}"):
                    delete_date_logs(date)
                    st.success(f"Deleted logs for {date}")
                    st.rerun()

            opening_tab, midday_tab, closing_tab, manual_tab = st.tabs([
                "🔔 Opening", "☀️ Midday", "🔔 Pre-Close", "✋ Manual"
            ])

            with opening_tab:
                filepath = get_log_for_date_window(date, "opening")
                content = read_log_file(filepath)
                if content:
                    st.text(content)
                else:
                    st.caption("Window missed or not yet run.")

            with midday_tab:
                filepath = get_log_for_date_window(date, "midday")
                content = read_log_file(filepath)
                if content:
                    st.text(content)
                else:
                    st.caption("Window missed or not yet run.")

            with closing_tab:
                filepath = get_log_for_date_window(date, "closing")
                content = read_log_file(filepath)
                if content:
                    st.text(content)
                else:
                    st.caption("Window missed or not yet run.")

            with manual_tab:
                manual_logs = get_log_for_date_window(date, "manual") or []
                if manual_logs:
                    for i, filepath in enumerate(manual_logs):
                        content = read_log_file(filepath)
                        if content:
                            st.markdown(f"**Manual run {i+1}**")
                            st.text(content)
                else:
                    st.caption("No manual analyses run on this date.")

            st.divider()