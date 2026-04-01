import anthropic
import os
import time
import json
import streamlit as st
from dotenv import load_dotenv
from memory import save_analysis, get_memory_summary
from earnings import get_earnings_summary
from sectors import get_market_summary
from portfolio import (
    get_portfolio_summary, get_open_positions, get_current_prices,
    open_position, close_position, update_position,
    check_stop_losses, check_max_hold, check_50_percent_targets, check_quick_loser_exits,
    get_portfolio_balance, get_closed_positions, MAX_POSITIONS, CONFIDENCE_SIZES
)
from trade_analyzer import analyze_closed_positions, get_playbook_context_for_claude

from prediction_tracker import get_accuracy_summary

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

HIGH_ACCURACY_ASSETS = {
    "SNAP": 80.0,
    "HAL": 80.0,
    "XRP-USD": 71.4,
    "FANG": 66.7,
    "DOCU": 60.0,
    "SOL-USD": 60.0,
}

LOW_ACCURACY_ASSETS = {
    "XLY": 0.0,
    "ZW=F": 0.0,
    "RBLX": 5.0,
    "QQQ": 6.7,
    "NVDA": 10.5,
    "C": 12.5,
    "BTC-USD": 12.5,
    "RF": 14.3,
    "RTX": 14.3,
    "XLK": 14.3,
    "PH": 18.2,
    "META": 20.0,
    "MSFT": 20.0,
    "XLI": 20.0,
    "GE": 21.4,
    "XLU": 22.2,
    "EEM": 25.0,
    "AMD": 25.0,
    "GC=F": 25.0,
    "ZM": 25.0,
    "NFLX": 25.0,
    "BK": 25.0,
}

def get_accuracy_context(tickers):
    high = [f"{t}: {HIGH_ACCURACY_ASSETS[t]}%" for t in tickers if t in HIGH_ACCURACY_ASSETS]
    low = [f"{t}: {LOW_ACCURACY_ASSETS[t]}%" for t in tickers if t in LOW_ACCURACY_ASSETS]
    context = ""
    if high:
        context += f"HIGH CONFIDENCE: {', '.join(high)}\n"
    if low:
        context += f"LOW CONFIDENCE: {', '.join(low)}\n"
    return context if context else "No historical accuracy data for these assets.\n"

def build_news_string(news, max_per_stock=2):
    news_string = ""
    for ticker, data in news.items():
        if not data.get("has_signal") and data.get("avg_score", 0) == 0:
            news_string += f"{ticker}: No significant news\n"
            continue

        news_string += f"{ticker} ({data['overall_sentiment']} {data['avg_score']}):\n"
        significant = [h for h in data["headlines"] if abs(h["score"]) > 0.1]
        if not significant:
            significant = data["headlines"][:1]

        for h in significant[:max_per_stock]:
            age_str = h.get("age_str", "")
            source = h.get("source", "")
            summary = h.get("summary", "")
            news_string += f"  {h['sentiment']} ({h['score']}) [{age_str} — {source}]: {h['title'][:100]}\n"
            if summary:
                news_string += f"    {summary[:200]}\n"

        # Add earnings summary if available
        earnings = data.get("earnings_summary")
        if earnings:
            news_string += f"  EARNINGS: {earnings[:200]}\n"

    return news_string

def build_fundamentals_string(fundamentals):
    if not fundamentals:
        return "Fundamental data unavailable.\n"
    result = ""
    for ticker, d in fundamentals.items():
        if not d:
            continue
        parts = []
        if d.get("pe"):
            parts.append(f"PE {d['pe']}")
        if d.get("fwd_pe"):
            parts.append(f"FwdPE {d['fwd_pe']}")
        if d.get("analyst_target") and d.get("target_upside") is not None:
            parts.append(f"target ${d['analyst_target']} ({d['target_upside']:+.1f}%)")
        if d.get("short_pct") is not None:
            parts.append(f"short {d['short_pct']}%")
        if d.get("rev_growth") is not None:
            parts.append(f"revGrowth {d['rev_growth']:+.1f}%")
        if parts:
            result += f"{ticker}: {' | '.join(parts)}\n"
    return result if result else "No fundamental data available.\n"


