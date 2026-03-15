"use client";

import React from "react";
import dynamic from "next/dynamic";
import type { RiskRadarOut } from "@/lib/api";
import { t, type TranslationKey } from "@/lib/i18n";
import { useAppStore } from "@/lib/store";

const RadarChart = dynamic(() => import("recharts").then((m) => m.RadarChart), { ssr: false });
const PolarGrid = dynamic(() => import("recharts").then((m) => m.PolarGrid), { ssr: false });
const PolarAngleAxis = dynamic(() => import("recharts").then((m) => m.PolarAngleAxis), { ssr: false });
const Radar = dynamic(() => import("recharts").then((m) => m.Radar), { ssr: false });
const ResponsiveContainer = dynamic(() => import("recharts").then((m) => m.ResponsiveContainer), { ssr: false });

interface Props {
  data: RiskRadarOut;
  lang: "ko" | "en";
}

export function RiskRadar({ data, lang }: Props) {
  const isDark = useAppStore((s) => s.theme) === "dark";
  const chartData = data.axes.map((a) => ({
    axis: lang === "ko" ? a.label_ko : a.label_en,
    current: a.value,
    previous: a.prev_value,
  }));

  const trendKey = `dash_radar_${data.overall_trend}` as TranslationKey;
  const trendColor =
    data.overall_trend === "deteriorating"
      ? "text-red-400"
      : data.overall_trend === "improving"
        ? "text-emerald-400"
        : "text-muted-foreground";

  return (
    <div className="flex flex-col items-center">
      <div className="w-[130px] h-[130px]">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={chartData} cx="50%" cy="50%" outerRadius="70%">
            <PolarGrid stroke={isDark ? "rgba(156,163,175,0.15)" : "rgba(100,116,139,0.2)"} />
            <PolarAngleAxis
              dataKey="axis"
              tick={{ fontSize: 7, fill: isDark ? "rgba(156,163,175,0.7)" : "rgba(51,65,85,0.8)" }}
            />
            <Radar
              name="prev"
              dataKey="previous"
              stroke={isDark ? "rgba(156,163,175,0.4)" : "rgba(100,116,139,0.5)"}
              fill="none"
              strokeDasharray="4 3"
              strokeWidth={1}
            />
            <Radar
              name="current"
              dataKey="current"
              stroke={isDark ? "rgba(239,68,68,0.6)" : "rgba(220,38,38,0.7)"}
              fill={isDark ? "rgba(239,68,68,0.15)" : "rgba(239,68,68,0.12)"}
              strokeWidth={1.5}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex items-center gap-1 mt-0.5">
        <span className="text-[7px] text-muted-foreground/50">
          {t(lang, "dash_radar_vs_prev" as TranslationKey)}
        </span>
        <span className={`text-[8px] font-bold ${trendColor}`}>
          {t(lang, trendKey)}
        </span>
      </div>
    </div>
  );
}
