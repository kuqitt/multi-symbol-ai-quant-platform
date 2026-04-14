export function formatRuntimeValue(value: string): string {
  const map: Record<string, string> = {
    RUNNING: "运行中",
    PAUSED: "已暂停",
    STOPPED: "已停止",
    PROTECT_MODE: "保护模式",
    CONNECTED: "已连接",
    DISCONNECTED: "连接断开",
    NORMAL: "正常",
    HALTED: "已停机",
    paper: "模拟盘",
    testnet: "测试网",
    demo: "演示盘",
    live: "实盘",
    BUY: "买入",
    SELL: "卖出",
    HOLD: "观望",
    LONG: "多头",
    SHORT: "空头",
    NEW: "新建",
    OPEN: "挂单中",
    FILLED: "已成交",
    CANCELED: "已撤单",
    REJECTED: "已拒绝",
    ERROR: "异常",
    PENDING_APPROVAL: "待审批",
    APPROVED: "已通过",
    market: "市价",
    limit: "限价",
    spot: "现货",
    futures: "合约",
    trending_up: "上升趋势",
    trending_down: "下降趋势",
    range: "震荡区间",
    volatile: "高波动",
    unknown: "未知",
    simulated: "模拟报价",
    YES: "是",
    NO: "否",
  };

  return map[value] ?? value.replaceAll("_", " ");
}

export function formatPriceSourceValue(value: string): string {
  const map: Record<string, string> = {
    live: "实时交易所",
    simulated: "模拟报价",
  };

  return map[value] ?? formatRuntimeValue(value);
}

export function formatBooleanLabel(value: boolean): string {
  return value ? "是" : "否";
}