def build_options_string(options_summary):
    if not options_summary:
        return "No significant options activity.\n"
    result = ""
    for ticker, data in options_summary.items():
        result += f"{ticker} {data['overall']}: calls ${data['call_value']:,.0f} puts ${data['put_value']:,.0f}\n"
        for flow in data["flow"][:2]:
            result += f"  {flow['signal']} {flow['type']} ${flow['strike']} exp {flow['expiry']} vol {flow['volume']:,}\n"
    return result

def determine_confidence_level(ticker, score, historical, options_summary, insider_summary):
    """
    Determines confidence tier based on score, confirmers, insider and options data.
    Returns LOW, MEDIUM, CONFIDENT, or SUPER.
    """
    strong_confirmers = 0
    has_insider = ticker in insider_summary if insider_summary else False
    has_options = ticker in options_summary if options_summary else False

    if historical.get(ticker):
        rsi = historical[ticker].get("rsi")
        if rsi and rsi < 35:
            strong_confirmers += 1

    if score >= 14 and strong_confirmers >= 2 and has_insider and has_options:
        return "SUPER"
    elif score >= 11 and strong_confirmers >= 1 and (has_insider or has_options):
        return "CONFIDENT"
    elif score >= 9 and (has_insider or has_options):
        return "MEDIUM"
    else:
        return "LOW"

def review_open_positions(current_prices, news, options_summary, market_context):
    """
    Reviews all open positions and returns Claude's decisions on each.
    """
    open_positions = get_open_positions()
    if not open_positions:
        return "", []

    position_reviews = ""
    for p in open_positions:
        ticker = p["ticker"]
        current = current_prices.get(ticker, float(p["entry_price"]))
        entry = float(p["entry_price"])
        pnl_pct = round(((current - entry) / entry) * 100, 2)
        days_held = (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc) -
            __import__("datetime").datetime.strptime(p["opened_at"], "%Y-%m-%d %H:%M").replace(
                tzinfo=__import__("datetime").timezone.utc)
        ).days

        ticker_news = news.get(ticker, {})
        news_summary = ticker_news.get("overall_sentiment", "No news")

        position_reviews += f"""
{ticker}: entry {entry} | current {current} | pnl {pnl_pct}% | target {p['target_price']} | stop {p['stop_loss']} | day {days_held}/{10} | confidence {p['confidence']}
News: {news_summary}
Original reasoning: {p['claude_reasoning'][:200] if p['claude_reasoning'] else 'N/A'}
"""

    return position_reviews, open_positions

