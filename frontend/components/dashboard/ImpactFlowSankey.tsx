"use client";

import React, { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import { t, type TranslationKey } from "@/lib/i18n";
import { getFlag } from "@/lib/countries";
import { ChevronRight, X } from "lucide-react";
import type { ImpactFlowOut } from "@/lib/api";

// 고정 크기 Sankey 사용 — ResponsiveSankey는 내부 ResizeObserver 의존으로 모바일 인앱 브라우저에서 실패
const Sankey = dynamic(
  () => import("@nivo/sankey").then((m) => m.Sankey),
  {
    ssr: false,
    loading: () => <div className="h-[220px] animate-pulse bg-muted/20 rounded" />,
  }
);

interface ConflictIssue {
  clusterId?: string;
  title: string;
  countryCodes: string[];
}

interface Props {
  data: ImpactFlowOut;
  isPro: boolean;
  lang: "ko" | "en";
  /** 좌측 분쟁 노드에 매칭되는 이슈 정보 (cluster_id, full title 등) */
  conflictIssues?: ConflictIssue[];
}

const CATEGORY_COLORS: Record<string, string> = {
  conflict: "#dc2626",
  commodity: "#f59e0b",
  impact: "#3b82f6",
};

const NUM_LABELS = ["①", "②", "③", "④", "⑤"];

/** Truncate for non-conflict labels */
function truncateLabel(label: string, category: string, compact: boolean): string {
  if (category === "conflict") return ""; // conflict labels handled externally
  const maxLen = compact
    ? (category === "impact" ? 7 : 6)
    : (category === "impact" ? 14 : 10);
  if (label.length <= maxLen) return label;
  return label.slice(0, maxLen) + "…";
}

export function ImpactFlowSankey({ data, isPro, lang, conflictIssues }: Props) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState(0);
  const [popupIdx, setPopupIdx] = useState<number | null>(null);

  // 컨테이너 실제 너비 측정 — 직접 DOM 측정 (ResizeObserver 미사용)
  useEffect(() => {
    function measure() {
      if (containerRef.current) {
        const w = containerRef.current.clientWidth || containerRef.current.offsetWidth || containerRef.current.getBoundingClientRect().width;
        if (w > 0) setChartWidth(Math.floor(w));
      }
    }
    // 즉시 + 약간의 딜레이 후 재측정 (레이아웃 완료 보장)
    measure();
    const t1 = setTimeout(measure, 100);
    const t2 = setTimeout(measure, 500);

    window.addEventListener("resize", measure);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      window.removeEventListener("resize", measure);
    };
  }, []);

  const isCompact = chartWidth < 380;
  const chartHeight = 220;

  // conflict nodes: use number labels like ①②③
  const conflictNodes = data.nodes.filter((n) => n.category === "conflict");

  const categoryMap = new Map(data.nodes.map((n) => [n.id, n.category]));
  const conflictIdxMap = new Map(conflictNodes.map((n, i) => [n.id, i]));

  const sankeyData = {
    nodes: data.nodes.map((n) => {
      const isConflict = n.category === "conflict";
      const idx = conflictIdxMap.get(n.id) ?? 0;
      return {
        id: n.id,
        label: n.label,
        shortLabel: isConflict ? NUM_LABELS[idx] : truncateLabel(n.label, n.category, isCompact),
        color: n.color || CATEGORY_COLORS[n.category] || "#6b7280",
        category: n.category,
      };
    }),
    links: data.links.map((l) => ({
      source: l.source,
      target: l.target,
      value: Math.max(1, l.value),
    })),
  };

  const popupIssue = popupIdx !== null ? (conflictIssues?.[popupIdx] ?? {
    title: conflictNodes[popupIdx]?.label ?? "",
    countryCodes: [],
    clusterId: undefined,
  }) : null;

  return (
    <div className="relative" ref={containerRef}>
      {/* Sankey 차트 */}
      <div className={cn(
        "relative",
        !isPro && "after:absolute after:inset-0 after:bg-gradient-to-r after:from-transparent after:via-transparent after:to-background/80"
      )} style={{ height: chartHeight }}>
        {chartWidth > 0 && (
          <Sankey
            width={chartWidth}
            height={chartHeight}
            data={sankeyData}
            margin={{ top: 6, right: isCompact ? 55 : 80, bottom: 6, left: isCompact ? 20 : 24 }}
            align="justify"
            colors={(node: any) => node.color || "#6b7280"}
            nodeOpacity={1}
            nodeHoverOpacity={1}
            nodeThickness={isCompact ? 10 : 12}
            nodeInnerPadding={2}
            nodeBorderWidth={0}
            nodeBorderRadius={3}
            linkOpacity={isPro ? 0.4 : 0.15}
            linkHoverOpacity={0.6}
            linkContract={1}
            linkBlendMode="normal"
            enableLinkGradient={true}
            labelPosition="outside"
            labelOrientation="horizontal"
            labelPadding={isCompact ? 3 : 5}
            labelTextColor={{ from: "color", modifiers: [["brighter", 0.8]] }}
            label={(node: any) =>
              node.shortLabel ?? truncateLabel(
                node.label || node.id,
                categoryMap.get(node.id) || "commodity",
                isCompact
              )
            }
            nodeTooltip={({ node }: any) => (
              <div className="bg-popover text-popover-foreground border border-border rounded-lg px-3 py-2 shadow-lg max-w-[220px]">
                <p className="text-[11px] font-medium leading-snug">{node.label || node.id}</p>
              </div>
            )}
            linkTooltip={() => null}
            motionConfig="gentle"
            theme={{
              labels: {
                text: {
                  fontSize: isCompact ? 9 : 11,
                  fill: "rgba(156,163,175,0.9)",
                  fontWeight: 600,
                },
              },
            }}
          />
        )}
      </div>

      {/* 분쟁 이슈 버튼 목록 — Sankey 아래 */}
      <div className="px-3 pb-2 flex flex-wrap gap-1.5">
        {conflictNodes.map((node, idx) => {
          const issue = conflictIssues?.[idx];
          const flags = issue?.countryCodes?.slice(0, 2).map(getFlag).join("") ?? "";
          const shortTitle = node.label.length > 12 ? node.label.slice(0, 12) + "…" : node.label;
          return (
            <button
              key={node.id}
              onClick={(e) => { e.stopPropagation(); setPopupIdx(idx); }}
              className="inline-flex items-center gap-1 rounded-full bg-red-500/10 border border-red-500/20 px-2 py-1 text-[10px] font-medium text-red-400 hover:bg-red-500/20 transition-colors"
            >
              <span className="font-bold">{NUM_LABELS[idx]}</span>
              {flags && <span className="text-xs">{flags}</span>}
              <span className="truncate max-w-[100px]">{shortTitle}</span>
            </button>
          );
        })}
      </div>

      {/* Category legend */}
      <div className="flex items-center justify-center gap-3 px-3 pb-2 pt-0.5">
        {[
          { key: "conflict", color: "#dc2626", label: lang === "ko" ? "분쟁" : "Conflict" },
          { key: "commodity", color: "#f59e0b", label: lang === "ko" ? "산업" : "Industry" },
          { key: "impact", color: "#3b82f6", label: lang === "ko" ? "생활영향" : "Life Impact" },
        ].map((c) => (
          <span key={c.key} className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: c.color }} />
            <span className="text-[8px] text-muted-foreground">{c.label}</span>
          </span>
        ))}
      </div>

      {!isPro && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none" style={{ top: chartHeight / 2 }}>
          <span className="text-[10px] text-muted-foreground/40 bg-background/60 px-3 py-1 rounded-full pointer-events-auto">
            {t(lang, "dash_pro_demo_flow" as TranslationKey)}
          </span>
        </div>
      )}

      {/* 팝업 — 이슈 전체 제목 + 상세 보기 */}
      {popupIdx !== null && popupIssue && (
        <>
          <div className="fixed inset-0 z-50 bg-black/40" onClick={() => setPopupIdx(null)} />
          <div className="fixed bottom-0 left-0 right-0 z-50 rounded-t-2xl border-t border-border bg-card px-5 py-4 shadow-2xl animate-in slide-in-from-bottom duration-200 max-w-lg mx-auto">
            <div className="flex items-start gap-3">
              <span className="text-lg font-bold text-red-400 shrink-0">{NUM_LABELS[popupIdx]}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-1">
                  {(popupIssue as ConflictIssue).countryCodes?.map((cc) => (
                    <span key={cc} className="text-sm">{getFlag(cc)}</span>
                  ))}
                </div>
                <p className="text-sm font-semibold text-foreground leading-snug mb-3">
                  {popupIssue.title}
                </p>
                {(popupIssue as ConflictIssue).clusterId && (
                  <button
                    onClick={() => {
                      setPopupIdx(null);
                      router.push(`/issues/${(popupIssue as ConflictIssue).clusterId}`);
                    }}
                    className="inline-flex items-center gap-1 rounded-full bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground"
                  >
                    {lang === "ko" ? "이슈 상세 보기" : "View Issue"}
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
              <button
                onClick={() => setPopupIdx(null)}
                className="shrink-0 p-1 rounded-full hover:bg-muted/50 transition-colors"
              >
                <X className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
