"use client";

import React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface ProDemoProps {
  isPro: boolean;
  demoCount: number;
  totalCount: number;
  children: React.ReactNode;
  ctaText: string;
  ctaHref?: string;
  lang: "ko" | "en";
}

export function ProDemoWrapper({
  isPro,
  demoCount,
  totalCount,
  children,
  ctaText,
  ctaHref = "/upgrade",
  lang,
}: ProDemoProps) {
  if (isPro) return <>{children}</>;

  const childArray = React.Children.toArray(children);
  const visible = childArray.slice(0, demoCount);
  const hidden = childArray.slice(demoCount);
  const remaining = totalCount - demoCount;

  return (
    <div className="relative">
      {visible}
      {hidden.length > 0 && (
        <div className="relative">
          <div className="blur-[3px] opacity-25 pointer-events-none select-none">
            {hidden}
          </div>
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/80 to-transparent" />
        </div>
      )}
      {remaining > 0 && (
        <div className="flex justify-center pt-2 pb-1">
          <Link
            href={ctaHref}
            className="inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[10px] font-bold text-white transition-transform hover:scale-105"
            style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
          >
            {ctaText.replace("{n}", String(remaining))}
          </Link>
        </div>
      )}
    </div>
  );
}
