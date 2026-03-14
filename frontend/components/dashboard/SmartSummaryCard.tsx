"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { getFlag, getCountryName } from "@/lib/countries";
import { t, type TranslationKey } from "@/lib/i18n";
import {
  TOPIC_COLORS,
  personalizedKScore,
  roundKScore,
  kscoreAccent,
  getKScoreBadge,
  type TrendingItem,
} from "@/lib/kscore-utils";
import { stripTitlePrefix, isJunkTitle, buildSmartTitle } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { MarketSnapshot } from "@/lib/api";

/* ── Full card for #1 issue ── */

interface SmartSummaryFullProps {
  item: TrendingItem;
  homeCountry: string;
  lang: "ko" | "en";
  market?: MarketSnapshot | null;
  topIssueRaw?: any;
  isPro: boolean;
}

function getRelevantMarketChips(cc: string, market: MarketSnapshot | null | undefined) {
  if (!market) return [];
  if (["IL", "IR", "IQ", "SA", "SY", "LB", "YE"].includes(cc))
    return market.commodities.filter((c) => ["WTI", "BRENT"].includes(c.symbol));
  if (["CN", "TW", "JP", "KP", "KR"].includes(cc))
    return market.indices.filter((i) => ["KOSPI", "NKY"].includes(i.symbol)).map((i) => ({
      symbol: i.symbol, name: i.name, price_usd: i.value, change_pct: i.change_pct,
    }));
  if (["UA", "RU", "DE", "FR", "GB"].includes(cc))
    return market.indices.filter((i) => ["DAX", "FTSE"].includes(i.symbol)).map((i) => ({
      symbol: i.symbol, name: i.name, price_usd: i.value, change_pct: i.change_pct,
    }));
  return market.commodities.slice(0, 1);
}

