"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useTradeFlow } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getFlag, getCountryName } from "@/lib/countries";
import Link from "next/link";
import {
  GitBranch,
  ChevronDown,
  ChevronUp,
  Loader2,
  Lock,
  Info,
  AlertTriangle,
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

/* ── Demo data for Free users (403) ── */
const DEMO_TRADE_FLOW = {
  top_exports: [
    { partner_ko: "미국", partner_en: "United States", value_pct: 28, items_ko: "반도체, 자동차, 전자기기", items_en: "Semiconductors, Vehicles, Electronics" },
    { partner_ko: "중국", partner_en: "China", value_pct: 24, items_ko: "디스플레이, 석유화학, 철강", items_en: "Displays, Petrochemicals, Steel" },
    { partner_ko: "일본", partner_en: "Japan", value_pct: 12, items_ko: "반도체, 철강, 석유제품", items_en: "Semiconductors, Steel, Petroleum" },
  ],
  top_imports: [
    { partner_ko: "중국", partner_en: "China", value_pct: 32, items_ko: "전자부품, 의류, 기계류", items_en: "Electronics, Apparel, Machinery" },
    { partner_ko: "미국", partner_en: "United States", value_pct: 18, items_ko: "에너지, 항공기, 농산물", items_en: "Energy, Aircraft, Agriculture" },
    { partner_ko: "사우디", partner_en: "Saudi Arabia", value_pct: 14, items_ko: "원유, 석유화학", items_en: "Crude Oil, Petrochemicals" },
  ],
  risk_partners: [
    { partner_ko: "러시아", partner_en: "Russia", risk: "high" as const, reason_ko: "에너지 의존 + 제재 리스크", reason_en: "Energy dependency + sanctions risk" },
    { partner_ko: "대만", partner_en: "Taiwan", risk: "medium" as const, reason_ko: "반도체 공급망 집중", reason_en: "Semiconductor supply chain concentration" },
  ],
};

function buildDemoFlows(lang: "ko" | "en"): PartnerFlow[] {
  const map: Record<string, { exp: number; imp: number }> = {};
  for (const e of DEMO_TRADE_FLOW.top_exports) {
    const name = lang === "ko" ? e.partner_ko : e.partner_en;
    if (!map[name]) map[name] = { exp: 0, imp: 0 };
    map[name].exp = e.value_pct * 100; // scale for chart display
  }
  for (const i of DEMO_TRADE_FLOW.top_imports) {
    const name = lang === "ko" ? i.partner_ko : i.partner_en;
    if (!map[name]) map[name] = { exp: 0, imp: 0 };
    map[name].imp = i.value_pct * 100;
  }
  return Object.entries(map)
    .map(([name, v]) => ({
      code: name,
      name: name.length > 4 ? name.slice(0, 4) : name,
      flag: "",
      export: v.exp,
      import: v.imp,
      total: v.exp + v.imp,
    }))
    .sort((a, b) => b.total - a.total);
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
        exportMap[link.target] = (exportMap[link.target] || 0) + link.value;
      }
      // source=US_EXP target=KR_IMP → import
      if (link.target.endsWith(importSuffix)) {
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
  const demoFlows = buildDemoFlows(lang);

  /* ── Shared chart + list renderer ── */
  function renderChart(flows: PartnerFlow[]) {
    return (
      <>
        {/* Stacked Bar Chart */}
        <div className="h-[240px] w-full mt-3">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={flows}
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
                    ? t(lang, "dash_trade_export")
                    : t(lang, "dash_trade_import"),
                ]}
              />
              <Legend
                iconType="circle"
                iconSize={6}
                formatter={(value: any) =>
                  value === "export"
                    ? t(lang, "dash_trade_export")
                    : t(lang, "dash_trade_import")
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
          {flows.slice(0, 5).map((p, i) => (
            <div
              key={i}
              className="flex items-center gap-2 rounded-lg bg-muted/15 px-3 py-1.5 fade-in-up"
              style={{ animationDelay: `${i * 40}ms` }}
            >
              {p.flag && <span className="text-sm">{p.flag}</span>}
              <span className="text-[10px] font-medium flex-1">
                {p.code}
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

        {/* Risk Partners (demo only) */}
        {flows === demoFlows && (
          <div className="space-y-1 mt-2">
            <span className="text-[9px] font-medium text-muted-foreground/60">
              {lang === "ko" ? "리스크 파트너" : "Risk Partners"}
            </span>
            {DEMO_TRADE_FLOW.risk_partners.map((rp, i) => (
              <div
                key={i}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-1.5",
                  rp.risk === "high" ? "bg-red-500/10" : "bg-amber-500/10",
                )}
              >
                <AlertTriangle className={cn("h-3 w-3 shrink-0", rp.risk === "high" ? "text-red-400" : "text-amber-400")} />
                <span className="text-[10px] font-medium flex-1">
                  {lang === "ko" ? rp.partner_ko : rp.partner_en}
                </span>
                <span className={cn(
                  "text-[8px] font-bold px-1.5 py-0.5 rounded-full",
                  rp.risk === "high" ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400",
                )}>
                  {rp.risk.toUpperCase()}
                </span>
                <span className="text-[9px] text-muted-foreground truncate max-w-[140px]">
                  {lang === "ko" ? rp.reason_ko : rp.reason_en}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-start gap-1.5 text-[9px] text-muted-foreground/60 px-1 pt-2 border-t border-border/30">
          <Info className="h-3 w-3 mt-0.5 shrink-0" />
          <span>
            {t(lang, "trade_data_source")}
          </span>
        </div>
      </>
    );
  }

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
              ? t(lang, "trade_collapse")
              : t(lang, "trade_expand")}
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

            {/* 403: Demo chart with blur + overlay */}
            {is403 && (
              <div className="relative">
                <div className="blur-[3px] opacity-60 pointer-events-none select-none">
                  {renderChart(demoFlows)}
                </div>
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/40 z-10">
                  <Lock className="h-6 w-6 text-muted-foreground mb-2" />
                  <p className="text-xs font-medium text-foreground/80 mb-2">
                    {lang === "ko"
                      ? "Pro+ 플랜에서 이용 가능합니다"
                      : "Available on Pro+ plan"}
                  </p>
                  <Link
                    href="/upgrade?source=trade_flow"
                    className="inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[10px] font-bold text-white transition-transform hover:scale-105"
                    style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
                  >
                    {t(lang, "dash_unlock_pro_plus")}
                  </Link>
                </div>
              </div>
            )}

            {isError && !is403 && (
              <p className="text-xs text-red-400 text-center py-4">
                {t(lang, "trade_load_error")}
              </p>
            )}

            {topFlows.length > 0 && renderChart(topFlows)}

            {data && partnerFlows.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">
                {t(lang, "trade_no_data")}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
