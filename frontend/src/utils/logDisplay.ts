import type { AlertRecord, LogEntry, RiskEvent } from "../types";

const levelMap: Record<string, string> = {
  INFO: "信息",
  WARNING: "警告",
  ERROR: "错误",
  CRITICAL: "严重",
  DEBUG: "调试",
};

const categoryMap: Record<string, string> = {
  system: "系统",
  auth: "认证",
  risk: "风控",
  strategy: "策略",
  execution: "执行",
  market: "行情",
  notifier: "通知",
};

const codeMap: Record<string, string> = {
  approved: "已通过",
  "orchestrated": "编排决策",
  "live-order-requires-approval": "实盘订单需要人工审核",
  "large-order-requires-approval": "大额订单需要人工审核",
  "live-trading-disabled": "未开启实盘总开关",
  "exchange-unavailable": "交易所或网络状态异常",
  "state-mismatch": "账户状态不一致",
  "no-enabled-strategy": "未启用任何有效策略",
  "insufficient-data": "行情数据不足",
  "indicator-warmup": "指标预热中",
  "filters-not-met": "策略过滤条件未满足",
  "ma-cross-up-rsi-confirmed": "均线金叉且 RSI 买入条件满足",
  "ma-cross-down-rsi-confirmed": "均线死叉且 RSI 卖出条件满足",
  "range-intact": "价格仍在区间内，未形成突破",
  "breakout-up": "向上突破成立",
  "breakout-down": "向下突破成立",
  "signal-score-too-low": "信号综合得分不足",
  "cost-too-high": "预估执行成本过高",
  "allocation-blocked": "仓位分配器未分配有效仓位",
  "regime-conflict": "当前市场状态与信号方向冲突",
  "spread-too-wide": "点差过大",
  "slippage-too-high": "滑点过高",
  "daily-loss-limit-hit": "触发日亏损限制",
  "consecutive-loss-limit-hit": "触发连续亏损限制",
  "martingale-blocked": "禁止逆势加仓",
  "no-position-to-sell": "无可卖出现货持仓",
  "symbol-exposure-limit-hit": "单交易对敞口超限",
  "total-exposure-limit-hit": "组合总敞口超限",
  "strategy-exposure-limit-hit": "策略敞口超限",
  "portfolio-heat-limit-hit": "组合热度超限",
  "zero-quantity-after-risk-sizing": "风险计算后下单数量为 0",
  "stop-loss-triggered": "触发止损",
  "take-profit-triggered": "触发止盈",
  "spot-long-only-waits-for-buy": "现货模式下无持仓时忽略卖出信号",
  "already-in-position": "已有持仓，忽略重复买入",
  "strategy-status-protect_mode": "当前处于保护模式，禁止继续交易",
  "strategy-status-stopped": "策略已停止，禁止继续交易",
  "risk-status-protect_mode": "风控处于保护模式，禁止继续交易",
  "ai=neutral": "AI 偏向中性",
  "ai=bullish": "AI 偏向看多",
  "ai=bearish": "AI 偏向看空",
};

function translateCodeFragment(value: string): string {
  return codeMap[value] ?? value;
}

function formatAiBias(value: unknown): string | null {
  if (typeof value !== "string" || !value) {
    return null;
  }
  return translateCodeFragment(`ai=${value.toLowerCase()}`);
}

export function formatLogLevel(level: string): string {
  return levelMap[level] ?? level;
}

export function formatLogCategory(category: string): string {
  return categoryMap[category] ?? category;
}

export function formatReasonText(reason: string, context?: unknown): string {
  if (!reason) {
    return "--";
  }

  if (reason.startsWith("manual-rejection:")) {
    const comment = reason.slice("manual-rejection:".length).trim();
    return comment ? `人工驳回：${comment}` : "人工驳回";
  }

  if (reason.startsWith("adapter-error:")) {
    return `交易所适配器报错：${reason.slice("adapter-error:".length).trim()}`;
  }

  if (reason.startsWith("orchestrated:")) {
    const orchestratedBody = reason.slice("orchestrated:".length);
    const parts = orchestratedBody
      .split("|")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => translateCodeFragment(part));
    return parts.length > 0 ? `编排决策：${parts.join("，")}` : "编排决策";
  }

  if (reason.includes("|")) {
    const parts = reason
      .split("|")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => translateCodeFragment(part));
    return parts.join("，");
  }

  const translated = translateCodeFragment(reason);
  if (!context || typeof context !== "object") {
    return translated;
  }

  const aiBias = formatAiBias((context as { ai_bias?: unknown }).ai_bias);
  const selectedStrategy = (context as { selected_strategy?: unknown }).selected_strategy;
  const suffix: string[] = [];
  if (aiBias && aiBias !== translated) {
    suffix.push(aiBias);
  }
  if (typeof selectedStrategy === "string" && selectedStrategy) {
    suffix.push(`策略 ${selectedStrategy}`);
  }

  return suffix.length > 0 ? `${translated}，${suffix.join("，")}` : translated;
}

