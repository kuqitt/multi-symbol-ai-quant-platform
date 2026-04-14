import { useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import { ReplayPlayer } from "../components/ReplayPlayer";
import { useConfig } from "../hooks/useConfig";
import type { ReplayFrame } from "../types";

export function ReplayPage() {
  const { config } = useConfig();
  const [symbol, setSymbol] = useState("");
  const [frames, setFrames] = useState<ReplayFrame[]>([]);

  const symbols = useMemo(() => config?.symbols ?? [], [config]);

  useEffect(() => {
    if (!symbols.length) {
      return;
    }
    if (!symbol || !symbols.includes(symbol)) {
      setSymbol(symbols[0]);
    }
  }, [symbol, symbols]);

  useEffect(() => {
    if (!symbol) {
      return;
    }
    void api.getReplayFrames(symbol).then((response) => setFrames(response.frames));
  }, [symbol]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-white">细粒度回放</h1>
          <p className="mt-1 text-sm text-slate-400">按帧回看局部行情与最新成交，用于策略复盘和人工审核。</p>
        </div>
        <select
          className="rounded-full border border-white/10 bg-slate-950/80 px-4 py-2 text-white"
          onChange={(event) => setSymbol(event.target.value)}
          value={symbol}
        >
          {symbols.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <ReplayPlayer symbol={symbol} frames={frames} />
    </div>
  );
}
