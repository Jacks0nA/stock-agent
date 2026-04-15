import yfinance as yf
import pandas as pd
from fetcher import calculate_rsi
from datetime import datetime, timedelta
import json
import os
from monte_carlo import get_monte_carlo_analysis
from monte_carlo_learning import learning_system, print_learning_report
from debate_framework import debate_stock, format_debate_summary
from cross_validation import validate_stock
from moat_scorer import score_moat
from regime_detector import detect_regime
from sector_rotation import SectorRotationStrategy

# Cache file for screening results (expires after 1 hour)
CACHE_FILE = "/tmp/screener_cache.json"
CACHE_EXPIRY_MINUTES = 60

# Assets excluded based on 2-year backtest with min 5 signals
# Only excluding assets with meaningful sample sizes and consistently poor accuracy
LOW_ACCURACY_ASSETS = {
    "XLY", "ZW=F", "RBLX", "QQQ", "NVDA", "C", "BTC-USD",
    "RF", "RTX", "XLK", "PH", "META", "MSFT", "XLI",
    "GE", "XLU", "EEM", "AMD", "GC=F", "ZM", "NFLX",
    "BK", "UBER", "SI=F", "SPY", "BKR", "V"
}
SECTOR_ETFS = {
    "AAPL": "XLK", "GOOGL": "XLK", "NVDA": "XLK", "MSFT": "XLK",
    "META": "XLK", "TSLA": "XLK", "INTC": "XLK", "CRM": "XLK",
    "NFLX": "XLK", "PYPL": "XLK", "UBER": "XLK", "SNAP": "XLK",
    "SPOT": "XLK", "SHOP": "XLK", "PLTR": "XLK", "RBLX": "XLK",
    "NET": "XLK", "ZM": "XLK", "DOCU": "XLK", "TWLO": "XLK",
    "MDB": "XLK", "OKTA": "XLK",
    "JPM": "XLF", "BAC": "XLF", "GS": "XLF", "MS": "XLF",
    "V": "XLF", "AXP": "XLF", "WFC": "XLF", "BLK": "XLF",
    "SCHW": "XLF", "BK": "XLF",
    "PFE": "XLV", "MRK": "XLV", "ABBV": "XLV", "ABT": "XLV",
    "DHR": "XLV", "VRTX": "XLV", "SYK": "XLV", "MDT": "XLV",
    "COP": "XLE", "EOG": "XLE", "MPC": "XLE", "VLO": "XLE",
    "PSX": "XLE", "OXY": "XLE", "HAL": "XLE", "APA": "XLE",
    "MCD": "XLY", "SBUX": "XLY", "NKE": "XLY", "ROST": "XLY",
    "DLTR": "XLY", "YUM": "XLY", "DPZ": "XLY", "QSR": "XLY",
    "DE": "XLI", "MMM": "XLI", "GD": "XLI", "EMR": "XLI",
    "PH": "XLI", "ROK": "XLI", "XYL": "XLI", "AME": "XLI",
}

ALL_TICKERS = {
    "Tech": [
        # Large-cap
        "AAPL", "GOOGL", "NVDA", "MSFT", "META", "TSLA", "INTC",
        "AMD", "CRM", "NFLX", "PYPL", "UBER", "SNAP",
        "SPOT", "SHOP", "PLTR", "RBLX", "NET", "ZM", "DOCU", "TWLO",
        "MDB", "OKTA",
        # Mid-cap
        "DDOG", "CRWD", "SQ", "NOW", "SNPS", "CDNS", "BILL", "UPST",
        "SNOW", "DBX", "FTNT", "PINS", "ANET", "LRCX", "ENPH",
        "SMCI", "MSTR", "PSTG", "ALGN", "TEAM"
    ],
    "Finance": [
        # Large-cap
        "JPM", "BAC", "GS", "MS", "V", "AXP", "WFC", "BLK",
        "SCHW", "COF", "USB", "BK", "CFG", "C", "RF",
        # Mid-cap
        "SOFI", "HOOD", "COIN", "KKR", "OWL", "AVTR", "EQIX", "DLR"
    ],
    "Healthcare": [
        # Large-cap
        "PFE", "UNH", "MRK", "ABBV", "ABT", "DHR",
        "AMGN", "GILD", "BIIB", "VRTX", "SYK", "MDT",
        "BMY", "TMO",
        # Mid-cap
        "VEEV", "EXAS", "DXCM", "TMDX", "CHWY", "TECH", "ISRG", "PODD",
        "VYGR", "OSCR"
    ],
    "Energy": [
        # Large-cap
        "COP", "EOG", "MPC", "VLO", "PSX",
        "OXY", "HAL", "BKR", "OVV", "SM", "APA",
        "DVN", "FANG",
        # Mid-cap
        "MRO", "CNX", "EQT", "AR", "MTDR", "RRC", "CIVI", "DOOR"
    ],
    "Consumer": [
        # Large-cap
        "WMT", "PEP", "MCD", "SBUX", "NKE",
        "TJX", "ROST", "DG", "DLTR", "YUM", "DPZ", "QSR",
        # Mid-cap
        "DECK", "ULTA", "RH", "DASH", "ETSY", "SFIX", "LULU", "FIVE",
        "BJRI", "TPH", "PTON", "APTV"
    ],
    "Industrial": [
        # Large-cap
        "CAT", "DE", "HON", "MMM", "FDX",
        "NOC", "GD", "EMR", "PH", "ROK", "DOV", "XYL", "AME",
        "RTX", "GE",
        # Mid-cap
        "CPRT", "IEX", "IR", "STLD", "HWM", "ABM", "LIN", "AWK",
        "SITE", "ROP"
    ],
    "ETFs": [
        "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLY",
        "XLI", "XLB", "XLU", "EEM"
    ],
    "Commodities_ETF": [
        "USO", "UNG", "CORN", "WEAT", "CPER"
    ],
    "Commodities_Futures": [
        "CL=F", "GC=F", "SI=F", "HG=F", "ZW=F"
    ],
    "Crypto": [
        "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
        "ADA-USD", "DOGE-USD", "LINK-USD"
    ]
}

