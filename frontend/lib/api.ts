import type {
  AllocationResponse,
  BacktestResult,
  BuyPosition,
  ExitDecisionLogEntry,
  ExitMode,
  ExitSettings,
  Market,
  MarketAnalysis,
  MarketSort,
  PortfolioSummary,
  PricePoint,
  Trade,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text();
    let message = body || `API ${res.status}`;
    try {
      const parsed = JSON.parse(body);
      if (parsed?.detail) message = parsed.detail;
    } catch {
      // body wasn't JSON — fall back to the raw text above
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export function listMarkets(sortBy: MarketSort = "volume"): Promise<Market[]> {
  return apiFetch<Market[]>(`/api/markets?sort_by=${sortBy}`, { cache: "no-store" });
}

export function getMarket(ticker: string): Promise<Market> {
  return apiFetch<Market>(`/api/markets/${ticker}`, { cache: "no-store" });
}

export function getMarketHistory(ticker: string): Promise<PricePoint[]> {
  return apiFetch<PricePoint[]>(`/api/markets/${ticker}/history`, { cache: "no-store" });
}

export function analyzeMarket(ticker: string): Promise<MarketAnalysis> {
  return apiFetch<MarketAnalysis>(`/api/markets/${ticker}/analyze`, { method: "POST" });
}

export async function getCachedAnalysis(ticker: string): Promise<MarketAnalysis | null> {
  try {
    return await apiFetch<MarketAnalysis>(`/api/markets/${ticker}/analysis`, { cache: "no-store" });
  } catch {
    return null;
  }
}

export function getPortfolio(): Promise<PortfolioSummary> {
  return apiFetch<PortfolioSummary>("/api/portfolio", { cache: "no-store" });
}

export function buyPosition(ticker: string, position: BuyPosition, amount: number): Promise<Trade> {
  return apiFetch<Trade>("/api/portfolio/trades", {
    method: "POST",
    body: JSON.stringify({ ticker, position, amount }),
  });
}

export function sellPosition(tradeId: number): Promise<Trade> {
  return apiFetch<Trade>(`/api/portfolio/trades/${tradeId}/sell`, { method: "POST" });
}

export function runAllocation(tickers: string[]): Promise<AllocationResponse> {
  return apiFetch<AllocationResponse>("/api/portfolio/allocate", {
    method: "POST",
    body: JSON.stringify({ tickers }),
  });
}

export function getExitSettings(): Promise<ExitSettings> {
  return apiFetch<ExitSettings>("/api/portfolio/exit-settings", { cache: "no-store" });
}

export function updateExitSettings(mode: ExitMode): Promise<ExitSettings> {
  return apiFetch<ExitSettings>("/api/portfolio/exit-settings", {
    method: "PUT",
    body: JSON.stringify({ mode }),
  });
}

export function getExitLog(limit = 50): Promise<ExitDecisionLogEntry[]> {
  return apiFetch<ExitDecisionLogEntry[]>(`/api/portfolio/exit-log?limit=${limit}`, { cache: "no-store" });
}

export function runBacktest(
  ticker: string,
  params?: { starting_balance?: number; bet_size?: number }
): Promise<BacktestResult> {
  return apiFetch<BacktestResult>(`/api/markets/${ticker}/backtest`, {
    method: "POST",
    body: JSON.stringify(params ?? {}),
  });
}
