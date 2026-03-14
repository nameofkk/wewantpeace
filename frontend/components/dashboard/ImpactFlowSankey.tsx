"use client";

import React from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import { t, type TranslationKey } from "@/lib/i18n";
import type { ImpactFlowOut } from "@/lib/api";

const ResponsiveSankey = dynamic(
  () => import("@nivo/sankey").then((m) => m.ResponsiveSankey),
  {
    ssr: false,
    loading: () => <div className="h-[220px] animate-pulse bg-muted/20 rounded" />,
  }
);

interface Props {
  data: ImpactFlowOut;
  isPro: boolean;
  lang: "ko" | "en";
}

const CATEGORY_COLORS: Record<string, string> = {
  conflict: "#dc2626",
  commodity: "#f59e0b",
  impact: "#3b82f6",
};

/** Truncate label based on category to prevent overflow */
function truncateLabel(label: string, category: string): string {
  const maxLen = category === "conflict" ? 10 : category === "impact" ? 8 : 6;
  if (label.length <= maxLen) return label;
  return label.slice(0, maxLen) + "…";
}

export function ImpactFlowSankey({ data, isPro, lang }: Props) {
  // Build category lookup for truncation
  const categoryMap = new Map(data.nodes.map((n) => [n.id, n.category]));

  const sankeyData = {
    nodes: data.nodes.map((n) => ({
      id: n.id,
      label: n.label,
      shortLabel: truncateLabel(n.label, n.category),
      color: n.color || CATEGORY_COLORS[n.category] || "#6b7280",
      category: n.category,
    })),
    links: data.links.map((l) => ({
      source: l.source,
      target: l.target,
      value: Math.max(1, l.value),
    })),
  };

  return (
    <div className="relative">
      <div className={cn("h-[220px]", !isPro && "after:absolute after:inset-0 after:bg-gradient-to-r after:from-transparent after:via-transparent after:to-background/80")}>
        <ResponsiveSankey
          data={sankeyData}
          margin={{ top: 8, right: 90, bottom: 8, left: 90 }}
          align="justify"
          colors={(node: any) => node.color || "#6b7280"}
          nodeOpacity={1}
          nodeHoverOpacity={1}
          nodeThickness={12}
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
          labelPadding={6}
          labelTextColor={{ from: "color", modifiers: [["brighter", 0.8]] }}
          label={(node: any) => node.shortLabel ?? truncateLabel(node.label || node.id, categoryMap.get(node.id) || "commodity")}
          nodeTooltip={({ node }: any) => (
            <div className="bg-popover text-popover-foreground border border-border rounded-lg px-3 py-2 shadow-lg max-w-[200px]">
              <p className="text-[11px] font-medium leading-snug">{node.label || node.id}</p>
              <p className="text-[9px] text-muted-foreground mt-0.5 capitalize">{node.category}</p>
            </div>
          )}
          linkTooltip={() => null}
          motionConfig="gentle"
          theme={{
            labels: { text: { fontSize: 8, fill: "rgba(156,163,175,0.9)", fontWeight: 500 } },
          }}
        />
      </div>
      {/* Category legend */}
      <div className="flex items-center justify-center gap-4 px-4 pb-2 pt-0.5">
        {[
          { key: "conflict", color: "#dc2626", label: lang === "ko" ? "분쟁" : "Conflict" },
          { key: "commodity", color: "#f59e0b", label: lang === "ko" ? "산업/원자재" : "Industry" },
          { key: "impact", color: "#3b82f6", label: lang === "ko" ? "생활 영향" : "Daily Cost" },
        ].map((c) => (
          <span key={c.key} className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: c.color }} />
            <span className="text-[8px] text-muted-foreground">{c.label}</span>
          </span>
        ))}
      </div>
      {!isPro && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
          <span className="text-[10px] text-muted-foreground/40 bg-background/60 px-3 py-1 rounded-full pointer-events-auto">
            {t(lang, "dash_pro_demo_flow" as TranslationKey)}
          </span>
        </div>
      )}
    </div>
  );
}
