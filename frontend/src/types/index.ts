export type EnvironmentMode = "paper" | "testnet" | "demo" | "live";
export type RuntimeStatus = "STOPPED" | "RUNNING" | "PAUSED" | "PROTECT_MODE";

export interface StrategyConfig {
  ma_fast: number;
  ma_slow: number;
  rsi_period: number;
  rsi_buy_threshold: number;
  rsi_sell_threshold: number;
  atr_period: number;
  stop_loss_atr_multiple: number;
  take_profit_atr_multiple: number;
}

export interface RiskConfig {
  risk_per_trade: number;
  max_daily_loss: number;
  max_symbol_exposure: number;
  max_total_exposure: number;
  max_strategy_exposure: number;
  max_portfolio_heat: number;
  max_consecutive_losses: number;
  max_slippage: number;
  max_spread: number;
}

export interface ExecutionConfig {
  order_type: "market" | "limit";
  retry_count: number;
}

export interface UIConfig {
  refresh_interval_ms: number;
  chart_points_limit: number;
}

export interface LoggingConfig {
  level: string;
}

export interface StrategyEngineConfig {
  enabled_strategies: string[];
  selection_mode: "vote" | "weighted";
  strategy_weights: Record<string, number>;
  minimum_confidence: number;
}

export interface RegimeConfig {
  enabled: boolean;
  trend_lookback: number;
  trend_strength_threshold: number;
  high_volatility_threshold: number;
  low_volatility_threshold: number;
  confidence_floor: number;
}

export interface SignalPolicyConfig {
  min_signal_score: number;
  ai_weight: number;
  regime_weight: number;
  momentum_weight: number;
  mean_reversion_weight: number;
  breakout_weight: number;
  sell_score_buffer: number;
}

export interface AllocationConfig {
  enabled: boolean;
  base_risk_budget: number;
  min_notional_ratio: number;
  max_notional_ratio: number;
  max_concurrent_positions: number;
  regime_multipliers: Record<string, number>;
}

export interface CostModelConfig {
  enabled: boolean;
  taker_fee_bps: number;
  slippage_spread_weight: number;
  impact_weight: number;
  max_cost_bps: number;
}

export interface OptimizationConfig {
  enable_grid_search: boolean;
  walk_forward_train_bars: number;
  walk_forward_test_bars: number;
  parameter_grid: Record<string, number[]>;
}

export interface ApprovalConfig {
  enabled: boolean;
  require_manual_approval_for_live: boolean;
  require_manual_approval_for_large_orders: boolean;
  auto_approve_small_accounts: boolean;
  auto_approve_below_equity: number;
  approval_min_notional: number;
  approval_timeout_seconds: number;
}

export interface AuthConfig {
  access_token_ttl_minutes: number;
}

export interface NotifierConfig {
  telegram_enabled: boolean;
  feishu_enabled: boolean;
  telegram_bot_token: string;
  telegram_chat_id: string;
  feishu_app_id: string;
  feishu_webhook_url: string;
  feishu_app_secret: string;
  feishu_receive_id: string;
  feishu_receive_id_type: "open_id" | "user_id" | "union_id" | "chat_id" | "email";
}

export interface SimulationConfig {
  starting_balance: number;
  fee_rate: number;
  use_live_market_data: boolean;
  max_slippage_multiplier: number;
  max_spread_multiplier: number;
  reset_account_on_start: boolean;
}

export interface OKXConnectorConfig {
  base_url: string;
  public_ws_url: string;
  demo_public_ws_url: string;
  demo_broker_id: string;
}

export interface BinanceConnectorConfig {
  base_url: string;
  testnet_base_url: string;
  public_ws_url: string;
  testnet_public_ws_url: string;
}

export interface ConnectorsConfig {
  okx: OKXConnectorConfig;
  binance: BinanceConnectorConfig;
}

export interface BusinessConfig {
  symbols: string[];
  timeframe: string;
  strategy: StrategyConfig;
  strategy_engine: StrategyEngineConfig;
  regime: RegimeConfig;
  signal: SignalPolicyConfig;
  allocation: AllocationConfig;
  cost_model: CostModelConfig;
  optimization: OptimizationConfig;
  risk: RiskConfig;
  execution: ExecutionConfig;
}

