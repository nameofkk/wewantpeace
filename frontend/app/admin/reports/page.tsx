"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Flag, CheckCircle, X, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useAdminToast } from "@/components/ui/admin-toast";
import { API_BASE } from "@/lib/admin-utils";

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

export default function AdminReportsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const lang = useAppStore((s) => s.lang);
  const { toast } = useAdminToast();
  const [statusFilter, setStatusFilter] = useState<"pending" | "all">("pending");

  const locale = lang === "en" ? "en-US" : "ko-KR";

  const getTargetLabel = (type: string) => {
    const map: Record<string, string> = {
      post: t(lang, "admin_report_target_post"),
      comment: t(lang, "admin_report_target_comment"),
      user: t(lang, "admin_report_target_user"),
    };
    return map[type] ?? type;
  };

  const getStatusLabel = (status: string) => {
    if (status === "pending") return t(lang, "admin_report_pending");
    if (status === "resolved") return t(lang, "admin_report_resolved");
    return t(lang, "admin_report_dismissed");
  };

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
      if (!res.ok) throw new Error("Failed to load reports");
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
      if (!res.ok) throw new Error("Failed to update report");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-reports"] });
      toast(t(lang, "admin_toast_updated"), "success");
    },
    onError: () => toast(t(lang, "admin_toast_error"), "error"),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_reports_title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t(lang, "admin_reports_subtitle", { n: reports.filter((r) => r.status === "pending").length })}
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
              {s === "pending" ? t(lang, "admin_report_pending") : t(lang, "admin_all")}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
              <div className="flex gap-2">
                <div className="h-5 w-24 rounded-full bg-secondary" />
                <div className="h-5 w-12 rounded-full bg-secondary" />
              </div>
              <div className="h-4 w-3/4 rounded bg-secondary" />
              <div className="h-3 w-32 rounded bg-secondary" />
            </div>
          ))}
        </div>
      ) : reports.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Flag className="h-10 w-10 mb-3" />
          <p className="text-sm">{t(lang, "admin_reports_empty")}</p>
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
                      {getTargetLabel(report.target_type)} #{report.target_id.slice(0, 8)}...
                    </span>
                    <span className={cn("text-[10px] rounded-full px-2 py-0.5 font-medium", STATUS_COLORS[report.status])}>
                      {getStatusLabel(report.status)}
                    </span>
                  </div>
                  <p className="text-sm">
                    <span className="font-medium">{report.reporter_nickname || t(lang, "admin_report_anonymous")}</span>
                    {" — "}
                    <span className="text-muted-foreground">{report.reason}</span>
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <p className="text-[11px] text-muted-foreground">
                      {new Date(report.created_at).toLocaleString(locale)}
                    </p>
                    {report.target_type === "post" && (
                      <a
                        href={`/community/${report.target_id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 text-[11px] text-primary hover:underline"
                      >
                        <ExternalLink className="h-3 w-3" />
                        {t(lang, "admin_report_view_original")}
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
                      {t(lang, "admin_report_resolve")}
                    </button>
                    <button
                      onClick={() => reviewMutation.mutate({ reportId: report.id, action: "dismiss" })}
                      disabled={reviewMutation.isPending}
                      className="flex items-center gap-1 rounded-lg bg-secondary px-3 py-1.5 text-xs text-muted-foreground hover:bg-border"
                    >
                      <X className="h-3 w-3" />
                      {t(lang, "admin_report_dismiss")}
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
