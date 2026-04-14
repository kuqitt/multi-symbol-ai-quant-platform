import { useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import { OrderbookPanel } from "../components/OrderbookPanel";
import type { DashboardSocketState, LatestTradeSnapshot, OrderbookSnapshot } from "../types";

interface OrderFlowPageProps {
  dashboard: DashboardSocketState & { connected: boolean };
}

export function OrderFlowPage({ dashboard }: OrderFlowPageProps) {
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [orderbook, setOrderbook] = useState<OrderbookSnapshot | null>(null);
  const [trades, setTrades] = useState<LatestTradeSnapshot[]>([]);

  useEffect(() => {
    const firstSymbol = dashboard.tickers[0]?.symbol;
    if (firstSymbol && (!selectedSymbol || !dashboard.tickers.find((item) => item.symbol === selectedSymbol))) {
      setSelectedSymbol(firstSymbol);
    }
  }, [dashboard.tickers, selectedSymbol]);

  useEffect(() => {
    if (!selectedSymbol) {
      return;
    }
    void Promise.all([api.getOrderbook(selectedSymbol), api.getRecentTrades(selectedSymbol)]).then(([book, tradePayload]) => {
      setOrderbook(book);
      setTrades(tradePayload.trades);
    });
  }, [selectedSymbol]);

  const symbols = useMemo(
    () => Array.from(new Set([selectedSymbol, ...dashboard.tickers.map((item) => item.symbol)])).filter(Boolean),
    [dashboard.tickers, selectedSymbol],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-white">订单流与盘口</h1>
          <p className="mt-1 text-sm text-slate-400">查看五档盘口、逐笔成交和买卖力量变化，用于人工复核和执行诊断。</p>
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
      <OrderbookPanel
        orderbook={orderbook}
        trades={trades.map((trade, index) => ({
          id: index,
          order_id: null,
          client_order_id: `${trade.symbol}-${index}`,
          symbol: trade.symbol,
          side: trade.side,
          strategy_name: "market",
          quantity: trade.quantity,
          price: trade.price,
          fee: 0,
          realized_pnl: 0,
          regime: "unknown",
          entry_tag: "",
          exit_tag: "",
          signal_score: 0,
          expected_cost_bps: 0,
          slippage_bps: 0,
          fee_bps: 0,
          metadata_json: null,
          timestamp: trade.timestamp,
        }))}
      />
    </div>
  );
}
