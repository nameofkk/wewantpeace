"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { API_BASE } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Megaphone, ChevronRight } from "lucide-react";
import { communityPostPath } from "@/lib/toss-nav";

interface Notice {
  id: string;
  title: string;
  title_en?: string | null;
  created_at: string;
}

export function NoticeTicker() {
  const lang = useAppStore((s) => s.lang);
  const router = useRouter();

  const { data: notices } = useQuery<Notice[]>({
    queryKey: ["pinned-notices"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/community/pinned-notices`);
      if (!res.ok) return [];
      return res.json();
    },
    staleTime: 5 * 60 * 1000,
  });

  if (!notices || notices.length === 0) return null;

  const latest = notices[0];

  return (
    <button
      onClick={() => router.push(communityPostPath(latest.id))}
      className="group w-full flex items-center gap-2.5 px-4 py-2.5 border-b border-border/60 hover:bg-muted/30 transition-all"
    >
      <span className="flex items-center justify-center h-6 w-6 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 shadow-sm shrink-0">
        <Megaphone className="h-3 w-3 text-white" />
      </span>
      <span className="flex-1 min-w-0 flex items-center gap-1.5">
        <span className="text-[10px] font-bold text-blue-400 shrink-0">
          {t(lang, "dash_notice_ticker")}
        </span>
        <span className="text-[11px] text-foreground/80 truncate text-left">
          {lang === "en" && latest.title_en ? latest.title_en : latest.title}
        </span>
      </span>
      <span className="flex items-center gap-1 shrink-0">
        <span className="text-[9px] text-muted-foreground">
          {new Date(latest.created_at).toLocaleDateString(
            lang === "ko" ? "ko-KR" : "en-US",
            { month: "short", day: "numeric" }
          )}
        </span>
        <ChevronRight className="h-3 w-3 text-muted-foreground group-hover:text-blue-400 transition-colors" />
      </span>
    </button>
  );
}
