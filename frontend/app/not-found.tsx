"use client";

import Link from "next/link";
import { Home, AlertTriangle } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

export default function NotFound() {
  const lang = useAppStore((s) => s.lang);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6 text-center">
      <AlertTriangle className="h-16 w-16 text-muted-foreground mb-4" />
      <h1 className="text-4xl font-bold mb-2">404</h1>
      <p className="text-lg font-medium mb-1">{t(lang, "not_found_title")}</p>
      <p className="text-sm text-muted-foreground mb-8">
        {t(lang, "not_found_message")}
      </p>
      <Link
        href="/"
        className="flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        <Home className="h-4 w-4" />
        {t(lang, "not_found_go_home")}
      </Link>
    </div>
  );
}
