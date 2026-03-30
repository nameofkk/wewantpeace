"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { t } from "@/lib/i18n";
import { useAdminStore, API_BASE } from "@/lib/admin-utils";
import { useAuth } from "@/lib/auth";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface LogEntry {
  id: number;
  admin_nickname: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export default function AdminLogsPage() {
  const lang = "ko" as const;
  const { user } = useAuth();
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-logs", page],
    queryFn: async () => {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_BASE}/admin/logs?page=${page}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed");
      return res.json() as Promise<{ total: number; items: LogEntry[] }>;
    },
    enabled: !!user,
  });

  const totalPages = Math.ceil((data?.total ?? 0) / 20);
  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-lg font-bold">{t(lang, "admin_logs")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {lang === "ko" ? "관리자 액션 로그를 조회합니다" : "View admin action logs"}
        </p>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">{t(lang, "admin_loading")}</div>
      ) : !data || data.items.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t(lang, "admin_no_data")}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-4">{lang === "ko" ? "시간" : "Time"}</th>
                <th className="py-2 pr-4">{lang === "ko" ? "관리자" : "Admin"}</th>
                <th className="py-2 pr-4">{lang === "ko" ? "액션" : "Action"}</th>
                <th className="py-2 pr-4">{lang === "ko" ? "대상" : "Target"}</th>
                <th className="py-2">{lang === "ko" ? "상세" : "Detail"}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((log) => (
                <tr key={log.id} className="border-b border-border/50 hover:bg-secondary/30">
                  <td className="py-2.5 pr-4 text-xs text-muted-foreground whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </td>
                  <td className="py-2.5 pr-4 text-xs">{log.admin_nickname ?? "-"}</td>
                  <td className="py-2.5 pr-4">
                    <span className="rounded-full bg-secondary px-2 py-0.5 text-[11px] font-medium">{log.action}</span>
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-muted-foreground">
                    {log.target_type ? `${log.target_type}:${log.target_id ?? ""}` : "-"}
                  </td>
                  <td className="py-2.5 text-[10px] text-muted-foreground max-w-[200px] truncate">
                    {log.detail ? JSON.stringify(log.detail) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-6">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-30">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm text-muted-foreground">{t(lang, "admin_page_of", { page, total: totalPages })}</span>
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-30">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
