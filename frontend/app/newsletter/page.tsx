"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Mail, ArrowLeft, ExternalLink } from "lucide-react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://api.wewantpeace.live";

type ArchiveItem = {
  id: number;
  subject: string;
  sent_count: number;
  created_at: string;
};

const TEXT = {
  ko: {
    title: "뉴스레터 아카이브",
    desc: "지난 뉴스레터를 확인해보세요",
    empty: "아직 발송된 뉴스레터가 없습니다",
    cta: "이런 뉴스레터를 매주 받아보세요",
    web_version: "웹 버전으로 보기",
    back: "목록으로",
    home: "홈으로",
    subscribers: "명 수신",
    loading: "불러오는 중...",
  },
  en: {
    title: "Newsletter Archive",
    desc: "Browse past newsletters",
    empty: "No newsletters have been sent yet",
    cta: "Get newsletters like this every week",
    web_version: "View web version",
    back: "Back to list",
    home: "Home",
    subscribers: " recipients",
    loading: "Loading...",
  },
} as const;

function detectLang(): "ko" | "en" {
  if (typeof window === "undefined") return "ko";
  try {
    const store = JSON.parse(localStorage.getItem("wwp-store") || "{}");
    if (store.state?.lang) return store.state.lang === "en" ? "en" : "ko";
  } catch {
    // ignore
  }
  const nav = navigator.language || "";
  return nav.startsWith("ko") ? "ko" : "en";
}

export default function NewsletterArchivePage() {
  const [lang, setLang] = useState<"ko" | "en">("ko");
  const [archives, setArchives] = useState<ArchiveItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    setLang(detectLang());
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/newsletter/archive`)
      .then((r) => r.json())
      .then((data) => {
        setArchives(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const t = TEXT[lang];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto max-w-2xl px-4 py-3 flex items-center gap-3">
          {selectedId !== null ? (
            <button
              onClick={() => setSelectedId(null)}
              className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              {t.back}
            </button>
          ) : (
            <Link
              href="/"
              className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              {t.home}
            </Link>
          )}
          <div className="flex-1" />
          <Mail className="h-4 w-4 text-blue-400" />
          <span className="text-sm font-bold text-foreground">{t.title}</span>
        </div>
      </div>

      <div className="mx-auto max-w-2xl px-4 py-6">
        {/* Archive detail (iframe) */}
        {selectedId !== null && (
          <div className="mb-6">
            <div className="rounded-xl border border-border overflow-hidden bg-white">
              <iframe
                src={`${API_BASE}/newsletter/archive/${selectedId}`}
                className="w-full border-0"
                style={{ minHeight: "80vh" }}
                title="Newsletter"
              />
            </div>
            <div className="mt-4 text-center">
              <a
                href={`${API_BASE}/newsletter/archive/${selectedId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <ExternalLink className="h-3 w-3" />
                {t.web_version}
              </a>
            </div>
          </div>
        )}

        {/* Archive list */}
        {selectedId === null && (
          <>
            <p className="text-sm text-muted-foreground mb-4">{t.desc}</p>

            {loading && (
              <div className="text-center py-12">
                <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-primary" />
                <p className="mt-3 text-xs text-muted-foreground">
                  {t.loading}
                </p>
              </div>
            )}

            {!loading && archives.length === 0 && (
              <div className="rounded-xl border border-border bg-card p-8 text-center">
                <Mail className="mx-auto h-8 w-8 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">{t.empty}</p>
              </div>
            )}

            {!loading && archives.length > 0 && (
              <div className="space-y-2">
                {archives.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setSelectedId(item.id)}
                    className="w-full text-left rounded-lg border border-border bg-card p-4 hover:border-blue-500/30 hover:bg-blue-500/[0.02] transition-colors"
                  >
                    <p className="text-sm font-medium text-foreground">
                      {item.subject}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] text-muted-foreground">
                        {new Date(item.created_at).toLocaleDateString(
                          lang === "en" ? "en-US" : "ko-KR",
                          {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          }
                        )}
                      </span>
                      <span className="text-[10px] text-muted-foreground/50">
                        ·
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {item.sent_count}
                        {t.subscribers}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {/* Bottom CTA */}
            <div className="mt-8 rounded-xl border border-border bg-gradient-to-br from-blue-500/[0.03] to-indigo-500/[0.06] p-6 text-center">
              <Mail className="mx-auto h-6 w-6 text-blue-400/50 mb-2" />
              <p className="text-sm font-medium text-foreground mb-1">
                {t.cta}
              </p>
              <Link
                href="/"
                className="inline-block mt-2 text-xs text-primary hover:underline"
              >
                {t.home} →
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
