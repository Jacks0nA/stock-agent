import yfinance as yf
import pandas as pd
import math
from fetcher import calculate_rsi

# Regime thresholds
VIX_FEAR_THRESHOLD = 20
VIX_COMPLACENCY_THRESHOLD = 15
VIX_BEAR_THRESHOLD = 25

RSI_BULL_MIN = 40
RSI_BULL_MAX = 70
RSI_BEAR_MIN = 20
RSI_BEAR_MAX = 50
RSI_RANGING_MIN = 40
RSI_RANGING_MAX = 60

REGIME_BULL = "BULL"
REGIME_BEAR = "BEAR"
REGIME_RANGING = "RANGING"
REGIME_UNKNOWN = "UNKNOWN"


def _fetch_spy_data():
    """
    Fetches SPY price history (1 year) for MA and RSI calculations.
    Returns (hist DataFrame, closes Series) or raises on failure.
    """
    spy = yf.Ticker("SPY")
    hist = spy.history(period="1y")
    hist.index = hist.index.tz_localize(None)
    if len(hist) < 200:
        raise ValueError(f"Insufficient SPY history: {len(hist)} bars")
    return hist, hist["Close"]


def _fetch_vix():
    """
    Fetches the latest VIX closing level via the ^VIX ticker.
    Returns a float or None on failure.
    """
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        hist.index = hist.index.tz_localize(None)
        if len(hist) == 0:
            return None
        return round(hist["Close"].iloc[-1], 2)
    except Exception:
        return None


def _volume_trend(volumes, lookback=10):
    """
    Returns True if average volume over the last `lookback` days is higher
    than the preceding `lookback`-day window — i.e. volume is increasing.
    """
    try:
        if len(volumes) < lookback * 2:
            return None
        recent_avg = volumes.iloc[-lookback:].mean()
        prior_avg = volumes.iloc[-(lookback * 2):-lookback].mean()
        if prior_avg == 0:
            return None
        return recent_avg > prior_avg
    except Exception:
        return None


def _score_regime(
    price, ma20, ma50, ma200,
    rsi, vix, volume_rising
):
    """
    Scores each regime (BULL, BEAR, RANGING) based on indicator alignment.
    Returns a dict of {regime: score} and a list of contributing reasons.
    """
    scores = {REGIME_BULL: 0, REGIME_BEAR: 0, REGIME_RANGING: 0}
    reasons = []

    # --- SPY vs MA20 ---
    if price > ma20:
        scores[REGIME_BULL] += 1
        reasons.append(f"SPY above MA20 ({round(ma20, 2)})")
    else:
        scores[REGIME_BEAR] += 1
        scores[REGIME_RANGING] += 1
        reasons.append(f"SPY below MA20 ({round(ma20, 2)})")

    # --- SPY vs MA50 ---
    if price > ma50:
        scores[REGIME_BULL] += 2
        reasons.append(f"SPY above MA50 ({round(ma50, 2)})")
    else:
        scores[REGIME_BEAR] += 2
        scores[REGIME_RANGING] += 1
        reasons.append(f"SPY below MA50 ({round(ma50, 2)})")

    # --- SPY vs MA200 ---
    if not math.isnan(ma200):
        if price > ma200:
            scores[REGIME_BULL] += 2
            reasons.append(f"SPY above MA200 ({round(ma200, 2)}) — long-term uptrend")
        else:
            scores[REGIME_BEAR] += 2
            reasons.append(f"SPY below MA200 ({round(ma200, 2)}) — long-term downtrend")

    # --- RSI ---
    if RSI_BULL_MIN <= rsi <= RSI_BULL_MAX:
        scores[REGIME_BULL] += 2
        reasons.append(f"RSI {rsi} — bullish range (40-70)")
    elif RSI_BEAR_MIN <= rsi < RSI_BEAR_MAX:
        scores[REGIME_BEAR] += 2
        reasons.append(f"RSI {rsi} — bearish range (20-50)")
    if RSI_RANGING_MIN <= rsi <= RSI_RANGING_MAX:
        scores[REGIME_RANGING] += 2
        reasons.append(f"RSI {rsi} — ranging zone (40-60)")

    # --- VIX ---
    if vix is not None:
        if vix < VIX_COMPLACENCY_THRESHOLD:
            scores[REGIME_BULL] += 2
            reasons.append(f"VIX {vix} — complacency (<15), risk-on")
        elif vix < VIX_FEAR_THRESHOLD:
            scores[REGIME_BULL] += 1
            scores[REGIME_RANGING] += 1
            reasons.append(f"VIX {vix} — moderate (<20), neutral fear")
        elif vix < VIX_BEAR_THRESHOLD:
            scores[REGIME_RANGING] += 2
            scores[REGIME_BEAR] += 1
            reasons.append(f"VIX {vix} — elevated (20-25), caution")
        else:
            scores[REGIME_BEAR] += 3
            reasons.append(f"VIX {vix} — fear zone (>25), risk-off")
    else:
        reasons.append("VIX unavailable — skipped in regime scoring")

    # --- Volume trend ---
    if volume_rising is True:
        scores[REGIME_BULL] += 1
        reasons.append("Volume trend rising — buying conviction")
    elif volume_rising is False:
        scores[REGIME_RANGING] += 1
        reasons.append("Volume trend declining — waning conviction")

    return scores, reasons


