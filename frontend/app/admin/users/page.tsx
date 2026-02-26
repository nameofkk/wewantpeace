"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Ban, CheckCircle, Users, UserX } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminToast } from "@/components/ui/admin-toast";
import UserDetailDrawer from "@/components/admin/UserDetailDrawer";
import { API_BASE } from "@/lib/admin-utils";

interface AdminUser {
  id: string;
  email: string | null;
  nickname: string | null;
  display_name: string | null;
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
  const { toast } = useAdminToast();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState<"active" | "deleted">("active");
  const [statusFilter, setStatusFilter] = useState("");
  const [planFilter, setPlanFilter] = useState("");
  const [drawerUserId, setDrawerUserId] = useState<string | null>(null);

  // 탭에 따라 status 결정: active 탭은 statusFilter 또는 전체(deleted 제외), deleted 탭은 고정 "deleted"
  const effectiveStatus = tab === "deleted" ? "deleted" : statusFilter;

  const { data, isLoading } = useQuery<{ users: AdminUser[]; total: number }>({
    queryKey: ["admin-users", tab, page, search, effectiveStatus, planFilter],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ page: String(page), limit: "20" });
      if (search) params.append("search", search);
      if (effectiveStatus) params.append("status", effectiveStatus);
      if (tab === "active" && !statusFilter) params.append("exclude_status", "deleted");
      if (planFilter) params.append("plan", planFilter);
      const res = await fetch(`${API_BASE}/admin/users?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Load failed");
      return res.json();
    },
    enabled: !!user,
  });

  const patchMutation = useMutation({
    mutationFn: async ({ userId, body }: { userId: string; body: Record<string, unknown> }) => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Failed");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast(t(lang, "admin_toast_updated"), "success");
    },
    onError: () => toast(t(lang, "admin_toast_error"), "error"),
  });

  const suspendMutation = useMutation({
    mutationFn: async ({ userId, suspend }: { userId: string; suspend: boolean }) => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const body = suspend
        ? { suspended_until: new Date(Date.now() + 7 * 86400_000).toISOString(), suspend_reason: lang === "ko" ? "관리자 정지" : "Admin suspension" }
        : { suspended_until: null, suspend_reason: null };
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Failed");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast(t(lang, "admin_toast_updated"), "success");
    },
    onError: () => toast(t(lang, "admin_toast_error"), "error"),
  });

  const locale = lang === "en" ? "en-US" : "ko-KR";
  const totalPages = Math.ceil((data?.total ?? 0) / 20);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_users")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.total ?? 0} {t(lang, "admin_count_users")}
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

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-secondary p-1 mb-4">
        <button
          onClick={() => { setTab("active"); setPage(1); setStatusFilter(""); }}
          className={cn(
            "flex items-center gap-1.5 flex-1 py-2 rounded-md text-sm font-medium transition-colors",
            tab === "active" ? "bg-background text-foreground shadow" : "text-muted-foreground"
          )}
        >
          <Users className="h-3.5 w-3.5" />
          {t(lang, "admin_tab_active_users")}
        </button>
        <button
          onClick={() => { setTab("deleted"); setPage(1); setStatusFilter(""); setPlanFilter(""); }}
          className={cn(
            "flex items-center gap-1.5 flex-1 py-2 rounded-md text-sm font-medium transition-colors",
            tab === "deleted" ? "bg-background text-foreground shadow" : "text-muted-foreground"
          )}
        >
          <UserX className="h-3.5 w-3.5" />
          {t(lang, "admin_tab_deleted_users")}
        </button>
      </div>

      {/* Filters (active 탭에서만) */}
      {tab === "active" && (
        <div className="flex flex-wrap gap-3 mb-4">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
          >
            <option value="">{t(lang, "admin_status")}: {t(lang, "admin_all")}</option>
            <option value="active">{t(lang, "admin_active")}</option>
            <option value="suspended">{t(lang, "admin_suspend")}</option>
          </select>
          <select
            value={planFilter}
            onChange={(e) => { setPlanFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
          >
            <option value="">{t(lang, "admin_user_plan")}: {t(lang, "admin_all")}</option>
            <option value="free">Free</option>
            <option value="pro">Pro</option>
            <option value="pro_plus">Pro+</option>
          </select>
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <>
          {/* Desktop skeleton */}
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <div className="bg-secondary/50 h-10" />
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex gap-4 p-4 border-t border-border animate-pulse">
                <div className="h-4 w-32 rounded bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
                <div className="h-4 w-24 rounded bg-secondary" />
              </div>
            ))}
          </div>
          {/* Mobile skeleton */}
          <div className="md:hidden space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
                <div className="h-4 w-40 rounded bg-secondary" />
                <div className="h-3 w-24 rounded bg-secondary" />
                <div className="flex gap-2">
                  <div className="h-5 w-12 rounded-full bg-secondary" />
                  <div className="h-5 w-12 rounded-full bg-secondary" />
                </div>
              </div>
            ))}
          </div>
        </>
      ) : !data?.users?.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          {tab === "deleted" ? <UserX className="h-10 w-10 mb-3" /> : <Users className="h-10 w-10 mb-3" />}
          <p className="text-sm">{t(lang, "admin_no_data")}</p>
        </div>
      ) : tab === "deleted" ? (
        <>
          {/* Deleted — Desktop table */}
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">ID</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_user_nickname")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_user_plan")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_user_joined")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.users.map((u) => (
                  <tr key={u.id} className="hover:bg-secondary/20 cursor-pointer opacity-60" onClick={() => setDrawerUserId(u.id)}>
                    <td className="px-4 py-3 text-xs text-muted-foreground font-mono">{u.id.slice(0, 8)}</td>
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium line-through text-muted-foreground">{u.nickname || u.display_name || t(lang, "admin_no_name")}</p>
                        <p className="text-xs text-muted-foreground">{u.email || "—"}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", PLAN_BADGE[u.plan] || "bg-secondary")}>
                        {u.plan.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {new Date(u.created_at).toLocaleDateString(locale)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Deleted — Mobile cards */}
          <div className="md:hidden space-y-3">
            {data.users.map((u) => (
              <div
                key={u.id}
                className="rounded-xl border border-border bg-card p-4 cursor-pointer active:bg-secondary/20 opacity-60"
                onClick={() => setDrawerUserId(u.id)}
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-medium text-sm line-through text-muted-foreground">{u.nickname || u.display_name || t(lang, "admin_no_name")}</p>
                    <p className="text-xs text-muted-foreground">{u.email || "—"}</p>
                  </div>
                  <span className="text-xs font-medium text-muted-foreground">deleted</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground font-mono">{u.id.slice(0, 8)}</span>
                  <p className="text-xs text-muted-foreground">{new Date(u.created_at).toLocaleDateString(locale)}</p>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          {/* Active — Desktop table */}
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_user_nickname")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_user_plan")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_user_role")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_user_status")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_user_joined")}</th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground">{t(lang, "admin_actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.users.map((u) => (
                  <tr key={u.id} className="hover:bg-secondary/20 cursor-pointer" onClick={() => setDrawerUserId(u.id)}>
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium">{u.nickname || u.display_name || t(lang, "admin_no_name")}</p>
                        <p className="text-xs text-muted-foreground">{u.email || "—"}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <select
                        value={u.plan}
                        onChange={(e) => patchMutation.mutate({ userId: u.id, body: { plan: e.target.value } })}
                        className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium border-0 outline-none cursor-pointer", PLAN_BADGE[u.plan] || "bg-secondary")}
                      >
                        <option value="free">FREE</option>
                        <option value="pro">PRO</option>
                        <option value="pro_plus">PRO+</option>
                      </select>
                    </td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <select
                        value={u.role}
                        onChange={(e) => patchMutation.mutate({ userId: u.id, body: { role: e.target.value } })}
                        className="rounded border border-border bg-background text-xs px-2 py-1"
                      >
                        <option value="user">user</option>
                        <option value="moderator">moderator</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("text-xs font-medium", STATUS_BADGE[u.status])}>{u.status}</span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {new Date(u.created_at).toLocaleDateString(locale)}
                    </td>
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => suspendMutation.mutate({ userId: u.id, suspend: u.status === "active" })}
                        disabled={suspendMutation.isPending}
                        className="text-muted-foreground hover:text-foreground"
                        title={u.status === "active" ? t(lang, "admin_suspend") : t(lang, "admin_unsuspend")}
                      >
                        {u.status === "active"
                          ? <Ban className="h-4 w-4 hover:text-red-400" />
                          : <CheckCircle className="h-4 w-4 hover:text-green-400" />}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Active — Mobile cards */}
          <div className="md:hidden space-y-3">
            {data.users.map((u) => (
              <div
                key={u.id}
                className="rounded-xl border border-border bg-card p-4 cursor-pointer active:bg-secondary/20"
                onClick={() => setDrawerUserId(u.id)}
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-medium text-sm">{u.nickname || u.display_name || t(lang, "admin_no_name")}</p>
                    <p className="text-xs text-muted-foreground">{u.email || "—"}</p>
                  </div>
                  <span className={cn("text-xs font-medium", STATUS_BADGE[u.status])}>{u.status}</span>
                </div>
                <div className="flex items-center gap-2 mb-2">
                  <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", PLAN_BADGE[u.plan] || "bg-secondary")}>
                    {u.plan.toUpperCase()}
                  </span>
                  <span className="text-[10px] text-muted-foreground">{u.role}</span>
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-xs text-muted-foreground">{new Date(u.created_at).toLocaleDateString(locale)}</p>
                  <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                    <select
                      value={u.plan}
                      onChange={(e) => patchMutation.mutate({ userId: u.id, body: { plan: e.target.value } })}
                      className="rounded border border-border bg-background text-[10px] px-1.5 py-0.5"
                    >
                      <option value="free">FREE</option>
                      <option value="pro">PRO</option>
                      <option value="pro_plus">PRO+</option>
                    </select>
                    <button
                      onClick={() => suspendMutation.mutate({ userId: u.id, suspend: u.status === "active" })}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      {u.status === "active"
                        ? <Ban className="h-4 w-4 hover:text-red-400" />
                        : <CheckCircle className="h-4 w-4 hover:text-green-400" />}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
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
      )}

      {/* User Detail Drawer */}
      <UserDetailDrawer
        open={!!drawerUserId}
        onClose={() => setDrawerUserId(null)}
        userId={drawerUserId}
        lang={lang}
        onUpdated={() => queryClient.invalidateQueries({ queryKey: ["admin-users"] })}
      />
    </div>
  );
}
