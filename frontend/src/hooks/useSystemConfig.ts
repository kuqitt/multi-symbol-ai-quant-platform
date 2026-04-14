import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type { SystemConfigResponse } from "../types";

export function useSystemConfig() {
  const [data, setData] = useState<SystemConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextData = await api.getSystemConfig();
      setData(nextData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载系统配置失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, setData, loading, error, reload: load };
}
