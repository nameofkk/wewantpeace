"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { Activity, Globe, AlertTriangle, RefreshCw, ChevronDown, ChevronUp, Lock, Radio, Settings, MapPin, Pencil } from "lucide-react";
import Link from "next/link";
import { cn, TENSION_LEVELS, stripTitlePrefix } from "@/lib/utils";
import { useTensionMine, useTensionHistory, useMe } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { t, getTensionLevelLabel, type Lang } from "@/lib/i18n";
import { TensionHistoryChart } from "@/components/tension/TensionHistoryChart";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { LogoIcon } from "@/components/ui/logo-icon";
import { ALL_MONITORED_COUNTRIES, COUNTRY_MAP, getCountryName, getFlag } from "@/lib/countries";

interface ClusterSummary {
  id: string;
  title: string;
  title_ko?: string | null;
  severity: number;
  confidence: number;
  topic: string;
  kscore: number;
}

interface TensionData {
  country_code: string;
  raw_score: number;
  tension_level: 0 | 1 | 2 | 3 | 4;
  tension_label: string;
  percentile_30d: number;
  event_score: number;
  accel_score: number;
  spillover_score: number;
  updated_at: string;
  top5_clusters: ClusterSummary[];
}


type HistoryRange = "7d" | "30d" | "90d";

const RANGE_PLAN: Record<HistoryRange, string> = {
  "7d": "free",
  "30d": "pro",
  "90d": "pro_plus",
};

const PLAN_ORDER: Record<string, number> = { free: 0, pro: 1, "pro_plus": 2 };

// ── 실시간 경과 시간 훅 ──────────────────────────────────────────────────
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

// 게이지 호 색상: raw_score 절대값 기준 (5단계)
function scoreArcColor(score: number): string {
  if (score >= 80) return "#991b1b";  // 극심
  if (score >= 60) return "#ef4444";  // 심각
  if (score >= 40) return "#f97316";  // 경계
  if (score >= 20) return "#f59e0b";  // 주의
  return "#10b981";                   // 안정
}

