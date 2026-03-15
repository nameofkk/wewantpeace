"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { t, type TranslationKey } from "@/lib/i18n";
import { getFlag } from "@/lib/countries";
import { useAppStore } from "@/lib/store";
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
  if (max >= 999) return s; // no truncation
  return s.length > max ? s.slice(0, max) + "…" : s;
}

/** 3단 Sankey 레이아웃 계산 */
function computeLayout(data: ImpactFlowOut, width: number, height: number, sizeClass: "sm" | "md" | "lg", lang: "ko" | "en" = "ko") {
  const isEn = lang === "en";
  const sizeCfg = {
    sm:  { top: 10, right: isEn ? 130 : 100, bottom: 18, left: isEn ? 16 : 22, nodeW: 10, colGap: 40, nodePad: 6, minNodeH: 12, maxLinkH: 20, minLink: 2 },
    md:  { top: 10, right: isEn ? 160 : 140, bottom: 20, left: isEn ? 22 : 28, nodeW: 14, colGap: 60, nodePad: 10, minNodeH: 18, maxLinkH: 28, minLink: 3 },
    lg:  { top: 12, right: 160, bottom: 22, left: 36, nodeW: 16, colGap: 80, nodePad: 14, minNodeH: 22, maxLinkH: 34, minLink: 4 },
  };
  const cfg = sizeCfg[sizeClass];
  const margin = { top: cfg.top, right: cfg.right, bottom: cfg.bottom, left: cfg.left };
  const nodeW = cfg.nodeW;
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
    commodity: margin.left + (innerW - nodeW) / 2 - cfg.colGap / 2,
    impact: margin.left + innerW - nodeW,
  };

  // 각 노드에 y위치 계산 (균등 분배)
  const nodePositions = new Map<string, { x: number; y: number; h: number; color: string; label: string; category: string }>();

  for (const cat of ["conflict", "commodity", "impact"] as const) {
    const nodes = cols[cat];
    if (!nodes.length) continue;
    const totalPad = Math.max(0, (nodes.length - 1) * cfg.nodePad);
    const nodeH = Math.max(cfg.minNodeH, (innerH - totalPad) / nodes.length);
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
      y += nodeH + cfg.nodePad;
    }
  }

  // 링크 계산: 각 링크에 대해 source/target 노드의 중앙 연결
  const nodeOutOffset = new Map<string, number>();
  const nodeInOffset = new Map<string, number>();
  for (const n of data.nodes) {
    nodeOutOffset.set(n.id, 0);
    nodeInOffset.set(n.id, 0);
  }

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
    const linkThickness = Math.max(cfg.minLink, Math.min(srcH, tgtH, cfg.maxLinkH));

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

/** 방향성 추적: 해당 노드의 흐름만 하이라이트 (다른 conflict로 번지지 않음) */
function getConnectedSet(
  nodeId: string,
  links: { sourceId: string; targetId: string }[],
  nodePositions: Map<string, { category: string }>,
) {
  const connectedLinks = new Set<number>();
  const connectedNodes = new Set<string>([nodeId]);
  const cat = nodePositions.get(nodeId)?.category;

  if (cat === "conflict") {
    // conflict → 순방향만: conflict→commodity→impact
    const midNodes = new Set<string>();
    links.forEach((l, i) => {
      if (l.sourceId === nodeId) {
        connectedLinks.add(i);
        connectedNodes.add(l.targetId);
        midNodes.add(l.targetId);
      }
    });
    links.forEach((l, i) => {
      if (midNodes.has(l.sourceId)) {
        connectedLinks.add(i);
        connectedNodes.add(l.targetId);
      }
    });
  } else if (cat === "impact") {
    // impact → 역방향만: impact←commodity←conflict
    const midNodes = new Set<string>();
    links.forEach((l, i) => {
      if (l.targetId === nodeId) {
        connectedLinks.add(i);
        connectedNodes.add(l.sourceId);
        midNodes.add(l.sourceId);
      }
    });
    links.forEach((l, i) => {
      if (midNodes.has(l.targetId)) {
        connectedLinks.add(i);
        connectedNodes.add(l.sourceId);
      }
    });
  } else {
    // commodity → 양방향이지만 해당 commodity 경유 링크만
    links.forEach((l, i) => {
      if (l.sourceId === nodeId || l.targetId === nodeId) {
        connectedLinks.add(i);
        connectedNodes.add(l.sourceId);
        connectedNodes.add(l.targetId);
      }
    });
  }

  return { connectedLinks, connectedNodes };
}