def analyse_stocks(df, news, historical, earnings, market_context,
                   insider_summary=None, options_summary=None, market_is_open=True,
                   fundamentals=None):

    data_string = df.to_string(index=False)
    tickers = df["ticker"].tolist()

    historical_string = ""
    for ticker, data in historical.items():
        if data:
            line = (
                f"{ticker}: RSI {data.get('rsi','N/A')} ({data.get('rsi_signal','N/A')}) | "
                f"{data.get('weekly_rsi_signal','N/A')} | "
                f"{data.get('ma_signal','N/A')} | MACD {data.get('macd_signal','N/A')} | "
                f"BB {data.get('bb_signal','N/A')} | {data.get('trend','N/A')} | Vol {data.get('volume_signal','N/A')}"
            )
            if data.get("sector_signal"):
                line += f" | Sector: {data['sector_signal']}"
            historical_string += line + "\n"

    insider_string = "None detected.\n"
    if insider_summary:
        insider_string = ""
        for ticker, data in insider_summary.items():
            insider_string += f"{ticker}: {data['signal']} — ${data['total_value']:,.0f} total\n"

    memory_summary = get_memory_summary()
    earnings_summary = get_earnings_summary(earnings)
    market_summary = get_market_summary(market_context)
    accuracy_context = get_accuracy_context(tickers)
    prediction_accuracy = get_accuracy_summary()
    news_string = build_news_string(news)
    options_string = build_options_string(options_summary)
    fundamentals_string = build_fundamentals_string(fundamentals)
    portfolio_summary = get_portfolio_summary()

    # Auto-manage positions before analysis (SMART STRATEGY)
    open_positions = get_open_positions()
    if open_positions:
        position_tickers = [p["ticker"] for p in open_positions]
        all_tickers = list(set(tickers + position_tickers))
        current_prices = get_current_prices(all_tickers)

        # Exit positions (in order of priority)
        check_50_percent_targets(open_positions, current_prices)  # Lock in gains first
        check_stop_losses(open_positions, current_prices)         # Stop losses always
        check_quick_loser_exits(open_positions, current_prices)   # Free capital from losers
        check_max_hold(open_positions, current_prices)            # Time-based exits

        # Refresh positions after auto-closures
        open_positions = get_open_positions()
    else:
        current_prices = get_current_prices(tickers)

    # Get position reviews for Claude
    position_reviews, open_positions = review_open_positions(
        current_prices, news, options_summary, market_context
    )

    available_slots = MAX_POSITIONS - len(open_positions)
    balance = get_portfolio_balance()

    # Generate learned playbook from historical trades
    closed_positions = get_closed_positions()
    trade_analysis = analyze_closed_positions(closed_positions) if closed_positions else {}
    playbook_context = get_playbook_context_for_claude(trade_analysis)

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2500,
                messages=[
                    {
                        "role": "user",
                        "content": f"""You are a professional stock analyst managing a paper trading portfolio.

MARKET: {market_summary}

PORTFOLIO: {portfolio_summary}

OPEN POSITION REVIEW:
{position_reviews if position_reviews else "No open positions to review."}

ACCURACY: {accuracy_context}

PREDICTION HISTORY:
{prediction_accuracy}

MEMORY: {memory_summary}

YOUR LEARNED PLAYBOOK (Trading patterns that work):
{playbook_context}

FUNDAMENTALS:
{fundamentals_string}

PRICES & TECHNICALS:
{data_string}
{historical_string}

NEWS: {news_string}

OPTIONS: {options_string}

INSIDER: {insider_string}

EARNINGS: {earnings_summary}

INSTRUCTIONS:

PART 1 — REVIEW OPEN POSITIONS:
For each open position review whether to HOLD or EXIT.
Rules you must follow:
- Stop loss NEVER moves down
- When target is hit, move stop loss up to just below target achieved
- Exit if confidence drops to LOW
- Exit if stop loss breached (already handled automatically)
- Maximum 10 days hold (already handled automatically)

AGGRESSIVE EXIT RULES (CRITICAL for AI learning):
- **EXIT AT 50% TARGET (PRIMARY RULE)**
  Example: Entry 100, target 110, exit at 105 (50% of 10-point move)
  This locks in gains, increases learning cycles (more closed trades = faster learning)
  Let other 50% run if momentum continues

- Exit immediately if RSI reverses from overbought (>70 → <60) without new highs
  Signal: Momentum failed, mean reversion done

- Exit if volume dies below 20-day average for 2+ days
  Signal: Institutional conviction gone

- Exit if position flat/sideways for 5+ days
  Signal: Mean reversion complete, time to redeploy capital

- Exit if sector turns negative and stock hasn't outperformed
  Signal: Sector rotation, even if stock still up

For each open position output:
POSITION_REVIEW: [TICKER] | [HOLD/EXIT] | [NEW_TARGET if changed] | [NEW_STOP if changed] | [NEW_CONFIDENCE] | [REASONING]

PART 2 — NEW TRADE DECISIONS (QUALITY OVER QUANTITY STRATEGY):

**CRITICAL: The goal is 50-70 HIGH-QUALITY closed trades over 2 months for AI learning.**
**Better to make 2 excellent trades/week than 10 mediocre ones.**

Available portfolio slots: {available_slots}
Available cash: £{round(balance, 2)}

🔥 ULTRA-SELECTIVE ENTRY CRITERIA (ALL must pass):

1. **SCORE THRESHOLD: 11+ minimum** (not 10)
   - Only suggest score 11-13 or higher
   - Skip anything below 11, no exceptions

2. **CONFIRMERS: 2+ STRONG signals required**
   - Strong signals: RSI divergence, insider buying, bullish options £1M+, support hold
   - Weak signals: Above MA20, volume ratio >1.5x (these alone aren't enough)

3. **Risk/Reward: Strict 2:1 minimum**
   - Target must be 2x the distance below stop loss
   - Example: Stop at 100, Target at 110, Risk = 10, Reward = 20 ✓

4. **Sector Filter: Only STRONGEST 3 sectors**
   - Check sector RSI vs market RSI
   - Skip if sector RSI < market RSI (weak sector)
   - Rotate through different sectors week-to-week (XLK one week, XLE next)

5. **Options Confirmation for CONFIDENT tier**
   - CONFIDENT (£1000): Requires bullish options £1M+ calls, ZERO puts
   - Without options: Downgrade to MEDIUM (£250)

6. **Earnings: Skip 5 days before AND 2 days after**
   - IV crush kills mean reversion setups

7. **Trend Confirmation**
   - Price MUST be above MA20 AND MA50 for LONGS
   - No "broken structure" plays unless extreme oversold (RSI <20)

Confidence tiers and position sizes (QUALITY-FIRST):
- SUPER (£2000): ONLY rare perfect setups (3+ confirmers + insider + options + score 13+)
- CONFIDENT (£1000): Score 11-13 AND bullish options flow (£1M+ calls, zero puts)
- MEDIUM (£250): Score 11+ AND 2 confirmers (no options required, but options helps)
- LOW (£100): AVOID except extreme oversold (RSI <20) with clear support

**VOLUME TARGET: 2-3 trades per week MAXIMUM**
- This gives time for positions to mature
- Better learning from diverse scenarios
- Allows active exit management (exit at 50% target)

**CRITICAL RULE: It is ALWAYS better to say NO TRADE than to force a marginal setup.**
- If only 1 trade meets criteria today, suggest only that 1
- If 0 trades meet criteria, output: NO_TRADE: [reason]
- Resist the urge to lower thresholds just to "make a trade"

For each new trade meeting criteria output:
NEW_TRADE: [TICKER] | [LONG/SHORT] | [ENTRY_PRICE] | [TARGET] | [STOP_LOSS] | [CONFIDENCE] | [REASONING]

**If no setups meet the ULTRA-SELECTIVE criteria:**
NO_TRADE: [Explain which criteria failed]
Example: "NO_TRADE: Only 2 candidates (MSFT, GOOGL) — both score <11 and lack 2+ confirmers. Waiting for higher-conviction setups."

**EXPECTED OUTCOME:** 2-3 NEW_TRADE suggestions per analysis (not 5-10).
If you see 0 trades after a day of analysis, that's GOOD — means we're waiting for quality.

PART 3 — FORMAT YOUR FULL ANALYSIS IN THIS EXACT ORDER:

### 1. Market Regime
Single line: BULL or BEAR | SPY price vs 50MA | Risk-on or Risk-off | One sentence overall market tone.

### 2. Portfolio Status
Current open positions summary, total unrealised P&L, cash available, any stop losses currently at risk.

### 3. Current Position Review
For each open position: HOLD or EXIT decision, updated target and stop if changed, confidence level, one sentence reasoning.

### 4. News & Sentiment Impact
What is moving markets today. Which held positions are affected by news. Any sector-wide events. Sentiment direction per ticker.

### 5. New Trade Decisions
If genuine setups exist, list them with full parameters.
If no good setups, state NO TRADE TODAY and explain why in one sentence.

### 6. Watchlist Triggers
For each WATCH signal, state the exact price level or RSI level that would trigger a BUY entry. Format: TICKER — trigger condition — why it matters.

### 7. Risk Exposure Summary
Total capital at risk across all open positions as percentage of portfolio.
Flag any sector concentration risk — if 2 or more positions are in the same sector.
Flag if total risk exceeds 10% of portfolio.

### 8. Key Technical Signals
RSI extremes, MA crossovers, divergences, volume anomalies. Flagged only — no noise. Max 8 lines.

### 9. Options & Insider Activity
Any significant flow detected. Divergences vs price. Flag if options contradict technical signal.

### 10. Position Summary Table
| Ticker | Entry | Current | Target | Stop | P&L | Confidence |
All open positions in one clean table.

### 11. One-Line Summary
| Ticker | Direction | Confidence | Reason |
Every analysed ticker. One line each. No exceptions.

Weight confidence by historical accuracy. Flag options/technical divergences prominently.
Optimal hold period is 5 days. BUY signals have 80% historical accuracy in bull markets."""
                    }
                ]
            )

            analysis_text = message.content[0].text

            # Parse and execute trade decisions
            execute_trade_decisions(
                analysis_text, historical, options_summary,
                insider_summary, current_prices, open_positions,
                market_is_open=market_is_open
            )

            save_analysis(tickers, analysis_text, historical)
            return analysis_text

        except anthropic.APIStatusError as e:
            if attempt < 2:
                st.warning(f"Claude is busy, retrying in 10 seconds... (attempt {attempt + 1}/3)")
                time.sleep(10)
            else:
                return "Claude is currently overloaded. Please wait a moment and refresh."

