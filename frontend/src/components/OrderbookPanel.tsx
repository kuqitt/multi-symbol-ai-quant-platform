import type { OrderbookSnapshot, Trade } from "../types";
import { formatRuntimeValue } from "../utils/display";

interface OrderbookPanelProps {
  orderbook: OrderbookSnapshot | null;
  trades: Trade[];
}

export function OrderbookPanel({ orderbook, trades }: OrderbookPanelProps) {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
        <h3 className="text-lg font-semibold text-white">五档盘口</h3>
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="mb-2 text-slate-400">卖盘</p>
            <div className="space-y-2">
              {(orderbook?.asks ?? []).map(([price, size], index) => (
                <div key={`ask-${index}`} className="flex justify-between rounded-2xl bg-rose-500/10 px-3 py-2 text-rose-200">
                  <span>{price.toFixed(4)}</span>
                  <span>{size.toFixed(4)}</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-slate-400">买盘</p>
            <div className="space-y-2">
              {(orderbook?.bids ?? []).map(([price, size], index) => (
                <div key={`bid-${index}`} className="flex justify-between rounded-2xl bg-emerald-500/10 px-3 py-2 text-emerald-200">
                  <span>{price.toFixed(4)}</span>
                  <span>{size.toFixed(4)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
        <h3 className="text-lg font-semibold text-white">最新逐笔</h3>
        <div className="mt-4 space-y-2">
          {trades.length === 0 ? <p className="text-sm text-slate-400">暂无逐笔成交。</p> : null}
          {trades.map((trade) => (
            <div key={`${trade.client_order_id}-${trade.timestamp}`} className="flex items-center justify-between rounded-2xl border border-white/5 bg-white/5 px-3 py-2 text-sm">
              <span className="text-slate-200">{formatRuntimeValue(trade.side)}</span>
              <span className="text-white">{trade.price.toFixed(4)}</span>
              <span className="text-slate-300">{trade.quantity.toFixed(4)}</span>
              <span className="text-xs text-slate-400">{new Date(trade.timestamp).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
