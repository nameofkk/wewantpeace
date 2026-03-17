"use client";

import { useState, useEffect } from "react";
import { adminFetch } from "@/lib/admin-utils";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { HelpCircle, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface KpiData {
  period_days: number;
  a1_onboarding_rate: number;
  paywall_conversion_rate: number;
  trial_to_paid_rate: number;
  promo_to_paid_rate: number;
  discount_conversion_rate: number;
  d7_retention_rate: number;
  raw: Record<string, number>;
}

interface KpiSnapshot {
  week: string;
  a1_onboarding_rate: number;
  paywall_conversion_rate: number;
  trial_to_paid_rate: number;
  d7_retention_rate: number;
}

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
          {t(lang, "admin_page_guide")}
        </span>
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="px-4 pb-3 text-xs text-muted-foreground space-y-1 leading-relaxed">
          <p>
            {lang === "ko"
              ? "온보딩 완료율, 유료 전환율, 체험판→유료 전환율, 7일 재방문율을 실시간으로 추적합니다. 주간 추이에서 전주 대비 비교가 가능합니다."
              : "Track onboarding rate, paid conversion, trial-to-paid rate, and D7 retention in real time. Use the weekly trend for week-over-week comparisons."}
          </p>
        </div>
      )}
    </div>
  );
}

function KpiCard({
  label,
  value,
  suffix,
  color,
}: {
  label: string;
  value: number;
  suffix?: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className={`text-3xl font-bold ${color}`}>
        {value}
        <span className="text-lg font-normal text-muted-foreground ml-0.5">
          {suffix || "%"}
        </span>
      </p>
    </div>
  );
}

function WowBadge({ delta }: { delta: number }) {
  const isPositive = delta > 0;
  const isSevereDrop = delta <= -30;
  const colorClass = isSevereDrop
    ? "bg-orange-500/20 text-orange-400"
    : isPositive
      ? "bg-green-500/20 text-green-400"
      : delta < 0
        ? "bg-red-500/20 text-red-400"
        : "bg-secondary text-muted-foreground";
  const sign = delta > 0 ? "+" : "";
  return (
    <span className={cn("rounded-full px-1.5 py-0.5 text-[10px] font-medium", colorClass)}>
      {sign}{delta.toFixed(1)}
    </span>
  );
}

const RAW_METRIC_LABELS_KO: Record<string, string> = {
  auth_success: "로그인 성공",
  onboarding_complete: "온보딩 완료",
  dashboard_view: "대시보드 조회",
  issue_view: "이슈 상세 조회",
  map_view: "지도 조회",
  alert_click: "알림 클릭",
  share_click: "공유 클릭",
  paywall_shown: "페이월 노출",
  paywall_purchase: "페이월 결제",
  trial_started: "체험판 시작",
  trial_converted: "체험판 → 유료 전환",
  promo_started: "프로모션 시작",
  promo_converted: "프로모션 → 유료 전환",
  discount_eligible: "할인 대상",
  discount_converted: "할인 전환",
  active_referral_users: "추천 활성 유저",
  d7_cohort: "D7 코호트 (7~14일 전 가입)",
  d7_retained: "D7 재방문 유저",
  push_sent: "푸시 발송",
  push_clicked: "푸시 클릭",
  subscription_created: "구독 생성",
  subscription_cancelled: "구독 취소",
};

