"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery } from "@tanstack/react-query";
import { Loader2, CreditCard } from "lucide-react";
import { cn } from "@/lib/utils";
import { API_BASE } from "@/lib/admin-utils";

interface SubscriptionItem {
  id: string;
  user_id: string;
  email: string | null;
  nickname: string | null;
  plan: string;
  status: string; // active, cancelled, expired, trial, grace_period, admin_granted
  amount: number;
  currency: string;
  platform: string;
  started_at: string;
  expires_at: string | null;
  next_billing_at: string | null;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-500/20 text-green-400",
  admin_granted: "bg-indigo-500/20 text-indigo-400",
  cancelled: "bg-yellow-500/20 text-yellow-400",
  expired: "bg-red-500/20 text-red-400",
  trial: "bg-blue-500/20 text-blue-400",
  grace_period: "bg-orange-500/20 text-orange-400",
};

const PLAN_BADGE: Record<string, string> = {
  pro: "bg-yellow-500/20 text-yellow-400",
  pro_plus: "bg-purple-500/20 text-purple-400",
};

const STATUS_LABEL_KEY: Record<string, string> = {
  active: "admin_sub_active",
  admin_granted: "admin_sub_granted",
  cancelled: "admin_sub_cancelled",
  expired: "admin_sub_expired",
  trial: "admin_sub_trial",
  grace_period: "admin_sub_grace_period",
};

export default function AdminSubscriptionsPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const [page, setPage] = useState(1);
  const [planFilter, setPlanFilter] = useState("all");

  const { data, isLoading } = useQuery<{ items: SubscriptionItem[]; total: number }>({
    queryKey: ["admin-subscriptions", page, planFilter],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ page: String(page) });
      if (planFilter !== "all") params.append("plan", planFilter);
      const res = await fetch(`${API_BASE}/admin/subscriptions?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("구독 목록 로드 실패");
      return res.json();
    },
    enabled: !!user,
  });

  const locale = lang === "en" ? "en-US" : "ko-KR";

  const filtered = data?.items ?? [];

  const totalPages = Math.ceil((data?.total ?? 0) / 20);

  const formatDate = (d: string | null) => {
    if (!d) return "—";
    return new Date(d).toLocaleDateString(locale);
  };

  const formatAmount = (amount: number, currency: string) => {
    return `${amount.toLocaleString(locale)} ${currency}`;
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_subscriptions")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.total ?? 0} {lang === "ko" ? "건" : "subscriptions"}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
        {["all", "pro", "pro_plus"].map((p) => (
          <button
            key={p}
            onClick={() => { setPlanFilter(p); setPage(1); }}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              planFilter === p ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"
            )}
          >
            {p === "all" ? t(lang, "admin_all") : p === "pro_plus" ? "Pro+" : "Pro"}
          </button>
        ))}
      </div>

      {/* Loading skeleton */}
      {isLoading ? (
        <>
          {/* Desktop skeleton */}
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <div className="bg-secondary/50 h-10" />
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="border-t border-border px-4 py-4">
                <div className="h-4 bg-secondary/50 rounded animate-pulse w-full" />
              </div>
            ))}
          </div>
          {/* Mobile skeleton */}
          <div className="md:hidden space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="h-4 bg-secondary/50 rounded animate-pulse w-3/4" />
                <div className="h-3 bg-secondary/50 rounded animate-pulse w-1/2" />
                <div className="h-3 bg-secondary/50 rounded animate-pulse w-2/3" />
              </div>
            ))}
          </div>
        </>
      ) : !filtered.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <CreditCard className="h-10 w-10 mb-3" />
          <p className="text-sm">{t(lang, "admin_no_data")}</p>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-xl border border-border overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_user_email")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_user_nickname")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_sub_plan")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_sub_status")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_sub_platform")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_sub_started")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_sub_expires")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((item) => (
                  <tr key={item.id} className="hover:bg-secondary/20">
                    <td className="px-4 py-3 text-xs">{item.email ?? "-"}</td>
                    <td className="px-4 py-3 text-xs">{item.nickname ?? "-"}</td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", PLAN_BADGE[item.plan] || "bg-secondary")}>
                        {item.plan.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", STATUS_COLORS[item.status] || "bg-secondary")}>
                        {t(lang, STATUS_LABEL_KEY[item.status] as any) || item.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {item.platform}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {formatDate(item.started_at)}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {formatDate(item.expires_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {filtered.map((item) => (
              <div key={item.id} className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="min-w-0">
                    <p className="text-xs font-medium truncate">{item.nickname ?? item.email ?? "-"}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{item.email ?? "-"}</p>
                  </div>
                  <div className="flex gap-1.5 shrink-0">
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", PLAN_BADGE[item.plan] || "bg-secondary")}>
                      {item.plan.toUpperCase()}
                    </span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", STATUS_COLORS[item.status] || "bg-secondary")}>
                      {t(lang, STATUS_LABEL_KEY[item.status] as any) || item.status}
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-y-2 text-xs">
                  <div>
                    <span className="text-muted-foreground">{t(lang, "admin_sub_platform")}</span>
                    <p className="font-medium">{item.platform}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t(lang, "admin_sub_started")}</span>
                    <p className="font-medium">{formatDate(item.started_at)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t(lang, "admin_sub_expires")}</span>
                    <p className="font-medium">{formatDate(item.expires_at)}</p>
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
    </div>
  );
}