def check_exit_signals(open_positions, historical, current_prices):
    """
    Check for proactive exit signals: technical flip, volatility spike, momentum decay.
    Returns list of (ticker, reason) tuples for positions that should exit.
    """
    exit_signals = []

    for position in open_positions:
        ticker = position["ticker"]
        hist = historical.get(ticker, {})
        current_price = current_prices.get(ticker)
        entry_price = float(position["entry_price"])

        if not hist or not current_price:
            continue

        # 1. TECHNICAL SIGNAL EXIT: RSI/MACD bearish flip
        rsi = hist.get("rsi", None)
        rsi_signal = hist.get("rsi_signal", "")
        macd_signal = hist.get("macd_signal", "")

        if rsi and rsi > 60 and rsi_signal == "SELL":
            exit_signals.append((ticker, f"RSI bearish flip at {rsi}"))

        if macd_signal == "SELL":
            exit_signals.append((ticker, "MACD turned bearish"))

        # 2. VOLATILITY EXIT: Volatility spikes
        bb_signal = hist.get("bb_signal", "")
        if "OVERBOUGHT" in bb_signal or "extreme" in bb_signal.lower():
            exit_signals.append((ticker, "Bollinger Bands overbought (volatility spike)"))

        # 3. MOMENTUM DECAY: RSI declining from peaks while price still up
        if rsi and rsi < 45 and current_price > entry_price:
            exit_signals.append((ticker, f"Momentum decay: RSI fell to {rsi} despite price up {round((current_price - entry_price) / entry_price * 100, 1)}%"))

    return exit_signals

