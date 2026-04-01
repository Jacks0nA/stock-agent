"""
Phase 1: Signal Effectiveness Scoring
Analyzes which technical signals are actually predictive of wins
"""

from collections import defaultdict
import statistics


def score_signal_effectiveness(closed_positions):
    """
    For each technical signal/condition, calculate:
    - Appearance rate in winners vs losers
    - Win rate when signal is present
    - Predictive power (how much better than baseline)
    """

    if not closed_positions or len(closed_positions) < 5:
        return None

    winners = [p for p in closed_positions if p.get("pnl") and float(p.get("pnl", 0)) > 0]
    losers = [p for p in closed_positions if p.get("pnl") and float(p.get("pnl", 0)) < 0]

    baseline_win_rate = len(winners) / len(closed_positions) if closed_positions else 0

    # Analyze different signal categories
    signals = {
        "confidence_tier": analyze_confidence_signal(winners, losers, baseline_win_rate),
        "hold_time": analyze_hold_time_signal(winners, losers),
        "sector_performance": analyze_sector_signal(winners, losers),
        "entry_timing": analyze_entry_timing_signal(winners, losers),
        "position_size": analyze_position_size_signal(winners, losers),
    }

    # Calculate overall signal effectiveness
    effectiveness = {
        "baseline_win_rate": round(baseline_win_rate * 100, 1),
        "total_trades": len(closed_positions),
        "winners": len(winners),
        "losers": len(losers),
        "signals": signals,
        "top_predictors": get_top_predictors(signals),
        "recommendations": generate_signal_recommendations(signals)
    }

    return effectiveness


def analyze_confidence_signal(winners, losers, baseline):
    """
    Which confidence tiers have best win rates?
    """
    tier_stats = defaultdict(lambda: {"wins": 0, "losses": 0})

    for winner in winners:
        tier = winner.get("confidence", "UNKNOWN")
        tier_stats[tier]["wins"] += 1

    for loser in losers:
        tier = loser.get("confidence", "UNKNOWN")
        tier_stats[tier]["losses"] += 1

    results = {}
    for tier, stats in tier_stats.items():
        total = stats["wins"] + stats["losses"]
        win_rate = stats["wins"] / total * 100 if total > 0 else 0
        edge = win_rate - (baseline * 100)  # Edge vs baseline

        results[tier] = {
            "win_rate": round(win_rate, 1),
            "total_trades": total,
            "wins": stats["wins"],
            "edge_vs_baseline": round(edge, 1),
            "predictive_power": "HIGH" if edge > 15 else "MEDIUM" if edge > 5 else "LOW"
        }

    return results


def analyze_hold_time_signal(winners, losers):
    """
    What hold times are associated with wins?
    """
    from datetime import datetime

    winner_holds = []
    loser_holds = []

    for p in winners:
        try:
            opened = datetime.strptime(p["opened_at"], "%Y-%m-%d %H:%M")
            closed = datetime.strptime(p["closed_at"], "%Y-%m-%d %H:%M")
            days = (closed - opened).days
            winner_holds.append(days)
        except:
            pass

    for p in losers:
        try:
            opened = datetime.strptime(p["opened_at"], "%Y-%m-%d %H:%M")
            closed = datetime.strptime(p["closed_at"], "%Y-%m-%d %H:%M")
            days = (closed - opened).days
            loser_holds.append(days)
        except:
            pass

    results = {
        "winner_avg_hold": round(statistics.mean(winner_holds), 1) if winner_holds else 0,
        "winner_median_hold": statistics.median(winner_holds) if winner_holds else 0,
        "loser_avg_hold": round(statistics.mean(loser_holds), 1) if loser_holds else 0,
        "loser_median_hold": statistics.median(loser_holds) if loser_holds else 0,
        "insight": "Winners exit faster than losers means mean reversion dominates your trades"
        if winner_holds and loser_holds and statistics.median(winner_holds) < statistics.median(loser_holds)
        else "Winners hold longer means momentum/trend following works for you"
    }

    return results


