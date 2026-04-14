import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { DailyPnlPoint } from "../types";

interface PnlChartProps {
  points: DailyPnlPoint[];
}

export function PnlChart({ points }: PnlChartProps) {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
      <h3 className="mb-4 text-lg font-semibold text-white">日收益柱状图</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={points}>
            <CartesianGrid stroke="rgba(148,163,184,0.18)" vertical={false} />
            <XAxis dataKey="date" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" width={72} />
            <Tooltip />
            <Bar dataKey="pnl" fill="#22c55e" radius={[10, 10, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
