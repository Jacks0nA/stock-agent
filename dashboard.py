import streamlit as st
import time
import os
import json
import httpx
import pandas as pd
import subprocess
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dotenv import load_dotenv
import pytz

# Set timezone explicitly to ensure consistency across all environments
os.environ['TZ'] = 'Europe/London'
try:
    import time as _time
    _time.tzset()
except (AttributeError, OSError):
    # tzset() not available on all systems (e.g., Windows), but that's fine
    pass

try:
    from streamlit_autorefresh import st_autorefresh
    autorefresh_available = True
except ImportError:
    autorefresh_available = False
    st_autorefresh = None

from fetcher import fetch_stock_data, fetch_historical_data
from agent import analyse_stocks
from news import fetch_stock_news
from earnings import get_earnings_calendar, get_earnings_summary
from sectors import get_market_context, get_market_summary
from screener import run_screen
from insider import get_insider_summary
from options import get_options_summary
from logger import save_daily_log, get_all_dates, get_log_for_date_window, read_log_file, delete_date_logs
from deep_dive import run_deep_dive
from portfolio import (
    get_portfolio_balance, get_open_positions, get_closed_positions,
    get_current_prices, STARTING_BALANCE
)

# Only auto-refresh when not running an analysis
if "analysis_running" not in st.session_state:
    st.session_state.analysis_running = False
if "analysis_start_time" not in st.session_state:
    st.session_state.analysis_start_time = None

# Auto-reset analysis flag after 6 minutes, then resume 60s refresh
if st.session_state.analysis_running and st.session_state.analysis_start_time:
    elapsed = (datetime.now(timezone.utc) - st.session_state.analysis_start_time).total_seconds()
    if elapsed > 360:  # 6 minutes = 360 seconds
        st.session_state.analysis_running = False
        st.session_state.analysis_start_time = None

if not st.session_state.analysis_running and autorefresh_available:
    st_autorefresh(interval=60000, key="autorefresh")

load_dotenv()

GMT = pytz.timezone("Europe/London")
ET = pytz.timezone("America/New_York")

def get_uk_time():
    """Get current time in UK timezone (handles DST automatically)"""
    utc_now = datetime.now(timezone.utc)
    # Explicitly convert UTC to Europe/London timezone
    uk_time = utc_now.astimezone(pytz.timezone('Europe/London'))
    return uk_time

def get_daily_windows():
    """Calculate market windows dynamically based on current DST status for both UK and US"""
    # Define US market times in ET
    market_times_et = [
        (9, 30, "US Market Open"),
        (13, 30, "US Midday"),
        (15, 30, "US Pre-Close"),
    ]

    windows = []
    now_utc = datetime.now(timezone.utc)

    for hour_et, minute_et, name in market_times_et:
        # Create a time in ET for today
        et_time = ET.localize(datetime(now_utc.year, now_utc.month, now_utc.day, hour_et, minute_et))
        # Convert to UTC then to UK timezone
        uk_time = et_time.astimezone(GMT)
        windows.append({
            "name": name,
            "hour": uk_time.hour,
            "minute": uk_time.minute,
        })

    return windows

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
        date = get_uk_time().strftime("%Y-%m-%d")
    return f"{date}_{window['name'].replace(' ', '_')}"

def get_missed_window():
    now = get_uk_time()
    today = now.strftime("%Y-%m-%d")
    state = load_schedule_state()
    last_run = state.get("last_run_windows", {})
    windows = get_daily_windows()

    passed_windows = []
    for window in windows:
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
    now = get_uk_time()
    windows = get_daily_windows()
    for window in windows:
        window_time = now.replace(hour=window["hour"], minute=window["minute"], second=0, microsecond=0)
        if window_time > now:
            return window, window_time
    tomorrow = (now + timedelta(days=1)).replace(
        hour=windows[0]["hour"],
        minute=windows[0]["minute"],
        second=0, microsecond=0
    )
    return windows[0], tomorrow

def mark_window_complete(window):
    state = load_schedule_state()
    today = get_uk_time().strftime("%Y-%m-%d")
    key = get_window_key(window, today)
    state.setdefault("last_run_windows", {})[key] = get_uk_time().strftime("%Y-%m-%d %H:%M")
    save_schedule_state(state)

