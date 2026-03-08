"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard, Users, Layers, Activity, FileText,
  Settings, ArrowLeft, Menu, X, Shield, Globe, LogOut, Radio,
  MessageSquare, TrendingUp, MessageCircleQuestion,
  Mail, ScrollText, Workflow, BarChart3,
  Handshake, Link2, FileBarChart, BookOpen, Share2, ShieldCheck,
} from "lucide-react";
import { AdminToastProvider } from "@/components/ui/admin-toast";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { useAuth, signOut } from "@/lib/auth";
import { API_BASE } from "@/lib/admin-utils";

interface NavItem {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  labelKey: Parameters<typeof t>[1];
  exact?: boolean;
}

interface NavGroup {
  labelKey: Parameters<typeof t>[1];
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    labelKey: "admin_group_overview",
    items: [
      { href: "/admin", icon: LayoutDashboard, labelKey: "admin_dashboard", exact: true },
    ],
  },
  {
    labelKey: "admin_group_users",
    items: [
      { href: "/admin/users", icon: Users, labelKey: "admin_users" },
      { href: "/admin/marketing", icon: Mail, labelKey: "admin_marketing" },
    ],
  },
  {
    labelKey: "admin_group_content",
    items: [
      { href: "/admin/content", icon: ShieldCheck, labelKey: "admin_content_moderation" },
      { href: "/admin/comments", icon: ScrollText, labelKey: "admin_comments" },
      { href: "/admin/feedbacks", icon: MessageCircleQuestion, labelKey: "admin_feedbacks" },
    ],
  },
  {
    labelKey: "admin_group_data",
    items: [
      { href: "/admin/pipeline", icon: Workflow, labelKey: "admin_pipeline" },
      { href: "/admin/clusters", icon: Layers, labelKey: "admin_clusters" },
      { href: "/admin/events", icon: FileText, labelKey: "admin_events" },
      { href: "/admin/sources", icon: Radio, labelKey: "admin_sources" },
    ],
  },
  {
    labelKey: "admin_group_analytics",
    items: [
      { href: "/admin/kpi", icon: BarChart3, labelKey: "admin_kpi" },
      { href: "/admin/kscore", icon: TrendingUp, labelKey: "admin_trending" },
      { href: "/admin/tension", icon: Activity, labelKey: "admin_tension" },
    ],
  },
  {
    labelKey: "admin_group_ops",
    items: [
      { href: "/admin/partners", icon: Handshake, labelKey: "admin_partners" },
      { href: "/admin/links", icon: Link2, labelKey: "admin_links" },
      { href: "/admin/weekly-report", icon: FileBarChart, labelKey: "admin_weekly_report" },
      { href: "/admin/guide", icon: BookOpen, labelKey: "admin_guide" },
      { href: "/admin/social", icon: Share2, labelKey: "admin_social" },
    ],
  },
  {
    labelKey: "admin_group_system",
    items: [
      { href: "/admin/settings", icon: Settings, labelKey: "admin_settings" },
      { href: "/admin/logs", icon: ScrollText, labelKey: "admin_logs" },
    ],
  },
];

const ALL_NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

