"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import { Bell } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUnreadCount } from "@/lib/api";
import { isTossMiniApp } from "@/lib/platform";
import { getFirebaseAuth } from "@/lib/auth";

function AppHeaderInner() {
  const [hidden, setHidden] = useState(false);
  const [tapped, setTapped] = useState(false);
  const lastY = useRef(0);

  const [isLoggedIn, setIsLoggedIn] = useState(false);
  useEffect(() => {
    const auth = getFirebaseAuth();
    const hasAuth = !!localStorage.getItem("dev_uid") || !!auth?.currentUser;
    setIsLoggedIn(hasAuth);
  }, []);

  const { data: unreadData } = useUnreadCount(isLoggedIn);
  const unread = unreadData?.unread ?? 0;

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      if (y > lastY.current + 6 && y > 40) {
        setHidden(true);
      } else if (y < lastY.current - 4) {
        setHidden(false);
      }
      lastY.current = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleTap = () => {
    setTapped(true);
    setTimeout(() => setTapped(false), 450);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <>
      <header
        className={cn(
          "fixed top-0 left-0 right-0 z-40",
          "bg-background/85 backdrop-blur-md border-b border-border/50",
          "transition-transform duration-300 ease-in-out",
          hidden ? "-translate-y-full" : "translate-y-0"
        )}
      >
        <div className="flex items-center justify-between h-[52px] px-4">
          <div className="w-9" />
          <Link
            href="/home"
            onClick={handleTap}
            className={cn(
              "flex items-center gap-2.5 transition-all duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]",
              tapped ? "scale-90 opacity-70" : "scale-100 opacity-100"
            )}
          >
            <div
              className={cn(
                "relative overflow-hidden transition-transform duration-300",
                tapped && "rotate-[-8deg]"
              )}
              style={{ width: 36, height: 36 }}
            >
              <Image
                src="/logo.png"
                alt="WeWantPeace"
                fill
                priority
                className="object-cover"
                style={{
                  objectPosition: "50% 50%",
                  transform: "scale(2.5)",
                  transformOrigin: "50% 50%",
                }}
              />
            </div>
            <span className="text-[15px] font-semibold tracking-wide text-foreground">
              WeWantPeace
            </span>
          </Link>
          {isLoggedIn ? (
            <Link href="/notifications" className="relative w-9 h-9 flex items-center justify-center" aria-label={unread > 0 ? `알림 ${unread}개 읽지 않음` : "알림"}>
              <Bell className="w-5 h-5 text-muted-foreground" aria-hidden="true" />
              {unread > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-1">
                  {unread > 99 ? "99+" : unread}
                </span>
              )}
            </Link>
          ) : (
            <div className="w-9" />
          )}
        </div>
      </header>
      <div className="h-[52px]" />
    </>
  );
}

/** Toss 미니앱용 간소 헤더 — 로고만 표시 (공통 내비게이션 바 요건 충족) */
function TossHeader() {
  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-40 bg-background/85 backdrop-blur-md border-b border-border/50">
        <div className="flex items-center justify-center h-[48px] px-4">
          <div className="flex items-center gap-2">
            <div
              className="relative overflow-hidden"
              style={{ width: 32, height: 32 }}
            >
              <Image
                src="/logo.png"
                alt="WeWantPeace"
                fill
                priority
                className="object-cover"
                style={{
                  objectPosition: "50% 50%",
                  transform: "scale(2.5)",
                  transformOrigin: "50% 50%",
                }}
              />
            </div>
            <span className="text-[14px] font-semibold tracking-wide text-foreground">
              Wewantpeace
            </span>
          </div>
        </div>
      </header>
      <div className="h-[48px]" />
    </>
  );
}

export function AppHeader() {
  if (isTossMiniApp()) return <TossHeader />;
  return <AppHeaderInner />;
}
