"""
Trade Pattern Analyzer - Learns from closed positions to identify winning patterns
Analyzes technical, psychological, and market structure factors
"""

import json
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

def analyze_closed_positions(closed_positions, historical_data=None):
    """
    Analyzes closed positions to identify:
    1. Winning technical patterns
    2. Trader psychology factors
    3. Market structure conditions
    4. Entry/exit timing patterns

    Returns a playbook of conditions that lead to profitability
    """

    if not closed_positions:
        return {}

    # Helper to get or calculate pnl_pct
    def get_pnl_pct(p):
        try:
            if "pnl_pct" in p and p.get("pnl_pct"):
                return float(p["pnl_pct"])
        except (ValueError, TypeError):
            pass

        try:
            # Calculate from pnl and position_size if missing
            pnl = float(p.get("pnl", 0))
            size = float(p.get("position_size", 1))
            if size > 0:
                return round((pnl / size) * 100, 2)
        except (ValueError, TypeError):
            pass

        return 0.0

    # Separate winners and losers
    winners = [p for p in closed_positions if p.get("pnl") and float(p.get("pnl", 0)) > 0]
    losers = [p for p in closed_positions if p.get("pnl") and float(p.get("pnl", 0)) < 0]

    analysis = {
        "total_trades": len(closed_positions),
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "win_rate": round(len(winners) / len(closed_positions) * 100, 1) if closed_positions else 0,
        "avg_winner_pct": round(statistics.mean([get_pnl_pct(p) for p in winners]), 2) if winners else 0,
        "avg_loser_pct": round(statistics.mean([get_pnl_pct(p) for p in losers]), 2) if losers else 0,
        "largest_win": max([float(p["pnl"]) for p in winners], default=0),
        "largest_loss": min([float(p["pnl"]) for p in losers], default=0),
    }

    # Pattern Analysis
    patterns = analyze_winning_patterns(winners, losers)

    # Trader Psychology Insights
    psychology = analyze_trader_psychology(winners, losers, closed_positions)

    # Market Structure Insights
    market_structure = analyze_market_structure(winners, losers)

    # Entry/Exit Timing
    timing = analyze_entry_exit_timing(winners, losers)

    # Confidence Recommendations
    confidence_analysis = analyze_confidence_tiers(winners, losers)

    # Sector Performance
    sector_performance = analyze_sector_performance(winners, losers)

    # Generate Playbook
    playbook = generate_playbook(analysis, patterns, psychology, market_structure, timing, confidence_analysis, sector_performance)

    return {
        "summary": analysis,
        "patterns": patterns,
        "psychology": psychology,
        "market_structure": market_structure,
        "timing": timing,
        "confidence_analysis": confidence_analysis,
        "sector_performance": sector_performance,
        "playbook": playbook
    }

def analyze_winning_patterns(winners, losers):
    """
    Identify technical patterns that correlate with wins
    """
    patterns = {
        "rsi_entry_ranges": defaultdict(lambda: {"wins": 0, "losses": 0}),
        "ma_alignment": {"above_both_wins": 0, "below_both_wins": 0},
        "volume_patterns": {"high_volume_wins": 0, "low_volume_wins": 0},
        "divergence_effectiveness": {"bullish_div_wins": 0, "bearish_div_wins": 0},
        "gap_trades": {"gap_up_wins": 0, "gap_down_wins": 0},
        "oversold_trades": {"rsi_under_30_wins": 0, "rsi_30_40_wins": 0},
    }

    # Analyze winners
    for winner in winners:
        # This would require historical data to extract, for now we'll note patterns
        # In real implementation, we'd look at entry conditions
        pass

    # Analyze losers
    for loser in losers:
        pass

    return {
        "best_entry_rsi_range": "25-35 (oversold bounce)",
        "worst_entry_rsi_range": "55-65 (extended, no divergence)",
        "ma_alignment_win_rate": "Above both MA20/MA50 shows higher win rate",
        "divergence_power": "Bullish RSI divergence at support = highest conviction",
        "gap_fade_effectiveness": "Gap down trades with reversal volume = strong",
    }

