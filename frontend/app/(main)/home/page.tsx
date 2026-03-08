"use client";

import React, { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Globe, MapPin, AlertTriangle, RefreshCw, Pencil, ChevronRight, ChevronDown, ChevronUp, Lock, Check, X, Loader2, Bell, BarChart3 } from "lucide-react";
import Link from "next/link";
import { COUNTRY_MAP, getFlag, getCountryName } from "@/lib/countries";
import { cn, TOPIC_LABELS, stripTitlePrefix, isJunkTitle, buildSmartTitle } from "@/lib/utils";
import { useAppStore, FREE_COUNTRY_LIMIT } from "@/lib/store";
import { calcImpactFactor } from "@/lib/impact-factors";
import { useGlobalTrending, useMineTrending, useMe, useKScoreHistory, usePatchCluster, useClusters, useMissedSpikes, useTensionAll } from "@/lib/api";
import { PaywallModal, usePaywall } from "@/components/ui/PaywallModal";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { LogoIcon } from "@/components/ui/logo-icon";
import { t } from "@/lib/i18n";
import { KScoreHistoryChart } from "@/components/trending/KScoreHistoryChart";
import { ShareButton } from "@/components/issue/ShareButton";
import WelcomeModal from "@/components/ui/WelcomeModal";

const TOPIC_COLORS: Record<string, string> = {
  conflict:  "bg-red-500/20 text-red-600 dark:text-red-400",
  terror:    "bg-red-700/20 text-red-700 dark:text-red-600",
  coup:      "bg-purple-500/20 text-purple-600 dark:text-purple-400",
  sanctions: "bg-blue-500/20 text-blue-600 dark:text-blue-400",
  cyber:     "bg-cyan-500/20 text-cyan-600 dark:text-cyan-400",
  protest:   "bg-orange-500/20 text-orange-600 dark:text-orange-400",
  diplomacy: "bg-green-500/20 text-green-600 dark:text-green-400",
  maritime:  "bg-teal-500/20 text-teal-600 dark:text-teal-400",
  disaster:  "bg-sky-500/20 text-sky-600 dark:text-sky-400",
  health:    "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400",
  unknown:   "bg-muted text-muted-foreground",
};


// KScore 반올림: 표시값과 색상 판별에 동일한 값 사용
function roundKScore(kscore: number): number {
  return Math.round(kscore * 100) / 100;
}

// 개인화 KScore: kscore(decay 포함) × impact_factor
function personalizedKScore(item: TrendingItem, homeCountry: string): number {
  const country = item.country_codes?.[0] || "";
  const factor = calcImpactFactor(country, item.topic || "unknown", homeCountry);
  return Math.round(item.kscore * factor * 100) / 100;
}

// KScore에 따른 카드 좌측 강조선 색 (0-10 스케일, 5단계)
function kscoreAccent(kscore?: number): string {
  if (!kscore) return "border-l-border";
  const k = roundKScore(kscore);
  if (k >= 8) return "border-l-red-900";
  if (k >= 6) return "border-l-red-500";
  if (k >= 4) return "border-l-orange-500";
  if (k >= 2) return "border-l-amber-500";
  return "border-l-emerald-500";
}

// KScore 상태 뱃지 — 색상 + 라벨 (0-10 스케일, 5단계)
function getKScoreBadge(kscore: number, lang: "ko" | "en"): { label: string; bg: string; text: string; glow: string } {
  const k = roundKScore(kscore);
  if (k >= 8) return {
    label: lang === "ko" ? "극심" : "Extreme",
    bg: "bg-red-900/20", text: "text-red-700 dark:text-red-300",
    glow: "shadow-red-900/30 shadow-lg",
  };
  if (k >= 6) return {
    label: lang === "ko" ? "심각" : "Severe",
    bg: "bg-red-500/15", text: "text-red-600 dark:text-red-400",
    glow: "shadow-red-500/20 shadow-lg",
  };
  if (k >= 4) return {
    label: lang === "ko" ? "경계" : "Alert",
    bg: "bg-orange-500/15", text: "text-orange-600 dark:text-orange-300",
    glow: "shadow-orange-500/15 shadow-md",
  };
  if (k >= 2) return {
    label: lang === "ko" ? "주의" : "Caution",
    bg: "bg-amber-500/10", text: "text-amber-600 dark:text-amber-300",
    glow: "",
  };
  return {
    label: lang === "ko" ? "안정" : "Stable",
    bg: "bg-emerald-500/10", text: "text-emerald-600 dark:text-emerald-400",
    glow: "",
  };
}

