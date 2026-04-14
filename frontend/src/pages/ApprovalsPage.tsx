import { useEffect, useState } from "react";

import { api } from "../api/client";
import { ApprovalsTable } from "../components/ApprovalsTable";
import type { ApprovalItem } from "../types";

export function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);

  const load = async () => {
    const rows = await api.getApprovals();
    setApprovals(rows);
  };

  useEffect(() => {
    void load();
  }, []);

  const approve = async (id: number) => {
    await api.approveOrder(id, "前端人工放行");
    await load();
  };

  const reject = async (id: number) => {
    await api.rejectOrder(id, "前端人工驳回");
    await load();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-white">人工审核放行</h1>
        <p className="mt-1 text-sm text-slate-400">展示等待审批的订单，并支持人工通过或驳回。</p>
      </div>
      <ApprovalsTable approvals={approvals} onApprove={approve} onReject={reject} />
    </div>
  );
}