def get_market_times_uk(date=None):
    """Get market open/close times in UK timezone for a given date"""
    if date is None:
        date = datetime.now(timezone.utc).date()

    # US market hours: 09:30 - 16:00 ET
    market_open_et = ET.localize(datetime(date.year, date.month, date.day, 9, 30))
    market_close_et = ET.localize(datetime(date.year, date.month, date.day, 16, 0))

    # Convert to UK timezone
    market_open_uk = market_open_et.astimezone(GMT)
    market_close_uk = market_close_et.astimezone(GMT)

    return market_open_uk, market_close_uk

def is_market_open():
    now = get_uk_time()
    market_open_uk, market_close_uk = get_market_times_uk(now.date())

    is_weekend = now.weekday() >= 5
    return not is_weekend and market_open_uk.replace(second=0, microsecond=0) <= now <= market_close_uk.replace(second=0, microsecond=0)

def get_portfolio_value_over_time(closed_positions):
    """Reconstruct portfolio value timeline from closed positions"""
    if not closed_positions:
        return pd.DataFrame({"Date": ["Today"], "Portfolio Value": [STARTING_BALANCE]})

    # Start with initial balance
    timeline = [{"Date": "Start", "Portfolio Value": STARTING_BALANCE}]

    # Sort by closed_at date
    sorted_positions = sorted(closed_positions, key=lambda p: p.get("closed_at", ""))

    cumulative_pnl = 0
    for pos in sorted_positions:
        pnl = float(pos.get("pnl", 0)) or 0
        cumulative_pnl += pnl
        date_str = pos.get("closed_at", "").split(" ")[0]  # Extract just the date
        timeline.append({"Date": date_str, "Portfolio Value": STARTING_BALANCE + cumulative_pnl})

    # Add current value as final point
    current_balance = get_portfolio_balance()
    open_positions = get_open_positions()
    total_invested = sum(float(p["position_size"]) for p in open_positions) if open_positions else 0
    current_value = current_balance + total_invested
    timeline.append({"Date": get_uk_time().strftime("%Y-%m-%d"), "Portfolio Value": current_value})

    return pd.DataFrame(timeline)

def get_win_rate_by_tier(closed_positions):
    """Calculate win rate for each confidence tier"""
    tiers = ["LOW", "MEDIUM", "CONFIDENT", "SUPER"]
    data = []

    for tier in tiers:
        tier_trades = [p for p in closed_positions if p.get("confidence") == tier]
        if tier_trades:
            wins = len([p for p in tier_trades if float(p.get("pnl", 0) or 0) > 0])
            win_rate = (wins / len(tier_trades) * 100) if tier_trades else 0
        else:
            win_rate = 0

        data.append({"Confidence": tier, "Win Rate %": round(win_rate, 1)})

    return pd.DataFrame(data)

def get_pnl_by_trade(closed_positions):
    """Prepare P&L data for bar chart (last 20 trades)"""
    trades = []
    for pos in closed_positions[-20:]:
        ticker = pos.get("ticker", "?")
        closed_at = pos.get("closed_at", "").split(" ")[0]
        pnl = float(pos.get("pnl", 0)) or 0
        trades.append({"Trade": f"{ticker} {closed_at}", "P&L £": pnl})

    return pd.DataFrame(trades[::-1])  # Reverse to show oldest first

def run_full_analysis(mode="Manual", market_is_open=True):
    st.session_state.analysis_running = True
    st.session_state.analysis_start_time = datetime.now(timezone.utc)
    try:
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
                market_is_open=market_is_open,
            )

        st.subheader("Claude's Analysis")
        st.write(analysis)

        log_file = save_daily_log(analysis, mode=mode, tickers=tickers)
        st.success(f"Saved to {log_file}")

        return analysis, tickers
    finally:
        st.session_state.analysis_running = False

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
now_gmt = get_uk_time()
tz_name = now_gmt.strftime('%Z')  # Get the actual timezone name (BST or GMT)
st.sidebar.caption(f"Current time: {now_gmt.strftime('%H:%M')} {tz_name}")

