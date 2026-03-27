import yfinance as yf
import pandas as pd
import json
from datetime import datetime
from screener import (
    get_all_tickers,
    check_signal_quality,
)
from fetcher import calculate_rsi

BACKTEST_FILE = "backtest_results.json"
MIN_MOVE_PCT = 1.0

def calculate_rsi_series(closes, period=14):
    delta = closes.diff()
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_adx_series(hist, period=14):
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

        return adx, plus_di, minus_di
    except Exception:
        return None, None, None

def get_spy_regime_series():
    """
    Downloads 2 years of SPY data and returns a series of daily regime labels.
    BULL = SPY above its 50MA on that day.
    BEAR = SPY below its 50MA on that day.
    """
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="2y")
        hist.index = hist.index.tz_localize(None)
        closes = hist["Close"]
        ma50 = closes.rolling(window=50).mean()
        regime_series = pd.Series(
            ["BULL" if closes.iloc[i] > ma50.iloc[i] else "BEAR"
             for i in range(len(closes))],
            index=closes.index
        )
        return regime_series
    except Exception:
        return None

def generate_signal_full(i, closes, volumes, rsi_series, ma20_series, ma50_series,
                          avg_volume_series, high_30d_series, low_30d_series,
                          adx_series, plus_di_series, minus_di_series, market_regime):
    try:
        current_price = closes.iloc[i]
        prev_price = closes.iloc[i - 1]
        rsi = rsi_series.iloc[i]
        ma20 = ma20_series.iloc[i]
        ma50 = ma50_series.iloc[i]
        ma20_prev = ma20_series.iloc[i - 1]
        avg_vol = avg_volume_series.iloc[i]
        today_vol = volumes.iloc[i]
        volume_ratio = today_vol / avg_vol if avg_vol > 0 else 1
        high_30d = high_30d_series.iloc[i]
        low_30d = low_30d_series.iloc[i]
        pct_from_high = ((current_price - high_30d) / high_30d) * 100
        pct_from_low = ((current_price - low_30d) / low_30d) * 100
        change_pct = ((current_price - prev_price) / prev_price) * 100

        adx = adx_series.iloc[i] if adx_series is not None else None
        plus_di = plus_di_series.iloc[i] if plus_di_series is not None else None
        minus_di = minus_di_series.iloc[i] if minus_di_series is not None else None

        price_range = high_30d - low_30d
        near_support = ((current_price - low_30d) / price_range * 100 < 10) if price_range > 0 else False
        near_resistance = ((high_30d - current_price) / price_range * 100 < 10) if price_range > 0 else False

        prev_prev_price = closes.iloc[i - 2]
        prev_rsi = rsi_series.iloc[i - 1]
        price_turning_up = current_price > prev_price and prev_price <= prev_prev_price
        price_turning_down = current_price < prev_price and prev_price >= prev_prev_price
        rsi_turning_up = rsi > prev_rsi
        rsi_turning_down = rsi < prev_rsi
        bullish_momentum = price_turning_up and rsi_turning_up
        bearish_momentum = price_turning_down and rsi_turning_down

        crossed_above_ma20 = prev_price < ma20_prev and current_price > ma20
        crossed_below_ma20 = prev_price > ma20_prev and current_price < ma20

        # Volume consistency
        recent_vols = volumes.iloc[i-4:i+1]
        days_above_avg = sum(1 for v in recent_vols if v > avg_vol)
        volume_consistent = days_above_avg >= 3

        # Price consistency
        recent_closes = closes.iloc[i-4:i+1]
        daily_changes = [recent_closes.iloc[j] - recent_closes.iloc[j-1] for j in range(1, len(recent_closes))]
        up_days = sum(1 for c in daily_changes if c > 0)
        down_days = sum(1 for c in daily_changes if c < 0)
        price_up_consistent = up_days >= 3
        price_down_consistent = down_days >= 3

        # RSI divergence
        lookback = 10
        if i >= lookback:
            rsi_window = rsi_series.iloc[i-lookback:i+1]
            close_window = closes.iloc[i-lookback:i+1]
            half = lookback // 2
            price_low_early = close_window.iloc[:half].min()
            price_low_late = close_window.iloc[half:].min()
            rsi_low_early = rsi_window.iloc[:half].min()
            rsi_low_late = rsi_window.iloc[half:].min()
            price_high_early = close_window.iloc[:half].max()
            price_high_late = close_window.iloc[half:].max()
            rsi_high_early = rsi_window.iloc[:half].max()
            rsi_high_late = rsi_window.iloc[half:].max()
            bullish_divergence = price_low_late < price_low_early and rsi_low_late > rsi_low_early
            bearish_divergence = price_high_late > price_high_early and rsi_high_late < rsi_high_early
        else:
            bullish_divergence = False
            bearish_divergence = False

        # Gap detection
        gap_down = change_pct <= -2.0
        gap_up = change_pct >= 2.0

        if pd.isna(rsi) or pd.isna(ma20) or pd.isna(ma50):
            return "NEUTRAL"

        score = 0

        if rsi < 30:
            score += 3
        elif rsi < 40:
            score += 1
        elif rsi > 70:
            score -= 3
        elif rsi > 60:
            score -= 1

        if bullish_divergence:
            score += 2
        elif bearish_divergence:
            score -= 2

        if crossed_above_ma20:
            score += 2
        elif crossed_below_ma20:
            score -= 2

        if current_price > ma20 and current_price > ma50:
            score += 1
        elif current_price < ma20 and current_price < ma50:
            score -= 1

        if ma20 > ma50:
            score += 1
        else:
            score -= 1

        if volume_ratio > 2:
            if change_pct > 0:
                score += 2
            else:
                score -= 2
        elif volume_ratio > 1.5:
            if change_pct > 0:
                score += 1
            else:
                score -= 1

        if volume_consistent and change_pct > 0:
            score += 1
        elif volume_consistent and change_pct < 0:
            score -= 1

        if price_up_consistent:
            score += 1
        elif price_down_consistent:
            score -= 1

        if gap_down:
            score += 1
        elif gap_up:
            score -= 1

        if pct_from_low < 2:
            score += 1
        elif pct_from_high > -2:
            score -= 1

        if adx is not None and not pd.isna(adx) and adx > 25:
            if plus_di > minus_di:
                score += 2
            else:
                score -= 2

        if near_support:
            score += 2
        elif near_resistance:
            score -= 2

        if bullish_momentum:
            score += 2
        elif bearish_momentum:
            score -= 2

        has_quality = check_signal_quality(
            score, rsi, near_support, bullish_momentum,
            near_resistance, bearish_momentum
        )

        if score >= 6 and has_quality:
            if market_regime == "BEAR":
                return "WATCH"
            return "BUY"
        elif score <= -6 and has_quality:
            return "AVOID"
        elif abs(score) >= 3:
            return "WATCH"
        else:
            return "NEUTRAL"

    except Exception:
        return "NEUTRAL"