def get_all_tickers():
    tickers = []
    for sector, stocks in ALL_TICKERS.items():
        tickers.extend(stocks)
    return [t for t in set(tickers) if t not in LOW_ACCURACY_ASSETS]

def get_market_regime():
    """
    Returns market regime (BULL/BEAR/RANGING) using multi-signal detection.

    Signals:
    - SPY trend (50MA vs 200MA)
    - Volatility (VIX level)
    - Breadth (growth vs value participation)

    Returns: (regime_string, current_spy_price, spy_50ma)
    """
    try:
        # Use new regime detector
        regime_result = detect_regime()
        regime = regime_result.get("regime", "RANGING")
        confidence = regime_result.get("confidence", 0)

        # Get SPY price for display
        spy = yf.Ticker("SPY")
        hist = spy.history(period="1y")
        hist.index = hist.index.tz_localize(None)

        current_spy = round(hist["Close"].iloc[-1], 2)
        spy_50ma = round(hist["Close"].rolling(window=50).mean().iloc[-1], 2)

        print(f"🔍 Regime Detection:")
        print(f"   Regime: {regime} (Confidence: {confidence*100:.0f}%)")
        print(f"   Interpretation: {regime_result.get('interpretation', '')}")

        return regime, current_spy, spy_50ma

    except Exception as e:
        print(f"⚠️ Regime detection error: {str(e)[:50]} — defaulting to RANGING")
        return "RANGING", None, None

def get_sector_rsi(ticker):
    """
    Returns the RSI of the sector ETF for a given ticker.
    Used for relative strength comparison.
    """
    try:
        etf = SECTOR_ETFS.get(ticker)
        if not etf:
            return None
        stock = yf.Ticker(etf)
        hist = stock.history(period="3mo")
        hist.index = hist.index.tz_localize(None)
        return calculate_rsi(hist["Close"])
    except Exception:
        return None

def is_near_earnings(ticker, days_before=5, days_after=2):
    """
    Returns True if the ticker is within the earnings exclusion window.
    Suppresses BUY signals in the 5 days before and 2 days after earnings.
    """
    try:
        stock = yf.Ticker(ticker)
        calendar = stock.calendar
        if calendar is None or len(calendar) == 0:
            return False
        if "Earnings Date" not in calendar:
            return False
        earnings_date = calendar["Earnings Date"]
        if isinstance(earnings_date, list):
            earnings_date = earnings_date[0]
        if hasattr(earnings_date, "to_pydatetime"):
            earnings_date = earnings_date.to_pydatetime()
        earnings_date = earnings_date.replace(tzinfo=None)
        today = datetime.now()
        days_until = (earnings_date - today).days
        return -days_after <= days_until <= days_before
    except Exception:
        return False

def check_volume_consistency(volumes, lookback=5):
    """
    Returns True if volume has been consistently building over the last N days.
    More reliable than a single-day spike.
    """
    try:
        recent = volumes.tail(lookback)
        avg_volume = volumes.rolling(window=20).mean().iloc[-1]
        days_above_avg = sum(1 for v in recent if v > avg_volume)
        return days_above_avg >= 3
    except Exception:
        return False

def check_price_consistency(closes, lookback=5):
    """
    Returns up_consistent, down_consistent.
    True if 3 of last 5 closes moved in the same direction.
    """
    try:
        recent = closes.tail(lookback + 1)
        daily_changes = [recent.iloc[i] - recent.iloc[i-1] for i in range(1, len(recent))]
        up_days = sum(1 for c in daily_changes if c > 0)
        down_days = sum(1 for c in daily_changes if c < 0)
        return up_days >= 3, down_days >= 3
    except Exception:
        return False, False

