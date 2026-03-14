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
    loading: () => <div className="h-[200px] animate-pulse bg-muted/20 rounded" />,
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

export function ImpactFlowSankey({ data, isPro, lang }: Props) {
  // Transform data for nivo sankey format
  const sankeyData = {
    nodes: data.nodes.map((n) => ({
      id: n.id,
      label: n.label,
      color: n.color || CATEGORY_COLORS[n.category] || "#6b7280",
    })),
    links: data.links.map((l) => ({
      source: l.source,
      target: l.target,
      value: Math.max(1, l.value),
    })),
  };

  return (
    <div className="relative">
      <div className={cn("h-[200px]", !isPro && "after:absolute after:inset-0 after:bg-gradient-to-r after:from-transparent after:via-transparent after:to-background/80")}>
        <ResponsiveSankey
          data={sankeyData}
          margin={{ top: 8, right: 80, bottom: 8, left: 80 }}
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
          labelPadding={8}
          labelTextColor={{ from: "color", modifiers: [["brighter", 0.8]] }}
          label={(node: any) => node.label}
          nodeTooltip={() => null}
          linkTooltip={() => null}
          motionConfig="gentle"
          theme={{
            labels: { text: { fontSize: 9, fill: "rgba(156,163,175,0.8)" } },
          }}
        />
      </div>
      {!isPro && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <span className="text-[10px] text-muted-foreground/40 bg-background/60 px-3 py-1 rounded-full pointer-events-auto">
            {t(lang, "dash_pro_demo_flow" as TranslationKey)}
          </span>
        </div>
      )}
    </div>
  );
}