interface TrendingItem {
  id: number;
  keyword: string;
  keyword_ko?: string | null;
  kscore: number;
  raw_score?: number;
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

// RISING 태그 기준: 6시간 이내 + raw KScore >= 3 (personalizedKScore 아님)
function isRising(firstEventAt?: string | null, kscore?: number): boolean {
  if (!firstEventAt || !kscore) return false;
  const ageMs = Date.now() - new Date(firstEventAt).getTime();
  return ageMs < 6 * 60 * 60 * 1000 && kscore >= 3;
}

// UPDATED 태그 기준: 생성은 2시간 이전이지만, 최근 2시간 내 이벤트 편입
function isUpdated(firstEventAt?: string | null, calculatedAt?: string): boolean {
  if (!firstEventAt || !calculatedAt) return false;
  const now = Date.now();
  const firstAge = now - new Date(firstEventAt).getTime();
  const lastAge = now - new Date(calculatedAt).getTime();
  return firstAge > 2 * 60 * 60 * 1000 && lastAge < 2 * 60 * 60 * 1000;
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
        (item.severity ?? 0) >= 80 ? "bg-red-900" :
        (item.severity ?? 0) >= 60 ? "bg-red-500" :
        (item.severity ?? 0) >= 40 ? "bg-orange-500" :
        (item.severity ?? 0) >= 20 ? "bg-amber-500" :
        "bg-emerald-500",
      tooltip: t(lang, "signal_severity_tooltip"),
    },
    {
      label: t(lang, "signal_spread"),
      value: Math.min(1.0, spread / 8),
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
          className="mb-3 flex items-center justify-between rounded-lg px-3 py-2 bg-black/[0.04] dark:bg-white/[0.04] border border-black/[0.08] dark:border-white/[0.08]"
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
const TrendingCard = React.memo(function TrendingCard({ item, rank, delay = 0, userPlan = "free", isAdmin = false }: { item: TrendingItem; rank: number; delay?: number; userPlan?: string; isAdmin?: boolean }) {
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const homeCountry = useAppStore((s) => s.homeCountry);
  const [showHistory, setShowHistory] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const patchCluster = usePatchCluster();
  const topic = item.topic ?? "unknown";
  const pKScore = personalizedKScore(item, homeCountry);
  const k = roundKScore(pKScore);
  const isExtreme = k >= 8;
  const isSevere = k >= 6;
  const isAlert = k >= 4;
  const badge = getKScoreBadge(pKScore, lang);
  const clusterId = item.cluster_ids?.[0];
  // 영어 모드: 원문 영어 키워드 / 한국어 모드: 번역된 한국어 우선
  const rawTitle = lang === "en" ? item.keyword : (item.keyword_ko ?? item.keyword);
  const topicKey = `topic_${topic}` as Parameters<typeof t>[1];
  const topicLabel = t(lang, topicKey) || topic;
  // 쓰레기 제목(해시태그만): 국가명+토픽 조합 / 정상 제목: 접두어 제거
  const displayTitle = isJunkTitle(rawTitle)
    ? buildSmartTitle(item.keyword, topic, lang, getCountryName, item.country_codes[0])
    : (stripTitlePrefix(rawTitle) || topicLabel);

  const handleEditStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditValue(item.keyword_ko ?? item.keyword ?? "");
    setEditing(true);
  };

  const handleEditSave = async (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation();
    if (!clusterId || !editValue.trim()) return;
    try {
      await patchCluster.mutateAsync({ id: clusterId, body: { title_ko: editValue.trim() } });
      setEditing(false);
    } catch {
      // 실패 시 편집 모드 유지
    }
  };

  const handleEditCancel = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation();
    setEditing(false);
  };

  return (
    <div
      className={cn(
        "card-enter rounded-xl border-l-4 border border-border bg-card p-4 relative",
        "transition-all hover:bg-card/80",
        clusterId && !editing && "cursor-pointer",
        kscoreAccent(pKScore),
        badge.glow,
        isExtreme && "card-pulse-extreme",
        isSevere && !isExtreme && "card-pulse-severe",
        isAlert && !isSevere && "card-pulse-alert",
      )}
      style={{ animationDelay: `${delay}ms` }}
      onClick={clusterId && !editing ? () => router.push(`/issues/${clusterId}`) : undefined}
    >
      {/* 배경 글로우 (경계 이상) */}
      {isAlert && (
        <div
          className="absolute inset-0 rounded-xl pointer-events-none"
          style={{
            background: isExtreme
              ? "linear-gradient(135deg, rgba(153,27,27,0.12) 0%, transparent 50%)"
              : isSevere
              ? "linear-gradient(135deg, rgba(239,68,68,0.08) 0%, transparent 60%)"
              : "linear-gradient(135deg, rgba(249,115,22,0.05) 0%, transparent 60%)",
          }}
        />
      )}

      <div className="flex items-start gap-3 relative">
        {/* 순위 — 1위는 특별 강조 */}
        <div className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold",
          rank === 1 ? "bg-primary text-primary-foreground" : "bg-secondary"
        )}>
          {rank}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            {/* KScore 상태 뱃지 */}
            <span className={cn(
              "inline-flex items-center h-5 rounded-full px-2 text-[10px] font-bold leading-none",
              badge.bg, badge.text,
              isSevere && "animate-pulse",
            )}>
              {badge.label}
            </span>
            {isNew(item.first_event_at) && (
              <span className="inline-flex items-center h-5 gap-0.5 rounded-full bg-blue-500/20 px-1.5 text-[9px] font-bold text-blue-400 leading-none">
                NEW
                <InfoTooltip direction="down" text={t(lang, "signal_new_tooltip")} />
              </span>
            )}
            {isRising(item.first_event_at, item.kscore) && !isNew(item.first_event_at) && (
              <span className="inline-flex items-center h-5 gap-0.5 rounded-full bg-emerald-500/20 px-1.5 text-[9px] font-bold text-emerald-500 leading-none animate-pulse">
                RISING
                <InfoTooltip direction="down" text={t(lang, "signal_rising_tooltip")} />
              </span>
            )}
            {isUpdated(item.first_event_at, item.calculated_at) && !isNew(item.first_event_at) && !isRising(item.first_event_at, item.kscore) && (
              <span className="inline-flex items-center h-5 gap-0.5 rounded-full bg-amber-500/20 px-1.5 text-[9px] font-bold text-amber-400 leading-none">
                UPDATED
                <InfoTooltip direction="down" text={t(lang, "signal_updated_tooltip")} />
              </span>
            )}
            <span className={cn("inline-flex items-center h-5 gap-0.5 rounded-full px-2 text-[10px] font-medium leading-none", TOPIC_COLORS[topic])}>
              {topicLabel}
              <InfoTooltip direction="down" text={t(lang, (`topic_${topic}_tooltip`) as Parameters<typeof t>[1]) || topicLabel} />
            </span>
            {item.country_codes.length > 0 && (
              <span className="text-[11px] text-muted-foreground">
                {item.country_codes.map((code: string) => getFlag(code)).join(" ")}
              </span>
            )}
          </div>

