"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useTradeFlow } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getFlag, getCountryName } from "@/lib/countries";
import { GitBranch, ChevronDown, ChevronUp, Loader2, Lock, Info } from "lucide-react";
import { SectionHeader } from "./SectionHeader";

// Nivo 컴포넌트는 dynamic import (SSR 불가)
import dynamic from "next/dynamic";
const ResponsiveSankey = dynamic(
  () => import("@nivo/sankey").then((m) => m.ResponsiveSankey),
  { ssr: false },
);

const FLOW_COLORS = [
  "#3b82f6", "#ef4444", "#f59e0b", "#10b981", "#8b5cf6",
  "#ec4899", "#06b6d4", "#f97316", "#14b8a6", "#a855f7",
];

export function TradeFlowSankey() {
  const lang = useAppStore((s) => s.lang);
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading, isError, error } = useTradeFlow(expanded);

  const is403 = (error as any)?.status === 403;

  // Nivo Sankey 데이터 변환
  const sankeyData = data
    ? {
        nodes: data.nodes.map((n) => ({
          id: n.id,
          label: `${getFlag(n.id)} ${getCountryName(n.id, lang)}`,
        })),
        links: data.links.map((l) => ({
          source: l.source,
          target: l.target,
          value: l.value,
        })),
      }
    : null;

  return (
    <div>
      <SectionHeader
        icon={<GitBranch className="h-3.5 w-3.5 text-cyan-400" />}
        titleKey="dash_trade_flow"
        descKey="dash_trade_flow_desc"
        badge={{ label: "Pro+", color: "bg-cyan-500/10 text-cyan-400" }}
      />
      <div className="rounded-xl border border-border bg-card fade-in-up overflow-hidden">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-card/80 transition-colors"
        >
          <span className="text-xs font-medium text-foreground/80">
            {expanded
              ? (lang === "ko" ? "접기" : "Collapse")
              : (lang === "ko" ? "교역 흐름 시각화 보기" : "View trade flow visualization")}
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        {expanded && (
          <div className="px-4 pb-4 space-y-3">
            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
              </div>
            )}

            {is403 && (
              <div className="text-center py-6 space-y-2">
                <Lock className="h-6 w-6 mx-auto text-muted-foreground" />
                <p className="text-xs text-muted-foreground">
                  {lang === "ko"
                    ? "교역 흐름 시각화는 Pro+ 전용입니다"
                    : "Trade flow visualization is Pro+ only"}
                </p>
              </div>
            )}

            {isError && !is403 && (
              <p className="text-xs text-red-400 text-center py-4">
                {lang === "ko" ? "데이터를 불러올 수 없습니다" : "Failed to load data"}
              </p>
            )}

            {sankeyData && sankeyData.links.length > 0 && (
              <>
                <div className="h-[320px] w-full">
                  <ResponsiveSankey
                    data={sankeyData}
                    margin={{ top: 10, right: 120, bottom: 10, left: 120 }}
                    align="justify"
                    colors={FLOW_COLORS}
                    nodeOpacity={1}
                    nodeHoverOthersOpacity={0.35}
                    nodeThickness={14}
                    nodeSpacing={16}
                    nodeBorderWidth={0}
                    nodeBorderRadius={3}
                    linkOpacity={0.4}
                    linkHoverOpacity={0.7}
                    linkContract={2}
                    enableLinkGradient
                    labelPosition="outside"
                    labelOrientation="horizontal"
                    labelPadding={8}
                    labelTextColor={{
                      from: "color",
                      modifiers: [["brighter", 0.8]],
                    }}
                    theme={{
                      text: { fontSize: 10, fill: "#94a3b8" },
                      tooltip: {
                        container: {
                          background: "#1e293b",
                          color: "#e2e8f0",
                          fontSize: 11,
                          borderRadius: "8px",
                          padding: "8px 12px",
                        },
                      },
                    }}
                  />
                </div>

                {/* 범례 */}
                <div className="flex flex-wrap gap-2 px-1">
                  {data!.links
                    .sort((a, b) => b.value - a.value)
                    .slice(0, 5)
                    .map((l, i) => (
                      <span
                        key={i}
                        className="text-[10px] text-muted-foreground bg-muted/30 rounded-full px-2 py-0.5"
                      >
                        {getFlag(l.source)} → {getFlag(l.target)}{" "}
                        <span className="font-mono">${l.value.toFixed(1)}M</span>
                      </span>
                    ))}
                </div>

                <div className="flex items-start gap-1.5 text-[10px] text-muted-foreground/60 px-1">
                  <Info className="h-3 w-3 mt-0.5 shrink-0" />
                  <span>
                    {lang === "ko"
                      ? "데이터: IMF IMTS / World Bank. AI 분석 기반 추정치이며 투자 자문이 아닙니다."
                      : "Data: IMF IMTS / World Bank. AI-powered estimate, not investment advice."}
                  </span>
                </div>
              </>
            )}

            {sankeyData && sankeyData.links.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">
                {lang === "ko"
                  ? "교역 데이터가 아직 없습니다"
                  : "No trade data available yet"}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
