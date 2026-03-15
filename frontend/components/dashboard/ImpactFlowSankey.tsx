"use client";

import React, { useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { t, type TranslationKey } from "@/lib/i18n";
import { getFlag } from "@/lib/countries";
import { ChevronRight, X } from "lucide-react";
import type { ImpactFlowOut } from "@/lib/api";

/**
 * 순수 SVG Sankey 차트 — @nivo/sankey 제거
 * nivo의 ResponsiveSankey/Sankey 모두 내부적으로 ResizeObserver 또는
 * useMeasure를 사용하여 모바일 인앱 브라우저(토스, 웨일 등)에서 렌더링 실패.
 * 외부 라이브러리 의존성 0으로 모바일 호환성 100% 보장.
 */

interface ConflictIssue {
  clusterId?: string;
  title: string;
  countryCodes: string[];
}

interface Props {
  data: ImpactFlowOut;
  isPro: boolean;
  lang: "ko" | "en";
  conflictIssues?: ConflictIssue[];
}

const CATEGORY_COLORS: Record<string, string> = {
  conflict: "#dc2626",
  commodity: "#f59e0b",
  impact: "#3b82f6",
};

const NUM_LABELS = ["①", "②", "③", "④", "⑤"];

function truncLabel(s: string, max: number) {
  return s.length > max ? s.slice(0, max) + "…" : s;
}

/** 3단 Sankey 레이아웃 계산 */
function computeLayout(data: ImpactFlowOut, width: number, height: number) {
  const margin = { top: 8, right: 8, bottom: 8, left: 8 };
  const nodeW = 10;
  const colGap = 40;
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  // 3개 칼럼: conflict, commodity, impact
  const cols: Record<string, typeof data.nodes> = { conflict: [], commodity: [], impact: [] };
  for (const n of data.nodes) {
    const cat = n.category || "commodity";
    if (cols[cat]) cols[cat].push(n);
    else cols.commodity.push(n);
  }

  const colX = {
    conflict: margin.left,
    commodity: margin.left + (innerW - nodeW) / 2 - colGap / 2,
    impact: margin.left + innerW - nodeW,
  };

  // 각 노드에 y위치 계산 (균등 분배)
  const nodePositions = new Map<string, { x: number; y: number; h: number; color: string; label: string; category: string }>();

  for (const cat of ["conflict", "commodity", "impact"] as const) {
    const nodes = cols[cat];
    if (!nodes.length) continue;
    const totalPad = Math.max(0, (nodes.length - 1) * 6);
    const nodeH = Math.max(12, (innerH - totalPad) / nodes.length);
    let y = margin.top;
    for (const n of nodes) {
      nodePositions.set(n.id, {
        x: colX[cat],
        y,
        h: nodeH,
        color: n.color || CATEGORY_COLORS[cat] || "#6b7280",
        label: n.label,
        category: cat,
      });
      y += nodeH + 6;
    }
  }

  // 링크 계산: 각 링크에 대해 source/target 노드의 중앙 연결
  // 각 노드의 링크 할당 위치 추적
  const nodeOutOffset = new Map<string, number>();
  const nodeInOffset = new Map<string, number>();
  for (const n of data.nodes) {
    nodeOutOffset.set(n.id, 0);
    nodeInOffset.set(n.id, 0);
  }

  // 링크 value 합계 계산
  const nodeOutTotal = new Map<string, number>();
  const nodeInTotal = new Map<string, number>();
  for (const l of data.links) {
    nodeOutTotal.set(l.source, (nodeOutTotal.get(l.source) ?? 0) + Math.max(1, l.value));
    nodeInTotal.set(l.target, (nodeInTotal.get(l.target) ?? 0) + Math.max(1, l.value));
  }

  const links = data.links.map((l) => {
    const src = nodePositions.get(l.source);
    const tgt = nodePositions.get(l.target);
    if (!src || !tgt) return null;

    const val = Math.max(1, l.value);
    const srcTotal = nodeOutTotal.get(l.source) ?? 1;
    const tgtTotal = nodeInTotal.get(l.target) ?? 1;

    const srcH = (val / srcTotal) * src.h;
    const tgtH = (val / tgtTotal) * tgt.h;
    const linkThickness = Math.max(2, Math.min(srcH, tgtH, 20));

    const srcOff = nodeOutOffset.get(l.source) ?? 0;
    const tgtOff = nodeInOffset.get(l.target) ?? 0;

    const y0 = src.y + srcOff + linkThickness / 2;
    const y1 = tgt.y + tgtOff + linkThickness / 2;

    nodeOutOffset.set(l.source, srcOff + linkThickness);
    nodeInOffset.set(l.target, tgtOff + linkThickness);

    const x0 = src.x + nodeW;
    const x1 = tgt.x;
    const cx = (x0 + x1) / 2;

    return {
      d: `M${x0},${y0} C${cx},${y0} ${cx},${y1} ${x1},${y1}`,
      thickness: linkThickness,
      srcColor: src.color,
      tgtColor: tgt.color,
      sourceId: l.source,
      targetId: l.target,
    };
  }).filter(Boolean);

  return { nodePositions, links: links as NonNullable<(typeof links)[0]>[], nodeW, colX };
}

export function ImpactFlowSankey({ data, isPro, lang, conflictIssues }: Props) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState(0);
  const [popupIdx, setPopupIdx] = useState<number | null>(null);

  useEffect(() => {
    function measure() {
      if (containerRef.current) {
        const w = containerRef.current.clientWidth || containerRef.current.offsetWidth || containerRef.current.getBoundingClientRect().width;
        if (w > 0) setChartWidth(Math.floor(w));
      }
    }
    measure();
    const t1 = setTimeout(measure, 50);
    const t2 = setTimeout(measure, 200);
    const t3 = setTimeout(measure, 500);
    window.addEventListener("resize", measure);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      window.removeEventListener("resize", measure);
    };
  }, []);

  // fallback: window.innerWidth 기반
  const effectiveWidth = chartWidth > 0 ? chartWidth : (typeof window !== "undefined" ? Math.min(window.innerWidth - 32, 600) : 360);
  const chartHeight = 200;

  const conflictNodes = data.nodes.filter((n) => n.category === "conflict");
  const conflictIdxMap = new Map(conflictNodes.map((n, i) => [n.id, i]));

  const { nodePositions, links, nodeW } = computeLayout(data, effectiveWidth, chartHeight);

  const popupIssue = popupIdx !== null ? (conflictIssues?.[popupIdx] ?? {
    title: conflictNodes[popupIdx]?.label ?? "",
    countryCodes: [],
    clusterId: undefined,
  }) : null;

  return (
    <div className="relative" ref={containerRef}>
      {/* 순수 SVG Sankey */}
      <div className={cn(
        "relative",
        !isPro && "after:absolute after:inset-0 after:bg-gradient-to-r after:from-transparent after:via-transparent after:to-background/80"
      )}>
        <svg
          width={effectiveWidth}
          height={chartHeight}
          viewBox={`0 0 ${effectiveWidth} ${chartHeight}`}
          className="w-full"
          style={{ display: "block" }}
        >
          {/* 링크 (곡선) */}
          {links.map((l, i) => (
            <path
              key={i}
              d={l.d}
              fill="none"
              stroke={l.srcColor}
              strokeWidth={l.thickness}
              strokeOpacity={isPro ? 0.3 : 0.12}
              strokeLinecap="round"
            />
          ))}

          {/* 노드 (사각형) */}
          {Array.from(nodePositions.entries()).map(([id, pos]) => (
            <rect
              key={id}
              x={pos.x}
              y={pos.y}
              width={nodeW}
              height={pos.h}
              rx={3}
              fill={pos.color}
            />
          ))}

          {/* 라벨 */}
          {Array.from(nodePositions.entries()).map(([id, pos]) => {
            const isConflict = pos.category === "conflict";
            const isImpact = pos.category === "impact";
            const idx = conflictIdxMap.get(id) ?? -1;
            const maxLen = effectiveWidth < 380 ? 6 : 10;

            const labelText = isConflict
              ? NUM_LABELS[idx] ?? ""
              : truncLabel(pos.label, isImpact ? maxLen + 4 : maxLen);

            const textX = isConflict
              ? pos.x - 4
              : pos.x + nodeW + 4;
            const textAnchor = isConflict ? "end" : "start";

            return (
              <text
                key={`label-${id}`}
                x={textX}
                y={pos.y + pos.h / 2}
                dy="0.35em"
                textAnchor={textAnchor}
                fill={isConflict ? pos.color : "rgba(156,163,175,0.9)"}
                fontSize={effectiveWidth < 380 ? 9 : 11}
                fontWeight={600}
              >
                {labelText}
              </text>
            );
          })}
        </svg>
      </div>

      {/* 분쟁 이슈 버튼 목록 */}
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
        <div className="absolute pointer-events-none" style={{ top: chartHeight / 2, left: "50%", transform: "translate(-50%, -50%)" }}>
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
