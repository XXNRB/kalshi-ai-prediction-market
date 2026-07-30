# Kalshi AI Trading Research Assistant

An AI-assisted research and paper-trading platform for Kalshi prediction
markets. This is a **decision-support tool, not a trading bot** — no real or
simulated money moves automatically, and every AI recommendation is shown
with its reasoning, confidence, risks, and data sources.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the system design and roadmap.

## Phase 1 (current)

- Ingest live Kalshi markets (public, unauthenticated market-data API).
- Store markets + price history in SQLite.
- Dashboard with sortable market table (volume, movers, expiration, probability change).
- Market detail page with price-history chart.
- On-demand AI research analysis per market (Agent 1: OpenAI-based Research Analyst).

Paper trading, opportunity scoring, and real trading are **not** built yet —
see the roadmap in `ARCHITECTURE.md`.

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
Kalshi and then every `INGESTION_INTERVAL_SECONDS` (default 60s).

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

See [.env.example](./.env.example) for the full list. Backend reads from
`backend/.env`; frontend reads from `frontend/.env.local`.

## Project principles

- Never assume an AI prediction is correct. Every recommendation must show
  its reasoning, confidence, risk, and data sources.
- Build in phases — this is a research tool first, paper-trading second,
  and real-money trading only later, behind explicit opt-in and risk limits.
