import { lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";

import { api, clearAuthSession, getStoredIdentity, setAuthSession } from "./api/client";
import { useDashboardSocket } from "./hooks/useDashboardSocket";
import { LoginPage } from "./pages/LoginPage";

const DashboardPage = lazy(() => import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const MarketPage = lazy(() => import("./pages/MarketPage").then((module) => ({ default: module.MarketPage })));
const KlinePage = lazy(() => import("./pages/KlinePage").then((module) => ({ default: module.KlinePage })));
const OrderFlowPage = lazy(() => import("./pages/OrderFlowPage").then((module) => ({ default: module.OrderFlowPage })));
const ReplayPage = lazy(() => import("./pages/ReplayPage").then((module) => ({ default: module.ReplayPage })));
const PositionsPage = lazy(() => import("./pages/PositionsPage").then((module) => ({ default: module.PositionsPage })));
const MetricsPage = lazy(() => import("./pages/MetricsPage").then((module) => ({ default: module.MetricsPage })));
const ApprovalsPage = lazy(() => import("./pages/ApprovalsPage").then((module) => ({ default: module.ApprovalsPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));
const SystemConfigPage = lazy(() => import("./pages/SystemConfigPage").then((module) => ({ default: module.SystemConfigPage })));
const LogsPage = lazy(() => import("./pages/LogsPage").then((module) => ({ default: module.LogsPage })));

const navItems = [
  { label: "仪表盘", path: "/" },
  { label: "行情总览", path: "/market" },
  { label: "K 线图", path: "/kline" },
  { label: "订单流", path: "/orderflow" },
  { label: "细粒度回放", path: "/replay" },
  { label: "持仓订单", path: "/positions" },
  { label: "收益统计", path: "/metrics" },
  { label: "人工审核", path: "/approvals" },
  { label: "参数配置", path: "/settings" },
  { label: "系统配置", path: "/system-settings" },
  { label: "日志告警", path: "/logs" },
];

function LoadingPanel() {
  return <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 text-slate-300">页面加载中...</div>;
}

function Shell({
  darkMode,
  onToggleTheme,
  onLogout,
  userLabel,
  children,
}: {
  darkMode: boolean;
  onToggleTheme: () => void;
  onLogout: () => void;
  userLabel: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(45,212,191,0.18),_rgba(15,23,42,0.95)_38%,_rgba(2,6,23,1)_100%)] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1680px] gap-6 px-4 py-4 lg:px-6">
        <aside className="hidden w-72 shrink-0 rounded-[2rem] border border-white/10 bg-slate-950/75 p-5 shadow-panel backdrop-blur xl:block">
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-300">量化交易平台</p>
          <h2 className="mt-3 text-2xl font-semibold text-white">控制中心</h2>
          <nav className="mt-8 space-y-2">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                className={({ isActive }) =>
                  `block rounded-2xl px-4 py-3 text-sm transition ${
                    isActive ? "bg-cyan-400 text-slate-950" : "bg-white/0 text-slate-300 hover:bg-white/5 hover:text-white"
                  }`
                }
                to={item.path}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-8 rounded-3xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-400">默认安全原则</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-300">
              <li>优先使用模拟盘、测试网和 Demo 环境</li>
              <li>所有下单都必须先经过风控和审批流程</li>
              <li>交易所密钥只从环境变量读取</li>
            </ul>
          </div>
        </aside>

        <main className="flex-1">
          <header className="mb-6 rounded-[2rem] border border-white/10 bg-slate-950/70 px-5 py-4 shadow-panel backdrop-blur">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap gap-2 xl:hidden">
                {navItems.map((item) => (
                  <NavLink
                    key={item.path}
                    className={({ isActive }) =>
                      `rounded-full px-4 py-2 text-sm transition ${
                        isActive ? "bg-cyan-400 text-slate-950" : "border border-white/10 text-slate-300"
                      }`
                    }
                    to={item.path}
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200">{userLabel}</span>
                <button className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200" onClick={onToggleTheme}>
                  {darkMode ? "切换浅色占位" : "深色模式"}
                </button>
                <button className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200" onClick={onLogout}>
                  退出登录
                </button>
              </div>
            </div>
          </header>
          <Suspense fallback={<LoadingPanel />}>{children}</Suspense>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(() => Boolean(getStoredIdentity()));
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem("quant-theme") !== "light");
  const [userLabel, setUserLabel] = useState(() => {
    const identity = getStoredIdentity();
    return identity ? `${identity.username} / ${identity.role}` : "未登录";
  });
  const dashboard = useDashboardSocket(authenticated);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
    localStorage.setItem("quant-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    if (!authenticated) {
      return;
    }
    void api
      .getMe()
      .then((profile) => {
        setUserLabel(`${profile.username} / ${profile.role}`);
      })
      .catch(() => {
        clearAuthSession();
        setAuthenticated(false);
        setUserLabel("未登录");
      });
  }, [authenticated]);

  const login = async (username: string, password: string) => {
    const session = await api.login(username, password);
    setAuthSession(session);
    setUserLabel(`${session.username} / ${session.role}`);
    setAuthenticated(true);
  };

  const logout = () => {
    clearAuthSession();
    setAuthenticated(false);
    setUserLabel("未登录");
  };

  const socketState = useMemo(() => ({ ...dashboard }), [dashboard]);

  if (!authenticated) {
    return <LoginPage onLogin={login} />;
  }

  return (
    <BrowserRouter>
      <Shell darkMode={darkMode} onToggleTheme={() => setDarkMode((current) => !current)} onLogout={logout} userLabel={userLabel}>
        <Routes>
          <Route path="/" element={<DashboardPage dashboard={socketState} />} />
          <Route path="/market" element={<MarketPage dashboard={socketState} />} />
          <Route path="/kline" element={<KlinePage dashboard={socketState} />} />
          <Route path="/orderflow" element={<OrderFlowPage dashboard={socketState} />} />
          <Route path="/replay" element={<ReplayPage />} />
          <Route path="/positions" element={<PositionsPage />} />
          <Route path="/metrics" element={<MetricsPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/system-settings" element={<SystemConfigPage />} />
          <Route path="/logs" element={<LogsPage />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  );
}
