# Project Status

_Last updated: 2026-08-21 — this file is the source of truth for what's actually
built. If `README.md` or `ARCHITECTURE.md` ever disagree with this file, this
file wins until they're updated to match._

## Where we are

Three build phases shipped, a fourth planned next:

| Phase | What it is | Status |
|---|---|---|
| 1 | Market ingestion, dashboard, AI research analysis (Agent 1) | ✅ Shipped |
| 1.5 | Paper trading engine, opportunity ranking, backtesting engine | ✅ Shipped |
| 2 | $1,000 bankroll, conviction-weighted allocation, position stats, modular exit engine | ✅ Shipped |
| 3 | MLB live game-state — data layer only | ✅ Shipped |
| 4 (planned) | Data collection + backtesting infrastructure | ⚪ Not started |

Deliberately **not** next: an ML/AI trading subsystem (BTC or otherwise).
That comes after Phase 4 builds the labeled dataset it would need to be
anything more than sophisticated guessing — see "Next up" below.

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
- **MLB live game-state (Phase 3)** — see its own section below.

## Built but explicitly not validated: the exit engine

The modular exit engine (`backend/app/services/exit_engine.py`) is real,
tested, and running in the background — but its automation should be treated
as **experimental until proven**, not as a feature we trust yet.

- **`RECOMMEND_ONLY` is the default and the only mode this project actually
  endorses right now.** It logs a structured decision for every open
  position, every cycle, and never acts on it.
- **`AUTO_EXECUTE` is opt-in and experimental.** It exists so the
  architecture (safety checks, audit logging, peak tracking) is in place
  when it's needed — not because it's been shown to help. (An earlier live
  test session had left the running app's own setting on `AUTO_EXECUTE`;
  caught and reset to `RECOMMEND_ONLY` during Phase 3 verification — it's a
  live toggle, not a hardcoded default, so it's worth checking after any
  round of manual testing.)
- **The validation plan, not yet built:** use the `RECOMMEND_ONLY` audit log
  (`ExitDecisionLog` — every evaluation, executed or not, with reason codes)
  to compute what the engine's recommendations *would have* returned had
  they been followed, and compare that hypothetical performance against
  hold-to-resolution and other simple exits (e.g. fixed stop-loss). Only
  once that comparison shows an actual edge does `AUTO_EXECUTE` become
  something to recommend turning on, or a candidate for a new default. This
  comparison is Phase 4 work — see "Next up."
- Until then: don't read the existence of the exit engine, or of
  `AUTO_EXECUTE` as a config option, as a claim that automated exits have
  been shown to add value. They haven't been tested against a baseline yet.

## Shipped: MLB live game-state (Phase 3)

Scoped deliberately narrow, and stayed that way through implementation. MLB
Gameday is a **data provider only** — resolved once per market, polled,
displayed next to the Kalshi position, and stored for later analysis.
**No buy/sell decision depends on MLB game-state data** — `evaluate_exit()`
still calls only the flat-ROI strategy for every market, MLB included, with
no dispatch branch added. That boundary is enforced by construction: the
exit engine's function signature never receives the MLB provider, cache, or
any MLB model — there's nothing there *to* wire in by accident.

What shipped:
- **Provider** (`backend/app/services/mlb/provider.py`) — `statsapi.mlb.com`
  confirmed live (not scraping) as the same backend Gameday's own frontend
  calls, isolated behind an `MLBProvider` Protocol so swapping providers
  later means implementing the interface again, nothing else changes.
- **Mapper** (`services/mlb/mapper.py`) — raw live-feed JSON → a structured
  `GameState` (score, inning/half, outs, baserunners, batter/pitcher, last
  play, status), tested against a real captured game.
- **Matcher** (`services/mlb/matcher.py`) — resolves a `Market` to an MLB
  `gamePk` **once**, off the ticker's own team codes (verified against
  MLB's official team abbreviations, not fuzzy title parsing), persisted to
  `MLBGameLink` and reused forever after. Doubleheaders tie-break on
  closest game time to when Kalshi opened the market; unresolved markets
  retry at most once/hour, never every cycle.
