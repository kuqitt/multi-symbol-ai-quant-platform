import { useState } from "react";

import { api } from "../api/client";
import { ConfigForm } from "../components/ConfigForm";
import { useConfig } from "../hooks/useConfig";

export function SettingsPage() {
  const { config, loading, error, reload } = useConfig();
  const [saving, setSaving] = useState(false);

  const handleSave = async (nextConfig: NonNullable<typeof config>, applyImmediately: boolean) => {
    setSaving(true);
    try {
      await api.updateConfig(nextConfig, applyImmediately);
      await reload();
    } finally {
      setSaving(false);
    }
  };

  if (loading || !config) {
    return <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 text-slate-300">正在加载业务参数...</div>;
  }

  if (error) {
    return <div className="rounded-3xl border border-rose-400/30 bg-rose-500/10 p-6 text-rose-200">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-white">参数配置</h1>
        <p className="mt-1 text-sm text-slate-400">业务参数留在这里，系统配置请到独立的“系统配置”页面维护。</p>
      </div>
      <ConfigForm config={config} saving={saving} onSave={handleSave} />
    </div>
  );
}
