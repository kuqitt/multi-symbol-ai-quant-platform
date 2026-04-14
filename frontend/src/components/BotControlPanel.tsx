import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { BotMetaResponse, BotPreviewResponse, BotTarget, SystemConfig } from "../types";

interface BotControlPanelProps {
  config: SystemConfig;
}

function SectionTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <div>
      <h3 className="text-xl font-semibold text-white">{title}</h3>
      <p className="mt-1 text-sm text-slate-400">{hint}</p>
    </div>
  );
}

export function BotControlPanel({ config }: BotControlPanelProps) {
  const [meta, setMeta] = useState<BotMetaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [previewCommand, setPreviewCommand] = useState("/status");
  const [previewResult, setPreviewResult] = useState<BotPreviewResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadMeta = async () => {
    setLoading(true);
    try {
      const next = await api.getBotMeta();
      setMeta(next);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadMeta();
  }, []);

  const syncTelegram = async () => {
    setSyncing(true);
    try {
      const result = await api.syncTelegramBot();
      setMessage(`Telegram 已同步 ${result.processed_updates} 条更新。`);
      await loadMeta();
    } finally {
      setSyncing(false);
    }
  };

  const bindTelegram = async (chatId: string) => {
    await api.bindTelegramChat(chatId);
    setMessage(`Telegram 默认会话已绑定为 ${chatId}。`);
    await loadMeta();
  };

  const bindFeishu = async () => {
    if (!config.notifier.feishu_receive_id) {
      setMessage("请先在上面的飞书配置里填写默认 receive_id，或在飞书里给机器人发送 /bind。");
      return;
    }
    await api.bindFeishuChat(config.notifier.feishu_receive_id, config.notifier.feishu_receive_id_type);
    setMessage(`飞书默认会话已绑定为 ${config.notifier.feishu_receive_id}。`);
    await loadMeta();
  };

  const preview = async () => {
    const result = await api.previewBotCommand("telegram", previewCommand, meta?.telegram.bound_target_id || "preview-chat");
    setPreviewResult(result);
  };

  if (loading || !meta) {
    return <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 text-slate-300">正在加载机器人控制面板...</div>;
  }

  return (
    <div className="space-y-6 rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-panel">
      <SectionTitle title="机器人控制" hint="这里集中管理 Telegram / 飞书机器人命令菜单、绑定状态和调试入口。" />

      {message ? <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">{message}</div> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-3xl border border-cyan-400/20 bg-cyan-500/5 p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h4 className="text-base font-semibold text-white">Telegram 命令机器人</h4>
              <p className="mt-1 text-sm text-slate-400">{meta.telegram.setup_hint}</p>
            </div>
            <button
              className="rounded-full bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-600"
              disabled={syncing || !meta.telegram.enabled}
              onClick={() => void syncTelegram()}
              type="button"
            >
              {syncing ? "同步中..." : "同步最近消息"}
            </button>
          </div>
          <div className="mt-4 space-y-2 text-sm text-slate-200">
            <div>启用状态：{meta.telegram.enabled ? "已启用" : "未启用"}</div>
            <div>接收方式：{meta.telegram.transport}</div>
            <div>后台任务：{meta.telegram.worker_active ? "运行中" : "未运行"}</div>
            <div>当前绑定：{meta.telegram.bound_target_id || "未绑定"}</div>
            <div>Webhook 兼容路径：{meta.telegram.callback_path}</div>
          </div>

          <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
            <div className="mb-3 text-sm font-semibold text-white">最近识别到的 Telegram 会话</div>
            {meta.telegram.recent_targets.length === 0 ? (
              <div className="text-sm text-slate-400">还没有识别到会话。先给机器人发送任意消息，然后点击“同步最近消息”。</div>
            ) : (
              <div className="space-y-3">
                {meta.telegram.recent_targets.map((target) => (
                  <TelegramTargetRow key={target.id} target={target} onBind={bindTelegram} />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="rounded-3xl border border-emerald-400/20 bg-emerald-500/5 p-5">
          <h4 className="text-base font-semibold text-white">飞书命令机器人</h4>
          <p className="mt-1 text-sm text-slate-400">{meta.feishu.setup_hint}</p>
          <div className="mt-4 space-y-2 text-sm text-slate-200">
            <div>启用状态：{meta.feishu.enabled ? "已启用" : "未启用"}</div>
            <div>接收方式：{meta.feishu.transport}</div>
            <div>当前绑定：{meta.feishu.bound_target_id || "未绑定"}</div>
            <div>事件回调地址：{meta.feishu.callback_path}</div>
          </div>
          <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4 text-sm text-slate-300">
            <div>推荐做法：</div>
            <div className="mt-2">1. 在飞书开放平台启用机器人能力。</div>
            <div>2. 事件订阅方式切换为长连接。</div>
            <div>3. 订阅 im.message.receive_v1 事件。</div>
            <div>4. 保持当前后端服务在线后，在群里给机器人发送 /bind。</div>
          </div>
          <button
            className="mt-4 rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:text-slate-500"
            disabled={!config.notifier.feishu_receive_id}
            onClick={() => void bindFeishu()}
            type="button"
          >
            用当前配置值绑定飞书默认会话
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <h4 className="text-base font-semibold text-white">完整命令菜单</h4>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {meta.commands.map((item) => (
              <div key={item.command} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                <div className="text-sm font-semibold text-white">{item.command}</div>
                <div className="mt-2 text-sm text-slate-300">{item.description}</div>
                <div className="mt-3 text-xs text-slate-500">
                  {item.requires_binding ? "需要已绑定会话" : "任何会话可用"}
                  {item.control ? " · 控制命令" : " · 查询命令"}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <h4 className="text-base font-semibold text-white">命令预览</h4>
          <p className="mt-1 text-sm text-slate-400">不需要真的发到机器人，先看后端会返回什么。</p>
          <input
            className="mt-4 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
            value={previewCommand}
            onChange={(event) => setPreviewCommand(event.target.value)}
            placeholder="例如 /status"
          />
          <button
            className="mt-3 rounded-full bg-white/10 px-4 py-2 text-sm text-slate-100 transition hover:bg-white/20"
            onClick={() => void preview()}
            type="button"
          >
            预览 Telegram 返回内容
          </button>
          {previewResult ? (
            <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4 text-sm text-slate-200">
              <div>识别命令：{previewResult.recognized_command}</div>
              <div className="mt-2">授权状态：{previewResult.authorized ? "已授权" : "未授权"}</div>
              <pre className="mt-3 whitespace-pre-wrap text-slate-300">{previewResult.message}</pre>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function TelegramTargetRow({ target, onBind }: { target: BotTarget; onBind: (chatId: string) => void }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-white">{target.title || target.id}</div>
        <div className="mt-1 text-xs text-slate-400">
          {target.chat_type} · {target.id}
          {target.username ? ` · @${target.username}` : ""}
        </div>
      </div>
      <button
        className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-100 transition hover:bg-white/10"
        onClick={() => onBind(target.id)}
        type="button"
      >
        绑定
      </button>
    </div>
  );
}