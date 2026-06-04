"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Home, Newspaper, Map, Activity, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { isTossMiniApp } from "@/lib/platform";

export function BottomNav() {
  const pathname = usePathname();
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);

  const NAV_ITEMS = [
    { href: "/home", icon: Home, label: t(lang, "nav_home") },
    { href: "/feed", icon: Newspaper, label: t(lang, "nav_feed") },
    { href: "/map", icon: Map, label: t(lang, "nav_map") },
    { href: "/tension", icon: Activity, label: t(lang, "nav_tension") },
    { href: "/settings", icon: Settings, label: t(lang, "nav_settings") },
  ];

  // 모든 탭 라우트를 미리 프리페치 (첫 진입 지연 제거)
  useEffect(() => {
    ["/home", "/feed", "/map", "/tension", "/settings"].forEach((href) => {
      router.prefetch(href);
    });
  }, [router]);

  if (pathname === "/onboarding" || pathname.startsWith("/login") || pathname.startsWith("/admin")) return null;

  const toss = isTossMiniApp();

  return (
    <nav
      className={cn(
        "fixed z-50",
        toss
          ? "bottom-[calc(12px+env(safe-area-inset-bottom))] left-4 right-4 rounded-full bg-background/90 backdrop-blur-xl shadow-[0_4px_24px_rgba(0,0,0,0.35)]"
          : "tab-bar bottom-[calc(8px+env(safe-area-inset-bottom))] left-3 right-3 rounded-2xl bg-background/90 backdrop-blur-xl shadow-[0_2px_20px_rgba(0,0,0,0.12)] dark:shadow-[0_2px_20px_rgba(0,0,0,0.4)] border border-border/40"
      )}
      role="tablist"
      aria-label="Main navigation"
    >
      <div className={cn(
        "flex items-center justify-around",
        toss ? "h-[56px] px-3" : "h-[56px] px-2"
      )}>
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          // /issues/*, /notifications/*, /upgrade/* 는 /feed의 하위 플로우로 간주
          const isActive = pathname.startsWith(href) ||
            (href === "/feed" && (pathname.startsWith("/issues") || pathname.startsWith("/notifications") || pathname.startsWith("/upgrade")));
          return (
            <Link
              key={href}
              href={href}
              role="tab"
              aria-selected={isActive}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 rounded-lg py-1 transition-colors",
                isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
              <span className="text-[10px] font-medium">{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
