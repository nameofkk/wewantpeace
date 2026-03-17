"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Search, Ban, CheckCircle, Users, UserX,
  ChevronUp, ChevronDown, ChevronsUpDown,
} from "lucide-react";
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
  visit_count: number;
}

const PLAN_BADGE: Record<string, string> = {
  free: "bg-secondary text-muted-foreground",
  pro: "bg-yellow-500/20 text-yellow-400",
  pro_plus: "bg-purple-500/20 text-purple-400",
};

const STATUS_DOT: Record<string, string> = {
  active: "bg-green-400",
  suspended: "bg-red-400",
  deleted: "bg-muted-foreground",
};

type SortKey = "created_at" | "last_active" | "visit_count" | "nickname" | "plan";

function SortIcon({ column, current, order }: { column: SortKey; current: SortKey; order: "asc" | "desc" }) {
  if (column !== current) return <ChevronsUpDown className="h-3 w-3 opacity-30" />;
  return order === "asc"
    ? <ChevronUp className="h-3 w-3 text-primary" />
    : <ChevronDown className="h-3 w-3 text-primary" />;
}

function timeAgo(dateStr: string | null, locale: string): string {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return locale === "ko-KR" ? "방금 전" : "Just now";
  if (mins < 60) return `${mins}${locale === "ko-KR" ? "분 전" : "m ago"}`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}${locale === "ko-KR" ? "시간 전" : "h ago"}`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}${locale === "ko-KR" ? "일 전" : "d ago"}`;
  return new Date(dateStr).toLocaleDateString(locale, { month: "short", day: "numeric" });
}

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
  const [sortBy, setSortBy] = useState<SortKey>("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [drawerUserId, setDrawerUserId] = useState<string | null>(null);

  const effectiveStatus = tab === "deleted" ? "deleted" : statusFilter;

  function toggleSort(col: SortKey) {
    if (sortBy === col) {
      setSortOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortOrder("desc");
    }
    setPage(1);
  }

  const { data, isLoading } = useQuery<{ users: AdminUser[]; total: number }>({
    queryKey: ["admin-users", tab, page, search, effectiveStatus, planFilter, sortBy, sortOrder],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ page: String(page), limit: "20", sort_by: sortBy, sort_order: sortOrder });
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
  const ko = lang === "ko";

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_users")}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {ko ? "전체" : "Total"} {data?.total ?? 0}{ko ? "명" : " users"}
          </p>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder={ko ? "이름, 이메일 검색" : "Search name, email"}
            className="rounded-xl border border-border bg-card pl-9 pr-4 py-2.5 text-sm outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 w-60 transition-all"
          />
        </div>
      </div>

      {/* Tabs + Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex rounded-xl bg-secondary/60 p-1 gap-0.5">
          <button
            onClick={() => { setTab("active"); setPage(1); setStatusFilter(""); }}
            className={cn(
              "flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all",
              tab === "active" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Users className="h-3.5 w-3.5" />
            {ko ? "가입 회원" : "Active"}
          </button>
          <button
            onClick={() => { setTab("deleted"); setPage(1); setStatusFilter(""); setPlanFilter(""); }}
            className={cn(
              "flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all",
              tab === "deleted" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <UserX className="h-3.5 w-3.5" />
            {ko ? "탈퇴 회원" : "Deleted"}
          </button>
        </div>

        {tab === "active" && (
          <div className="flex gap-2">
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="rounded-lg border border-border bg-card px-3 py-2 text-xs outline-none cursor-pointer"
            >
              <option value="">{ko ? "상태 전체" : "All Status"}</option>
              <option value="active">{ko ? "활성" : "Active"}</option>
              <option value="suspended">{ko ? "정지" : "Suspended"}</option>
            </select>
            <select
              value={planFilter}
              onChange={(e) => { setPlanFilter(e.target.value); setPage(1); }}
              className="rounded-lg border border-border bg-card px-3 py-2 text-xs outline-none cursor-pointer"
            >
              <option value="">{ko ? "플랜 전체" : "All Plans"}</option>
              <option value="free">Free</option>
              <option value="pro">Pro</option>
              <option value="pro_plus">Pro+</option>
            </select>
          </div>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="rounded-xl border border-border overflow-hidden">
          <div className="bg-secondary/50 h-11" />
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex gap-4 px-4 py-3.5 border-t border-border animate-pulse">
              <div className="h-4 w-32 rounded bg-secondary" />
              <div className="h-4 w-16 rounded bg-secondary" />
              <div className="h-4 w-20 rounded bg-secondary" />
              <div className="h-4 w-12 rounded bg-secondary" />
              <div className="h-4 w-24 rounded bg-secondary" />
            </div>
          ))}
        </div>
      ) : !data?.users?.length ? (
        <div className="flex flex-col items-center py-20 text-muted-foreground">
          {tab === "deleted" ? <UserX className="h-10 w-10 mb-3 opacity-40" /> : <Users className="h-10 w-10 mb-3 opacity-40" />}
          <p className="text-sm">{ko ? "해당하는 회원이 없습니다" : "No users found"}</p>
        </div>
      ) : (
        <>
          {/* Desktop Table */}
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-secondary/50 border-b border-border">
                  <th className="px-4 py-3 text-left">
                    <button onClick={() => toggleSort("nickname")} className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
                      {ko ? "회원" : "User"}
                      <SortIcon column="nickname" current={sortBy} order={sortOrder} />
                    </button>
                  </th>
                  <th className="px-3 py-3 text-left">
                    <button onClick={() => toggleSort("plan")} className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
                      {ko ? "플랜" : "Plan"}
                      <SortIcon column="plan" current={sortBy} order={sortOrder} />
                    </button>
                  </th>
                  {tab === "active" && (
                    <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "상태" : "Status"}</th>
                  )}
                  <th className="px-3 py-3 text-left">
                    <button onClick={() => toggleSort("created_at")} className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
                      {ko ? "가입일" : "Joined"}
                      <SortIcon column="created_at" current={sortBy} order={sortOrder} />
                    </button>
                  </th>
                  <th className="px-3 py-3 text-left">
                    <button onClick={() => toggleSort("last_active")} className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
                      {ko ? "최근 방문" : "Last Visit"}
                      <SortIcon column="last_active" current={sortBy} order={sortOrder} />
                    </button>
                  </th>
                  <th className="px-3 py-3 text-right">
                    <button onClick={() => toggleSort("visit_count")} className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors ml-auto">
                      {ko ? "방문" : "Visits"}
                      <SortIcon column="visit_count" current={sortBy} order={sortOrder} />
                    </button>
                  </th>
                  {tab === "active" && (
                    <th className="px-3 py-3 w-10" />
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.users.map((u) => (
                  <tr
                    key={u.id}
                    className={cn(
                      "hover:bg-secondary/30 cursor-pointer transition-colors",
                      tab === "deleted" && "opacity-50",
                    )}
                    onClick={() => setDrawerUserId(u.id)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className={cn("h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0",
                          u.plan === "pro" ? "bg-yellow-500/20 text-yellow-400"
                            : u.plan === "pro_plus" ? "bg-purple-500/20 text-purple-400"
                            : "bg-secondary text-muted-foreground"
                        )}>
                          {(u.nickname || u.email || "?")[0].toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <p className={cn("font-medium text-sm truncate", tab === "deleted" && "line-through text-muted-foreground")}>
                            {u.nickname || u.display_name || (ko ? "이름 없음" : "No name")}
                          </p>
                          <p className="text-[11px] text-muted-foreground truncate">{u.email || "—"}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3" onClick={(e) => tab === "active" && e.stopPropagation()}>
                      {tab === "active" ? (
                        <select
                          value={u.plan}
                          onChange={(e) => patchMutation.mutate({ userId: u.id, body: { plan: e.target.value } })}
                          className={cn("rounded-full px-2.5 py-1 text-[10px] font-semibold border-0 outline-none cursor-pointer", PLAN_BADGE[u.plan] || "bg-secondary")}
                        >
                          <option value="free">FREE</option>
                          <option value="pro">PRO</option>
                          <option value="pro_plus">PRO+</option>
                        </select>
                      ) : (
                        <span className={cn("rounded-full px-2.5 py-1 text-[10px] font-semibold", PLAN_BADGE[u.plan] || "bg-secondary")}>
                          {u.plan.toUpperCase()}
                        </span>
                      )}
                    </td>
                    {tab === "active" && (
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1.5">
                          <div className={cn("h-2 w-2 rounded-full", STATUS_DOT[u.status])} />
                          <span className="text-xs text-muted-foreground">{u.status === "active" ? (ko ? "활성" : "Active") : (ko ? "정지" : "Suspended")}</span>
                        </div>
                      </td>
                    )}
                    <td className="px-3 py-3 text-xs text-muted-foreground whitespace-nowrap">
                      {new Date(u.created_at).toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric" })}
                    </td>
                    <td className="px-3 py-3 text-xs text-muted-foreground whitespace-nowrap">
                      {u.last_active ? (
                        <span title={new Date(u.last_active).toLocaleString(locale)}>
                          {timeAgo(u.last_active, locale)}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="px-3 py-3 text-right">
                      <span className={cn(
                        "text-xs font-medium tabular-nums",
                        u.visit_count > 0 ? "text-foreground" : "text-muted-foreground/50",
                      )}>
                        {u.visit_count}
                      </span>
                    </td>
                    {tab === "active" && (
                      <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => suspendMutation.mutate({ userId: u.id, suspend: u.status === "active" })}
                          disabled={suspendMutation.isPending}
                          className="text-muted-foreground/50 hover:text-foreground transition-colors"
                          title={u.status === "active" ? (ko ? "정지" : "Suspend") : (ko ? "해제" : "Unsuspend")}
                        >
                          {u.status === "active"
                            ? <Ban className="h-3.5 w-3.5 hover:text-red-400" />
                            : <CheckCircle className="h-3.5 w-3.5 hover:text-green-400" />}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Cards */}
          <div className="md:hidden space-y-2.5">
            {data.users.map((u) => (
              <div
                key={u.id}
                className={cn(
                  "rounded-xl border border-border bg-card p-4 cursor-pointer active:bg-secondary/20 transition-colors",
                  tab === "deleted" && "opacity-50",
                )}
                onClick={() => setDrawerUserId(u.id)}
              >
                <div className="flex items-start justify-between mb-2.5">
                  <div className="flex items-center gap-2.5">
                    <div className={cn("h-9 w-9 rounded-full flex items-center justify-center text-xs font-bold shrink-0",
                      u.plan === "pro" ? "bg-yellow-500/20 text-yellow-400"
                        : u.plan === "pro_plus" ? "bg-purple-500/20 text-purple-400"
                        : "bg-secondary text-muted-foreground"
                    )}>
                      {(u.nickname || u.email || "?")[0].toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <p className={cn("font-medium text-sm", tab === "deleted" && "line-through text-muted-foreground")}>
                        {u.nickname || u.display_name || (ko ? "이름 없음" : "No name")}
                      </p>
                      <p className="text-[11px] text-muted-foreground truncate">{u.email || "—"}</p>
                    </div>
                  </div>
                  {tab === "active" && (
                    <div className="flex items-center gap-1.5">
                      <div className={cn("h-2 w-2 rounded-full", STATUS_DOT[u.status])} />
                      <span className="text-[10px] text-muted-foreground">{u.status === "active" ? (ko ? "활성" : "Active") : (ko ? "정지" : "Susp.")}</span>
                    </div>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", PLAN_BADGE[u.plan] || "bg-secondary")}>
                      {u.plan.toUpperCase()}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {ko ? "방문" : "Visits"} {u.visit_count}
                    </span>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] text-muted-foreground">
                      {u.last_active && u.last_active !== u.created_at
                        ? timeAgo(u.last_active, locale)
                        : new Date(u.created_at).toLocaleDateString(locale, { month: "short", day: "numeric" })
                      }
                    </p>
                  </div>
                </div>
                {tab === "active" && (
                  <div className="flex items-center justify-end gap-2 mt-2 pt-2 border-t border-border/50" onClick={(e) => e.stopPropagation()}>
                    <select
                      value={u.plan}
                      onChange={(e) => patchMutation.mutate({ userId: u.id, body: { plan: e.target.value } })}
                      className="rounded-lg border border-border bg-background text-[10px] px-2 py-1"
                    >
                      <option value="free">FREE</option>
                      <option value="pro">PRO</option>
                      <option value="pro_plus">PRO+</option>
                    </select>
                    <button
                      onClick={() => suspendMutation.mutate({ userId: u.id, suspend: u.status === "active" })}
                      className="text-muted-foreground hover:text-foreground transition-colors p-1"
                    >
                      {u.status === "active"
                        ? <Ban className="h-3.5 w-3.5 hover:text-red-400" />
                        : <CheckCircle className="h-3.5 w-3.5 hover:text-green-400" />}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1.5 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-border px-3.5 py-2 text-xs font-medium disabled:opacity-30 hover:bg-secondary/50 transition-colors"
          >
            {ko ? "이전" : "Prev"}
          </button>
          {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
            let n: number;
            if (totalPages <= 5) n = i + 1;
            else if (page <= 3) n = i + 1;
            else if (page >= totalPages - 2) n = totalPages - 4 + i;
            else n = page - 2 + i;
            return (
              <button
                key={n}
                onClick={() => setPage(n)}
                className={cn(
                  "rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                  page === n ? "bg-primary text-primary-foreground" : "hover:bg-secondary/50 text-muted-foreground",
                )}
              >
                {n}
              </button>
            );
          })}
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded-lg border border-border px-3.5 py-2 text-xs font-medium disabled:opacity-30 hover:bg-secondary/50 transition-colors"
          >
            {ko ? "다음" : "Next"}
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
