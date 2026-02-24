"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { t, getTensionLevelLabel, type Lang } from "@/lib/i18n";

// 긴장도 레벨별 색상
const LEVEL_COLORS: Record<number, string> = {
  0: "#22c55e", // 안정 - green
  1: "#eab308", // 주의 - yellow
  2: "#f97316", // 경계 - orange
  3: "#ef4444", // 위기 - red
};

interface HistoryPoint {
  time: string;
  raw_score: number;
  tension_level: number;
  percentile_30d: number;
}

interface TensionHistoryChartProps {
  data: HistoryPoint[];
  countryCode: string;
  range: "7d" | "30d" | "90d";
  lang: Lang;
}

function formatDate(isoStr: string, range: "7d" | "30d" | "90d", lang: Lang) {
  const locale = lang === "en" ? "en-US" : "ko-KR";
  const d = new Date(isoStr);
  if (range === "7d") {
    return d.toLocaleString(locale, { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleString(locale, { month: "short", day: "numeric" });
}

interface TooltipPayloadItem {
  payload: HistoryPoint;
}

function CustomTooltip({
  active,
  payload,
  lang,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  lang: Lang;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const color = LEVEL_COLORS[d.tension_level] ?? "#6b7280";
  const label = getTensionLevelLabel(d.tension_level as 0 | 1 | 2 | 3, lang);
  const locale = lang === "en" ? "en-US" : "ko-KR";
  const scoreUnit = t(lang, "chart_tooltip_score_unit");
  const pctLabel = t(lang, "chart_tooltip_percentile");

  return (
    <div className="rounded-lg border border-border bg-card/95 backdrop-blur-sm px-3 py-2 text-xs shadow-lg">
      <p className="text-muted-foreground mb-1">{new Date(d.time).toLocaleString(locale)}</p>
      <p className="font-bold" style={{ color }}>
        {label} <span className="font-normal text-foreground">{d.raw_score.toFixed(1)}{scoreUnit}</span>
      </p>
      <p className="text-muted-foreground">{pctLabel} {d.percentile_30d.toFixed(0)}%</p>
    </div>
  );
}

export function TensionHistoryChart({ data, range, lang }: TensionHistoryChartProps) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-40 text-sm text-muted-foreground">
        {t(lang, "chart_no_data")}
      </div>
    );
  }

  // 가장 높은 tension_level 기준 선 색상
  const maxLevel = Math.max(...data.map((d) => d.tension_level)) as keyof typeof LEVEL_COLORS;
  const lineColor = LEVEL_COLORS[maxLevel] ?? "#6b7280";

  return (
    <div className="w-full overflow-hidden">
      <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />

          {/* 단계 경계선 */}
          <ReferenceLine y={25} stroke="#eab308" strokeDasharray="4 4" strokeOpacity={0.4} />
          <ReferenceLine y={50} stroke="#f97316" strokeDasharray="4 4" strokeOpacity={0.4} />
          <ReferenceLine y={75} stroke="#ef4444" strokeDasharray="4 4" strokeOpacity={0.4} />

          <XAxis
            dataKey="time"
            tickFormatter={(v) => formatDate(v, range, lang)}
            tick={{ fontSize: 9, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 9, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
            ticks={[0, 25, 50, 75, 100]}
          />
          <Tooltip content={<CustomTooltip lang={lang} />} />
          <Line
            type="monotone"
            dataKey="raw_score"
            stroke={lineColor}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: lineColor }}
            animationDuration={400}
          />
        </LineChart>
      </ResponsiveContainer>
      </div>

      {/* 레벨 범례 */}
      <div className="flex items-center justify-center gap-3 mt-3 mb-2">
        {([0, 1, 2, 3] as const).map((level) => (
          <span key={level} className="flex items-center gap-1 text-[9px] text-muted-foreground">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ background: LEVEL_COLORS[level] }}
            />
            {getTensionLevelLabel(level, lang)}
          </span>
        ))}
      </div>
    </div>
  );
}