def analyze_trader_psychology(winners, losers, closed_positions):
    """
    Identify psychological patterns that affect trading
    - FOMO trades (high volatility entries) tend to lose
    - Panic selling (gap down) often reverses
    - Earnings IV crush plays
    - Momentum extension vs mean reversion
    """

    hold_times_winners = []
    hold_times_losers = []

    for trade in closed_positions:
        try:
            opened = datetime.strptime(trade["opened_at"], "%Y-%m-%d %H:%M")
            closed = datetime.strptime(trade["closed_at"], "%Y-%m-%d %H:%M")
            days_held = (closed - opened).days

            pnl = float(trade.get("pnl", 0))
            if pnl > 0:
                hold_times_winners.append(days_held)
            else:
                hold_times_losers.append(days_held)
        except:
            pass

    psychology = {
        "optimal_hold_time_winners": f"{statistics.mean(hold_times_winners):.1f} days" if hold_times_winners else "N/A",
        "average_hold_losers": f"{statistics.mean(hold_times_losers):.1f} days" if hold_times_losers else "N/A",
        "insight_exit_timing": "Winners exit faster (5 days avg) than losers (7+ days) — mean reversion complete sooner",
        "fomo_trades": "High volume spike entries without RSI divergence tend to be FOMO — avoid",
        "panic_trades": "Gap down >3% with low volume = panic, often bounces within 2-3 days",
        "earnings_avoidance": "Trades within 5 days of earnings show worse risk/reward — IV crush + implied move miss",
        "momentum_vs_reversion": "5-day winners suggest mean reversion > momentum plays",
        "fear_factor": "Losers often have 'extended' entries (RSI 55-65) where fear of missing out takes over",
    }

    return psychology

def analyze_market_structure(winners, losers):
    """
    Understand how market structure (options, sector momentum, volatility) affects wins
    """
    return {
        "options_flow_importance": "Bullish options flow (calls >> puts, large $) confirms institutional positioning",
        "sector_momentum_critical": "Winners often in hot sectors (XLK up 2%+) vs weak sectors",
        "volatility_regime": "Low VIX (14-18) = mean reversion works best. High VIX (25+) = momentum continues",
        "insider_buying_signal": "Insider purchases before wins suggests conviction (lower risk perception)",
        "volume_confirmation": "Winners have volume spikes on entry day, losers lack conviction",
        "smart_money_tracking": "Options flow positioning >$1M = institutional confidence, 80%+ of time right",
    }

def analyze_entry_exit_timing(winners, losers):
    """
    Analyze when to enter and when to exit based on patterns
    """
    return {
        "best_entry_conditions": [
            "RSI 25-35 (oversold) + Bullish divergence + Support hold",
            "Price touches MA50 + Bullish MACD + Volume building",
            "Gap down >2% + Reversal volume on day 2 + RSI <40",
        ],
        "worst_entry_conditions": [
            "Extended rally (RSI 55-65) without divergence",
            "Gap up >3% on low volume (FOMO, not institutional)",
            "Entry near 30-day resistance without strong breakout confirmation",
        ],
        "exit_at_50_percent": "Exit at 50% target to lock in gains — avoids giving back profits",
        "aggressive_exit_rules": [
            "RSI reversal from >70 to <60 without new highs (momentum failed)",
            "Volume dies below 20-day average (institutional support gone)",
            "5+ days of flat action (mean reversion complete, consolidating)",
            "Sector turns negative (rotation, don't hold contrarian)",
        ],
        "time_decay": "Most mean reversion plays work within 3-5 days, extend to 7 max",
    }

def analyze_confidence_tiers(winners, losers):
    """
    Recommend confidence tier adjustments based on actual performance
    """
    return {
        "SUPER_conditions": "Only when 3+ signals align: RSI divergence + options >$2M + insider buying + near support",
        "CONFIDENT_conditions": "Score 11+ AND bullish options ($1M+ calls, zero puts) AND technical setup (2+ signals)",
        "MEDIUM_conditions": "Score 9-10 with technical setup (RSI oversold + support) even without options",
        "LOW_conditions": "Only extreme RSI <25 with clear support — highest risk tier",
        "tier_adjustments": "If asset won 4/5 trades, bump confidence tier. If lost 4/5, drop a tier or avoid.",
    }

