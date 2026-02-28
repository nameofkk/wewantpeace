"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, AlertTriangle, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { COUNTRY_MAP } from "@/lib/countries";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t, getTensionLevelLabel } from "@/lib/i18n";
import { API_BASE } from "@/lib/api";

interface ClusterOut {
  id: string;
  cluster_key: string;
  topic: string;
  title: string;
  title_ko: string | null;
  lat: number | null;
  lon: number | null;
  country_code: string | null;
  severity: number;
  confidence: number;
  event_count: number;
  is_spike: boolean;
  is_verified: boolean;
  kscore: number;
  first_event_at: string;
  last_event_at: string;
}

function getSeverityColor(severity: number): string {
  if (severity >= 80) return "#991b1b";   // 극심 - dark maroon
  if (severity >= 60) return "#ef4444";   // 심각 - red
  if (severity >= 40) return "#f97316";   // 경계 - orange
  if (severity >= 20) return "#f59e0b";   // 주의 - amber
  return "#22c55e";                        // 안정 - green
}

const TENSION_BG: Record<number, string> = {
  0: "bg-green-500/20 text-green-400",
  1: "bg-amber-500/30 text-amber-300",
  2: "bg-orange-500/40 text-orange-300",
  3: "bg-red-500/40 text-red-400",
  4: "bg-red-900/50 text-red-100",
};

export default function CountryIssuesPage() {
  const { code } = useParams<{ code: string }>();
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const countryInfo = COUNTRY_MAP[code as keyof typeof COUNTRY_MAP];
  const displayName = lang === "en"
    ? (() => { try { return new Intl.DisplayNames(["en"], { type: "region" }).of(code) || (countryInfo?.name ?? code); } catch { return countryInfo?.name ?? code; } })()
    : (countryInfo?.name ?? code);
  const countryName = countryInfo ? `${countryInfo.flag} ${displayName}` : displayName;

  const { data: clusters, isLoading, isError } = useQuery<ClusterOut[]>({
    queryKey: ["issues", "country", code],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/issues?country_code=${code}&limit=100`);
      if (!res.ok) throw new Error("Failed to fetch");
      return res.json();
    },
    staleTime: 2 * 60 * 1000,
  });

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* 헤더 */}
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <button onClick={() => router.back()} className="text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-base font-bold">{t(lang, "country_issues_title", { country: countryName })}</h1>
          {clusters && (
            <p className="text-[11px] text-muted-foreground">{t(lang, "country_issues_count", { n: clusters.length })}</p>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {isLoading && (
          <div className="flex justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {isError && (
          <div className="py-16 text-center text-sm text-muted-foreground">
            {t(lang, "country_issues_error")}
          </div>
        )}

        {clusters?.length === 0 && (
          <div className="py-16 text-center text-sm text-muted-foreground">
            {t(lang, "country_issues_empty", { country: countryName })}
          </div>
        )}

        {clusters?.map((cluster) => {
          const color = getSeverityColor(cluster.severity);
          const level = (cluster.severity >= 80 ? 4 : cluster.severity >= 60 ? 3 : cluster.severity >= 40 ? 2 : cluster.severity >= 20 ? 1 : 0) as 0 | 1 | 2 | 3 | 4;
          const levelLabel = getTensionLevelLabel(level, lang);
          const topicKey = `topic_${cluster.topic}` as Parameters<typeof t>[1];
          const clusterTitle = lang === "en" ? cluster.title : (cluster.title_ko ?? cluster.title);
          const locale = lang === "en" ? "en-US" : "ko-KR";

          function formatTime(iso: string): string {
            const d = new Date(iso);
            const now = new Date();
            const isToday = d.toDateString() === now.toDateString();
            if (isToday) return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
            return d.toLocaleDateString(locale, { month: "short", day: "numeric" });
          }

          return (
            <Link
              key={cluster.id}
              href={`/issues/${cluster.id}`}
              className="block rounded-xl border bg-card p-4 hover:border-primary/30 transition-colors"
              style={{ borderLeftWidth: 3, borderLeftColor: color }}
            >
              <div className="flex items-start gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
                    {cluster.is_spike && (
                      <span className="flex items-center gap-0.5 rounded-full bg-red-500/20 px-1.5 py-0.5 text-[10px] font-bold text-red-400">
                        <AlertTriangle className="h-2.5 w-2.5" /> {t(lang, "country_issue_spike")}
                      </span>
                    )}
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", TENSION_BG[level])}>
                      {levelLabel}
                    </span>
                    <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                      {t(lang, topicKey)}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold leading-snug">
                    {clusterTitle}
                  </h3>
                  <div className="flex items-center gap-3 mt-2 text-[11px] text-muted-foreground">
                    <span>{t(lang, "country_stat_severity")} <span className="font-medium" style={{ color }}>{cluster.severity}</span></span>
                    <span>{t(lang, "country_stat_events")} {cluster.event_count}</span>
                    <span>KScore {cluster.kscore.toFixed(1)}</span>
                    <span className="ml-auto">{formatTime(cluster.last_event_at)}</span>
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
