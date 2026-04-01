import os
import json
import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv
import yfinance as yf

load_dotenv()

GMT = timezone.utc
MAX_POSITIONS = 10
MAX_HOLD_DAYS = 10
STARTING_BALANCE = 30000.0

CONFIDENCE_SIZES = {
    "LOW": 100.0,
    "MEDIUM": 250.0,
    "CONFIDENT": 1000.0,
    "SUPER": 2000.0
}

def get_headers():
    return {
        "apikey": os.getenv("SUPABASE_KEY"),
        "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def get_base_url():
    return os.getenv("SUPABASE_URL")

def get_portfolio_balance():
    try:
        url = f"{get_base_url()}/rest/v1/portfolio_state?key=eq.balance"
        response = httpx.get(url, headers=get_headers())
        data = response.json()
        if data:
            return float(data[0]["value"])
        # Initialise balance if not set
        set_portfolio_balance(STARTING_BALANCE)
        return STARTING_BALANCE
    except Exception as e:
        print(f"Balance fetch error: {e}")
        return STARTING_BALANCE

def set_portfolio_balance(balance):
    try:
        url = f"{get_base_url()}/rest/v1/portfolio_state"
        httpx.post(url, headers=get_headers(), json={
            "key": "balance",
            "value": str(balance)
        })
    except Exception as e:
        print(f"Balance set error: {e}")

def get_open_positions():
    try:
        url = f"{get_base_url()}/rest/v1/positions?status=eq.OPEN&order=opened_at.asc"
        response = httpx.get(url, headers=get_headers())
        return response.json() or []
    except Exception as e:
        print(f"Position fetch error: {e}")
        return []

def get_closed_positions():
    try:
        url = f"{get_base_url()}/rest/v1/positions?status=eq.CLOSED&order=closed_at.desc"
        response = httpx.get(url, headers=get_headers())
        return response.json() or []
    except Exception as e:
        print(f"Closed position fetch error: {e}")
        return []

def open_position(ticker, direction, entry_price, target_price, stop_loss,
                  confidence, score, claude_reasoning, position_size=None):
    try:
        if position_size is None:
            position_size = CONFIDENCE_SIZES.get(confidence, 100.0)

        balance = get_portfolio_balance()
        if position_size > balance:
            print(f"Insufficient balance to open position in {ticker}")
            return None

        url = f"{get_base_url()}/rest/v1/positions"
        data = {
            "ticker": ticker,
            "direction": direction,
            "entry_price": entry_price,
            "current_price": entry_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "position_size": position_size,
            "confidence": confidence,
            "score": score,
            "opened_at": datetime.now(GMT).strftime("%Y-%m-%d %H:%M"),
            "status": "OPEN",
            "claude_reasoning": claude_reasoning,
            "pnl": 0.0,
            "pnl_pct": 0.0
        }
        response = httpx.post(url, headers=get_headers(), json=data)

        if response.status_code not in (200, 201):
            print(f"Supabase rejected position insert for {ticker}: {response.status_code} {response.text}")
            return None

        # Deduct from balance only after confirmed insert
        new_balance = balance - position_size
        url2 = f"{get_base_url()}/rest/v1/portfolio_state"
        httpx.post(url2, headers=get_headers(), json={
            "key": "balance",
            "value": str(new_balance)
        })

        print(f"✅ Opened {direction} position in {ticker} — size £{position_size} — confidence {confidence}")
        print(f"   Balance: £{balance:.2f} → £{new_balance:.2f}")
        return True

    except Exception as e:
        print(f"Open position error: {e}")
        return None

def close_position(position_id, exit_price, reason):
    try:
        # Get position details
        url = f"{get_base_url()}/rest/v1/positions?id=eq.{position_id}"
        response = httpx.get(url, headers=get_headers())
        positions = response.json()
        if not positions:
            return None

        position = positions[0]
        entry_price = float(position["entry_price"])
        position_size = float(position["position_size"])

        # Calculate P&L
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        pnl = position_size * (pnl_pct / 100)
        return_amount = position_size + pnl

        # Update position
        update_url = f"{get_base_url()}/rest/v1/positions?id=eq.{position_id}"
        httpx.patch(update_url, headers=get_headers(), json={
            "status": "CLOSED",
            "exit_price": exit_price,
            "closed_at": datetime.now(GMT).strftime("%Y-%m-%d %H:%M"),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "claude_reasoning": reason
        })

        # Return capital + P&L to balance
        balance = get_portfolio_balance()
        new_balance = balance + return_amount
        url2 = f"{get_base_url()}/rest/v1/portfolio_state"
        httpx.post(url2, headers=get_headers(), json={
            "key": "balance",
            "value": str(new_balance)
        })

        print(f"✅ Closed {position['ticker']} at £{exit_price} — P&L: £{round(pnl, 2)} ({round(pnl_pct, 2)}%)")
        print(f"   Balance: £{balance:.2f} → £{new_balance:.2f} (returned £{round(return_amount, 2)})")
        return pnl

    except Exception as e:
        print(f"Close position error: {e}")
        return None

def update_position(position_id, updates):
    """
    Update position fields — used for stop loss and target reassessment.
    Enforces stop loss can only move up.
    """
    try:
        # Enforce stop loss never moves down
        if "stop_loss" in updates:
            url = f"{get_base_url()}/rest/v1/positions?id=eq.{position_id}"
            current = httpx.get(url, headers=get_headers()).json()
            if current:
                current_sl = float(current[0]["stop_loss"])
                if updates["stop_loss"] < current_sl:
                    print(f"Stop loss move rejected — cannot move down (current: {current_sl}, attempted: {updates['stop_loss']})")
                    del updates["stop_loss"]

        if not updates:
            return

        update_url = f"{get_base_url()}/rest/v1/positions?id=eq.{position_id}"
        httpx.patch(update_url, headers=get_headers(), json=updates)

    except Exception as e:
        print(f"Update position error: {e}")

def get_position(position_id):
    """Fetch a single position by ID"""
    try:
        url = f"{get_base_url()}/rest/v1/positions?id=eq.{position_id}"
        response = httpx.get(url, headers=get_headers())
        positions = response.json()
        return positions[0] if positions else None
    except Exception as e:
        print(f"Get position error: {e}")
        return None

def log_pyramid_action(position_id, old_confidence, new_confidence, size_diff, entry_price):
    """Log pyramid scaling actions for learning analytics"""
    try:
        import json
        from pathlib import Path

        log_file = Path("/Users/jacksonamies/stock-agent/pyramid_trades.json")

        action = {
            "timestamp": datetime.now(GMT).strftime("%Y-%m-%d %H:%M:%S"),
            "position_id": position_id,
            "action": "upgrade" if size_diff > 0 else "downgrade",
            "old_confidence": old_confidence,
            "new_confidence": new_confidence,
            "size_change": size_diff,
            "entry_price": entry_price
        }

        # Append to log file
        if log_file.exists():
            with open(log_file, 'a') as f:
                f.write(json.dumps(action) + "\n")
        else:
            with open(log_file, 'w') as f:
                f.write(json.dumps(action) + "\n")
    except Exception as e:
        print(f"Pyramid logging error: {e}")

def update_position_confidence_with_pyramid(position_id, new_confidence, current_price):
    """
    Scale position up/down when confidence tier changes.
    Upgrade: Add new layer at current price
    Downgrade: Remove top layer (sell at current price)
    """
    try:
        position = get_position(position_id)
        if not position:
            print(f"Position {position_id} not found")
            return False

        old_confidence = position.get("confidence")
        if old_confidence == new_confidence:
            return True  # No change needed

        old_size = CONFIDENCE_SIZES.get(old_confidence, 0)
        new_size = CONFIDENCE_SIZES.get(new_confidence, 0)
        size_diff = new_size - old_size

        # Initialize pyramid_layers if doesn't exist
        pyramid_layers = position.get("pyramid_layers", [])
        if not pyramid_layers:
            pyramid_layers = [
                {
                    "tier": old_confidence,
                    "size": old_size,
                    "entry_price": float(position["entry_price"]),
                    "opened_at": position.get("opened_at", datetime.now(GMT).strftime("%Y-%m-%d %H:%M"))
                }
            ]

        if size_diff > 0:
            # UPGRADE: Add new layer
            pyramid_layers.append({
                "tier": new_confidence,
                "size": abs(size_diff),
                "entry_price": current_price,
                "opened_at": datetime.now(GMT).strftime("%Y-%m-%d %H:%M")
            })
        elif size_diff < 0:
            # DOWNGRADE: Remove top layer(s)
            amount_to_remove = abs(size_diff)
            removed_layers = 0
            while amount_to_remove > 0 and len(pyramid_layers) > 1:
                removed_layer = pyramid_layers.pop()
                amount_to_remove -= removed_layer["size"]
                removed_layers += 1

        # Recalculate totals
        total_size = sum(layer["size"] for layer in pyramid_layers)
        if total_size > 0:
            weighted_entry = sum(
                layer["size"] * layer["entry_price"]
                for layer in pyramid_layers
            ) / total_size
        else:
            weighted_entry = current_price

        # Update position in database
        updates = {
            "confidence": new_confidence,
            "position_size": total_size,
            "entry_price": weighted_entry,
            "pyramid_layers": pyramid_layers,
            "current_price": current_price
        }

        update_position(position_id, updates)

        # Log the pyramid action
        log_pyramid_action(position_id, old_confidence, new_confidence, size_diff, current_price)

        print(f"Pyramid scaling: {position['ticker']} {old_confidence}→{new_confidence}, size: £{old_size}→£{new_size}")
        return True

    except Exception as e:
        print(f"Pyramid update error: {e}")
        return False

def get_current_prices(tickers):
    prices = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if len(hist) > 0:
                prices[ticker] = round(float(hist["Close"].iloc[-1]), 2)
        except Exception:
            prices[ticker] = None
    return prices

def check_stop_losses(open_positions, current_prices):
    """
    Automatically closes any position that has breached its stop loss.
    Returns list of positions that were stopped out.
    """
    stopped_out = []
    for position in open_positions:
        ticker = position["ticker"]
        current_price = current_prices.get(ticker)
        if current_price is None:
            continue
        stop_loss = float(position["stop_loss"])
        if current_price <= stop_loss:
            print(f"STOP LOSS TRIGGERED: {ticker} at {current_price} (stop: {stop_loss})")
            close_position(
                position["id"],
                current_price,
                f"Stop loss triggered at {current_price} (stop was {stop_loss})"
            )
            stopped_out.append(ticker)
    return stopped_out

def check_max_hold(open_positions, current_prices):
    """
    Closes any position held longer than MAX_HOLD_DAYS.
    """
    closed = []
    today = datetime.now(GMT)
    for position in open_positions:
        opened = datetime.strptime(position["opened_at"], "%Y-%m-%d %H:%M").replace(tzinfo=GMT)
        days_held = (today - opened).days
        if days_held >= MAX_HOLD_DAYS:
            ticker = position["ticker"]
            current_price = current_prices.get(ticker, float(position["entry_price"]))
            print(f"MAX HOLD REACHED: {ticker} held {days_held} days — closing")
            close_position(
                position["id"],
                current_price,
                f"Maximum hold period of {MAX_HOLD_DAYS} days reached"
            )
            closed.append(ticker)
    return closed

def check_50_percent_targets(open_positions, current_prices):
    """
    SMART STRATEGY: Automatically closes positions at 50% of target profit.
    This accelerates learning cycles and locks in gains.
    """
    exits = []
    for position in open_positions:
        ticker = position["ticker"]
        current_price = current_prices.get(ticker)
        if current_price is None:
            continue

        entry = float(position["entry_price"])
        target = float(position["target_price"])
        target_profit = target - entry
        fifty_percent_target = entry + (target_profit * 0.5)

        # Exit if price has reached 50% of target profit
        if current_price >= fifty_percent_target and position["direction"] == "LONG":
            profit_pct = round(((current_price - entry) / entry) * 100, 2)
            print(f"✅ 50% TARGET EXIT: {ticker} at {current_price} (entry: {entry}, target: {target}) — +{profit_pct}%")
            close_position(
                position["id"],
                current_price,
                f"Automated 50% target exit at {current_price} (accelerates learning cycles)"
            )
            exits.append(ticker)
        elif current_price <= fifty_percent_target and position["direction"] == "SHORT":
            profit_pct = round(((entry - current_price) / entry) * 100, 2)
            print(f"✅ 50% TARGET EXIT: {ticker} at {current_price} (short) — +{profit_pct}%")
            close_position(
                position["id"],
                current_price,
                f"Automated 50% target exit at {current_price} (accelerates learning cycles)"
            )
            exits.append(ticker)

    return exits

def check_quick_loser_exits(open_positions, current_prices):
    """
    SMART STRATEGY: Automatically exits losers after 3-4 days to free capital.
    Prevents holding losing positions, accelerates learning.
    """
    exits = []
    today = datetime.now(GMT)

    for position in open_positions:
        # Only check losers
        loss_pct = float(position.get("pnl_pct", 0))
        if loss_pct >= 0:  # Not a loser
            continue

        # Only exit after 3 days (some patience for mean reversion)
        opened = datetime.strptime(position["opened_at"], "%Y-%m-%d %H:%M").replace(tzinfo=GMT)
        days_held = (today - opened).days

        if days_held >= 3:
            ticker = position["ticker"]
            current_price = current_prices.get(ticker, float(position["entry_price"]))
            entry = float(position["entry_price"])

            # Only exit if still negative (don't let it bounce back)
            if current_price < entry:
                loss_pct = round(((current_price - entry) / entry) * 100, 2)
                print(f"⚠️ QUICK LOSER EXIT: {ticker} at {current_price} after {days_held} days — {loss_pct}%")
                close_position(
                    position["id"],
                    current_price,
                    f"Automatic loser exit after {days_held} days to free capital for new trades"
                )
                exits.append(ticker)

    return exits

def get_portfolio_summary():
    """
    Returns a summary string for Claude to use in analysis.
    """
    try:
        open_positions = get_open_positions()
        closed_positions = get_closed_positions()
        balance = get_portfolio_balance()

        total_invested = sum(float(p["position_size"]) for p in open_positions)
        total_pnl = sum(float(p["pnl"]) for p in closed_positions if p["pnl"])
        total_trades = len(closed_positions)
        winning_trades = len([p for p in closed_positions if p["pnl"] and float(p["pnl"]) > 0])
        win_rate = round(winning_trades / total_trades * 100, 1) if total_trades > 0 else 0

        summary = f"""
PORTFOLIO STATUS:
Cash balance: £{round(balance, 2)}
Invested: £{round(total_invested, 2)}
Total value: £{round(balance + total_invested, 2)}
Starting balance: £{STARTING_BALANCE}
Total return: £{round(total_pnl, 2)} ({round((total_pnl / STARTING_BALANCE) * 100, 2)}%)
Closed trades: {total_trades} ({win_rate}% win rate)

OPEN POSITIONS ({len(open_positions)}/{MAX_POSITIONS}):
"""
        if not open_positions:
            summary += "No open positions.\n"
        else:
            tickers = [p["ticker"] for p in open_positions]
            current_prices = get_current_prices(tickers)
            for p in open_positions:
                ticker = p["ticker"]
                current = current_prices.get(ticker, float(p["entry_price"]))
                entry = float(p["entry_price"])
                unrealised_pct = round(((current - entry) / entry) * 100, 2)
                days_held = (datetime.now(GMT) - datetime.strptime(
                    p["opened_at"], "%Y-%m-%d %H:%M").replace(tzinfo=GMT)).days
                summary += f"{ticker}: entry {entry} | current {current} | target {p['target_price']} | stop {p['stop_loss']} | {unrealised_pct}% | day {days_held}/{MAX_HOLD_DAYS} | {p['confidence']}\n"

        return summary

    except Exception as e:
        print(f"Portfolio summary error: {e}")
        return "Portfolio data unavailable."