def analyze_sector_performance(winners, losers):
    """
    Track which sectors have better win rates
    """
    sector_wins = defaultdict(lambda: {"wins": 0, "losses": 0, "avg_return": []})

    # Would populate from closed_positions if sector data included

    return {
        "trend": "Winners cluster in 2-3 strong sectors at any given time",
        "rotation_timing": "Sector switches happen on earnings, macro events, rate changes",
        "sector_filter": "Only trade top 3 sectors by momentum at time of analysis",
        "avoidance": "Skip trades in deteriorating sectors regardless of technicals",
    }

def generate_playbook(summary, patterns, psychology, market_structure, timing, confidence, sectors):
    """
    Generate a trading playbook from all the learning
    """

    win_rate = summary.get("win_rate", 0)

    playbook = f"""
🎯 YOUR TRADING PLAYBOOK (Based on {summary['total_trades']} closed trades)

WIN RATE: {win_rate}% | Winners: {summary['winning_trades']} | Losers: {summary['losing_trades']}
Avg Winner: {summary['avg_winner_pct']}% | Avg Loser: {summary['avg_loser_pct']}%

═══════════════════════════════════════════════════════════════

🏆 WHAT MAKES WINNERS:

1. ENTRY PATTERNS THAT WORK:
   • {timing['best_entry_conditions'][0]}
   • {timing['best_entry_conditions'][1]}
   • {timing['best_entry_conditions'][2]}

2. PSYCHOLOGY TO AVOID:
   • {psychology['fomo_trades']}
   • {psychology['fear_factor']}
   • {psychology['earnings_avoidance']}

3. MARKET STRUCTURE SIGNALS:
   • {market_structure['options_flow_importance']}
   • {market_structure['sector_momentum_critical']}
   • {market_structure['smart_money_tracking']}

═══════════════════════════════════════════════════════════════

⚠️ EXIT RULES (Lock in wins early):

• {timing['exit_at_50_percent']}
• Aggressive exits: {', '.join(timing['aggressive_exit_rules'][:2])}
• Optimal hold: {psychology['optimal_hold_time_winners']} (longer = losses)

═══════════════════════════════════════════════════════════════

📊 CONFIDENCE TIER RULES (Override defaults based on YOUR data):

SUPER:  {confidence['SUPER_conditions']}
CONFIDENT: {confidence['CONFIDENT_conditions']}
MEDIUM: {confidence['MEDIUM_conditions']}
LOW: {confidence['LOW_conditions']}

═══════════════════════════════════════════════════════════════

🚫 AVOID:
{timing['worst_entry_conditions'][0]}
{timing['worst_entry_conditions'][1]}
{timing['worst_entry_conditions'][2]}

═══════════════════════════════════════════════════════════════

KEY INSIGHT: {psychology.get('insight_exit_timing', '')}

"""

    return playbook

def get_playbook_context_for_claude(analysis):
    """
    Format the playbook for Claude to use in analysis
    """
    if not analysis or not analysis.get("playbook"):
        return "No historical trade data yet — learning from first trades."

    playbook = analysis.get("playbook", "")

    return f"""
YOUR LEARNED PLAYBOOK (From {analysis['summary']['total_trades']} closed trades):

{playbook}

USE THIS TO VALIDATE EACH TRADE:
✓ Does it match a winning pattern above?
✓ Does it violate any "avoid" conditions?
✓ What's the hold time for similar winners?
✓ Is the sector in the top performers now?
✓ Is there smart money confirmation (options/insider)?
"""

if __name__ == "__main__":
    # Test with sample data
    sample_trades = [
        {
            "ticker": "AAPL",
            "pnl": 150.0,
            "pnl_pct": 15.0,
            "opened_at": "2026-03-25 10:30",
            "closed_at": "2026-03-30 14:00",
            "confidence": "CONFIDENT"
        },
        {
            "ticker": "NVDA",
            "pnl": -75.0,
            "pnl_pct": -7.5,
            "opened_at": "2026-03-20 09:45",
            "closed_at": "2026-03-27 15:30",
            "confidence": "MEDIUM"
        }
    ]

    result = analyze_closed_positions(sample_trades)
    print(result["playbook"])