def run_optimised_backtest():
    print("Loading tickers...")
    tickers = get_all_tickers()

    print(f"Testing {len(tickers)} assets")
    print(f"Minimum move threshold: {MIN_MOVE_PCT}%")
    print(f"Multi-checkpoint validation: price must hold direction at day 1, 3 AND 5")
    print(f"Per-day regime calculation: SPY vs 50MA on each historical day")
    print("This will take 3-5 minutes...\n")

    print("Downloading SPY regime data...")
    spy_regime_series = get_spy_regime_series()
    if spy_regime_series is not None:
        bull_days = (spy_regime_series == "BULL").sum()
        bear_days = (spy_regime_series == "BEAR").sum()
        print(f"SPY regime over 2 years: {bull_days} BULL days, {bear_days} BEAR days\n")
    else:
        print("WARNING: Could not load SPY regime data — defaulting to BULL for all days\n")

    all_results = []

    print("Downloading price data for all assets...")
    data_cache = {}
    for i, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2y")
            hist.index = hist.index.tz_localize(None)
            if len(hist) >= 60:
                data_cache[ticker] = hist
        except Exception:
            pass
        if (i + 1) % 20 == 0:
            print(f"  Downloaded {i + 1}/{len(tickers)}...")

    print(f"\nSuccessfully downloaded {len(data_cache)} assets")
    print("\nRunning multi-checkpoint backtest with per-day regime...\n")

    for ticker, hist in data_cache.items():
        try:
            closes = hist["Close"]
            volumes = hist["Volume"]
            rsi_series = calculate_rsi_series(closes)
            ma20_series = closes.rolling(window=20).mean()
            ma50_series = closes.rolling(window=50).mean()
            avg_volume_series = volumes.rolling(window=20).mean()
            high_30d_series = closes.rolling(window=30).max()
            low_30d_series = closes.rolling(window=30).min()
            adx_series, plus_di_series, minus_di_series = calculate_adx_series(hist)

            start_index = max(len(hist) - 500, 51)

            for i in range(start_index, len(hist) - 5):
                try:
                    # Get regime for this specific day
                    current_date = closes.index[i]
                    if spy_regime_series is not None and current_date in spy_regime_series.index:
                        day_regime = spy_regime_series[current_date]
                    else:
                        # Find nearest date
                        nearest = spy_regime_series.index.get_indexer(
                            [current_date], method="nearest"
                        )[0] if spy_regime_series is not None else None
                        day_regime = spy_regime_series.iloc[nearest] if nearest is not None else "BULL"

                    signal = generate_signal_full(
                        i, closes, volumes, rsi_series,
                        ma20_series, ma50_series, avg_volume_series,
                        high_30d_series, low_30d_series,
                        adx_series, plus_di_series, minus_di_series,
                        day_regime
                    )

                    current_price = closes.iloc[i]
                    price_1d = closes.iloc[i + 1]
                    price_3d = closes.iloc[i + 3]
                    price_5d = closes.iloc[i + 5]

                    change_1d = ((price_1d - current_price) / current_price) * 100
                    change_3d = ((price_3d - current_price) / current_price) * 100
                    change_5d = ((price_5d - current_price) / current_price) * 100

                    if signal == "BUY":
                        best_move = max(change_1d, change_3d, change_5d)
                        worst_move = min(change_1d, change_3d, change_5d)
                        if best_move >= MIN_MOVE_PCT:
                            outcome = "CORRECT"
                        elif worst_move <= -MIN_MOVE_PCT:
                            outcome = "INCORRECT"
                        else:
                            outcome = "WATCH"
                    elif signal == "AVOID":
                        if change_1d <= -MIN_MOVE_PCT and change_3d <= -MIN_MOVE_PCT and change_5d <= -MIN_MOVE_PCT:
                            outcome = "CORRECT"
                        elif change_5d >= MIN_MOVE_PCT:
                            outcome = "INCORRECT"
                        else:
                            outcome = "WATCH"
                    else:
                        outcome = "WATCH"

                    all_results.append({
                        "ticker": ticker,
                        "date": hist.index[i].strftime("%Y-%m-%d"),
                        "signal": signal,
                        "regime": day_regime,
                        "price": round(float(current_price), 2),
                        "rsi": round(float(rsi_series.iloc[i]), 2) if not pd.isna(rsi_series.iloc[i]) else None,
                        "price_1d": round(float(price_1d), 2),
                        "price_3d": round(float(price_3d), 2),
                        "price_5d": round(float(price_5d), 2),
                        "change_1d": round(change_1d, 2),
                        "change_3d": round(change_3d, 2),
                        "change_5d": round(change_5d, 2),
                        "outcome": outcome
                    })

                except Exception:
                    pass
        except Exception:
            pass

    # Results
    scored = [r for r in all_results if r["outcome"] != "WATCH"]
    correct = [r for r in scored if r["outcome"] == "CORRECT"]
    buy_signals = [r for r in scored if r["signal"] == "BUY"]
    avoid_signals = [r for r in scored if r["signal"] == "AVOID"]
    buy_correct = [r for r in buy_signals if r["outcome"] == "CORRECT"]
    avoid_correct = [r for r in avoid_signals if r["outcome"] == "CORRECT"]
    buy_incorrect = [r for r in buy_signals if r["outcome"] == "INCORRECT"]

    # Split by regime
    buy_bull = [r for r in buy_signals if r["regime"] == "BULL"]
    buy_bull_correct = [r for r in buy_bull if r["outcome"] == "CORRECT"]
    buy_bear = [r for r in buy_signals if r["regime"] == "BEAR"]
    buy_bear_correct = [r for r in buy_bear if r["outcome"] == "CORRECT"]

    overall_accuracy = round(len(correct) / len(scored) * 100, 1) if scored else 0
    buy_accuracy = round(len(buy_correct) / len(buy_signals) * 100, 1) if buy_signals else 0
    avoid_accuracy = round(len(avoid_correct) / len(avoid_signals) * 100, 1) if avoid_signals else 0
    buy_bull_accuracy = round(len(buy_bull_correct) / len(buy_bull) * 100, 1) if buy_bull else 0
    buy_bear_accuracy = round(len(buy_bear_correct) / len(buy_bear) * 100, 1) if buy_bear else 0

    avg_gain_1d = round(sum(r["change_1d"] for r in buy_correct) / len(buy_correct), 2) if buy_correct else 0
    avg_gain_3d = round(sum(r["change_3d"] for r in buy_correct) / len(buy_correct), 2) if buy_correct else 0
    avg_gain_5d = round(sum(r["change_5d"] for r in buy_correct) / len(buy_correct), 2) if buy_correct else 0
    avg_loss_5d = round(sum(r["change_5d"] for r in buy_incorrect) / len(buy_incorrect), 2) if buy_incorrect else 0

    print(f"""
MULTI-CHECKPOINT RESULTS (must hold direction at day 1, 3 AND 5)
=================================================================
Overall accuracy:     {overall_accuracy}%
Buy accuracy:         {buy_accuracy}% ({len(buy_signals)} signals)
  — Bull market:      {buy_bull_accuracy}% ({len(buy_bull)} signals)
  — Bear market:      {buy_bear_accuracy}% ({len(buy_bear)} signals)
Avoid accuracy:       {avoid_accuracy}% ({len(avoid_signals)} signals)

Buy correct avg gain:
  Day 1:  +{avg_gain_1d}%
  Day 3:  +{avg_gain_3d}%
  Day 5:  +{avg_gain_5d}%
Buy incorrect avg loss (day 5): {avg_loss_5d}%

Scored signals:       {len(scored)}
Excluded (ambiguous / watch / neutral): {len(all_results) - len(scored)}
""")

    # Per asset breakdown
    asset_stats = {}
    for r in scored:
        t = r["ticker"]
        if t not in asset_stats:
            asset_stats[t] = {"correct": 0, "total": 0}
        asset_stats[t]["total"] += 1
        if r["outcome"] == "CORRECT":
            asset_stats[t]["correct"] += 1

    MIN_SAMPLES = 5
    sorted_assets = sorted(
        [(t, s) for t, s in asset_stats.items() if s["total"] >= MIN_SAMPLES],
        key=lambda x: x[1]["correct"] / x[1]["total"],
        reverse=True
    )

    low_sample = [(t, s) for t, s in asset_stats.items() if s["total"] < MIN_SAMPLES]

    print(f"Top 10 most accurate assets (min {MIN_SAMPLES} signals):")
    for ticker, stats in sorted_assets[:10]:
        acc = round(stats["correct"] / stats["total"] * 100, 1)
        print(f"  {ticker}: {acc}% ({stats['correct']}/{stats['total']} correct)")

    print(f"\nBottom 10 least accurate assets (min {MIN_SAMPLES} signals):")
    for ticker, stats in sorted_assets[-10:]:
        acc = round(stats["correct"] / stats["total"] * 100, 1)
        print(f"  {ticker}: {acc}% ({stats['correct']}/{stats['total']} correct)")

    print(f"\nAssets with insufficient signals (<{MIN_SAMPLES}) excluded: {len(low_sample)}")

    print(f"\n--- UPDATED HIGH ACCURACY ASSETS (>60%, min {MIN_SAMPLES} signals) ---")
    high_acc = [(t, round(s["correct"] / s["total"] * 100, 1))
                for t, s in asset_stats.items()
                if s["total"] >= MIN_SAMPLES and (s["correct"] / s["total"]) > 0.60]
    high_acc.sort(key=lambda x: x[1], reverse=True)
    for t, acc in high_acc:
        print(f'  "{t}": {acc},')

    print(f"\n--- UPDATED LOW ACCURACY ASSETS (<45%, min {MIN_SAMPLES} signals) ---")
    low_acc = [(t, round(s["correct"] / s["total"] * 100, 1))
               for t, s in asset_stats.items()
               if s["total"] >= MIN_SAMPLES and (s["correct"] / s["total"]) < 0.45]
    low_acc.sort(key=lambda x: x[1])
    for t, acc in low_acc:
        print(f'  "{t}": {acc},')

    with open(BACKTEST_FILE, "w") as f:
        json.dump({
            "methodology": "Multi-checkpoint with per-day regime: BUY correct only if up >= 1% at day 1, 3 AND 5",
            "min_move_pct": MIN_MOVE_PCT,
            "overall_accuracy": overall_accuracy,
            "buy_accuracy": buy_accuracy,
            "buy_bull_accuracy": buy_bull_accuracy,
            "buy_bear_accuracy": buy_bear_accuracy,
            "avoid_accuracy": avoid_accuracy,
            "total_scored": len(scored),
            "asset_stats": {
                t: {
                    **s,
                    "accuracy": round(s["correct"] / s["total"] * 100, 1)
                }
                for t, s in asset_stats.items() if s["total"] >= MIN_SAMPLES
            },
            "sample_results": all_results[:200]
        }, f, indent=2)

    print(f"\nResults saved to {BACKTEST_FILE}")

if __name__ == "__main__":
    run_optimised_backtest()