def get_market_regime():
    """
    Detects the current market regime: BULL, BEAR, or RANGING.

    Uses SPY price vs 20MA / 50MA / 200MA, RSI(14) of SPY,
    VIX level, and volume trend to score each regime.

    Returns a dict:
        {
            "regime":         str,   # "BULL" | "BEAR" | "RANGING" | "UNKNOWN"
            "spy_price":      float,
            "ma20":           float,
            "ma50":           float,
            "ma200":          float | None,
            "rsi":            float,
            "vix":            float | None,
            "volume_rising":  bool  | None,
            "scores":         dict,  # {regime: score}
            "reasons":        list,  # contributing signal descriptions
            "confidence":     str,   # "HIGH" | "MEDIUM" | "LOW"
        }
    """
    result = {
        "regime": REGIME_UNKNOWN,
        "spy_price": None,
        "ma20": None,
        "ma50": None,
        "ma200": None,
        "rsi": None,
        "vix": None,
        "volume_rising": None,
        "scores": {},
        "reasons": [],
        "confidence": "LOW",
    }

    try:
        hist, closes = _fetch_spy_data()
        volumes = hist["Volume"]

        price = round(closes.iloc[-1], 2)
        ma20 = round(closes.rolling(window=20).mean().iloc[-1], 2)
        ma50 = round(closes.rolling(window=50).mean().iloc[-1], 2)
        ma200_raw = closes.rolling(window=200).mean().iloc[-1]
        ma200 = round(ma200_raw, 2) if not math.isnan(ma200_raw) else None

        rsi = calculate_rsi(closes)
        vix = _fetch_vix()
        volume_rising = _volume_trend(volumes)

        scores, reasons = _score_regime(
            price=price,
            ma20=ma20,
            ma50=ma50,
            ma200=ma200_raw if ma200 is not None else float("nan"),
            rsi=rsi,
            vix=vix,
            volume_rising=volume_rising,
        )

        # Determine winning regime
        top_regime = max(scores, key=scores.get)
        top_score = scores[top_regime]

        # Require a meaningful margin over the next-best regime
        sorted_scores = sorted(scores.values(), reverse=True)
        margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else top_score

        if margin >= 3:
            confidence = "HIGH"
        elif margin >= 1:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
            # Tie-break: default to RANGING when signals are mixed
            top_regime = REGIME_RANGING
            reasons.append("Mixed signals — defaulting to RANGING")

        result.update({
            "regime": top_regime,
            "spy_price": price,
            "ma20": ma20,
            "ma50": ma50,
            "ma200": ma200,
            "rsi": rsi,
            "vix": vix,
            "volume_rising": volume_rising,
            "scores": scores,
            "reasons": reasons,
            "confidence": confidence,
        })

    except Exception as e:
        result["reasons"].append(f"Regime detection failed: {e}")

    return result


def get_regime_label(regime_data):
    """
    Returns a concise human-readable label for display in the UI or agent context.
    Example: "BULL (HIGH confidence) — SPY $512.34, VIX 14.2"
    """
    regime = regime_data.get("regime", REGIME_UNKNOWN)
    confidence = regime_data.get("confidence", "LOW")
    spy = regime_data.get("spy_price")
    vix = regime_data.get("vix")

    label = f"{regime} ({confidence} confidence)"
    if spy:
        label += f" — SPY ${spy}"
    if vix:
        label += f", VIX {vix}"
    return label


def regime_suppresses_buys(regime_data):
    """
    Returns True if the current regime should suppress BUY signals.
    BEAR regime always suppresses. RANGING does not.
    """
    return regime_data.get("regime") == REGIME_BEAR


def regime_requires_caution(regime_data):
    """
    Returns True if the current regime warrants extra caution (RANGING or low-confidence).
    """
    regime = regime_data.get("regime")
    confidence = regime_data.get("confidence")
    return regime == REGIME_RANGING or confidence == "LOW"


if __name__ == "__main__":
    data = get_market_regime()
    print(f"\nMARKET REGIME DETECTION")
    print(f"=======================")
    print(f"Regime:        {data['regime']}")
    print(f"Confidence:    {data['confidence']}")
    print(f"SPY Price:     {data['spy_price']}")
    print(f"MA20:          {data['ma20']}")
    print(f"MA50:          {data['ma50']}")
    print(f"MA200:         {data['ma200']}")
    print(f"RSI (SPY):     {data['rsi']}")
    print(f"VIX:           {data['vix']}")
    print(f"Volume rising: {data['volume_rising']}")
    print(f"\nScores:        {data['scores']}")
    print(f"\nSignals:")
    for r in data["reasons"]:
        print(f"  - {r}")
    print(f"\nLabel: {get_regime_label(data)}")
