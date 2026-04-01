# Daily Monitoring Guide - Fully Autonomous System

**Time commitment:** 2 minutes per day

---

## What You Need to Know

Your trading system is now **fully autonomous**. It opens trades AND closes them without your intervention. Your job is simply to monitor what's happening.

---

## Daily Workflow

### Morning (1 minute)
1. **Open dashboard** at `localhost:8501` or your deployment
2. **Glance at:**
   - Open positions (should be 2-4 typically)
   - Any overnight closes
   - Portfolio balance change
3. **Note:** System ran analysis at 1:30am ET (8:30am UK)

### Midday (30 seconds)
- Check if any positions hit 50% target and auto-closed (excellent!)
- No action needed — system closes them automatically

### Evening (30 seconds)
- Review if any losers were auto-exited (capital freed for new trades)
- Check portfolio balance update
- Done!

---

## What You'll See (And What It Means)

### ✅ **"50% TARGET EXIT" Messages**
```
✅ 50% TARGET EXIT: AAPL at 192.50 (entry: 190, target: 200) — +1.32%
```
**Meaning:** Claude opened at 190, target was 200, position closed at 192.50 (50% of way)
**Why:** Locks in gains, increases trading cycles, accelerates learning
**Action:** None — this is automatic and desired!

### ✅ **"QUICK LOSER EXIT" Messages**
```
⚠️ QUICK LOSER EXIT: MSFT at 402 after 3 days — -1.5%
```
**Meaning:** Position was down 1.5% after 3 days, auto-closed to free capital
**Why:** Don't let losers sit indefinitely, redeploy capital to new opportunities
**Action:** None — working as designed

### ✅ **"NO_TRADE" Days**
```
NO_TRADE: Only 2 candidates (MSFT, GOOGL) both score <11 and lack 2+ confirmers
```
**Meaning:** No setups met ultra-selective criteria (score 11+, 2+ confirmers)
**Why:** Quality > quantity. Better to wait than force marginal trades
**Action:** None — this is GOOD discipline!

### ⚠️ **"STOP LOSS" Closes**
```
STOP LOSS TRIGGERED: SPY at 410 (stop: 411)
```
**Meaning:** Position hit its risk limit, closed to prevent further losses
**Why:** Capital preservation — automatic risk management
**Action:** Note this for learning — signal failed, take note for future

### 📋 **"MAX HOLD" Closes**
```
MAX HOLD REACHED: NVDA held 10 days — closing
```
**Meaning:** Position held 10 days (max allowed), closed regardless of P&L
**Why:** Prevent capital from getting locked up too long
**Action:** None — periodic hygiene

---

## What The System Learns Each Week

Every closed position teaches the system:
- ✅ Did this confidence tier work? (CONFIDENT/MEDIUM/etc)
- ✅ Did this signal combination predict wins? (RSI div + insider, etc)
- ✅ Did this sector perform? (Tech vs Energy vs Healthcare)
- ✅ Did this hold time work? (3 days vs 5 days vs 10 days)
- ✅ Which entry conditions led to profits?

**By week 4:** System adapts to what's working
**By week 8:** System recognizes market regimes (bull/bear/VIX)
**By week 12:** System has personalized per-ticker rules with 70%+ accuracy

---

## Weekly Review (5 minutes on Friday)

### Check These Numbers

**Portfolio Status:**
- [ ] How many positions closed this week?
- [ ] What was win rate? (target: 65%+)
- [ ] Avg winner size? (target: +1.5%+)
- [ ] Avg loser size? (target: -0.5% or better)

**Closed Positions Details:**
- [ ] Click "View All Closed Positions"
- [ ] Note the reasoning for each exit
- [ ] Identify patterns in winners vs losers

**Learning Tab:**
- [ ] Check which signals appear most in winners
- [ ] Note confidence tier effectiveness
- [ ] See sector performance ranking

---

## Monthly Review (10 minutes, end of month)

### Track Acceleration

| Metric | Target | Your Result |
|--------|--------|------------|
| Closed positions | 8-12 | _____ |
| Win rate | 65%+ | _____ |
| Avg winner | +1.8%+ | _____ |
| Avg loser | -0.6% or better | _____ |
| Sharpe ratio trend | → | _____ |

### Month 1 Checklist
- [ ] At least 8 closed trades (learning fuel)
- [ ] 50%+ win rate (baseline establishment)
- [ ] Clear winners/losers emerging (signal validation)
- [ ] 2-3 different sectors traded (diversity)

### Month 2 Checklist
- [ ] 16-20 closed trades total (doubling learning data)
- [ ] 65%+ win rate (system learning)
- [ ] Avg winner 1.8%+ (edge emerging)
- [ ] Recognizable patterns (system adaptation)
- [ ] Month 2 expected: 70%+ accuracy

---

## What NOT to Do

### ❌ **Don't manually close winning positions early**
The system exits at 50% target. It knows what it's doing.

### ❌ **Don't lower the score threshold to 10**
Ultra-selective criteria (11+) is what makes this work.

### ❌ **Don't second-guess NO_TRADE days**
No good setups = no trade. Quality over quantity.

### ❌ **Don't override stop losses**
Let losers exit. Capital freed = new opportunities.

### ❌ **Don't trade the same sector repeatedly**
Rotation is how the system learns diversity.

### ❌ **Don't check the dashboard every 5 minutes**
Check morning, midday, evening. That's it.

---

## Troubleshooting

**Q: A position didn't auto-close at 50% target — why?**
A: Probably just hasn't reached that price yet. Check the entry, target, and current price. 50% target = entry + (target-entry) × 0.5

**Q: Why did a winning position auto-close? Seems early.**
A: By design! Locks in gains, increases learning cycles. The other 50% can run if momentum continues.

**Q: Why so many NO_TRADE days?**
A: Good! Means criteria are working. Score <11 setups often fail. Better to skip.

**Q: A position exited at max hold (10 days) with small loss — was this wrong?**
A: No, it's capital hygiene. Prevents capital lockup. Small losses are okay for the learning.

**Q: Why hasn't win rate hit 65% yet?**
A: Week 1-2 is baseline establishment. Week 3+ accelerates. By week 4 should see improvement.

---

## Portfolio Health Signals

### 🟢 **Green Flags** (System working well)
- [ ] 2-3 NEW_TRADE decisions per analysis
- [ ] 1-2 NO_TRADE days per week
- [ ] Positions closing at ~50% target
- [ ] Quick loser exits happening (3+ day rule)
- [ ] Different sectors being traded
- [ ] Win rate trending up week-to-week

### 🟡 **Yellow Flags** (Monitor closely)
- Only 1 closed trade per week (not hitting targets?)
- Win rate stuck at 50% (signals not working?)
- Same sector repeatedly (not rotating?)
- Long hold times (not exiting at 50% target?)

### 🔴 **Red Flags** (Needs investigation)
- 0 closed trades in a week (system not opening?)
- Win rate <40% (criteria broken?)
- Large losing streak (market regime change?)
- Portfolio balance declining sharply (losers too large?)

---

## The Big Picture

**Your job:** Monitor and celebrate wins
**System's job:** Learn, adapt, improve

By following this simple workflow, the AI will:
- Analyze 50+ trades in 8 weeks
- Learn which signals work in your favor
- Adapt to market conditions
- Build a personalized 70%+ accuracy model

Just keep the dashboard open, check it 2 minutes a day, and let the system learn.

🚀 That's it. Go make money!
