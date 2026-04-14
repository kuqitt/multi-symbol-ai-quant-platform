import { useEffect, useState } from "react";

import { getAuthToken, getWebSocketUrl } from "../api/client";
import type { DashboardSocketState, LogEntry, MarketTicker, Position, StatusResponse, SummaryMetrics } from "../types";

const initialState: DashboardSocketState = {
  tickers: [],
  positions: [],
  recentLogs: [],
  alerts: [],
};

function mergeTickers(previousTickers: MarketTicker[], incomingTickers: MarketTicker[]): MarketTicker[] {
  if (incomingTickers.length === 0) {
    return previousTickers;
  }

  if (previousTickers.length === 0 || incomingTickers.length > 1) {
    return incomingTickers;
  }

  const merged = new Map(previousTickers.map((ticker) => [ticker.symbol, ticker]));
  for (const ticker of incomingTickers) {
    merged.set(ticker.symbol, ticker);
  }

  return previousTickers.map((ticker) => merged.get(ticker.symbol) ?? ticker);
}

export function useDashboardSocket(enabled = true) {
  const [state, setState] = useState<DashboardSocketState>(initialState);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!enabled || !getAuthToken()) {
      setConnected(false);
      return;
    }
    const socket = new WebSocket(getWebSocketUrl("/ws/dashboard"));
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as Record<string, unknown>;
      setState((previous) => {
        if (payload.type === "snapshot") {
          return {
            status: payload.status as StatusResponse,
            metrics: payload.metrics as SummaryMetrics,
            tickers: (payload.tickers as MarketTicker[]) ?? [],
            positions: (payload.positions as Position[]) ?? [],
            recentLogs: (payload.recent_logs as LogEntry[]) ?? [],
            alerts: (payload.alerts as DashboardSocketState["alerts"]) ?? [],
          };
        }
        if (payload.type === "market") {
          return {
            ...previous,
            tickers: mergeTickers(previous.tickers, (payload.tickers as MarketTicker[]) ?? []),
          };
        }
        if (payload.type === "metrics") {
          return { ...previous, metrics: payload.summary as SummaryMetrics };
        }
        if (payload.type === "status") {
          return { ...previous, status: payload.status as StatusResponse };
        }
        if (payload.type === "log" && payload.log) {
          return {
            ...previous,
            recentLogs: [payload.log as LogEntry, ...previous.recentLogs].slice(0, 40),
            alerts: (payload.alerts as DashboardSocketState["alerts"]) ?? previous.alerts,
          };
        }
        return previous;
      });
    };
    const heartbeat = window.setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send("ping");
      }
    }, 15000);
    return () => {
      window.clearInterval(heartbeat);
      socket.close();
    };
  }, [enabled]);

  return { ...state, connected };
}