- **Polling loop** (`services/mlb/poller.py` + `core/scheduler.py`) — a
  third background task, adaptive per game status (live ~30s, pregame
  ~5min, delayed/suspended ~2min, final → stops entirely), deduped so two
  markets on the same game share one fetch. The only place in the app that
  makes an MLB network call — a slow or failing MLB API can't stall Kalshi
  ingestion or the exit-monitor loop.
- **Storage** (`MLBGameStateSnapshot`) — one row per successful poll: the
  full game state next to the linked market's Kalshi prices at that same
  moment. This is the Phase 4 dataset's MLB half.
- **Display** (`PositionStatsRow.tsx`) — an informational "Game" line,
  separate from the exit-engine action badge, omitted entirely when no
  state is available yet rather than showing a placeholder.
- Also fixed as part of this phase: the flat 20% ROI threshold in the exit
  engine no longer returns a sell recommendation (`SELL_ALL`) on its own —
  a price crossing a threshold isn't evidence that selling beats holding,
  so it now stays `HOLD` with an informational `PROFIT_MILESTONE_REACHED`
  reason code.

Verified live against the real MLB Stats API (not just fixtures): a real
market's ticker resolved to its real `gamePk`, a real live-feed poll wrote a
correct `MLBGameStateSnapshot`, and the frontend rendered the resulting
score/inning line — while `exit_decision` on that same position kept coming
from the unchanged flat-ROI logic throughout.

## Task board

| # | Task | Status |
|---|---|---|
| 1–15 | Phase 1.5 / Phase 2 (bankroll, allocation, position stats, exit engine core, safety controls, background loop, routes, frontend, tests) | ✅ Done |
| 16–26 | Phase 3 (MLB schema, provider/mapper, models, matcher, cache, config, polling loop, route/schema wiring, tests, frontend display, verification) | ✅ Done |

100/100 backend tests passing, including 22 new MLB tests (mapper, matcher,
poller/snapshot) run against real captured MLB data, no live network calls
in the suite itself.

## Explicit non-goals right now

- MLB (or any) game-state data influencing a buy/sell decision.
- Treating `AUTO_EXECUTE` as production-ready or as the recommended mode.
- Real-money trading of any kind — everything above is paper trading only.
- An ML/AI trading subsystem of any kind (BTC included) before Phase 4's
  dataset exists to test it against.

## Next up: Phase 4 — data collection + backtesting infrastructure

Deliberately comes *before* any ML/AI trading subsystem, not after. The
goal is a labeled historical dataset that can actually answer questions
like: when Kalshi YES was 43¢ with 7 minutes remaining, BTC was $18 below
threshold, 1-minute momentum was positive, RSI was X, volatility was Y,
spread was Z — what actually happened? Without that dataset, a model is
mostly sophisticated guessing.

Scope, not yet built:
1. Extend the snapshot approach beyond MLB — systematic price/feature
   history for non-MLB markets (BTC threshold markets included), not just
   whatever `PriceHistory` already captures incidentally.
2. The `RECOMMEND_ONLY`-log-vs-baseline comparison described above, so the
   exit engine's hypothetical performance is measured against
   hold-to-resolution and other simple exits before `AUTO_EXECUTE` is ever
   reconsidered as a default.
3. Architecture references worth studying (not copying): a separate Kalshi
   research project doing short-horizon (5/15/30/60-minute) prediction with
   a mixture-of-experts approach across multiple model families, and other
   open-source Kalshi systems implementing WebSocket market feeds, market
   scanning, risk controls, momentum/reversion strategies, paper trading,
   and position sizing. Useful for how to structure Phase 4's data/
   infrastructure layer — their trading logic isn't something to adopt
   wholesale, especially not before this project has its own validation
   data.

Only after Phase 4 produces that dataset does an ML/AI subsystem (BTC or
otherwise) become something to scope.
