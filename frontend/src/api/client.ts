import type {
  ApprovalItem,
  AttributionResponse,
  BacktestResult,
  BotMetaResponse,
  BotPreviewResponse,
  BusinessConfig,
  DailyPnlPoint,
  LatestTradeSnapshot,
  LoginResponse,
  LogsResponse,
  MarketTicker,
  OptimizationResult,
  Order,
  PaperAccountResetResponse,
  OrderbookSnapshot,
  Position,
  ReplayFrame,
  SeriesPoint,
  StatusResponse,
  SummaryMetrics,
  SystemConfig,
  SystemConfigResponse,
  Trade,
  UserProfile,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const TOKEN_KEY = "quant-access-token";
const USERNAME_KEY = "quant-username";
const ROLE_KEY = "quant-role";

export function getAuthToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setAuthSession(session: LoginResponse): void {
  localStorage.setItem(TOKEN_KEY, session.access_token);
  localStorage.setItem(USERNAME_KEY, session.username);
  localStorage.setItem(ROLE_KEY, session.role);
}

export function clearAuthSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function getStoredIdentity(): { username: string; role: string } | null {
  const username = localStorage.getItem(USERNAME_KEY);
  const role = localStorage.getItem(ROLE_KEY);
  return username && role ? { username, role } : null;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (response.status === 401) {
    clearAuthSession();
  }

  if (!response.ok) {
    const raw = await response.text();
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: string };
      if (parsed.detail) {
        detail = parsed.detail;
      }
    } catch {
      // Keep raw text when the response body is not JSON.
    }
    throw new Error(detail || `请求失败：${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) =>
    request<LoginResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  getMe: () => request<UserProfile>("/api/auth/me"),
  getHealth: () => request<{ ok: boolean; env: string; exchange: string; database: string }>("/api/health"),
  getConfig: () => request<BusinessConfig>("/api/config"),
  updateConfig: (config: BusinessConfig, applyImmediately: boolean) =>
    request<{ success: boolean; config: BusinessConfig }>("/api/config", {
      method: "PUT",
      body: JSON.stringify({ config, apply_immediately: applyImmediately, changed_by: "frontend" }),
    }),
  getSystemConfig: () => request<SystemConfigResponse>("/api/system-config"),
  updateSystemConfig: (config: SystemConfig, applyImmediately: boolean) =>
    request<{ success: boolean; config: SystemConfig }>("/api/system-config", {
      method: "PUT",
      body: JSON.stringify({ config, apply_immediately: applyImmediately, changed_by: "frontend" }),
    }),
  getBotMeta: () => request<BotMetaResponse>("/api/bot/meta"),
  syncTelegramBot: () => request<{ processed_updates: number; recent_targets: Array<Record<string, string>> }>("/api/bot/telegram/sync", {
    method: "POST",
  }),
  bindTelegramChat: (chatId: string) =>
    request<{ success: boolean; chat_id: string }>("/api/bot/telegram/bind", {
      method: "POST",
      body: JSON.stringify({ chat_id: chatId }),
    }),
  bindFeishuChat: (receiveId: string, receiveIdType: string) =>
    request<{ success: boolean; receive_id: string; receive_id_type: string }>("/api/bot/feishu/bind", {
      method: "POST",
      body: JSON.stringify({ receive_id: receiveId, receive_id_type: receiveIdType }),
    }),
  previewBotCommand: (platform: "telegram" | "feishu", command: string, sourceId: string) =>
    request<BotPreviewResponse>("/api/bot/command-preview", {
      method: "POST",
      body: JSON.stringify({ platform, command, source_id: sourceId }),
    }),
  getStatus: () => request<StatusResponse>("/api/status"),
  controlStrategy: (action: "start" | "pause" | "stop" | "protect") =>
    request<{ success: boolean; status: string; message: string }>(`/api/strategy/${action}`, { method: "POST" }),
  resetPaperAccount: (startingBalance?: number) =>
    request<PaperAccountResetResponse>("/api/strategy/paper-account/reset", {
      method: "POST",
      body: JSON.stringify({ starting_balance: startingBalance }),
    }),
  getSummary: () => request<SummaryMetrics>("/api/metrics/summary"),
  getAttribution: () => request<AttributionResponse>("/api/metrics/attribution"),
  getEquityCurve: () => request<{ points: SeriesPoint[] }>("/api/metrics/equity-curve"),
  getDrawdown: () => request<{ points: SeriesPoint[] }>("/api/metrics/drawdown"),
  getDailyPnl: () => request<{ points: DailyPnlPoint[] }>("/api/metrics/daily-pnl"),
  getPositions: () => request<Position[]>("/api/positions"),
  getOrders: () => request<Order[]>("/api/orders"),
  getTrades: () => request<Trade[]>("/api/trades"),
  getLogs: () => request<LogsResponse>("/api/logs"),
  getTickers: () => request<MarketTicker[]>("/api/market/tickers"),
  getCandles: (symbol: string) =>
    request<{ symbol: string; candles: Array<Record<string, number | string>> }>(`/api/market/candles/${symbol}`),
  getOrderbook: (symbol: string) => request<OrderbookSnapshot>(`/api/market/orderbook/${symbol}`),
  getRecentTrades: (symbol: string) => request<{ symbol: string; trades: LatestTradeSnapshot[] }>(`/api/market/trades/${symbol}`),
  getReplayFrames: (symbol: string) => request<{ symbol: string; frames: ReplayFrame[] }>(`/api/market/replay/${symbol}`),
  runBacktest: (name: string) =>
    request<{ success: boolean; result: BacktestResult }>("/api/backtest/run", {
      method: "POST",
      body: JSON.stringify({ name, csv_paths: [], symbols: [], use_current_config: true }),
    }),
  runOptimization: (name: string, symbol: string, strategyName: string) =>
    request<{ success: boolean; result: OptimizationResult }>("/api/backtest/optimize", {
      method: "POST",
      body: JSON.stringify({ name, symbol, strategy_name: strategyName }),
    }),
  getBacktestResults: () => request<BacktestResult[]>("/api/backtest/results"),
  getOptimizationResults: () => request<OptimizationResult[]>("/api/backtest/optimizations"),
  getApprovals: () => request<ApprovalItem[]>("/api/approvals"),
  approveOrder: (approvalId: number, comment = "") =>
    request<Order>(`/api/approvals/${approvalId}/approve`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),
  rejectOrder: (approvalId: number, comment = "") =>
    request<ApprovalItem>(`/api/approvals/${approvalId}/reject`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),
  downloadMetricsExport: () => `${API_BASE_URL}/api/metrics/export`,
};

export function getWebSocketUrl(path: string): string {
  const token = getAuthToken();
  if (API_BASE_URL) {
    const baseUrl = new URL(API_BASE_URL);
    const wsUrl = new URL(path, baseUrl);
    wsUrl.protocol = baseUrl.protocol === "https:" ? "wss:" : "ws:";
    wsUrl.search = token ? `token=${encodeURIComponent(token)}` : "";
    return wsUrl.toString();
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${protocol}//${window.location.host}${path}${query}`;
}
