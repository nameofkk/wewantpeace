import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "WeWantPeace Issue";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default async function OGImage({ params }: { params: { id: string } }) {
  let issue: { title_ko?: string; title: string; severity: number; topic: string; event_count: number; country_code?: string } | null = null;
  try {
    const res = await fetch(`${API_BASE}/issues/${params.id}`, { next: { revalidate: 120 } });
    if (res.ok) issue = await res.json();
  } catch {}

  if (!issue) {
    return new ImageResponse(
      (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", background: "#0f172a", color: "#fff", fontSize: 48 }}>
          WeWantPeace
        </div>
      ),
      { ...size }
    );
  }

  const title = issue.title_ko || issue.title;
  const bgColor = issue.severity >= 70 ? "#991b1b" : issue.severity >= 40 ? "#c2410c" : "#334155";

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          width: "100%",
          height: "100%",
          background: bgColor,
          padding: "60px",
          fontFamily: "sans-serif",
        }}
      >
        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "rgba(255,255,255,0.7)", fontSize: 24 }}>
            <span>WeWantPeace</span>
          </div>
          {issue.country_code && (
            <div style={{ display: "flex", marginLeft: "auto", background: "rgba(255,255,255,0.15)", borderRadius: "8px", padding: "6px 16px", color: "#fff", fontSize: 20 }}>
              {issue.country_code}
            </div>
          )}
        </div>

        {/* Title */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", flex: 1, justifyContent: "center" }}>
          <div style={{ color: "#fff", fontSize: title.length > 60 ? 36 : 48, fontWeight: 700, lineHeight: 1.2, maxHeight: "240px", overflow: "hidden" }}>
            {title.length > 100 ? title.slice(0, 97) + "..." : title}
          </div>
        </div>

        {/* Bottom stats */}
        <div style={{ display: "flex", gap: "32px", color: "rgba(255,255,255,0.8)", fontSize: 22 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontWeight: 700, color: "#fff", fontSize: 28 }}>{issue.severity}</span>
            <span>Severity</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontWeight: 700, color: "#fff", fontSize: 28 }}>{issue.event_count}</span>
            <span>Reports</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontWeight: 700, color: "#fff", fontSize: 28 }}>{issue.topic}</span>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
