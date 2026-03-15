"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { API_BASE } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Megaphone } from "lucide-react";

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
      onClick={() => router.push(`/community/${latest.id}`)}
      className="w-full flex items-center gap-2 px-4 py-2 bg-blue-500/5 border-b border-blue-500/10 hover:bg-blue-500/10 transition-colors"
    >
      <span className="flex items-center gap-1.5 shrink-0">
        <Megaphone className="h-3 w-3 text-blue-400" />
        <span className="text-[10px] font-bold text-blue-400">
          {t(lang, "dash_notice_ticker")}
        </span>
      </span>
      <span className="flex-1 text-[11px] text-foreground/80 truncate text-left">
        {lang === "en" && latest.title_en ? latest.title_en : latest.title}
      </span>
      <span className="text-[9px] text-muted-foreground shrink-0">
        {new Date(latest.created_at).toLocaleDateString(
          lang === "ko" ? "ko-KR" : "en-US",
          { month: "short", day: "numeric" }
        )}
      </span>
    </button>
  );
}
