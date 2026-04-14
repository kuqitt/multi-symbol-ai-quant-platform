import { useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import type { DashboardSocketState, MarketTicker } from "../types";
import { getConnectionBadgeValue } from "../utils/dashboardControls";
import { formatPriceSourceValue, formatRuntimeValue } from "../utils/display";

interface MarketPageProps {
  dashboard: DashboardSocketState & { connected: boolean };
}

function Sparkline({ points }: { points: number[] }) {
  if (!points.length) {
    return <div className="h-10" />;
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const d = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * 100;
      const y = 100 - ((point - min) / range) * 100;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <svg className="h-10 w-24" preserveAspectRatio="none" viewBox="0 0 100 100">
      <path d={d} fill="none" stroke="#2dd4bf" strokeLinecap="round" strokeWidth="5" />
    </svg>
  );
}

export function MarketPage({ dashboard }: MarketPageProps) {
  const [tickers, setTickers] = useState<MarketTicker[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("");

  useEffect(() => {
    void api.getTickers().then(setTickers).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!dashboard.tickers.length) {
      return;
    }
    setTickers(dashboard.tickers);
    if (!selectedSymbol || !dashboard.tickers.some((item) => item.symbol === selectedSymbol)) {
      setSelectedSymbol(dashboard.tickers[0].symbol);
    }
  }, [dashboard.tickers, selectedSymbol]);

  const selectedTicker = useMemo(() => tickers.find((item) => item.symbol === selectedSymbol), [selectedSymbol, tickers]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-white">实时行情总览</h1>
          <p className="mt-1 text-sm text-slate-400">这里展示的是后端推送的实际行情来源，并明确标记当前价格来自交易所还是模拟报价。</p>
        </div>
        <StatusBadge value={getConnectionBadgeValue(dashboard.connected)} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel">
          <div className="border-b border-white/10 px-5 py-4">
            <h3 className="text-lg font-semibold text-white">行情列表</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10 text-sm">
              <thead className="bg-white/5 text-left text-slate-300">
                <tr>
                  {["交易对", "最新价", "来源", "市场", "涨跌幅", "买一", "卖一", "点差", "K 线简图"].map((label) => (
                    <th key={label} className="px-4 py-3 font-medium">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-100">
                {tickers.map((ticker) => (
                  <tr
                    key={ticker.symbol}
                    className={`cursor-pointer transition hover:bg-white/5 ${selectedSymbol === ticker.symbol ? "bg-white/5" : ""}`}
                    onClick={() => setSelectedSymbol(ticker.symbol)}
                  >
                    <td className="px-4 py-3">{ticker.symbol}</td>
                    <td className="px-4 py-3">{ticker.price.toFixed(4)}</td>
                    <td className="px-4 py-3 text-slate-300">{formatPriceSourceValue(ticker.price_source)}</td>
                    <td className="px-4 py-3 text-slate-300">{formatRuntimeValue(ticker.market_type)}</td>
                    <td className={`px-4 py-3 ${ticker.change_percent >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                      {ticker.change_percent.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3">{ticker.bid.toFixed(4)}</td>
                    <td className="px-4 py-3">{ticker.ask.toFixed(4)}</td>
                    <td className="px-4 py-3">{(ticker.spread * 100).toFixed(3)}%</td>
                    <td className="px-4 py-3">
                      <Sparkline points={ticker.sparkline} />
                    </td>
                  </tr>
                ))}
                {tickers.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-slate-400" colSpan={9}>
                      暂无行情数据。
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
          <h3 className="text-lg font-semibold text-white">当前焦点</h3>
          {selectedTicker ? (
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-sm text-slate-400">交易对</p>
                <p className="mt-1 text-2xl font-semibold text-white">{selectedTicker.symbol}</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-sm text-slate-400">最新价</p>
                  <p className="mt-1 text-xl font-semibold text-white">{selectedTicker.price.toFixed(4)}</p>
                  <p className="mt-2 text-xs text-slate-400">
                    {formatRuntimeValue(selectedTicker.market_type)} / {formatPriceSourceValue(selectedTicker.price_source)}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-sm text-slate-400">24h 涨跌</p>
                  <p className={`mt-1 text-xl font-semibold ${selectedTicker.change_percent >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                    {selectedTicker.change_percent.toFixed(2)}%
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-sm text-slate-400">买卖点差</p>
                  <p className="mt-1 text-xl font-semibold text-white">{(selectedTicker.spread * 100).toFixed(3)}%</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-sm text-slate-400">成交量</p>
                  <p className="mt-1 text-xl font-semibold text-white">{selectedTicker.volume.toFixed(2)}</p>
                </div>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-400">请先等待后端推送，或从列表中选择一个交易对。</p>
          )}
        </div>
      </div>
    </div>
  );
}
