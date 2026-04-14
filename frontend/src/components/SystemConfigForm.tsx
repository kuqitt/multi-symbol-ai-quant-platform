import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { CredentialStatus, SystemConfig, SystemConfigResponse } from "../types";
import { formatBooleanLabel, formatRuntimeValue } from "../utils/display";

interface SystemConfigFormProps {
  data: SystemConfigResponse;
  saving: boolean;
  onSave: (config: SystemConfig, applyImmediately: boolean) => Promise<void>;
}

function FieldLabel({ children }: { children: string }) {
  return <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{children}</label>;
}

function NumberInput({
  value,
  onChange,
  step = "1",
}: {
  value: number;
  onChange: (value: number) => void;
  step?: string;
}) {
  return (
    <input
      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white outline-none transition focus:border-cyan-400"
      type="number"
      value={value}
      step={step}
      onChange={(event) => onChange(Number(event.target.value))}
    />
  );
}

function SecretCard({ title, status }: { title: string; status: CredentialStatus }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
      <h4 className="text-base font-semibold text-white">{title}</h4>
      <div className="mt-3 space-y-2 text-sm text-slate-300">
        <div>API Key：{status.api_key_configured ? status.api_key_masked : "未配置"}</div>
        <div>Secret：{status.secret_configured ? status.secret_masked : "未配置"}</div>
        <div>Passphrase：{formatBooleanLabel(status.passphrase_configured)}</div>
      </div>
    </div>
  );
}