def analyze_sector_signal(winners, losers):
    """
    Which sectors generate winners vs losers?
    """
    sector_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0})

    for winner in winners:
        pnl = float(winner.get("pnl", 0))
        # Try to infer sector from ticker (simplified)
        ticker = winner.get("ticker", "UNKNOWN")
        sector_stats[ticker]["wins"] += 1
        sector_stats[ticker]["total_pnl"] += pnl

    for loser in losers:
        pnl = float(loser.get("pnl", 0))
        ticker = loser.get("ticker", "UNKNOWN")
        sector_stats[ticker]["losses"] += 1
        sector_stats[ticker]["total_pnl"] += pnl

    # Sort by win rate
    results = {}
    for ticker, stats in sorted(sector_stats.items(), key=lambda x: x[1]["wins"] / max(1, x[1]["wins"] + x[1]["losses"]), reverse=True):
        total = stats["wins"] + stats["losses"]
        if total >= 2:  # Only show tickers with 2+ trades
            win_rate = stats["wins"] / total * 100
            avg_pnl = stats["total_pnl"] / total
            results[ticker] = {
                "win_rate": round(win_rate, 1),
                "trades": total,
                "avg_pnl": round(avg_pnl, 2),
                "predictive_power": "STRONG EDGE" if win_rate > 70 else "GOOD EDGE" if win_rate > 60 else "WEAK"
            }

    return results


def analyze_entry_timing_signal(winners, losers):
    """
    What entry timing patterns characterize winners?
    """
    from datetime import datetime
    import pytz

    winner_entry_hours = []
    loser_entry_hours = []

    for p in winners:
        try:
            time_str = p.get("opened_at", "")
            if time_str:
                hour = int(time_str.split()[1].split(":")[0])
                winner_entry_hours.append(hour)
        except:
            pass

    for p in losers:
        try:
            time_str = p.get("opened_at", "")
            if time_str:
                hour = int(time_str.split()[1].split(":")[0])
                loser_entry_hours.append(hour)
        except:
            pass

    results = {
        "winner_avg_entry_hour": round(statistics.mean(winner_entry_hours), 1) if winner_entry_hours else "N/A",
        "loser_avg_entry_hour": round(statistics.mean(loser_entry_hours), 1) if loser_entry_hours else "N/A",
        "best_entry_hours": get_best_entry_hours(winner_entry_hours) if winner_entry_hours else [],
        "insight": "Entry timing varies - analyze when winners typically entered"
    }

    return results


def get_best_entry_hours(hours):
    """
    Find most common winning entry hours
    """
    if not hours:
        return []

    from collections import Counter
    counter = Counter(hours)
    top_3 = counter.most_common(3)
    return [f"{h}:00 GMT ({count} wins)" for h, count in top_3]


def analyze_position_size_signal(winners, losers):
    """
    Does position size correlate with wins?
    """
    winner_sizes = [float(p.get("position_size", 0)) for p in winners]
    loser_sizes = [float(p.get("position_size", 0)) for p in losers]

    results = {
        "winner_avg_size": round(statistics.mean(winner_sizes), 2) if winner_sizes else 0,
        "loser_avg_size": round(statistics.mean(loser_sizes), 2) if loser_sizes else 0,
        "insight": "Larger positions win more" if winner_sizes and loser_sizes and statistics.mean(winner_sizes) > statistics.mean(loser_sizes) else "Position size doesn't strongly predict wins"
    }

    return results


def get_top_predictors(signals):
    """
    Rank signals by their predictive power
    """
    predictors = []

    # Confidence tier analysis
    confidence = signals.get("confidence_tier", {})
    for tier, stats in confidence.items():
        if stats.get("edge_vs_baseline", 0) > 0:
            predictors.append({
                "signal": f"Confidence: {tier}",
                "edge": stats["edge_vs_baseline"],
                "strength": stats["predictive_power"],
                "data": f"{stats['wins']}/{stats['total_trades']} wins"
            })

    # Hold time analysis
    hold = signals.get("hold_time", {})
    if hold.get("insight"):
        predictors.append({
            "signal": "Hold Time Pattern",
            "insight": hold["insight"],
            "winner_days": hold.get("winner_avg_hold"),
            "loser_days": hold.get("loser_avg_hold")
        })

    # Sector analysis
    sector = signals.get("sector_performance", {})
    top_sector = next(iter(sector.items())) if sector else None
    if top_sector:
        ticker, stats = top_sector
        predictors.append({
            "signal": f"Top Performer: {ticker}",
            "win_rate": stats["win_rate"],
            "strength": stats["predictive_power"],
            "data": f"{stats['trades']} trades"
        })

    return sorted(predictors, key=lambda x: x.get("edge", x.get("win_rate", 0)), reverse=True)[:5]


