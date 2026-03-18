import streamlit as st
import time
from fetcher import fetch_stock_data, fetch_historical_data
from agent import analyse_stocks
from news import fetch_stock_news
from earnings import get_earnings_calendar, get_earnings_summary
from sectors import get_market_context, get_market_summary
from screener import run_screen, get_all_tickers
from insider import get_insider_summary, format_insider_string
from options import get_options_summary, format_options_string

st.title("AI Stock Market Agent")
st.write("Screening 125+ assets — only the best signals reach Claude")

st.sidebar.title("Settings")
refresh_rate = st.sidebar.slider("Refresh every (minutes)", 1, 30, 5)

placeholder = st.empty()

while True:
    with placeholder.container():

        with st.spinner("Stage 1 — Screening 125+ assets..."):
            shortlist = run_screen()

        tickers = [r["ticker"] for r in shortlist]

        st.subheader("Stage 1 — Screener Results")
        st.write(f"Screened 125+ assets. Top {len(tickers)} signals shortlisted for Claude.")

        buy_signals = [r for r in shortlist if r["signal"] == "BUY"]
        avoid_signals = [r for r in shortlist if r["signal"] == "AVOID"]
        watch_signals = [r for r in shortlist if r["signal"] == "WATCH"]

        col1, col2, col3 = st.columns(3)
        col1.metric("🟢 Buy signals", len(buy_signals))
        col2.metric("🔴 Avoid signals", len(avoid_signals))
        col3.metric("⚪ Watch signals", len(watch_signals))

        st.subheader("Shortlisted Assets")
        for r in shortlist:
            emoji = "🟢" if r["signal"] == "BUY" else "🔴" if r["signal"] == "AVOID" else "⚪"
            st.write(f"{emoji} **{r['ticker']}** — ${r['price']} — Score: {r['score']} — {', '.join(r['reasons'])}")

        with st.spinner("Fetching market context..."):
            market_context = get_market_context()

        st.subheader("Market Overview")
        col1, col2, col3 = st.columns(3)
        spy = market_context.get("SPY")
        qqq = market_context.get("QQQ")
        xle = market_context.get("XLE")
        if spy:
            col1.metric("S&P 500", f"${spy['price']}", f"{spy['change_percent']}%")
        if qqq:
            col2.metric("NASDAQ", f"${qqq['price']}", f"{qqq['change_percent']}%")
        if xle:
            col3.metric("Energy", f"${xle['price']}", f"{xle['change_percent']}%")

        st.subheader("Stage 2 — Deep Analysis")

        with st.spinner("Fetching live prices..."):
            df = fetch_stock_data(tickers)

        st.subheader("Live Prices")
        st.dataframe(df)

        with st.spinner("Fetching technical indicators..."):
            historical = fetch_historical_data(tickers)

        st.subheader("Technical Indicators")
        for ticker, data in historical.items():
            if data:
                with st.expander(ticker):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("RSI", f"{data.get('rsi', 'N/A')} — {data.get('rsi_signal', 'N/A')}")
                    col2.metric("MA Signal", data.get('ma_signal', 'N/A'))
                    col3.metric("Volume", data.get('volume_signal', 'N/A'))
                    st.write(f"30d High: ${data.get('high_30d')}  |  30d Low: ${data.get('low_30d')}  |  30d Avg: ${data.get('avg_30d')}")
                    st.write(f"Overall trend: {data.get('trend')}")

        with st.spinner("Checking earnings calendar..."):
            earnings = get_earnings_calendar(tickers)

        earnings_summary = get_earnings_summary(earnings)
        if "No earnings" not in earnings_summary:
            st.warning(earnings_summary)
        else:
            st.info("No earnings reports in the next 7 days")

        with st.spinner("Fetching options flow..."):
            options_summary = get_options_summary(tickers)

        st.subheader("Options Flow")
        if options_summary:
            for ticker, data in options_summary.items():
                with st.expander(f"{ticker} — {data['overall']}"):
                    st.write(f"Call value: ${data['call_value']:,.0f} | Put value: ${data['put_value']:,.0f}")
                    for flow in data["flow"][:3]:
                        st.write(f"{flow['signal']} {flow['type']} — Strike ${flow['strike']} exp {flow['expiry']} — Vol {flow['volume']:,} — ${flow['total_value']:,.0f} — IV {flow['iv']}%")
        else:
            st.info("No unusual options activity detected")

        with st.spinner("Checking insider activity..."):
            insider_summary = get_insider_summary(tickers)

        st.subheader("Insider Activity")
        if insider_summary:
            for ticker, data in insider_summary.items():
                with st.expander(f"{ticker} — {data['signal']}"):
                    st.write(f"Total bought: ${data['total_value']:,.0f} across {data['num_trades']} trades")
                    for trade in data["trades"][:3]:
                        st.write(f"{trade['date']} — {trade['insider']} ({trade['title']}) bought {trade['shares']:,.0f} shares @ ${trade['price']:.2f}")
        else:
            st.info("No insider buying detected in last 90 days")

        with st.spinner("Fetching latest news..."):
            news = fetch_stock_news(tickers)

        st.subheader("Latest News")
        for ticker, data in news.items():
            with st.expander(f"{ticker} — Sentiment: {data['overall_sentiment']} ({data['avg_score']})"):
                for h in data["headlines"]:
                    emoji = "🟢" if h["sentiment"] == "Positive" else "🔴" if h["sentiment"] == "Negative" else "⚪"
                    st.write(f"{emoji} {h['sentiment']} ({h['score']}) — {h['title']}")

        with st.spinner("Claude is analysing everything..."):
            analysis = analyse_stocks(df, news, historical, earnings, market_context, insider_summary, options_summary)

        st.subheader("Claude's Analysis")
        st.write(analysis)

        st.write(f"Next update in {refresh_rate} minutes")

    time.sleep(refresh_rate * 60)