export function SystemConfigForm({ data, saving, onSave }: SystemConfigFormProps) {
  const [draft, setDraft] = useState<SystemConfig>(data.config);
  const [applyImmediately, setApplyImmediately] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [resettingPaper, setResettingPaper] = useState(false);

  useEffect(() => {
    setDraft(data.config);
  }, [data]);

  const save = async () => {
    await onSave(draft, applyImmediately);
    setMessage("系统配置已保存。");
  };

  const reset = () => {
    setDraft(data.config);
    setMessage("已恢复为当前系统配置。");
  };

  const resetPaperAccount = async () => {
    setResettingPaper(true);
    try {
      const result = await api.resetPaperAccount(draft.simulation.starting_balance);
      setMessage(`模拟账户已重置为 ${result.starting_balance.toFixed(2)} USDT。`);
    } finally {
      setResettingPaper(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-panel">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-semibold text-white">系统配置中心</h3>
            <p className="mt-1 text-sm text-slate-400">
              这里维护交易所接入、运行环境、模拟盘账户、通知、认证与 UI 等平台级配置。
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:bg-white/10"
              onClick={reset}
              type="button"
            >
              重置
            </button>
            <button
              className="rounded-full bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-600"
              disabled={saving}
              onClick={() => void save()}
              type="button"
            >
              {saving ? "保存中..." : "保存系统配置"}
            </button>
          </div>
        </div>

        {message ? <div className="mb-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">{message}</div> : null}

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <FieldLabel>交易所</FieldLabel>
                <select
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                  value={draft.exchange}
                  onChange={(event) => setDraft({ ...draft, exchange: event.target.value as SystemConfig["exchange"] })}
                >
                  <option value="okx">OKX</option>
                  <option value="binance">Binance</option>
                </select>
              </div>
              <div>
                <FieldLabel>运行环境</FieldLabel>
                <select
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                  value={draft.env}
                  onChange={(event) => setDraft({ ...draft, env: event.target.value as SystemConfig["env"] })}
                >
                  <option value="paper">{formatRuntimeValue("paper")}</option>
                  <option value="testnet">{formatRuntimeValue("testnet")}</option>
                  <option value="demo">{formatRuntimeValue("demo")}</option>
                  <option value="live">{formatRuntimeValue("live")}</option>
                </select>
              </div>
              <div>
                <FieldLabel>市场类型</FieldLabel>
                <select
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                  value={draft.market_type}
                  onChange={(event) => setDraft({ ...draft, market_type: event.target.value as SystemConfig["market_type"] })}
                >
                  <option value="spot">{formatRuntimeValue("spot")}</option>
                  <option value="futures">{formatRuntimeValue("futures")}</option>
                </select>
              </div>
              <div>
                <FieldLabel>日志级别</FieldLabel>
                <input
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                  value={draft.logging.level}
                  onChange={(event) => setDraft({ ...draft, logging: { ...draft.logging, level: event.target.value.toUpperCase() } })}
                />
              </div>
              <div>
                <FieldLabel>访问令牌有效期（分钟）</FieldLabel>
                <NumberInput
                  value={draft.auth.access_token_ttl_minutes}
                  onChange={(value) => setDraft({ ...draft, auth: { ...draft.auth, access_token_ttl_minutes: value } })}
                />
              </div>
              <div>
                <FieldLabel>前端刷新间隔（毫秒）</FieldLabel>
                <NumberInput
                  value={draft.ui.refresh_interval_ms}
                  onChange={(value) => setDraft({ ...draft, ui: { ...draft.ui, refresh_interval_ms: value } })}
                  step="100"
                />
              </div>
              <div>
                <FieldLabel>图表点数上限</FieldLabel>
                <NumberInput
                  value={draft.ui.chart_points_limit}
                  onChange={(value) => setDraft({ ...draft, ui: { ...draft.ui, chart_points_limit: value } })}
                  step="10"
                />
              </div>
              <div>
                <FieldLabel>审批超时（秒）</FieldLabel>
                <NumberInput
                  value={draft.approval.approval_timeout_seconds}
                  onChange={(value) => setDraft({ ...draft, approval: { ...draft.approval, approval_timeout_seconds: value } })}
                />
              </div>
              <div>
                <FieldLabel>小资金免审阈值（USDT）</FieldLabel>
                <NumberInput
                  value={draft.approval.auto_approve_below_equity}
                  onChange={(value) => setDraft({ ...draft, approval: { ...draft.approval, auto_approve_below_equity: value } })}
                  step="100"
                />
              </div>
              <div>
                <FieldLabel>大额订单审批阈值</FieldLabel>
                <NumberInput
                  value={draft.approval.approval_min_notional}
                  onChange={(value) => setDraft({ ...draft, approval: { ...draft.approval, approval_min_notional: value } })}
                  step="100"
                />
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h4 className="text-base font-semibold text-white">模拟账户</h4>
                  <p className="mt-1 text-sm text-slate-400">给策略一个明确的纸面资金起点，并控制模拟盘费用与保护阈值。</p>
                </div>
                <button
                  className="rounded-full bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600"
                  disabled={resettingPaper || draft.env !== "paper"}
                  onClick={() => void resetPaperAccount()}
                  type="button"
                >
                  {resettingPaper ? "重置中..." : "重置模拟账户"}
                </button>
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div>
                  <FieldLabel>初始资金（USDT）</FieldLabel>
                  <NumberInput
                    value={draft.simulation.starting_balance}
                    onChange={(value) => setDraft({ ...draft, simulation: { ...draft.simulation, starting_balance: value } })}
                    step="100"
                  />
                </div>
                <div>
                  <FieldLabel>手续费率</FieldLabel>
                  <NumberInput
                    value={draft.simulation.fee_rate}
                    onChange={(value) => setDraft({ ...draft, simulation: { ...draft.simulation, fee_rate: value } })}
                    step="0.0001"
                  />
                </div>
                <div>
                  <FieldLabel>滑点阈值倍率</FieldLabel>
                  <NumberInput
                    value={draft.simulation.max_slippage_multiplier}
                    onChange={(value) =>
                      setDraft({ ...draft, simulation: { ...draft.simulation, max_slippage_multiplier: value } })
                    }
                    step="0.1"
                  />
                </div>
                <div>
                  <FieldLabel>点差阈值倍率</FieldLabel>
                  <NumberInput
                    value={draft.simulation.max_spread_multiplier}
                    onChange={(value) =>
                      setDraft({ ...draft, simulation: { ...draft.simulation, max_spread_multiplier: value } })
                    }
                    step="0.1"
                  />
                </div>
              </div>
              <label className="mt-4 flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={draft.simulation.use_live_market_data}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      simulation: { ...draft.simulation, use_live_market_data: event.target.checked },
                    })
                  }
                />
                模拟盘使用交易所实时行情，不使用本地模拟报价
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={draft.simulation.reset_account_on_start}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      simulation: { ...draft.simulation, reset_account_on_start: event.target.checked },
                    })
                  }
                />
                启动策略时自动把模拟账户重置到初始资金
              </label>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={draft.approval.enabled}
                  onChange={(event) => setDraft({ ...draft, approval: { ...draft.approval, enabled: event.target.checked } })}
                />
                开启人工审核流程
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={draft.approval.require_manual_approval_for_live}
                  onChange={(event) =>
                    setDraft({ ...draft, approval: { ...draft.approval, require_manual_approval_for_live: event.target.checked } })
                  }
                />
                实盘订单必须人工审批
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={draft.approval.require_manual_approval_for_large_orders}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      approval: { ...draft.approval, require_manual_approval_for_large_orders: event.target.checked },
                    })
                  }
                />
                大额订单必须人工审批
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={draft.approval.auto_approve_small_accounts}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      approval: { ...draft.approval, auto_approve_small_accounts: event.target.checked },
                    })
                  }
                />
                总权益低于阈值时自动放行，不进入人工审核
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={draft.notifier.telegram_enabled}
                  onChange={(event) => setDraft({ ...draft, notifier: { ...draft.notifier, telegram_enabled: event.target.checked } })}
                />
                启用 Telegram 告警
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={draft.notifier.feishu_enabled}
                  onChange={(event) => setDraft({ ...draft, notifier: { ...draft.notifier, feishu_enabled: event.target.checked } })}
                />
                启用飞书告警
              </label>
            </div>

            {draft.notifier.telegram_enabled ? (
              <div className="rounded-3xl border border-cyan-400/20 bg-cyan-500/5 p-5">
                <h4 className="text-base font-semibold text-white">Telegram 机器人配置</h4>
                <p className="mt-1 text-sm text-slate-400">
                  根据 Telegram Bot API，鉴权只需要 Bot Token。系统会优先用这里的 Token 发消息；如果未填写 Chat ID，会自动从机器人最近收到的会话里识别。
                </p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div>
                    <FieldLabel>Bot Token</FieldLabel>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                      placeholder="例如 123456:ABC-DEF"
                      value={draft.notifier.telegram_bot_token}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          notifier: { ...draft.notifier, telegram_bot_token: event.target.value },
                        })
                      }
                    />
                  </div>
                  <div>
                    <FieldLabel>Chat ID（通常可留空）</FieldLabel>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                      placeholder="不填则自动从最近会话识别"
                      value={draft.notifier.telegram_chat_id}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          notifier: { ...draft.notifier, telegram_chat_id: event.target.value },
                        })
                      }
                    />
                  </div>
                </div>
              </div>
            ) : null}

            {draft.notifier.feishu_enabled ? (
              <div className="rounded-3xl border border-emerald-400/20 bg-emerald-500/5 p-5">
                <h4 className="text-base font-semibold text-white">飞书机器人配置</h4>
                <p className="mt-1 text-sm text-slate-400">
                  根据飞书应用机器人文档，默认先填写 App ID 和 App Secret 获取 tenant_access_token。若需主动推送到固定用户或群，再补充默认接收者信息。
                </p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div>
                    <FieldLabel>App ID</FieldLabel>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                      placeholder="例如 cli_xxxxxxxxxxxx"
                      value={draft.notifier.feishu_app_id}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          notifier: { ...draft.notifier, feishu_app_id: event.target.value },
                        })
                      }
                    />
                  </div>
                  <div>
                    <FieldLabel>App Secret</FieldLabel>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                      placeholder="例如 xxxxxxxxxxxxxxxx"
                      value={draft.notifier.feishu_app_secret}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          notifier: { ...draft.notifier, feishu_app_secret: event.target.value },
                        })
                      }
                    />
                  </div>
                  <div>
                    <FieldLabel>默认接收者 ID（可选）</FieldLabel>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                      placeholder="例如 open_id 或 chat_id"
                      value={draft.notifier.feishu_receive_id}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          notifier: { ...draft.notifier, feishu_receive_id: event.target.value },
                        })
                      }
                    />
                  </div>
                  <div>
                    <FieldLabel>接收者 ID 类型</FieldLabel>
                    <select
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                      value={draft.notifier.feishu_receive_id_type}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          notifier: {
                            ...draft.notifier,
                            feishu_receive_id_type: event.target.value as SystemConfig["notifier"]["feishu_receive_id_type"],
                          },
                        })
                      }
                    >
                      <option value="chat_id">chat_id</option>
                      <option value="open_id">open_id</option>
                      <option value="user_id">user_id</option>
                      <option value="union_id">union_id</option>
                      <option value="email">email</option>
                    </select>
                  </div>
                  <div className="sm:col-span-2">
                    <FieldLabel>Webhook URL（兼容旧配置，可选）</FieldLabel>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                      placeholder="旧版自定义机器人地址，不填则优先走 App ID / App Secret"
                      value={draft.notifier.feishu_webhook_url}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          notifier: { ...draft.notifier, feishu_webhook_url: event.target.value },
                        })
                      }
                    />
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="space-y-5">
            <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
              <h4 className="text-base font-semibold text-white">OKX 接入配置</h4>
              <div className="mt-4 grid gap-4">
                <div>
                  <FieldLabel>REST Base URL</FieldLabel>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                    value={draft.connectors.okx.base_url}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        connectors: { ...draft.connectors, okx: { ...draft.connectors.okx, base_url: event.target.value } },
                      })
                    }
                  />
                </div>
                <div>
                  <FieldLabel>公共 WS URL</FieldLabel>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                    value={draft.connectors.okx.public_ws_url}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        connectors: { ...draft.connectors, okx: { ...draft.connectors.okx, public_ws_url: event.target.value } },
                      })
                    }
                  />
                </div>
                <div>
                  <FieldLabel>Demo / Testnet WS URL</FieldLabel>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                    value={draft.connectors.okx.demo_public_ws_url}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        connectors: { ...draft.connectors, okx: { ...draft.connectors.okx, demo_public_ws_url: event.target.value } },
                      })
                    }
                  />
                </div>
                <div>
                  <FieldLabel>Demo Broker ID</FieldLabel>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                    value={draft.connectors.okx.demo_broker_id}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        connectors: { ...draft.connectors, okx: { ...draft.connectors.okx, demo_broker_id: event.target.value } },
                      })
                    }
                  />
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
              <h4 className="text-base font-semibold text-white">Binance 接入配置</h4>
              <div className="mt-4 grid gap-4">
                <div>
                  <FieldLabel>REST Base URL</FieldLabel>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                    value={draft.connectors.binance.base_url}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        connectors: { ...draft.connectors, binance: { ...draft.connectors.binance, base_url: event.target.value } },
                      })
                    }
                  />
                </div>
                <div>
                  <FieldLabel>Testnet Base URL</FieldLabel>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                    value={draft.connectors.binance.testnet_base_url}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        connectors: {
                          ...draft.connectors,
                          binance: { ...draft.connectors.binance, testnet_base_url: event.target.value },
                        },
                      })
                    }
                  />
                </div>
                <div>
                  <FieldLabel>公共 WS URL</FieldLabel>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                    value={draft.connectors.binance.public_ws_url}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        connectors: {
                          ...draft.connectors,
                          binance: { ...draft.connectors.binance, public_ws_url: event.target.value },
                        },
                      })
                    }
                  />
                </div>
                <div>
                  <FieldLabel>Testnet WS URL</FieldLabel>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                    value={draft.connectors.binance.testnet_public_ws_url}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        connectors: {
                          ...draft.connectors,
                          binance: { ...draft.connectors.binance, testnet_public_ws_url: event.target.value },
                        },
                      })
                    }
                  />
                </div>
              </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <SecretCard title="OKX 环境变量状态" status={data.okx_credentials} />
              <SecretCard title="Binance 环境变量状态" status={data.binance_credentials} />
            </div>
          </div>
        </div>

        <div className="mt-6 rounded-3xl border border-white/10 bg-white/5 p-5 text-sm text-slate-300">
          <p>密钥来源：{data.secrets_source}</p>
          <p className="mt-2">实盘开关：{formatBooleanLabel(data.live_trading_enabled)}</p>
          <p className="mt-2">数据库热更新：{formatBooleanLabel(data.database_hot_reload_supported)}</p>
          <p className="mt-2">
            说明：API Key / Secret / Passphrase 只从环境变量读取，不会写入系统配置或业务参数配置。
          </p>
          <label className="mt-4 flex items-center gap-3 text-sm text-slate-200">
            <input
              className="h-4 w-4 rounded border-white/20 bg-slate-950"
              type="checkbox"
              checked={applyImmediately}
              onChange={(event) => setApplyImmediately(event.target.checked)}
            />
            保存后立即热更新
          </label>
        </div>
      </div>
    </div>
  );
}
