"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminStore, adminFetch } from "@/lib/admin-utils";

interface PaymentItem {
  id: string;
  paid_at: string;
  email: string | null;
  nickname: string | null;
  user_plan: string;
  platform: string;
  status: "success" | "failed" | "refunded";
  amount: number;
  currency: string;
  charged_currency: string | null;
  charged_amount: number | null;
  order_id: string | null;
  plan: string | null;
  sub_status: string | null;
  expires_at: string | null;
  auto_renewing: boolean | null;
}

const PLATFORM_LABEL: Record<string, { ko: string; en: string }> = {
  android: { ko: "구글 플레이", en: "Google Play" },
  ios: { ko: "앱스토어", en: "App Store" },
  dodopayments: { ko: "웹 결제", en: "Web" },
};

const SUB_STATUS: Record<string, { ko: string; en: string; cls: string }> = {
  active: { ko: "이용 중", en: "Active", cls: "bg-green-500/20 text-green-400" },
  trial: { ko: "체험 중", en: "Trial", cls: "bg-blue-500/20 text-blue-400" },
  cancelled: { ko: "해지 예약", en: "Cancels at end", cls: "bg-yellow-500/20 text-yellow-400" },
  grace_period: { ko: "결제 유예", en: "Grace", cls: "bg-orange-500/20 text-orange-400" },
  billing_retry: { ko: "결제 재시도", en: "Retrying", cls: "bg-pink-500/20 text-pink-400" },
  expired: { ko: "만료", en: "Expired", cls: "bg-red-500/20 text-red-400" },
};

function money(minor: number, currency: string, locale: string) {
  const zeroDecimal = ["KRW", "JPY", "VND", "IDR"].includes(currency);
  const value = zeroDecimal ? minor : minor / 100;
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency }).format(value);
  } catch {
    return `${value} ${currency}`;
  }
}

export default function PaymentsTable() {
  const { lang } = useAdminStore();
  const ko = lang === "ko";
  const locale = ko ? "ko-KR" : "en-US";
  const [page, setPage] = useState(1);
  const [platform, setPlatform] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");

  const { data, isLoading } = useQuery<{ total: number; platforms: string[]; items: PaymentItem[] }>({
    queryKey: ["admin-payments", page, platform, query],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page) });
      if (platform) params.append("platform", platform);
      if (query) params.append("q", query);
      return adminFetch(`/admin/payments?${params}`);
    },
  });

  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / 20));
  const fmt = (iso: string | null) =>
    iso ? new Date(iso).toLocaleString(locale, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

  return (
    <section className="mt-10">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">{ko ? "결제 내역" : "Payments"}</h2>
          <p className="text-xs text-muted-foreground">
            {ko ? `앱·웹 결제 전체 ${data?.total ?? 0}건 · 해지·만료된 손님도 남습니다` : `${data?.total ?? 0} payments across app and web`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <form
            onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); setPage(1); }}
            className="relative"
          >
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={ko ? "이메일·닉네임·주문번호" : "Email, nickname, order ID"}
              className="w-60 max-w-full rounded-lg border border-border bg-card pl-8 pr-3 py-2 text-sm outline-none"
            />
          </form>
          <select
            value={platform}
            onChange={(e) => { setPlatform(e.target.value); setPage(1); }}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
          >
            <option value="">{ko ? "결제 경로 전체" : "All channels"}</option>
            {(data?.platforms ?? []).map((p) => (
              <option key={p} value={p}>{PLATFORM_LABEL[p]?.[ko ? "ko" : "en"] ?? p}</option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-10"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
      ) : (
        <div className="rounded-xl border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-secondary/50">
              <tr>
                <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground w-10">#</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "결제 시각" : "Paid at"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "손님" : "Customer"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "경로" : "Channel"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "플랜" : "Plan"}</th>
                <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground">{ko ? "청구액" : "Charged"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "구독 상태" : "Subscription"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "이용 기한" : "Access until"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "주문번호" : "Order ID"}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(data?.items ?? []).map((p, i) => {
                const st = p.sub_status ? SUB_STATUS[p.sub_status] : null;
                return (
                  <tr key={p.id} className="hover:bg-secondary/20">
                    <td className="px-3 py-2.5 text-right text-xs text-muted-foreground tabular-nums">{(page - 1) * 20 + i + 1}</td>
                    <td className="px-3 py-2.5 text-xs whitespace-nowrap">{fmt(p.paid_at)}</td>
                    <td className="px-3 py-2.5 text-xs">
                      <div className="font-medium">{p.nickname || "—"}</div>
                      <div className="text-muted-foreground">{p.email || "—"}</div>
                    </td>
                    <td className="px-3 py-2.5 text-xs">{PLATFORM_LABEL[p.platform]?.[ko ? "ko" : "en"] ?? p.platform}</td>
                    <td className="px-3 py-2.5 text-xs">{p.plan === "pro_plus" ? "Pro+" : p.plan === "pro" ? "Pro" : "—"}</td>
                    <td className={cn("px-3 py-2.5 text-right text-xs tabular-nums whitespace-nowrap", p.status !== "success" && "text-red-400")}>
                      {p.charged_currency && p.charged_amount !== null
                        ? money(p.charged_amount, p.charged_currency, locale)
                        : money(p.amount, p.currency, locale)}
                      {p.amount === 0 && <span className="block text-[10px] text-muted-foreground">{ko ? "무료 체험" : "Free trial"}</span>}
                      {p.status === "refunded" && <span className="block text-[10px]">{ko ? "환불" : "Refunded"}</span>}
                    </td>
                    <td className="px-3 py-2.5 text-xs">
                      {st ? <span className={cn("rounded px-1.5 py-0.5 font-medium", st.cls)}>{st[ko ? "ko" : "en"]}</span> : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{fmt(p.expires_at)}</td>
                    <td className="px-3 py-2.5 font-mono text-[11px] text-muted-foreground max-w-[200px] truncate" title={p.order_id ?? ""}>
                      {p.order_id || "—"}
                    </td>
                  </tr>
                );
              })}
              {(data?.items ?? []).length === 0 && (
                <tr>
                  <td colSpan={9} className="px-3 py-10 text-center text-sm text-muted-foreground">
                    {ko ? "결제 내역이 없습니다" : "No payments"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-3 flex items-center justify-center gap-3 text-sm">
          <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}
            className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-40">{ko ? "이전" : "Prev"}</button>
          <span className="tabular-nums text-muted-foreground">{page} / {totalPages}</span>
          <button type="button" disabled={page >= totalPages} onClick={() => setPage(page + 1)}
            className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-40">{ko ? "다음" : "Next"}</button>
        </div>
      )}
    </section>
  );
}