function TensionGauge({ score, level, lang }: { score: number; level: 0 | 1 | 2 | 3 | 4; lang: Lang }) {
  const info = TENSION_LEVELS[level];
  const radius = 60;
  const circumference = Math.PI * radius;
  const targetOffset = circumference - (score / 100) * circumference;
  const arcColor = scoreArcColor(score);

  const [animOffset, setAnimOffset] = useState(circumference);
  useEffect(() => {
    const timer = setTimeout(() => setAnimOffset(targetOffset), 120);
    return () => clearTimeout(timer);
  }, [targetOffset]);

  const [displayScore, setDisplayScore] = useState(0);
  useEffect(() => {
    const end = Math.round(score);
    const duration = 900;
    let raf: number;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - (1 - p) ** 3;
      setDisplayScore(Math.round(eased * end));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    const timer = setTimeout(() => { raf = requestAnimationFrame(tick); }, 180);
    return () => { clearTimeout(timer); cancelAnimationFrame(raf); };
  }, [score]);

  return (
    <div className="relative flex items-center justify-center">
      <svg width="140" height="80" viewBox="0 0 140 80">
        <path
          d="M 10 70 A 60 60 0 0 1 130 70"
          fill="none"
          stroke="hsl(217 32% 17%)"
          strokeWidth="12"
          strokeLinecap="round"
        />
        <path
          d="M 10 70 A 60 60 0 0 1 130 70"
          fill="none"
          stroke={arcColor}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${circumference}`}
          strokeDashoffset={`${animOffset}`}
          style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94)" }}
        />
      </svg>
      <div className="absolute bottom-1 flex flex-col items-center">
        <span className="text-2xl font-bold tabular-nums" style={{ color: arcColor }}>
          {displayScore}
        </span>
        <span className="text-[9px] text-muted-foreground -mt-0.5">{t(lang, "tension_score_label")}</span>
        <span className="flex items-center gap-1 mt-0.5">
          <span className={cn("text-xs font-medium badge-pop", info.color)}>{getTensionLevelLabel(level, lang)}</span>
          <InfoTooltip
            direction="up"
            text={t(lang, "tension_gauge_tooltip")}
          />
        </span>
      </div>
    </div>
  );
}

function ScoreBreakdown({ event_score, accel_score, spillover_score, lang }: {
  event_score: number;
  accel_score: number;
  spillover_score: number;
  lang: Lang;
}) {
  const [filled, setFilled] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setFilled(true), 350);
    return () => clearTimeout(timer);
  }, []);

  const items = [
    {
      label: t(lang, "tension_breakdown_event"), value: event_score, weight: "55%", color: "bg-blue-500",
      tip: t(lang, "tension_breakdown_event_tip"),
    },
    {
      label: t(lang, "tension_breakdown_accel"), value: accel_score, weight: "35%", color: "bg-orange-500",
      tip: t(lang, "tension_breakdown_accel_tip"),
    },
    {
      label: t(lang, "tension_breakdown_spillover"), value: spillover_score, weight: "10%", color: "bg-purple-500",
      tip: t(lang, "tension_breakdown_spillover_tip"),
    },
  ];
  return (
    <div className="space-y-1.5">
      {items.map(({ label, value, weight, color, tip }) => (
        <div key={label} className="flex items-center gap-2">
          <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground w-12">
            {label}
            <InfoTooltip direction="up" text={tip} />
          </span>
          <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
            <div
              className={`h-full rounded-full ${color} transition-all duration-700`}
              style={{ width: filled ? `${Math.min(value, 100)}%` : '0%' }}
            />
          </div>
          <span className="text-[10px] text-muted-foreground w-8 text-right">{value.toFixed(0)}</span>
          <span className="text-[10px] text-muted-foreground w-6">{weight}</span>
        </div>
      ))}
    </div>
  );
}

function HistorySection({
  countryCode,
  userPlan,
  lang,
}: {
  countryCode: string;
  userPlan: string;
  lang: Lang;
}) {
  const [range, setRange] = useState<HistoryRange>("7d");
  const userLevel = PLAN_ORDER[userPlan.toLowerCase()] ?? 0;

  const { data, isPending } = useTensionHistory(countryCode, range);

  const rangeOptions: { value: HistoryRange; labelKey: "tension_history_7d" | "tension_history_30d" | "tension_history_90d"; requiredPlan: string }[] = [
    { value: "7d", labelKey: "tension_history_7d", requiredPlan: "free" },
    { value: "30d", labelKey: "tension_history_30d", requiredPlan: "pro" },
    { value: "90d", labelKey: "tension_history_90d", requiredPlan: "pro_plus" },
  ];

  return (
    <div className="mt-4 pt-4 border-t border-border">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-muted-foreground">{t(lang, "tension_history_section")}</p>
        <div className="flex gap-1">
          {rangeOptions.map(({ value, labelKey, requiredPlan }) => {
            const reqLevel = PLAN_ORDER[requiredPlan] ?? 0;
            const locked = userLevel < reqLevel;
            if (locked) {
              return (
                <span
                  key={value}
                  className="flex items-center gap-0.5 rounded px-2 py-0.5 text-[10px] text-muted-foreground/40 border border-border/40 cursor-not-allowed select-none"
                >
                  <Lock className="h-2.5 w-2.5" />
                  {t(lang, labelKey)}
                </span>
              );
            }
            return (
              <button
                key={value}
                onClick={() => setRange(value)}
                className={cn(
                  "rounded px-2 py-0.5 text-[10px] transition-colors",
                  range === value
                    ? "bg-primary text-primary-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground border border-border"
                )}
              >
                {t(lang, labelKey)}
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
            <span className="whitespace-nowrap">
              {userLevel < (PLAN_ORDER["pro"] ?? 1)
                ? (lang === "ko" ? "Pro 30일 · Pro+ 90일 히스토리" : "Pro: 30d · Pro+: 90d history")
                : (lang === "ko" ? "90일 히스토리는 Pro+ 전용" : "90d history — Pro+ only")}
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

      {isPending ? (
        <div className="h-48 flex items-center justify-center">
          <div className="h-4 w-32 rounded bg-secondary animate-pulse" />
        </div>
      ) : (
        <TensionHistoryChart
          data={data ?? []}
          countryCode={countryCode}
          range={range}
          lang={lang}
        />
      )}
    </div>
  );
}

// ── raw_score 절대값 기준 레벨 (배지·테두리·배경 전용, 5단계) ─────────────────
function scoreLevel(score: number): 0 | 1 | 2 | 3 | 4 {
  if (score >= 80) return 4;
  if (score >= 60) return 3;
  if (score >= 40) return 2;
  if (score >= 20) return 1;
  return 0;
}

// 30일 퍼센타일 → 번역 키 기반 텍스트
function pctRankLabel(pct: number, lang: Lang): { text: string; color: string } {
  if (pct >= 95) return { text: t(lang, "tension_rank_highest"), color: "text-red-400" };
  if (pct >= 75) return { text: t(lang, "tension_rank_top", { pct: Math.round(100 - pct) }), color: "text-amber-400" };
  if (pct >= 50) return { text: t(lang, "tension_rank_above"), color: "text-yellow-400" };
  if (pct >= 25) return { text: t(lang, "tension_rank_average"), color: "text-muted-foreground" };
  return               { text: t(lang, "tension_rank_below"),   color: "text-green-400" };
}

function scoreBorderStyle(score: number): string {
  if (score >= 80) return "border-red-800/70 shadow-red-950/50 shadow-lg";
  if (score >= 60) return "border-red-500/60 shadow-red-950/40 shadow-lg";
  if (score >= 40) return "border-orange-500/50 shadow-orange-950/20 shadow-md";
  if (score >= 20) return "border-amber-500/30";
  return "border-border";
}

function TensionCard({ data, userPlan, index, lang }: { data: TensionData; userPlan: string; index: number; lang: Lang }) {
  const [showHistory, setShowHistory] = useState(false);
  const [pctFilled, setPctFilled] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setPctFilled(true), 300 + index * 80);
    return () => clearTimeout(timer);
  }, [index]);

  const displayLevel = scoreLevel(data.raw_score);
  const info = TENSION_LEVELS[displayLevel];
  const label = getCountryName(data.country_code, lang);
  const isExtreme = displayLevel >= 4;
  const isCritical = displayLevel >= 3;
  const isSpike = data.percentile_30d >= 75 && displayLevel < 3;

  const locale = lang === "en" ? "en-US" : "ko-KR";
  const updatedTime = new Date(data.updated_at).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });

  return (
    <div
      className={cn(
        "relative card-enter rounded-xl border bg-card p-4 transition-all",
        scoreBorderStyle(data.raw_score),
        isExtreme && "alert-pulse-extreme",
        isCritical && !isExtreme && "alert-pulse-critical",
        displayLevel === 2 && "alert-pulse-warning",
      )}
      style={{ animationDelay: `${index * 100}ms` }}
    >
      {/* 경각심 컬러 오버레이 (5단계) */}
      {data.raw_score >= 60 && (
        <div className={cn(
          "absolute inset-0 rounded-xl pointer-events-none",
          data.raw_score >= 80 ? "bg-red-900/[0.12]" :
          "bg-red-500/[0.07]"
        )} />
      )}
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="flex items-center gap-1.5">
            <span className="text-base leading-none">{getFlag(data.country_code)}</span>
            <h3 className="text-sm font-bold">{label}</h3>
            {isCritical && (
              <span className="flex items-center gap-0.5 rounded-full bg-red-500/20 px-1.5 py-0.5 text-[9px] font-bold text-red-400 animate-pulse">
                <AlertTriangle className="h-2 w-2" /> {t(lang, "tension_crisis_badge")}
              </span>
            )}
            {isSpike && (
              <span className="flex items-center gap-0.5">
                <span className="spike-pulse rounded-full bg-amber-500/15 border border-amber-500/30 px-1.5 py-0.5 text-[9px] font-bold text-amber-400">
                  {t(lang, "tension_spike_label")}
                </span>
                <InfoTooltip
                  direction="up"
                  text={t(lang, "tension_spike_tooltip", { pct: Math.round(100 - data.percentile_30d) })}
                />
              </span>
            )}
          </div>
          <p className="text-[10px] text-muted-foreground">
            {t(lang, "tension_updated_at", { time: updatedTime })}
          </p>
        </div>
        <span className={cn(
          "rounded-full px-3 py-1 text-xs font-bold border badge-pop",
          info.bg, info.color, info.border,
          isExtreme && "shadow-red-950/70 shadow-lg",
          isCritical && !isExtreme && "shadow-red-900/60 shadow-md",
          displayLevel === 2 && "shadow-orange-900/40 shadow-sm",
        )}>
          {getTensionLevelLabel(displayLevel, lang)}
        </span>
      </div>

      <TensionGauge score={data.raw_score} level={displayLevel} lang={lang} />

      {/* 최근 30일 대비 */}
      {(() => {
        const pct = data.percentile_30d;
        const rank = pctRankLabel(pct, lang);
        return (
          <div className="mt-3">
            <div className="flex items-center justify-between text-[10px] mb-1">
              <span className="text-muted-foreground flex items-center gap-1">
                {t(lang, "tension_percentile_label")}
                <InfoTooltip
                  direction="up"
                  text={t(lang, "tension_percentile_tooltip")}
                />
              </span>
              <span className={cn("font-bold", rank.color)}>{rank.text}</span>
            </div>
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-700",
                  pct >= 80 ? "bg-red-900" :
                  pct >= 60 ? "bg-red-500" :
                  pct >= 40 ? "bg-orange-500" :
                  pct >= 20 ? "bg-amber-500" : "bg-emerald-500"
                )}
                style={{ width: pctFilled ? `${pct}%` : "0%" }}
              />
              <div className="absolute top-0 bottom-0 w-px bg-white/20" style={{ left: "50%" }} />
            </div>
            <div className="flex justify-between text-[9px] text-muted-foreground/50 mt-0.5 px-0.5">
              <span>{t(lang, "tension_percentile_low")}</span>
              <span>{t(lang, "tension_percentile_avg")}</span>
              <span>{t(lang, "tension_percentile_high")}</span>
            </div>
          </div>
        );
      })()}

      {/* 점수 구성 */}
      <div className="mt-3">
        <p className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground mb-2">
          {t(lang, "tension_breakdown_title")}
          <InfoTooltip
            direction="up"
            text={t(lang, "tension_breakdown_tooltip")}
          />
        </p>
        <ScoreBreakdown
          event_score={data.event_score}
          accel_score={data.accel_score}
          spillover_score={data.spillover_score}
          lang={lang}
        />
      </div>

      {/* 원인 이슈 */}
      {data.top5_clusters.length > 0 && (
        <div className={cn("mt-3 rounded-lg p-3", isCritical ? "bg-red-950/30 border border-red-900/30" : "bg-secondary/50")}>
          <p className="text-[10px] font-medium text-muted-foreground mb-2">
            {t(lang, "tension_cause_issues", { n: data.top5_clusters.length })}
          </p>
          <div className="space-y-1.5">
            {data.top5_clusters.map((c, i) => {
              const strippedTitle = stripTitlePrefix(lang === "en" ? c.title : (c.title_ko ?? c.title));
              const topicKey = `topic_${c.topic}` as Parameters<typeof t>[1];
              const clusterTitle = strippedTitle || t(lang, topicKey);
              return (
                <Link
                  key={c.id}
                  href={`/issues/${c.id}`}
                  className="flex items-center gap-2 hover:opacity-80 transition-opacity fade-in-up"
                  style={{ animationDelay: `${500 + i * 70}ms` }}
                >
                  <span className="text-[10px] text-muted-foreground w-4">{i + 1}.</span>
                  <span className="flex-1 text-[11px] truncate">{clusterTitle}</span>
                  <span className="text-[10px] text-muted-foreground">{t(lang, topicKey)}</span>
                  <span className={cn(
                    "text-[10px] font-bold tabular-nums",
                    (c.kscore ?? 0) >= 8 ? "text-red-100" : (c.kscore ?? 0) >= 6 ? "text-red-400" : (c.kscore ?? 0) >= 4 ? "text-orange-300" : (c.kscore ?? 0) >= 2 ? "text-amber-300" : "text-muted-foreground"
                  )}>K{(c.kscore ?? 0).toFixed(1)}</span>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* 히스토리 토글 */}
      <button
        onClick={() => setShowHistory((v) => !v)}
        className="mt-3 w-full flex items-center justify-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors py-1"
      >
        {showHistory ? (
          <><ChevronUp className="h-3 w-3" /> {t(lang, "tension_history_collapse")}</>
        ) : (
          <><ChevronDown className="h-3 w-3" /> {t(lang, "tension_history_expand")}</>
        )}
      </button>

      {showHistory && <HistorySection countryCode={data.country_code} userPlan={userPlan} lang={lang} />}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="card-enter rounded-xl border border-border bg-card p-4 animate-pulse"
          style={{ animationDelay: `${(i - 1) * 100}ms` }}
        >
          <div className="h-4 w-24 rounded bg-secondary mb-3" />
          <div className="h-20 w-full rounded bg-secondary mb-3" />
          <div className="h-2 w-full rounded bg-secondary" />
        </div>
      ))}
    </div>
  );
}

export default function TensionPage() {
  const { myCountries, lang } = useAppStore();

  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);

  const [viewMode, setViewMode] = useState<"mine" | "all">("all");

  const targetCountries = viewMode === "all"
    ? ALL_MONITORED_COUNTRIES
    : myCountries;

  const { data, isLoading, isFetching, isError, refetch } = useTensionMine(
    hydrated ? targetCountries : null
  );
  const { data: me } = useMe();
  const tensionsRaw = data as TensionData[] | undefined;
  const tensions = useMemo(
    () => tensionsRaw ? [...tensionsRaw].sort((a, b) => b.raw_score - a.raw_score) : undefined,
    [tensionsRaw]
  );
  const userPlan = (me as { plan?: string } | undefined)?.plan ?? "free";
  const [spinning, setSpinning] = useState(false);

  // hydrate 후 관심지역이 있으면 "mine" 탭으로 전환
  const [autoSwitched, setAutoSwitched] = useState(false);
  useEffect(() => {
    if (hydrated && myCountries.length > 0 && !autoSwitched) {
      setViewMode("mine");
      setAutoSwitched(true);
    }
  }, [hydrated, myCountries.length, autoSwitched]);

  // 관심지역 탭에서 데이터 없으면 전체 탭으로 fallback
  useEffect(() => {
    if (tensions && tensions.length === 0 && !isLoading && viewMode === "mine") {
      setViewMode("all");
    }
  }, [tensions, isLoading, viewMode]);

  // 빈 배열이면 10초 후 자동 refetch (서버 시작 직후 데이터 아직 준비 안 된 경우)
  useEffect(() => {
    if (tensions && tensions.length === 0 && !isLoading) {
      const timer = setTimeout(() => refetch(), 10_000);
      return () => clearTimeout(timer);
    }
  }, [tensions, isLoading, refetch]);

  const crisisCount = (tensions ?? []).filter((item) => item.raw_score >= 80).length;
  const severeCount = (tensions ?? []).filter((item) => item.raw_score >= 60).length;
  const warningCount = (tensions ?? []).filter((item) => item.raw_score >= 40).length;

  const [lastFetchedAt, setLastFetchedAt] = useState(() => new Date().toISOString());
  useEffect(() => {
    if (tensions) setLastFetchedAt(new Date().toISOString());
  }, [tensions]);
  const elapsed = useElapsed(lastFetchedAt, lang);

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
        <div className="grid grid-cols-3 items-center mb-3">
          {/* 왼쪽 */}
          <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
            <h1 className="text-sm font-bold truncate">{t(lang, "tension_title")}</h1>
            <span className="shrink-0 flex items-center gap-0.5 rounded-full bg-red-500/10 px-1.5 py-0.5 border border-red-500/20">
              <span className="live-dot h-1.5 w-1.5 rounded-full bg-red-500" />
              <span className="text-[9px] font-bold text-red-400">LIVE</span>
            </span>
          </div>
          {/* 중앙 — 로고 */}
          <div className="flex justify-center">
            <LogoIcon height={26} hideText />
          </div>
          {/* 오른쪽 */}
          <div className="flex items-center justify-end gap-1.5">
            {crisisCount > 0 && (
              <span className="flex items-center gap-0.5 rounded-full bg-red-500/15 px-1.5 py-0.5 text-[9px] font-bold text-red-400">
                <AlertTriangle className="h-2.5 w-2.5" />
                {crisisCount}
              </span>
            )}
            {crisisCount === 0 && severeCount > 0 && (
              <span className="flex items-center gap-0.5 rounded-full bg-red-500/15 px-1.5 py-0.5 text-[9px] font-bold text-red-400">
                <AlertTriangle className="h-2.5 w-2.5" />
                {severeCount}
              </span>
            )}
            {crisisCount === 0 && severeCount === 0 && warningCount > 0 && (
              <span className="flex items-center gap-0.5 rounded-full bg-orange-500/15 px-1.5 py-0.5 text-[9px] font-bold text-orange-400">
                <AlertTriangle className="h-2.5 w-2.5" />
                {warningCount}
              </span>
            )}
            <span className="text-[9px] text-muted-foreground whitespace-nowrap">{elapsed}</span>
            <button
              onClick={handleRefresh}
              className="text-muted-foreground hover:text-foreground disabled:opacity-50"
              disabled={spinning || isFetching}
            >
              <RefreshCw className={cn("h-3.5 w-3.5", (spinning || isFetching) && "animate-spin")} />
            </button>
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground mb-3 -mt-1">
          {t(lang, "tension_subtitle")}
        </p>

        {/* 글로벌 / 관심지역 토글 탭 (홈과 동일 구조) */}
        <div className="flex gap-0">
          {(["all", "mine"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 py-2.5 text-sm font-medium border-b-2 transition-colors",
                viewMode === mode
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {mode === "all" ? (
                <><Globe className="h-3.5 w-3.5" />{t(lang, "tension_tab_all")}</>
              ) : (
                <><MapPin className="h-3.5 w-3.5" />{t(lang, "tension_tab_mine")}</>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── 내 관심지역 국가 표시 바 (관심지역 탭) ─────────────────── */}
      {viewMode === "mine" && hydrated && myCountries.length > 0 && (
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
        </div>
      )}

      {/* ── Free 플랜 업그레이드 힌트 (관심지역 탭일 때) ──────────── */}
      {viewMode === "mine" && userPlan === "free" && (
        <div className="flex items-center justify-between gap-2 px-4 py-2 border-b border-border/40" style={{ background: "rgba(99,102,241,0.06)" }}>
          <p className="text-[10px] text-muted-foreground whitespace-nowrap">
            {lang === "ko"
              ? "📍 Pro 5개 · Pro+ 무제한"
              : "📍 Pro: 5 regions · Pro+: Unlimited"}
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

      {/* ── 카드 목록 ─────────────────────────────────────────────── */}
      {/* 관심지역 탭인데 미설정 — 중앙 정렬 */}
      {hydrated && viewMode === "mine" && myCountries.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center px-4 text-center">
          <Activity className="h-10 w-10 text-muted-foreground mb-3" />
          <p className="text-sm font-medium">{t(lang, "tension_no_monitored")}</p>
          <p className="text-sm text-muted-foreground mb-4">{t(lang, "tension_no_monitored_sub")}</p>
          <Link
            href="/settings?section=countries"
            className="flex items-center gap-1.5 rounded-full bg-primary px-4 py-2 text-xs font-bold text-primary-foreground"
          >
            <Settings className="h-3.5 w-3.5" />
            {t(lang, "tension_go_settings")}
          </Link>
          {userPlan === "free" && (
            <div className="mt-4 flex items-center justify-between gap-2 w-full max-w-xs rounded-lg px-3 py-2" style={{ background: "rgba(99,102,241,0.07)", border: "1px solid rgba(99,102,241,0.2)" }}>
              <p className="text-[11px] text-muted-foreground text-left whitespace-nowrap">
                {lang === "ko"
                  ? `📍 Pro 5개 · Pro+ 무제한`
                  : `📍 Pro: 5 regions · Pro+: Unlimited`}
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
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {(isLoading || (!isError && !tensions)) && <LoadingSkeleton />}

          {isError && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <AlertTriangle className="h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">{t(lang, "tension_load_error")}</p>
              <button onClick={() => refetch()} className="mt-3 text-xs text-primary hover:underline">
                {t(lang, "tension_retry")}
              </button>
              <button
                onClick={async () => {
                  try {
                    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                    await fetch(`${API}/tension/recalculate`, { method: "POST" });
                    setTimeout(() => refetch(), 1500);
                  } catch {}
                }}
                className="mt-2 text-xs text-muted-foreground hover:text-foreground"
              >
                {t(lang, "tension_recalc")}
              </button>
            </div>
          )}

          {!isLoading && !isError && tensions && tensions.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <Radio className="h-10 w-10 text-muted-foreground mb-3 animate-pulse" />
              <p className="text-sm font-medium">{t(lang, "tension_no_data_empty")}</p>
              <p className="text-sm text-muted-foreground mb-4">{t(lang, "tension_no_data_sub")}</p>
              <button
                onClick={async () => {
                  try {
                    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                    const res = await fetch(`${API}/tension/recalculate`, { method: "POST" });
                    if (res.ok) {
                      setTimeout(() => refetch(), 1000);
                    }
                  } catch {}
                }}
                className="flex items-center gap-1.5 rounded-full bg-primary px-4 py-2 text-xs font-bold text-primary-foreground"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                {t(lang, "tension_recalc")}
              </button>
            </div>
          )}

          {!isLoading && !isError && tensions && tensions.length > 0 && tensions.map((item, i) => (
            <TensionCard key={item.country_code} data={item} userPlan={userPlan} index={i} lang={lang} />
          ))}
        </div>
      )}
    </div>
  );
}
