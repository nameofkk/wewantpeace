"use client";

import { useState } from "react";
import { ChevronLeft, ChevronDown, ChevronRight, Search } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { useRouter } from "next/navigation";
import { LogoIcon } from "@/components/ui/logo-icon";
import { cn } from "@/lib/utils";

type GlossaryItem = { key: string; label: string; desc: string };
type GlossaryCategory = { title: string; color: string; icon: string; items: GlossaryItem[] };

function getCategories(lang: Lang): GlossaryCategory[] {
  return [
    {
      title: t(lang, "glossary_cat_core"),
      color: "border-l-blue-500",
      icon: "🧩",
      items: [
        { key: "issue", label: t(lang, "glossary_issue"), desc: t(lang, "glossary_issue_desc") },
        { key: "event", label: t(lang, "glossary_event"), desc: t(lang, "glossary_event_desc") },
        { key: "trending", label: t(lang, "glossary_trending"), desc: t(lang, "glossary_trending_desc") },
        { key: "tension", label: t(lang, "glossary_tension"), desc: t(lang, "glossary_tension_desc") },
        { key: "home_country", label: t(lang, "glossary_home_country"), desc: t(lang, "glossary_home_country_desc") },
        { key: "watched_country", label: t(lang, "glossary_watched_country"), desc: t(lang, "glossary_watched_country_desc") },
      ],
    },
    {
      title: t(lang, "glossary_cat_levels"),
      color: "border-l-green-500",
      icon: "📊",
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
      icon: "🏷️",
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
      icon: "🔢",
      items: [
        { key: "kscore", label: t(lang, "glossary_kscore"), desc: t(lang, "glossary_kscore_desc") },
        { key: "severity", label: t(lang, "glossary_severity"), desc: t(lang, "glossary_severity_desc") },
        { key: "confidence", label: t(lang, "glossary_confidence"), desc: t(lang, "glossary_confidence_desc") },
        { key: "kscore_alert", label: t(lang, "glossary_kscore_alert"), desc: t(lang, "glossary_kscore_alert_desc") },
        { key: "fast_alert", label: t(lang, "glossary_fast_alert"), desc: t(lang, "glossary_fast_alert_desc") },
        { key: "verified_alert", label: t(lang, "glossary_verified_alert"), desc: t(lang, "glossary_verified_alert_desc") },
        { key: "critical_bypass", label: t(lang, "glossary_critical_bypass"), desc: t(lang, "glossary_critical_bypass_desc") },
      ],
    },
    {
      title: t(lang, "glossary_cat_sources"),
      color: "border-l-emerald-500",
      icon: "📡",
      items: [
        { key: "t1", label: t(lang, "glossary_source_t1"), desc: t(lang, "glossary_source_t1_desc") },
        { key: "t2", label: t(lang, "glossary_source_t2"), desc: t(lang, "glossary_source_t2_desc") },
        { key: "t3", label: t(lang, "glossary_source_t3"), desc: t(lang, "glossary_source_t3_desc") },
      ],
    },
    {
      title: t(lang, "glossary_cat_intel"),
      color: "border-l-cyan-500",
      icon: "🛰️",
      items: [
        { key: "firms", label: t(lang, "glossary_firms"), desc: t(lang, "glossary_firms_desc") },
        { key: "ioda", label: t(lang, "glossary_ioda"), desc: t(lang, "glossary_ioda_desc") },
        { key: "gps_jam", label: t(lang, "glossary_gps_jam"), desc: t(lang, "glossary_gps_jam_desc") },
        { key: "cross_verify", label: t(lang, "glossary_cross_verify"), desc: t(lang, "glossary_cross_verify_desc") },
      ],
    },
  ];
}

function AccordionItem({ item, color }: { item: GlossaryItem; color: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`border-l-2 ${color}`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-muted/30 transition-colors"
      >
        <p className="text-sm font-medium">{item.label}</p>
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        )}
      </button>
      {open && (
        <div className="px-4 pb-3">
          <p className="text-[11px] text-muted-foreground whitespace-pre-line leading-relaxed">
            {item.desc}
          </p>
        </div>
      )}
    </div>
  );
}

export default function GlossaryPage() {
  const router = useRouter();
  const { lang } = useAppStore();
  const categories = getCategories(lang);
  const [search, setSearch] = useState("");

  const filteredCategories = search.trim()
    ? categories.map((cat) => ({
        ...cat,
        items: cat.items.filter(
          (item) =>
            item.label.toLowerCase().includes(search.toLowerCase()) ||
            item.desc.toLowerCase().includes(search.toLowerCase())
        ),
      })).filter((cat) => cat.items.length > 0)
    : categories;

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

        {/* 검색 필터 */}
        <div className="relative mt-2">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder={lang === "ko" ? "용어 검색..." : "Search terms..."}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-border bg-secondary pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-primary"
          />
        </div>
      </div>

      <div className="px-4 py-4 space-y-5">
        {filteredCategories.map((cat) => (
          <section key={cat.title}>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
              <span>{cat.icon}</span>
              <span>{cat.title}</span>
            </h2>
            <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
              {cat.items.map((item) => (
                <AccordionItem key={item.key} item={item} color={cat.color} />
              ))}
            </div>
          </section>
        ))}

        {filteredCategories.length === 0 && (
          <div className="text-center py-8 text-sm text-muted-foreground">
            {lang === "ko" ? "검색 결과가 없습니다" : "No results found"}
          </div>
        )}

        <div className="pb-8" />
      </div>
    </div>
  );
}
