from __future__ import annotations

import asyncio
import logging

from app.models import Position
from app.risk_manager import RiskManager, TradeIntent


def test_risk_manager_blocks_martingale(session, config, state, adapter) -> None:
  ticker = asyncio.run(adapter.fetch_ticker("BTC/USDT"))
  session.add(
      Position(
          symbol="BTC/USDT",
          strategy_name="ma_rsi",
          quantity=1.0,
          avg_price=ticker.price * 1.1,
          market_price=ticker.price,
          market_value=ticker.price,
          unrealized_pnl=-0.1 * ticker.price,
      )
  )
  session.commit()

  manager = RiskManager(state, logging.getLogger("test-risk"))
  result = asyncio.run(
      manager.evaluate(
          session=session,
          config=config,
          adapter=adapter,
          metrics_summary={"equity": 100000.0, "daily_pnl": 0.0},
          intent=TradeIntent(
              symbol="BTC/USDT",
              side="BUY",
              quantity=0.01,
              expected_price=ticker.price,
              order_type="market",
              signal_id="sig-1",
              strategy_name="ma_rsi",
              stop_loss=ticker.price * 0.98,
          ),
      )
  )
  assert result.allowed is False
  assert result.reason == "martingale-blocked"
