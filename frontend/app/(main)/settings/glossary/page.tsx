"use client";

import { ChevronLeft } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { useRouter } from "next/navigation";
import { LogoIcon } from "@/components/ui/logo-icon";

type GlossaryItem = { key: string; label: string; desc: string };
type GlossaryCategory = { title: string; color: string; items: GlossaryItem[] };

function getCategories(lang: Lang): GlossaryCategory[] {
  return [
    {
      title: t(lang, "glossary_cat_core"),
      color: "border-l-blue-500",
      items: [
        { key: "issue", label: t(lang, "glossary_issue"), desc: t(lang, "glossary_issue_desc") },
        { key: "event", label: t(lang, "glossary_event"), desc: t(lang, "glossary_event_desc") },
        { key: "trending", label: t(lang, "glossary_trending"), desc: t(lang, "glossary_trending_desc") },
        { key: "tension", label: t(lang, "glossary_tension"), desc: t(lang, "glossary_tension_desc") },
      ],
    },
    {
      title: t(lang, "glossary_cat_levels"),
      color: "border-l-green-500",
      items: [
        { key: "stable", label: t(lang, "glossary_level_stable"), desc: t(lang, "glossary_level_stable_desc") },
        { key: "caution", label: t(lang, "glossary_level_caution"), desc: t(lang, "glossary_level_caution_desc") },
        { key: "warning", label: t(lang, "glossary_level_warning"), desc: t(lang, "glossary_level_warning_desc") },
        { key: "severe", label: t(lang, "glossary_level_severe"), desc: t(lang, "glossary_level_severe_desc") },
        { key: "crisis", label: t(lang, "glossary_level_crisis"), desc: t(lang, "glossary_level_crisis_desc") },
      ],
    },
    {
      title: t(lang, "glossary_cat_topics"),
      color: "border-l-orange-500",
      items: [
        { key: "conflict", label: t(lang, "glossary_topic_conflict"), desc: t(lang, "glossary_topic_conflict_desc") },
        { key: "terror", label: t(lang, "glossary_topic_terror"), desc: t(lang, "glossary_topic_terror_desc") },
        { key: "coup", label: t(lang, "glossary_topic_coup"), desc: t(lang, "glossary_topic_coup_desc") },
        { key: "sanctions", label: t(lang, "glossary_topic_sanctions"), desc: t(lang, "glossary_topic_sanctions_desc") },
        { key: "cyber", label: t(lang, "glossary_topic_cyber"), desc: t(lang, "glossary_topic_cyber_desc") },
        { key: "protest", label: t(lang, "glossary_topic_protest"), desc: t(lang, "glossary_topic_protest_desc") },
        { key: "diplomacy", label: t(lang, "glossary_topic_diplomacy"), desc: t(lang, "glossary_topic_diplomacy_desc") },
        { key: "maritime", label: t(lang, "glossary_topic_maritime"), desc: t(lang, "glossary_topic_maritime_desc") },
        { key: "disaster", label: t(lang, "glossary_topic_disaster"), desc: t(lang, "glossary_topic_disaster_desc") },
        { key: "health", label: t(lang, "glossary_topic_health"), desc: t(lang, "glossary_topic_health_desc") },
      ],
    },
    {
      title: t(lang, "glossary_cat_scoring"),
      color: "border-l-purple-500",
      items: [
        { key: "kscore", label: t(lang, "glossary_kscore"), desc: t(lang, "glossary_kscore_desc") },
        { key: "severity", label: t(lang, "glossary_severity"), desc: t(lang, "glossary_severity_desc") },
        { key: "confidence", label: t(lang, "glossary_confidence"), desc: t(lang, "glossary_confidence_desc") },
        { key: "kscore_alert", label: t(lang, "glossary_kscore_alert"), desc: t(lang, "glossary_kscore_alert_desc") },
      ],
    },
    {
      title: t(lang, "glossary_cat_sources"),
      color: "border-l-emerald-500",
      items: [
        { key: "t1", label: t(lang, "glossary_source_t1"), desc: t(lang, "glossary_source_t1_desc") },
        { key: "t2", label: t(lang, "glossary_source_t2"), desc: t(lang, "glossary_source_t2_desc") },
        { key: "t3", label: t(lang, "glossary_source_t3"), desc: t(lang, "glossary_source_t3_desc") },
      ],
    },
  ];
}

export default function GlossaryPage() {
  const router = useRouter();
  const { lang } = useAppStore();
  const categories = getCategories(lang);

  return (
    <div className="flex flex-col">
      {/* 헤더 */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <div className="grid grid-cols-3 items-center mb-1">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-0.5 text-sm text-primary -ml-1"
          >
            <ChevronLeft className="h-4 w-4" />
            <span>{t(lang, "glossary_back")}</span>
          </button>
          <div className="flex justify-center">
            <LogoIcon height={26} hideText />
          </div>
          <div />
        </div>
        <h1 className="text-sm font-bold">{t(lang, "glossary_title")}</h1>
        <p className="text-[11px] text-muted-foreground">{t(lang, "settings_glossary_sub")}</p>
      </div>

      <div className="px-4 py-4 space-y-5">
        {categories.map((cat) => (
          <section key={cat.title}>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
              {cat.title}
            </h2>
            <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
              {cat.items.map((item) => (
                <div key={item.key} className={`px-4 py-3 border-l-2 ${cat.color}`}>
                  <p className="text-sm font-medium">{item.label}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5 whitespace-pre-line leading-relaxed">
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </section>
        ))}

        <div className="pb-8" />
      </div>
    </div>
  );
}
