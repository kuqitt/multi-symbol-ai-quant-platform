interface StatCardProps {
  label: string;
  value: string;
  hint?: string;
  accent?: "default" | "success" | "danger";
}

export function StatCard({ label, value, hint, accent = "default" }: StatCardProps) {
  const accentClass =
    accent === "success"
      ? "from-emerald-500/20 to-emerald-300/5"
      : accent === "danger"
        ? "from-rose-500/20 to-rose-300/5"
        : "from-cyan-500/20 to-white/0";

  return (
    <div className={`rounded-3xl border border-white/10 bg-gradient-to-br ${accentClass} p-5 shadow-panel backdrop-blur`}>
      <p className="text-xs uppercase tracking-[0.28em] text-slate-300">{label}</p>
      <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
      {hint ? <p className="mt-2 text-sm text-slate-300">{hint}</p> : null}
    </div>
  );
}

