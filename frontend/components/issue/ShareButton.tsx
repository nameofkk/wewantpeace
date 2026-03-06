"use client";

import { useState } from "react";
import { Share2, Check } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { trackEvent } from "@/lib/analytics";

export function ShareButton({
  issueId,
  url: urlProp,
  title,
  analyticsEvent = "issue_share",
}: {
  issueId?: string;
  url?: string;
  title: string;
  analyticsEvent?: string;
}) {
  const lang = useAppStore((s) => s.lang);
  const [copied, setCopied] = useState(false);

  const url = urlProp ?? `https://www.wewantpeace.live/issues/${issueId}`;

  async function handleShare() {
    trackEvent(analyticsEvent, { url, method: "unknown" });

    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({
          title: t(lang, "share_title", { title }),
          url,
        });
        trackEvent(analyticsEvent, { url, method: "native" });
        return;
      } catch {
        // user cancelled or not supported
      }
    }

    // Fallback: clipboard
    try {
      await navigator.clipboard.writeText(url);
      trackEvent(analyticsEvent, { url, method: "clipboard" });
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // silent fail
    }
  }

  return (
    <button
      onClick={handleShare}
      className="flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
    >
      {copied ? (
        <>
          <Check className="h-3.5 w-3.5" />
          {t(lang, "share_copied")}
        </>
      ) : (
        <>
          <Share2 className="h-3.5 w-3.5" />
          {t(lang, "share_button")}
        </>
      )}
    </button>
  );
}
