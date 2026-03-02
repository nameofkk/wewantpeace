"use client";

import { useState, useEffect } from "react";
import { adminFetch } from "@/lib/admin-utils";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";

interface KpiData {
  period_days: number;
  a1_onboarding_rate: number;
  paywall_conversion_rate: number;
  trial_to_paid_rate: number;
  d7_retention_rate: number;
  raw: Record<string, number>;
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

export default function KpiPage() {
  const lang = useAppStore((s) => s.lang);
  const [kpi, setKpi] = useState<KpiData | null>(null);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    adminFetch<KpiData>(`/admin/kpi?days=${days}`)
      .then(setKpi)
      .catch(() => setKpi(null))
      .finally(() => setLoading(false));
  }, [days]);

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
            {lang === "ko" ? "KPI 대시보드" : "KPI Dashboard"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {lang === "ko"
              ? "Phase Gate 핵심 지표를 실시간으로 추적합니다"
              : "Track Phase Gate key metrics in real time"}
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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label={lang === "ko" ? "온보딩 완료율 (A1)" : "Onboarding Rate (A1)"}
          value={kpi.a1_onboarding_rate}
          color="text-blue-500"
        />
        <KpiCard
          label={lang === "ko" ? "Paywall 전환율" : "Paywall Conversion"}
          value={kpi.paywall_conversion_rate}
          color="text-green-500"
        />
        <KpiCard
          label={lang === "ko" ? "Trial → Paid 전환율" : "Trial → Paid Rate"}
          value={kpi.trial_to_paid_rate}
          color="text-purple-500"
        />
        <KpiCard
          label={lang === "ko" ? "D7 리텐션" : "D7 Retention"}
          value={kpi.d7_retention_rate}
          color="text-orange-500"
        />
      </div>

      {/* Raw Metrics Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border">
          <h2 className="text-sm font-semibold">
            {lang === "ko" ? "원시 이벤트 카운트" : "Raw Event Counts"}
          </h2>
        </div>
        <div className="divide-y divide-border">
          {Object.entries(kpi.raw)
            .sort(([, a], [, b]) => b - a)
            .map(([key, val]) => (
              <div
                key={key}
                className="flex items-center justify-between px-5 py-2.5 text-sm"
              >
                <span className="text-muted-foreground font-mono text-xs">
                  {key}
                </span>
                <span className="font-medium tabular-nums">{val.toLocaleString()}</span>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
