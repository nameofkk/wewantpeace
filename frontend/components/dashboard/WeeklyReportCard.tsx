"use client";

import { useAppStore } from "@/lib/store";
import { FileText, Clock } from "lucide-react";
import { SectionHeader } from "./SectionHeader";

export function WeeklyReportCard() {
  const lang = useAppStore((s) => s.lang);

  return (
    <div>
      <SectionHeader
        icon={<FileText className="h-3.5 w-3.5 text-cyan-400" />}
        titleKey="dash_weekly_report"
        descKey="dash_weekly_report_desc"
        badge={{ label: "Pro+", color: "bg-cyan-500/10 text-cyan-400" }}
      />
      <div className="rounded-xl border border-border bg-card fade-in-up overflow-hidden">
        <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
          <div className="h-10 w-10 rounded-full bg-cyan-500/10 flex items-center justify-center mb-3">
            <Clock className="h-5 w-5 text-cyan-400" />
          </div>
          <p className="text-sm font-medium text-foreground/80">
            {lang === "ko" ? "준비중" : "Coming Soon"}
          </p>
          <p className="text-[11px] text-muted-foreground mt-1">
            {lang === "ko"
              ? "주간 분쟁 모니터링 리포트가 곧 제공됩니다"
              : "Weekly conflict monitoring report coming soon"}
          </p>
        </div>
      </div>
    </div>
  );
}
