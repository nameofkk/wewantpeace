"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, AlertTriangle, Loader2 } from "lucide-react";
import { COUNTRY_MAP, getCountryName } from "@/lib/countries";
import { cn, stripTitlePrefix, isJunkTitle, buildSmartTitle } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { API_BASE } from "@/lib/api";
import { issueDetailPath } from "@/lib/toss-nav";
import Link from "next/link";

interface ClusterOut {
  id: string;
  topic: string;
  title: string;
  title_ko: string | null;
  country_code: string | null;
  severity: number;
  event_count: number;
  kscore: number;
  first_event_at: string;
  last_event_at: string;
}

function getSeverityColor(severity: number): string {
  if (severity >= 80) return "#991b1b";
  if (severity >= 60) return "#ef4444";
  if (severity >= 40) return "#f97316";
  if (severity >= 20) return "#f59e0b";
  return "#22c55e";
}

export default function CountryIssuesInner() {
  const searchParams = useSearchParams();
  const code = searchParams.get("code") || "";
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const countryInfo = COUNTRY_MAP[code as keyof typeof COUNTRY_MAP];
  const displayName = lang === "en"
    ? (() => { try { return new Intl.DisplayNames(["en"], { type: "region" }).of(code) || (countryInfo?.name ?? code); } catch { return countryInfo?.name ?? code; } })()
    : (countryInfo?.name ?? code);
  const countryName = countryInfo ? `${countryInfo.flag} ${displayName}` : displayName;

  const { data: clusters, isLoading, isError } = useQuery<ClusterOut[]>({
    queryKey: ["issues", "country", code],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/issues?country_code=${code}&limit=100`);
      if (!res.ok) throw new Error("Failed to fetch");
      return res.json();
    },
    enabled: !!code,
    staleTime: 2 * 60 * 1000,
  });

  if (!code) {
    return <div className="flex items-center justify-center min-h-screen text-muted-foreground">국가 코드가 없습니다.</div>;
  }

  return (
    <div className="flex flex-col min-h-screen bg-background">
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <button onClick={() => router.back()} className="text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h1 className="text-base font-bold truncate">{countryName}</h1>
      </div>

      <div className="flex-1 px-4 py-4 space-y-3">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        )}

        {isError && (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <AlertTriangle className="h-6 w-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{t(lang, "error_generic")}</p>
          </div>
        )}

        {clusters && clusters.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-12">{t(lang, "tension_no_events")}</p>
        )}

        {clusters?.map((c) => {
          const raw = lang === "en" ? c.title : (c.title_ko ?? c.title);
          const title = isJunkTitle(raw) ? buildSmartTitle(raw, c.topic, lang, getCountryName, c.country_code) : stripTitlePrefix(raw);
          const color = getSeverityColor(c.severity);

          return (
            <Link key={c.id} href={issueDetailPath(c.id)}>
              <div className="rounded-xl border border-border bg-card p-4 hover:bg-card/80 transition-colors">
                <div className="flex items-start gap-3">
                  <div className="h-2 w-2 mt-1.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium line-clamp-2">{title}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] text-muted-foreground">{c.event_count} {t(lang, "issue_events")}</span>
                      <span className="text-[10px] text-muted-foreground">K{c.kscore.toFixed(1)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
