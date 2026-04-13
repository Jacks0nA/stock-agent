"""
Reset portfolio to 30,000 pounds and verify trade closing logic
"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def get_headers():
    return {
        "apikey": os.getenv("SUPABASE_KEY"),
        "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def get_base_url():
    return os.getenv("SUPABASE_URL")

def reset_portfolio():
    """Reset portfolio balance to 30,000 pounds"""
    try:
        url = f"{get_base_url()}/rest/v1/portfolio_state"

        # Try to update existing balance record
        headers = get_headers()
        response = httpx.patch(
            f"{url}?key=eq.balance",
            headers=headers,
            json={"value": "30000.0"}
        )

        if response.status_code in (200, 204):
            print("✅ Portfolio balance reset to £30,000.00")
            return True
        else:
            # If update fails, try insert
            response = httpx.post(url, headers=headers, json={
                "key": "balance",
                "value": "30000.0"
            })
            if response.status_code in (200, 201):
                print("✅ Portfolio balance initialized to £30,000.00")
                return True
            else:
                print(f"❌ Failed to reset balance: {response.status_code} {response.text}")
                return False
    except Exception as e:
        print(f"❌ Error resetting portfolio: {e}")
        return False

def verify_closed_trades():
    """Verify that closed trades have correct P&L calculation"""
    try:
        url = f"{get_base_url()}/rest/v1/positions?status=eq.CLOSED&order=closed_at.desc&limit=10"
        response = httpx.get(url, headers=get_headers())

        if response.status_code != 200:
            print(f"❌ Failed to fetch closed trades: {response.status_code}")
            return False

        closed_trades = response.json()
        if not closed_trades:
            print("ℹ️ No closed trades to verify")
            return True

        print("\n📊 CLOSED TRADES VERIFICATION:")
        print("-" * 80)

        for trade in closed_trades[:10]:  # Check last 10 trades
            ticker = trade["ticker"]
            position_size = float(trade["position_size"])
            entry_price = float(trade["entry_price"])
            exit_price = float(trade["exit_price"]) if trade.get("exit_price") else 0
            pnl = float(trade["pnl"]) if trade.get("pnl") else 0
            pnl_pct = float(trade["pnl_pct"]) if trade.get("pnl_pct") else 0

            # Verify calculation: pnl should be position_size * (pnl_pct / 100)
            expected_pnl = position_size * (pnl_pct / 100)
            expected_return = position_size + pnl

            status = "✅" if abs(expected_pnl - pnl) < 0.01 else "⚠️"
            print(f"{status} {ticker}")
            print(f"   Size: £{position_size:.2f} | Entry: £{entry_price:.2f} | Exit: £{exit_price:.2f}")
            print(f"   P&L: £{pnl:.2f} ({pnl_pct:.2f}%) | Return: £{expected_return:.2f}")
            if abs(expected_pnl - pnl) >= 0.01:
                print(f"   ⚠️ WARNING: Expected P&L £{expected_pnl:.2f}, got £{pnl:.2f}")
            print()

        return True
    except Exception as e:
        print(f"❌ Error verifying closed trades: {e}")
        return False

def get_portfolio_status():
    """Show current portfolio status"""
    try:
        # Get balance
        url = f"{get_base_url()}/rest/v1/portfolio_state?key=eq.balance"
        response = httpx.get(url, headers=get_headers())
        balance_data = response.json()
        balance = float(balance_data[0]["value"]) if balance_data else 30000.0

        # Get open positions
        url = f"{get_base_url()}/rest/v1/positions?status=eq.OPEN"
        response = httpx.get(url, headers=get_headers())
        open_positions = response.json() or []

        # Get closed positions
        url = f"{get_base_url()}/rest/v1/positions?status=eq.CLOSED"
        response = httpx.get(url, headers=get_headers())
        closed_positions = response.json() or []

        total_invested = sum(float(p["position_size"]) for p in open_positions)
        total_pnl = sum(float(p.get("pnl", 0)) for p in closed_positions)

        print("\n" + "="*80)
        print("💰 PORTFOLIO STATUS")
        print("="*80)
        print(f"Cash Balance:     £{balance:,.2f}")
        print(f"Invested:         £{total_invested:,.2f}")
        print(f"Total Value:      £{balance + total_invested:,.2f}")
        print(f"Closed Trades:    {len(closed_positions)} (Total P&L: £{total_pnl:,.2f})")
        print(f"Open Positions:   {len(open_positions)}")
        print("="*80)

        return True
    except Exception as e:
        print(f"❌ Error getting portfolio status: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Portfolio Recovery Tool\n")

    # Step 1: Show current status
    get_portfolio_status()

    # Step 2: Reset balance
    print("\n🔄 Resetting portfolio balance...")
    reset_portfolio()

    # Step 3: Verify closed trades
    verify_closed_trades()

    # Step 4: Show new status
    print("\n✅ Reset complete!")
    get_portfolio_status()
