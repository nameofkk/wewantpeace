"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { getFlag, getCountryName } from "@/lib/countries";
import { t, type TranslationKey } from "@/lib/i18n";
import {
  TOPIC_COLORS,
  type TrendingItem,
} from "@/lib/kscore-utils";
import { stripTitlePrefix, isJunkTitle, buildSmartTitle } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";
import { issueDetailPath } from "@/lib/toss-nav";
import type { MarketSnapshot } from "@/lib/api";

/* ── Impact score color helpers ── */

function impactScoreColor(score: number) {
  if (score >= 70) return { text: "text-red-500", bar: "bg-red-500", border: "border-l-red-500" };
  if (score >= 40) return { text: "text-orange-500", bar: "bg-orange-500", border: "border-l-orange-500" };
  return { text: "text-emerald-500", bar: "bg-emerald-500", border: "border-l-emerald-500" };
}

/* ── Full card for #1 issue ── */

interface SmartSummaryFullProps {
  item: TrendingItem;
  homeCountry: string;
  lang: "ko" | "en";
  market?: MarketSnapshot | null;
  topIssueRaw?: any;
  isPro: boolean;
}

function getRelevantMarketChips(cc: string, market: MarketSnapshot | null | undefined, recommended?: string[] | null) {
  if (!market) return [];
  const toChip = (i: { symbol: string; name: string; value: number; change_pct: number }) => ({
    symbol: i.symbol, name: i.name, price_usd: i.value, change_pct: i.change_pct,
  });
  // 백엔드 추천 심볼이 있으면 우선 사용
  if (recommended?.length) {
    const chips = market.commodities.filter((c) => recommended.includes(c.symbol));
    if (chips.length > 0) return chips;
  }
  // 폴백: 이벤트 국가별 관련 원자재/지수
  const OIL = ["IL", "IR", "IQ", "SA", "SY", "LB", "YE", "KW", "LY", "AE"];
  const GRAIN = ["UA", "RU", "BR", "AR", "AU"];
  const RICE = ["IN", "TH", "VN", "MM", "PH", "ID"];
  const SHIP = ["EG", "PA", "SO", "YE", "SG"];
  if (OIL.includes(cc))
    return market.commodities.filter((c) => ["WTI", "BRENT"].includes(c.symbol));
  if (GRAIN.includes(cc))
    return market.commodities.filter((c) => ["WHEAT", "CORN", "SOYBEAN"].includes(c.symbol)).slice(0, 2);
  if (RICE.includes(cc))
    return market.commodities.filter((c) => ["RICE", "WHEAT"].includes(c.symbol)).slice(0, 2);
  if (SHIP.includes(cc))
    return market.commodities.filter((c) => ["BDRY", "WTI"].includes(c.symbol));
  return market.commodities.slice(0, 1);
}

