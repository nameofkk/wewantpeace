"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Bell, X, ExternalLink, TrendingUp } from "lucide-react";
import Link from "next/link";
import { cn, TOPIC_LABELS } from "@/lib/utils";
import { COUNTRY_MAP, getFlag } from "@/lib/countries";
import { API_BASE } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { t, getTensionLevelLabel } from "@/lib/i18n";
const POLL_INTERVAL = 60_000;
const AUTO_DISMISS_MS = 9_000;

interface PeekItem {
  id: number;
  keyword: string;
  keyword_ko: string | null;
  kscore: number;
  topic: string | null;
  cluster_ids: string[];
  is_spike: boolean;
}

interface TensionPeekItem {
  country_code: string;
  tension_level: number;
  prev_level: number;
  raw_score: number;
  change_type: string;
}

// 배너 표시 우선순위 타입
type BannerData =
  | { type: "tension"; data: TensionPeekItem }
  | { type: "event"; data: PeekItem };

const TOPIC_ACCENT: Record<string, string> = {
  terror:    "bg-red-500",
  conflict:  "bg-orange-500",
  coup:      "bg-red-600",
  sanctions: "bg-yellow-500",
  cyber:     "bg-violet-500",
  protest:   "bg-blue-500",
  diplomacy: "bg-sky-500",
  maritime:  "bg-cyan-500",
  disaster:  "bg-sky-400",
  health:    "bg-emerald-500",
  unknown:   "bg-slate-500",
};

const TOPIC_DOT: Record<string, string> = {
  terror:    "bg-red-500",
  conflict:  "bg-orange-500",
  coup:      "bg-red-600",
  sanctions: "bg-yellow-400",
  cyber:     "bg-violet-400",
  protest:   "bg-blue-400",
  diplomacy: "bg-sky-400",
  maritime:  "bg-cyan-400",
  disaster:  "bg-sky-400",
  health:    "bg-emerald-400",
  unknown:   "bg-slate-400",
};

const TENSION_ACCENT: Record<number, string> = {
  0: "bg-emerald-500",
  1: "bg-amber-500",
  2: "bg-orange-500",
  3: "bg-red-500",
  4: "bg-red-900",
};

const TENSION_DOT: Record<number, string> = {
  0: "bg-emerald-400",
  1: "bg-amber-400",
  2: "bg-orange-400",
  3: "bg-red-400",
  4: "bg-red-300",
};

