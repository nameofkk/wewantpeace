"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { getFlag } from "@/lib/countries";
import { useAppStore } from "@/lib/store";
import { useWeeklyReport, useWeeklyPdf } from "@/lib/api";
import { t } from "@/lib/i18n";
import {
  FileText,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  Minus,
  Loader2,
  Lock,
  Calendar,
  Download,
  Info,
} from "lucide-react";
import { SectionHeader } from "./SectionHeader";
import dynamic from "next/dynamic";

const BarChart = dynamic(
  () => import("recharts").then((m) => m.BarChart),
  { ssr: false },
);
const Bar = dynamic(
  () => import("recharts").then((m) => m.Bar),
  { ssr: false },
);
const XAxis = dynamic(
  () => import("recharts").then((m) => m.XAxis),
  { ssr: false },
);
const YAxis = dynamic(
  () => import("recharts").then((m) => m.YAxis),
  { ssr: false },
);
const ResponsiveContainer = dynamic(
  () => import("recharts").then((m) => m.ResponsiveContainer),
  { ssr: false },
);
const Cell = dynamic(
  () => import("recharts").then((m) => m.Cell),
  { ssr: false },
);
const Tooltip = dynamic(
  () => import("recharts").then((m) => m.Tooltip),
  { ssr: false },
);

function impactColor(score: number) {
  if (score >= 70) return "#dc2626";
  if (score >= 50) return "#f97316";
  if (score >= 30) return "#f59e0b";
  return "#10b981";
}