export function SmartSummaryCardFull({ item, homeCountry, lang, market, topIssueRaw, isPro }: SmartSummaryFullProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);

  const topic = item.topic ?? "unknown";
  const clusterId = item.cluster_ids?.[0];
  const rawTitle = lang === "en" ? item.keyword : (item.keyword_ko ?? item.keyword);
  const topicKey = `topic_${topic}` as TranslationKey;
  const topicLabel = t(lang, topicKey) || topic;
  const displayTitle = isJunkTitle(rawTitle)
    ? buildSmartTitle(item.keyword, topic, lang, getCountryName, item.country_codes[0])
    : (stripTitlePrefix(rawTitle) || topicLabel);

  const impactScore = topIssueRaw?.impact_score ?? 0;
  const cc = item.country_codes?.[0] ?? "";
  const marketChips = getRelevantMarketChips(cc, market, topIssueRaw?.relevant_commodities);
  const colors = impactScoreColor(impactScore);

  const whatLine = topIssueRaw?.what_line;
  const soWhatLine = topIssueRaw?.so_what_line;
  const whenLine = topIssueRaw?.when_line;
  const bodySnippet = topIssueRaw?.body_snippet;

  return (
    <section
      className={cn("rounded-xl border border-border bg-card overflow-hidden cursor-pointer border-l-[3px]", colors.border)}
      onClick={clusterId ? () => router.push(issueDetailPath(clusterId)) : undefined}
    >
      {/* ── Header: Title + Impact Score ── */}
      <div className="px-3.5 pt-3 pb-2.5">
        <div className="flex items-start gap-2.5">
          <div className="flex-1 min-w-0">
            {/* Flags + Title */}
            <div className="flex items-center gap-1.5 mb-1.5">
              {item.country_codes.length > 0 && (
                <span className="text-sm shrink-0">
                  {item.country_codes.slice(0, 3).map((code: string) => getFlag(code)).join("")}
                </span>
              )}
              <h3 className="text-[13px] font-bold text-foreground leading-snug line-clamp-2">{displayTitle}</h3>
            </div>
            {/* Topic + badges row */}
            <div className="flex items-center gap-1.5 flex-nowrap overflow-x-auto scrollbar-hide">
              <span className={cn(
                "inline-flex items-center h-[18px] rounded-full px-2 text-[9px] font-medium leading-none shrink-0",
                TOPIC_COLORS[topic]
              )}>
                {topicLabel}
              </span>
              {item.is_spike && (
                <span className="text-[8px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 font-semibold shrink-0">
                  SPIKE
                </span>
              )}
              {(item.confidence ?? 0) >= 0.7 && (
                <span className="text-[8px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-semibold shrink-0">
                  {t(lang, "dash_badge_verified" as TranslationKey)}
                </span>
              )}
            </div>
          </div>
          {/* Impact Score */}
          <div className="shrink-0 text-right">
            <div className={cn("text-2xl font-bold tabular-nums leading-none", colors.text)}>{impactScore}</div>
            <div className="text-[8px] text-muted-foreground mt-0.5">{lang === "ko" ? "영향도" : "Impact"}</div>
          </div>
        </div>
      </div>

      {/* ── 3-line Smart Summary ── */}
      <div className="px-3.5 py-3 space-y-2.5 border-t border-border/20">
        {whatLine && (
          <div className="flex gap-2.5">
            <div className="shrink-0 w-[3px] rounded-full bg-red-400 self-stretch" />
            <div className="min-w-0">
              <span className="text-[9px] font-bold text-red-400 block mb-0.5">
                {t(lang, "dash_smart_what" as TranslationKey)}
              </span>
              <span className="text-[11px] text-foreground/80 leading-snug line-clamp-2 block">{whatLine}</span>
            </div>
          </div>
        )}
        {soWhatLine && (
          <div className="flex gap-2.5">
            <div className="shrink-0 w-[3px] rounded-full bg-orange-400 self-stretch" />
            <div className="min-w-0">
              <span className="text-[9px] font-bold text-orange-400 block mb-0.5">
                {t(lang, "dash_smart_so_what" as TranslationKey)}
              </span>
              <span className="text-[11px] text-foreground/80 leading-snug font-medium line-clamp-2 block">{soWhatLine}</span>
            </div>
          </div>
        )}
        {whenLine && (
          <div className="flex gap-2.5">
            <div className="shrink-0 w-[3px] rounded-full bg-blue-400 self-stretch" />
            <div className="min-w-0">
              <span className="text-[9px] font-bold text-blue-400 block mb-0.5">
                {t(lang, "dash_smart_when" as TranslationKey)}
              </span>
              <span className="text-[11px] text-foreground/70 leading-snug block">{whenLine}</span>
            </div>
          </div>
        )}
      </div>

      {/* ── Impact score bar ── */}
      <div className="px-3.5 pb-2.5">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-muted/30 rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all", colors.bar)}
              style={{ width: `${Math.min(impactScore, 100)}%` }}
            />
          </div>
          <span className={cn("text-[9px] font-bold tabular-nums", colors.text)}>{impactScore}/100</span>
        </div>
      </div>

      {/* ── Market chips ── */}
      {marketChips.length > 0 && (
        <div className="px-3.5 pb-2.5">
          <div className="flex gap-1.5 overflow-x-auto scrollbar-hide">
            {marketChips.map((m) => (
              <span key={m.symbol} className="shrink-0 inline-flex items-center gap-1 rounded-md bg-muted/20 px-2 py-1 text-[9px]">
                <span className="font-medium">{m.name}</span>
                <span className="tabular-nums">${m.price_usd.toLocaleString()}</span>
                <span className={cn("font-semibold tabular-nums", m.change_pct > 0 ? "text-red-500" : m.change_pct < 0 ? "text-blue-500" : "text-muted-foreground")}>
                  {m.change_pct > 0 ? "+" : ""}{m.change_pct.toFixed(1)}%
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Body snippet (Pro, collapsible) ── */}
      {isPro && bodySnippet && (
        <div className="px-3.5 pb-2.5 border-t border-border/20 pt-2.5">
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
            className="flex items-center gap-1 text-[9px] text-muted-foreground hover:text-foreground transition-colors"
          >
            {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            {t(lang, "dash_smart_detail" as TranslationKey)}
          </button>
          {expanded && (
            <p className="text-[10px] text-foreground/60 leading-relaxed mt-1.5">{bodySnippet}</p>
          )}
        </div>
      )}

      {/* ── Footer ── */}
      <div className="px-3.5 py-2.5 border-t border-border/20 flex justify-end">
        <span className="text-[10px] text-primary font-medium flex items-center gap-0.5">
          {t(lang, "dash_chain_detail" as TranslationKey)}
          <ChevronRight className="h-3 w-3" />
        </span>
      </div>
    </section>
  );
}

/* ── Compact card for #2-#5 issues ── */

interface SmartSummaryCompactProps {
  item: TrendingItem;
  index: number;
  homeCountry: string;
  lang: "ko" | "en";
  topIssueRaw?: any;
  isLast?: boolean;
}

export function SmartSummaryCompact({ item, index, homeCountry, lang, topIssueRaw, isLast }: SmartSummaryCompactProps) {
  const router = useRouter();
  const topic = item.topic ?? "unknown";
  const clusterId = item.cluster_ids?.[0];
  const rawTitle = lang === "en" ? item.keyword : (item.keyword_ko ?? item.keyword);
  const topicKey = `topic_${topic}` as TranslationKey;
  const topicLabel = t(lang, topicKey) || topic;
  const displayTitle = isJunkTitle(rawTitle)
    ? buildSmartTitle(item.keyword, topic, lang, getCountryName, item.country_codes[0])
    : (stripTitlePrefix(rawTitle) || topicLabel);

  const impactScore = topIssueRaw?.impact_score ?? 0;
  const soWhatLine = topIssueRaw?.so_what_line;
  const colors = impactScoreColor(impactScore);

  return (
    <div
      onClick={clusterId ? () => router.push(issueDetailPath(clusterId)) : undefined}
      className={cn(
        "flex items-center gap-2 py-2.5 cursor-pointer hover:bg-muted/10 transition-all duration-200 rounded-lg px-1.5 -mx-1.5",
        !isLast && "border-b border-border/30",
      )}
    >
      {/* Ranking */}
      <span className="text-[10px] font-bold text-muted-foreground w-5 text-center shrink-0">#{index + 2}</span>

      {/* Flag */}
      {item.country_codes.length > 0 && (
        <span className="text-sm shrink-0">{getFlag(item.country_codes[0])}</span>
      )}

      {/* Title + description */}
      <div className="flex-1 min-w-0">
        <span className="text-[11px] font-semibold truncate block leading-tight">{displayTitle}</span>
        {soWhatLine && (
          <span className="text-[9px] text-foreground/50 truncate block mt-0.5 leading-tight">{soWhatLine}</span>
        )}
      </div>

      {/* Impact score mini bar */}
      <div className="shrink-0 flex items-center gap-1.5 w-[60px]">
        <div className="flex-1 h-1 bg-muted/30 rounded-full overflow-hidden">
          <div className={cn("h-full rounded-full", colors.bar)} style={{ width: `${Math.min(impactScore, 100)}%` }} />
        </div>
        <span className={cn("text-[10px] font-bold tabular-nums w-5 text-right", colors.text)}>{impactScore}</span>
      </div>

      <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
    </div>
  );
}
