"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Globe, MapPin, AlertTriangle, RefreshCw, Pencil, ChevronRight, ChevronDown, ChevronUp, Lock } from "lucide-react";
import Link from "next/link";
import { COUNTRY_MAP, getFlag, getCountryName } from "@/lib/countries";
import { cn, TOPIC_LABELS } from "@/lib/utils";
import { useAppStore, FREE_COUNTRY_LIMIT } from "@/lib/store";
import { useGlobalTrending, useMineTrending, useMe, useKScoreHistory } from "@/lib/api";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { LogoIcon } from "@/components/ui/logo-icon";
import { t } from "@/lib/i18n";
import { KScoreHistoryChart } from "@/components/trending/KScoreHistoryChart";

const TOPIC_COLORS: Record<string, string> = {
  conflict:  "bg-red-500/20 text-red-400",
  terror:    "bg-red-700/20 text-red-600",
  coup:      "bg-purple-500/20 text-purple-400",
  sanctions: "bg-blue-500/20 text-blue-400",
  cyber:     "bg-cyan-500/20 text-cyan-400",
  protest:   "bg-orange-500/20 text-orange-400",
  diplomacy: "bg-green-500/20 text-green-400",
  maritime:  "bg-teal-500/20 text-teal-400",
  disaster:  "bg-sky-500/20 text-sky-400",
  health:    "bg-emerald-500/20 text-emerald-400",
  unknown:   "bg-muted text-muted-foreground",
};


// KScore에 따른 카드 좌측 강조선 색
function kscoreAccent(kscore?: number): string {
  if (!kscore) return "border-l-border";
  if (kscore >= 3.0) return "border-l-red-500";
  if (kscore >= 2.0) return "border-l-orange-500";
  if (kscore >= 1.0) return "border-l-yellow-500";
  return "border-l-green-600";
}

interface TrendingItem {
  id: number;
  keyword: string;
  keyword_ko?: string | null;
  kscore: number;
  topic: string | null;
  country_codes: string[];
  cluster_ids?: string[];
  is_spike?: boolean;
  event_count?: number;
  severity?: number;
  reason?: string;
  calculated_at?: string;
  first_event_at?: string | null;
  independent_sources?: number;
}

// NEW 태그 기준: 2시간 이내
function isNew(isoString?: string | null): boolean {
  if (!isoString) return false;
  return Date.now() - new Date(isoString).getTime() < 2 * 60 * 60 * 1000;
}

// 날짜+시분 포맷
import { type Lang } from "@/lib/i18n";

function formatFirstSeen(isoString?: string | null, lang: Lang = "ko"): string | null {
  if (!isoString) return null;
  const d = new Date(isoString);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const locale = lang === "en" ? "en-US" : "ko-KR";
  if (isToday) {
    const time = d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
    return lang === "en" ? `First reported at ${time}` : `${time} 최초 발생`;
  }
  const date = d.toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  return lang === "en" ? `First reported ${date}` : `${date} 최초 발생`;
}

// ── 실시간 경과 시간 훅 ───────────────────────────────────────────────────
function useElapsed(isoString?: string, lang: Lang = "ko") {
  const [elapsed, setElapsed] = useState(0);
  const ref = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isoString) return;
    const base = new Date(isoString).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - base) / 1000));
    tick();
    ref.current = setInterval(tick, 10000);
    return () => { if (ref.current) clearInterval(ref.current); };
  }, [isoString]);

  if (!isoString) return null;
  if (lang === "en") {
    if (elapsed < 60) return "just now";
    if (elapsed < 3600) return `${Math.floor(elapsed / 60)}m ago`;
    return `${Math.floor(elapsed / 3600)}h ago`;
  }
  if (elapsed < 60) return "방금 전";
  if (elapsed < 3600) return `${Math.floor(elapsed / 60)}분 전`;
  return `${Math.floor(elapsed / 3600)}시간 전`;
}