export function SmartSummaryCardFull({ item, homeCountry, lang, market, topIssueRaw, isPro }: SmartSummaryFullProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);

  const topic = item.topic ?? "unknown";
  const pKScore = personalizedKScore(item, homeCountry);
  const k = roundKScore(pKScore);
  const badge = getKScoreBadge(pKScore, lang);
  const clusterId = item.cluster_ids?.[0];
  const rawTitle = lang === "en" ? item.keyword : (item.keyword_ko ?? item.keyword);
  const topicKey = `topic_${topic}` as TranslationKey;
  const topicLabel = t(lang, topicKey) || topic;
  const displayTitle = isJunkTitle(rawTitle)
    ? buildSmartTitle(item.keyword, topic, lang, getCountryName, item.country_codes[0])
    : (stripTitlePrefix(rawTitle) || topicLabel);

  const cc = item.country_codes?.[0] ?? "";
  const marketChips = getRelevantMarketChips(cc, market);

  const whatLine = topIssueRaw?.what_line;
  const soWhatLine = topIssueRaw?.so_what_line;
  const whenLine = topIssueRaw?.when_line;
  const entityAnchor = topIssueRaw?.entity_anchor;
  const bodySnippet = topIssueRaw?.body_snippet;

  return (
    <section
      className="rounded-xl border border-border bg-card overflow-hidden cursor-pointer"
      onClick={clusterId ? () => router.push(`/issues/${clusterId}`) : undefined}
    >
      {/* Header */}
      <div className={cn("px-4 pt-3 pb-2 border-b border-border/30", kscoreAccent(pKScore))}>
        <div className="flex items-center gap-2 mb-1">
          <span className={cn(
            "inline-flex items-center h-4 rounded-full px-1.5 text-[9px] font-medium leading-none",
            TOPIC_COLORS[topic]
          )}>
            {topicLabel}
          </span>
          {item.country_codes.length > 0 && (
            <span className="text-sm">
              {item.country_codes.map((code: string) => getFlag(code)).join(" ")}
            </span>
          )}
          {item.is_spike && (
            <span className="text-[8px] px-1 py-0.5 rounded bg-red-500/10 text-red-400 font-medium">
              {t(lang, "dash_badge_spike" as TranslationKey)}
            </span>
          )}
          {(item.confidence ?? 0) >= 0.7 && (
            <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-medium">
              {t(lang, "dash_badge_verified" as TranslationKey)}
            </span>
          )}
          <div className="ml-auto shrink-0 text-right">
            <span className={cn("text-[9px]", badge.text)}>K </span>
            <span className={cn("text-lg font-bold tabular-nums leading-none", badge.text)}>
              {k.toFixed(1)}
            </span>
          </div>
        </div>
      </div>

      {/* Smart Summary 3 lines */}
      <div className="px-4 py-3 space-y-1.5">
        {whatLine && (
          <div className="flex items-start gap-2">
            <span className="text-[9px] font-bold text-red-400 shrink-0 mt-0.5 w-10">
              {t(lang, "dash_smart_what" as TranslationKey)}
            </span>
            <span className="text-[11px] text-foreground/80 leading-snug">{whatLine}</span>
          </div>
        )}
        {soWhatLine && (
          <div className="flex items-start gap-2">
            <span className="text-[9px] font-bold text-orange-400 shrink-0 mt-0.5 w-10">
              {t(lang, "dash_smart_so_what" as TranslationKey)}
            </span>
            <span className="text-[11px] text-foreground/80 leading-snug font-medium">{soWhatLine}</span>
          </div>
        )}
        {whenLine && (
          <div className="flex items-start gap-2">
            <span className="text-[9px] font-bold text-blue-400 shrink-0 mt-0.5 w-10">
              {t(lang, "dash_smart_when" as TranslationKey)}
            </span>
            <span className="text-[11px] text-foreground/60 leading-snug">{whenLine}</span>
          </div>
        )}
      </div>

      {/* Market chips + entity_anchor */}
      <div className="px-4 pb-2 space-y-1.5">
        {marketChips.length > 0 && (
          <div className="flex gap-1.5 overflow-x-auto scrollbar-hide">
            {marketChips.map((m) => (
              <span key={m.symbol} className="shrink-0 inline-flex items-center gap-1 rounded bg-muted/20 px-1.5 py-0.5 text-[9px]">
                <span className="font-medium">{m.name}</span>
                <span className="tabular-nums">${m.price_usd.toLocaleString()}</span>
                <span className={cn("font-medium tabular-nums", m.change_pct > 0 ? "text-red-500" : m.change_pct < 0 ? "text-blue-500" : "text-muted-foreground")}>
                  {m.change_pct > 0 ? "+" : ""}{m.change_pct.toFixed(1)}%
                </span>
              </span>
            ))}
          </div>
        )}
        {isPro && entityAnchor && (
          <p className="text-[9px] text-muted-foreground/60">{entityAnchor}</p>
        )}
      </div>

      {/* Body snippet (Pro, collapsible) */}
      {isPro && bodySnippet && (
        <div className="px-4 pb-3 border-t border-border/20 pt-2">
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

      {/* Footer */}
      <div className="px-4 pb-3 flex justify-end">
        <span className="text-[10px] text-primary font-medium flex items-center gap-1">
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
  const pKScore = personalizedKScore(item, homeCountry);
  const k = roundKScore(pKScore);
  const badge = getKScoreBadge(pKScore, lang);
  const clusterId = item.cluster_ids?.[0];
  const rawTitle = lang === "en" ? item.keyword : (item.keyword_ko ?? item.keyword);
  const topicKey = `topic_${topic}` as TranslationKey;
  const topicLabel = t(lang, topicKey) || topic;
  const displayTitle = isJunkTitle(rawTitle)
    ? buildSmartTitle(item.keyword, topic, lang, getCountryName, item.country_codes[0])
    : (stripTitlePrefix(rawTitle) || topicLabel);

  const soWhatLine = topIssueRaw?.so_what_line;

  return (
    <div
      onClick={clusterId ? () => router.push(`/issues/${clusterId}`) : undefined}
      className={cn(
        "flex items-center gap-2 py-2.5 cursor-pointer hover:bg-muted/10 transition-all duration-200 rounded-lg px-1 -mx-1",
        !isLast && "border-b border-border/30",
      )}
    >
      <span className="text-[10px] font-bold text-muted-foreground w-5 text-center">#{index + 2}</span>
      {item.country_codes.length > 0 && (
        <span className="text-[11px]">
          {item.country_codes.map((code: string) => getFlag(code)).join("")}
        </span>
      )}
      <div className="flex-1 min-w-0">
        <span className="text-[11px] font-medium truncate block">{displayTitle}</span>
        {soWhatLine && (
          <span className="text-[9px] text-foreground/50 truncate block mt-0.5">{soWhatLine}</span>
        )}
      </div>
      <div className="shrink-0 flex items-center gap-0.5">
        <span className="text-[8px] text-muted-foreground">K</span>
        <span className={cn("text-sm font-bold tabular-nums", badge.text)}>
          {k.toFixed(1)}
        </span>
      </div>
      <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
    </div>
  );
}