export function formatLogMessage(message: string): string {
  if (!message) {
    return "--";
  }

  const directMap: Record<string, string> = {
    "Application startup complete": "应用启动完成",
    "Application shutdown complete": "应用关闭完成",
    "Seeded default admin user": "已初始化默认管理员账号",
    "Balance refresh failed": "账户余额刷新失败",
    "Market data refresh failed": "行情数据刷新失败",
    "Notifier delivery failed": "通知发送失败",
  };

  if (directMap[message]) {
    return directMap[message];
  }

  let matched = message.match(/^strategy decision\s+(.+?)\s+(BUY|SELL|HOLD)\s+strategy=(.+?)\s+reason=(.+)$/i);
  if (matched) {
    const [, symbol, side, strategyName, reason] = matched;
    return `策略决策：${symbol} ${side}，策略 ${strategyName}，原因：${formatReasonText(reason)}`;
  }

  matched = message.match(/^strategy protective exit\s+(.+?)\s+(BUY|SELL)\s+reason=(.+)$/i);
  if (matched) {
    const [, symbol, side, reason] = matched;
    return `策略保护性离场：${symbol} ${side}，原因：${formatReasonText(reason)}`;
  }

  matched = message.match(/^Strategy loop failed for\s+(.+)$/i);
  if (matched) {
    return `策略轮询执行失败：${matched[1]}`;
  }

  matched = message.match(/^Market stream disconnected:\s*(.+)$/i);
  if (matched) {
    return `行情流连接断开：${matched[1]}`;
  }

  matched = message.match(/^order filled\s+(.+?)\s+(BUY|SELL)\s+qty=(\S+)\s+price=(\S+)\s+strategy=(.+)$/i);
  if (matched) {
    const [, symbol, side, quantity, price, strategyName] = matched;
    return `订单已成交：${symbol} ${side}，数量 ${quantity}，成交价 ${price}，策略 ${strategyName}`;
  }

  matched = message.match(/^(.+?):\s+([a-z0-9\-_:]+)$/i);
  if (matched) {
    const [, prefix, reason] = matched;
    if (prefix.toUpperCase() !== prefix) {
      return `${prefix}：${formatReasonText(reason)}`;
    }
  }

  return message;
}

export function formatRiskEventDetail(detail: string): string {
  if (!detail) {
    return "--";
  }

  return detail
    .replace(/^spread=(\S+) threshold=(\S+)$/i, "当前点差 $1，超过阈值 $2")
    .replace(/^slippage=(\S+) threshold=(\S+)$/i, "当前滑点 $1，超过阈值 $2")
    .replace(/^consecutive losses >= (\d+)$/i, "连续亏损次数已达到上限 $1")
    .replace(/^next exposure (\S+) exceeds threshold$/i, "该交易对下一步风险敞口 $1 已超过限制")
    .replace(/^next total exposure (\S+) exceeds threshold$/i, "组合总风险敞口 $1 已超过限制")
    .replace(/^next strategy exposure (\S+) exceeds threshold$/i, "当前策略风险敞口 $1 已超过限制")
    .replace(/^portfolio heat (\S+) exceeds threshold (\S+)$/i, "组合热度 $1 已超过阈值 $2")
    .replace(/^daily_pnl=(\S+), max_daily_loss=(\S+)$/i, "当日盈亏 $1，已触发最大日亏损限制 $2");
}

export function formatAlertMessage(alert: AlertRecord): string {
  return formatLogMessage(alert.message);
}

export function formatLogEntryMessage(log: LogEntry): string {
  return formatLogMessage(log.message);
}

export function formatRiskEventReason(event: RiskEvent): string {
  return formatReasonText(event.reason);
}

export function formatRiskEventMessage(event: RiskEvent): string {
  return formatRiskEventDetail(event.detail);
}