"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "@/lib/admin-utils";
import {
  FileBarChart, HelpCircle, ChevronDown, Users, Award, ArrowUpRight,
  Mail, AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface WeeklyPerf {
  week: string;
  sent: number;
  failed: number;
  total_users: number;
}

interface WeeklyPerfResponse {
  items: WeeklyPerf[];
}

interface ReferralKPI {
  total_codes: number;
  total_used: number;
  pro_converted: number;
  top_referrers: { user_id: string; email: string | null; nickname: string | null; referral_count: number }[];
}

/* ------------------------------------------------------------------ */
/*  Inline Guide                                                       */
/* ------------------------------------------------------------------ */
function InlineGuide({ lang }: { lang: "ko" | "en" }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-4 rounded-xl border border-border/50 bg-card/50">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <span className="flex items-center gap-1.5">
          <HelpCircle className="h-3.5 w-3.5" />
          {lang === "ko" ? "이 페이지 가이드" : "Page Guide"}
        </span>
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="px-4 pb-3 text-xs text-muted-foreground space-y-1">
          <p>{lang === "ko"
            ? "- 주간 리포트의 발송 성공/실패 현황을 확인합니다."
            : "- View weekly report send success/failure status."}</p>
          <p>{lang === "ko"
            ? "- 레퍼럴 코드 사용 현황과 Pro 전환율을 추적합니다."
            : "- Track referral code usage and Pro conversion rates."}</p>
          <p>{lang === "ko"
            ? "- Top 10 레퍼러를 확인하여 핵심 추천인을 파악합니다."
            : "- Identify key referrers through the Top 10 list."}</p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  KPI Card                                                           */
/* ------------------------------------------------------------------ */
function KpiCard({
  icon: Icon,
  label,
  value,
  subValue,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  subValue?: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={cn("rounded-lg p-2", color)}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p className="text-2xl font-bold">{typeof value === "number" ? value.toLocaleString() : value}</p>
      {subValue && <p className="text-xs text-muted-foreground mt-1">{subValue}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */
export default function AdminReportsPerfPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();

  const locale = lang === "en" ? "en-US" : "ko-KR";

  /* fetch helper */
  const fetchWithToken = async <T,>(path: string): Promise<T> => {
    if (!user) throw new Error("Unauthorized");
    const token = await user.getIdToken();
    const res = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    });
    if (!res.ok) throw new Error(`Admin API error: ${res.status}`);
    return res.json();
  };

  /* queries */
  const { data: weeklyData, isLoading: weeklyLoading } = useQuery<WeeklyPerfResponse>({
    queryKey: ["admin-reports-weekly-perf"],
    queryFn: () => fetchWithToken<WeeklyPerfResponse>("/admin/reports/weekly-performance"),
    enabled: !!user,
  });

  const { data: referralData, isLoading: referralLoading } = useQuery<ReferralKPI>({
    queryKey: ["admin-reports-referral-kpi"],
    queryFn: () => fetchWithToken<ReferralKPI>("/admin/reports/referral-kpi"),
    enabled: !!user,
  });

  const weeklyItems = weeklyData?.items ?? [];

  return (
    <div>
      <InlineGuide lang={lang} />

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <FileBarChart className="h-6 w-6 text-primary" />
          {lang === "ko" ? "리포트 성과" : "Reports Performance"}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {lang === "ko" ? "주간 리포트 발송 현황 및 레퍼럴 KPI" : "Weekly report delivery and referral KPIs"}
        </p>
      </div>

      {/* Section 1: Weekly Report Performance */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Mail className="h-4 w-4 text-muted-foreground" />
          {lang === "ko" ? "주간 리포트 발송 현황" : "Weekly Report Performance"}
        </h2>

        {weeklyLoading ? (
          <div className="rounded-xl border border-border overflow-hidden">
            <div className="bg-secondary/50 h-10" />
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="border-t border-border px-4 py-4">
                <div className="h-4 bg-secondary/50 rounded animate-pulse w-full" />
              </div>
            ))}
          </div>
        ) : weeklyItems.length === 0 ? (
          <div className="flex flex-col items-center py-12 text-muted-foreground">
            <Mail className="h-10 w-10 mb-3" />
            <p className="text-sm">{lang === "ko" ? "발송 데이터가 없습니다" : "No delivery data"}</p>
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block rounded-xl border border-border overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-secondary/50">
                  <tr>
                    <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "주차" : "Week"}</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "대상 유저" : "Total Users"}</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "발송 성공" : "Sent"}</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "발송 실패" : "Failed"}</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "성공률" : "Success Rate"}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {weeklyItems.map((w) => {
                    const rate = w.sent + w.failed > 0
                      ? ((w.sent / (w.sent + w.failed)) * 100).toFixed(1)
                      : "0.0";
                    return (
                      <tr key={w.week} className="hover:bg-secondary/20">
                        <td className="px-4 py-3 text-xs font-medium">{w.week}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{w.total_users.toLocaleString(locale)}</td>
                        <td className="px-4 py-3 text-xs text-green-400">{w.sent.toLocaleString(locale)}</td>
                        <td className="px-4 py-3 text-xs text-red-400">{w.failed.toLocaleString(locale)}</td>
                        <td className="px-4 py-3">
                          <span className={cn(
                            "rounded-full px-2 py-0.5 text-[10px] font-medium",
                            Number(rate) >= 95 ? "bg-green-500/20 text-green-400" :
                            Number(rate) >= 80 ? "bg-yellow-500/20 text-yellow-400" :
                            "bg-red-500/20 text-red-400"
                          )}>
                            {rate}%
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden space-y-3">
              {weeklyItems.map((w) => {
                const rate = w.sent + w.failed > 0
                  ? ((w.sent / (w.sent + w.failed)) * 100).toFixed(1)
                  : "0.0";
                return (
                  <div key={w.week} className="rounded-xl border border-border bg-card p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium">{w.week}</span>
                      <span className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-medium",
                        Number(rate) >= 95 ? "bg-green-500/20 text-green-400" :
                        Number(rate) >= 80 ? "bg-yellow-500/20 text-yellow-400" :
                        "bg-red-500/20 text-red-400"
                      )}>
                        {rate}%
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <span className="text-muted-foreground">{lang === "ko" ? "대상" : "Users"}</span>
                        <p className="font-medium">{w.total_users.toLocaleString(locale)}</p>
                      </div>
                      <div>
                        <span className="text-green-400">{lang === "ko" ? "성공" : "Sent"}</span>
                        <p className="font-medium text-green-400">{w.sent.toLocaleString(locale)}</p>
                      </div>
                      <div>
                        <span className="text-red-400">{lang === "ko" ? "실패" : "Failed"}</span>
                        <p className="font-medium text-red-400">{w.failed.toLocaleString(locale)}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Section 2: Referral KPI */}
      <div>
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Users className="h-4 w-4 text-muted-foreground" />
          {lang === "ko" ? "레퍼럴 KPI" : "Referral KPI"}
        </h2>

        {referralLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-4">
                <div className="h-4 bg-secondary/50 rounded animate-pulse w-1/2 mb-3" />
                <div className="h-8 bg-secondary/50 rounded animate-pulse w-2/3" />
              </div>
            ))}
          </div>
        ) : referralData ? (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
              <KpiCard
                icon={Award}
                label={lang === "ko" ? "총 레퍼럴 코드" : "Total Referral Codes"}
                value={referralData.total_codes}
                color="bg-blue-500/10 text-blue-400"
              />
              <KpiCard
                icon={ArrowUpRight}
                label={lang === "ko" ? "사용된 코드" : "Codes Used"}
                value={referralData.total_used}
                subValue={referralData.total_codes > 0
                  ? `${((referralData.total_used / referralData.total_codes) * 100).toFixed(1)}% ${lang === "ko" ? "사용률" : "usage rate"}`
                  : undefined}
                color="bg-green-500/10 text-green-400"
              />
              <KpiCard
                icon={AlertTriangle}
                label={lang === "ko" ? "Pro 전환" : "Pro Converted"}
                value={referralData.pro_converted}
                subValue={referralData.total_used > 0
                  ? `${((referralData.pro_converted / referralData.total_used) * 100).toFixed(1)}% ${lang === "ko" ? "전환률" : "conversion rate"}`
                  : undefined}
                color="bg-purple-500/10 text-purple-400"
              />
            </div>

            {/* Top 10 Referrers */}
            <h3 className="text-sm font-semibold mb-3">
              {lang === "ko" ? "Top 10 레퍼러" : "Top 10 Referrers"}
            </h3>

            {referralData.top_referrers.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground text-sm">
                {lang === "ko" ? "레퍼럴 데이터 없음" : "No referral data"}
              </div>
            ) : (
              <>
                {/* Desktop */}
                <div className="hidden md:block rounded-xl border border-border overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-secondary/50">
                      <tr>
                        <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">#</th>
                        <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "닉네임" : "Nickname"}</th>
                        <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "이메일" : "Email"}</th>
                        <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "레퍼럴 수" : "Referrals"}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {referralData.top_referrers.map((r, i) => (
                        <tr key={r.user_id} className="hover:bg-secondary/20">
                          <td className="px-4 py-3 text-xs font-medium text-muted-foreground">{i + 1}</td>
                          <td className="px-4 py-3 text-xs">{r.nickname ?? "\u2014"}</td>
                          <td className="px-4 py-3 text-xs text-muted-foreground">{r.email ?? "\u2014"}</td>
                          <td className="px-4 py-3">
                            <span className="rounded-full bg-primary/10 text-primary px-2 py-0.5 text-[10px] font-medium">
                              {r.referral_count}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile */}
                <div className="md:hidden space-y-2">
                  {referralData.top_referrers.map((r, i) => (
                    <div key={r.user_id} className="flex items-center gap-3 rounded-xl border border-border bg-card p-3">
                      <span className="text-xs font-bold text-muted-foreground w-5 text-center">{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium truncate">{r.nickname ?? r.email ?? "\u2014"}</p>
                        {r.nickname && r.email && (
                          <p className="text-[10px] text-muted-foreground truncate">{r.email}</p>
                        )}
                      </div>
                      <span className="rounded-full bg-primary/10 text-primary px-2 py-0.5 text-[10px] font-medium shrink-0">
                        {r.referral_count}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        ) : (
          <div className="text-center py-12 text-muted-foreground text-sm">
            {lang === "ko" ? "데이터를 불러올 수 없습니다" : "Failed to load data"}
          </div>
        )}
      </div>
    </div>
  );
}
