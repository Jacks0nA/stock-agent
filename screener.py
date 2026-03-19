import yfinance as yf
import pandas as pd
from fetcher import calculate_rsi

# Assets with proven low backtest accuracy — excluded from screening entirely
LOW_ACCURACY_ASSETS = {
    "FANG", "AMZN", "UNH", "C", "TMO", "GC=F", "RF", "DVN", "RTX", "CPER",
    "CFG", "BNB-USD", "COF", "TJX", "NOC", "GILD", "FDX", "PEP", "DG", "MRK",
    "HON", "USB", "SI=F", "DOV", "GE", "BIIB", "XLB", "USO", "AMGN", "CAT",
    "WMT", "QSR", "SM", "AMD", "BKR", "WFC", "OVV"
}

ALL_TICKERS = {
    "Tech": [
        "AAPL", "GOOGL", "NVDA", "MSFT", "META", "TSLA", "INTC",
        "AMD", "CRM", "NFLX", "PYPL", "UBER", "SNAP",
        "SPOT", "SHOP", "PLTR", "RBLX", "NET", "ZM", "DOCU", "TWLO",
        "MDB", "OKTA"
    ],
    "Finance": [
        "JPM", "BAC", "GS", "MS", "V", "AXP", "WFC", "BLK",
        "SCHW", "COF", "USB", "BK", "CFG"
    ],
    "Healthcare": [
        "PFE", "UNH", "MRK", "ABBV", "ABT", "DHR",
        "AMGN", "GILD", "BIIB", "VRTX", "SYK", "MDT"
    ],
    "Energy": [
        "COP", "EOG", "MPC", "VLO", "PSX",
        "OXY", "HAL", "BKR", "OVV", "SM", "APA"
    ],
    "Consumer": [
        "WMT", "PEP", "MCD", "SBUX", "NKE",
        "TJX", "ROST", "DG", "DLTR", "YUM", "DPZ", "QSR"
    ],
    "Industrial": [
        "CAT", "DE", "HON", "MMM", "FDX",
        "NOC", "GD", "EMR", "PH", "ROK", "DOV", "XYL", "AME"
    ],
    "ETFs": [
        "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLY",
        "XLI", "XLB", "XLU", "EEM"
    ],
    "Commodities_ETF": [
        "USO", "UNG", "CORN", "WEAT"
    ],
    "Commodities_Futures": [
        "CL=F", "SI=F", "HG=F", "ZW=F"
    ],
    "Crypto": [
        "SOL-USD", "BNB-USD", "XRP-USD",
        "ADA-USD", "DOGE-USD", "LINK-USD"
    ]
}

def get_all_tickers():
    tickers = []
    for sector, stocks in ALL_TICKERS.items():
        tickers.extend(stocks)
    return [t for t in set(tickers) if t not in LOW_ACCURACY_ASSETS]

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

def screen_ticker(ticker):
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

        # Support / resistance — no $ sign to avoid Streamlit rendering bug
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

        # Signal thresholds
        if score >= 6:
            signal = "BUY"
        elif score <= -6:
            signal = "AVOID"
        elif abs(score) >= 3:
            signal = "WATCH"
        else:
            signal = "NEUTRAL"

        return {
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
            "score": score,
            "signal": signal,
            "reasons": reasons
        }

    except Exception as e:
        return None

def run_screen(tickers=None):
    if tickers is None:
        tickers = get_all_tickers()

    print(f"Screening {len(tickers)} assets (low accuracy assets pre-excluded)...")

    results = []
    for i, ticker in enumerate(tickers):
        result = screen_ticker(ticker)
        if result:
            results.append(result)
        if (i + 1) % 20 == 0:
            print(f"  Screened {i + 1}/{len(tickers)}...")

    buy = [r for r in results if r["signal"] == "BUY"]
    watch = [r for r in results if r["signal"] == "WATCH"]

    # AVOID excluded — backtest shows only 24.6% accuracy
    shortlist = buy + watch
    shortlist.sort(key=lambda x: abs(x["score"]), reverse=True)
    shortlist = shortlist[:15]

    print(f"\nSCREENER RESULTS")
    print(f"================")
    print(f"Total screened: {len(results)}")
    print(f"BUY signals:   {len(buy)}")
    print(f"WATCH signals: {len(watch)}")
    print(f"Shortlist for Claude: {len(shortlist)}")

    print(f"\nTOP BUY SIGNALS:")
    for r in buy[:5]:
        print(f"  {r['ticker']} — Score: {r['score']} — {', '.join(r['reasons'])}")

    return shortlist

if __name__ == "__main__":
    run_screen()