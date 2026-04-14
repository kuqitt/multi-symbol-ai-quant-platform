import { useState } from "react";

import { DecisionDetailDrawer } from "./DecisionDetailDrawer";
import type { Order, Trade } from "../types";
import { formatRuntimeValue } from "../utils/display";
import { formatReasonText } from "../utils/logDisplay";

interface OrdersTableProps {
  orders: Order[];
  trades?: Trade[];
}

export function OrdersTable({ orders, trades = [] }: OrdersTableProps) {
  const [selected, setSelected] = useState<{ title: string; subtitle: string; data: Record<string, unknown> | null } | null>(null);

  return (
    <>
      <div className="grid gap-6 lg:grid-cols-2">
      <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel">
        <div className="border-b border-white/10 px-5 py-4">
          <h3 className="text-lg font-semibold text-white">历史订单</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-slate-300">
              <tr>
                {["交易对", "方向", "类型", "状态", "市场状态", "信号分数", "目标仓位", "预估成本", "数量", "委托价", "成交价", "决策原因", "风控结果", "详情"].map((label) => (
                  <th key={label} className="px-4 py-3 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-100">
              {orders.map((order) => (
                <tr key={order.id}>
                  <td className="px-4 py-3">{order.symbol}</td>
                  <td className="px-4 py-3">{formatRuntimeValue(order.side)}</td>
                  <td className="px-4 py-3">{formatRuntimeValue(order.order_type)}</td>
                  <td className="px-4 py-3">{formatRuntimeValue(order.status)}</td>
                  <td className="px-4 py-3">{formatRuntimeValue(order.regime)}</td>
                  <td className="px-4 py-3">{order.signal_score.toFixed(3)}</td>
                  <td className="px-4 py-3">{(order.target_weight * 100).toFixed(1)}%</td>
                  <td className="px-4 py-3">{order.expected_cost_bps.toFixed(2)} bps</td>
                  <td className="px-4 py-3">{order.quantity.toFixed(6)}</td>
                  <td className="px-4 py-3">{order.price.toFixed(4)}</td>
                  <td className="px-4 py-3">{order.average_fill_price.toFixed(4)}</td>
                  <td className="px-4 py-3 text-xs text-slate-300">{formatReasonText(order.decision_reason, (order.metadata_json as { reason_context?: unknown } | null)?.reason_context)}</td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    {order.risk_reason
                      ? formatReasonText(order.risk_reason, (order.metadata_json as { reason_context?: unknown } | null)?.reason_context)
                      : "通过"}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-200 hover:bg-white/10"
                      onClick={() =>
                        setSelected({
                          title: `${order.symbol} ${formatRuntimeValue(order.side)} 订单详情`,
                          subtitle: `${formatRuntimeValue(order.status)} · ${order.strategy_name}`,
                          data: { ...order, ...(order.metadata_json ?? {}) },
                        })
                      }
                    >
                      查看
                    </button>
                  </td>
                </tr>
              ))}
              {orders.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-slate-400" colSpan={14}>
                    当前没有订单记录。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel">
        <div className="border-b border-white/10 px-5 py-4">
          <h3 className="text-lg font-semibold text-white">历史成交</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-slate-300">
              <tr>
                {["交易对", "方向", "市场状态", "数量", "成交价", "手续费", "信号分数", "预估成本", "已实现收益", "成交时间", "详情"].map((label) => (
                  <th key={label} className="px-4 py-3 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-100">
              {trades.map((trade) => (
                <tr key={trade.id}>
                  <td className="px-4 py-3">{trade.symbol}</td>
                  <td className="px-4 py-3">{formatRuntimeValue(trade.side)}</td>
                  <td className="px-4 py-3">{formatRuntimeValue(trade.regime)}</td>
                  <td className="px-4 py-3">{trade.quantity.toFixed(6)}</td>
                  <td className="px-4 py-3">{trade.price.toFixed(4)}</td>
                  <td className="px-4 py-3">{trade.fee.toFixed(4)}</td>
                  <td className="px-4 py-3">{trade.signal_score.toFixed(3)}</td>
                  <td className="px-4 py-3">{trade.expected_cost_bps.toFixed(2)} bps</td>
                  <td className={`px-4 py-3 ${trade.realized_pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{trade.realized_pnl.toFixed(2)}</td>
                  <td className="px-4 py-3 text-xs text-slate-400">{new Date(trade.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <button
                      className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-200 hover:bg-white/10"
                      onClick={() =>
                        setSelected({
                          title: `${trade.symbol} ${formatRuntimeValue(trade.side)} 成交详情`,
                          subtitle: `${trade.strategy_name} · ${new Date(trade.timestamp).toLocaleString()}`,
                          data: { ...trade, ...(trade.metadata_json ?? {}) },
                        })
                      }
                    >
                      查看
                    </button>
                  </td>
                </tr>
              ))}
              {trades.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-slate-400" colSpan={11}>
                    当前没有成交记录。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
      </div>
      <DecisionDetailDrawer open={Boolean(selected)} title={selected?.title ?? ""} subtitle={selected?.subtitle} data={selected?.data} onClose={() => setSelected(null)} />
    </>
  );
}
