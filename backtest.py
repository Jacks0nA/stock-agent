import yfinance as yf
import pandas as pd
import json
from screener import get_all_tickers

BACKTEST_FILE = "backtest_results.json"

def calculate_rsi(closes, period=14):
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

def generate_signal(rsi, ma20, ma50, current_price, prev_price, ma20_prev,
                    volume_ratio, pct_from_low, pct_from_high,
                    adx, plus_di, minus_di, near_support, near_resistance,
                    bullish_momentum, bearish_momentum):

    if pd.isna(rsi) or pd.isna(ma20) or pd.isna(ma50):
        return "WATCH"

    bullish = 0
    bearish = 0

    if rsi < 30:
        bullish += 3
    elif rsi < 40:
        bullish += 1
    elif rsi > 70:
        bearish += 3
    elif rsi > 60:
        bearish += 1

    crossed_above_ma20 = prev_price < ma20_prev and current_price > ma20
    crossed_below_ma20 = prev_price > ma20_prev and current_price < ma20

    if crossed_above_ma20:
        bullish += 2
    elif crossed_below_ma20:
        bearish += 2

    if current_price > ma20 and current_price > ma50:
        bullish += 1
    elif current_price < ma20 and current_price < ma50:
        bearish += 1

    if ma20 > ma50:
        bullish += 1
    else:
        bearish += 1

    change_pct = ((current_price - prev_price) / prev_price) * 100
    if volume_ratio > 2:
        if change_pct > 0:
            bullish += 2
        else:
            bearish += 2
    elif volume_ratio > 1.5:
        if change_pct > 0:
            bullish += 1
        else:
            bearish += 1

    if pct_from_low < 2:
        bullish += 1
    elif pct_from_high > -2:
        bearish += 1

    if adx is not None and not pd.isna(adx) and adx > 25:
        if plus_di > minus_di:
            bullish += 2
        else:
            bearish += 2

    if near_support:
        bullish += 2
    elif near_resistance:
        bearish += 2

    if bullish_momentum:
        bullish += 2
    elif bearish_momentum:
        bearish += 2

    if bullish >= 4:
        return "BUY"
    elif bearish >= 4:
        return "AVOID"
    else:
        return "WATCH"

