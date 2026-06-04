"use client";

import { useEffect, useState } from "react";
import { X, Globe, BarChart3, Bell, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { LogoIcon } from "@/components/ui/logo-icon";

const STORAGE_KEY = "wwp_welcome_seen";

export default function WelcomeModal() {
  const { lang } = useAppStore();
  const [open, setOpen] = useState(false);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    // 온보딩 완료 유저에게는 WelcomeModal을 표시하지 않음
    if (localStorage.getItem("onboarding_done") === "true") {
      localStorage.setItem(STORAGE_KEY, String(Date.now()));
      return;
    }
    if (!localStorage.getItem(STORAGE_KEY)) {
      setOpen(true);
    }
  }, []);

  // 모달 열릴 때 body scroll lock
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  const handleClose = () => {
    setClosing(true);
    setTimeout(() => {
      localStorage.setItem(STORAGE_KEY, String(Date.now()));
      setClosing(false);
      setOpen(false);
    }, 200);
  };

  const features = [
    { icon: Globe, text: t(lang, "welcome_feat_1") },
    { icon: BarChart3, text: t(lang, "welcome_feat_2") },
    { icon: Bell, text: t(lang, "welcome_feat_3") },
  ];

  const trustItems = [
    t(lang, "welcome_trust_1"),
    t(lang, "welcome_trust_2"),
    t(lang, "welcome_trust_3"),
  ];

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center",
        closing ? "animate-out fade-out" : "animate-in fade-in"
      )}
      onKeyDown={(e) => e.key === "Escape" && handleClose()}
    >
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div
        className={cn(
          "relative w-full max-w-md mx-4 sm:mx-auto rounded-3xl bg-card border border-border/60 overflow-hidden max-h-[calc(100dvh-90px)] sm:max-h-[90vh] overflow-y-auto"
        )}
        style={{
          animation: closing
            ? "welcomeSlideDown 0.2s ease forwards"
            : "welcomeSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        }}
      >
        <style>{`
          @keyframes welcomeSlideUp {
            from { opacity: 0; transform: scale(0.95) translateY(20px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
          }
          @keyframes welcomeSlideDown {
            from { opacity: 1; transform: scale(1) translateY(0); }
            to { opacity: 0; transform: scale(0.95) translateY(20px); }
          }
        `}</style>

        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 z-10 rounded-full p-1.5 bg-muted/50 hover:bg-muted transition-colors"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Header */}
        <div className="pt-8 pb-2 px-6 text-center">
          <div className="flex justify-center mb-4">
            <LogoIcon height={40} hideText />
          </div>
          <h3 className="text-xl font-black tracking-tight break-keep">
            {t(lang, "welcome_title")}
          </h3>
          <p className="mt-1.5 text-sm text-muted-foreground break-keep">
            {t(lang, "welcome_subtitle")}
          </p>
        </div>

        {/* Features */}
        <div className="px-6 py-4">
          <div className="space-y-3">
            {features.map(({ icon: Icon, text }, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-blue-500/15 to-cyan-500/15 flex items-center justify-center shrink-0">
                  <Icon className="h-4.5 w-4.5 text-blue-500" />
                </div>
                <p className="text-sm text-foreground/90 pt-1.5">{text}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Trust badges */}
        <div className="px-6 pb-4">
          <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4">
            <div className="space-y-2">
              {trustItems.map((item, i) => (
                <div key={i} className="flex items-center gap-2.5">
                  <div className="h-5 w-5 rounded-full bg-emerald-500/15 flex items-center justify-center shrink-0">
                    <Check className="h-3 w-3 text-emerald-500" />
                  </div>
                  <span className="text-xs text-foreground/80">{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="px-6 pb-6">
          <button
            onClick={handleClose}
            className="w-full rounded-xl py-3.5 text-sm font-bold bg-gradient-to-r from-blue-500 to-cyan-500 text-white hover:shadow-lg hover:shadow-blue-500/25 transition-all active:scale-[0.98]"
          >
            {t(lang, "welcome_cta")}
          </button>
        </div>
      </div>
    </div>
  );
}
