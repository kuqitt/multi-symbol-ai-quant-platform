import { useState } from "react";

import { api } from "../api/client";
import { BotControlPanel } from "../components/BotControlPanel";
import { SystemConfigForm } from "../components/SystemConfigForm";
import { useSystemConfig } from "../hooks/useSystemConfig";

export function SystemConfigPage() {
  const { data, loading, error, reload } = useSystemConfig();
  const [saving, setSaving] = useState(false);

  const handleSave = async (nextConfig: NonNullable<typeof data>["config"], applyImmediately: boolean) => {
    setSaving(true);
    try {
      await api.updateSystemConfig(nextConfig, applyImmediately);
      await reload();
    } finally {
      setSaving(false);
    }
  };

  if (loading || !data) {
    return <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 text-slate-300">正在加载系统配置...</div>;
  }

  if (error) {
    return <div className="rounded-3xl border border-rose-400/30 bg-rose-500/10 p-6 text-rose-200">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-white">系统配置</h1>
        <p className="mt-1 text-sm text-slate-400">
          这里维护交易所接入、运行环境、模拟盘账户、通知、认证和机器人控制等平台级配置。
        </p>
      </div>
      <SystemConfigForm data={data} saving={saving} onSave={handleSave} />
      <BotControlPanel config={data.config} />
    </div>
  );
}
