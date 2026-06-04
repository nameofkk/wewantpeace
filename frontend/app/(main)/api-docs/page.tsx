"use client";

import { useState } from "react";
import { ArrowLeft, Copy, Check, ExternalLink, Lock, Zap, Globe, Code } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";

const API_BASE_URL = "https://backend-production-3af7.up.railway.app";

interface EndpointParam {
  name: string;
  type: string;
  required: boolean;
  descKo: string;
  descEn: string;
}

interface Endpoint {
  method: string;
  path: string;
  descKo: string;
  descEn: string;
  params: EndpointParam[];
  exampleResponse: string;
}

const ENDPOINTS: Endpoint[] = [
  {
    method: "GET",
    path: "/public/trending/top",
    descKo: "KScore 기준 상위 20개 트렌딩 이슈를 반환합니다.",
    descEn: "Returns the top 20 trending issues ranked by KScore.",
    params: [],
    exampleResponse: JSON.stringify(
      {
        count: 20,
        data: [
          {
            id: "a1b2c3d4-...",
            title: "Ukraine-Russia border tensions escalate",
            title_ko: "[UA] 우크라이나-러시아 국경 긴장 고조",
            severity: 4,
            kscore: 8.72,
            event_count: 47,
            country_code: "UA",
            topic: "conflict",
            lat: 48.38,
            lon: 35.04,
            last_event_at: "2026-03-09T12:00:00+00:00",
            image_url: null,
          },
        ],
      },
      null,
      2
    ),
  },
  {
    method: "GET",
    path: "/public/tension/all",
    descKo: "모든 국가의 최신 긴장도 점수를 반환합니다.",
    descEn: "Returns the latest tension scores for all monitored countries.",
    params: [],
    exampleResponse: JSON.stringify(
      {
        count: 180,
        data: [
          {
            country_code: "UA",
            raw_score: 82.5,
            tension_level: 4,
            event_score: 45.2,
            accel_score: 12.3,
            spillover_score: 8.1,
            percentile_30d: 95.0,
            updated_at: "2026-03-09T12:00:00+00:00",
          },
        ],
      },
      null,
      2
    ),
  },
  {
    method: "GET",
    path: "/public/tension/{country_code}",
    descKo: "특정 국가의 최신 긴장도와 최근 30일 히스토리를 반환합니다.",
    descEn: "Returns the latest tension and 30-day history for a specific country.",
    params: [
      {
        name: "country_code",
        type: "string (path)",
        required: true,
        descKo: "ISO 3166-1 alpha-2 국가 코드 (예: UA, KR, US)",
        descEn: "ISO 3166-1 alpha-2 country code (e.g., UA, KR, US)",
      },
    ],
    exampleResponse: JSON.stringify(
      {
        country_code: "UA",
        latest: {
          raw_score: 82.5,
          tension_level: 4,
          event_score: 45.2,
          accel_score: 12.3,
          spillover_score: 8.1,
          percentile_30d: 95.0,
          updated_at: "2026-03-09T12:00:00+00:00",
        },
        history: [
          {
            time: "2026-02-07T12:00:00+00:00",
            raw_score: 71.3,
            tension_level: 3,
          },
        ],
      },
      null,
      2
    ),
  },
  {
    method: "GET",
    path: "/public/countries",
    descKo: "데이터가 존재하는 모든 국가 코드 목록을 반환합니다.",
    descEn: "Returns a list of all country codes that have available data.",
    params: [],
    exampleResponse: JSON.stringify(
      {
        count: 180,
        data: ["AF", "AL", "AM", "AO", "AR", "AU", "AZ", "BA", "BD", "..."],
      },
      null,
      2
    ),
  },
  {
    method: "GET",
    path: "/public/stats",
    descKo: "플랫폼 전체 통계를 반환합니다. (총 이벤트 수, 활성 클러스터 수 등)",
    descEn: "Returns overall platform statistics (total events, active clusters, etc.).",
    params: [],
    exampleResponse: JSON.stringify(
      {
        total_events: 154320,
        events_24h: 1247,
        active_clusters: 342,
        monitored_countries: 180,
        new_clusters_7d: 89,
        updated_at: "2026-03-09T12:00:00+00:00",
      },
      null,
      2
    ),
  },
  {
    method: "GET",
    path: "/public/weekly-summary",
    descKo: "최근 7일간의 주간 요약을 반환합니다. (상위 이슈, 긴장도, 통계)",
    descEn: "Returns a weekly summary for the past 7 days (top issues, tension, stats).",
    params: [],
    exampleResponse: JSON.stringify(
      {
        period: {
          start: "2026-03-02T12:00:00+00:00",
          end: "2026-03-09T12:00:00+00:00",
        },
        top_issues: [
          {
            id: "a1b2c3d4-...",
            title: "...",
            title_ko: "...",
            severity: 4,
            kscore: 8.72,
            event_count: 47,
            country_code: "UA",
            topic: "conflict",
          },
        ],
        top_tension: [
          { country_code: "UA", raw_score: 82.5, tension_level: 4 },
        ],
        stats: {
          total_events: 1247,
          new_clusters: 89,
          crisis_countries: 5,
        },
        prev_stats: {
          total_events: 1102,
          new_clusters: 76,
        },
      },
      null,
      2
    ),
  },
];

