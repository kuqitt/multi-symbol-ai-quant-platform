import type { StatusResponse } from "../types";

export type DashboardControlAction = "start" | "pause" | "stop" | "protect" | "reset-paper";

export interface DashboardControl {
  action: DashboardControlAction;
  label: string;
  tone: "primary" | "secondary" | "danger";
  disabled: boolean;
}

export function getConnectionBadgeValue(connected: boolean): "CONNECTED" | "DISCONNECTED" {
  return connected ? "CONNECTED" : "DISCONNECTED";
}

export function getDashboardControls(status?: StatusResponse): DashboardControl[] {
  const runtimeStatus = status?.status ?? "STOPPED";
  const riskStatus = status?.risk_status ?? "NORMAL";
  const strategyRunning = Boolean(status?.strategy_running);
  const isPaper = (status?.env ?? "paper") === "paper";
  const inProtectMode = runtimeStatus === "PROTECT_MODE" || riskStatus === "PROTECT_MODE";

  const controls: DashboardControl[] = [
    {
      action: "start",
      label:
        runtimeStatus === "PAUSED"
          ? "恢复运行"
          : inProtectMode
            ? "解除保护并启动"
            : strategyRunning
              ? "策略运行中"
              : "启动策略",
      tone: "primary",
      disabled: strategyRunning && runtimeStatus === "RUNNING",
    },
    {
      action: "pause",
      label: "暂停策略",
      tone: "secondary",
      disabled: runtimeStatus !== "RUNNING",
    },
    {
      action: "stop",
      label: "停止策略",
      tone: "secondary",
      disabled: runtimeStatus === "STOPPED",
    },
    {
      action: "protect",
      label: inProtectMode ? "已在保护模式" : "进入保护模式",
      tone: "danger",
      disabled: runtimeStatus === "STOPPED" || inProtectMode,
    },
  ];

  if (isPaper) {
    controls.push({
      action: "reset-paper",
      label: "重置模拟账户",
      tone: "secondary",
      disabled: runtimeStatus === "RUNNING",
    });
  }

  return controls;
}