def run_optimised_backtest():
    print("Loading tickers...")
    tickers = get_all_tickers()
    print(f"Testing {len(tickers)} assets across multiple hold periods")
    print("This will take about 30 seconds...\n")

    hold_periods = [1, 3, 5, 10, 20]
    best_period = 5
    best_accuracy = 0
    all_results_by_period = {}

    print("Downloading price data for all assets...")
    data_cache = {}
    for i, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            hist.index = hist.index.tz_localize(None)
            if len(hist) >= 60:
                data_cache[ticker] = hist
        except Exception:
            pass
        if (i + 1) % 20 == 0:
            print(f"  Downloaded {i + 1}/{len(tickers)}...")

    print(f"\nSuccessfully downloaded {len(data_cache)} assets")
    print("\nTesting hold periods...")

    for hold_days in hold_periods:
        print(f"\nTesting {hold_days} day hold period...")
        all_results = []

        for ticker, hist in data_cache.items():
            try:
                closes = hist["Close"]
                volumes = hist["Volume"]
                rsi_series = calculate_rsi(closes)
                ma20_series = closes.rolling(window=20).mean()
                ma50_series = closes.rolling(window=50).mean()
                avg_volume_series = volumes.rolling(window=20).mean()
                high_30d_series = closes.rolling(window=30).max()
                low_30d_series = closes.rolling(window=30).min()
                adx_series, plus_di_series, minus_di_series = calculate_adx_series(hist)

                start_index = max(len(hist) - 90, 51)

                for i in range(start_index, len(hist) - hold_days):
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

                        signal = generate_signal(
                            rsi, ma20, ma50, current_price, prev_price, ma20_prev,
                            volume_ratio, pct_from_low, pct_from_high,
                            adx, plus_di, minus_di, near_support, near_resistance,
                            bullish_momentum, bearish_momentum
                        )

                        future_price = closes.iloc[i + hold_days]
                        actual_change = round(((future_price - current_price) / current_price) * 100, 2)
                        actual_direction = "UP" if actual_change > 0 else "DOWN"

                        if signal == "BUY" and actual_direction == "UP":
                            outcome = "CORRECT"
                        elif signal == "AVOID" and actual_direction == "DOWN":
                            outcome = "CORRECT"
                        elif signal == "WATCH":
                            outcome = "WATCH"
                        else:
                            outcome = "INCORRECT"

                        all_results.append({
                            "ticker": ticker,
                            "date": hist.index[i].strftime("%Y-%m-%d"),
                            "signal": signal,
                            "price": round(float(current_price), 2),
                            "rsi": round(float(rsi), 2) if not pd.isna(rsi) else None,
                            "future_price": round(float(future_price), 2),
                            "actual_change": actual_change,
                            "outcome": outcome
                        })
                    except Exception:
                        pass
            except Exception:
                pass

        scored = [r for r in all_results if r["outcome"] != "WATCH"]
        correct = [r for r in scored if r["outcome"] == "CORRECT"]
        buy_signals = [r for r in scored if r["signal"] == "BUY"]
        avoid_signals = [r for r in scored if r["signal"] == "AVOID"]
        buy_correct = [r for r in buy_signals if r["outcome"] == "CORRECT"]
        avoid_correct = [r for r in avoid_signals if r["outcome"] == "CORRECT"]
        buy_incorrect = [r for r in buy_signals if r["outcome"] == "INCORRECT"]

        overall_accuracy = round(len(correct) / len(scored) * 100, 1) if scored else 0
        buy_accuracy = round(len(buy_correct) / len(buy_signals) * 100, 1) if buy_signals else 0
        avoid_accuracy = round(len(avoid_correct) / len(avoid_signals) * 100, 1) if avoid_signals else 0
        avg_gain = round(sum(r["actual_change"] for r in buy_correct) / len(buy_correct), 2) if buy_correct else 0
        avg_loss = round(sum(r["actual_change"] for r in buy_incorrect) / len(buy_incorrect), 2) if buy_incorrect else 0

        print(f"""
HOLD PERIOD: {hold_days} days
------------------------------
Overall accuracy:  {overall_accuracy}%
Buy accuracy:      {buy_accuracy}% ({len(buy_signals)} signals)
Avoid accuracy:    {avoid_accuracy}% ({len(avoid_signals)} signals)
Avg gain correct:  +{avg_gain}%
Avg loss wrong:    {avg_loss}%
Scored signals:    {len(scored)}
Watch (skipped):   {len(all_results) - len(scored)}""")

        all_results_by_period[hold_days] = all_results

        if overall_accuracy > best_accuracy:
            best_accuracy = overall_accuracy
            best_period = hold_days

    print(f"\n{'='*40}")
    print(f"OPTIMAL HOLD PERIOD: {best_period} days ({best_accuracy}% accuracy)")
    print(f"{'='*40}")

    best_results = all_results_by_period[best_period]
    scored = [r for r in best_results if r["outcome"] != "WATCH"]

    asset_stats = {}
    for r in scored:
        t = r["ticker"]
        if t not in asset_stats:
            asset_stats[t] = {"correct": 0, "total": 0}
        asset_stats[t]["total"] += 1
        if r["outcome"] == "CORRECT":
            asset_stats[t]["correct"] += 1

    MIN_SAMPLES = 8
    sorted_assets = sorted(
        [(t, s) for t, s in asset_stats.items() if s["total"] >= MIN_SAMPLES],
        key=lambda x: x[1]["correct"] / x[1]["total"],
        reverse=True
    )

    low_sample = [(t, s) for t, s in asset_stats.items() if s["total"] < MIN_SAMPLES]

    print(f"\nTop 10 most accurate assets (min {MIN_SAMPLES} signals):")
    for ticker, stats in sorted_assets[:10]:
        acc = round(stats["correct"] / stats["total"] * 100, 1)
        print(f"  {ticker}: {acc}% ({stats['correct']}/{stats['total']} correct)")

    print(f"\nBottom 10 least accurate assets (min {MIN_SAMPLES} signals):")
    for ticker, stats in sorted_assets[-10:]:
        acc = round(stats["correct"] / stats["total"] * 100, 1)
        print(f"  {ticker}: {acc}% ({stats['correct']}/{stats['total']} correct)")

    print(f"\nAssets with insufficient signals (<{MIN_SAMPLES}) excluded: {len(low_sample)}")

    with open(BACKTEST_FILE, "w") as f:
        json.dump({
            "optimal_hold_days": best_period,
            "optimal_accuracy": best_accuracy,
            "results_by_period": {str(k): v[:100] for k, v in all_results_by_period.items()}
        }, f, indent=2)

    print(f"\nResults saved to {BACKTEST_FILE}")

if __name__ == "__main__":
    run_optimised_backtest()
