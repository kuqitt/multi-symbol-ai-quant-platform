import ReactECharts from "echarts-for-react";

import type { ReplayFrame } from "../types";

interface CandlestickChartProps {
  title: string;
  candles: ReplayFrame[];
}

export function CandlestickChart({ title, candles }: CandlestickChartProps) {
  const option = {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 20, top: 42, bottom: 42 },
    xAxis: {
      type: "category",
      data: candles.map((item) => new Date(item.timestamp).toLocaleTimeString()),
      axisLine: { lineStyle: { color: "#475569" } },
      axisLabel: { color: "#cbd5e1" },
    },
    yAxis: {
      scale: true,
      axisLine: { lineStyle: { color: "#475569" } },
      splitLine: { lineStyle: { color: "rgba(148,163,184,0.15)" } },
      axisLabel: { color: "#cbd5e1" },
    },
    series: [
      {
        name: title,
        type: "candlestick",
        itemStyle: {
          color: "#22c55e",
          color0: "#ef4444",
          borderColor: "#22c55e",
          borderColor0: "#ef4444",
        },
        data: candles.map((item) => [item.open, item.close, item.low, item.high]),
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 360, width: "100%" }} />;
}
