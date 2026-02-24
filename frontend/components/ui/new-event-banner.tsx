"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Bell, X, ExternalLink } from "lucide-react";
import Link from "next/link";
import { cn, TOPIC_LABELS } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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

export function NewEventBanner() {
  const [item, setItem] = useState<PeekItem | null>(null);
  const [visible, setVisible] = useState(false);
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback((target?: PeekItem | null) => {
    const t = target ?? item;
    const cid = t?.cluster_ids?.[0];
    if (cid) markSeenCluster(cid);
    setVisible(false);
    if (dismissTimer.current) clearTimeout(dismissTimer.current);
  }, [item]);

  const poll = useCallback(async () => {
    try {
      const since =
        sessionStorage.getItem("banner_last_peek") ||
        new Date(Date.now() - 3 * 60_000).toISOString();
      sessionStorage.setItem("banner_last_peek", new Date().toISOString());

      const res = await fetch(
        `${API_BASE}/trending/peek?min_kscore=1&since=${encodeURIComponent(since)}`
      );
      if (!res.ok) return;

      const data: PeekItem[] = await res.json();
      const seen = getSeenClusters();
      // cluster_id 기반 중복 체크 (row id는 워커 실행마다 바뀌므로 신뢰 불가)
      const newItem = data.find((d) => d.cluster_ids?.[0] && !seen.has(d.cluster_ids[0]));
      if (newItem) {
        setItem(newItem);
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
    if (!visible || !item) return;
    dismissTimer.current = setTimeout(() => dismiss(item), AUTO_DISMISS_MS);
    return () => { if (dismissTimer.current) clearTimeout(dismissTimer.current); };
  }, [visible, item, dismiss]);

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
                새 이슈 감지
              </span>
              <span className="text-[10px] text-muted-foreground/60">·</span>
              <span className="text-[10px] text-muted-foreground">{topicLabel}</span>
              {item?.is_spike && (
                <span className="text-[10px] bg-red-500/15 text-red-400 px-1.5 py-0.5 rounded-full leading-none">
                  스파이크
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
                onClick={() => dismiss(item)}
                className="flex items-center gap-1 rounded-lg bg-secondary hover:bg-secondary/80 px-2.5 py-1.5 text-[11px] font-medium text-foreground transition-colors"
              >
                보기
                <ExternalLink className="h-3 w-3 text-muted-foreground" />
              </Link>
            )}
            <button
              onClick={() => dismiss(item)}
              className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
              aria-label="닫기"
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
