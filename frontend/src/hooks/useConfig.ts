import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type { BusinessConfig } from "../types";

export function useConfig() {
  const [config, setConfig] = useState<BusinessConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextConfig = await api.getConfig();
      setConfig(nextConfig);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载参数配置失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { config, setConfig, loading, error, reload: load };
}
