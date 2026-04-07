import yfinance as yf
import pandas as pd
from fetcher import calculate_rsi
from datetime import datetime, timedelta
import json
import os

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
    Returns BULL, BEAR, or NEUTRAL based on SPY vs its 50MA.
    BEAR suppresses BUY signals entirely.
    """
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="3mo")
        hist.index = hist.index.tz_localize(None)
        current = hist["Close"].iloc[-1]
        ma50 = hist["Close"].rolling(window=50).mean().iloc[-1]
        if current > ma50:
            return "BULL", round(current, 2), round(ma50, 2)
        else:
            return "BEAR", round(current, 2), round(ma50, 2)
    except Exception:
        return "NEUTRAL", None, None

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
        minus_dm = low.diff().abs()

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

def screen_ticker(ticker, market_regime="BULL"):
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

        # RSI
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

        # Gap detection
        if gap_down:
            score += 1
            reasons.append(f"Gap down detected ({change_pct}%) — potential oversold bounce")
        elif gap_up:
            score -= 1
            reasons.append(f"Gap up detected ({change_pct}%) — extended, watch for reversal")

        # Distance from 30d range
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

        # BUY: score 10+ AND 2+ strong bullish signals
        if score >= 10 and strong_bullish >= 2:
            if market_regime == "BEAR":
                signal = "WATCH"
                reasons.append("BUY suppressed — bear market regime (SPY below 50MA)")
            elif near_earnings:
                signal = "WATCH"
                reasons.append("BUY suppressed — within earnings exclusion window")
            else:
                signal = "BUY"
        # AVOID: score -10 or lower AND 2+ strong bearish signals
        elif score <= -10 and strong_bearish >= 2:
            signal = "AVOID"
        # WATCH: marginal setups (score 7-9 with some confirmation)
        elif (score >= 7 and strong_bullish >= 1) or (abs(score) >= 5 and check_signal_quality(score, rsi, near_support, bullish_momentum, near_resistance, bearish_momentum)):
            signal = "WATCH"
        else:
            signal = "NEUTRAL"

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

    print(f"\nScreening {len(tickers)} assets...")

    results = []
    for i, ticker in enumerate(tickers):
        result = screen_ticker(ticker, market_regime=regime)
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

    print(f"\nSHORTLIST WITH ACTION LABELS:")
    for r in shortlist:
        label = assign_action_label(r)
        print(f"  {label} — {r['ticker']} (${r['price']}) | Score: {r['score']}")

    print(f"\nTOP BUY SIGNALS:")
    for r in buy[:5]:
        print(f"  {r['ticker']} — Score: {r['score']} — {', '.join(r['reasons'])}")

    # Save to cache if full screen
    if is_full_screen:
        save_cache(shortlist, regime)

    return shortlist, regime

if __name__ == "__main__":
    run_screen()