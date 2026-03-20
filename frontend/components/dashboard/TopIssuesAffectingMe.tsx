"use client";

import React, { useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { cn, stripTitlePrefix, isJunkTitle, buildSmartTitle } from "@/lib/utils";
import { getFlag, getCountryName } from "@/lib/countries";
import { useAppStore } from "@/lib/store";
import { useClusters } from "@/lib/api";
import { t } from "@/lib/i18n";
import {
  TOPIC_COLORS,
  roundKScore,
  personalizedKScore,
  kscoreAccent,
  getKScoreBadge,
  type TrendingItem,
} from "@/lib/kscore-utils";
import { ChevronRight, Newspaper, AlertTriangle } from "lucide-react";
import { issueDetailPath } from "@/lib/toss-nav";
import { SectionHeader } from "./SectionHeader";

export function TopIssuesAffectingMe() {
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const homeCountry = useAppStore((s) => s.homeCountry);

  const { data: clusterData, isLoading } = useClusters({ limit: "2000" });

  const topItems = useMemo(() => {
    if (!clusterData || !Array.isArray(clusterData)) return [];
    return (clusterData as any[])
      .filter((c) => c.severity > 0 && c.kscore > 0)
      .map((c, i) => ({
        id: i,
        keyword: c.title,
        keyword_ko: c.title_ko,
        kscore: c.kscore,
        topic: c.topic,
        country_codes: c.country_code ? [c.country_code] : [],
        cluster_ids: [c.id],
        event_count: c.event_count,
        severity: c.severity,
        reason: "",
        calculated_at: c.last_event_at,
        first_event_at: c.first_event_at,
        independent_sources: c.independent_sources ?? 1,
      } as TrendingItem))
      .sort((a, b) => personalizedKScore(b, homeCountry) - personalizedKScore(a, homeCountry))
      .slice(0, 5);
  }, [clusterData, homeCountry]);

  if (isLoading) {
    return (
      <div>
        <SectionHeader
          icon={<AlertTriangle className="h-3.5 w-3.5 text-muted-foreground" />}
          titleKey="dash_top_issues"
          subtitleKey="dash_top_issues_sub"
          descKey="dash_top_issues_desc"
        />
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-[68px] rounded-xl bg-card border border-border overflow-hidden">
              <div className="h-full w-full animate-pulse bg-gradient-to-r from-transparent via-muted/30 to-transparent" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (topItems.length === 0) {
    return (
      <div>
        <SectionHeader
          icon={<AlertTriangle className="h-3.5 w-3.5 text-muted-foreground" />}
          titleKey="dash_top_issues"
          descKey="dash_top_issues_desc"
        />
        <div className="rounded-xl border border-border bg-card/50 p-5 text-center fade-in-up">
          <Newspaper className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">{t(lang, "dash_no_issues")}</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <SectionHeader
        icon={<AlertTriangle className="h-3.5 w-3.5 text-muted-foreground" />}
        titleKey="dash_top_issues"
        subtitleKey="dash_top_issues_sub"
        descKey="dash_top_issues_desc"
      />

      <div className="space-y-2">
        {topItems.map((item, idx) => {
          const topic = item.topic ?? "unknown";
          const pKScore = personalizedKScore(item, homeCountry);
          const k = roundKScore(pKScore);
          const badge = getKScoreBadge(pKScore, lang);
          const clusterId = item.cluster_ids?.[0];
          const rawTitle = lang === "en" ? item.keyword : (item.keyword_ko ?? item.keyword);
          const topicKey = `topic_${topic}` as Parameters<typeof t>[1];
          const topicLabel = t(lang, topicKey) || topic;
          const displayTitle = isJunkTitle(rawTitle)
            ? buildSmartTitle(item.keyword, topic, lang, getCountryName, item.country_codes[0])
            : (stripTitlePrefix(rawTitle) || topicLabel);

          return (
            <div
              key={item.id}
              onClick={clusterId ? () => router.push(issueDetailPath(clusterId)) : undefined}
              className={cn(
                "flex items-center gap-3 rounded-xl border border-border bg-card p-3 cursor-pointer",
                "hover:bg-card/80 transition-all border-l-4 fade-in-up",
                kscoreAccent(pKScore),
              )}
              style={{ animationDelay: `${idx * 60}ms` }}
            >
              {/* Rank */}
              <div className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold",
                idx === 0 ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"
              )}>
                {idx + 1}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide mb-0.5">
                  {item.country_codes.length > 0 && (
                    <span className="text-[11px]">
                      {item.country_codes.map((code: string) => getFlag(code)).join(" ")}
                    </span>
                  )}
                  <span className={cn(
                    "inline-flex items-center h-4 rounded-full px-1.5 text-[9px] font-medium leading-none",
                    TOPIC_COLORS[topic]
                  )}>
                    {topicLabel}
                  </span>
                  {(item.independent_sources ?? 0) >= 3 && (
                    <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-medium">
                      {lang === "ko" ? "검증됨" : "Verified"}
                    </span>
                  )}
                </div>
                <h4 className="text-[12px] font-semibold leading-snug line-clamp-1">{displayTitle}</h4>
              </div>

              {/* KScore */}
              <div className="shrink-0 text-right">
                <span className={cn("text-sm font-bold tabular-nums", badge.text)}>
                  {k.toFixed(1)}
                </span>
                <p className="text-[9px] text-muted-foreground">{t(lang, "dash_impact_score")}</p>
              </div>

              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            </div>
          );
        })}
      </div>

      {/* View All CTA */}
      <Link
        href="/feed"
        className="flex items-center justify-center gap-1.5 mt-3 rounded-xl border border-border bg-card/50 py-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-card/80 transition-colors"
      >
        <Newspaper className="h-3.5 w-3.5" />
        {t(lang, "dash_view_all_issues")}
      </Link>
    </div>
  );
}