def check_rsi_divergence(closes, rsi_series, lookback=10):
    """
    Detects bullish and bearish RSI divergence.
    Bullish: price making lower lows but RSI making higher lows.
    Bearish: price making higher highs but RSI making lower highs.
    """
    try:
        recent_closes = closes.tail(lookback)
        recent_rsi = rsi_series.tail(lookback)

        price_low_early = recent_closes.iloc[:lookback//2].min()
        price_low_late = recent_closes.iloc[lookback//2:].min()
        rsi_low_early = recent_rsi.iloc[:lookback//2].min()
        rsi_low_late = recent_rsi.iloc[lookback//2:].min()

        price_high_early = recent_closes.iloc[:lookback//2].max()
        price_high_late = recent_closes.iloc[lookback//2:].max()
        rsi_high_early = recent_rsi.iloc[:lookback//2].max()
        rsi_high_late = recent_rsi.iloc[lookback//2:].max()

        bullish_divergence = (
            price_low_late < price_low_early and
            rsi_low_late > rsi_low_early
        )
        bearish_divergence = (
            price_high_late > price_high_early and
            rsi_high_late < rsi_high_early
        )

        return bullish_divergence, bearish_divergence
    except Exception:
        return False, False

def check_gap(closes):
    """
    Detects significant gaps.
    gap_down: today opened significantly below yesterday's close.
    gap_up: today opened significantly above yesterday's close.
    Uses close prices as proxy since open isn't always available.
    """
    try:
        change_pct = ((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2]) * 100
        gap_down = change_pct <= -2.0
        gap_up = change_pct >= 2.0
        return gap_down, gap_up
    except Exception:
        return False, False

def check_signal_quality(score, rsi, near_support, bullish_momentum,
                          near_resistance, bearish_momentum):
    """
    Requires score >= 8 AND at least ONE strong confirming signal.
    Strong bullish: RSI oversold (<35), near support, or bullish momentum
    Strong bearish: RSI overbought (>65), near resistance, or bearish momentum
    """
    if score >= 7:
        return (
            (rsi is not None and rsi < 35) or
            near_support is True or
            bullish_momentum is True
        )
    elif score <= -7:
        return (
            (rsi is not None and rsi > 65) or
            near_resistance is True or
            bearish_momentum is True
        )
    return False

def calculate_adx(hist, period=14):
    try:
        high = hist["High"]
        low = hist["Low"]
        close = hist["Close"]

        plus_dm = high.diff()
        minus_dm = (low.shift() - low).abs()  # yesterday's low - today's low (corrected)

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
        adx = dx.rolling(window=period).mean()

        return round(adx.iloc[-1], 2), round(plus_di.iloc[-1], 2), round(minus_di.iloc[-1], 2)
    except Exception:
        return None, None, None

def find_support_resistance(closes, lookback=30):
    try:
        recent = closes.tail(lookback)
        current = closes.iloc[-1]

        resistance = round(recent.max(), 2)
        support = round(recent.min(), 2)

        price_range = resistance - support
        if price_range == 0:
            return None, None, None, None

        pct_from_support = round(((current - support) / price_range) * 100, 2)
        pct_from_resistance = round(((resistance - current) / price_range) * 100, 2)

        near_support = pct_from_support < 10
        near_resistance = pct_from_resistance < 10

        return support, resistance, near_support, near_resistance
    except Exception:
        return None, None, None, None

def check_momentum_confirmation(closes, rsi_series):
    try:
        current_price = closes.iloc[-1]
        prev_price = closes.iloc[-2]
        prev_prev_price = closes.iloc[-3]

        current_rsi = rsi_series.iloc[-1]
        prev_rsi = rsi_series.iloc[-2]

        price_turning_up = current_price > prev_price and prev_price <= prev_prev_price
        price_turning_down = current_price < prev_price and prev_price >= prev_prev_price

        rsi_turning_up = current_rsi > prev_rsi
        rsi_turning_down = current_rsi < prev_rsi

        bullish_confirmation = price_turning_up and rsi_turning_up
        bearish_confirmation = price_turning_down and rsi_turning_down

        return bullish_confirmation, bearish_confirmation
    except Exception:
        return False, False

def assign_action_label(result):
    """
    Assign a clear action label to each stock based on score, technicals, and regime.
    Returns: label string with emoji and description
    """
    score = result.get("score", 0)
    signal = result.get("signal", "NEUTRAL")
    rsi = result.get("rsi", 50)
    near_support = result.get("near_support", False)
    bullish_momentum = result.get("bullish_momentum", False)
    near_resistance = result.get("near_resistance", False)
    bearish_momentum = result.get("bearish_momentum", False)
    bullish_divergence = result.get("bullish_divergence", False)

    # Count bullish confirmers
    bullish_confirmers = 0
    if rsi and rsi < 30:
        bullish_confirmers += 1
    if bullish_divergence:
        bullish_confirmers += 1
    if near_support and bullish_momentum:
        bullish_confirmers += 1

    # BUY signal: strong setup with good score
    if signal == "BUY":
        return "🟢 BUY SIGNAL"

    # WATCH THE BOUNCE: oversold at support (best bounce candidate)
    # Works even in bear markets if price is testing key support
    if (rsi < 30 and near_support) or (rsi < 25 and near_support and bullish_divergence):
        return "📈 WATCH THE BOUNCE"

    # DON'T TRADE: negative score in strong downtrend with no bullish signals
    if score < -5 and bearish_momentum and near_resistance and bullish_confirmers == 0:
        return "❌ DON'T TRADE THIS"

    # AVOID: explicit avoid signals (strong bearish setup)
    if signal == "AVOID":
        return "❌ DON'T TRADE THIS"

    # WATCH: other marginal setups
    if signal == "WATCH":
        # Prioritize bounce setups at support
        if rsi < 35 and near_support:
            return "📈 WATCH THE BOUNCE"
        # Otherwise neutral watch
        return "⚪ WATCH FOR SETUP"

    # Default neutral
    return "⚪ NEUTRAL"

def screen_ticker(ticker, market_regime="BULL", sector_strategy=None):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        hist.index = hist.index.tz_localize(None)

        if len(hist) < 50:
            return None

        closes = hist["Close"]
        volumes = hist["Volume"]

        current_price = round(closes.iloc[-1], 2)
        prev_price = round(closes.iloc[-2], 2)
        change_pct = round(((current_price - prev_price) / prev_price) * 100, 2)

        rsi = calculate_rsi(closes)
        ma20 = round(closes.rolling(window=20).mean().iloc[-1], 2)
        ma50 = round(closes.rolling(window=50).mean().iloc[-1], 2)
        ma20_prev = round(closes.rolling(window=20).mean().iloc[-2], 2)

        avg_volume = volumes.rolling(window=20).mean().iloc[-1]
        today_volume = volumes.iloc[-1]
        volume_ratio = round(today_volume / avg_volume, 2) if avg_volume > 0 else 1

        high_30d = round(closes.tail(30).max(), 2)
        low_30d = round(closes.tail(30).min(), 2)
        pct_from_high = round(((current_price - high_30d) / high_30d) * 100, 2)
        pct_from_low = round(((current_price - low_30d) / low_30d) * 100, 2)

        crossed_above_ma20 = prev_price < ma20_prev and current_price > ma20
        crossed_below_ma20 = prev_price > ma20_prev and current_price < ma20

        adx, plus_di, minus_di = calculate_adx(hist)
        support, resistance, near_support, near_resistance = find_support_resistance(closes)

        rsi_series_proper = closes.rolling(window=15).apply(
            lambda x: calculate_rsi(pd.Series(x)), raw=False
        )
        bullish_momentum, bearish_momentum = check_momentum_confirmation(closes, rsi_series_proper)

        # New signals
        volume_consistent = check_volume_consistency(volumes)
        price_up_consistent, price_down_consistent = check_price_consistency(closes)
        bullish_divergence, bearish_divergence = check_rsi_divergence(closes, rsi_series_proper)
        gap_down, gap_up = check_gap(closes)
        sector_rsi = get_sector_rsi(ticker)
        near_earnings = is_near_earnings(ticker)

        score = 0
        reasons = []

        # RSI (regime-aware)
        if market_regime == "BULL":
            # In bull markets, overbought is NORMAL and bullish
            if rsi > 70:
                score += 3
                reasons.append(f"RSI overbought ({rsi}) — bullish in BULL market")
            elif rsi > 60:
                score += 1
                reasons.append(f"RSI elevated ({rsi}) — strength in BULL market")
            elif rsi < 40:
                score -= 1
                reasons.append(f"RSI {rsi} — weakness in BULL market")
        elif market_regime == "BEAR":
            # In bear markets, oversold is opportunity
            if rsi < 30:
                score += 3
                reasons.append(f"RSI oversold ({rsi})")
            elif rsi < 40:
                score += 1
                reasons.append(f"RSI approaching oversold ({rsi})")
            elif rsi > 70:
                score -= 3
                reasons.append(f"RSI overbought ({rsi})")
            elif rsi > 60:
                score -= 1
                reasons.append(f"RSI elevated ({rsi})")
        else:  # RANGING
            # In ranging markets, extremes are mean reversion setups
            if rsi < 30:
                score += 2
                reasons.append(f"RSI oversold ({rsi})")
            elif rsi > 70:
                score += 2
                reasons.append(f"RSI overbought ({rsi})")
            elif 40 <= rsi <= 60:
                reasons.append(f"RSI neutral ({rsi}) — ranging market")

        # Relative strength vs sector
        if sector_rsi is not None:
            if rsi < sector_rsi - 10:
                score += 1
                reasons.append(f"Stronger than sector (RSI {rsi} vs sector {round(sector_rsi, 1)})")
            elif rsi > sector_rsi + 10:
                score -= 1
                reasons.append(f"Weaker than sector (RSI {rsi} vs sector {round(sector_rsi, 1)})")

        # RSI divergence
        if bullish_divergence:
            score += 2
            reasons.append("Bullish RSI divergence — price lower lows, RSI higher lows")
        elif bearish_divergence:
            score -= 2
            reasons.append("Bearish RSI divergence — price higher highs, RSI lower highs")

        # MA crossover
        if crossed_above_ma20:
            score += 2
            reasons.append("Price crossed above MA20")
        elif crossed_below_ma20:
            score -= 2
            reasons.append("Price crossed below MA20")

        # Price vs MAs
        if current_price > ma20 and current_price > ma50:
            score += 1
            reasons.append("Above both MAs")
        elif current_price < ma20 and current_price < ma50:
            score -= 1
            reasons.append("Below both MAs")

        # MA alignment
        if ma20 > ma50:
            score += 1
            reasons.append("MA20 above MA50 — bullish structure")
        else:
            score -= 1
            reasons.append("MA20 below MA50 — bearish structure")

        # Volume
        if volume_ratio > 2:
            if change_pct > 0:
                score += 2
                reasons.append(f"High volume surge ({volume_ratio}x avg)")
            else:
                score -= 2
                reasons.append(f"High volume selloff ({volume_ratio}x avg)")
        elif volume_ratio > 1.5:
            if change_pct > 0:
                score += 1
                reasons.append(f"Above avg volume ({volume_ratio}x)")
            else:
                score -= 1
                reasons.append(f"Above avg volume selling ({volume_ratio}x)")

        # Volume consistency
        if volume_consistent and change_pct > 0:
            score += 1
            reasons.append("Volume building consistently — sustained buying")
        elif volume_consistent and change_pct < 0:
            score -= 1
            reasons.append("Volume building consistently — sustained selling")

        # Price consistency
        if price_up_consistent:
            score += 1
            reasons.append("3 of last 5 days closed higher — consistent upward pressure")
        elif price_down_consistent:
            score -= 1
            reasons.append("3 of last 5 days closed lower — consistent downward pressure")

        # Gap detection (regime-aware)
        if market_regime == "BULL":
            if gap_up:
                score += 1
                reasons.append(f"Gap up detected ({change_pct}%) — bullish momentum")
            elif gap_down:
                score -= 1
                reasons.append(f"Gap down detected ({change_pct}%) — weakness in BULL")
        elif market_regime == "BEAR":
            if gap_down:
                score += 1
                reasons.append(f"Gap down detected ({change_pct}%) — potential bounce")
            elif gap_up:
                score -= 1
                reasons.append(f"Gap up detected ({change_pct}%) — extended, watch for reversal")
        else:  # RANGING
            if gap_down:
                score += 1
                reasons.append(f"Gap down detected ({change_pct}%) — potential oversold bounce")
            elif gap_up:
                score -= 1
                reasons.append(f"Gap up detected ({change_pct}%) — extended, watch for reversal")

        # Distance from 30d range (regime-aware)
        if market_regime == "BULL":
            if pct_from_high > -2:
                score += 2
                reasons.append("At/near 30d high — bullish momentum in BULL")
            elif pct_from_low < 2:
                score -= 1
                reasons.append("Near 30d low — weakness in BULL")
        elif market_regime == "BEAR":
            if pct_from_low < 2:
                score += 1
                reasons.append("Near 30d low — potential bounce")
            elif pct_from_high > -2:
                score -= 2
                reasons.append("Near 30d high — potential resistance")
        else:  # RANGING
            if pct_from_low < 2:
                score += 1
                reasons.append("Near 30d low — potential bounce")
            elif pct_from_high > -2:
                score -= 1
                reasons.append("Near 30d high — potential resistance")

        # ADX trend strength
        if adx is not None:
            if adx > 25:
                if plus_di > minus_di:
                    score += 2
                    reasons.append(f"Strong uptrend confirmed (ADX {adx})")
                else:
                    score -= 2
                    reasons.append(f"Strong downtrend confirmed (ADX {adx})")
            elif adx < 20:
                reasons.append(f"Weak trend — ranging market (ADX {adx})")

        # Support / resistance
        if near_support:
            score += 2
            reasons.append(f"Near key support ({support})")
        elif near_resistance:
            score -= 2
            reasons.append(f"Near key resistance ({resistance})")

        # Momentum confirmation
        if bullish_momentum:
            score += 2
            reasons.append("Bullish momentum confirmed — price and RSI both turning up")
        elif bearish_momentum:
            score -= 2
            reasons.append("Bearish momentum confirmed — price and RSI both turning down")

        # IMPROVED Signal thresholds: higher bar, require 2+ strong signals
        # Count strong confirmers (RSI extreme + momentum/divergence/support)
        strong_bullish = 0
        if rsi and rsi < 30:  # Extreme oversold
            strong_bullish += 1
        if bullish_divergence:  # Price weakness but RSI strength
            strong_bullish += 1
        if near_support and bullish_momentum:  # Support + uptrend
            strong_bullish += 1
        if volume_consistent and change_pct > 0:  # Conviction
            strong_bullish += 1

        strong_bearish = 0
        if rsi and rsi > 70:  # Extreme overbought
            strong_bearish += 1
        if bearish_divergence:  # Price strength but RSI weakness
            strong_bearish += 1
        if near_resistance and bearish_momentum:  # Resistance + downtrend
            strong_bearish += 1
        if volume_consistent and change_pct < 0:  # Conviction
            strong_bearish += 1

        # REGIME-AWARE SIGNAL THRESHOLDS
        # Adjust thresholds based on market regime
        if market_regime == "BULL":
            # Bull markets: lower thresholds (favor growth/momentum)
            buy_threshold = 8
            strong_signal_count = 1
        elif market_regime == "BEAR":
            # Bear markets: higher thresholds (favor defensive/high conviction)
            buy_threshold = 10
            strong_signal_count = 1
        else:  # RANGING
            # Ranging markets: standard thresholds
            buy_threshold = 9
            strong_signal_count = 1

        # BUY Signal Logic
        if score >= buy_threshold and strong_bullish >= strong_signal_count:
            if market_regime == "BEAR":
                signal = "WATCH"
                reasons.append(f"BUY suppressed — bear market regime (requires score {buy_threshold}+, need 75%+ recovery prob)")
            elif near_earnings:
                signal = "WATCH"
                reasons.append("BUY suppressed — within earnings exclusion window")
            else:
                signal = "BUY"
        # AVOID: score lower bound AND 2+ strong bearish signals
        elif score <= -buy_threshold and strong_bearish >= strong_signal_count:
            signal = "AVOID"
        # WATCH: marginal setups (score 7-9 with some confirmation, regime-adjusted)
        elif (score >= (buy_threshold - 1) and strong_bullish >= 1) or (abs(score) >= 5 and check_signal_quality(score, rsi, near_support, bullish_momentum, near_resistance, bearish_momentum)):
            signal = "WATCH"
        else:
            signal = "NEUTRAL"

        # Calculate moat score (competitive advantage analysis)
        try:
            moat_result = score_moat(ticker)
            moat_score = moat_result.get("moat_score", 2.5)
            moat_strength = moat_result.get("strength", "UNKNOWN")
        except Exception as e:
            moat_score = 2.5
            moat_strength = "UNKNOWN"

        # SECTOR ROTATION: Apply sector boost/penalty
        sector_boost = 0
        sector_rank = "N/A"
        if sector_strategy:
            try:
                # Check which sector this ticker belongs to
                etf = SECTOR_ETFS.get(ticker)
                if etf:
                    # Get sector rank from strategy
                    sector_ranks = sector_strategy.sector_ranks
                    sector_rank = sector_ranks.get(etf, 5)  # Default to middle rank
                    sector_boost = sector_strategy.get_screener_boost(sector_rank)

                    if sector_boost > 0:
                        reasons.append(f"✅ Top sector (rank {sector_rank}) — sector rotation boost +{sector_boost}")
                    elif sector_boost < 0:
                        reasons.append(f"⚠️ Lagging sector (rank {sector_rank}) — sector rotation penalty {sector_boost}")

                    score += sector_boost
            except Exception as e:
                pass  # Sector rotation error shouldn't break screening

        result_dict = {
            "ticker": ticker,
            "price": current_price,
            "change_pct": change_pct,
            "rsi": rsi,
            "ma20": ma20,
            "ma50": ma50,
            "volume_ratio": volume_ratio,
            "pct_from_high": pct_from_high,
            "pct_from_low": pct_from_low,
            "adx": adx,
            "near_support": near_support,
            "near_resistance": near_resistance,
            "support": support,
            "resistance": resistance,
            "bullish_momentum": bullish_momentum,
            "bearish_momentum": bearish_momentum,
            "bullish_divergence": bullish_divergence,
            "bearish_divergence": bearish_divergence,
            "volume_consistent": volume_consistent,
            "price_up_consistent": price_up_consistent,
            "price_down_consistent": price_down_consistent,
            "gap_down": gap_down,
            "gap_up": gap_up,
            "near_earnings": near_earnings,
            "sector_rsi": sector_rsi,
            "moat_score": moat_score,
            "moat_strength": moat_strength,
            "sector_rank": sector_rank,
            "sector_boost": sector_boost,
            "score": score,
            "signal": signal,
            "reasons": reasons
        }
        # Add action label for clear trader guidance
        result_dict["action_label"] = assign_action_label(result_dict)
        return result_dict

    except Exception as e:
        return None

def get_cached_results():
    """Returns cached screening results if they exist and are fresh."""
    try:
        if not os.path.exists(CACHE_FILE):
            return None
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        cache_time = datetime.fromisoformat(cache.get("timestamp"))
        if datetime.now() - cache_time < timedelta(minutes=CACHE_EXPIRY_MINUTES):
            return cache.get("results"), cache.get("regime")
    except Exception:
        pass
    return None

def save_cache(results, regime):
    """Save screening results to cache."""
    try:
        cache = {
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "regime": regime
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass

def run_screen(tickers=None, use_cache=True):
    is_full_screen = tickers is None
    if tickers is None:
        tickers = get_all_tickers()

    # Try cache only for full screening
    if use_cache and is_full_screen:
        cached = get_cached_results()
        if cached:
            shortlist, regime = cached
            print(f"\n⚡ Using cached results (1 hour refresh)")
            print(f"Market regime: {regime}")
            print(f"Shortlist for Claude: {len(shortlist)}")
            return shortlist, regime

    regime, spy_price, spy_ma50 = get_market_regime()
    print(f"\nMARKET REGIME: {regime}")
    if spy_price:
        print(f"SPY: {spy_price} | 50MA: {spy_ma50}")
    if regime == "BEAR":
        print("WARNING: Bear market regime — BUY signals suppressed")

    # SECTOR ROTATION: Calculate sector scores
    print(f"\n🌍 Calculating sector rotation strategy...")
    sector_strategy = SectorRotationStrategy()
    sector_scores = sector_strategy.calculate_sector_scores()
    print(f"   Sectors ranked 1-9 by momentum, relative strength, and RSI")

    print(f"\nScreening {len(tickers)} assets...")

    results = []
    for i, ticker in enumerate(tickers):
        result = screen_ticker(ticker, market_regime=regime, sector_strategy=sector_strategy)
        if result:
            results.append(result)
        if (i + 1) % 20 == 0:
            print(f"  Screened {i + 1}/{len(tickers)}...")

    buy = [r for r in results if r["signal"] == "BUY"]
    watch = [r for r in results if r["signal"] == "WATCH"]

    shortlist = buy + watch
    shortlist.sort(key=lambda x: abs(x["score"]), reverse=True)
    shortlist = shortlist[:15]

    print(f"\nSCREENER RESULTS")
    print(f"================")
    print(f"Market regime: {regime}")
    print(f"Total screened: {len(results)}")
    print(f"BUY signals:   {len(buy)}")
    print(f"WATCH signals: {len(watch)}")
    print(f"Shortlist for Claude: {len(shortlist)}")

    # ADD MONTE CARLO RECOVERY PROBABILITY (Change #9)
    print(f"\nRunning Monte Carlo analysis (10K simulations per stock)...")
    tickers_for_mc = [r["ticker"] for r in shortlist]
    mc_results = get_monte_carlo_analysis(tickers_for_mc)

    # Add recovery probability to shortlist
    for item in shortlist:
        ticker = item["ticker"]
        if ticker in mc_results:
            mc_data = mc_results[ticker]
            item["recovery_probability"] = mc_data.get("recovery_probability", 0)
            item["recovery_probability_pct"] = mc_data.get("recovery_probability_pct", 0)
            item["median_return_1yr"] = mc_data.get("percentile_50", 0)
            item["downside_risk"] = mc_data.get("downside_risk", 0)
            item["upside_potential"] = mc_data.get("upside_potential", 0)

            # Boost score if recovery probability is high (regime-aware)
            # BULL market: 50%+ recovery prob is enough for boost
            # BEAR market: require 75%+ for boost (stricter)
            # RANGING: 60%+ is sufficient
            if regime == "BULL":
                recovery_threshold = 0.50
                strong_recovery_threshold = 0.70
            elif regime == "BEAR":
                recovery_threshold = 0.75
                strong_recovery_threshold = 0.85
            else:  # RANGING
                recovery_threshold = 0.60
                strong_recovery_threshold = 0.75

            if item["recovery_probability"] > strong_recovery_threshold:
                item["score"] += 5  # Strong recovery boost
                item["mc_signal"] = "STRONG RECOVERY"
            elif item["recovery_probability"] > recovery_threshold:
                item["score"] += 2  # Moderate recovery boost
                item["mc_signal"] = "MODERATE RECOVERY"
            else:
                item["mc_signal"] = "WEAK RECOVERY"
        else:
            item["recovery_probability_pct"] = 0
            item["mc_signal"] = "NOT ANALYZED"

    # Re-sort by updated score (now includes Monte Carlo boost)
    shortlist.sort(key=lambda x: x["score"], reverse=True)

    # CROSS-VALIDATION (Change #5): Validate financial quality
    print(f"\n✓ Running cross-validation checks (financial quality)...")
    for item in shortlist:
        try:
            ticker = item["ticker"]
            validation = validate_stock(ticker)
            item["validation_score"] = validation.get("validation_score", 0)
            item["validation_pass"] = validation.get("is_valid", False)
            item["validation_issues"] = validation.get("issues", [])

            if validation.get("is_valid"):
                item["validation_status"] = "✅ PASS"
            else:
                item["validation_status"] = "⚠️ CAUTION"
        except Exception as e:
            item["validation_status"] = "❓ ERROR"
            item["validation_score"] = 0
            item["validation_pass"] = False
            continue

    print(f"\nSHORTLIST WITH ACTION LABELS, RECOVERY & VALIDATION:")
    for r in shortlist:
        label = assign_action_label(r)
        recovery = r.get("recovery_probability_pct", 0)
        mc_signal = r.get("mc_signal", "")
        validation_status = r.get("validation_status", "❓")
        validation_score = r.get("validation_score", 0)
        print(f"  {label} — {r['ticker']} (${r['price']}) | Score: {r['score']} | Recovery: {recovery}% | Validation: {validation_status} ({validation_score}/100)")

    print(f"\nTOP BUY SIGNALS (WITH MONTE CARLO BOOST):")
    for r in buy[:5]:
        recovery = r.get("recovery_probability_pct", 0)
        print(f"  {r['ticker']} — Score: {r['score']} — Recovery Prob: {recovery}% — {', '.join(r['reasons'])}")

    # DEBATE FRAMEWORK (Change #1): High-confidence BUY signals get debated
    print(f"\n🎤 DEBATE FRAMEWORK: Running debates on top 3 BUY signals...")
    print(f"    (Bull vs Bear agents providing perspectives)\n")

    for i, buy_signal in enumerate(buy[:3]):
        try:
            ticker = buy_signal["ticker"]
            price = buy_signal.get("price", 0)
            technical_signal = buy_signal.get("signal", "BUY")
            news_sentiment = buy_signal.get("news_sentiment", "Neutral")
            recovery_prob = buy_signal.get("recovery_probability", 0.5)
            moat_score = buy_signal.get("moat_score", 2.5)
            volatility = buy_signal.get("volatility", 0.25)
            insider_activity = buy_signal.get("insider_activity", "None")

            # Run debate
            debate_result = debate_stock(
                ticker, price, technical_signal, news_sentiment,
                recovery_prob, moat_score, volatility, insider_activity
            )

            # Add debate result to shortlist item
            buy_signal["debate_synthesis"] = debate_result.get("synthesis", "")
            buy_signal["debate_complete"] = True

            # Extract confidence from debate
            synthesis = debate_result.get("synthesis", "")
            if "Confidence: 9" in synthesis or "Confidence: 10" in synthesis:
                buy_signal["debate_confidence"] = "VERY_HIGH"
                print(f"  ✅ {ticker}: DEBATE CONFIDENCE = VERY HIGH")
            elif "Confidence: 7" in synthesis or "Confidence: 8" in synthesis:
                buy_signal["debate_confidence"] = "HIGH"
                print(f"  ✅ {ticker}: DEBATE CONFIDENCE = HIGH")
            elif "Confidence: 5" in synthesis or "Confidence: 6" in synthesis:
                buy_signal["debate_confidence"] = "MEDIUM"
                print(f"  ⚠️ {ticker}: DEBATE CONFIDENCE = MEDIUM (proceed with caution)")
            else:
                buy_signal["debate_confidence"] = "LOW"
                print(f"  ❌ {ticker}: DEBATE CONFIDENCE = LOW (debate suggests caution)")

        except Exception as e:
            print(f"  ⚠️ Debate error for {buy_signal.get('ticker', 'UNKNOWN')}: {str(e)[:50]}")
            buy_signal["debate_complete"] = False
            continue

    # Save to cache if full screen
    if is_full_screen:
        save_cache(shortlist, regime)

    # Display Monte Carlo Learning Report (Change #15: Self-Learning System)
    print_learning_report()
    monthly_summary = learning_system.get_monthly_summary()
    if monthly_summary.get("completed", 0) > 0:
        print(f"\n📈 LAST 30 DAYS ACCURACY: {monthly_summary['accuracy']*100:.1f}%")
        print(f"   ({monthly_summary['completed']} trades completed)")
        if monthly_summary.get("improvement"):
            print(f"   Improvement vs baseline: +{monthly_summary['improvement']:.1f}%")

    # Return tuple with shortlist and comprehensive screening data for learning
    screening_summary = {
        "total_screened": len(results),
        "buy_signals": len(buy),
        "watch_signals": len(watch),
        "all_results": results,  # All analyzed stocks for learning
        "shortlist": shortlist,  # Filtered shortlist for trading
    }

    return shortlist, regime, screening_summary

if __name__ == "__main__":
    run_screen()