export default function KpiPage() {
  const lang = useAppStore((s) => s.lang);
  const [kpi, setKpi] = useState<KpiData | null>(null);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [snapshots, setSnapshots] = useState<KpiSnapshot[]>([]);
  const [snapshotsLoading, setSnapshotsLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    adminFetch<KpiData>(`/admin/kpi?days=${days}`)
      .then(setKpi)
      .catch(() => setKpi(null))
      .finally(() => setLoading(false));
  }, [days]);

  useEffect(() => {
    setSnapshotsLoading(true);
    adminFetch<KpiSnapshot[]>(`/admin/kpi/snapshots?weeks=8`)
      .then(setSnapshots)
      .catch(() => setSnapshots([]))
      .finally(() => setSnapshotsLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!kpi) {
    return (
      <div className="text-center py-20 text-muted-foreground">
        {lang === "ko" ? "KPI 데이터를 불러올 수 없습니다" : "Failed to load KPI data"}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">
            {lang === "ko" ? "핵심 지표" : "KPI Dashboard"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {lang === "ko"
              ? "서비스 핵심 지표를 실시간으로 추적합니다"
              : "Track key metrics in real time"}
          </p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-lg border border-border bg-card px-3 py-1.5 text-sm"
        >
          <option value={7}>{lang === "ko" ? "최근 7일" : "Last 7 days"}</option>
          <option value={14}>{lang === "ko" ? "최근 14일" : "Last 14 days"}</option>
          <option value={30}>{lang === "ko" ? "최근 30일" : "Last 30 days"}</option>
        </select>
      </div>

      {/* Inline Guide */}
      <InlineGuide lang={lang} />

      {/* KPI Cards — Phase Gate */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label={lang === "ko" ? "온보딩 완료율" : "Onboarding Rate"}
          value={kpi.a1_onboarding_rate}
          color="text-blue-500"
        />
        <KpiCard
          label={lang === "ko" ? "유료 전환율" : "Paid Conversion"}
          value={kpi.paywall_conversion_rate}
          color="text-green-500"
        />
        <KpiCard
          label={lang === "ko" ? "체험판 → 유료 전환" : "Trial → Paid Rate"}
          value={kpi.trial_to_paid_rate}
          color="text-purple-500"
        />
        <KpiCard
          label={lang === "ko" ? "7일 재방문율" : "D7 Retention"}
          value={kpi.d7_retention_rate}
          color="text-orange-500"
        />
      </div>

      {/* 전환 유도 효과 카드 */}
      <div>
        <h2 className="text-sm font-semibold mb-3">
          {lang === "ko" ? "전환 분석" : "Conversion Pipeline"}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            label={lang === "ko" ? "프로모 → 유료 전환" : "Promo → Paid Rate"}
            value={kpi.promo_to_paid_rate}
            color="text-cyan-500"
          />
          <KpiCard
            label={lang === "ko" ? "할인 전환율" : "Discount Conversion"}
            value={kpi.discount_conversion_rate}
            color="text-pink-500"
          />
          <KpiCard
            label={lang === "ko" ? "추천 활성 유저" : "Active Referral Users"}
            value={kpi.raw.active_referral_users ?? 0}
            suffix={lang === "ko" ? "명" : ""}
            color="text-amber-500"
          />
          <div className="rounded-xl border border-border bg-card p-5">
            <p className="text-xs text-muted-foreground mb-1">
              {lang === "ko" ? "할인 대상 / 유료 전환" : "Discount Eligible / Converted"}
            </p>
            <p className="text-2xl font-bold text-muted-foreground">
              {kpi.raw.discount_eligible ?? 0}
              <span className="text-base mx-1">/</span>
              <span className="text-pink-500">{kpi.raw.discount_converted ?? 0}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Raw Metrics Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border">
          <h2 className="text-sm font-semibold">
            {lang === "ko" ? "상세 수치" : "Detailed Counts"}
          </h2>
        </div>
        <div className="divide-y divide-border">
          {Object.entries(kpi.raw)
            .sort(([, a], [, b]) => b - a)
            .map(([key, val]) => {
              const label = lang === "ko" ? (RAW_METRIC_LABELS_KO[key] ?? key) : key;
              return (
                <div
                  key={key}
                  className="flex items-center justify-between px-5 py-2.5 text-sm"
                >
                  <span className="text-muted-foreground text-xs">
                    {label}
                  </span>
                  <span className="font-medium tabular-nums">{val.toLocaleString()}</span>
                </div>
              );
            })}
        </div>
      </div>

      {/* Weekly Trend */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border">
          <h2 className="text-sm font-semibold">
            {t(lang, "admin_kpi_weekly")}
          </h2>
        </div>
        {snapshotsLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-5 w-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : snapshots.length === 0 ? (
          <div className="text-center py-12 text-sm text-muted-foreground">
            {lang === "ko" ? "스냅샷 데이터가 없습니다" : "No snapshot data available"}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    {lang === "ko" ? "주차" : "Week"}
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    {lang === "ko" ? "온보딩" : "Onboarding"}
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    {lang === "ko" ? "유료전환" : "Paid Conv."}
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    {lang === "ko" ? "체험→유료" : "Trial→Paid"}
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    {lang === "ko" ? "7일 재방문" : "D7 Retention"}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {snapshots.map((snap, idx) => {
                  const prev = idx < snapshots.length - 1 ? snapshots[idx + 1] : null;
                  const deltas = prev
                    ? {
                        onboarding: snap.a1_onboarding_rate - prev.a1_onboarding_rate,
                        paywall: snap.paywall_conversion_rate - prev.paywall_conversion_rate,
                        trial: snap.trial_to_paid_rate - prev.trial_to_paid_rate,
                        retention: snap.d7_retention_rate - prev.d7_retention_rate,
                      }
                    : null;
                  const hasAlert = deltas
                    ? Object.values(deltas).some((d) => d <= -30)
                    : false;
                  return (
                    <tr
                      key={snap.week}
                      className={cn(
                        "hover:bg-secondary/20",
                        hasAlert && "bg-red-500/5"
                      )}
                    >
                      <td className="px-3 py-2.5 text-xs font-medium">
                        {snap.week}
                        {hasAlert && (
                          <span className="ml-1.5 rounded-full bg-red-500/20 px-1.5 py-0.5 text-[9px] font-bold text-red-400">
                            {t(lang, "admin_kpi_alert")}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-xs tabular-nums">
                        {snap.a1_onboarding_rate}%
                        {deltas && <span className="ml-1"><WowBadge delta={deltas.onboarding} /></span>}
                      </td>
                      <td className="px-3 py-2.5 text-xs tabular-nums">
                        {snap.paywall_conversion_rate}%
                        {deltas && <span className="ml-1"><WowBadge delta={deltas.paywall} /></span>}
                      </td>
                      <td className="px-3 py-2.5 text-xs tabular-nums">
                        {snap.trial_to_paid_rate}%
                        {deltas && <span className="ml-1"><WowBadge delta={deltas.trial} /></span>}
                      </td>
                      <td className="px-3 py-2.5 text-xs tabular-nums">
                        {snap.d7_retention_rate}%
                        {deltas && <span className="ml-1"><WowBadge delta={deltas.retention} /></span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
