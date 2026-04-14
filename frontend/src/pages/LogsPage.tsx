import { useEffect, useState } from "react";

import { api } from "../api/client";
import { LogViewer } from "../components/LogViewer";
import type { LogsResponse } from "../types";

export function LogsPage() {
  const [data, setData] = useState<LogsResponse>({ logs: [], risk_events: [], alerts: [] });

  useEffect(() => {
    void api.getLogs().then(setData);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-white">日志与告警</h1>
        <p className="mt-1 text-sm text-slate-400">查看系统日志、风控拒绝记录、异常订单和保护模式原因。</p>
      </div>
      <LogViewer logs={data.logs} riskEvents={data.risk_events} alerts={data.alerts} />
    </div>
  );
}
