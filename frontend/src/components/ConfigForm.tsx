import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { BusinessConfig } from "../types";
import { formatRuntimeValue } from "../utils/display";

interface ConfigFormProps {
  config: BusinessConfig;
  saving: boolean;
  onSave: (config: BusinessConfig, applyImmediately: boolean) => Promise<void>;
}

function FieldLabel({ children }: { children: string }) {
  return <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{children}</label>;
}

function SectionCard({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
      <div className="mb-4">
        <h4 className="text-base font-semibold text-white">{title}</h4>
        <p className="mt-1 text-sm text-slate-400">{description}</p>
      </div>
      <div className="grid gap-5 sm:grid-cols-2">{children}</div>
    </div>
  );
}

function NumberInput({
  value,
  onChange,
  step = "0.1",
}: {
  value: number;
  onChange: (next: number) => void;
  step?: string;
}) {
  return (
    <input
      className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white outline-none ring-0 transition focus:border-cyan-400"
      type="number"
      value={value}
      step={step}
      onChange={(event) => onChange(Number(event.target.value))}
    />
  );
}

export function ConfigForm({ config, saving, onSave }: ConfigFormProps) {
  const [draft, setDraft] = useState<BusinessConfig>(config);
  const [applyImmediately, setApplyImmediately] = useState(true);
  const [symbolsText, setSymbolsText] = useState(config.symbols.join(", "));
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setDraft(config);
    setSymbolsText(config.symbols.join(", "));
  }, [config]);

  const validationError = useMemo(() => {
    if (draft.strategy.ma_fast >= draft.strategy.ma_slow) {
      return "短周期均线必须小于长周期均线。";
    }
    if (!symbolsText.split(",").map((item) => item.trim()).filter(Boolean).length) {
      return "至少需要配置一个交易对。";
    }
    return null;
  }, [draft, symbolsText]);

  const save = async () => {
    if (validationError) {
      setMessage(validationError);
      return;
    }
    const normalized: BusinessConfig = {
      ...draft,
      symbols: symbolsText
        .split(",")
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean),
    };
    await onSave(normalized, applyImmediately);
    setMessage("业务参数已保存并回显。");
  };

  const reset = () => {
    setDraft(config);
    setSymbolsText(config.symbols.join(", "));
    setMessage("已恢复为当前业务参数配置。");
  };

  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-panel">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-xl font-semibold text-white">业务参数配置</h3>
          <p className="mt-1 text-sm text-slate-400">这里只维护 symbols、时间周期、策略、风控和执行参数。</p>
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
            {saving ? "保存中..." : "保存参数"}
          </button>
        </div>
      </div>

      {message ? <div className="mb-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">{message}</div> : null}
      {validationError ? <div className="mb-4 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{validationError}</div> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-5">
          <div>
            <FieldLabel>交易对列表</FieldLabel>
            <input
              className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white outline-none transition focus:border-cyan-400"
              value={symbolsText}
              onChange={(event) => setSymbolsText(event.target.value)}
            />
          </div>

          <div>
            <FieldLabel>K 线周期</FieldLabel>
            <input
              className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
              value={draft.timeframe}
              onChange={(event) => setDraft({ ...draft, timeframe: event.target.value })}
            />
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <FieldLabel>短周期均线</FieldLabel>
              <NumberInput value={draft.strategy.ma_fast} onChange={(value) => setDraft({ ...draft, strategy: { ...draft.strategy, ma_fast: value } })} step="1" />
            </div>
            <div>
              <FieldLabel>长周期均线</FieldLabel>
              <NumberInput value={draft.strategy.ma_slow} onChange={(value) => setDraft({ ...draft, strategy: { ...draft.strategy, ma_slow: value } })} step="1" />
            </div>
            <div>
              <FieldLabel>RSI 周期</FieldLabel>
              <NumberInput value={draft.strategy.rsi_period} onChange={(value) => setDraft({ ...draft, strategy: { ...draft.strategy, rsi_period: value } })} step="1" />
            </div>
            <div>
              <FieldLabel>ATR 周期</FieldLabel>
              <NumberInput value={draft.strategy.atr_period} onChange={(value) => setDraft({ ...draft, strategy: { ...draft.strategy, atr_period: value } })} step="1" />
            </div>
            <div>
              <FieldLabel>RSI 买入阈值</FieldLabel>
              <NumberInput value={draft.strategy.rsi_buy_threshold} onChange={(value) => setDraft({ ...draft, strategy: { ...draft.strategy, rsi_buy_threshold: value } })} />
            </div>
            <div>
              <FieldLabel>RSI 卖出阈值</FieldLabel>
              <NumberInput value={draft.strategy.rsi_sell_threshold} onChange={(value) => setDraft({ ...draft, strategy: { ...draft.strategy, rsi_sell_threshold: value } })} />
            </div>
            <div>
              <FieldLabel>止损 ATR 倍数</FieldLabel>
              <NumberInput
                value={draft.strategy.stop_loss_atr_multiple}
                onChange={(value) => setDraft({ ...draft, strategy: { ...draft.strategy, stop_loss_atr_multiple: value } })}
              />
            </div>
            <div>
              <FieldLabel>止盈 ATR 倍数</FieldLabel>
              <NumberInput
                value={draft.strategy.take_profit_atr_multiple}
                onChange={(value) => setDraft({ ...draft, strategy: { ...draft.strategy, take_profit_atr_multiple: value } })}
              />
            </div>
          </div>
        </div>

        <div className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <FieldLabel>单笔风险比例</FieldLabel>
              <NumberInput value={draft.risk.risk_per_trade} onChange={(value) => setDraft({ ...draft, risk: { ...draft.risk, risk_per_trade: value } })} step="0.001" />
            </div>
            <div>
              <FieldLabel>日内最大亏损</FieldLabel>
              <NumberInput value={draft.risk.max_daily_loss} onChange={(value) => setDraft({ ...draft, risk: { ...draft.risk, max_daily_loss: value } })} step="0.001" />
            </div>
            <div>
              <FieldLabel>单币种最大敞口</FieldLabel>
              <NumberInput value={draft.risk.max_symbol_exposure} onChange={(value) => setDraft({ ...draft, risk: { ...draft.risk, max_symbol_exposure: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>账户最大总敞口</FieldLabel>
              <NumberInput value={draft.risk.max_total_exposure} onChange={(value) => setDraft({ ...draft, risk: { ...draft.risk, max_total_exposure: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>策略最大敞口</FieldLabel>
              <NumberInput value={draft.risk.max_strategy_exposure} onChange={(value) => setDraft({ ...draft, risk: { ...draft.risk, max_strategy_exposure: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>组合热度上限</FieldLabel>
              <NumberInput value={draft.risk.max_portfolio_heat} onChange={(value) => setDraft({ ...draft, risk: { ...draft.risk, max_portfolio_heat: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>最大连续亏损次数</FieldLabel>
              <NumberInput value={draft.risk.max_consecutive_losses} onChange={(value) => setDraft({ ...draft, risk: { ...draft.risk, max_consecutive_losses: value } })} step="1" />
            </div>
            <div>
              <FieldLabel>最大滑点</FieldLabel>
              <NumberInput value={draft.risk.max_slippage} onChange={(value) => setDraft({ ...draft, risk: { ...draft.risk, max_slippage: value } })} step="0.0001" />
            </div>
            <div>
              <FieldLabel>最大点差</FieldLabel>
              <NumberInput value={draft.risk.max_spread} onChange={(value) => setDraft({ ...draft, risk: { ...draft.risk, max_spread: value } })} step="0.0001" />
            </div>
            <div>
              <FieldLabel>重试次数</FieldLabel>
              <NumberInput value={draft.execution.retry_count} onChange={(value) => setDraft({ ...draft, execution: { ...draft.execution, retry_count: value } })} step="1" />
            </div>
            <div>
              <FieldLabel>下单类型</FieldLabel>
              <select
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                value={draft.execution.order_type}
                onChange={(event) => setDraft({ ...draft, execution: { ...draft.execution, order_type: event.target.value as "market" | "limit" } })}
              >
                <option value="market">{formatRuntimeValue("market")}</option>
                <option value="limit">{formatRuntimeValue("limit")}</option>
              </select>
            </div>
          </div>

          <SectionCard title="市场状态识别" description="定义趋势、波动和状态识别的窗口与阈值。">
            <div>
              <FieldLabel>启用状态识别</FieldLabel>
              <select
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                value={String(draft.regime.enabled)}
                onChange={(event) => setDraft({ ...draft, regime: { ...draft.regime, enabled: event.target.value === "true" } })}
              >
                <option value="true">开启</option>
                <option value="false">关闭</option>
              </select>
            </div>
            <div>
              <FieldLabel>趋势回看窗口</FieldLabel>
              <NumberInput value={draft.regime.trend_lookback} onChange={(value) => setDraft({ ...draft, regime: { ...draft.regime, trend_lookback: value } })} step="1" />
            </div>
            <div>
              <FieldLabel>趋势强度阈值</FieldLabel>
              <NumberInput value={draft.regime.trend_strength_threshold} onChange={(value) => setDraft({ ...draft, regime: { ...draft.regime, trend_strength_threshold: value } })} step="0.001" />
            </div>
            <div>
              <FieldLabel>高波动阈值</FieldLabel>
              <NumberInput value={draft.regime.high_volatility_threshold} onChange={(value) => setDraft({ ...draft, regime: { ...draft.regime, high_volatility_threshold: value } })} step="0.001" />
            </div>
            <div>
              <FieldLabel>低波动阈值</FieldLabel>
              <NumberInput value={draft.regime.low_volatility_threshold} onChange={(value) => setDraft({ ...draft, regime: { ...draft.regime, low_volatility_threshold: value } })} step="0.001" />
            </div>
            <div>
              <FieldLabel>状态置信度下限</FieldLabel>
              <NumberInput value={draft.regime.confidence_floor} onChange={(value) => setDraft({ ...draft, regime: { ...draft.regime, confidence_floor: value } })} step="0.01" />
            </div>
          </SectionCard>

          <SectionCard title="信号评分策略" description="统一买卖分数、AI 权重、状态权重和突破加权。">
            <div>
              <FieldLabel>最小信号分数</FieldLabel>
              <NumberInput value={draft.signal.min_signal_score} onChange={(value) => setDraft({ ...draft, signal: { ...draft.signal, min_signal_score: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>AI 权重</FieldLabel>
              <NumberInput value={draft.signal.ai_weight} onChange={(value) => setDraft({ ...draft, signal: { ...draft.signal, ai_weight: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>状态权重</FieldLabel>
              <NumberInput value={draft.signal.regime_weight} onChange={(value) => setDraft({ ...draft, signal: { ...draft.signal, regime_weight: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>动量权重</FieldLabel>
              <NumberInput value={draft.signal.momentum_weight} onChange={(value) => setDraft({ ...draft, signal: { ...draft.signal, momentum_weight: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>均值回归权重</FieldLabel>
              <NumberInput value={draft.signal.mean_reversion_weight} onChange={(value) => setDraft({ ...draft, signal: { ...draft.signal, mean_reversion_weight: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>突破权重</FieldLabel>
              <NumberInput value={draft.signal.breakout_weight} onChange={(value) => setDraft({ ...draft, signal: { ...draft.signal, breakout_weight: value } })} step="0.01" />
            </div>
          </SectionCard>

          <SectionCard title="仓位分配器" description="根据账户权益、状态和信号评分给出目标仓位。">
            <div>
              <FieldLabel>启用分配器</FieldLabel>
              <select
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                value={String(draft.allocation.enabled)}
                onChange={(event) => setDraft({ ...draft, allocation: { ...draft.allocation, enabled: event.target.value === "true" } })}
              >
                <option value="true">开启</option>
                <option value="false">关闭</option>
              </select>
            </div>
            <div>
              <FieldLabel>基础风险预算</FieldLabel>
              <NumberInput value={draft.allocation.base_risk_budget} onChange={(value) => setDraft({ ...draft, allocation: { ...draft.allocation, base_risk_budget: value } })} step="0.05" />
            </div>
            <div>
              <FieldLabel>最小名义仓位占比</FieldLabel>
              <NumberInput value={draft.allocation.min_notional_ratio} onChange={(value) => setDraft({ ...draft, allocation: { ...draft.allocation, min_notional_ratio: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>最大名义仓位占比</FieldLabel>
              <NumberInput value={draft.allocation.max_notional_ratio} onChange={(value) => setDraft({ ...draft, allocation: { ...draft.allocation, max_notional_ratio: value } })} step="0.01" />
            </div>
            <div>
              <FieldLabel>最大并发持仓数</FieldLabel>
              <NumberInput value={draft.allocation.max_concurrent_positions} onChange={(value) => setDraft({ ...draft, allocation: { ...draft.allocation, max_concurrent_positions: value } })} step="1" />
            </div>
          </SectionCard>

          <SectionCard title="成本模型" description="将手续费、点差和冲击成本纳入决策。">
            <div>
              <FieldLabel>启用成本模型</FieldLabel>
              <select
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-white"
                value={String(draft.cost_model.enabled)}
                onChange={(event) => setDraft({ ...draft, cost_model: { ...draft.cost_model, enabled: event.target.value === "true" } })}
              >
                <option value="true">开启</option>
                <option value="false">关闭</option>
              </select>
            </div>
            <div>
              <FieldLabel>Taker 手续费(bps)</FieldLabel>
              <NumberInput value={draft.cost_model.taker_fee_bps} onChange={(value) => setDraft({ ...draft, cost_model: { ...draft.cost_model, taker_fee_bps: value } })} step="0.1" />
            </div>
            <div>
              <FieldLabel>点差滑点权重</FieldLabel>
              <NumberInput value={draft.cost_model.slippage_spread_weight} onChange={(value) => setDraft({ ...draft, cost_model: { ...draft.cost_model, slippage_spread_weight: value } })} step="0.05" />
            </div>
            <div>
              <FieldLabel>冲击成本权重</FieldLabel>
              <NumberInput value={draft.cost_model.impact_weight} onChange={(value) => setDraft({ ...draft, cost_model: { ...draft.cost_model, impact_weight: value } })} step="0.05" />
            </div>
            <div>
              <FieldLabel>最大允许总成本(bps)</FieldLabel>
              <NumberInput value={draft.cost_model.max_cost_bps} onChange={(value) => setDraft({ ...draft, cost_model: { ...draft.cost_model, max_cost_bps: value } })} step="0.5" />
            </div>
            <div>
              <FieldLabel>卖出分数缓冲</FieldLabel>
              <NumberInput value={draft.signal.sell_score_buffer} onChange={(value) => setDraft({ ...draft, signal: { ...draft.signal, sell_score_buffer: value } })} step="0.01" />
            </div>
          </SectionCard>

          <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
            <label className="flex items-center gap-3 text-sm text-slate-200">
              <input
                className="h-4 w-4 rounded border-white/20 bg-slate-950"
                type="checkbox"
                checked={applyImmediately}
                onChange={(event) => setApplyImmediately(event.target.checked)}
              />
              保存后立即生效
            </label>
            <p className="mt-3 text-sm text-slate-400">
              这里的业务参数支持热更新；如果修改了 symbols 或 timeframe，系统会自动重建行情订阅。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
