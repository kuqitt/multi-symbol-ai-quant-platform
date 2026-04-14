import { useState } from "react";

interface LoginPageProps {
  onLogin: (username: string, password: string) => Promise<void>;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("ChangeMe123!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    setError("");
    try {
      await onLogin(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.18),_rgba(15,23,42,0.96)_40%,_rgba(2,6,23,1)_100%)] px-4">
      <div className="w-full max-w-md rounded-[2rem] border border-white/10 bg-slate-900/85 p-8 shadow-panel backdrop-blur">
        <p className="text-xs uppercase tracking-[0.36em] text-cyan-300">权限登录</p>
        <h1 className="mt-3 text-3xl font-semibold text-white">交易控制台登录</h1>
        <p className="mt-3 text-sm leading-6 text-slate-300">
          当前版本已接入后端 JWT 认证和基础 RBAC。默认会自动初始化一个管理员账号，首次登录后建议尽快修改环境变量中的初始密码。
        </p>
        <div className="mt-6 space-y-4">
          <input
            className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white outline-none focus:border-cyan-400"
            placeholder="请输入用户名"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <input
            className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white outline-none focus:border-cyan-400"
            placeholder="请输入密码"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}
        <button
          className="mt-6 w-full rounded-full bg-cyan-400 px-4 py-3 font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-600"
          disabled={loading}
          onClick={() => void submit()}
          type="button"
        >
          {loading ? "登录中..." : "进入控制台"}
        </button>
      </div>
    </div>
  );
}
