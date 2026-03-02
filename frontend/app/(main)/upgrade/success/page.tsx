"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Check, MapPin, Bell, Globe, ArrowRight } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import Link from "next/link";

export default function UpgradeSuccessPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const lang = (useAppStore((s) => s.lang) || "ko") as Lang;
  const plan = searchParams.get("plan") || "pro";
  const isProPlus = plan === "pro_plus" || plan === "proplus";

  const [show, setShow] = useState(false);
  const [showFeatures, setShowFeatures] = useState(false);
  const [showButtons, setShowButtons] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setShow(true));
    const t1 = setTimeout(() => setShowFeatures(true), 400);
    const t2 = setTimeout(() => setShowButtons(true), 700);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  const features = [
    {
      icon: <MapPin className="w-5 h-5" />,
      text: t(lang, isProPlus ? "upgrade_success_feature1_proplus" : "upgrade_success_feature1_pro"),
    },
    {
      icon: <Globe className="w-5 h-5" />,
      text: t(lang, "upgrade_success_feature2"),
    },
    {
      icon: <Bell className="w-5 h-5" />,
      text: t(lang, "upgrade_success_feature3"),
    },
  ];

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <style>{`
        @keyframes checkPop {
          0% { transform: scale(0); opacity: 0; }
          50% { transform: scale(1.2); }
          100% { transform: scale(1); opacity: 1; }
        }
        @keyframes ripple {
          0% { transform: scale(0.8); opacity: 0.5; }
          100% { transform: scale(2.5); opacity: 0; }
        }
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>

      <div
        className="w-full max-w-sm flex flex-col items-center text-center"
        style={{
          opacity: show ? 1 : 0,
          transition: "opacity 0.5s ease",
        }}
      >
        {/* Check icon with ripple */}
        <div className="relative mb-8">
          <div
            className="absolute inset-0 rounded-full"
            style={{
              background: isProPlus
                ? "linear-gradient(135deg, #a855f7, #ec4899)"
                : "linear-gradient(135deg, #3b82f6, #06b6d4)",
              animation: show ? "ripple 1.5s ease-out forwards" : "none",
            }}
          />
          <div
            className="relative w-20 h-20 rounded-full flex items-center justify-center"
            style={{
              background: isProPlus
                ? "linear-gradient(135deg, #a855f7, #ec4899)"
                : "linear-gradient(135deg, #3b82f6, #06b6d4)",
              animation: show ? "checkPop 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards" : "none",
              boxShadow: isProPlus
                ? "0 8px 32px rgba(168, 85, 247, 0.4)"
                : "0 8px 32px rgba(59, 130, 246, 0.4)",
            }}
          >
            <Check className="w-10 h-10 text-white" strokeWidth={3} />
          </div>
        </div>

        {/* Title */}
        <h1
          className="text-2xl font-bold mb-2"
          style={{
            animation: show ? "fadeSlideUp 0.5s ease forwards" : "none",
            animationDelay: "0.2s",
            opacity: 0,
          }}
        >
          {t(lang, "upgrade_success_title")}
        </h1>

        {/* Plan badge */}
        <div
          className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold text-white mb-3"
          style={{
            background: isProPlus
              ? "linear-gradient(135deg, #a855f7, #ec4899)"
              : "linear-gradient(135deg, #3b82f6, #06b6d4)",
            backgroundSize: "200% 100%",
            animation: show
              ? "fadeSlideUp 0.5s ease forwards, shimmer 3s ease-in-out infinite"
              : "none",
            animationDelay: "0.3s, 0s",
            opacity: 0,
          }}
        >
          {isProPlus ? "Pro+" : "Pro"}
        </div>

        <p
          className="text-muted-foreground mb-8"
          style={{
            animation: show ? "fadeSlideUp 0.5s ease forwards" : "none",
            animationDelay: "0.35s",
            opacity: 0,
          }}
        >
          {t(lang, isProPlus ? "upgrade_success_subtitle_proplus" : "upgrade_success_subtitle_pro")}
        </p>

        {/* Features */}
        <div className="w-full space-y-3 mb-10">
          {features.map((f, i) => (
            <div
              key={i}
              className="flex items-center gap-3 px-4 py-3 rounded-xl bg-card border border-border/50"
              style={{
                animation: showFeatures ? "fadeSlideUp 0.4s ease forwards" : "none",
                animationDelay: `${i * 0.12}s`,
                opacity: 0,
              }}
            >
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{
                  background: isProPlus
                    ? "linear-gradient(135deg, rgba(168,85,247,0.15), rgba(236,72,153,0.15))"
                    : "linear-gradient(135deg, rgba(59,130,246,0.15), rgba(6,182,212,0.15))",
                  color: isProPlus ? "#a855f7" : "#3b82f6",
                }}
              >
                {f.icon}
              </div>
              <span className="text-sm font-medium text-left">{f.text}</span>
            </div>
          ))}
        </div>

        {/* Buttons */}
        <div
          className="w-full space-y-3"
          style={{
            animation: showButtons ? "fadeSlideUp 0.4s ease forwards" : "none",
            opacity: 0,
          }}
        >
          <Link
            href="/"
            className="flex items-center justify-center gap-2 w-full py-3.5 rounded-xl text-white font-semibold text-base transition-transform active:scale-[0.98]"
            style={{
              background: isProPlus
                ? "linear-gradient(135deg, #a855f7, #ec4899)"
                : "linear-gradient(135deg, #3b82f6, #06b6d4)",
            }}
          >
            {t(lang, "upgrade_success_go_home")}
            <ArrowRight className="w-4 h-4" />
          </Link>

          <Link
            href="/settings"
            className="flex items-center justify-center w-full py-3 rounded-xl text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            {t(lang, "upgrade_success_go_settings")}
          </Link>
        </div>
      </div>
    </div>
  );
}