export function WeeklyReportCard() {
  const lang = useAppStore((s) => s.lang);
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading, isError, error } = useWeeklyReport(expanded);
  const { data: pdfData } = useWeeklyPdf(expanded);

  const is403 = (error as any)?.status === 403;

  const issueChartData = data?.top_issues.slice(0, 7).map((issue) => ({
    name:
      issue.title.length > 8 ? issue.title.slice(0, 8) + ".." : issue.title,
    fullTitle: issue.title,
    impact: issue.impact_score,
    kscore: issue.kscore,
    flags: issue.country_codes.map((cc) => getFlag(cc)).join(""),
  }));

  return (
    <div>
      <SectionHeader
        icon={<FileText className="h-3.5 w-3.5 text-cyan-400" />}
        titleKey="dash_weekly_report"
        descKey="dash_weekly_report_desc"
        badge={{ label: "Pro+", color: "bg-cyan-500/10 text-cyan-400" }}
      />
      <div className="rounded-xl border border-border bg-card fade-in-up overflow-hidden">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-card/80 transition-colors"
        >
          <span className="text-xs font-medium text-foreground/80">
            {expanded
              ? lang === "ko"
                ? "접기"
                : "Collapse"
              : lang === "ko"
                ? "주간 리포트 보기"
                : "View weekly report"}
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        {expanded && (
          <div className="px-4 pb-4 border-t border-border/40">
            {isLoading && (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
              </div>
            )}

            {is403 && (
              <div className="py-4 text-center">
                <Lock className="h-5 w-5 text-muted-foreground mx-auto mb-2" />
                <p className="text-xs text-muted-foreground mb-2">
                  {lang === "ko"
                    ? "Pro+ 플랜에서 이용 가능합니다"
                    : "Available for Pro+ plan"}
                </p>
                <a
                  href="/upgrade"
                  className="inline-flex rounded-full px-3 py-1.5 text-[10px] font-bold text-white"
                  style={{
                    background: "linear-gradient(to right, #7c3aed, #6366f1)",
                  }}
                >
                  {t(lang, "dash_unlock_pro_plus")}
                </a>
              </div>
            )}

            {isError && !is403 && (
              <p className="py-4 text-xs text-muted-foreground text-center">
                {lang === "ko"
                  ? "리포트를 불러올 수 없습니다"
                  : "Failed to load report"}
              </p>
            )}

            {data && (
              <div className="space-y-4 mt-3">
                {/* Period + Highlight */}
                <div>
                  <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mb-1.5">
                    <Calendar className="h-3 w-3" />
                    {new Date(data.week_start).toLocaleDateString(
                      lang === "ko" ? "ko-KR" : "en-US",
                      { month: "short", day: "numeric" },
                    )}
                    {" — "}
                    {new Date(data.week_end).toLocaleDateString(
                      lang === "ko" ? "ko-KR" : "en-US",
                      { month: "short", day: "numeric" },
                    )}
                  </div>
                  <p className="text-[11px] text-foreground/80 leading-relaxed font-medium">
                    {data.highlight}
                  </p>
                </div>

                {/* Tension Summary */}
                <div className="flex items-center gap-3 rounded-lg bg-muted/20 p-3">
                  <div className="flex-1">
                    <p className="text-[10px] text-muted-foreground mb-0.5">
                      {lang === "ko" ? "홈 국가 긴장도" : "Home Tension"}
                    </p>
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-xl font-bold tabular-nums">
                        {Math.round(data.tension_summary.current)}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        /100
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {data.tension_summary.trend === "up" && (
                      <TrendingUp className="h-4 w-4 text-red-400" />
                    )}
                    {data.tension_summary.trend === "down" && (
                      <TrendingDown className="h-4 w-4 text-emerald-400" />
                    )}
                    {data.tension_summary.trend === "stable" && (
                      <Minus className="h-4 w-4 text-muted-foreground" />
                    )}
                    <span
                      className={cn(
                        "text-sm font-bold tabular-nums",
                        data.tension_summary.delta > 0
                          ? "text-red-400"
                          : data.tension_summary.delta < 0
                            ? "text-emerald-400"
                            : "text-muted-foreground",
                      )}
                    >
                      {data.tension_summary.delta > 0 ? "+" : ""}
                      {data.tension_summary.delta}
                    </span>
                  </div>
                </div>

                {/* Impact Score Chart */}
                {issueChartData && issueChartData.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold text-muted-foreground mb-2">
                      {lang === "ko"
                        ? "주요 이슈 영향도"
                        : "Top Issue Impact Scores"}
                    </p>
                    <div className="h-[160px] w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={issueChartData}
                          margin={{ top: 4, right: 4, bottom: 4, left: 0 }}
                        >
                          <XAxis
                            dataKey="name"
                            tick={{ fontSize: 8, fill: "#94a3b8" }}
                            interval={0}
                            angle={-20}
                            textAnchor="end"
                            height={40}
                          />
                          <YAxis
                            domain={[0, 100]}
                            tick={{ fontSize: 9, fill: "#94a3b8" }}
                            width={28}
                          />
                          <Tooltip
                            contentStyle={{
                              background: "#1e293b",
                              border: "none",
                              borderRadius: "8px",
                              fontSize: 11,
                              color: "#e2e8f0",
                            }}
                            formatter={(
                              value: any,
                              _name: any,
                              props: any,
                            ) => [
                              `${value}/100`,
                              `${props.payload.flags} ${props.payload.fullTitle}`,
                            ]}
                          />
                          <Bar dataKey="impact" radius={[4, 4, 0, 0]}>
                            {issueChartData.map((entry, idx) => (
                              <Cell
                                key={idx}
                                fill={impactColor(entry.impact)}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {/* Top Issues List */}
                {data.top_issues.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold text-muted-foreground mb-1.5">
                      {lang === "ko"
                        ? "이번 주 주요 이슈"
                        : "Top Issues This Week"}
                    </p>
                    <div className="space-y-1">
                      {data.top_issues.slice(0, 5).map((issue, idx) => (
                        <div
                          key={issue.cluster_id}
                          onClick={() =>
                            router.push(`/issues/${issue.cluster_id}`)
                          }
                          className="flex items-center gap-2 rounded-lg bg-muted/10 px-2.5 py-2 cursor-pointer hover:bg-muted/20 transition-colors fade-in-up"
                          style={{ animationDelay: `${idx * 40}ms` }}
                        >
                          <span className="text-[10px] font-bold text-muted-foreground w-4">
                            {idx + 1}
                          </span>
                          <span className="text-[11px]">
                            {issue.country_codes
                              .map((cc) => getFlag(cc))
                              .join(" ")}
                          </span>
                          <span className="flex-1 text-[11px] font-medium truncate">
                            {issue.title}
                          </span>
                          <div className="flex items-center gap-2 shrink-0">
                            <span
                              className="text-[9px] font-bold px-1.5 py-0.5 rounded-full"
                              style={{
                                color: impactColor(issue.impact_score),
                                backgroundColor: `${impactColor(issue.impact_score)}15`,
                              }}
                            >
                              {issue.impact_score}
                            </span>
                            <span className="text-[9px] text-muted-foreground tabular-nums">
                              K{issue.kscore.toFixed(1)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Footer: Stats + PDF */}
                <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-2 border-t border-border/30">
                  <div className="flex items-center gap-3">
                    <span>
                      {lang === "ko"
                        ? `총 ${data.total_events}건 이벤트`
                        : `${data.total_events} events total`}
                    </span>
                    <div className="flex items-center gap-1">
                      <Info className="h-3 w-3" />
                      <span className="text-[9px] text-muted-foreground/60">
                        {t(lang, "dash_ai_estimate")}
                      </span>
                    </div>
                  </div>
                  {pdfData?.available && pdfData.url && (
                    <a
                      href={pdfData.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20 transition-colors"
                    >
                      <Download className="h-3 w-3" />
                      <span className="font-medium">PDF</span>
                    </a>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
