import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { SeriesPoint } from "../types";

interface EquityChartProps {
  points: SeriesPoint[];
  title?: string;
}

export function EquityChart({ points, title = "资金净值曲线" }: EquityChartProps) {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <span className="text-xs uppercase tracking-[0.25em] text-slate-400">{points.length} 个点</span>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points}>
            <defs>
              <linearGradient id="equityFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.7} />
                <stop offset="95%" stopColor="#14b8a6" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(148,163,184,0.18)" vertical={false} />
            <XAxis dataKey="timestamp" hide />
            <YAxis stroke="#94a3b8" width={72} />
            <Tooltip />
            <Area type="monotone" dataKey="value" stroke="#2dd4bf" fill="url(#equityFill)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
