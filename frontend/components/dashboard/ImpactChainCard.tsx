"use client";

import { cn } from "@/lib/utils";

interface ImpactChainProps {
  event: string;
  marketImpact?: string | null;
  dailyLife?: string | null;
  timeline?: string | null;
  trustLevel?: string | null;
  trustDetail?: string | null;
  sensorContext?: string | null;
  lang: "ko" | "en";
}

const TRUST_STYLES: Record<string, { bg: string; text: string; label: string; labelEn: string }> = {
  confirmed: { bg: "bg-emerald-600/15", text: "text-emerald-600", label: "검증 완료", labelEn: "Confirmed" },
  verified: { bg: "bg-emerald-500/10", text: "text-emerald-500", label: "검증됨", labelEn: "Verified" },
  reported: { bg: "bg-blue-500/10", text: "text-blue-500", label: "보도됨", labelEn: "Reported" },
  unconfirmed: { bg: "bg-amber-500/10", text: "text-amber-500", label: "미확인", labelEn: "Unconfirmed" },
};

function ChainStep({ color, label, content }: { color: string; label: string; content: string }) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
        <div className="flex-1 w-px bg-border" />
      </div>
      <div className="pb-3 min-w-0">
        <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color }}>
          {label}
        </span>
        <p className="text-[11px] text-foreground/80 leading-relaxed mt-0.5">{content}</p>
      </div>
    </div>
  );
}

export function ImpactChainCard({
  event,
  marketImpact,
  dailyLife,
  timeline,
  trustLevel,
  trustDetail,
  sensorContext,
  lang,
}: ImpactChainProps) {
  if (!event) return null;

  const trust = trustLevel ? TRUST_STYLES[trustLevel] ?? TRUST_STYLES.unconfirmed : null;

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold text-foreground">
          {lang === "ko" ? "영향 경로" : "Impact Chain"}
        </span>
        {trust && (
          <span className={cn("text-[9px] font-medium px-1.5 py-0.5 rounded-full", trust.bg, trust.text)}>
            {lang === "ko" ? trust.label : trust.labelEn}
          </span>
        )}
      </div>

      <div className="ml-0.5">
        <ChainStep
          color="#EF4444"
          label={lang === "ko" ? "사건" : "EVENT"}
          content={event}
        />
        {marketImpact && (
          <ChainStep
            color="#F97316"
            label={lang === "ko" ? "시장" : "MARKET"}
            content={marketImpact}
          />
        )}
        {dailyLife && (
          <ChainStep
            color="#EAB308"
            label={lang === "ko" ? "생활" : "DAILY LIFE"}
            content={dailyLife}
          />
        )}
        {timeline && (
          <div className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className="h-2.5 w-2.5 rounded-full shrink-0 bg-muted-foreground/30" />
            </div>
            <div className="min-w-0">
              <span className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">
                {lang === "ko" ? "시기" : "WHEN"}
              </span>
              <p className="text-[11px] text-foreground/60 leading-relaxed mt-0.5">{timeline}</p>
            </div>
          </div>
        )}
      </div>

      {sensorContext && (
        <div className="mt-3 pt-2 border-t border-border/50">
          <p className="text-[9px] text-muted-foreground flex items-center gap-1">
            <span>🛰️</span>
            <span>{sensorContext}</span>
          </p>
        </div>
      )}
    </div>
  );
}
