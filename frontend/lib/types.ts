export type MarketSort = "volume" | "movers" | "expiration" | "prob_change";

export type SignalType = "entry" | "exit" | "none";

export interface Signal {
  type: SignalType;
  label: string | null;
  explanation: string | null;
}

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
  signal: Signal | null;
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

export type BuyPosition = "YES" | "NO";

export interface Trade {
  id: number;
  ticker: string;
  market_title: string;
  position: BuyPosition;
  status: "open" | "closed";
  entry_price: number;
  exit_price: number | null;
  amount: number;
  contracts: number;
  current_price: number | null;
  profit_loss: number | null;
  timestamp: string;
  exit_timestamp: string | null;
}

export interface PortfolioSummary {
  starting_balance: number;
  cash_balance: number;
  portfolio_value: number;
  total_pl: number;
  roi_pct: number;
  win_rate_pct: number | null;
  open_positions: Trade[];
  closed_trades: Trade[];
}
