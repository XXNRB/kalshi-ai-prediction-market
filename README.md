# Kalshi AI Trading Research Assistant

An AI-assisted research and paper-trading platform for Kalshi prediction
markets. This is a **decision-support tool, not a trading bot** — no real
money moves automatically, every AI recommendation is shown with its
reasoning, confidence, risks, and data sources, and the paper-trading exit
engine's automated mode is off by default and treated as experimental (see
below).

See [ARCHITECTURE.md](./ARCHITECTURE.md) for system design and
[PROJECT_STATUS.md](./PROJECT_STATUS.md) for exactly what's built, what's in
progress, and what's explicitly not validated yet — that file is the source
of truth if anything here goes stale.

## What's built

- **Market ingestion & dashboard** — live Kalshi markets polled every 60s,
  stored in SQLite, sortable table (volume, movers, expiration, probability
  change), price-history charts.
- **AI research analysis (Agent 1)** — on-demand OpenAI-based analysis per
  market: probability estimate, confidence, reasoning, risks, recommendation.
- **Opportunity ranking** — a 0–100 score (liquidity, volatility,
  time-to-expiration, AI conviction) shown as a star rating with a full
  breakdown.
- **Backtesting engine** — replays a market's real candle history and
  compares a signal-based strategy against buy-and-hold.
- **Paper trading engine** — a $1,000 simulated bankroll, conviction-weighted
  allocation across a batch of candidate markets, and a math-only Position
  Stats Panel (ROI, probability change, expected value, momentum, risk
  score).
- **Modular exit engine** — logs a structured `HOLD` / `SELL_PARTIAL` /
  `SELL_ALL` recommendation for every open position on a background loop.
  `RECOMMEND_ONLY` is the default and only mode this project currently
  endorses; `AUTO_EXECUTE` exists and is safety-gated, but is experimental
  and unvalidated — see [PROJECT_STATUS.md](./PROJECT_STATUS.md).
- **MLB live game-state** — MLB Gameday data (via `statsapi.mlb.com`,
  isolated behind a swappable provider interface) resolved, polled, and
  stored alongside Kalshi prices, and shown as an informational line next
  to the position. Not wired into any buy/sell decision — the exit engine's
  logic doesn't change for MLB markets, by design, until there's enough
  paper-trading history to backtest whether game state actually helps.

## Not built yet

- Data collection + backtesting infrastructure (Phase 4, planned next): a
  systematic labeled dataset across markets, and the backtest comparing the
  exit engine's logged recommendations against hold-to-resolution and other
  simple baselines — the actual test of whether it's worth trusting.
- Any ML/AI trading subsystem (BTC included) — deliberately comes after
  Phase 4's dataset exists, not before.
- Real-money trading of any kind.

## Prerequisites

- Python 3.9+
- Node.js 18+
- An OpenAI API key (for AI analysis — the rest of the app works without one)

## Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # then fill in OPENAI_API_KEY
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`. On startup it immediately polls
Kalshi, then every `INGESTION_INTERVAL_SECONDS` (default 60s); the exit
engine evaluates every open position every `EXIT_MONITOR_INTERVAL_SECONDS`
(default 45s) in the background, independent of the frontend being open.

Run tests:

```bash
pytest
```

## Frontend setup

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

The dashboard runs at `http://localhost:3000`.

## Environment variables

See [.env.example](./.env.example) for the base list. Backend reads from
`backend/.env`; frontend reads from `frontend/.env.local`. Exit-engine and
paper-trading tuning (bankroll size, auto-execute confidence/size/staleness
limits, per-cycle sell cap) live in `backend/app/config.py` with sane
defaults and can be overridden the same way.

## Project principles

- Never assume an AI prediction is correct. Every recommendation must show
  its reasoning, confidence, risk, and data sources.
- Build in phases, and don't trust automation until it's validated. Research
  tool → paper trading → exit-strategy validation → optional real-money
  trading, each phase gated behind the previous one's data proving out.
  `AUTO_EXECUTE` exists today but is off by default and stays that way until
  its logged, hypothetical decisions are shown to beat hold-to-resolution
  and other simple baselines.
- New external data sources (e.g. MLB game state) are isolated behind a
  provider interface and start as display/storage only — they don't get to
  influence a trading decision until there's enough history to backtest
  whether they actually help.
