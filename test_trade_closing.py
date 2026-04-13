"""
Test script to verify trade opening and closing logic
This creates test positions, closes them with various P&L outcomes, and verifies the balance is updated correctly
"""
import sys
sys.path.insert(0, '/Users/jacksonamies/stock-agent')

from portfolio import (
    get_portfolio_balance,
    set_portfolio_balance,
    open_position,
    close_position,
    get_open_positions,
    STARTING_BALANCE
)

def print_balance(label):
    balance = get_portfolio_balance()
    open_positions = get_open_positions()
    invested = sum(float(p["position_size"]) for p in open_positions)
    total = balance + invested
    print(f"\n{'='*70}")
    print(f"{label}")
    print(f"{'='*70}")
    print(f"Cash Balance:   £{balance:>10,.2f}")
    print(f"Invested:       £{invested:>10,.2f}")
    print(f"Total Value:    £{total:>10,.2f}")
    print(f"Open Positions: {len(open_positions)}")
    return balance

def test_trade_cycle():
    """
    Test the complete trade cycle:
    1. Start with £30,000
    2. Open position (£1,000)
    3. Close with loss (£994 returned)
    4. Verify balance = 30,000 - 1,000 + 994 = 29,994
    """
    print("\n" + "#"*70)
    print("TEST: Trade Opening and Closing Logic")
    print("#"*70)

    # Reset to known state
    set_portfolio_balance(STARTING_BALANCE)
    initial_balance = print_balance("1️⃣  INITIAL STATE (reset to £30,000)")

    # Open a position that we'll close with a loss
    print("\n2️⃣  OPENING POSITION: £1,000 at £100 (will close at £99)")
    print("   Expected: Balance £30,000 → £29,000")

    open_result = open_position(
        ticker="TEST1",
        direction="LONG",
        entry_price=100.0,
        target_price=110.0,
        stop_loss=95.0,
        confidence="CONFIDENT",
        score=8,
        claude_reasoning="Test trade with £1,000 position",
        position_size=1000.0
    )

    if not open_result:
        print("❌ Failed to open position")
        return False

    balance_after_open = print_balance("   After opening")

    # Get the position ID
    open_positions = get_open_positions()
    if not open_positions:
        print("❌ No open positions found after opening")
        return False

    position = open_positions[-1]
    position_id = position["id"]

    # Close with a loss
    print(f"\n3️⃣  CLOSING POSITION: {position['ticker']} at £99")
    print("   Entry: £100, Exit: £99 → Loss: £-10 (return £990)")
    print("   Expected Balance: £29,000 + £990 = £29,990")

    close_result = close_position(
        position_id=position_id,
        exit_price=99.0,
        reason="Test close - loss scenario"
    )

    if close_result is None:
        print("❌ Failed to close position")
        return False

    balance_after_close = print_balance("   After closing")

    # Verify the math
    expected_balance = STARTING_BALANCE - 1000 + 990
    actual_balance = get_portfolio_balance()

    print(f"\n4️⃣  VERIFICATION")
    print(f"   Expected balance: £{expected_balance:.2f}")
    print(f"   Actual balance:   £{actual_balance:.2f}")

    if abs(actual_balance - expected_balance) < 0.01:
        print(f"   ✅ PASS: Balance correctly updated!")
    else:
        print(f"   ❌ FAIL: Balance mismatch of £{abs(actual_balance - expected_balance):.2f}")
        return False

    # Test a winning trade
    print(f"\n5️⃣  OPENING SECOND POSITION: £500 at £200 (will close at £210)")
    print("   Expected: Balance £29,990 → £29,490")

    open_result = open_position(
        ticker="TEST2",
        direction="LONG",
        entry_price=200.0,
        target_price=220.0,
        stop_loss=190.0,
        confidence="MEDIUM",
        score=7,
        claude_reasoning="Test trade 2 with £500 position",
        position_size=500.0
    )

    if not open_result:
        print("❌ Failed to open second position")
        return False

    balance_after_open2 = print_balance("   After opening")

    # Get the new position
    open_positions = get_open_positions()
    if len(open_positions) < 1:
        print("❌ No open positions found after second opening")
        return False

    position2 = open_positions[-1]
    position_id2 = position2["id"]

    # Close with a gain
    print(f"\n6️⃣  CLOSING SECOND POSITION: {position2['ticker']} at £210")
    print("   Entry: £200, Exit: £210 → Gain: £+25 (return £525)")
    print("   Calculation: £500 * (210-200)/200 = £500 * 5% = £25 gain")
    print("   Expected Balance: £29,490 + £525 = £30,015")

    close_result2 = close_position(
        position_id=position_id2,
        exit_price=210.0,
        reason="Test close - gain scenario"
    )

    if close_result2 is None:
        print("❌ Failed to close second position")
        return False

    balance_after_close2 = print_balance("   After closing")

    # Final verification
    # Trade 1: Open £1000, Close at loss of £10 (return £990) → Net: -£10
    # Trade 2: Open £500, Close at gain of £25 (return £525) → Net: +£25
    # Final: £30,000 - £10 + £25 = £30,015
    expected_final_balance = STARTING_BALANCE - 10 + 25
    actual_final_balance = get_portfolio_balance()

    print(f"\n7️⃣  FINAL VERIFICATION")
    print(f"   Starting Balance:        £{STARTING_BALANCE:,.2f}")
    print(f"   Trade 1 (Loss):          -£1,000 opening → +£990 return = -£10 net")
    print(f"   Trade 2 (Gain):          -£500 opening → +£525 return = +£25 net")
    print(f"   Expected final balance:  £{expected_final_balance:,.2f}")
    print(f"   Actual final balance:    £{actual_final_balance:,.2f}")

    if abs(actual_final_balance - expected_final_balance) < 0.01:
        print(f"\n   ✅ PASS: All trades calculated correctly!")
        return True
    else:
        print(f"\n   ❌ FAIL: Final balance mismatch of £{abs(actual_final_balance - expected_final_balance):.2f}")
        return False

if __name__ == "__main__":
    success = test_trade_cycle()
    sys.exit(0 if success else 1)
