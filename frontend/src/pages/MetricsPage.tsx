import { useEffect, useMemo, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { api } from "../api/client";
import { DrawdownChart } from "../components/DrawdownChart";
import { EquityChart } from "../components/EquityChart";
import { PnlChart } from "../components/PnlChart";
import { StatCard } from "../components/StatCard";
import { useConfig } from "../hooks/useConfig";
import type { AttributionResponse, BacktestResult, DailyPnlPoint, OptimizationResult, SeriesPoint, SummaryMetrics } from "../types";
import { formatRuntimeValue } from "../utils/display";
import { formatReasonText } from "../utils/logDisplay";

const PIE_COLORS = ["#2dd4bf", "#38bdf8", "#f59e0b", "#f97316", "#fb7185", "#a78bfa"];

export function MetricsPage() {
  const { config } = useConfig();
  const [summary, setSummary] = useState<SummaryMetrics | null>(null);
  const [equityCurve, setEquityCurve] = useState<SeriesPoint[]>([]);
  const [drawdownCurve, setDrawdownCurve] = useState<SeriesPoint[]>([]);
  const [dailyPnl, setDailyPnl] = useState<DailyPnlPoint[]>([]);
  const [backtests, setBacktests] = useState<BacktestResult[]>([]);
  const [optimizations, setOptimizations] = useState<OptimizationResult[]>([]);
  const [attribution, setAttribution] = useState<AttributionResponse | null>(null);
  const [runningBacktest, setRunningBacktest] = useState(false);
  const [runningOptimize, setRunningOptimize] = useState(false);
  const [optimizationSymbol, setOptimizationSymbol] = useState("");

  const load = async () => {
    const [summaryData, attributionData, equityData, drawdownData, dailyData, backtestData, optimizationData] = await Promise.all([
      api.getSummary(),
      api.getAttribution(),
      api.getEquityCurve(),
      api.getDrawdown(),
      api.getDailyPnl(),
      api.getBacktestResults(),
      api.getOptimizationResults(),
    ]);
    setSummary(summaryData);
    setAttribution(attributionData);
    setEquityCurve(equityData.points);
    setDrawdownCurve(drawdownData.points);
    setDailyPnl(dailyData.points);
    setBacktests(backtestData);
    setOptimizations(optimizationData);
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const symbols = config?.symbols ?? [];
    if (!symbols.length) {
      return;
    }
    if (!optimizationSymbol || !symbols.includes(optimizationSymbol)) {
      setOptimizationSymbol(symbols[0]);
    }
  }, [config, optimizationSymbol]);

  const pieData = useMemo(
    () =>
      Object.entries(summary?.per_symbol_pnl ?? {}).map(([name, value]) => ({
        name,
        value,
      })),
    [summary],
  );

  const runBacktest = async () => {
    setRunningBacktest(true);
    try {
      await api.runBacktest(`backtest_${Date.now()}`);
      await load();
    } finally {
      setRunningBacktest(false);
    }
  };

  const runOptimization = async () => {
    if (!optimizationSymbol) {
      return;
    }
    setRunningOptimize(true);
    try {
      await api.runOptimization(`opt_${Date.now()}`, optimizationSymbol, "ma_rsi");
      await load();
    } finally {
      setRunningOptimize(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-white">收益统计与研究</h1>
          <p className="mt-1 text-sm text-slate-400">查看净值、回撤、币种收益拆分，并运行回测与参数寻优。</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <select
            className="rounded-full border border-white/10 bg-slate-950/80 px-4 py-2 text-white"
            onChange={(event) => setOptimizationSymbol(event.target.value)}
            value={optimizationSymbol}
          >
            {(config?.symbols ?? []).map((symbol) => (
              <option key={symbol} value={symbol}>
                {symbol}
              </option>
            ))}
          </select>
          <a
            className="rounded-full border border-white/10 px-4 py-2 text-sm text-white transition hover:bg-white/10"
            href={api.downloadMetricsExport()}
            rel="noreferrer"
            target="_blank"
          >
            导出收益报表
          </a>
          <button className="rounded-full bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950" onClick={() => void runBacktest()}>
            {runningBacktest ? "回测运行中..." : "运行示例回测"}
          </button>
          <button className="rounded-full border border-cyan-300/30 px-4 py-2 text-sm text-cyan-200" onClick={() => void runOptimization()}>
            {runningOptimize ? "寻优中..." : "运行参数寻优"}
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="当前总资产" value={summary ? summary.equity.toFixed(2) : "--"} />
        <StatCard label="累计收益" value={summary ? summary.total_pnl.toFixed(2) : "--"} accent={summary && summary.total_pnl >= 0 ? "success" : "danger"} />
        <StatCard label="总手续费" value={attribution ? attribution.overview.total_fees.toFixed(2) : "--"} accent="danger" />
        <StatCard label="平均预估成本" value={attribution ? `${attribution.overview.avg_expected_cost_bps.toFixed(2)} bps` : "--"} />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <EquityChart points={equityCurve} />
        <DrawdownChart points={drawdownCurve} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <PnlChart points={dailyPnl} />
        <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
          <h3 className="text-lg font-semibold text-white">按币种收益拆分</h3>
          <div className="mt-4 h-72">
            {pieData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={100}>
                    {pieData.map((entry, index) => (
                      <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-slate-400">暂无币种收益拆分。</p>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel xl:col-span-1">
          <h3 className="text-lg font-semibold text-white">归因概览</h3>
          <div className="mt-4 grid gap-3 text-sm text-slate-300">
            <div className="rounded-2xl border border-white/5 bg-white/5 p-4">已实现收益：{attribution ? attribution.overview.total_realized_pnl.toFixed(2) : "--"}</div>
            <div className="rounded-2xl border border-white/5 bg-white/5 p-4">未实现收益：{attribution ? attribution.overview.total_unrealized_pnl.toFixed(2) : "--"}</div>
            <div className="rounded-2xl border border-white/5 bg-white/5 p-4">持仓市值：{attribution ? attribution.overview.open_position_value.toFixed(2) : "--"}</div>
            <div className="rounded-2xl border border-white/5 bg-white/5 p-4">平均滑点：{attribution ? `${attribution.overview.avg_slippage_bps.toFixed(2)} bps` : "--"}</div>
          </div>
        </div>

        <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel xl:col-span-1">
          <div className="border-b border-white/10 px-5 py-4">
            <h3 className="text-lg font-semibold text-white">按策略归因</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10 text-sm">
              <thead className="bg-white/5 text-left text-slate-300">
                <tr>
                  {['策略', '收益', '交易数', '胜率', '手续费'].map((label) => (
                    <th key={label} className="px-4 py-3 font-medium">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-100">
                {(attribution?.by_strategy ?? []).map((item) => (
                  <tr key={item.name}>
                    <td className="px-4 py-3">{item.name}</td>
                    <td className={`px-4 py-3 ${item.pnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>{item.pnl.toFixed(2)}</td>
                    <td className="px-4 py-3">{item.trade_count}</td>
                    <td className="px-4 py-3">{item.win_rate != null ? `${(item.win_rate * 100).toFixed(1)}%` : '--'}</td>
                    <td className="px-4 py-3">{item.fees != null ? item.fees.toFixed(2) : '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel xl:col-span-1">
          <div className="border-b border-white/10 px-5 py-4">
            <h3 className="text-lg font-semibold text-white">按市场状态归因</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10 text-sm">
              <thead className="bg-white/5 text-left text-slate-300">
                <tr>
                  {['状态', '收益', '交易数'].map((label) => (
                    <th key={label} className="px-4 py-3 font-medium">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-100">
                {(attribution?.by_regime ?? []).map((item) => (
                  <tr key={item.name}>
                    <td className="px-4 py-3">{formatRuntimeValue(item.name)}</td>
                    <td className={`px-4 py-3 ${item.pnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>{item.pnl.toFixed(2)}</td>
                    <td className="px-4 py-3">{item.trade_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel">
          <div className="border-b border-white/10 px-5 py-4">
            <h3 className="text-lg font-semibold text-white">高频决策原因</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10 text-sm">
              <thead className="bg-white/5 text-left text-slate-300">
                <tr>
                  {['原因', '次数'].map((label) => (
                    <th key={label} className="px-4 py-3 font-medium">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-100">
                {(attribution?.top_reasons ?? []).map((item) => (
                  <tr key={item.reason}>
                    <td className="px-4 py-3 text-slate-300">{formatReasonText(item.reason)}</td>
                    <td className="px-4 py-3">{item.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel">
          <div className="border-b border-white/10 px-5 py-4">
            <h3 className="text-lg font-semibold text-white">最近决策日志</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10 text-sm">
              <thead className="bg-white/5 text-left text-slate-300">
                <tr>
                  {['时间', '交易对', '信号', '状态', '分数', '原因'].map((label) => (
                    <th key={label} className="px-4 py-3 font-medium">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-100">
                {(attribution?.recent_decisions ?? []).map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-3 text-xs text-slate-400">{new Date(item.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3">{item.symbol}</td>
                    <td className="px-4 py-3">{formatRuntimeValue(item.final_action)}</td>
                    <td className="px-4 py-3">{formatRuntimeValue(item.regime)}</td>
                    <td className="px-4 py-3">{item.signal_score.toFixed(3)}</td>
                    <td className="px-4 py-3 text-slate-300">{formatReasonText(item.reason, item.context_json)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel">
          <div className="border-b border-white/10 px-5 py-4">
            <h3 className="text-lg font-semibold text-white">最近回测结果</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10 text-sm">
              <thead className="bg-white/5 text-left text-slate-300">
                <tr>
                  {["名称", "交易对", "总收益率", "胜率", "最大回撤", "Sharpe"].map((label) => (
                    <th key={label} className="px-4 py-3 font-medium">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-100">
                {backtests.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-3">{item.name}</td>
                    <td className="px-4 py-3">{item.symbols_csv}</td>
                    <td className="px-4 py-3">{(item.total_return * 100).toFixed(2)}%</td>
                    <td className="px-4 py-3">{(item.win_rate * 100).toFixed(2)}%</td>
                    <td className="px-4 py-3">{(item.max_drawdown * 100).toFixed(2)}%</td>
                    <td className="px-4 py-3">{item.sharpe.toFixed(2)}</td>
                  </tr>
                ))}
                {backtests.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-slate-400" colSpan={6}>
                      还没有回测结果。
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>

        <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel">
          <div className="border-b border-white/10 px-5 py-4">
            <h3 className="text-lg font-semibold text-white">参数寻优与 Walk-Forward</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10 text-sm">
              <thead className="bg-white/5 text-left text-slate-300">
                <tr>
                  {["名称", "交易对", "策略", "评分", "最佳参数"].map((label) => (
                    <th key={label} className="px-4 py-3 font-medium">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-100">
                {optimizations.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-3">{item.name}</td>
                    <td className="px-4 py-3">{item.symbol}</td>
                    <td className="px-4 py-3">{item.strategy_name}</td>
                    <td className="px-4 py-3">{item.score.toFixed(4)}</td>
                    <td className="px-4 py-3 text-xs text-slate-300">{JSON.stringify(item.parameters_json ?? {})}</td>
                  </tr>
                ))}
                {optimizations.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-slate-400" colSpan={5}>
                      还没有参数寻优结果。
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