export interface SystemConfig {
  exchange: "okx" | "binance";
  env: EnvironmentMode;
  market_type: "spot" | "futures";
  simulation: SimulationConfig;
  approval: ApprovalConfig;
  auth: AuthConfig;
  notifier: NotifierConfig;
  ui: UIConfig;
  logging: LoggingConfig;
  connectors: ConnectorsConfig;
}

export interface AppConfig extends BusinessConfig, SystemConfig {}

export interface CredentialStatus {
  api_key_configured: boolean;
  api_key_masked: string;
  secret_configured: boolean;
  secret_masked: string;
  passphrase_configured: boolean;
}

export interface SystemConfigResponse {
  config: SystemConfig;
  live_trading_enabled: boolean;
  secrets_source: string;
  database_hot_reload_supported: boolean;
  okx_credentials: CredentialStatus;
  binance_credentials: CredentialStatus;
}

export interface BotCommandItem {
  command: string;
  description: string;
  requires_binding: boolean;
  control: boolean;
}

export interface BotTarget {
  id: string;
  title: string;
  platform: string;
  chat_type: string;
  username: string;
}

export interface BotPlatformMeta {
  enabled: boolean;
  transport: string;
  worker_active: boolean;
  bound_target_id: string;
  supports_inbound: boolean;
  setup_hint: string;
  recent_targets: BotTarget[];
  callback_path: string;
}

export interface BotMetaResponse {
  commands: BotCommandItem[];
  telegram: BotPlatformMeta;
  feishu: BotPlatformMeta;
}

export interface BotPreviewResponse {
  recognized_command: string;
  message: string;
  authorized: boolean;
  include_keyboard: boolean;
}

export interface AlertRecord {
  level: string;
  category: string;
  message: string;
  created_at: string;
  symbol?: string;
}

export interface StatusResponse {
  status: RuntimeStatus;
  risk_status: "NORMAL" | "PROTECT_MODE" | "HALTED";
  env: EnvironmentMode;
  exchange: string;
  strategy_running: boolean;
  live_enabled: boolean;
  last_heartbeat: string | null;
  latest_alerts: AlertRecord[];
  symbol_states: Array<Record<string, unknown>>;
  paper_account: {
    starting_balance: number;
    last_reset_at: string | null;
  };
}

export interface MarketTicker {
  symbol: string;
  price: number;
  change_percent: number;
  bid: number;
  ask: number;
  spread: number;
  volume: number;
  sparkline: number[];
  last_updated: string;
  market_type: string;
  price_source: string;
}

export interface Position {
  id: number;
  symbol: string;
  side: string;
  strategy_name: string;
  quantity: number;
  avg_price: number;
  market_price: number;
  market_value: number;
  exposure_ratio: number;
  realized_pnl: number;
  unrealized_pnl: number;
  regime: string;
  entry_tag: string;
  stop_loss: number;
  take_profit: number;
  signal_score: number;
  target_weight: number;
  expected_cost_bps: number;
  updated_at: string;
}

export interface Order {
  id: number;
  client_order_id: string;
  signal_id: string;
  strategy_name: string;
  symbol: string;
  side: string;
  order_type: string;
  status: string;
  quantity: number;
  price: number;
  average_fill_price: number;
  expected_price: number;
  risk_checked: boolean;
  risk_reason: string;
  decision_reason: string;
  regime: string;
  signal_score: number;
  target_weight: number;
  expected_cost_bps: number;
  expected_slippage_bps: number;
  env: string;
  is_live: boolean;
  requested_by: string;
  requested_at: string;
  updated_at: string;
  metadata_json?: Record<string, unknown> | null;
}

export interface Trade {
  id: number;
  order_id: number | null;
  client_order_id: string;
  symbol: string;
  side: string;
  strategy_name: string;
  quantity: number;
  price: number;
  fee: number;
  realized_pnl: number;
  regime: string;
  entry_tag: string;
  exit_tag: string;
  signal_score: number;
  expected_cost_bps: number;
  slippage_bps: number;
  fee_bps: number;
  metadata_json?: Record<string, unknown> | null;
  timestamp: string;
}

