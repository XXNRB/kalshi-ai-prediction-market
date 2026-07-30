export type MarketSort = "volume" | "movers" | "expiration" | "prob_change";

export interface Market {
  id: number;
  ticker: string;
  title: string;
  category: string | null;
  description: string | null;
  yes_price: number;
  no_price: number;
  volume: number;
  open_interest: number;
  liquidity: number;
  expiration_date: string | null;
  updated_at: string;
  price_change_24h: number;
}

export interface PricePoint {
  timestamp: string;
  yes_price: number;
  no_price: number;
  volume: number;
}

export interface MarketAnalysis {
  market_ticker: string;
  market_implied_probability: number;
  ai_estimated_probability: number;
  edge: number;
  reasoning: string[];
  risks: string[];
  confidence: number;
  recommendation: string;
  suggested_allocation_pct: number;
  data_sources: string[];
}
