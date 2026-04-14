import { formatRuntimeValue } from "../utils/display";
import { formatReasonText } from "../utils/logDisplay";

interface DecisionDetailDrawerProps {
  open: boolean;
  title: string;
  subtitle?: string;
  data?: Record<string, unknown> | null;
  onClose: () => void;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.24em] text-slate-500">{label}</div>
      <div className="text-sm text-slate-100">{value}</div>
    </div>
  );
}

function numberValue(value: unknown, suffix = "", digits = 3): string {
  return typeof value === "number" ? `${value.toFixed(digits)}${suffix}` : "--";
}

export function DecisionDetailDrawer({ open, title, subtitle, data, onClose }: DecisionDetailDrawerProps) {
  if (!open) {
    return null;
  }

  const reasonContext = (data?.reason_context as Record<string, unknown> | undefined) ?? data ?? {};
  const cost = (reasonContext.cost as Record<string, unknown> | undefined) ?? {};
  const contributors = Array.isArray(data?.contributors) ? data?.contributors : [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/70 backdrop-blur-sm">
      <button aria-label="关闭详情抽屉" className="flex-1" onClick={onClose} type="button" />
      <div className="h-full w-full max-w-2xl overflow-y-auto border-l border-white/10 bg-slate-950 px-6 py-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-cyan-300">Decision Detail</p>
            <h3 className="mt-2 text-2xl font-semibold text-white">{title}</h3>
            {subtitle ? <p className="mt-2 text-sm text-slate-400">{subtitle}</p> : null}
          </div>
          <button className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 hover:bg-white/10" onClick={onClose} type="button">
            关闭
          </button>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <DetailRow label="决策原因" value={formatReasonText(String(data?.reason ?? data?.decision_reason ?? ""), reasonContext)} />
          <DetailRow label="风控结果" value={formatReasonText(String(data?.risk_reason ?? data?.approval_reason ?? ""), reasonContext)} />
          <DetailRow label="市场状态" value={formatRuntimeValue(String(data?.regime ?? reasonContext.regime ?? "unknown"))} />
          <DetailRow label="最终动作" value={formatRuntimeValue(String(data?.side ?? data?.signal ?? data?.final_action ?? "--"))} />
          <DetailRow label="信号分数" value={numberValue(data?.signal_score ?? reasonContext.signal_score)} />
          <DetailRow label="目标仓位" value={typeof (data?.target_weight ?? reasonContext.target_weight) === "number" ? `${(((data?.target_weight ?? reasonContext.target_weight) as number) * 100).toFixed(2)}%` : "--"} />
          <DetailRow label="预估总成本" value={numberValue(data?.expected_cost_bps ?? cost.total_cost_bps, " bps", 2)} />
          <DetailRow label="预估滑点" value={numberValue(data?.expected_slippage_bps ?? cost.slippage_bps, " bps", 2)} />
          <DetailRow label="止损" value={numberValue(data?.stop_loss ?? reasonContext.stop_loss, "", 4)} />
          <DetailRow label="止盈" value={numberValue(data?.take_profit ?? reasonContext.take_profit, "", 4)} />
          <DetailRow label="期望名义仓位" value={numberValue(reasonContext.desired_notional, " USDT", 2)} />
          <DetailRow label="申请人/来源" value={String(data?.requested_by ?? data?.strategy_name ?? "system")} />
        </div>

        <div className="mt-6 rounded-3xl border border-white/10 bg-white/5 p-5">
          <h4 className="text-lg font-semibold text-white">贡献策略</h4>
          {contributors.length === 0 ? <p className="mt-3 text-sm text-slate-400">当前没有贡献策略明细。</p> : null}
          <div className="mt-4 space-y-3">
            {contributors.map((item, index) => {
              const contributor = item as Record<string, unknown>;
              return (
                <div key={`${contributor.strategy_name ?? contributor.name ?? index}`} className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-3 text-slate-100">
                    <span>{String(contributor.strategy_name ?? contributor.name ?? `contributor-${index + 1}`)}</span>
                    <span>{formatRuntimeValue(String(contributor.signal ?? contributor.final_action ?? "--"))}</span>
                  </div>
                  <div className="mt-2 text-slate-400">{formatReasonText(String(contributor.reason ?? ""), contributor.reason_context)}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-6 rounded-3xl border border-white/10 bg-white/5 p-5">
          <h4 className="text-lg font-semibold text-white">原始上下文</h4>
          <pre className="mt-4 overflow-x-auto rounded-2xl bg-slate-950/80 p-4 text-xs leading-6 text-slate-300">{JSON.stringify(data ?? {}, null, 2)}</pre>
        </div>
      </div>
    </div>
  );
}