export interface LogEntry {
  id: number;
  timestamp: string;
  level: string;
  category: string;
  message: string;
  metadata_json?: Record<string, unknown> | null;
}

export interface RiskEvent {
  id: number;
  created_at: string;
  level: string;
  symbol: string;
  strategy_name: string;
  reason: string;
  detail: string;
  blocked: boolean;
  status_after: string;
  metadata_json?: Record<string, unknown> | null;
}

export interface SummaryMetrics {
  equity: number;
  available_balance: number;
  total_pnl: number;
  daily_pnl: number;
  total_return: number;
  daily_return: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  avg_win_loss_ratio: number;
  total_trades: number;
  trades_today: number;
  position_count: number;
  realized_pnl: number;
  unrealized_pnl: number;
  per_symbol_pnl: Record<string, number>;
  strategy_status: RuntimeStatus;
  risk_status: string;
  strategy_breakdown: Record<string, number>;
}

export interface AttributionOverview {
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  total_fees: number;
  open_position_value: number;
  avg_expected_cost_bps: number;
  avg_slippage_bps: number;
}

export interface AttributionBucket {
  name: string;
  pnl: number;
  trade_count: number;
  win_rate?: number | null;
  fees?: number | null;
}

export interface ReasonCount {
  reason: string;
  count: number;
}

export interface StrategyDecisionLogItem {
  id: number;
  created_at: string;
  symbol: string;
  timeframe: string;
  strategy_name: string;
  signal: string;
  final_action: string;
  reason: string;
  regime: string;
  confidence: number;
  signal_score: number;
  buy_score: number;
  sell_score: number;
  target_weight: number;
  desired_notional: number;
  expected_cost_bps: number;
  context_json?: Record<string, unknown> | null;
}

export interface AttributionResponse {
  overview: AttributionOverview;
  by_strategy: AttributionBucket[];
  by_regime: AttributionBucket[];
  top_reasons: ReasonCount[];
  recent_decisions: StrategyDecisionLogItem[];
}

export interface SeriesPoint {
  timestamp: string;
  value: number;
}

export interface DailyPnlPoint {
  date: string;
  pnl: number;
}

export interface LogsResponse {
  logs: LogEntry[];
  risk_events: RiskEvent[];
  alerts: AlertRecord[];
}

export interface BacktestResult {
  id: number;
  created_at: string;
  name: string;
  symbols_csv: string;
  total_return: number;
  win_rate: number;
  max_drawdown: number;
  sharpe: number;
  summary_json?: Record<string, unknown> | null;
  trades_csv_path: string;
  report_json_path: string;
}

export interface OptimizationResult {
  id: number;
  created_at: string;
  name: string;
  symbol: string;
  strategy_name: string;
  score: number;
  parameters_json?: Record<string, unknown> | null;
  walk_forward_json?: Record<string, unknown> | null;
}

export interface ApprovalItem {
  id: number;
  order_id: number | null;
  signal_id: string;
  symbol: string;
  side: string;
  quantity: number;
  expected_price: number;
  notional: number;
  status: string;
  reason: string;
  requested_by: string;
  reviewed_by: string;
  requested_at: string;
  reviewed_at: string | null;
  expires_at: string | null;
  request_payload?: Record<string, unknown> | null;
}

export interface UserProfile {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  username: string;
  role: string;
}

export interface OrderbookSnapshot {
  symbol: string;
  bids: number[][];
  asks: number[][];
  timestamp: string;
}

export interface LatestTradeSnapshot {
  symbol: string;
  price: number;
  quantity: number;
  side: string;
  timestamp: string;
}

export interface ReplayFrame {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  latest_trade?: LatestTradeSnapshot | null;
}

export interface DashboardSocketState {
  status?: StatusResponse;
  metrics?: SummaryMetrics;
  tickers: MarketTicker[];
  positions: Position[];
  recentLogs: LogEntry[];
  alerts: AlertRecord[];
}

export interface PaperAccountResetResponse {
  success: boolean;
  status: RuntimeStatus;
  message: string;
  starting_balance: number;
  equity: number;
  available_balance: number;
}
