"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useTradeFlow } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getFlag, getCountryName } from "@/lib/countries";
import {
  GitBranch,
  ChevronDown,
  ChevronUp,
  Loader2,
  Lock,
  Info,
} from "lucide-react";
import { SectionHeader } from "./SectionHeader";
import dynamic from "next/dynamic";

const BarChart = dynamic(
  () => import("recharts").then((m) => m.BarChart),
  { ssr: false },
);
const Bar = dynamic(
  () => import("recharts").then((m) => m.Bar),
  { ssr: false },
);
const XAxis = dynamic(
  () => import("recharts").then((m) => m.XAxis),
  { ssr: false },
);
const YAxis = dynamic(
  () => import("recharts").then((m) => m.YAxis),
  { ssr: false },
);
const ResponsiveContainer = dynamic(
  () => import("recharts").then((m) => m.ResponsiveContainer),
  { ssr: false },
);
const Tooltip = dynamic(
  () => import("recharts").then((m) => m.Tooltip),
  { ssr: false },
);
const Legend = dynamic(
  () => import("recharts").then((m) => m.Legend),
  { ssr: false },
);

interface PartnerFlow {
  code: string;
  name: string;
  flag: string;
  export: number;
  import: number;
  total: number;
}

export function TradeFlowSankey() {
  const lang = useAppStore((s) => s.lang);
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading, isError, error } = useTradeFlow(expanded);

  const is403 = (error as any)?.status === 403;

  // 데이터를 파트너별 export/import 쌍으로 변환
  const partnerFlows: PartnerFlow[] = [];
  if (data) {
    const home = data.home_country;
    const exportSuffix = "_EXP";
    const importSuffix = "_IMP";

    const exportMap: Record<string, number> = {};
    const importMap: Record<string, number> = {};

    for (const link of data.links) {
      // source=KR_EXP target=US → export
      if (link.source.endsWith(exportSuffix)) {
        // This is an export from home to target
        // Actually: source=KR_EXP, target=partner
        exportMap[link.target] = (exportMap[link.target] || 0) + link.value;
      }
      // source=US_EXP target=KR_IMP → import
      if (link.target.endsWith(importSuffix)) {
        // partner exports to home = our import
        const partner = link.source;
        importMap[partner] = (importMap[partner] || 0) + link.value;
      }
      // Fallback for non-suffixed data (old format)
      if (
        !link.source.endsWith(exportSuffix) &&
        !link.target.endsWith(importSuffix)
      ) {
        if (link.source === home) {
          exportMap[link.target] = (exportMap[link.target] || 0) + link.value;
        } else if (link.target === home) {
          importMap[link.source] = (importMap[link.source] || 0) + link.value;
        }
      }
    }

    const allPartners = new Set([
      ...Object.keys(exportMap),
      ...Object.keys(importMap),
    ]);
    for (const p of allPartners) {
      const exp = exportMap[p] || 0;
      const imp = importMap[p] || 0;
      const fullName = getCountryName(p, lang);
      partnerFlows.push({
        code: p,
        name: fullName.length > 4 ? fullName.slice(0, 4) : fullName,
        flag: getFlag(p),
        export: Math.round(exp),
        import: Math.round(imp),
        total: Math.round(exp + imp),
      });
    }
    partnerFlows.sort((a, b) => b.total - a.total);
  }

  const topFlows = partnerFlows.slice(0, 8);

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
              ? lang === "ko"
                ? "접기"
                : "Collapse"
              : lang === "ko"
                ? "교역 흐름 시각화 보기"
                : "View trade flow visualization"}
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        {expanded && (
          <div className="px-4 pb-4 space-y-3 border-t border-border/40">
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
                {lang === "ko"
                  ? "데이터를 불러올 수 없습니다"
                  : "Failed to load data"}
              </p>
            )}

            {topFlows.length > 0 && (
              <>
                {/* Stacked Bar Chart */}
                <div className="h-[240px] w-full mt-3">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={topFlows}
                      margin={{ top: 4, right: 8, bottom: 4, left: 0 }}
                    >
                      <XAxis
                        dataKey="name"
                        tick={{ fontSize: 9, fill: "#94a3b8" }}
                      />
                      <YAxis
                        tick={{ fontSize: 9, fill: "#94a3b8" }}
                        tickFormatter={(v: number) =>
                          v >= 1000 ? `$${(v / 1000).toFixed(0)}B` : `$${v}M`
                        }
                      />
                      <Tooltip
                        contentStyle={{
                          background: "#1e293b",
                          border: "none",
                          borderRadius: "8px",
                          fontSize: 11,
                          color: "#e2e8f0",
                        }}
                        formatter={(value: any, name: any) => [
                          value >= 1000
                            ? `$${(value / 1000).toFixed(1)}B`
                            : `$${value}M`,
                          name === "export"
                            ? lang === "ko"
                              ? "수출"
                              : "Export"
                            : lang === "ko"
                              ? "수입"
                              : "Import",
                        ]}
                      />
                      <Legend
                        iconType="circle"
                        iconSize={6}
                        formatter={(value: any) =>
                          value === "export"
                            ? lang === "ko"
                              ? "수출"
                              : "Export"
                            : lang === "ko"
                              ? "수입"
                              : "Import"
                        }
                        wrapperStyle={{ fontSize: 10 }}
                      />
                      <Bar
                        dataKey="export"
                        stackId="a"
                        fill="#3b82f6"
                        radius={[0, 0, 0, 0]}
                      />
                      <Bar
                        dataKey="import"
                        stackId="a"
                        fill="#f97316"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Top Partners List */}
                <div className="space-y-1">
                  {topFlows.slice(0, 5).map((p, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 rounded-lg bg-muted/15 px-3 py-1.5 fade-in-up"
                      style={{ animationDelay: `${i * 40}ms` }}
                    >
                      <span className="text-sm">{p.flag}</span>
                      <span className="text-[10px] font-medium flex-1">
                        {getCountryName(p.code, lang)}
                      </span>
                      <div className="flex items-center gap-3 text-[9px] tabular-nums">
                        <span className="text-blue-400">
                          ↑{" "}
                          {p.export >= 1000
                            ? `$${(p.export / 1000).toFixed(1)}B`
                            : `$${p.export}M`}
                        </span>
                        <span className="text-orange-400">
                          ↓{" "}
                          {p.import >= 1000
                            ? `$${(p.import / 1000).toFixed(1)}B`
                            : `$${p.import}M`}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Footer */}
                <div className="flex items-start gap-1.5 text-[9px] text-muted-foreground/60 px-1 pt-2 border-t border-border/30">
                  <Info className="h-3 w-3 mt-0.5 shrink-0" />
                  <span>
                    {lang === "ko"
                      ? "데이터: UN Comtrade / World Bank. 실제 교역 데이터 기반이며 투자 자문이 아닙니다."
                      : "Data: UN Comtrade / World Bank. Based on actual trade data, not investment advice."}
                  </span>
                </div>
              </>
            )}

            {data && partnerFlows.length === 0 && (
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