function MethodBadge({ method }: { method: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider",
        method === "GET"
          ? "bg-green-500/15 text-green-400 border border-green-500/30"
          : method === "POST"
          ? "bg-blue-500/15 text-blue-400 border border-blue-500/30"
          : "bg-muted text-muted-foreground border border-border"
      )}
    >
      {method}
    </span>
  );
}

function CopyButton({ text, lang }: { text: string; lang: Lang }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 rounded-md px-2 py-1 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
    >
      {copied ? (
        <>
          <Check className="h-3 w-3 text-green-400" />
          <span className="text-green-400">{t(lang, "api_docs_copied")}</span>
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" />
          <span>{t(lang, "api_docs_copy")}</span>
        </>
      )}
    </button>
  );
}

function EndpointCard({
  endpoint,
  lang,
}: {
  endpoint: Endpoint;
  lang: Lang;
}) {
  const [expanded, setExpanded] = useState(false);
  const curlCmd = `curl -s "${API_BASE_URL}${endpoint.path.replace("{country_code}", "UA")}" | python3 -m json.tool`;

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/30 transition-colors"
      >
        <MethodBadge method={endpoint.method} />
        <code className="flex-1 text-sm font-mono text-foreground break-all">
          {endpoint.path}
        </code>
        <span
          className={cn(
            "text-muted-foreground transition-transform text-xs",
            expanded && "rotate-180"
          )}
        >
          ▼
        </span>
      </button>

      {/* Description */}
      <div className="px-4 pb-3 -mt-1">
        <p className="text-[12px] text-muted-foreground">
          {lang === "ko" ? endpoint.descKo : endpoint.descEn}
        </p>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border">
          {/* Parameters */}
          {endpoint.params.length > 0 && (
            <div className="px-4 py-3 border-b border-border">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                {t(lang, "api_docs_params")}
              </h4>
              <div className="space-y-2">
                {endpoint.params.map((p) => (
                  <div key={p.name} className="flex items-start gap-2">
                    <code className="text-[12px] font-mono text-primary bg-primary/10 rounded px-1.5 py-0.5 shrink-0">
                      {p.name}
                    </code>
                    <div>
                      <span className="text-[11px] text-muted-foreground">
                        {p.type}
                        {p.required && (
                          <span className="ml-1 text-red-400">*required</span>
                        )}
                      </span>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {lang === "ko" ? p.descKo : p.descEn}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {endpoint.params.length === 0 && (
            <div className="px-4 py-3 border-b border-border">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                {t(lang, "api_docs_params")}
              </h4>
              <p className="text-[11px] text-muted-foreground">
                {t(lang, "api_docs_no_params")}
              </p>
            </div>
          )}

          {/* curl example */}
          <div className="px-4 py-3 border-b border-border">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {t(lang, "api_docs_curl")}
              </h4>
              <CopyButton text={curlCmd} lang={lang} />
            </div>
            <div className="rounded-lg bg-[#0d1117] border border-[#30363d] p-3 overflow-x-auto">
              <pre className="text-[11px] font-mono text-[#c9d1d9] whitespace-pre-wrap break-all">
                <span className="text-[#7ee787]">$</span> {curlCmd}
              </pre>
            </div>
          </div>

          {/* Response example */}
          <div className="px-4 py-3">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {t(lang, "api_docs_response")}
              </h4>
              <CopyButton text={endpoint.exampleResponse} lang={lang} />
            </div>
            <div className="rounded-lg bg-[#0d1117] border border-[#30363d] p-3 overflow-x-auto max-h-80 overflow-y-auto">
              <pre className="text-[11px] font-mono text-[#c9d1d9] whitespace-pre">
                {endpoint.exampleResponse}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ApiDocsPage() {
  const { lang } = useAppStore();

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <Link
          href="/settings"
          className="rounded-full p-1.5 hover:bg-muted transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex items-center gap-2">
          <Code className="h-4 w-4 text-primary" />
          <h1 className="text-sm font-bold">{t(lang, "api_docs_title")}</h1>
        </div>
      </div>

      <div className="mx-auto max-w-2xl px-4 py-6 space-y-6">
        {/* Title section */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5">
            <Globe className="h-3.5 w-3.5 text-primary" />
            <span className="text-xs font-semibold text-primary">
              Public API v1
            </span>
          </div>
          <h2 className="text-xl font-bold">{t(lang, "api_docs_title")}</h2>
          <p className="text-sm text-muted-foreground">
            {t(lang, "api_docs_subtitle")}
          </p>
        </div>

        {/* Base URL */}
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            {t(lang, "api_docs_base_url")}
          </h3>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded-lg bg-[#0d1117] border border-[#30363d] px-3 py-2 text-sm font-mono text-[#c9d1d9] select-all">
              {API_BASE_URL}
            </code>
            <CopyButton text={API_BASE_URL} lang={lang} />
          </div>
        </div>

        {/* Auth & Rate limit */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Authentication */}
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <Lock className="h-3.5 w-3.5 text-muted-foreground" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {t(lang, "api_docs_auth_title")}
              </h3>
            </div>
            <p className="text-[12px] text-muted-foreground leading-relaxed">
              {t(lang, "api_docs_auth_desc")}
            </p>
          </div>

          {/* Rate limit */}
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="h-3.5 w-3.5 text-muted-foreground" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {t(lang, "api_docs_rate_limit_title")}
              </h3>
            </div>
            <p className="text-[12px] text-muted-foreground leading-relaxed">
              {t(lang, "api_docs_rate_limit_desc")}
            </p>
            <div className="mt-2 rounded-lg bg-muted/30 px-3 py-1.5">
              <code className="text-[11px] font-mono text-foreground">
                60 req/min per IP
              </code>
            </div>
          </div>
        </div>

        {/* Endpoints */}
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
            {t(lang, "api_docs_endpoints_title")}
          </h3>
          <div className="space-y-3">
            {ENDPOINTS.map((ep) => (
              <EndpointCard
                key={ep.path}
                endpoint={ep}
                lang={lang}
              />
            ))}
          </div>
        </div>

        {/* Try it out */}
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 text-center">
          <h3 className="text-sm font-semibold mb-1">
            {t(lang, "api_docs_try_it")}
          </h3>
          <p className="text-[12px] text-muted-foreground mb-3">
            {lang === "ko"
              ? "브라우저에서 바로 API를 호출해볼 수 있습니다."
              : "You can call the API directly from your browser."}
          </p>
          <a
            href={`${API_BASE_URL}/public/stats`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            GET /public/stats
          </a>
        </div>

        {/* Footer */}
        <div className="text-center text-[11px] text-muted-foreground pb-6 space-y-1">
          <p>
            {lang === "ko"
              ? "API 관련 문의나 피드백은 설정 > 고객센터에서 보내주세요."
              : "For API inquiries or feedback, use Settings > Support."}
          </p>
          <p className="text-muted-foreground/50">
            WeWantPeace Public API v1.0
          </p>
        </div>
      </div>
    </div>
  );
}