def generate_signal_recommendations(signals):
    """
    Generate actionable recommendations based on signal analysis
    """
    recommendations = []

    # Confidence tier recommendations
    confidence = signals.get("confidence_tier", {})
    for tier, stats in sorted(confidence.items(), key=lambda x: x[1].get("edge_vs_baseline", 0), reverse=True):
        if stats["edge_vs_baseline"] > 20:
            recommendations.append(
                f"🎯 PRIORITIZE {tier} confidence trades — {stats['win_rate']}% win rate "
                f"(+{stats['edge_vs_baseline']:.1f}% edge vs baseline)"
            )
        elif stats["edge_vs_baseline"] < -10:
            recommendations.append(
                f"⚠️ REDUCE {tier} confidence trades — only {stats['win_rate']}% win rate "
                f"({stats['edge_vs_baseline']:.1f}% below baseline)"
            )

    # Hold time recommendations
    hold = signals.get("hold_time", {})
    if hold.get("winner_avg_hold") and hold.get("loser_avg_hold"):
        if hold["winner_avg_hold"] < hold["loser_avg_hold"]:
            recommendations.append(
                f"⏱️ MEAN REVERSION EDGE — Winners exit in {hold['winner_avg_hold']} days, "
                f"losers in {hold['loser_avg_hold']} days. Exit winners faster."
            )
        else:
            recommendations.append(
                f"📈 TREND EDGE — Winners hold {hold['winner_avg_hold']} days, "
                f"losers {hold['loser_avg_hold']} days. Let winners run."
            )

    # Sector recommendations
    sector = signals.get("sector_performance", {})
    strong_tickers = [t for t, s in sector.items() if s.get("win_rate", 0) > 70]
    weak_tickers = [t for t, s in sector.items() if s.get("win_rate", 0) < 40]

    if strong_tickers:
        recommendations.append(
            f"✅ FOCUS ON: {', '.join(strong_tickers[:3])} — These have 70%+ win rates"
        )

    if weak_tickers:
        recommendations.append(
            f"❌ AVOID: {', '.join(weak_tickers[:3])} — These have <40% win rates"
        )

    return recommendations


def format_signal_effectiveness_report(effectiveness):
    """
    Format for display in dashboard
    """
    if not effectiveness:
        return "Not enough trade data yet to analyze signal effectiveness"

    report = f"""
### Signal Effectiveness Analysis

**Baseline Win Rate:** {effectiveness['baseline_win_rate']}% ({effectiveness['winners']} wins, {effectiveness['losers']} losses)

#### Top Predictors (Most Powerful Signals):
"""

    for i, predictor in enumerate(effectiveness.get("top_predictors", []), 1):
        if "edge" in predictor:
            report += f"{i}. **{predictor['signal']}** - +{predictor['edge']:.1f}% edge ({predictor['data']})\n"
        else:
            report += f"{i}. **{predictor['signal']}** - {predictor.get('insight', '')}\n"

    report += "\n#### Recommendations:\n"
    for rec in effectiveness.get("recommendations", []):
        report += f"- {rec}\n"

    return report


if __name__ == "__main__":
    # Test with sample data
    sample_trades = [
        {"ticker": "AAPL", "pnl": 150, "pnl_pct": 15, "confidence": "CONFIDENT", "position_size": 1000, "opened_at": "2026-03-25 10:30", "closed_at": "2026-03-29 14:00"},
        {"ticker": "NVDA", "pnl": -75, "pnl_pct": -7.5, "confidence": "MEDIUM", "position_size": 250, "opened_at": "2026-03-20 09:45", "closed_at": "2026-03-27 15:30"},
    ]

    result = score_signal_effectiveness(sample_trades)
    print(format_signal_effectiveness_report(result))
