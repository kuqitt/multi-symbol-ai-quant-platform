import { useState } from "react";

import { DecisionDetailDrawer } from "./DecisionDetailDrawer";
import { formatRuntimeValue } from "../utils/display";
import type { ApprovalItem } from "../types";
import { formatReasonText } from "../utils/logDisplay";

interface ApprovalsTableProps {
  approvals: ApprovalItem[];
  onApprove: (id: number) => Promise<void>;
  onReject: (id: number) => Promise<void>;
}

export function ApprovalsTable({ approvals, onApprove, onReject }: ApprovalsTableProps) {
  const [selectedApproval, setSelectedApproval] = useState<ApprovalItem | null>(null);

  return (
    <>
      <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-panel">
        <div className="border-b border-white/10 px-5 py-4">
          <h3 className="text-lg font-semibold text-white">待审核订单</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-slate-300">
              <tr>
                {["ID", "交易对", "方向", "数量", "预期价格", "名义价值", "状态", "原因", "申请人", "详情", "操作"].map((label) => (
                  <th key={label} className="px-4 py-3 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-100">
              {approvals.map((approval) => (
                <tr key={approval.id}>
                  <td className="px-4 py-3">{approval.id}</td>
                  <td className="px-4 py-3">{approval.symbol}</td>
                  <td className="px-4 py-3">{formatRuntimeValue(approval.side)}</td>
                  <td className="px-4 py-3">{approval.quantity.toFixed(6)}</td>
                  <td className="px-4 py-3">{approval.expected_price.toFixed(4)}</td>
                  <td className="px-4 py-3">{approval.notional.toFixed(2)}</td>
                  <td className="px-4 py-3">{formatRuntimeValue(approval.status)}</td>
                  <td className="px-4 py-3">{formatReasonText(approval.reason)}</td>
                  <td className="px-4 py-3">{approval.requested_by}</td>
                  <td className="px-4 py-3">
                    <button className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-200 hover:bg-white/10" onClick={() => setSelectedApproval(approval)}>
                      查看
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button className="rounded-full bg-emerald-400 px-3 py-1 text-slate-950" onClick={() => void onApprove(approval.id)}>
                        通过
                      </button>
                      <button className="rounded-full bg-rose-500 px-3 py-1 text-white" onClick={() => void onReject(approval.id)}>
                        驳回
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {approvals.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-slate-400" colSpan={11}>
                    当前没有待处理审批。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
      <DecisionDetailDrawer
        open={Boolean(selectedApproval)}
        title={selectedApproval ? `${selectedApproval.symbol} 审批详情` : ""}
        subtitle={selectedApproval ? `${formatRuntimeValue(selectedApproval.side)} · ${formatRuntimeValue(selectedApproval.status)}` : undefined}
        data={selectedApproval ? { ...selectedApproval, ...(selectedApproval.request_payload ?? {}), approval_reason: selectedApproval.reason } : null}
        onClose={() => setSelectedApproval(null)}
      />
    </>
  );
}
