import type { Position } from "../types";
import { formatRuntimeValue } from "../utils/display";

interface PositionsTableProps {
  positions: Position[];
}

export function PositionsTable({ positions }: PositionsTableProps) {
  return (
    <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel">
      <div className="border-b border-white/10 px-5 py-4">
        <h3 className="text-lg font-semibold text-white">当前持仓</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/10 text-sm">
          <thead className="bg-white/5 text-left text-slate-300">
            <tr>
                {["交易对", "方向", "市场状态", "数量", "持仓均价", "最新价", "市值", "信号分数", "目标仓位", "预估成本", "已实现收益", "未实现收益", "仓位占比"].map((label) => (
                <th key={label} className="px-4 py-3 font-medium">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-slate-100">
            {positions.map((position) => (
              <tr key={position.id}>
                <td className="px-4 py-3">{position.symbol}</td>
                <td className="px-4 py-3">{formatRuntimeValue(position.side)}</td>
                  <td className="px-4 py-3">{formatRuntimeValue(position.regime)}</td>
                <td className="px-4 py-3">{position.quantity.toFixed(6)}</td>
                <td className="px-4 py-3">{position.avg_price.toFixed(4)}</td>
                <td className="px-4 py-3">{position.market_price.toFixed(4)}</td>
                <td className="px-4 py-3">{position.market_value.toFixed(2)}</td>
                  <td className="px-4 py-3">{position.signal_score.toFixed(3)}</td>
                  <td className="px-4 py-3">{(position.target_weight * 100).toFixed(1)}%</td>
                  <td className="px-4 py-3">{position.expected_cost_bps.toFixed(2)} bps</td>
                <td className="px-4 py-3">{position.realized_pnl.toFixed(2)}</td>
                <td className={`px-4 py-3 ${position.unrealized_pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{position.unrealized_pnl.toFixed(2)}</td>
                <td className="px-4 py-3">{(position.exposure_ratio * 100).toFixed(2)}%</td>
              </tr>
            ))}
            {positions.length === 0 ? (
              <tr>
                  <td className="px-4 py-6 text-slate-400" colSpan={13}>
                  当前没有持仓。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