function Sidebar({
  lang,
  collapsed,
  onClose,
}: {
  lang: Lang;
  collapsed: boolean;
  onClose?: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border bg-card h-full",
        collapsed ? "w-16" : "w-56"
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 h-14 px-3 border-b border-border">
        <Globe className="h-5 w-5 text-primary shrink-0" />
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold truncate">WeWantPeace</p>
            <p className="text-[10px] text-muted-foreground">{t(lang, "admin_title")}</p>
          </div>
        )}
        {onClose && (
          <button onClick={onClose} className="ml-auto p-1 text-muted-foreground md:hidden">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {NAV_GROUPS.map((group, gi) => (
          <div key={gi}>
            {!collapsed && (
              <p className="px-5 pt-3 pb-1 text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider">
                {t(lang, group.labelKey)}
              </p>
            )}
            {collapsed && gi > 0 && (
              <div className="mx-3 my-1 border-t border-border/40" />
            )}
            <div className="space-y-0.5">
              {group.items.map(({ href, icon: Icon, labelKey, exact }) => {
                const active = exact ? pathname === href : pathname.startsWith(href + "/") || pathname === href;
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={onClose}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2 mx-2 rounded-lg text-sm transition-colors",
                      active
                        ? "bg-primary/10 text-primary font-medium"
                        : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {!collapsed && <span className="truncate">{t(lang, labelKey)}</span>}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-border p-3 space-y-1">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {!collapsed && t(lang, "admin_back_to_site")}
        </Link>
        <button
          onClick={() => signOut().then(() => router.push("/login"))}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
        >
          <LogOut className="h-3.5 w-3.5" />
          {!collapsed && (lang === "ko" ? "로그아웃" : "Log Out")}
        </button>
      </div>
    </aside>
  );
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { lang } = useAppStore();
  const router = useRouter();
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const [authStatus, setAuthStatus] = useState<"loading" | "ok" | "denied">("loading");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => setMobileOpen(false), [pathname]);

  // 인증 + 어드민 권한 확인 (10초 타임아웃)
  useEffect(() => {
    if (loading) return;
    if (!user) {
      setAuthStatus("denied");
      return;
    }
    let cancelled = false;
    const timeout = setTimeout(() => {
      if (!cancelled) setAuthStatus("denied");
    }, 10_000);

    user
      .getIdToken()
      .then(async (token) => {
        try {
          const res = await fetch(`${API_BASE}/admin/stats`, {
            headers: { Authorization: `Bearer ${token}` },
            signal: AbortSignal.timeout(8_000),
          });
          if (!cancelled) setAuthStatus(res.ok ? "ok" : "denied");
        } catch {
          if (!cancelled) setAuthStatus("denied");
        }
      })
      .catch(() => {
        if (!cancelled) setAuthStatus("denied");
      })
      .finally(() => clearTimeout(timeout));

    return () => { cancelled = true; clearTimeout(timeout); };
  }, [user, loading]);

  if (loading || authStatus === "loading") {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="h-6 w-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (authStatus === "denied") {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-background text-center px-4">
        <Shield className="h-16 w-16 text-red-400 mb-4" />
        <h1 className="text-xl font-bold mb-2">{t(lang, "admin_no_access")}</h1>
        <p className="text-sm text-muted-foreground mb-6">{t(lang, "admin_no_access_sub")}</p>
        <Link href="/" className="text-sm text-primary hover:underline">
          {t(lang, "admin_back_to_site")}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <div className="hidden md:flex h-screen sticky top-0">
        <Sidebar lang={lang} collapsed={false} />
      </div>

      {/* Mobile header */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-30 flex items-center justify-between h-12 px-4 border-b border-border bg-card">
        <button onClick={() => setMobileOpen(true)} className="p-1 text-muted-foreground">
          <Menu className="h-5 w-5" />
        </button>
        <span className="text-sm font-bold text-primary">
          {(() => {
            const nav = ALL_NAV_ITEMS.find((n) => n.exact ? pathname === n.href : pathname.startsWith(n.href + "/") || pathname === n.href);
            return nav ? t(lang, nav.labelKey) : t(lang, "admin_title");
          })()}
        </span>
        <Link href="/" className="p-1 text-muted-foreground">
          <ArrowLeft className="h-5 w-5" />
        </Link>
      </div>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <>
          <div className="md:hidden fixed inset-0 z-40 bg-black/50" onClick={() => setMobileOpen(false)} />
          <div className="md:hidden fixed inset-y-0 left-0 z-50 w-56">
            <Sidebar lang={lang} collapsed={false} onClose={() => setMobileOpen(false)} />
          </div>
        </>
      )}

      {/* Main content */}
      <main className="flex-1 overflow-auto pt-12 md:pt-0">
        <AdminToastProvider>
          <div className="p-4 md:p-6 max-w-7xl">{children}</div>
        </AdminToastProvider>
      </main>
    </div>
  );
}