// ── 트렌딩 신호 (KScore 3요소 개별 바) ───────────────────────────────────
function TrendingSignals({ item, delay }: { item: TrendingItem; delay: number }) {
  const lang = useAppStore((s) => s.lang);
  const hasSpike = item.is_spike;
  const eventCount = item.event_count ?? 0;
  const spread = item.independent_sources ?? 1;
  const [filled, setFilled] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setFilled(true), delay + 250);
    return () => clearTimeout(timer);
  }, [delay]);

  const bars = [
    {
      label: t(lang, "signal_speed"),
      value: Math.min(1.0, (eventCount / 10) * (hasSpike ? 1.5 : 1.0)),
      display: hasSpike ? t(lang, "signal_count_spike", { n: eventCount }) : t(lang, "signal_count", { n: eventCount }),
      color: "bg-blue-500",
      tooltip: t(lang, "signal_speed_tooltip"),
    },
    {
      label: t(lang, "signal_severity"),
      value: (item.severity ?? 0) / 100,
      display: String(item.severity ?? 0),
      color:
        (item.severity ?? 0) >= 75 ? "bg-red-500" :
        (item.severity ?? 0) >= 50 ? "bg-orange-500" :
        (item.severity ?? 0) >= 25 ? "bg-yellow-500" :
        "bg-green-600",
      tooltip: t(lang, "signal_severity_tooltip"),
    },
    {
      label: t(lang, "signal_spread"),
      value: Math.min(1.0, spread / 5),
      display: t(lang, "signal_sources", { n: spread }),
      color: "bg-purple-500",
      tooltip: t(lang, "signal_spread_tooltip"),
    },
  ];

  return (
    <div className="mt-2.5">
      {/* 3개 지표 가로 배열 */}
      <div className="flex gap-2">
        {bars.map(({ label, value, display, color, tooltip }) => (
          <div key={label} className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-muted-foreground flex items-center gap-0.5 shrink-0">
                {label}
                <InfoTooltip direction="up" text={tooltip} />
              </span>
              <span className="text-[10px] text-muted-foreground/70 tabular-nums truncate ml-1">
                {display}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full ${color} rounded-full transition-all duration-700`}
                style={{ width: filled ? `${Math.round(value * 100)}%` : "0%" }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

type HistoryRange = "7d" | "30d" | "90d";
const PLAN_ORDER: Record<string, number> = { free: 0, pro: 1, pro_plus: 2 };

function KScoreHistorySection({
  clusterId,
  userPlan,
  lang,
}: {
  clusterId: string;
  userPlan: string;
  lang: "ko" | "en";
}) {
  const [range, setRange] = useState<HistoryRange>("7d");
  const userLevel = PLAN_ORDER[userPlan.toLowerCase()] ?? 0;
  const { data, isLoading } = useKScoreHistory(clusterId, range === "7d" ? 7 : range === "30d" ? 30 : 90);

  const rangeOptions: { value: HistoryRange; labelKo: string; labelEn: string; requiredPlan: string }[] = [
    { value: "7d",  labelKo: "7일",  labelEn: "7d",  requiredPlan: "free" },
    { value: "30d", labelKo: "30일", labelEn: "30d", requiredPlan: "pro" },
    { value: "90d", labelKo: "90일", labelEn: "90d", requiredPlan: "pro_plus" },
  ];

  return (
    <div className="mt-4 pt-4 border-t border-border">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-muted-foreground">
          KScore {lang === "ko" ? "히스토리" : "History"}
        </p>
        <div className="flex gap-1">
          {rangeOptions.map(({ value, labelKo, labelEn, requiredPlan }) => {
            const reqLevel = PLAN_ORDER[requiredPlan] ?? 0;
            const locked = userLevel < reqLevel;
            if (locked) {
              return (
                <span
                  key={value}
                  className="flex items-center gap-0.5 rounded px-2 py-0.5 text-[10px] text-muted-foreground/40 border border-border/40 cursor-not-allowed select-none"
                >
                  <Lock className="h-2.5 w-2.5" />
                  {lang === "ko" ? labelKo : labelEn}
                </span>
              );
            }
            return (
              <button
                key={value}
                onClick={(e) => { e.stopPropagation(); setRange(value); }}
                className={cn(
                  "rounded px-2 py-0.5 text-[10px] transition-colors",
                  range === value
                    ? "bg-primary text-primary-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground border border-border"
                )}
              >
                {lang === "ko" ? labelKo : labelEn}
              </button>
            );
          })}
        </div>
      </div>

      {/* 잠긴 범위 플랜 안내 */}
      {userLevel < (PLAN_ORDER["pro_plus"] ?? 2) && (
        <div
          className="mb-3 flex items-center justify-between rounded-lg px-3 py-2"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
        >
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
            <Lock className="h-3 w-3 shrink-0" />
            <span style={{ wordBreak: "keep-all" }}>
              {userLevel < (PLAN_ORDER["pro"] ?? 1)
                ? (lang === "ko" ? "30일 히스토리는 Pro · 90일은 Pro+ 플랜에서 이용 가능" : "30-day requires Pro · 90-day requires Pro+")
                : (lang === "ko" ? "90일 히스토리는 Pro+ 플랜에서 이용 가능" : "90-day history requires Pro+ plan")}
            </span>
          </div>
          <a
            href="/upgrade"
            className="ml-3 shrink-0 rounded-md px-2.5 py-1 text-[10px] font-bold text-white"
            style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
          >
            {lang === "ko" ? "구독" : "Upgrade"}
          </a>
        </div>
      )}

      {isLoading ? (
        <div className="h-36 flex items-center justify-center">
          <div className="h-4 w-32 rounded bg-secondary animate-pulse" />
        </div>
      ) : (
        <KScoreHistoryChart data={data ?? []} range={range} lang={lang} />
      )}
    </div>
  );
}

// ── 트렌딩 카드 ──────────────────────────────────────────────────────────
function TrendingCard({ item, rank, delay = 0, userPlan = "free" }: { item: TrendingItem; rank: number; delay?: number; userPlan?: string }) {
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const [showHistory, setShowHistory] = useState(false);
  const topic = item.topic ?? "unknown";
  const isCritical = item.kscore >= 3.0;
  const clusterId = item.cluster_ids?.[0];
  // 영어 모드: 원문 영어 키워드 / 한국어 모드: 번역된 한국어 우선
  const displayTitle = lang === "en" ? item.keyword : (item.keyword_ko ?? item.keyword);
  // 토픽 레이블
  const topicKey = `topic_${topic}` as Parameters<typeof t>[1];
  const topicLabel = t(lang, topicKey) || topic;

  return (
    <div
      className={cn(
        "card-enter rounded-xl border-l-4 border border-border bg-card p-4",
        "transition-all hover:bg-card/80",
        clusterId && "cursor-pointer",
        kscoreAccent(item.kscore),
        isCritical && "shadow-red-900/20 shadow-md"
      )}
      style={{ animationDelay: `${delay}ms` }}
      onClick={clusterId ? () => router.push(`/issues/${clusterId}`) : undefined}
    >
      <div className="flex items-start gap-3">
        {/* 순위 — 1위는 특별 강조 */}
        <div className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold",
          rank === 1 ? "bg-primary text-primary-foreground" : "bg-secondary"
        )}>
          {rank}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            {isNew(item.first_event_at) && (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-blue-500/20 px-1.5 py-0.5 text-[9px] font-bold text-blue-400 leading-none">
                NEW
                <InfoTooltip direction="down" text={t(lang, "signal_new_tooltip")} />
              </span>
            )}
            <span className={cn("inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[10px] font-medium", TOPIC_COLORS[topic])}>
              {topicLabel}
              <InfoTooltip direction="down" text={t(lang, (`topic_${topic}_tooltip`) as Parameters<typeof t>[1]) || topicLabel} />
            </span>
            {item.country_codes.length > 0 && (
              <span className="text-[11px] text-muted-foreground">
                {item.country_codes.map((code: string) => getFlag(code)).join(" ")}
              </span>
            )}
          </div>

          <h3 className="mt-1.5 text-sm font-semibold leading-snug">{displayTitle}</h3>

          {formatFirstSeen(item.first_event_at, lang) && (
            <p className="mt-0.5 text-[10px] text-muted-foreground/70">
              {formatFirstSeen(item.first_event_at, lang)}
            </p>
          )}

          {/* 트렌딩 이유 — 항상 표시 */}
          <TrendingSignals item={item} delay={delay} />
        </div>

        {/* KScore 뱃지 */}
        <div className="shrink-0 flex flex-col items-end gap-0.5">
          <span className={cn(
            "text-sm font-bold tabular-nums",
            item.kscore >= 3.0 ? "text-red-400" :
            item.kscore >= 2.0 ? "text-orange-400" :
            item.kscore >= 1.0 ? "text-yellow-400" :
            "text-muted-foreground"
          )}>
            {item.kscore.toFixed(2)}
          </span>
          <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
            KScore
            <InfoTooltip direction="down" text={t(lang, "signal_kscore_tooltip")} />
          </span>
        </div>
      </div>

      {clusterId && (
        <div className="flex items-center justify-end mt-2 gap-1 text-[10px] text-primary/70">
          <span>{t(lang, "home_view_detail")}</span>
          <ChevronRight className="h-3 w-3" />
        </div>
      )}

      {clusterId && (
        <button
          onClick={(e) => { e.stopPropagation(); setShowHistory((v) => !v); }}
          className="mt-3 w-full flex items-center justify-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors py-1"
        >
          {showHistory
            ? <><ChevronUp className="h-3 w-3" />{lang === "ko" ? "KScore 히스토리 접기" : "Hide KScore history"}</>
            : <><ChevronDown className="h-3 w-3" />{lang === "ko" ? "KScore 히스토리 보기" : "Show KScore history"}</>
          }
        </button>
      )}

      {showHistory && clusterId && (
        <KScoreHistorySection clusterId={clusterId} userPlan={userPlan} lang={lang} />
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="card-enter rounded-xl border-l-4 border-l-border border border-border bg-card p-4 animate-pulse"
          style={{ animationDelay: `${i * 80}ms` }}
        >
          <div className="flex items-start gap-3">
            <div className="h-8 w-8 rounded-lg bg-secondary" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-20 rounded bg-secondary" />
              <div className="h-4 w-3/4 rounded bg-secondary" />
              <div className="h-1 w-full rounded bg-secondary" />
            </div>
            <div className="h-8 w-6 rounded bg-secondary" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── 메인 ─────────────────────────────────────────────────────────────────
export default function HomePage() {
  const { trendingTab, setTrendingTab, myCountries, lang } = useAppStore();
  const { data: me } = useMe();
  const userPlan = (me as { plan?: string } | undefined)?.plan ?? "free";

  // Zustand persist 수화 완료 전까지 mine 쿼리 비활성화
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);

  const { data: globalData, isLoading: globalLoading, isFetching: globalFetching, isError: globalError, refetch: refetchGlobal } = useGlobalTrending();
  const { data: mineData, isLoading: mineLoading, isFetching: mineFetching, isError: mineError, refetch: refetchMine } = useMineTrending(
    hydrated ? myCountries : null
  );

  const [spinning, setSpinning] = useState(false);

  const items    = (trendingTab === "global" ? globalData : mineData) as TrendingItem[] | undefined;
  const isLoading = trendingTab === "global" ? globalLoading : mineLoading;
  const isFetching = trendingTab === "global" ? globalFetching : mineFetching;
  const isError  = trendingTab === "global" ? globalError  : mineError;
  const refetch  = trendingTab === "global" ? refetchGlobal : refetchMine;

  // 마지막 fetch 완료 시각 기준 경과 시간 (새로고침 버튼 클릭 시 갱신)
  const [lastFetchedAt, setLastFetchedAt] = useState(() => new Date().toISOString());
  useEffect(() => {
    if (items) setLastFetchedAt(new Date().toISOString());
  }, [items]);
  const elapsed = useElapsed(lastFetchedAt, lang);

  // 스파이크 카운트
  const spikeCount = (items ?? []).filter((i) => i.is_spike).length;

  const handleRefresh = useCallback(async () => {
    setSpinning(true);
    await refetch();
    setLastFetchedAt(new Date().toISOString());
    setSpinning(false);
  }, [refetch]);

  return (
    <div className="flex flex-col" style={{ height: "calc(100dvh - 60px)" }}>
      {/* ── 헤더 ─────────────────────────────────────────────────── */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm px-4 pt-4 pb-0">
        <div className="flex items-center justify-between gap-2 mb-3">
          {/* 왼쪽 */}
          <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
            <h1 className="text-base font-bold shrink-0">{t(lang, "home_title")}</h1>
            <span className="shrink-0 flex items-center gap-1 rounded-full bg-red-500/10 px-1.5 py-0.5 border border-red-500/20">
              <span className="live-dot h-1.5 w-1.5 rounded-full bg-red-500" />
              <span className="text-[10px] font-bold text-red-400">LIVE</span>
            </span>
            {spikeCount > 0 && (
              <span className="shrink-0 flex items-center gap-1 rounded-full bg-red-500/15 px-1.5 py-0.5 text-[10px] font-bold text-red-400">
                <AlertTriangle className="h-2.5 w-2.5" />
                {spikeCount}
              </span>
            )}
          </div>
          {/* 중앙 — 로고 */}
          <div className="shrink-0">
            <LogoIcon height={30} />
          </div>
          {/* 오른쪽 */}
          <div className="flex items-center justify-end gap-1.5 min-w-0">
            <button
              onClick={handleRefresh}
              className="shrink-0 text-muted-foreground hover:text-foreground disabled:opacity-50"
              disabled={spinning || isFetching}
            >
              <RefreshCw className={cn("h-3.5 w-3.5", (spinning || isFetching) && "animate-spin")} />
            </button>
            {elapsed && (
              <span className="text-[10px] text-muted-foreground truncate">{elapsed}</span>
            )}
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground mb-3 -mt-1">
          {t(lang, "home_subtitle")}
        </p>

        {/* 탭 */}
        <div className="flex gap-0">
          {(["global", "mine"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setTrendingTab(tab)}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 py-2.5 text-sm font-medium border-b-2 transition-colors",
                trendingTab === tab ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {tab === "global" ? (
                <><Globe className="h-3.5 w-3.5" />{t(lang, "home_tab_global")}</>
              ) : (
                <><MapPin className="h-3.5 w-3.5" />{t(lang, "home_tab_mine")}</>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── 내 관심지역 국가 표시 바 ──────────────────────────────── */}
      {trendingTab === "mine" && hydrated && myCountries.length > 0 && (
        <div className="border-b border-border/40 bg-secondary/20">
          <div className="flex items-center gap-2 px-4 py-2">
            <div className="flex flex-wrap gap-1.5 flex-1">
              {myCountries.map((code) => {
                const c = COUNTRY_MAP[code];
                return (
                  <span
                    key={code}
                    className="flex items-center gap-1 rounded-full bg-secondary px-2.5 py-0.5 text-[11px] font-medium"
                  >
                    <span>{c?.flag ?? "🌐"}</span>
                    <span>{getCountryName(code, lang)}</span>
                  </span>
                );
              })}
            </div>
            <Link
              href="/settings?section=countries"
              className="flex items-center gap-1 shrink-0 rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:border-primary transition-colors"
            >
              <Pencil className="h-2.5 w-2.5" />
              {t(lang, "home_change")}
            </Link>
          </div>
          {userPlan === "free" && myCountries.length >= FREE_COUNTRY_LIMIT && (
            <div className="flex items-center justify-between gap-2 px-4 pb-2">
              <p className="text-[10px] text-muted-foreground" style={{ wordBreak: "keep-all" }}>
                {lang === "ko"
                  ? `📍 Pro 10개 · Pro+ 무제한 — 더 많은 관심지역 추가 가능`
                  : `📍 Pro: 10 regions · Pro+: Unlimited`}
              </p>
              <a
                href="/upgrade"
                className="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold text-white"
                style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
              >
                {lang === "ko" ? "업그레이드" : "Upgrade"}
              </a>
            </div>
          )}
        </div>
      )}

      {/* ── 카드 목록 ─────────────────────────────────────────────── */}
        {/* 관심지역 탭인데 설정된 국가가 없을 때 — 중앙 정렬 */}
      {trendingTab === "mine" && hydrated && myCountries.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center px-4 text-center">
          <MapPin className="h-10 w-10 text-muted-foreground mb-3" />
          <p className="text-sm font-medium">{t(lang, "home_no_monitored")}</p>
          <p className="text-sm text-muted-foreground mb-4">{t(lang, "home_no_monitored_sub")}</p>
          <Link
            href="/settings?section=countries"
            className="flex items-center gap-1.5 rounded-full bg-primary px-4 py-2 text-xs font-bold text-primary-foreground"
          >
            <Pencil className="h-3.5 w-3.5" />
            {t(lang, "home_go_settings")}
          </Link>
          {userPlan === "free" && (
            <div className="mt-4 flex items-center justify-between gap-2 w-full max-w-xs rounded-lg px-3 py-2" style={{ background: "rgba(99,102,241,0.07)", border: "1px solid rgba(99,102,241,0.2)" }}>
              <p className="text-[11px] text-muted-foreground text-left" style={{ wordBreak: "keep-all" }}>
                {lang === "ko"
                  ? `📍 Pro 10개 · Pro+ 무제한 — 더 많은 관심지역 추가 가능`
                  : `📍 Pro: 10 regions · Pro+: Unlimited`}
              </p>
              <a
                href="/upgrade"
                className="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-bold text-white"
                style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
              >
                {lang === "ko" ? "업그레이드" : "Upgrade"}
              </a>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {!isLoading && !isError && items && items.length > 0 && (
              <p className="text-[11px] text-muted-foreground px-1">
                {trendingTab === "global"
                  ? t(lang, "home_global_count", { n: items.length })
                  : t(lang, "home_mine_count", { n: items.length })}
              </p>
            )}

            {isLoading && <LoadingSkeleton />}

            {isError && (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <AlertTriangle className="h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">{t(lang, "home_load_error")}</p>
                <button onClick={() => refetch()} className="mt-3 text-xs text-primary hover:underline">{t(lang, "home_retry")}</button>
              </div>
            )}

            {!isLoading && !isError && trendingTab === "mine" && myCountries.length > 0 && (!items || items.length === 0) && (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <MapPin className="h-10 w-10 text-muted-foreground mb-3" />
                <p className="text-sm font-medium">{t(lang, "home_no_trending")}</p>
                <p className="text-sm text-muted-foreground">{t(lang, "home_no_trending_sub")}</p>
              </div>
            )}

            {!isLoading && !isError && trendingTab === "global" && (!items || items.length === 0) && (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <MapPin className="h-10 w-10 text-muted-foreground mb-3" />
                <p className="text-sm font-medium">{t(lang, "home_no_trending")}</p>
                <p className="text-sm text-muted-foreground">{t(lang, "home_no_trending_sub")}</p>
              </div>
            )}

            {!isLoading && !isError && items && items.length > 0 &&
              items.map((item, i) => (
                <TrendingCard key={item.id} item={item} rank={i + 1} delay={i * 70} userPlan={userPlan} />
              ))
            }
          </div>
        )}
    </div>
  );
}