          {editing ? (
            <div className="mt-1.5 flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
              <input
                autoFocus
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleEditSave(e);
                  if (e.key === "Escape") handleEditCancel(e);
                }}
                className="flex-1 min-w-0 rounded-md border border-border bg-background px-2 py-1 text-sm font-semibold leading-snug outline-none focus:border-primary"
                placeholder={lang === "ko" ? "한국어 제목 입력" : "Enter Korean title"}
              />
              <button
                onClick={handleEditSave}
                disabled={patchCluster.isPending}
                className="shrink-0 rounded-md p-1 text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                onClick={handleEditCancel}
                className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-secondary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="mt-1.5 flex items-center gap-1">
              <h3 className="text-sm font-semibold leading-snug">{displayTitle}</h3>
              {isAdmin && clusterId && (
                <button
                  onClick={handleEditStart}
                  className="shrink-0 rounded p-0.5 text-muted-foreground/50 hover:text-primary hover:bg-primary/10 transition-colors"
                  title={t(lang, "admin_edit_title")}
                >
                  <Pencil className="h-3 w-3" />
                </button>
              )}
            </div>
          )}

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
            "text-lg font-bold tabular-nums",
            badge.text,
          )}>
            {k.toFixed(1)}
          </span>
          <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
            KScore
            <InfoTooltip direction="down" text={t(lang, "signal_kscore_tooltip")} />
          </span>
        </div>
      </div>

      {clusterId && (
        <div className="flex items-center justify-end mt-2 gap-1 text-[10px] text-primary/70 relative">
          <span>{t(lang, "home_view_detail")}</span>
          <ChevronRight className="h-3 w-3" />
        </div>
      )}

      {clusterId && (
        <div className="mt-3 flex items-center justify-between relative" onClick={(e) => e.stopPropagation()}>
          <ShareButton
            issueId={clusterId}
            title={displayTitle}
            analyticsEvent="cluster_card_share"
          />
          <button
            onClick={() => setShowHistory((v) => !v)}
            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors py-1"
          >
            {showHistory
              ? <><ChevronUp className="h-3 w-3" />{lang === "ko" ? "KScore 히스토리 접기" : "Hide KScore history"}</>
              : <><ChevronDown className="h-3 w-3" />{lang === "ko" ? "KScore 히스토리 보기" : "Show KScore history"}</>
            }
          </button>
        </div>
      )}

      {showHistory && clusterId && (
        <div onClick={(e) => e.stopPropagation()} className="relative">
          <KScoreHistorySection clusterId={clusterId} userPlan={userPlan} lang={lang} />
        </div>
      )}
    </div>
  );
});

