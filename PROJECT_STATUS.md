# Project Status

_Last updated: 2026-08-20 — this file is the source of truth for what's actually
built. If `README.md` or `ARCHITECTURE.md` ever disagree with this file, this
file wins until they're updated to match._

## Where we are

Three build phases in, the third in progress:

| Phase | What it is | Status |
|---|---|---|
| 1 | Market ingestion, dashboard, AI research analysis (Agent 1) | ✅ Shipped |
| 1.5 | Paper trading engine, opportunity ranking, backtesting engine | ✅ Shipped |
| 2 | $1,000 bankroll, conviction-weighted allocation, position stats, modular exit engine | ✅ Shipped |
| 3 | MLB live game-state — data layer only | 🟡 In progress |
| 4 (planned) | BTC ML subsystem | ⚪ Not started |

## Shipped and in active use

- **Market ingestion & dashboard** — live Kalshi markets polled every 60s,
  sortable table, price-history charts.
- **AI research analysis (Agent 1)** — on-demand, always shown with
  reasoning/confidence/risks, never presented as ground truth.
- **Opportunity ranking (Feature 5)** — 0–100 score across liquidity,
  volatility, time-to-expiration, and AI-conviction components; shown as a
  star rating with a full breakdown.
- **Backtesting engine** — replays a market's real candle history and
  compares a signal-based exit strategy against buy-and-hold, with
  win rate, max drawdown, and Sharpe.
- **Paper trading engine** — $1,000 simulated bankroll, conviction-weighted
  allocation across a batch of candidates (skips toss-ups, redistributes
  their stake to stronger picks), and a math-only Position Stats Panel
  (ROI, probability change, expected value, momentum, risk score).

## Built but explicitly not validated: the exit engine

The modular exit engine (`backend/app/services/exit_engine.py`) is real,
tested, and running in the background — but its automation should be treated
as **experimental until proven**, not as a feature we trust yet.

- **`RECOMMEND_ONLY` is the default and the only mode this project actually
  endorses right now.** It logs a structured decision for every open
  position, every cycle, and never acts on it.
- **`AUTO_EXECUTE` is opt-in and experimental.** It exists so the
  architecture (safety checks, audit logging, peak tracking) is in place
  when it's needed — not because it's been shown to help.
- **The validation plan, not yet built:** use the `RECOMMEND_ONLY` audit log
  (`ExitDecisionLog` — every evaluation, executed or not, with reason codes)
  to compute what the engine's recommendations *would have* returned had
  they been followed, and compare that hypothetical performance against
  hold-to-resolution and other simple exits (e.g. fixed stop-loss). Only
  once that comparison shows an actual edge does `AUTO_EXECUTE` become
  something to recommend turning on, or a candidate for a new default.
- Until then: don't read the existence of the exit engine, or of
  `AUTO_EXECUTE` as a config option, as a claim that automated exits have
  been shown to add value. They haven't been tested against a baseline yet.

## In progress: MLB live game-state (Phase 3)

Scoped deliberately narrow. MLB Gameday becomes a **data provider only** —
resolved once per market, polled, displayed next to the Kalshi position, and
stored for later analysis. **No buy/sell decision may depend on MLB
game-state data** until there's enough paper-trading history to backtest
whether it actually improves predictions.

Done so far:
- Relabeled the flat 20% ROI threshold in the exit engine: it no longer
  returns a sell recommendation (`SELL_ALL`) on its own. A price crossing a
  threshold isn't evidence that selling beats holding, so it now stays
  `HOLD` with an informational `PROFIT_MILESTONE_REACHED` reason code.
- `statsapi.mlb.com` confirmed live (not scraping) as the source Gameday's
  own frontend uses, and selected as the initial provider, isolated behind a
  swappable interface.

Not started yet: the `MLBProvider` implementation + mapper, game
resolution/matching, the polling loop, persistence tables, and the frontend
display line. See the task board below.

## Task board

| # | Task | Status |
|---|---|---|
| 1–15 | Phase 1.5 / Phase 2 (bankroll, allocation, position stats, exit engine core, safety controls, background loop, routes, frontend, tests) | ✅ Done |
| 16 | MLB `GameState` schema | 🟡 In progress |
| 17 | MLB provider + mapper (`statsapi.mlb.com`) | ⚪ Not started |
| 18 | `MLBGameLink` + `MLBGameStateSnapshot` models | ⚪ Not started |
| 19 | MLB matcher (team alias + game resolution) | ⚪ Not started |
| 20 | MLB in-memory cache | ⚪ Not started |
| 21 | Config settings for MLB | ⚪ Not started |
| 22 | `run_mlb_polling_loop` + wiring | ⚪ Not started |
| 23 | Relabel flat-ROI strategy (`SELL_ALL` → `HOLD` + milestone) | ✅ Done |
| 24 | Update/add tests for the above | ⚪ Not started |
| 25 | Frontend: game-state display line | ⚪ Not started |
| 26 | Verify: pytest + table creation + live checks | ⚪ Not started |

## Explicit non-goals right now

- MLB (or any) game-state data influencing a buy/sell decision.
- Treating `AUTO_EXECUTE` as production-ready or as the recommended mode.
- Real-money trading of any kind — everything above is paper trading only.

## Next up

1. Finish the Phase 3 MLB data layer (tasks 17–26) as a pure display/storage
   feature — still no coupling to decisions.
2. Build the `RECOMMEND_ONLY`-log-vs-baseline comparison described above, so
   the exit engine's value (if any) is measured before it's trusted.
3. BTC ML subsystem — planned next, not yet scoped.
