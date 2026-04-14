import type { AlertRecord, LogEntry, RiskEvent } from "../types";
import {
  formatAlertMessage,
  formatLogCategory,
  formatLogEntryMessage,
  formatLogLevel,
  formatRiskEventMessage,
  formatRiskEventReason,
} from "../utils/logDisplay";

interface LogViewerProps {
  logs: LogEntry[];
  riskEvents: RiskEvent[];
  alerts: AlertRecord[];
}

export function LogViewer({ logs, riskEvents, alerts }: LogViewerProps) {
  return (
    <div className="grid gap-6 xl:grid-cols-3">
      <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
        <h3 className="mb-4 text-lg font-semibold text-white">最近告警</h3>
        <div className="space-y-3">
          {alerts.map((alert, index) => (
            <div key={`${alert.created_at}-${index}`} className="rounded-2xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{formatLogLevel(alert.level)}</p>
              <p className="mt-1 text-sm text-white">{formatAlertMessage(alert)}</p>
              <p className="mt-1 text-xs text-slate-400">{new Date(alert.created_at).toLocaleString()}</p>
            </div>
          ))}
          {alerts.length === 0 ? <p className="text-sm text-slate-400">当前没有告警记录。</p> : null}
        </div>
      </section>

      <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
        <h3 className="mb-4 text-lg font-semibold text-white">风控事件</h3>
        <div className="space-y-3">
          {riskEvents.map((event) => (
            <div key={event.id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
              <p className="text-xs uppercase tracking-[0.24em] text-rose-300">{formatRiskEventReason(event)}</p>
              <p className="mt-1 text-sm text-white">{formatRiskEventMessage(event)}</p>
              <p className="mt-1 text-xs text-slate-400">
                {event.symbol || "系统"} | {new Date(event.created_at).toLocaleString()}
              </p>
            </div>
          ))}
          {riskEvents.length === 0 ? <p className="text-sm text-slate-400">当前没有风控事件。</p> : null}
        </div>
      </section>

      <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-panel">
        <h3 className="mb-4 text-lg font-semibold text-white">系统日志</h3>
        <div className="space-y-3">
          {logs.map((log) => (
            <div key={log.id} className="rounded-2xl border border-white/10 bg-white/5 p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-400">
                  {formatLogLevel(log.level)} | {formatLogCategory(log.category)}
                </p>
                <span className="text-xs text-slate-500">{new Date(log.timestamp).toLocaleString()}</span>
              </div>
              <p className="mt-1 text-sm text-white">{formatLogEntryMessage(log)}</p>
            </div>
          ))}
          {logs.length === 0 ? <p className="text-sm text-slate-400">当前没有日志。</p> : null}
        </div>
      </section>
    </div>
  );
}
