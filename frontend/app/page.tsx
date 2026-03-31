"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Root page: client-side redirect.
 * Server-side redirect() returns HTTP 307, which prevents social media
 * crawlers (KakaoTalk, Facebook, etc.) from reading OG meta tags.
 * layout.tsx metadata is served with 200 so OG previews work correctly.
 *
 * SEO: Hidden content for search bots that don't execute JavaScript.
 */
export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    router.replace(done ? "/home" : "/onboarding");
  }, [router]);

  return (
    <div className="sr-only" aria-hidden="true">
      <h1>WeWantPeace — Real-time War &amp; Conflict Tracker</h1>
      <p>
        Track how war and conflict impact your daily life in real time.
        Tension Index across 195 countries, personalized alerts, and global conflict map.
      </p>
      <ul>
        <li>Tension Index: Real-time country-level scores (0–100), updated every 15 minutes</li>
        <li>KScore: AI-powered impact analysis personalized to your country</li>
        <li>Risk Radar: Military, Energy, Trade, Food, Finance — 5-axis risk assessment</li>
        <li>Market Snapshot: Oil, gold, gas prices &amp; exchange rates linked to conflicts</li>
        <li>Global Conflict Map: Heatmap + real-time markers across 195 countries</li>
        <li>Smart Alerts: KScore-based push notifications for your countries of interest</li>
      </ul>
    </div>
  );
}
