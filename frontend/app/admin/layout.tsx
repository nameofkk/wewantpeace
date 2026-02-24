"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { LayoutDashboard, Users, Flag, Settings, LogOut, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth, signOut } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/admin", icon: LayoutDashboard, label: "대시보드", exact: true },
  { href: "/admin/users", icon: Users, label: "회원 관리" },
  { href: "/admin/reports", icon: Flag, label: "신고 관리" },
  { href: "/admin/settings", icon: Settings, label: "서비스 설정" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    // 어드민 권한 확인
    user.getIdToken().then(async (token) => {
      const res = await fetch(`${API_BASE}/admin/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 403) {
        router.replace("/home");
      }
    });
  }, [user, loading, router, API_BASE]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* 사이드바 */}
      <aside className="w-56 shrink-0 border-r border-border bg-card flex flex-col">
        <div className="flex items-center gap-2 px-4 py-4 border-b border-border">
          <Globe className="h-5 w-5 text-primary" />
          <div>
            <p className="text-sm font-bold">WeWantPeace</p>
            <p className="text-[10px] text-muted-foreground">어드민</p>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {NAV_ITEMS.map(({ href, icon: Icon, label, exact }) => {
            const isActive = exact ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t border-border">
          <Link
            href="/home"
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-secondary mb-1"
          >
            <Globe className="h-4 w-4" />
            서비스로 이동
          </Link>
          <button
            onClick={() => signOut().then(() => router.push("/login"))}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-secondary hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
            로그아웃
          </button>
        </div>
      </aside>

      {/* 메인 */}
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