next_window, next_time = get_next_window()
time_until = next_time - now_gmt
hours_until = int(time_until.total_seconds() // 3600)
mins_until = int((time_until.total_seconds() % 3600) // 60)
st.sidebar.info(f"Next window: {next_window['name']}\n{next_time.strftime('%H:%M GMT')} — in {hours_until}h {mins_until}m")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Analysis", "Portfolio", "Logs", "Deep Dive", "Learning"])

with tab1:
    if mode == "Manual":
        st.info("Manual mode — press the button to run one analysis.")
        if st.button("Run Analysis Now", type="primary"):
            market_open_flag = is_market_open()
            now = get_uk_time()
            is_weekend = now.weekday() >= 5
            if is_weekend:
                st.warning("Markets are closed — it's the weekend. Analysis will run but no new positions will be opened.")
            elif not market_open_flag:
                st.warning("US markets are currently closed. Analysis will run but no new positions will be opened.")
            run_full_analysis(mode="Manual", market_is_open=market_open_flag)

    elif mode == "Daily":
        windows = get_daily_windows()
        window_times = ", ".join([f"{w['name']} ({w['hour']:02d}:{w['minute']:02d})" for w in windows])
        st.info(f"Daily mode — auto-runs at {window_times} UK time.")

        missed_window, missed_time = get_missed_window()

        if missed_window:
            mins_ago = int((now_gmt - missed_time).total_seconds() / 60)
            st.warning(f"Missed window detected: {missed_window['name']} ({missed_time.strftime('%H:%M GMT')} — {mins_ago} mins ago). Running now...")
            now_check = get_uk_time()
            market_open_check, market_close_check = get_market_times_uk(now_check.date())
            is_weekend_check = now_check.weekday() >= 5
            market_open_flag = not is_weekend_check and market_open_check.replace(second=0, microsecond=0) <= now_check <= market_close_check.replace(second=0, microsecond=0)
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

    st.subheader(f"Open Positions ({len(open_positions)}/10)")
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
                # Show pyramid layers if they exist
                pyramid_layers = p.get("pyramid_layers", [])
                if pyramid_layers:
                    st.write("**📊 Position Layers (Pyramid):**")
                    layers_data = []
                    for layer in pyramid_layers:
                        layers_data.append({
                            "Confidence": layer.get("tier", ""),
                            "Entry $": f"${layer.get('entry_price', 0):.2f}",
                            "Size £": f"£{layer.get('size', 0):.0f}",
                            "Opened": layer.get("opened_at", "")
                        })
                    layers_df = pd.DataFrame(layers_data)
                    st.dataframe(layers_df, use_container_width=True, hide_index=True)
                    st.metric("Weighted Avg Entry", f"${entry:.2f}")
                    st.divider()

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

    st.divider()

    st.subheader("📊 Performance Charts")

    if closed_positions:
        col_chart1 = st.columns(1)[0]
        with col_chart1:
            st.write("**Portfolio Value Over Time**")
            portfolio_data = get_portfolio_value_over_time(closed_positions)
            st.line_chart(portfolio_data.set_index("Date")["Portfolio Value"])

        col_chart2, col_chart3 = st.columns(2)

        with col_chart2:
            st.write("**Win Rate by Confidence Tier**")
            tier_data = get_win_rate_by_tier(closed_positions)
            st.bar_chart(tier_data.set_index("Confidence")["Win Rate %"])

        with col_chart3:
            st.write("**P&L per Trade (Last 20)**")
            pnl_data = get_pnl_by_trade(closed_positions)
            st.bar_chart(pnl_data.set_index("Trade")["P&L £"])
    else:
        st.info("📊 Charts will appear once you close your first trade.")

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

with tab4:
    st.subheader("Deep Dive — Single Stock Analysis")
    st.caption("Enter any ticker to get a full investment thesis from Claude: technicals, news, options, insider activity, earnings, and a BUY/WATCH/AVOID verdict.")

    col_input, col_button = st.columns([3, 1])
    with col_input:
        deep_dive_ticker = st.text_input(
            "Ticker",
            placeholder="e.g. AAPL, NVDA, TSLA",
            label_visibility="collapsed"
        )
    with col_button:
        deep_dive_run = st.button("Analyse", type="primary", use_container_width=True)

    if deep_dive_run and deep_dive_ticker.strip():
        market_open_flag_dd = is_market_open()

        if not market_open_flag_dd:
            st.info("US markets are currently closed — analysis will run but no position will be opened.")

        result = run_deep_dive(
            deep_dive_ticker.strip(),
            use_enhanced_news=get_enhanced_news_setting(),
            market_is_open=market_open_flag_dd,
        )
        st.divider()
        st.markdown(result)

        if market_open_flag_dd and "NEW_TRADE:" in result:
            st.success("Position opened — check the Portfolio tab.")
        elif market_open_flag_dd:
            st.info("No position opened — verdict was WATCH or AVOID.")
    elif deep_dive_run:
        st.warning("Please enter a ticker symbol.")

with tab5:
    st.subheader("🧠 AI Learning Analytics")
    st.caption("Track what signals work best and guide AI improvements")

    if not closed_positions:
        st.info("📊 Learning dashboard will populate as you close trades. Trade more to provide AI training data!")
    else:
        # Win rate by confidence tier (with trade counts)
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Win Rate by Confidence Tier**")
            tier_data = []
            for tier in ["SUPER", "CONFIDENT", "MEDIUM", "LOW"]:
                tier_trades = [p for p in closed_positions if p.get("confidence") == tier]
                if tier_trades:
                    wins = len([p for p in tier_trades if float(p.get("pnl", 0) or 0) > 0])
                    total = len(tier_trades)
                    win_rate = (wins / total * 100) if total > 0 else 0
                    tier_data.append({
                        "Confidence": tier,
                        "Win Rate %": win_rate,
                        "Trades": total,
                        "Wins": wins
                    })

            if tier_data:
                tier_df = pd.DataFrame(tier_data)
                st.dataframe(tier_df, use_container_width=True, hide_index=True)
                st.bar_chart(tier_df.set_index("Confidence")["Win Rate %"])

        with col2:
            st.write("**Total Trades by Confidence**")
            trade_counts = tier_df.set_index("Confidence")["Trades"] if tier_data else pd.DataFrame()
            if not trade_counts.empty:
                st.bar_chart(trade_counts)

        st.divider()

        # Win rate by asset (top performers)
        st.write("**Best Performing Assets (Trade Count ≥ 2)**")

        ticker_stats = {}
        for p in closed_positions:
            ticker = p["ticker"]
            pnl = float(p.get("pnl", 0) or 0)
            if ticker not in ticker_stats:
                ticker_stats[ticker] = {"wins": 0, "total": 0, "avg_pnl": 0}
            ticker_stats[ticker]["total"] += 1
            if pnl > 0:
                ticker_stats[ticker]["wins"] += 1
            ticker_stats[ticker]["avg_pnl"] += pnl

        # Only show tickers with 2+ trades
        ticker_data = []
        for ticker, stats in sorted(ticker_stats.items(), key=lambda x: x[1]["wins"] / max(1, x[1]["total"]), reverse=True):
            if stats["total"] >= 2:
                win_rate = (stats["wins"] / stats["total"] * 100)
                avg_pnl = stats["avg_pnl"] / stats["total"]
                ticker_data.append({
                    "Ticker": ticker,
                    "Win Rate %": win_rate,
                    "Trades": stats["total"],
                    "Avg P&L £": round(avg_pnl, 2)
                })

        if ticker_data:
            ticker_df = pd.DataFrame(ticker_data[:10])  # Top 10
            st.dataframe(ticker_df, use_container_width=True, hide_index=True)

            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.bar_chart(ticker_df.set_index("Ticker")["Win Rate %"])
            with col_chart2:
                st.bar_chart(ticker_df.set_index("Ticker")["Avg P&L £"])

        st.divider()

        # Pyramid Performance Analysis
        st.write("**🔺 Pyramid Performance (Confidence Scaling)**")

        pyramid_stats = defaultdict(lambda: {"upgrades": 0, "stayed": 0, "downgrades": 0, "pnl": 0})

        # Analyze pyramid layers in open and closed positions
        all_positions = open_positions + closed_positions
        for pos in all_positions:
            if pos.get("pyramid_layers") and len(pos.get("pyramid_layers", [])) > 1:
                # Has pyramid layers = had confidence changes
                layers = pos["pyramid_layers"]
                if len(layers) >= 2:
                    for i in range(1, len(layers)):
                        prev_tier = layers[i-1].get("tier", "")
                        curr_tier = layers[i].get("tier", "")
                        key = f"{prev_tier}→{curr_tier}"
                        pyramid_stats[key]["upgrades"] += 1

                        # Track if it stayed (didn't downgrade)
                        if i == len(layers) - 1:  # Last layer
                            pyramid_stats[key]["stayed"] += 1

                        # Track P&L if closed
                        pnl = float(pos.get("pnl", 0) or 0)
                        if pnl != 0:
                            pyramid_stats[key]["pnl"] += pnl

        if pyramid_stats:
            pyramid_df_data = []
            for transition, stats_data in sorted(pyramid_stats.items()):
                success_rate = (stats_data["stayed"] / stats_data["upgrades"] * 100) if stats_data["upgrades"] > 0 else 0
                pyramid_df_data.append({
                    "Transition": transition,
                    "Upgrades": stats_data["upgrades"],
                    "Stayed": stats_data["stayed"],
                    "Success %": round(success_rate, 1),
                    "Avg P&L £": round(stats_data["pnl"] / max(1, stats_data["upgrades"]), 2)
                })

            if pyramid_df_data:
                pyramid_df = pd.DataFrame(pyramid_df_data)
                st.dataframe(pyramid_df, use_container_width=True, hide_index=True)

                st.info(
                    "💡 Pyramid scaling shows which confidence upgrades are **real signals** vs **false positives**. "
                    "High 'Success %' means the upgrade was justified; low % means you're over-committing to weak signals."
                )
            else:
                st.info("📊 No pyramid scaling data yet. Pyramid scaling will be tracked as confidence tiers change.")
        else:
            st.info("📊 No pyramid scaling data yet. Pyramid scaling will be tracked as confidence tiers change.")

        st.divider()

        # AI Learning Recommendations
        st.write("**💡 AI Improvement Recommendations**")

        recommendations = []

        # Find best performing tier
        if tier_data:
            best_tier = max(tier_data, key=lambda x: x["Win Rate %"])
            if best_tier["Trades"] >= 3:
                recommendations.append(
                    f"✓ **{best_tier['Confidence']} Confidence** has {best_tier['Win Rate %']:.1f}% win rate — "
                    f"consider increasing position size here (best edge detected)"
                )

        # Find best performing assets
        if ticker_data and ticker_data[0]["Trades"] >= 3:
            best_ticker = ticker_data[0]
            recommendations.append(
                f"✓ **{best_ticker['Ticker']}** shows {best_ticker['Win Rate %']:.1f}% accuracy — "
                f"prioritize this asset in screening/analysis"
            )

        # Identify struggling areas
        if tier_data:
            worst_tier = min(tier_data, key=lambda x: x["Win Rate %"])
            if worst_tier["Trades"] >= 3 and worst_tier["Win Rate %"] < 40:
                recommendations.append(
                    f"⚠️ **{worst_tier['Confidence']} Confidence** underperforming at {worst_tier['Win Rate %']:.1f}% — "
                    f"reduce position size or skip these trades"
                )

        # Volume feedback
        total_trades = len(closed_positions)
        if total_trades < 20:
            recommendations.append(
                f"📈 Only {total_trades} trades so far — need ~50+ trades minimum for AI to identify reliable patterns. "
                f"Increase trading volume to accelerate learning."
            )
        elif total_trades < 50:
            recommendations.append(
                f"📈 {total_trades} trades — good progress. Aim for 50+ trades to validate patterns across market conditions."
            )

        if recommendations:
            for rec in recommendations:
                st.info(rec)
        else:
            st.success("✅ Keep trading! More data = better AI learning.")