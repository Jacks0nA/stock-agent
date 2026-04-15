import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

MIN_OPTIONS_VALUE = 500000


def get_iv_percentile(ticker, current_iv):
    """
    Calculate IV percentile (where current IV ranks vs 52-week range).

    Returns:
        float: IV percentile 0-100 (0 = lowest, 100 = highest in period)
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")

        if hist.empty or len(hist) < 252:
            return 50.0  # Default neutral

        # Approximate IV from historical volatility as proxy
        returns = hist["Close"].pct_change().dropna()
        historical_volatility = returns.std() * np.sqrt(252) * 100

        # Simple percentile rank of current IV vs historical vol distribution
        vol_percentiles = [historical_volatility * (0.8 + (i * 0.04)) for i in range(6)]

        iv_pct = 0
        for i, threshold in enumerate(vol_percentiles):
            if current_iv >= threshold:
                iv_pct = min(100, 20 + (i * 20))

        return round(iv_pct, 0)

    except Exception:
        return 50.0


def get_put_call_ratio(calls_data, puts_data):
    """
    Calculate put/call ratio and trend.

    Returns:
        dict with ratio, interpretation, and trend
    """
    try:
        call_volume = calls_data["volume"].sum() if not calls_data.empty else 0
        put_volume = puts_data["volume"].sum() if not puts_data.empty else 0

        if call_volume == 0 and put_volume == 0:
            return {"ratio": 1.0, "interpretation": "No activity", "signal": "⚪ NEUTRAL"}

        ratio = put_volume / max(call_volume, 1)

        if ratio < 0.6:
            interpretation = "Heavy call volume (bullish bias)"
            signal = "🟢 BULLISH"
        elif ratio < 1.0:
            interpretation = "More calls than puts (slightly bullish)"
            signal = "🟢 BULLISH"
        elif ratio < 1.5:
            interpretation = "Balanced call/put activity"
            signal = "⚪ NEUTRAL"
        elif ratio < 2.0:
            interpretation = "More puts than calls (slightly bearish)"
            signal = "🔴 BEARISH"
        else:
            interpretation = "Heavy put volume (bearish bias)"
            signal = "🔴 BEARISH"

        return {
            "ratio": round(ratio, 2),
            "call_volume": int(call_volume),
            "put_volume": int(put_volume),
            "interpretation": interpretation,
            "signal": signal
        }

    except Exception:
        return {"ratio": 1.0, "interpretation": "Error calculating", "signal": "⚪ NEUTRAL"}

def get_options_flow(ticker):
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return None

        near_expiry = expirations[:3]
        unusual_activity = []

        for expiry in near_expiry:
            try:
                chain = stock.option_chain(expiry)
                calls = chain.calls
                puts = chain.puts
                current_price = stock.fast_info.last_price

                calls = calls[
                    (calls["volume"] > 100) &
                    (calls["volume"] > calls["openInterest"] * 0.5)
                ].copy()

                puts = puts[
                    (puts["volume"] > 100) &
                    (puts["volume"] > puts["openInterest"] * 0.5)
                ].copy()

                for _, row in calls.iterrows():
                    try:
                        strike = row["strike"]
                        volume = row["volume"]
                        open_interest = row["openInterest"]
                        iv = row["impliedVolatility"]
                        premium = row["lastPrice"]
                        total_value = volume * premium * 100

                        if total_value < MIN_OPTIONS_VALUE:
                            continue

                        pct_otm = ((strike - current_price) / current_price) * 100
                        signal = "🟢 BULLISH" if volume > 500 or total_value > 1000000 else "⚪ MODERATE BULLISH"

                        unusual_activity.append({
                            "type": "CALL",
                            "signal": signal,
                            "expiry": expiry,
                            "strike": strike,
                            "volume": int(volume),
                            "open_interest": int(open_interest),
                            "iv": round(iv * 100, 1),
                            "premium": premium,
                            "total_value": round(total_value, 0),
                            "pct_otm": round(pct_otm, 1)
                        })
                    except Exception:
                        continue

                for _, row in puts.iterrows():
                    try:
                        strike = row["strike"]
                        volume = row["volume"]
                        open_interest = row["openInterest"]
                        iv = row["impliedVolatility"]
                        premium = row["lastPrice"]
                        total_value = volume * premium * 100

                        if total_value < MIN_OPTIONS_VALUE:
                            continue

                        pct_otm = ((current_price - strike) / current_price) * 100
                        signal = "🔴 BEARISH" if volume > 500 or total_value > 1000000 else "⚪ MODERATE BEARISH"

                        unusual_activity.append({
                            "type": "PUT",
                            "signal": signal,
                            "expiry": expiry,
                            "strike": strike,
                            "volume": int(volume),
                            "open_interest": int(open_interest),
                            "iv": round(iv * 100, 1),
                            "premium": premium,
                            "total_value": round(total_value, 0),
                            "pct_otm": round(pct_otm, 1)
                        })
                    except Exception:
                        continue

            except Exception:
                continue

        if not unusual_activity:
            return None

        unusual_activity.sort(key=lambda x: x["total_value"], reverse=True)
        return unusual_activity[:3]

    except Exception:
        return None

def get_options_summary(tickers):
    summary = {}

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options

            if not expirations:
                continue

            near_expiry = expirations[:3]
            calls_all = pd.DataFrame()
            puts_all = pd.DataFrame()

            # Aggregate options data across expirations
            for expiry in near_expiry:
                try:
                    chain = stock.option_chain(expiry)
                    calls_all = pd.concat([calls_all, chain.calls])
                    puts_all = pd.concat([puts_all, chain.puts])
                except Exception:
                    continue

            # Calculate put/call ratio
            pc_analysis = get_put_call_ratio(calls_all, puts_all)

            # Get IV percentile from first expiration
            if expirations:
                try:
                    chain = stock.option_chain(expirations[0])
                    avg_iv = chain.calls["impliedVolatility"].mean()
                    iv_pct = get_iv_percentile(ticker, avg_iv * 100)
                except Exception:
                    iv_pct = 50.0
            else:
                iv_pct = 50.0

            # Get options flow
            flow = get_options_flow(ticker)

            if flow:
                calls = [f for f in flow if f["type"] == "CALL"]
                puts = [f for f in flow if f["type"] == "PUT"]
                call_value = sum(f["total_value"] for f in calls)
                put_value = sum(f["total_value"] for f in puts)

                # Enhanced signal incorporating IV and put/call ratio
                pc_signal = pc_analysis.get("signal", "⚪")

                # Combine signals
                if call_value > put_value * 2 and pc_signal == "🟢 BULLISH":
                    overall = "🟢🟢 STRONG BULLISH (high call flow + calls > puts)"
                elif put_value > call_value * 2 and pc_signal == "🔴 BEARISH":
                    overall = "🔴🔴 STRONG BEARISH (high put flow + puts > calls)"
                elif call_value > put_value * 1.5:
                    overall = "🟢 BULLISH OPTIONS FLOW"
                elif put_value > call_value * 1.5:
                    overall = "🔴 BEARISH OPTIONS FLOW"
                else:
                    overall = "⚪ MIXED OPTIONS FLOW"

                summary[ticker] = {
                    "flow": flow,
                    "call_value": call_value,
                    "put_value": put_value,
                    "overall": overall,
                    "iv_percentile": iv_pct,
                    "iv_interpretation": "Expensive" if iv_pct > 75 else "Cheap" if iv_pct < 25 else "Normal",
                    "put_call_ratio": pc_analysis.get("ratio", 1.0),
                    "put_call_signal": pc_signal,
                    "put_call_interpretation": pc_analysis.get("interpretation", ""),
                    "call_volume": pc_analysis.get("call_volume", 0),
                    "put_volume": pc_analysis.get("put_volume", 0)
                }
        except Exception:
            continue

    return summary

def format_options_string(options_summary):
    if not options_summary:
        return "No significant options activity detected (min $500k threshold)."

    result = "ENHANCED OPTIONS ANALYSIS (>$500k only):\n"

    for ticker, data in options_summary.items():
        result += f"\n{ticker} — {data['overall']}\n"
        result += f"  Call value: ${data['call_value']:,.0f}  Put value: ${data['put_value']:,.0f}\n"

        # Add IV percentile
        iv_pct = data.get("iv_percentile", 50)
        iv_interp = data.get("iv_interpretation", "Normal")
        result += f"  IV Percentile: {iv_pct:.0f}/100 ({iv_interp})\n"

        # Add put/call ratio
        pc_ratio = data.get("put_call_ratio", 1.0)
        pc_signal = data.get("put_call_signal", "")
        pc_interp = data.get("put_call_interpretation", "")
        result += f"  Put/Call Ratio: {pc_ratio:.2f} {pc_signal} — {pc_interp}\n"
        result += f"  (Calls: {data.get('call_volume', 0):,} | Puts: {data.get('put_volume', 0):,})\n"

        # Add flow details
        result += f"  Top unusual flows:\n"
        for flow in data.get("flow", [])[:2]:
            result += f"    {flow['signal']} {flow['type']} — Strike ${flow['strike']} exp {flow['expiry']} — Vol {flow['volume']:,} — ${flow['total_value']:,.0f}\n"

    return result

if __name__ == "__main__":
    test_tickers = ["AAPL", "NVDA", "TSLA", "SPY", "GE", "PLTR"]
    print("Fetching significant options flow...")
    summary = get_options_summary(test_tickers)
    print(format_options_string(summary))