export function ImpactFlowSankey({ data, isPro, lang, conflictIssues }: Props) {
  const router = useRouter();
  const isDark = useAppStore((s) => s.theme) === "dark";
  const containerRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState(0);
  const [popupIdx, setPopupIdx] = useState<number | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // 데이터 변경 시 자연스러운 트랜지션
  const dataKey = data.nodes.map((n) => n.id).join(",");
  const [visible, setVisible] = useState(true);
  const prevKeyRef = useRef(dataKey);
  useEffect(() => {
    if (dataKey !== prevKeyRef.current) {
      setVisible(false); // fade out
      const timer = setTimeout(() => {
        prevKeyRef.current = dataKey;
        setPopupIdx(null);
        setHoveredNodeId(null);
        setVisible(true); // fade in with new data
      }, 180);
      return () => clearTimeout(timer);
    }
  }, [dataKey]);

  useEffect(() => {
    function measure() {
      if (containerRef.current) {
        const w = containerRef.current.clientWidth || containerRef.current.offsetWidth || containerRef.current.getBoundingClientRect().width;
        if (w > 0) setChartWidth(Math.floor(w));
      }
      // fallback: DOM에서 못 읽으면 window.innerWidth 사용
      if (chartWidth <= 0 && typeof window !== "undefined") {
        setChartWidth(Math.min(window.innerWidth - 32, 900));
      }
    }
    measure();
    const t1 = setTimeout(measure, 50);
    const t2 = setTimeout(measure, 150);
    const t3 = setTimeout(measure, 400);
    const t4 = setTimeout(measure, 1000);
    window.addEventListener("resize", measure);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      window.removeEventListener("resize", measure);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 터치 해제 타이머
  const touchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleNodeHover = useCallback((nodeId: string | null) => {
    if (touchTimerRef.current) clearTimeout(touchTimerRef.current);
    setHoveredNodeId(nodeId);
    // 터치 후 3초 뒤 자동 해제
    if (nodeId) {
      touchTimerRef.current = setTimeout(() => setHoveredNodeId(null), 3000);
    }
  }, []);

  const sizeClass: "sm" | "md" | "lg" = chartWidth > 1024 ? "lg" : chartWidth > 640 ? "md" : "sm";
  const chartHeight = sizeClass === "lg" ? 300 : sizeClass === "md" ? 260 : 200;
  const isDesktop = sizeClass !== "sm";

  // SSR에서 렌더링하지 않음 — hydration mismatch 방지
  if (chartWidth <= 0) {
    return (
      <div ref={containerRef} className="relative" style={{ minHeight: 200 }}>
        <div className="flex items-center justify-center py-8">
          <div className="h-4 w-4 rounded-full border-2 border-red-400 border-t-transparent animate-spin" />
        </div>
      </div>
    );
  }

  const effectiveWidth = chartWidth;
  const conflictNodes = data.nodes.filter((n) => n.category === "conflict");
  const conflictIdxMap = new Map(conflictNodes.map((n, i) => [n.id, i]));

  const { nodePositions, links, nodeW } = computeLayout(data, effectiveWidth, chartHeight, sizeClass, lang);

  // 호버 시 연결 계산
  const { connectedLinks, connectedNodes } = hoveredNodeId
    ? getConnectedSet(hoveredNodeId, links, nodePositions as Map<string, { category: string }>)
    : { connectedLinks: new Set<number>(), connectedNodes: new Set<string>() };
  const isHovering = hoveredNodeId !== null;

  const popupIssue = popupIdx !== null ? (conflictIssues?.[popupIdx] ?? {
    title: conflictNodes[popupIdx]?.label ?? "",
    countryCodes: [],
    clusterId: undefined,
  }) : null;

  return (
    <div className="relative" ref={containerRef}>
      {/* 순수 SVG Sankey */}
      <div
        className={cn(
          "relative",
          !isPro && "after:absolute after:inset-0 after:bg-gradient-to-r after:from-transparent after:via-transparent after:to-background/80"
        )}
        style={{ opacity: visible ? 1 : 0, transition: "opacity 0.25s ease-in-out" }}
      >
        <svg
          width={effectiveWidth}
          height={chartHeight}
          viewBox={`0 0 ${effectiveWidth} ${chartHeight}`}
          className="w-full"
          style={{ display: "block", overflow: "visible" }}
          onMouseLeave={() => setHoveredNodeId(null)}
        >
          {/* 글로우 필터 (은은하게) */}
          <defs>
            <filter id="pg" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="1.5" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {/* 링크 (곡선) */}
          {links.map((l, i) => {
            const srcIdx = conflictIdxMap.get(l.sourceId) ?? -1;
            const isConnected = connectedLinks.has(i);
            const baseOpacity = isPro ? 0.3 : 0.12;
            const linkOpacity = isHovering
              ? isConnected ? 0.55 : 0.06
              : baseOpacity;
            const idleDur = 3.5 + (i % 5) * 0.8;

            return (
              <g key={i}>
                {/* 기본 링크 */}
                <path
                  d={l.d}
                  fill="none"
                  stroke={l.srcColor}
                  strokeWidth={l.thickness}
                  strokeOpacity={linkOpacity}
                  strokeLinecap="round"
                  style={{ transition: "stroke-opacity 0.25s ease" }}
                />

                {/* 유휴: 작은 점 1개가 천천히 경로를 따라 이동 */}
                {!isHovering && (
                  <circle
                    r={Math.max(l.thickness * 0.15, 1.5)}
                    fill={isDark ? "white" : l.srcColor}
                    opacity={isPro ? (isDark ? 0.35 : 0.5) : (isDark ? 0.18 : 0.3)}
                    filter="url(#pg)"
                  >
                    <animateMotion
                      dur={`${idleDur}s`}
                      repeatCount="indefinite"
                      path={l.d}
                    />
                  </circle>
                )}

                {/* 호버 시: 밝은 점 + 은은한 경로 글로우 */}
                {isHovering && isConnected && (
                  <>
                    <path
                      d={l.d}
                      fill="none"
                      stroke={isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)"}
                      strokeWidth={l.thickness + 3}
                      strokeLinecap="round"
                    />
                    <circle
                      r={Math.max(l.thickness * 0.22, 2)}
                      fill={isDark ? "white" : l.srcColor}
                      opacity={isDark ? 0.6 : 0.8}
                      filter="url(#pg)"
                    >
                      <animateMotion
                        dur="1.2s"
                        repeatCount="indefinite"
                        path={l.d}
                      />
                    </circle>
                  </>
                )}

                {/* 넓은 투명 터치 영역 (모바일 탭용) */}
                {srcIdx >= 0 && (
                  <path
                    d={l.d}
                    fill="none"
                    stroke="transparent"
                    strokeWidth={Math.max(l.thickness, 20)}
                    style={{ cursor: "pointer" }}
                    onClick={() => setPopupIdx(srcIdx)}
                  />
                )}
              </g>
            );
          })}

          {/* 노드 (사각형) + 터치/호버 영역 */}
          {Array.from(nodePositions.entries()).map(([id, pos]) => {
            const isConflict = pos.category === "conflict";
            const cIdx = conflictIdxMap.get(id) ?? -1;
            const isNodeConnected = !isHovering || connectedNodes.has(id);
            const nodeOpacity = isHovering && !isNodeConnected ? 0.2 : 1;

            return (
              <g key={id}>
                {/* 호버 시 연결된 노드 글로우 */}
                {isHovering && connectedNodes.has(id) && (
                  <rect
                    x={pos.x - 3}
                    y={pos.y - 3}
                    width={nodeW + 6}
                    height={pos.h + 6}
                    rx={5}
                    fill="none"
                    stroke={pos.color}
                    strokeWidth={1.5}
                    strokeOpacity={0.5}
                  >
                    <animate
                      attributeName="stroke-opacity"
                      values="0.3;0.7;0.3"
                      dur="1.5s"
                      repeatCount="indefinite"
                    />
                  </rect>
                )}
                <rect
                  x={pos.x}
                  y={pos.y}
                  width={nodeW}
                  height={pos.h}
                  rx={3}
                  fill={pos.color}
                  opacity={nodeOpacity}
                  style={{ transition: "opacity 0.25s ease" }}
                />
                {/* 넓은 호버/터치 영역 */}
                <rect
                  x={pos.x - 16}
                  y={pos.y - 4}
                  width={nodeW + 32}
                  height={pos.h + 8}
                  fill="transparent"
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => handleNodeHover(id)}
                  onTouchStart={() => handleNodeHover(id)}
                  onClick={isConflict && cIdx >= 0 ? () => setPopupIdx(cIdx) : undefined}
                />
              </g>
            );
          })}

          {/* 라벨 */}
          {Array.from(nodePositions.entries()).map(([id, pos]) => {
            const isConflict = pos.category === "conflict";
            const isImpact = pos.category === "impact";
            const idx = conflictIdxMap.get(id) ?? -1;
            const isNodeConnected = !isHovering || connectedNodes.has(id);

            const labelText = isConflict
              ? NUM_LABELS[idx] ?? ""
              : pos.label;

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
                fill={isConflict ? pos.color : isDark ? "rgba(156,163,175,0.9)" : "rgba(55,65,81,0.9)"}
                fontSize={sizeClass === "lg" ? 13 : sizeClass === "md" ? 12 : effectiveWidth < 380 ? 9 : 11}
                fontWeight={isHovering && isNodeConnected ? 700 : 600}
                opacity={isHovering && !isNodeConnected ? 0.25 : 1}
                style={{ transition: "opacity 0.25s ease, font-weight 0.25s ease" }}
              >
                {labelText}
              </text>
            );
          })}
        </svg>
      </div>

      {/* 분쟁 이슈 버튼 목록 */}
      <div className="px-3 pb-2 flex flex-wrap gap-1.5" style={{ opacity: visible ? 1 : 0, transition: "opacity 0.25s ease-in-out" }}>
        {conflictNodes.map((node, idx) => {
          const issue = conflictIssues?.[idx];
          const flags = issue?.countryCodes?.slice(0, 2).map(getFlag).join("") ?? "";
          const shortTitle = node.label.length > 12 ? node.label.slice(0, 12) + "…" : node.label;
          const isActive = hoveredNodeId === node.id;
          return (
            <button
              key={node.id}
              onMouseEnter={() => handleNodeHover(node.id)}
              onMouseLeave={() => setHoveredNodeId(null)}
              onTouchStart={() => handleNodeHover(node.id)}
              onClick={(e) => { e.stopPropagation(); setPopupIdx(idx); }}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] font-medium transition-colors",
                isActive
                  ? "bg-red-500/25 border-red-500/40 text-red-300"
                  : "bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20"
              )}
            >
              <span className="font-bold">{NUM_LABELS[idx]}</span>
              {flags && <span className="text-xs">{flags}</span>}
              <span className="truncate max-w-[140px]">{shortTitle}</span>
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
          <div className="fixed bottom-[60px] left-0 right-0 z-50 rounded-t-2xl border-t border-border bg-card px-5 py-4 shadow-2xl animate-in slide-in-from-bottom duration-200 max-w-lg mx-auto">
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
