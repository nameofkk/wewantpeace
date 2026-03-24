"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAppStore } from "@/lib/store";
import { useMe, usePatchProfile } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Mail, Bell, X } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "https://api.wewantpeace.live";
const DISMISSED_KEY = "wwp-newsletter-cta-dismissed";

export function NewsletterCTA() {
  const lang = useAppStore((s) => s.lang);
  const { data: me } = useMe();
  const patchProfile = usePatchProfile();

  const [dismissed, setDismissed] = useState(true); // default hidden until checked
  const [subCount, setSubCount] = useState<number | null>(null);

  // Check dismissed state
  useEffect(() => {
    try {
      const val = localStorage.getItem(DISMISSED_KEY);
      setDismissed(val === "true");
    } catch {
      setDismissed(false);
    }
  }, []);

  // Fetch subscriber count
  useEffect(() => {
    fetch(`${API}/newsletter/stats`)
      .then((r) => r.json())
      .then((d) => setSubCount(d.subscriber_count))
      .catch(() => {});
  }, []);

  const handleDismiss = () => {
    setDismissed(true);
    try {
      localStorage.setItem(DISMISSED_KEY, "true");
    } catch {}
  };

  const isLoggedIn = !!me?.id;
  const isSubscribed = !!me?.marketing_agreed_at;

  const handleToggle = () => {
    if (!isLoggedIn) return;
    if (isSubscribed) {
      patchProfile.mutate({ marketing_agreed_at: "" });
    } else {
      patchProfile.mutate({ marketing_agreed_at: "now" });
    }
  };

  if (dismissed) return null;

  const subscriberText = subCount !== null
    ? t(lang, "newsletter_subscribers").replace("{n}", String(subCount))
    : "";

  return (
    <div className="relative rounded-xl border border-border bg-card p-4 bg-gradient-to-br from-blue-500/[0.03] to-indigo-500/[0.06]">
      {/* Dismiss button */}
      <button
        onClick={handleDismiss}
        className="absolute top-2 right-2 p-1 rounded-full hover:bg-muted/50 transition-colors"
        aria-label="Close"
      >
        <X className="h-3.5 w-3.5 text-muted-foreground/50" />
      </button>

      {/* Header */}
      <div className="flex items-center gap-1.5 mb-3">
        <Mail className="h-3.5 w-3.5 text-blue-400 flex-shrink-0" />
        <span className="text-[11px] font-bold text-foreground">
          {t(lang, "newsletter_title")}
        </span>
      </div>
      <p className="text-[10px] text-muted-foreground mb-3">
        {t(lang, "newsletter_desc")}
      </p>

      {/* Preview thumbnail */}
      <Link href="/newsletter">
        <div className="h-[120px] rounded-lg border border-border/50 overflow-hidden cursor-pointer relative hover:border-blue-500/30 transition-colors mb-3">
          <div className="absolute inset-0 bg-gradient-to-b from-blue-500/5 to-indigo-500/10 flex items-center justify-center">
            <Mail className="h-8 w-8 text-blue-400/20" />
          </div>
          <div
            className="absolute inset-0"
            style={{ maskImage: "linear-gradient(black 60%, transparent)" }}
          />
          <div className="absolute bottom-2 left-0 right-0 text-center">
            <span className="text-[10px] font-bold text-blue-400">
              {t(lang, "newsletter_preview")}
            </span>
          </div>
        </div>
      </Link>

      {/* Toggle row or Login button */}
      {isLoggedIn ? (
        <div className="rounded-lg bg-muted/20 px-3 py-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
            <div>
              <p className="text-[11px] font-medium text-foreground">
                {t(lang, "newsletter_toggle_label")}
              </p>
              <p className="text-[9px] text-muted-foreground">
                {t(lang, "newsletter_toggle_sub")}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isSubscribed && (
              <span className="text-[9px] font-medium text-primary">
                {t(lang, "newsletter_subscribed")}
              </span>
            )}
            <button
              onClick={handleToggle}
              disabled={patchProfile.isPending}
              className={`relative h-5 w-9 rounded-full transition-colors ${
                isSubscribed ? "bg-primary" : "bg-muted/50"
              }`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
                  isSubscribed ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>
        </div>
      ) : (
        <Link href="/login">
          <div className="rounded-lg bg-primary/10 px-3 py-2.5 text-center cursor-pointer hover:bg-primary/15 transition-colors">
            <p className="text-[11px] font-bold text-primary">
              {t(lang, "newsletter_login_subscribe")}
            </p>
          </div>
        </Link>
      )}

      {/* Footer */}
      <p className="text-[9px] text-muted-foreground/50 text-center mt-2">
        {isLoggedIn
          ? isSubscribed
            ? t(lang, "newsletter_next_send")
            : subscriberText
          : t(lang, "newsletter_login_sub")}
      </p>
    </div>
  );
}
