import { formatRuntimeValue } from "../utils/display";

interface StatusBadgeProps {
  value: string;
}

const colorMap: Record<string, string> = {
  RUNNING: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
  PAUSED: "bg-amber-500/15 text-amber-200 ring-amber-400/30",
  STOPPED: "bg-slate-500/15 text-slate-200 ring-slate-400/30",
  PROTECT_MODE: "bg-rose-500/15 text-rose-200 ring-rose-400/30",
  CONNECTED: "bg-cyan-500/15 text-cyan-200 ring-cyan-400/30",
  DISCONNECTED: "bg-slate-500/15 text-slate-200 ring-slate-400/30",
  NORMAL: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
  HALTED: "bg-rose-500/15 text-rose-200 ring-rose-400/30",
  paper: "bg-sky-500/15 text-sky-200 ring-sky-400/30",
  testnet: "bg-teal-500/15 text-teal-200 ring-teal-400/30",
  demo: "bg-indigo-500/15 text-indigo-200 ring-indigo-400/30",
  live: "bg-rose-500/15 text-rose-200 ring-rose-400/30",
};

export function StatusBadge({ value }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ring-1 ${
        colorMap[value] ?? "bg-slate-500/15 text-slate-200 ring-slate-400/30"
      }`}
    >
      {formatRuntimeValue(value)}
    </span>
  );
}

