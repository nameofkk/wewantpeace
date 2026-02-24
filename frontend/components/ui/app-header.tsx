"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

export function AppHeader() {
  const [hidden, setHidden] = useState(false);
  const [tapped, setTapped] = useState(false);
  const lastY = useRef(0);

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
      {/* fixed 헤더 */}
      <header
        className={cn(
          "fixed top-0 left-0 right-0 z-40",
          "bg-background/85 backdrop-blur-md border-b border-border/50",
          "transition-transform duration-300 ease-in-out",
          hidden ? "-translate-y-full" : "translate-y-0"
        )}
      >
        <div className="flex items-center justify-center h-[52px]">
          <Link
            href="/home"
            onClick={handleTap}
            className={cn(
              "flex items-center gap-2.5 transition-all duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]",
              tapped ? "scale-90 opacity-70" : "scale-100 opacity-100"
            )}
          >
            {/* 눈 아이콘 — 크기 키움 */}
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
        </div>
      </header>

      {/* 헤더 높이만큼 공간 확보 */}
      <div className="h-[52px]" />
    </>
  );
}
