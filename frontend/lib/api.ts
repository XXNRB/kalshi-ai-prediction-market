import type { Market, MarketAnalysis, MarketSort, PricePoint } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
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
