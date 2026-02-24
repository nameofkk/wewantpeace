"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Flag, CheckCircle, X, Loader2, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Report {
  id: number;
  reporter_nickname: string | null;
  target_type: "post" | "comment" | "user";
  target_id: string;
  reason: string;
  status: "pending" | "resolved" | "dismissed";
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-400",
  resolved: "bg-green-500/20 text-green-400",
  dismissed: "bg-secondary text-muted-foreground",
};

const TARGET_LABELS: Record<string, string> = {
  post: "게시글",
  comment: "댓글",
  user: "회원",
};

export default function AdminReportsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<"pending" | "all">("pending");

  const { data: reports = [], isLoading } = useQuery<Report[]>({
    queryKey: ["admin-reports", statusFilter],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ limit: "50" });
      if (statusFilter !== "all") params.append("status", statusFilter);
      const res = await fetch(`${API_BASE}/admin/reports?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("신고 목록 로드 실패");
      return res.json();
    },
    enabled: !!user,
  });

  const reviewMutation = useMutation({
    mutationFn: async ({ reportId, action }: { reportId: number; action: "resolve" | "dismiss" }) => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const status = action === "resolve" ? "resolved" : "dismissed";
      const res = await fetch(`${API_BASE}/admin/reports/${reportId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error("처리 실패");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-reports"] }),
  });

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">신고 관리</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {reports.filter((r) => r.status === "pending").length}건 처리 대기
          </p>
        </div>

        <div className="flex gap-2">
          {(["pending", "all"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-sm",
                statusFilter === s
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground"
              )}
            >
              {s === "pending" ? "처리 대기" : "전체"}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : reports.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Flag className="h-10 w-10 mb-3" />
          <p className="text-sm">처리할 신고가 없습니다.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((report) => (
            <div
              key={report.id}
              className="rounded-xl border border-border bg-card p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-xs font-medium bg-secondary rounded-full px-2 py-0.5">
                      {TARGET_LABELS[report.target_type]} #{report.target_id.slice(0, 8)}...
                    </span>
                    <span className={cn("text-[10px] rounded-full px-2 py-0.5 font-medium", STATUS_COLORS[report.status])}>
                      {report.status === "pending" ? "대기" : report.status === "resolved" ? "처리됨" : "기각됨"}
                    </span>
                  </div>
                  <p className="text-sm">
                    <span className="font-medium">{report.reporter_nickname || "익명"}</span>
                    {" — "}
                    <span className="text-muted-foreground">{report.reason}</span>
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <p className="text-[11px] text-muted-foreground">
                      {new Date(report.created_at).toLocaleString("ko-KR")}
                    </p>
                    {report.target_type === "post" && (
                      <a
                        href={`/community/${report.target_id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 text-[11px] text-primary hover:underline"
                      >
                        <ExternalLink className="h-3 w-3" />
                        원문 보기
                      </a>
                    )}
                  </div>
                </div>

                {report.status === "pending" && (
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => reviewMutation.mutate({ reportId: report.id, action: "resolve" })}
                      disabled={reviewMutation.isPending}
                      className="flex items-center gap-1 rounded-lg bg-green-500/10 px-3 py-1.5 text-xs text-green-400 hover:bg-green-500/20"
                    >
                      <CheckCircle className="h-3 w-3" />
                      처리
                    </button>
                    <button
                      onClick={() => reviewMutation.mutate({ reportId: report.id, action: "dismiss" })}
                      disabled={reviewMutation.isPending}
                      className="flex items-center gap-1 rounded-lg bg-secondary px-3 py-1.5 text-xs text-muted-foreground hover:bg-border"
                    >
                      <X className="h-3 w-3" />
                      기각
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
