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
import { type Lang } from "@/lib/i18n";

// KScore 구간별 색상 (0-10 스케일)
function kscoreColor(kscore: number): string {
  if (kscore >= 7.0) return "#ef4444"; // 적색 (위기)
  if (kscore >= 5.0) return "#f97316"; // 주황 (경계)
  if (kscore >= 3.0) return "#eab308"; // 노랑 (주의)
  return "#22c55e"; // 녹색 (정상)
}

interface KScorePoint {
  time: string;
  kscore: number;
}

interface KScoreHistoryChartProps {
  data: KScorePoint[];
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
  payload: KScorePoint;
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
  const color = kscoreColor(d.kscore);
  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <div className="rounded-lg border border-border bg-card/95 backdrop-blur-sm px-3 py-2 text-xs shadow-lg">
      <p className="text-muted-foreground mb-1">{new Date(d.time).toLocaleString(locale)}</p>
      <p className="font-bold" style={{ color }}>
        KScore <span className="font-normal text-foreground">{d.kscore.toFixed(1)}</span>
      </p>
    </div>
  );
}

export function KScoreHistoryChart({ data, range, lang }: KScoreHistoryChartProps) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">
        {lang === "ko" ? "데이터가 없습니다" : "No data available"}
      </div>
    );
  }

  // 최고 KScore 기준으로 선 색상 결정
  const maxKscore = Math.max(...data.map((d) => d.kscore));
  const lineColor = kscoreColor(maxKscore);

  return (
    <div className="w-full overflow-hidden">
      <div className="h-36">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />

            {/* KScore 구간 경계선 (0-10 스케일) */}
            <ReferenceLine y={3.0} stroke="#eab308" strokeDasharray="4 4" strokeOpacity={0.4} />
            <ReferenceLine y={5.0} stroke="#f97316" strokeDasharray="4 4" strokeOpacity={0.4} />
            <ReferenceLine y={7.0} stroke="#ef4444" strokeDasharray="4 4" strokeOpacity={0.4} />

            <XAxis
              dataKey="time"
              tickFormatter={(v) => formatDate(v, range, lang)}
              tick={{ fontSize: 9, fill: "#6b7280" }}
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[0, Math.max(10, maxKscore + 1)]}
              tick={{ fontSize: 9, fill: "#6b7280" }}
              axisLine={false}
              tickLine={false}
              ticks={[0, 3, 5, 7, 10]}
            />
            <Tooltip content={<CustomTooltip lang={lang} />} />
            <Line
              type="monotone"
              dataKey="kscore"
              stroke={lineColor}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: lineColor }}
              animationDuration={400}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 범례 (0-10 스케일) */}
      <div className="flex items-center justify-center gap-3 mt-1 mb-1">
        {[
          { label: lang === "ko" ? "정상" : "Normal",    color: "#22c55e", range: "< 3" },
          { label: lang === "ko" ? "주의" : "Watch",     color: "#eab308", range: "3~5" },
          { label: lang === "ko" ? "경계" : "Alert",     color: "#f97316", range: "5~7" },
          { label: lang === "ko" ? "위기" : "Crisis",    color: "#ef4444", range: "7+" },
        ].map(({ label, color, range: r }) => (
          <span key={r} className="flex items-center gap-1 text-[9px] text-muted-foreground">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: color }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
