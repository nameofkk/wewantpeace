"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { PRIVACY_KO, PRIVACY_EN } from "@/lib/legal-data";

export default function PrivacyPage() {
  const lang = useAppStore((s) => s.lang);
  const router = useRouter();
  const sections = lang === "en" ? PRIVACY_EN : PRIVACY_KO;

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-2xl px-4 py-8">
        <div className="flex items-center gap-2 mb-6">
          <button onClick={() => router.back()} className="text-muted-foreground hover:text-foreground">
            <ChevronLeft className="h-5 w-5" />
          </button>
          <h1 className="text-xl font-bold">{t(lang, "privacy_title")}</h1>
        </div>

        <p className="text-sm text-muted-foreground mb-2">
          {t(lang, "privacy_date")}
        </p>
        <p className="text-sm text-muted-foreground mb-6">
          {t(lang, "privacy_compliance")}
        </p>

        <div className="space-y-6">
          {sections.map((section) => (
            <div key={section.title} className="rounded-xl border border-border bg-card p-5">
              <h2 className="text-sm font-bold mb-3 text-primary">{section.title}</h2>
              <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
                {section.content}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-8 text-center text-xs text-muted-foreground">
          {t(lang, "privacy_contact")}:{" "}
          <a href="mailto:contact@wewantpeace.app" className="hover:underline">
            contact@wewantpeace.app
          </a>
          {" · "}
          <Link href="/terms" className="hover:underline">{t(lang, "privacy_terms_link")}</Link>
        </div>
      </div>
    </div>
  );
}
