"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import Link from "next/link";
import {
  FileText,
  ChevronDown,
  ChevronUp,
  Lock,
  TrendingUp,
  TrendingDown,
  Minus,
  BarChart3,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { SectionHeader } from "./SectionHeader";

/* ── Demo data ── */
const DEMO_WEEKLY = {
  week_label: "2026-W11",
  period_ko: "2026.03.09 ~ 03.15",
  period_en: "Mar 9 \u2013 Mar 15, 2026",
  highlights: [
    { title_ko: "우크라이나-러시아 긴장 고조", title_en: "Ukraine-Russia tensions escalate", severity: 85, change: +12 },
    { title_ko: "중동 에너지 공급 우려", title_en: "Middle East energy supply concerns", severity: 72, change: +5 },
    { title_ko: "미얀마 내전 격화", title_en: "Myanmar civil war intensifies", severity: 68, change: -3 },
  ],
  total_events: 847,
  new_clusters: 12,
  avg_severity: 45,
};

function severityColor(s: number) {
  if (s >= 80) return "text-red-500 bg-red-500/10";
  if (s >= 60) return "text-orange-500 bg-orange-500/10";
  if (s >= 40) return "text-amber-500 bg-amber-500/10";
  return "text-emerald-500 bg-emerald-500/10";
}

function severityBarColor(s: number) {
  if (s >= 80) return "bg-red-500";
  if (s >= 60) return "bg-orange-500";
  if (s >= 40) return "bg-amber-500";
  return "bg-emerald-500";
}

export function WeeklyReportCard() {
  const lang = useAppStore((s) => s.lang);
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <SectionHeader
        icon={<FileText className="h-3.5 w-3.5 text-cyan-400" />}
        titleKey="dash_weekly_report"
        descKey="dash_weekly_report_desc"
        badge={{ label: "Pro+", color: "bg-cyan-500/10 text-cyan-400" }}
      />
      <div className="rounded-xl border border-border bg-card fade-in-up overflow-hidden">
        {/* Header toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-card/80 transition-colors"
        >
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-foreground/80">
              {lang === "ko" ? "주간 리포트" : "Weekly Report"}
            </span>
            <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400">
              Pro+
            </span>
          </div>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        {/* Expanded content: demo data with blur + overlay */}
        {expanded && (
          <div className="relative border-t border-border/40">
            {/* Blurred demo content */}
            <div className="blur-[3px] opacity-60 pointer-events-none select-none px-4 pb-4 pt-3 space-y-3">
              {/* Period */}
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-foreground/80">
                  {DEMO_WEEKLY.week_label}
                </span>
                <span className="text-[9px] text-muted-foreground">
                  {lang === "ko" ? DEMO_WEEKLY.period_ko : DEMO_WEEKLY.period_en}
                </span>
              </div>

              {/* Stats row */}
              <div className="flex gap-2">
                <div className="flex-1 rounded-lg bg-muted/15 px-3 py-2 text-center">
                  <Activity className="h-3 w-3 mx-auto mb-1 text-muted-foreground" />
                  <p className="text-sm font-bold tabular-nums">{DEMO_WEEKLY.total_events}</p>
                  <p className="text-[8px] text-muted-foreground">
                    {lang === "ko" ? "총 이벤트" : "Total Events"}
                  </p>
                </div>
                <div className="flex-1 rounded-lg bg-muted/15 px-3 py-2 text-center">
                  <BarChart3 className="h-3 w-3 mx-auto mb-1 text-muted-foreground" />
                  <p className="text-sm font-bold tabular-nums">{DEMO_WEEKLY.new_clusters}</p>
                  <p className="text-[8px] text-muted-foreground">
                    {lang === "ko" ? "신규 클러스터" : "New Clusters"}
                  </p>
                </div>
                <div className="flex-1 rounded-lg bg-muted/15 px-3 py-2 text-center">
                  <div className={cn("h-3 w-3 mx-auto mb-1 rounded-full", severityBarColor(DEMO_WEEKLY.avg_severity))} />
                  <p className="text-sm font-bold tabular-nums">{DEMO_WEEKLY.avg_severity}</p>
                  <p className="text-[8px] text-muted-foreground">
                    {lang === "ko" ? "평균 심각도" : "Avg Severity"}
                  </p>
                </div>
              </div>

              {/* Highlights */}
              <div className="space-y-1.5">
                <span className="text-[9px] font-medium text-muted-foreground/60">
                  {lang === "ko" ? "주간 하이라이트" : "Weekly Highlights"}
                </span>
                {DEMO_WEEKLY.highlights.map((h, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 rounded-lg bg-muted/15 px-3 py-2"
                  >
                    <span className={cn("text-[10px] font-bold tabular-nums px-1.5 py-0.5 rounded-full shrink-0", severityColor(h.severity))}>
                      {h.severity}
                    </span>
                    <span className="text-[10px] font-medium flex-1 truncate">
                      {lang === "ko" ? h.title_ko : h.title_en}
                    </span>
                    <div className="flex items-center gap-0.5 shrink-0">
                      {h.change > 0 ? (
                        <TrendingUp className="h-3 w-3 text-red-500" />
                      ) : h.change < 0 ? (
                        <TrendingDown className="h-3 w-3 text-blue-500" />
                      ) : (
                        <Minus className="h-3 w-3 text-muted-foreground" />
                      )}
                      <span className={cn(
                        "text-[9px] font-bold tabular-nums",
                        h.change > 0 ? "text-red-500" : h.change < 0 ? "text-blue-500" : "text-muted-foreground",
                      )}>
                        {h.change > 0 ? `+${h.change}` : h.change}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Lock overlay */}
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/40 z-10">
              <Lock className="h-6 w-6 text-muted-foreground mb-2" />
              <p className="text-xs font-medium text-foreground/80 mb-2">
                {lang === "ko"
                  ? "Pro+ 플랜에서 이용 가능합니다"
                  : "Available on Pro+ plan"}
              </p>
              <Link
                href="/upgrade?source=weekly_report"
                className="inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[10px] font-bold text-white transition-transform hover:scale-105"
                style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
              >
                {t(lang, "dash_unlock_pro_plus")}
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
