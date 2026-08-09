export type MarketSort = "volume" | "movers" | "expiration" | "prob_change" | "opportunity";

export type SignalType = "entry" | "exit" | "none";

export interface Signal {
  type: SignalType;
  label: string | null;
  explanation: string | null;
}

export interface ScoreComponent {
  label: string;
  score: number;
  max_score: number;
  explanation: string;
}

export interface OpportunityScore {
  total: number;
  stars: number;
  tier_label: string;
  researched: boolean;
  components: ScoreComponent[];
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
  opportunity: OpportunityScore | null;
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
  analyzed_at: string | null;
}

export type BuyPosition = "YES" | "NO";

export interface PositionMetrics {
  roi_pct: number;
  probability_change_pts: number;
  expected_value_pct: number | null;
  momentum_pts_per_step: number;
  risk_score: number;
  unrealized_profit_loss: number;
  peak_price: number;
  peak_profit_loss: number;
}

export type ExitAction = "HOLD" | "SELL_PARTIAL" | "SELL_ALL";
export type ExitUrgency = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type ExitMode = "recommend_only" | "auto_execute";

export interface ExitDecision {
  action: ExitAction;
  confidence: number;
  urgency: ExitUrgency;
  reason_codes: string[];
  summary: string;
  sell_fraction: number | null;
}

export interface ExitSettings {
  mode: ExitMode;
  updated_at: string;
}

export interface ExitDecisionLogEntry {
  id: number;
  trade_id: number;
  ticker: string;
  side: BuyPosition;
  timestamp: string;
  mode: ExitMode;
  entry_price: number;
  current_price: number;
  peak_price: number;
  contracts: number;
  unrealized_profit_loss: number;
  realized_profit_loss: number | null;
  action: ExitAction;
  confidence: number;
  urgency: ExitUrgency;
  reason_codes: string[];
  summary: string;
  executed: boolean;
  execution_price: number | null;
}

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
  metrics: PositionMetrics | null;
  exit_decision: ExitDecision | null;
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

export interface BacktestTrade {
  entry_time: string;
  entry_price: number;
  exit_time: string;
  exit_price: number;
  profit_loss: number;
  exit_reason: "exit_signal" | "end_of_window";
}

export interface StrategyResult {
  strategy: string;
  starting_balance: number;
  ending_balance: number;
  total_return_pct: number;
  win_rate_pct: number | null;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  trade_count: number;
  trades: BacktestTrade[];
}

export interface BacktestResult {
  ticker: string;
  period_start: string;
  period_end: string;
  candle_count: number;
  signal_strategy: StrategyResult;
  buy_hold_strategy: StrategyResult;
}

export interface AllocationItem {
  ticker: string;
  market_title: string;
  analysis: MarketAnalysis;
  raw_allocation_pct: number;
  final_allocation_pct: number;
  skipped: boolean;
  skip_reason: string | null;
}

export interface AllocationResponse {
  items: AllocationItem[];
  errors: string[];
}
