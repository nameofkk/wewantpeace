"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import { Download, X } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { isTossMiniApp } from "@/lib/platform";

const DISMISS_KEY = "pwa_install_dismissed";
const DISMISS_HOURS = 24;

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function isDismissed() {
  const dismissed = localStorage.getItem(DISMISS_KEY);
  if (!dismissed) return false;
  const dismissedAt = parseInt(dismissed, 10);
  if (Date.now() - dismissedAt < DISMISS_HOURS * 60 * 60 * 1000) return true;
  localStorage.removeItem(DISMISS_KEY);
  return false;
}

export function PWAInstallPrompt() {
  const pathname = usePathname();
  const lang = useAppStore((s) => s.lang);
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isDismissed() || isTossMiniApp()) return;

    const handler = (e: Event) => {
      e.preventDefault();
      if (isDismissed()) return;
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setVisible(true);
    };

    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const handleInstall = useCallback(async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setVisible(false);
      setDeferredPrompt(null);
    }
  }, [deferredPrompt]);

  const handleDismiss = useCallback(() => {
    setVisible(false);
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  }, []);

  if (!visible || pathname === "/upgrade") return null;

  return (
    <div className="fixed bottom-[72px] left-4 right-4 z-50 rounded-xl border border-border bg-card shadow-xl p-4 flex items-center gap-3 animate-in slide-in-from-bottom-4 duration-300">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/20">
        <Download className="h-5 w-5 text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold">{t(lang, "pwa_install_title")}</p>
        <p className="text-[11px] text-muted-foreground truncate">
          {t(lang, "pwa_install_desc")}
        </p>
      </div>
      <button
        onClick={handleInstall}
        className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        {t(lang, "pwa_install_btn")}
      </button>
      <button
        onClick={handleDismiss}
        className="shrink-0 rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
        aria-label="닫기"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
