import { useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import { CandlestickChart } from "../components/CandlestickChart";
import type { DashboardSocketState, ReplayFrame } from "../types";

interface KlinePageProps {
  dashboard: DashboardSocketState & { connected: boolean };
}

export function KlinePage({ dashboard }: KlinePageProps) {
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [candles, setCandles] = useState<ReplayFrame[]>([]);

  useEffect(() => {
    if (!dashboard.tickers.length) {
      return;
    }
    if (!selectedSymbol || !dashboard.tickers.some((item) => item.symbol === selectedSymbol)) {
      setSelectedSymbol(dashboard.tickers[0].symbol);
    }
  }, [dashboard.tickers, selectedSymbol]);

  useEffect(() => {
    if (!selectedSymbol) {
      return;
    }
    void api.getCandles(selectedSymbol).then((response) => {
      setCandles(
        response.candles.map((item) => ({
          timestamp: String(item.timestamp),
          open: Number(item.open),
          high: Number(item.high),
          low: Number(item.low),
          close: Number(item.close),
          volume: Number(item.volume),
        })),
      );
    });
  }, [selectedSymbol]);

  const symbols = useMemo(() => Array.from(new Set(dashboard.tickers.map((item) => item.symbol))).filter(Boolean), [dashboard.tickers]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-white">{"K \u7ebf\u56fe\u5206\u6790"}</h1>
          <p className="mt-1 text-sm text-slate-400">
            {"\u56fe\u8868\u76f4\u63a5\u7ed1\u5b9a\u540e\u7aef /api/market/candles/{symbol} \u63a5\u53e3\uff0c\u5207\u6362\u4ea4\u6613\u5bf9\u540e\u4f1a\u5373\u65f6\u5237\u65b0\u3002"}
          </p>
        </div>
        <select
          className="rounded-full border border-white/10 bg-slate-950/80 px-4 py-2 text-white"
          onChange={(event) => setSelectedSymbol(event.target.value)}
          value={selectedSymbol}
        >
          {symbols.map((symbol) => (
            <option key={symbol} value={symbol}>
              {symbol}
            </option>
          ))}
        </select>
      </div>
      <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
        <CandlestickChart candles={candles} title={selectedSymbol ? `${selectedSymbol} K \u7ebf` : "K \u7ebf"} />
      </div>
    </div>
  );
}
