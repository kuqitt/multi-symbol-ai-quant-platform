import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { SeriesPoint } from "../types";

interface DrawdownChartProps {
  points: SeriesPoint[];
}

export function DrawdownChart({ points }: DrawdownChartProps) {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
      <h3 className="mb-4 text-lg font-semibold text-white">回撤曲线</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points}>
            <defs>
              <linearGradient id="drawdownFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.65} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(148,163,184,0.18)" vertical={false} />
            <XAxis dataKey="timestamp" hide />
            <YAxis stroke="#94a3b8" width={72} />
            <Tooltip />
            <Area type="monotone" dataKey="value" stroke="#fb7185" fill="url(#drawdownFill)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
