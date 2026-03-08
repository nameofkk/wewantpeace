"use client";

import { X } from "lucide-react";
import Link from "next/link";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

const ONE_WEEK_MS = 7 * 24 * 60 * 60 * 1000;

/**
 * Free 사용자가 스파이크 알림을 3회 이상 확인하면 표시되는 Pro 전환 유도 배너.
 * - 닫기(X) 버튼으로 dismiss → 일주일 후 다시 표시
 * - localStorage (Zustand persist)로 카운트/dismiss 상태 관리
 */
export function UpgradeNudgeBanner() {
  const lang = useAppStore((s) => s.lang);
  const userPlan = useAppStore((s) => s.userPlan);
  const spikeAlertCount = useAppStore((s) => s.spikeAlertCount);
  const spikeAlertDismissedAt = useAppStore((s) => s.spikeAlertDismissedAt);
  const dismissUpgradeNudge = useAppStore((s) => s.dismissUpgradeNudge);

  // 표시 조건: Free 사용자 + 3회 이상 + dismiss 안 했거나 일주일 지남
  const isDismissedRecently =
    spikeAlertDismissedAt != null &&
    Date.now() - spikeAlertDismissedAt < ONE_WEEK_MS;

  if (userPlan !== "free") return null;
  if (spikeAlertCount < 3) return null;
  if (isDismissedRecently) return null;

  return (
    <div className="mx-4 mt-3 mb-1 rounded-xl border border-blue-500/20 bg-blue-500/10 px-4 py-3 relative">
      {/* 닫기 버튼 */}
      <button
        onClick={dismissUpgradeNudge}
        className="absolute top-2 right-2 p-1 rounded-md text-blue-400/60 hover:text-blue-400 hover:bg-blue-500/10 transition-colors"
        aria-label="Close"
      >
        <X className="h-4 w-4" />
      </button>

      <p className="text-xs text-blue-400 leading-relaxed pr-6">
        {t(lang, "upgrade_nudge_message", { count: spikeAlertCount })}
      </p>

      <Link
        href="/upgrade"
        className="mt-2 inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition-colors"
        style={{ background: "linear-gradient(to right, #3b82f6, #6366f1)" }}
      >
        {t(lang, "upgrade_nudge_cta")}
      </Link>
    </div>
  );
}
