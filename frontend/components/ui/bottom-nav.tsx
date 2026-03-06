"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Home, Map, Activity, MessageSquare, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

export function BottomNav() {
  const pathname = usePathname();
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);

  const NAV_ITEMS = [
    { href: "/home", icon: Home, label: t(lang, "nav_home") },
    { href: "/map", icon: Map, label: t(lang, "nav_map") },
    { href: "/tension", icon: Activity, label: t(lang, "nav_tension") },
    { href: "/community", icon: MessageSquare, label: t(lang, "nav_community") },
    { href: "/settings", icon: Settings, label: t(lang, "nav_settings") },
  ];

  // 모든 탭 라우트를 미리 프리페치 (첫 진입 지연 제거)
  useEffect(() => {
    ["/home", "/map", "/tension", "/community", "/settings"].forEach((href) => {
      router.prefetch(href);
    });
  }, [router]);

  if (pathname === "/onboarding" || pathname.startsWith("/login") || pathname.startsWith("/admin")) return null;

  return (
    <nav className="tab-bar fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur-sm" role="tablist" aria-label="Main navigation">
      <div className="flex h-[60px] items-center justify-around px-2">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const isActive = pathname.startsWith(href);
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