// cluster_id 기반 중복 추적 (row id가 매번 바뀌는 문제 방지)
function getSeenClusters(): Set<string> {
  try {
    const raw = sessionStorage.getItem("banner_seen_clusters");
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function markSeenCluster(clusterId: string) {
  try {
    const seen = getSeenClusters();
    seen.add(clusterId);
    sessionStorage.setItem("banner_seen_clusters", JSON.stringify([...seen].slice(-200)));
  } catch {}
}

// 긴장도 배너 중복 방지
function getSeenTensions(): Set<string> {
  try {
    const raw = sessionStorage.getItem("banner_seen_tensions");
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function markSeenTension(key: string) {
  try {
    const seen = getSeenTensions();
    seen.add(key);
    sessionStorage.setItem("banner_seen_tensions", JSON.stringify([...seen].slice(-50)));
  } catch {}
}

export function NewEventBanner() {
  const lang = useAppStore((s) => s.lang);
  const [banner, setBanner] = useState<BannerData | null>(null);
  const [visible, setVisible] = useState(false);
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback(() => {
    if (banner?.type === "event") {
      const cid = banner.data.cluster_ids?.[0];
      if (cid) markSeenCluster(cid);
    } else if (banner?.type === "tension") {
      const key = `${banner.data.country_code}:${banner.data.prev_level}:${banner.data.tension_level}`;
      markSeenTension(key);
    }
    setVisible(false);
    if (dismissTimer.current) clearTimeout(dismissTimer.current);
  }, [banner]);

  const poll = useCallback(async () => {
    try {
      const since =
        sessionStorage.getItem("banner_last_peek") ||
        new Date(Date.now() - 3 * 60_000).toISOString();
      sessionStorage.setItem("banner_last_peek", new Date().toISOString());

      // 긴장도 peek 먼저 체크 (우선순위 높음)
      try {
        const tensionRes = await fetch(
          `${API_BASE}/tension/peek?since=${encodeURIComponent(since)}`
        );
        if (tensionRes.ok) {
          const tensionData: TensionPeekItem[] = await tensionRes.json();
          const seenTensions = getSeenTensions();
          const newTension = tensionData.find((t) => {
            const key = `${t.country_code}:${t.prev_level}:${t.tension_level}`;
            return !seenTensions.has(key);
          });
          if (newTension) {
            setBanner({ type: "tension", data: newTension });
            setVisible(true);
            return; // 긴장도 배너 우선 표시
          }
        }
      } catch {}

      // 이슈 배너
      const res = await fetch(
        `${API_BASE}/trending/peek?min_kscore=1&since=${encodeURIComponent(since)}`
      );
      if (!res.ok) return;

      const data: PeekItem[] = await res.json();
      const seen = getSeenClusters();
      const newItem = data.find((d) => d.cluster_ids?.[0] && !seen.has(d.cluster_ids[0]));
      if (newItem) {
        setBanner({ type: "event", data: newItem });
        setVisible(true);
      }
    } catch {}
  }, []);

  useEffect(() => {
    sessionStorage.setItem("banner_last_peek", new Date().toISOString());
    const initial = setTimeout(poll, 5_000);
    const interval = setInterval(poll, POLL_INTERVAL);
    return () => { clearTimeout(initial); clearInterval(interval); };
  }, [poll]);

  useEffect(() => {
    if (!visible || !banner) return;
    dismissTimer.current = setTimeout(dismiss, AUTO_DISMISS_MS);
    return () => { if (dismissTimer.current) clearTimeout(dismissTimer.current); };
  }, [visible, banner, dismiss]);

  // 긴장도 배너 렌더링
  if (banner?.type === "tension") {
    const td = banner.data;
    const accent = TENSION_ACCENT[td.tension_level] ?? "bg-slate-500";
    const dot = TENSION_DOT[td.tension_level] ?? "bg-slate-400";
    const countryName = COUNTRY_MAP[td.country_code]?.name ?? td.country_code;
    const flag = getFlag(td.country_code);
    const prevLabel = getTensionLevelLabel(td.prev_level as 0 | 1 | 2 | 3 | 4, lang);
    const newLabel = getTensionLevelLabel(td.tension_level as 0 | 1 | 2 | 3 | 4, lang);

    return (
      <div
        className={cn(
          "fixed top-0 left-0 right-0 z-[200] transition-transform duration-300 ease-out",
          visible ? "translate-y-0" : "-translate-y-full"
        )}
        aria-live="polite"
        role="alert"
      >
        <div className="relative flex items-stretch bg-card/95 backdrop-blur-md border-b border-border shadow-[0_4px_20px_rgba(0,0,0,0.4)]">
          <div className={cn("w-1 shrink-0 rounded-r-full my-2", accent)} />

          <div className="flex items-center gap-3 px-4 py-3 flex-1 min-w-0 max-w-2xl mx-auto">
            <div className="shrink-0 relative">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              <span className={cn("absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full", dot)} />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                  {t(lang, "banner_tension_rise")}
                </span>
                <span className="text-[10px] text-muted-foreground/50 font-mono ml-auto">
                  {td.raw_score.toFixed(1)}{t(lang, "banner_score_suffix")}
                </span>
              </div>
              <p className="text-sm font-medium text-foreground truncate">
                {flag} {countryName} {prevLabel}→{newLabel} ({td.raw_score.toFixed(1)}{t(lang, "banner_score_suffix")})
              </p>
            </div>

            <div className="flex items-center gap-1 shrink-0">
              <Link
                href="/tension"
                onClick={dismiss}
                className="flex items-center gap-1 rounded-lg bg-secondary hover:bg-secondary/80 px-2.5 py-1.5 text-[11px] font-medium text-foreground transition-colors"
              >
                {t(lang, "banner_view")}
                <ExternalLink className="h-3 w-3 text-muted-foreground" />
              </Link>
              <button
                onClick={dismiss}
                className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                aria-label={t(lang, "banner_close")}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {visible && (
          <div className="h-[2px] bg-border">
            <div
              className={cn("h-full origin-left", accent, "opacity-60")}
              style={{ animation: `shrink-x ${AUTO_DISMISS_MS}ms linear forwards` }}
            />
          </div>
        )}
      </div>
    );
  }

  // 이슈 배너 렌더링 (기존)
  const item = banner?.type === "event" ? banner.data : null;
  const clusterId = item?.cluster_ids[0];
  const topic = item?.topic ?? "unknown";
  const topicLabel = TOPIC_LABELS[topic] ?? topic;
  const accent = TOPIC_ACCENT[topic] ?? "bg-slate-500";
  const dot = TOPIC_DOT[topic] ?? "bg-slate-400";

  return (
    <div
      className={cn(
        "fixed top-0 left-0 right-0 z-[200] transition-transform duration-300 ease-out",
        visible ? "translate-y-0" : "-translate-y-full"
      )}
      aria-live="polite"
      role="alert"
    >
      {/* 메인 배너 */}
      <div className="relative flex items-stretch bg-card/95 backdrop-blur-md border-b border-border shadow-[0_4px_20px_rgba(0,0,0,0.4)]">
        {/* 왼쪽 토픽 accent 바 */}
        <div className={cn("w-1 shrink-0 rounded-r-full my-2", accent)} />

        <div className="flex items-center gap-3 px-4 py-3 flex-1 min-w-0 max-w-2xl mx-auto">
          {/* 아이콘 */}
          <div className="shrink-0 relative">
            <Bell className="h-4 w-4 text-muted-foreground" />
            <span className={cn("absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full", dot)} />
          </div>

          {/* 텍스트 */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                {t(lang, "banner_new_event")}
              </span>
              <span className="text-[10px] text-muted-foreground/60">·</span>
              <span className="text-[10px] text-muted-foreground">{topicLabel}</span>
              {item?.is_spike && (
                <span className="text-[10px] bg-red-500/15 text-red-400 px-1.5 py-0.5 rounded-full leading-none">
                  {t(lang, "banner_spike")}
                </span>
              )}
              <span className="text-[10px] text-muted-foreground/50 font-mono ml-auto">
                KScore {item?.kscore.toFixed(1)}
              </span>
            </div>
            <p className="text-sm font-medium text-foreground truncate">
              {item?.keyword_ko || item?.keyword}
            </p>
          </div>

          {/* 버튼 */}
          <div className="flex items-center gap-1 shrink-0">
            {clusterId && (
              <Link
                href={`/issues/${clusterId}`}
                onClick={dismiss}
                className="flex items-center gap-1 rounded-lg bg-secondary hover:bg-secondary/80 px-2.5 py-1.5 text-[11px] font-medium text-foreground transition-colors"
              >
                {t(lang, "banner_view")}
                <ExternalLink className="h-3 w-3 text-muted-foreground" />
              </Link>
            )}
            <button
              onClick={dismiss}
              className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
              aria-label={t(lang, "banner_close")}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* 자동 닫힘 프로그레스 바 */}
      {visible && (
        <div className="h-[2px] bg-border">
          <div
            className={cn("h-full origin-left", accent, "opacity-60")}
            style={{ animation: `shrink-x ${AUTO_DISMISS_MS}ms linear forwards` }}
          />
        </div>
      )}
    </div>
  );
}
