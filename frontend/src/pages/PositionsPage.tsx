import { useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import { OrdersTable } from "../components/OrdersTable";
import { PositionsTable } from "../components/PositionsTable";
import type { Order, Position, Trade } from "../types";

export function PositionsPage() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    void Promise.all([api.getPositions(), api.getOrders(), api.getTrades()]).then(([positionsData, ordersData, tradesData]) => {
      setPositions(positionsData);
      setOrders(ordersData);
      setTrades(tradesData);
    });
  }, []);

  const normalizedQuery = query.trim().toUpperCase();
  const filteredPositions = useMemo(() => positions.filter((item) => item.symbol.includes(normalizedQuery)), [normalizedQuery, positions]);
  const filteredOrders = useMemo(
    () => orders.filter((item) => item.symbol.includes(normalizedQuery) || item.status.includes(normalizedQuery)),
    [normalizedQuery, orders],
  );
  const filteredTrades = useMemo(() => trades.filter((item) => item.symbol.includes(normalizedQuery)), [normalizedQuery, trades]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-white">持仓与订单</h1>
          <p className="mt-1 text-sm text-slate-400">筛选当前持仓、历史订单、成交记录和挂单状态，便于快速排查执行链路。</p>
        </div>
        <input
          className="w-full max-w-xs rounded-full border border-white/10 bg-slate-900/80 px-4 py-2 text-white outline-none focus:border-cyan-400"
          placeholder="搜索交易对或状态"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <PositionsTable positions={filteredPositions} />
      <OrdersTable orders={filteredOrders} trades={filteredTrades} />
    </div>
  );
}
