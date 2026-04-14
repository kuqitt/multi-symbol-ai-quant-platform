import { useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import { DecisionDetailDrawer } from "../components/DecisionDetailDrawer";
import { DrawdownChart } from "../components/DrawdownChart";
import { EquityChart } from "../components/EquityChart";
import { PnlChart } from "../components/PnlChart";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import type { AttributionResponse, DailyPnlPoint, DashboardSocketState, SeriesPoint, SystemConfig } from "../types";
import { getConnectionBadgeValue, getDashboardControls, type DashboardControlAction } from "../utils/dashboardControls";
import { formatBooleanLabel, formatRuntimeValue } from "../utils/display";
import { formatAlertMessage, formatReasonText } from "../utils/logDisplay";

interface DashboardPageProps {
  dashboard: DashboardSocketState & { connected: boolean };
}

interface SymbolRuntimeView {
  symbol: string;
  phase?: string;
  market_regime?: string;
  regime_confidence?: number;
  signal_score?: number;
  target_weight?: number;
  expected_cost_bps?: number;
  last_signal?: string;
  last_reason?: string;
  last_reason_context?: Record<string, unknown>;
  last_action?: string;
  blocked_reason?: string;
  position_quantity?: number;
  updated_at?: string;
}

export function DashboardPage({ dashboard }: DashboardPageProps) {
  const [equityCurve, setEquityCurve] = useState<SeriesPoint[]>([]);
  const [drawdownCurve, setDrawdownCurve] = useState<SeriesPoint[]>([]);
  const [dailyPnl, setDailyPnl] = useState<DailyPnlPoint[]>([]);
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null);
  const [attribution, setAttribution] = useState<AttributionResponse | null>(null);
  const [actionPending, setActionPending] = useState<DashboardControlAction | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [selectedDecision, setSelectedDecision] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let active = true;
    void Promise.all([api.getEquityCurve(), api.getDrawdown(), api.getDailyPnl(), api.getAttribution()]).then(([equity, drawdown, daily, attributionData]) => {
      if (!active) {
        return;
      }
      setEquityCurve(equity.points);
      setDrawdownCurve(drawdown.points);
      setDailyPnl(daily.points);
      setAttribution(attributionData);
    });
    void api
      .getSystemConfig()
      .then((response) => {
        if (active) {
          setSystemConfig(response.config);
        }
      })
      .catch(() => undefined);

    return () => {
      active = false;
    };
  }, []);

  const metrics = dashboard.metrics;
  const status = dashboard.status;
  const runnerStates = ((status?.symbol_states ?? []) as unknown as SymbolRuntimeView[]).slice().sort((left, right) => {
    return (right.updated_at ?? "").localeCompare(left.updated_at ?? "");
  });

  const cards = useMemo(
    () => [
      { label: "当前总资产", value: metrics ? metrics.equity.toFixed(2) : "--", accent: "default" as const },
      {
        label: "累计收益",
        value: metrics ? metrics.total_pnl.toFixed(2) : "--",
        accent: metrics && metrics.total_pnl >= 0 ? ("success" as const) : ("danger" as const),
      },
      {
        label: "当日收益",
        value: metrics ? metrics.daily_pnl.toFixed(2) : "--",
        accent: metrics && metrics.daily_pnl >= 0 ? ("success" as const) : ("danger" as const),
      },
      {
        label: "最大回撤",
        value: metrics ? `${(metrics.max_drawdown * 100).toFixed(2)}%` : "--",
        accent: "danger" as const,
      },
    ],
    [metrics],
  );

  const controls = useMemo(() => getDashboardControls(status), [status]);

  const runAction = async (action: DashboardControlAction) => {
    setActionPending(action);
    setActionMessage(null);
    try {
      if (action === "reset-paper") {
        const result = await api.resetPaperAccount(systemConfig?.simulation.starting_balance);
        setActionMessage(`模拟账户已重置为 ${result.starting_balance.toFixed(2)} USDT。`);
        return;
      }
      const result = await api.controlStrategy(action);
      setActionMessage(result.message);
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : "操作失败，请检查后端服务状态。");
    } finally {
      setActionPending(null);
    }
  };

  const actionClassMap = {
    primary: "bg-emerald-400 text-slate-950 hover:bg-emerald-300 disabled:bg-slate-700 disabled:text-slate-300",
    secondary: "border border-white/15 text-white hover:bg-white/10 disabled:border-white/10 disabled:text-slate-500",
    danger: "bg-rose-500 text-white hover:bg-rose-400 disabled:bg-slate-700 disabled:text-slate-300",
  };

  const approvalSummary = systemConfig
    ? systemConfig.approval.enabled
      ? systemConfig.approval.auto_approve_small_accounts
        ? `开启，小资金 ${systemConfig.approval.auto_approve_below_equity.toFixed(0)} USDT 以下自动放行`
        : "开启，所有命中规则的订单进入审核"
      : "关闭，订单不进入人工审核"
    : "--";

  const paperDataSummary = systemConfig
    ? systemConfig.env === "paper"
      ? formatBooleanLabel(systemConfig.simulation.use_live_market_data)
      : "当前非模拟盘"
    : "--";

  return (
    <div className="space-y-6">
      <div className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(45,212,191,0.25),_rgba(15,23,42,0.85)_45%,_rgba(15,23,42,1)_75%)] p-6 shadow-panel">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-200">实时交易总控台</p>
            <h1 className="mt-3 text-4xl font-semibold text-white">多币种 AI / 量化自动交易平台</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-200">
              当前版本优先保障模拟盘和测试网可运行。策略的每次开平仓都要先经过风控审核，未显式开启实盘开关时会被后端强制拦截。
            </p>
            {dashboard.connected ? null : (
              <p className="mt-3 max-w-3xl rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                当前与后端实时通道断开，页面展示的是最近一次缓存状态，按钮操作仍会直接请求后端 API。
              </p>
            )}
            {actionMessage ? <p className="mt-3 text-sm text-cyan-100">{actionMessage}</p> : null}
          </div>
          <div className="flex flex-wrap gap-3">
            {controls.map((control) => (
              <button
                key={control.action}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed ${actionClassMap[control.tone]}`}
                disabled={control.disabled || actionPending !== null}
                onClick={() => void runAction(control.action)}
              >
                {actionPending === control.action ? "执行中..." : control.label}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <StatusBadge value={status?.env ?? "paper"} />
          <StatusBadge value={status?.status ?? "STOPPED"} />
          <StatusBadge value={status?.risk_status ?? "NORMAL"} />
          <StatusBadge value={getConnectionBadgeValue(dashboard.connected)} />
        </div>
      </div>

      <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-white">最近决策流</h3>
          <span className="text-sm text-slate-400">展示最近一次已落库的策略决策与原因</span>
        </div>
        <div className="mt-4 space-y-3">
          {(attribution?.recent_decisions ?? []).slice(0, 8).map((item) => (
            <button
              key={item.id}
              className="flex w-full items-start justify-between gap-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left transition hover:bg-white/10"
              onClick={() => setSelectedDecision(item as unknown as Record<string, unknown>)}
              type="button"
            >
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-white">{item.symbol}</span>
                  <StatusBadge value={item.final_action} />
                  <StatusBadge value={item.regime} />
                </div>
                <p className="mt-2 text-sm text-slate-300">{formatReasonText(item.reason, item.context_json)}</p>
              </div>
              <div className="text-right text-xs text-slate-400">
                <div>分数 {item.signal_score.toFixed(3)}</div>
                <div className="mt-1">{new Date(item.created_at).toLocaleString()}</div>
              </div>
            </button>
          ))}
          {(attribution?.recent_decisions ?? []).length === 0 ? <p className="text-sm text-slate-400">当前还没有已落库的最新决策。</p> : null}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <StatCard key={card.label} accent={card.accent} label={card.label} value={card.value} />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <div className="grid gap-6">
          <EquityChart points={equityCurve} />
          <DrawdownChart points={drawdownCurve} />
        </div>
        <div className="grid gap-6">
          <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
            <h3 className="text-lg font-semibold text-white">系统状态</h3>
            <div className="mt-4 grid gap-3 text-sm text-slate-300">
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">环境模式：{status ? formatRuntimeValue(status.env) : "--"}</div>
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">交易所：{status?.exchange ?? "--"}</div>
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">市场类型：{systemConfig ? formatRuntimeValue(systemConfig.market_type) : "--"}</div>
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">行情连接：{formatRuntimeValue(getConnectionBadgeValue(dashboard.connected))}</div>
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">策略运行：{formatBooleanLabel(Boolean(status?.strategy_running))}</div>
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">人工审核：{approvalSummary}</div>
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">模拟盘实时行情：{paperDataSummary}</div>
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">实盘开关：{formatBooleanLabel(Boolean(status?.live_enabled))}</div>
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">
                模拟账户初始资金：{status?.paper_account?.starting_balance?.toFixed?.(2) ?? "--"} USDT
              </div>
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">
                最近重置：{status?.paper_account?.last_reset_at ? new Date(status.paper_account.last_reset_at).toLocaleString() : "未重置"}
              </div>
            </div>
          </div>
          <PnlChart points={dailyPnl} />
        </div>
      </div>

      <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-white">策略跑盘状态</h3>
          <span className="text-sm text-slate-400">每个交易对都会显示最近一次动作与阻塞原因</span>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-slate-300">
              <tr>
                {["交易对", "阶段", "市场状态", "信号分数", "目标仓位", "预估成本", "最近信号", "最近动作", "原因", "阻塞原因", "持仓数量", "更新时间"].map((label) => (
                  <th key={label} className="px-4 py-3 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-100">
              {runnerStates.map((item) => (
                <tr key={item.symbol}>
                  <td className="px-4 py-3">{item.symbol}</td>
                  <td className="px-4 py-3">{item.phase ?? "--"}</td>
                  <td className="px-4 py-3">{item.market_regime ? formatRuntimeValue(item.market_regime) : "--"}</td>
                  <td className="px-4 py-3">{typeof item.signal_score === "number" ? item.signal_score.toFixed(3) : "--"}</td>
                  <td className="px-4 py-3">{typeof item.target_weight === "number" ? `${(item.target_weight * 100).toFixed(1)}%` : "--"}</td>
                  <td className="px-4 py-3">{typeof item.expected_cost_bps === "number" ? `${item.expected_cost_bps.toFixed(2)} bps` : "--"}</td>
                  <td className="px-4 py-3">{item.last_signal ? formatRuntimeValue(item.last_signal) : "--"}</td>
                  <td className="px-4 py-3">{item.last_action ?? "--"}</td>
                  <td className="px-4 py-3 text-slate-300">{item.last_reason ? formatReasonText(item.last_reason, item.last_reason_context) : "--"}</td>
                  <td className="px-4 py-3 text-amber-200">{item.blocked_reason ? formatReasonText(item.blocked_reason) : "--"}</td>
                  <td className="px-4 py-3">{typeof item.position_quantity === "number" ? item.position_quantity.toFixed(6) : "--"}</td>
                  <td className="px-4 py-3 text-xs text-slate-400">{item.updated_at ? new Date(item.updated_at).toLocaleString() : "--"}</td>
                </tr>
              ))}
              {runnerStates.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-slate-400" colSpan={12}>
                    当前还没有策略运行轨迹。启动策略后，这里会显示每个交易对最近一次为什么买、为什么不买。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
        <h3 className="text-lg font-semibold text-white">最近告警</h3>
        <div className="mt-4 space-y-3">
          {dashboard.alerts.length === 0 ? <p className="text-sm text-slate-400">当前没有告警。</p> : null}
          {dashboard.alerts.map((alert, index) => (
            <div key={`${alert.created_at}-${index}`} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <StatusBadge value={alert.level} />
                  <span className="text-sm text-slate-200">{formatAlertMessage(alert)}</span>
                </div>
                <span className="text-xs text-slate-400">{new Date(alert.created_at).toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <DecisionDetailDrawer
        open={Boolean(selectedDecision)}
        title={selectedDecision ? `${String(selectedDecision.symbol ?? "--")} 决策详情` : ""}
        subtitle={selectedDecision ? `${formatRuntimeValue(String(selectedDecision.final_action ?? "--"))} · ${formatRuntimeValue(String(selectedDecision.regime ?? "unknown"))}` : undefined}
        data={selectedDecision}
        onClose={() => setSelectedDecision(null)}
      />
    </div>
  );
}
