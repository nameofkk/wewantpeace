"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Search, ArrowLeft, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { t } from "@/lib/i18n";
import { useAppStore } from "@/lib/store";
import { useSearchIssues, type SearchResult } from "@/lib/api";
import { useDebounce } from "@/lib/hooks/useDebounce";
import { issueDetailPath } from "@/lib/toss-nav";

function getSeverityColor(severity: number): string {
  if (severity >= 80) return "#991b1b";
  if (severity >= 60) return "#ef4444";
  if (severity >= 40) return "#f97316";
  if (severity >= 20) return "#f59e0b";
  return "#22c55e";
}

function getSeverityBg(severity: number): string {
  if (severity >= 80) return "bg-red-900/30 text-red-200";
  if (severity >= 60) return "bg-red-500/20 text-red-400";
  if (severity >= 40) return "bg-orange-500/20 text-orange-400";
  if (severity >= 20) return "bg-amber-500/20 text-amber-400";
  return "bg-green-500/20 text-green-400";
}

function getSeverityLabel(severity: number, lang: "ko" | "en"): string {
  if (severity >= 80) return lang === "ko" ? "위험" : "Critical";
  if (severity >= 60) return lang === "ko" ? "주의" : "Elevated";
  if (severity >= 40) return lang === "ko" ? "관심" : "Watch";
  if (severity >= 20) return lang === "ko" ? "양호" : "Fair";
  return lang === "ko" ? "안정" : "Clear";
}

function getWeatherEmoji(severity: number): string {
  if (severity >= 80) return "🌪️";
  if (severity >= 60) return "⛈️";
  if (severity >= 40) return "🌥️";
  if (severity >= 20) return "⛅";
  return "☀️";
}

const TOPIC_EMOJI: Record<string, string> = {
  conflict: "\u2694\uFE0F",
  terror: "\uD83D\uDCA3",
  sanctions: "\uD83D\uDEAB",
  diplomacy: "\uD83E\uDD1D",
  cyber: "\uD83D\uDDA5\uFE0F",
  protest: "\u270A",
  humanitarian: "\u2764\uFE0F",
  migration: "\uD83D\uDEB6",
};

export default function SearchPage() {
  const lang = useAppStore((s) => s.lang);
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);
  const { data: results, isLoading, isFetching } = useSearchIssues(debouncedQuery);

  const showResults = debouncedQuery.length >= 2;

  return (
    <div className="min-h-screen bg-background">
      {/* 헤더 */}
      <div className="sticky top-0 z-40 bg-background/95 backdrop-blur-sm border-b border-border">
        <div className="flex items-center gap-2 px-4 py-3">
          <Link href="/feed" className="p-1 -ml-1 rounded-lg hover:bg-muted transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t(lang, "search_placeholder")}
              autoFocus
              className={cn(
                "w-full pl-9 pr-4 py-2.5 rounded-xl text-sm",
                "bg-muted/50 border border-border/50",
                "focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50",
                "placeholder:text-muted-foreground/60",
                "transition-all",
              )}
            />
          </div>
        </div>
      </div>

      {/* 본문 */}
      <div className="px-4 py-3">
        {!showResults && (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <Search className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-sm">{t(lang, "search_min_chars")}</p>
          </div>
        )}

        {showResults && isLoading && (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-20 rounded-xl bg-muted/30 animate-pulse" />
            ))}
          </div>
        )}

        {showResults && !isLoading && results && results.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <AlertTriangle className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-sm">{t(lang, "search_no_results")}</p>
          </div>
        )}

        {showResults && results && results.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground mb-2">
              {results.length}{lang === "ko" ? "개 결과" : " results"}
              {isFetching && !isLoading && (
                <span className="ml-2 inline-block w-3 h-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
              )}
            </p>
            {results.map((item) => (
              <SearchResultCard key={item.id} item={item} lang={lang} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SearchResultCard({ item, lang }: { item: SearchResult; lang: "ko" | "en" }) {
  const title = lang === "ko" && item.title_ko ? item.title_ko : item.title;
  const emoji = TOPIC_EMOJI[item.topic] || "\uD83D\uDD34";
  const sevColor = getSeverityColor(item.severity);
  const sevBg = getSeverityBg(item.severity);
  const flag = item.country_code
    ? String.fromCodePoint(
        ...item.country_code
          .toUpperCase()
          .split("")
          .map((c) => 0x1f1e6 - 65 + c.charCodeAt(0)),
      )
    : null;

  const timeAgo = useMemo(() => {
    const d = new Date(item.last_event_at);
    const diff = Date.now() - d.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    if (hours < 1) return lang === "ko" ? "방금" : "Just now";
    if (hours < 24) return lang === "ko" ? `${hours}시간 전` : `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return lang === "ko" ? `${days}일 전` : `${days}d ago`;
  }, [item.last_event_at, lang]);

  return (
    <Link
      href={issueDetailPath(item.id)}
      className={cn(
        "block rounded-xl border border-border/50 p-3",
        "bg-card hover:bg-muted/50 transition-colors",
        "active:scale-[0.98] transition-transform",
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-sm">{getWeatherEmoji(item.severity)}</span>
            {flag && <span className="text-sm">{flag}</span>}
            <span className={cn("px-1.5 py-0.5 text-[10px] font-medium rounded-md", sevBg)}>
              {getSeverityLabel(item.severity, lang)}
            </span>
          </div>
          <p className="text-sm font-medium leading-snug line-clamp-2">{title}</p>
          <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground">
            <span>
              {item.event_count}{lang === "ko" ? "건 보도" : " reports"}
            </span>
            <span className="w-px h-3 bg-border" />
            <span>{timeAgo}</span>
          </div>
        </div>
        {item.image_url && (
          <img
            src={item.image_url}
            alt=""
            className="w-14 h-14 rounded-lg object-cover flex-shrink-0"
          />
        )}
      </div>
    </Link>
  );
}
