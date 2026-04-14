import { useEffect, useMemo, useState } from "react";

import type { ReplayFrame } from "../types";
import { CandlestickChart } from "./CandlestickChart";

interface ReplayPlayerProps {
  symbol: string;
  frames: ReplayFrame[];
}

export function ReplayPlayer({ symbol, frames }: ReplayPlayerProps) {
  const [index, setIndex] = useState(() => Math.max(frames.length - 1, 0));

  useEffect(() => {
    setIndex(Math.max(frames.length - 1, 0));
  }, [frames]);

  const visibleFrames = useMemo(() => frames.slice(0, index + 1), [frames, index]);
  const current = visibleFrames[visibleFrames.length - 1];

  if (frames.length === 0) {
    return <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 text-slate-300">暂无可回放数据。</div>;
  }

  return (
    <div className="space-y-4 rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">{symbol} 细粒度回放</h3>
          <p className="mt-1 text-sm text-slate-400">拖动时间轴逐帧查看价格、成交和局部走势。</p>
        </div>
        {current ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">
            当前帧：{new Date(current.timestamp).toLocaleString()}
          </div>
        ) : null}
      </div>
      <CandlestickChart title={`${symbol} 回放`} candles={visibleFrames} />
      <input
        className="w-full"
        max={Math.max(frames.length - 1, 0)}
        min={0}
        onChange={(event) => setIndex(Number(event.target.value))}
        type="range"
        value={index}
      />
    </div>
  );
}