// ── 브리핑 카드 ──────────────────────────────────────────────────────────
function BriefingCard({ items, lang }: { items: TrendingItem[]; lang: Lang }) {
  const homeCountry = useAppStore((s) => s.homeCountry);
  const extremeCount = items.filter((i) => roundKScore(personalizedKScore(i, homeCountry)) >= 8).length;
  const severeCount = items.filter((i) => { const k = roundKScore(personalizedKScore(i, homeCountry)); return k >= 6 && k < 8; }).length;
  const spikeCount = items.filter((i) => i.is_spike).length;
  const topItem = items[0];

  if (!topItem) return null;

  const topTitle = (() => {
    const raw = lang === "en" ? topItem.keyword : (topItem.keyword_ko ?? topItem.keyword);
    return isJunkTitle(raw)
      ? buildSmartTitle(topItem.keyword, topItem.topic ?? "unknown", lang, getCountryName, topItem.country_codes?.[0])
      : (stripTitlePrefix(raw) || topItem.keyword);
  })();

  const briefing = lang === "ko"
    ? extremeCount > 0
      ? `극심 ${extremeCount}건 발생 중 — 1위: ${topTitle}`
      : severeCount > 0
      ? `심각 ${severeCount}건 · 스파이크 ${spikeCount}건 — 주목: ${topTitle}`
      : spikeCount > 0
      ? `스파이크 ${spikeCount}건 감지됨 — 주목: ${topTitle}`
      : `현재 ${items.length}건 모니터링 중 — 1위: ${topTitle}`
    : extremeCount > 0
      ? `${extremeCount} extreme issue(s) — #1: ${topTitle}`
      : severeCount > 0
      ? `${severeCount} severe · ${spikeCount} spike(s) — Top: ${topTitle}`
      : spikeCount > 0
      ? `${spikeCount} spike(s) detected — Top: ${topTitle}`
      : `Monitoring ${items.length} issues — #1: ${topTitle}`;

  const accentColor = extremeCount > 0 ? "border-l-red-900" : severeCount > 0 ? "border-l-red-500" : spikeCount > 0 ? "border-l-amber-500" : "border-l-blue-500";

  return (
    <div className={cn("rounded-lg border-l-4 border border-border bg-card/50 px-3 py-2.5 mb-3", accentColor)}>
      <div className="flex items-center gap-1.5 mb-1">
        <BarChart3 className="h-3 w-3 text-muted-foreground shrink-0" />
        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
          {lang === "ko" ? "오늘의 브리핑" : "Today's Briefing"}
        </span>
      </div>
      <p className="text-[11px] leading-relaxed line-clamp-2" style={{ wordBreak: "keep-all" }}>
        {briefing}
      </p>
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
  const router = useRouter();
  const { trendingTab, setTrendingTab, myCountries, lang, setUserPlan, userPlan: storePlan, homeCountry } = useAppStore();
  const { data: me } = useMe();
  const meObj = me as { plan?: string; role?: string } | undefined;
  const userPlan = meObj?.plan ?? "free";
  const isAdmin = meObj?.role === "admin";

  // 서버 plan → store 동기화
  useEffect(() => {
    if (userPlan && userPlan !== storePlan) {
      setUserPlan(userPlan as "free" | "pro" | "pro_plus");
    }
  }, [userPlan, storePlan, setUserPlan]);

  // Sprint 3: 놓친 스파이크 배너
  const { data: missedSpikes } = useMissedSpikes();
  const missedCount = Array.isArray(missedSpikes) ? missedSpikes.length : 0;
  const paywall = usePaywall("map_locked");

  // Zustand persist 수화 완료 전까지 mine 쿼리 비활성화
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);

  // 글로벌: /issues API로 전체 활성 클러스터 조회 → TrendingItem 변환
  const { data: clusterData, isLoading: clusterLoading, isFetching: clusterFetching, isError: clusterError, refetch: refetchClusters } = useClusters({ limit: "2000" });
  const globalData = React.useMemo(() => {
    if (!clusterData || !Array.isArray(clusterData)) return undefined;
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
        is_spike: c.is_spike,
        event_count: c.event_count,
        severity: c.severity,
        reason: "",
        calculated_at: c.last_event_at,
        first_event_at: c.first_event_at,
        independent_sources: c.independent_sources ?? 1,
      }))
      .sort((a, b) => {
        const aK = personalizedKScore(a, homeCountry);
        const bK = personalizedKScore(b, homeCountry);
        const kDiff = bK - aK;
        // KScore 차이가 0.5 미만이면 최근 업데이트된 클러스터 우선
        if (Math.abs(kDiff) < 0.5) {
          const aTime = a.calculated_at ? new Date(a.calculated_at).getTime() : 0;
          const bTime = b.calculated_at ? new Date(b.calculated_at).getTime() : 0;
          if (bTime !== aTime) return bTime - aTime;
        }
        return kDiff || (b.severity ?? 0) - (a.severity ?? 0);
      }) as TrendingItem[];
  }, [clusterData, homeCountry]);
  // 급상승 데이터: 6시간 이내 생성 + raw KScore >= 3 (글로벌 탭 전용)
  // raw 기준으로 필터 후 personalizedKScore로 정렬 — 모든 홈 국가에서 Rising 표시 보장
  const risingData = useMemo(() => {
    if (!globalData) return [];
    const sixHoursAgo = Date.now() - 6 * 60 * 60 * 1000;
    return globalData
      .filter(item => item.first_event_at &&
        new Date(item.first_event_at).getTime() > sixHoursAgo &&
        (item.kscore ?? 0) >= 3)
      .sort((a, b) => personalizedKScore(b, homeCountry) - personalizedKScore(a, homeCountry))
      .slice(0, 5);
  }, [globalData, homeCountry]);

  const globalLoading = clusterLoading;
  const globalFetching = clusterFetching;
  const globalError = clusterError;
  const refetchGlobal = refetchClusters;

  const { data: mineData, isLoading: mineLoading, isFetching: mineFetching, isError: mineError, refetch: refetchMine } = useMineTrending(
    hydrated ? myCountries : null
  );

  const [spinning, setSpinning] = useState(false);
  const [visibleCount, setVisibleCount] = useState(30);
  const [loadingMore, setLoadingMore] = useState(false);

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

  // 레벨별 카운트 (개인화 KScore 기준)
  const extremeCount = (items ?? []).filter((i) => roundKScore(personalizedKScore(i, homeCountry)) >= 8).length;
  const crisisCount = (items ?? []).filter((i) => { const k = roundKScore(personalizedKScore(i, homeCountry)); return k >= 6 && k < 8; }).length;

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
            <h1 className="text-sm font-bold truncate">{t(lang, "home_title")}</h1>
            <span className="shrink-0 flex items-center gap-0.5 rounded-full bg-red-500/10 px-1.5 py-0.5 border border-red-500/20">
              <span className="live-dot h-1.5 w-1.5 rounded-full bg-red-500" />
              <span className="text-[9px] font-bold text-red-600 dark:text-red-400">LIVE</span>
            </span>
          </div>
          {/* 중앙 — 로고 (항상 정중앙) */}
          <div className="flex justify-center">
            <LogoIcon height={26} hideText />
          </div>
          {/* 오른쪽 */}
          <div className="flex items-center justify-end gap-1.5">
            {extremeCount > 0 && (
              <span className="inline-flex items-center gap-0.5 h-5 rounded-full bg-red-900/25 px-1.5 text-[9px] font-bold text-red-700 dark:text-red-300 border border-red-800/40">
                <AlertTriangle className="h-2.5 w-2.5" />
                {extremeCount}
              </span>
            )}
            {crisisCount > 0 && (
              <span className="inline-flex items-center gap-0.5 h-5 rounded-full bg-red-500/15 px-1.5 text-[9px] font-bold text-red-600 dark:text-red-400 border border-red-500/30">
                <AlertTriangle className="h-2.5 w-2.5" />
                {crisisCount}
              </span>
            )}
            {(extremeCount > 0 || crisisCount > 0) && (
              <InfoTooltip
                direction="down"
                text={lang === "ko"
                  ? `🔴 극심 ${extremeCount}건 (KScore 8+)\n🟠 심각 ${crisisCount}건 (KScore 6~8)`
                  : `🔴 ${extremeCount} Extreme (KScore 8+)\n🟠 ${crisisCount} Severe (KScore 6-8)`}
              />
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
          {t(lang, "home_subtitle")}
        </p>

        {/* 탭 */}
        <div className="flex gap-0">
          {(["global", "mine"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => { setTrendingTab(tab); setVisibleCount(30); }}
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

      {/* ── Sprint 3: 놓친 알림 배너 (Free 유저만) ─────────────────── */}
      {userPlan === "free" && missedCount > 0 && (
        <button
          onClick={() => paywall.show()}
          className="w-full flex items-center gap-2 px-4 py-2.5 border-b border-border bg-amber-500/5 hover:bg-amber-500/10 transition-colors text-left"
        >
          <Bell className="h-4 w-4 text-amber-500 shrink-0" />
          <span className="flex-1 text-xs font-medium text-amber-600 dark:text-amber-400">
            {t(lang, "missed_spike_banner", { n: missedCount })}
          </span>
          <span className="shrink-0 rounded-full bg-gradient-to-r from-blue-500 to-cyan-500 px-3 py-1 text-[10px] font-bold text-white">
            {t(lang, "missed_spike_cta")}
          </span>
        </button>
      )}
      <PaywallModal trigger="map_locked" isOpen={paywall.isOpen} onClose={paywall.close} />
      <WelcomeModal />

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
                {t(lang, "plan_country_limit_hint")}
              </p>
              <a
                href="/upgrade"
                className="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold text-white"
                style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
              >
                {t(lang, "btn_upgrade")}
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
              <p className="text-[11px] text-muted-foreground text-left whitespace-nowrap">
                {t(lang, "plan_country_limit_hint")}
              </p>
              <a
                href="/upgrade"
                className="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-bold text-white"
                style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
              >
                {t(lang, "btn_upgrade")}
              </a>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {/* 브리핑 카드 */}
            {!isLoading && !isError && items && items.length > 0 && (
              <BriefingCard items={items} lang={lang} />
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

            {/* ── 급상승 섹션 (글로벌 탭, 데이터 있을 때만) ──── */}
            {!isLoading && !isError && trendingTab === "global" && risingData.length > 0 && (
              <div className="mb-2">
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="text-xs font-bold">{t(lang, "home_rising_title")}</span>
                  <span className="inline-flex h-4 items-center rounded-full bg-emerald-500/20 px-1.5 text-[9px] font-bold text-emerald-500 animate-pulse leading-none">
                    RISING
                  </span>
                  <InfoTooltip text={t(lang, "signal_rising_tooltip")} direction="down" />
                </div>
                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                  {risingData.map((item) => {
                    const clusterId = item.cluster_ids?.[0];
                    const rawTitle = lang === "en" ? item.keyword : (item.keyword_ko ?? item.keyword);
                    const displayTitle = isJunkTitle(rawTitle)
                      ? buildSmartTitle(item.keyword, item.topic ?? "unknown", lang, getCountryName, item.country_codes?.[0])
                      : (stripTitlePrefix(rawTitle) || item.keyword);
                    const risingPK = personalizedKScore(item, homeCountry);
                    const badge = getKScoreBadge(risingPK, lang);
                    return (
                      <div
                        key={item.id}
                        onClick={clusterId ? () => router.push(`/issues/${clusterId}`) : undefined}
                        className={cn(
                          "shrink-0 w-48 rounded-lg border border-border bg-card p-3 cursor-pointer hover:bg-card/80 transition-colors",
                          kscoreAccent(risingPK),
                          "border-l-4",
                        )}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className={cn("text-[10px] font-bold", badge.text)}>
                            {roundKScore(risingPK).toFixed(1)}
                          </span>
                          {item.country_codes.length > 0 && (
                            <span className="text-[11px]">
                              {item.country_codes.map((code: string) => getFlag(code)).join(" ")}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] font-medium leading-snug line-clamp-2">{displayTitle}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {!isLoading && !isError && items && items.length > 0 && (
              <>
                {items.slice(0, visibleCount).map((item, i) => (
                  <TrendingCard key={item.id} item={item} rank={i + 1} delay={Math.min(i * 50, 500)} userPlan={userPlan} isAdmin={isAdmin} />
                ))}

                {items.length > visibleCount && (
                  <button
                    onClick={() => {
                      setLoadingMore(true);
                      requestAnimationFrame(() => {
                        setVisibleCount((v) => v + 30);
                        setLoadingMore(false);
                      });
                    }}
                    disabled={loadingMore}
                    className="w-full flex items-center justify-center gap-1.5 rounded-xl border border-border bg-card py-3 text-sm text-muted-foreground hover:text-foreground hover:bg-card/80 transition-colors disabled:opacity-60"
                  >
                    {loadingMore ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {lang === "ko" ? "불러오는 중…" : "Loading…"}
                      </>
                    ) : (
                      <>
                        <ChevronDown className="h-4 w-4" />
                        {lang === "ko"
                          ? `더보기 (${Math.min(visibleCount, items.length)}/${items.length})`
                          : `Load more (${Math.min(visibleCount, items.length)}/${items.length})`}
                      </>
                    )}
                  </button>
                )}
              </>
            )}
          </div>
        )}
    </div>
  );
}