def execute_trade_decisions(analysis_text, historical, options_summary,
                             insider_summary, current_prices, open_positions,
                             market_is_open=True):
    """
    Parses Claude's structured output and executes position opens/updates/closes.
    Also checks for proactive exit signals (technical flip, volatility, momentum decay).
    """
    lines = analysis_text.split("\n")
    new_trade_lines = [l for l in lines if l.startswith("NEW_TRADE:")]

    # Debug: show if NEW_TRADE lines were found
    if new_trade_lines:
        st.info(f"🔍 Found {len(new_trade_lines)} trade signal(s). Market open: {market_is_open}")
        for trade_line in new_trade_lines:
            st.caption(f"Trade signal: {trade_line[:80]}")
    else:
        st.caption("ℹ️ No NEW_TRADE signals in analysis")

    open_position_map = {p["ticker"]: p for p in open_positions}

    # Check for proactive exit signals before processing analysis
    exit_signals = check_exit_signals(open_positions, historical, current_prices)
    for ticker, reason in exit_signals:
        if ticker in open_position_map:
            position = open_position_map[ticker]
            current_price = current_prices.get(ticker, float(position["entry_price"]))
            close_position(position["id"], current_price, f"Auto-exit: {reason}")
            st.warning(f"⚠️ Auto-exited {ticker}: {reason}")

    for line in lines:
        line = line.strip()
        # Remove markdown bold/italic markers (** or *)
        line = line.replace("**", "").replace("*", "")

        # Handle position reviews
        if line.startswith("POSITION_REVIEW:"):
            try:
                parts = line.replace("POSITION_REVIEW:", "").strip().split("|")
                ticker = parts[0].strip()
                action = parts[1].strip()
                new_target = parts[2].strip() if len(parts) > 2 else None
                new_stop = parts[3].strip() if len(parts) > 3 else None
                new_confidence = parts[4].strip() if len(parts) > 4 else None
                reasoning = parts[5].strip() if len(parts) > 5 else ""

                if ticker in open_position_map:
                    position = open_position_map[ticker]
                    current_price = current_prices.get(ticker, float(position["entry_price"]))

                    if action == "EXIT":
                        close_position(position["id"], current_price, reasoning)
                        st.info(f"Closed {ticker} at ${current_price} — {reasoning[:80]}")
                    else:
                        updates = {}
                        if new_target and new_target not in ["", "unchanged"]:
                            try:
                                updates["target_price"] = float(new_target)
                            except ValueError:
                                pass
                        if new_stop and new_stop not in ["", "unchanged"]:
                            try:
                                updates["stop_loss"] = float(new_stop)
                            except ValueError:
                                pass
                        if new_confidence and new_confidence not in ["", "unchanged"]:
                            # Use pyramiding if confidence changed
                            if new_confidence != position.get("confidence"):
                                from portfolio import update_position_confidence_with_pyramid
                                update_position_confidence_with_pyramid(position["id"], new_confidence, current_price)
                                st.success(f"Pyramiding: {ticker} confidence upgraded from {position.get('confidence')} to {new_confidence}")
                            else:
                                updates["confidence"] = new_confidence
                        updates["current_price"] = current_price
                        if updates:
                            update_position(position["id"], updates)

            except Exception as e:
                st.error(f"Position review parse error: {e}")

        # Handle new trades
        elif line.startswith("NEW_TRADE:"):
            if not market_is_open:
                st.info(f"Markets closed — trade not opened. It will not be retried automatically.")
                continue
            try:
                parts = line.replace("NEW_TRADE:", "").strip().split("|")
                ticker = parts[0].strip()
                direction = parts[1].strip()
                entry_price = float(parts[2].strip())
                target = float(parts[3].strip())
                stop_loss = float(parts[4].strip())
                confidence = parts[5].strip()
                reasoning = parts[6].strip() if len(parts) > 6 else ""

                position_size = CONFIDENCE_SIZES.get(confidence, 100.0)
                balance = get_portfolio_balance()
                current_open = len(get_open_positions())

                if current_open >= MAX_POSITIONS:
                    st.warning(f"Max positions ({MAX_POSITIONS}) reached — {ticker} skipped.")
                    continue

                if position_size > balance:
                    st.warning(f"Insufficient balance for {ticker} — need £{position_size}, have £{round(balance, 2)}.")
                    continue

                result = open_position(
                    ticker, direction, entry_price, target,
                    stop_loss, confidence, 0, reasoning, position_size
                )
                if result:
                    st.success(f"Opened {ticker} {direction} — £{position_size} ({confidence}) | Entry ${entry_price} | Target ${target} | Stop ${stop_loss}")
                else:
                    st.error(f"Failed to open {ticker} — Supabase did not confirm. Check your portfolio manually.")

            except Exception as e:
                st.error(f"Trade parse error: {e} — line was: {line[:120]}")