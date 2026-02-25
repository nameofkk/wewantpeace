"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Ban, CheckCircle, Crown, Loader2, Users } from "lucide-react";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AdminUser {
  id: string;
  email: string | null;
  nickname: string | null;
  plan: string;
  role: string;
  status: string;
  created_at: string;
  last_active: string | null;
}

const PLAN_BADGE: Record<string, string> = {
  free: "bg-secondary text-muted-foreground",
  pro: "bg-yellow-500/20 text-yellow-400",
  pro_plus: "bg-purple-500/20 text-purple-400",
};

const STATUS_BADGE: Record<string, string> = {
  active: "text-green-400",
  suspended: "text-red-400",
  deleted: "text-muted-foreground",
};

export default function AdminUsersPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery<{ users: AdminUser[]; total: number }>({
    queryKey: ["admin-users", page, search],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ page: String(page), limit: "20" });
      if (search) params.append("search", search);
      const res = await fetch(`${API_BASE}/admin/users?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("회원 목록 로드 실패");
      return res.json();
    },
    enabled: !!user,
  });

  const suspendMutation = useMutation({
    mutationFn: async ({ userId, suspend }: { userId: string; suspend: boolean }) => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const body = suspend
        ? { suspended_until: new Date(Date.now() + 7 * 86400_000).toISOString(), suspend_reason: "관리자 정지" }
        : { suspended_until: null, suspend_reason: null };
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("처리 실패");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const roleMutation = useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: string }) => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ role }),
      });
      if (!res.ok) throw new Error("처리 실패");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <div>
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_users")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.total ?? 0} {lang === "ko" ? "명" : "users"}
          </p>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder={t(lang, "admin_search")}
            className="rounded-lg border border-border bg-card pl-9 pr-4 py-2 text-sm outline-none focus:border-primary w-56"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !data?.users?.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <Users className="h-10 w-10 mb-3" />
          <p className="text-sm">{t(lang, "admin_no_data")}</p>
        </div>
      ) : (
        <div className="rounded-xl border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-secondary/50">
              <tr>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "회원" : "User"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "플랜" : "Plan"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "역할" : "Role"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "상태" : "Status"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "가입일" : "Joined"}</th>
                <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground">{t(lang, "admin_actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data?.users.map((u) => (
                <tr key={u.id} className="hover:bg-secondary/20">
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-medium">{u.nickname || (lang === "ko" ? "닉네임 없음" : "No name")}</p>
                      <p className="text-xs text-muted-foreground">{u.email || "—"}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", PLAN_BADGE[u.plan] || "bg-secondary")}>
                      {u.plan.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={u.role}
                      onChange={(e) => roleMutation.mutate({ userId: u.id, role: e.target.value })}
                      className="rounded border border-border bg-background text-xs px-2 py-1"
                    >
                      <option value="user">user</option>
                      <option value="moderator">moderator</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn("text-xs font-medium", STATUS_BADGE[u.status])}>
                      {u.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(u.created_at).toLocaleDateString(locale)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => suspendMutation.mutate({ userId: u.id, suspend: u.status === "active" })}
                      disabled={suspendMutation.isPending}
                      className="text-muted-foreground hover:text-foreground"
                      title={u.status === "active" ? (lang === "ko" ? "정지" : "Suspend") : (lang === "ko" ? "정지 해제" : "Unsuspend")}
                    >
                      {u.status === "active"
                        ? <Ban className="h-4 w-4 hover:text-red-400" />
                        : <CheckCircle className="h-4 w-4 hover:text-green-400" />
                      }
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {(data?.total ?? 0) > 20 && (() => {
        const totalPages = Math.ceil((data?.total ?? 0) / 20);
        return (
          <div className="flex justify-center gap-2 mt-4">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50"
            >
              {t(lang, "admin_prev")}
            </button>
            <span className="flex items-center px-3 text-sm text-muted-foreground">
              {t(lang, "admin_page_of", { page, total: totalPages })}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50"
            >
              {t(lang, "admin_next")}
            </button>
          </div>
        );
      })()}
    </div>
  );
}
