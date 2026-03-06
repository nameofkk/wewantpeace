import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";

export const runtime = "edge";

const size = { width: 1200, height: 630 };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const COUNTRY_NAMES: Record<string, { ko: string; en: string }> = {
  UA: { ko: "우크라이나", en: "Ukraine" },
  RU: { ko: "러시아", en: "Russia" },
  CN: { ko: "중국", en: "China" },
  US: { ko: "미국", en: "United States" },
  KR: { ko: "대한민국", en: "South Korea" },
  KP: { ko: "북한", en: "North Korea" },
  JP: { ko: "일본", en: "Japan" },
  TW: { ko: "대만", en: "Taiwan" },
  IL: { ko: "이스라엘", en: "Israel" },
  PS: { ko: "팔레스타인", en: "Palestine" },
  IR: { ko: "이란", en: "Iran" },
  SY: { ko: "시리아", en: "Syria" },
  MM: { ko: "미얀마", en: "Myanmar" },
  AF: { ko: "아프가니스탄", en: "Afghanistan" },
  SD: { ko: "수단", en: "Sudan" },
  YE: { ko: "예멘", en: "Yemen" },
  ET: { ko: "에티오피아", en: "Ethiopia" },
  SO: { ko: "소말리아", en: "Somalia" },
  LB: { ko: "레바논", en: "Lebanon" },
  IQ: { ko: "이라크", en: "Iraq" },
};

const LEVEL_CONFIG = [
  { level: 4, bg: "#DC2626", label: "위험", labelEn: "Critical", barColor: "#EF4444" },
  { level: 3, bg: "#D97706", label: "심각", labelEn: "Serious", barColor: "#F59E0B" },
  { level: 2, bg: "#CA8A04", label: "경계", labelEn: "Elevated", barColor: "#EAB308" },
  { level: 1, bg: "#2563EB", label: "주의", labelEn: "Moderate", barColor: "#3B82F6" },
  { level: 0, bg: "#16A34A", label: "안정", labelEn: "Low", barColor: "#22C55E" },
];

function getLevelConfig(level: number) {
  return LEVEL_CONFIG.find((c) => c.level === level) || LEVEL_CONFIG[LEVEL_CONFIG.length - 1];
}

interface TensionData {
  country_code: string;
  raw_score: number;
  tension_level: number;
  event_score: number;
  accel_score: number;
  spillover_score: number;
  top5_clusters: { title_ko?: string; title: string; image_url?: string; topic?: string }[];
}

interface HistoryPoint {
  time: string;
  raw_score: number;
  tension_level: number;
}

export async function GET(
  _req: NextRequest,
  { params }: { params: { code: string } }
) {
  const code = params.code.toUpperCase();

  let logoSrc: string | null = null;
  try {
    const logoRes = await fetch(
      new URL("../../../../../public/logo-eye.png", import.meta.url)
    );
    const logoBuf = await logoRes.arrayBuffer();
    logoSrc = `data:image/png;base64,${Buffer.from(logoBuf).toString("base64")}`;
  } catch {}

  let tension: TensionData | null = null;
  try {
    const res = await fetch(`${API_BASE}/tension/country/${code}`, {
      next: { revalidate: 300 },
    });
    if (res.ok) tension = await res.json();
  } catch {}

  let history: HistoryPoint[] = [];
  try {
    const res = await fetch(`${API_BASE}/tension/country/${code}/history?range=7d`, {
      next: { revalidate: 300 },
    });
    if (res.ok) history = await res.json();
  } catch {}

  if (!tension) {
    return new ImageResponse(
      (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "100%",
            height: "100%",
            background: "#0F172A",
            color: "#E2E8F0",
            fontSize: 40,
            fontWeight: 800,
            fontFamily: "sans-serif",
          }}
        >
          {logoSrc ? (
            <img src={logoSrc} width={120} height={52} alt="" style={{ marginRight: "20px" }} />
          ) : null}
          WeWantPeace
        </div>
      ),
      { ...size }
    );
  }

  const country = COUNTRY_NAMES[code];
  const countryKo = country ? country.ko : code;
  const countryEn = country ? country.en : code;
  const config = getLevelConfig(tension.tension_level);
  const score = tension.raw_score;
  const scorePercent = Math.min(score, 100);

  // 7일 히스토리 → SVG path for sparkline
  const graphPoints = history.length >= 2 ? history : [];
  const graphWidth = 500;
  const graphHeight = 140;
  let svgPath = "";
  let svgAreaPath = "";
  if (graphPoints.length >= 2) {
    const maxScore = Math.max(...graphPoints.map((p) => p.raw_score), 10);
    const step = graphWidth / (graphPoints.length - 1);
    const pts = graphPoints.map((p, i) => ({
      x: Math.round(i * step),
      y: Math.round(graphHeight - (p.raw_score / maxScore) * (graphHeight - 8)),
    }));
    svgPath = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
    svgAreaPath = `${svgPath} L${pts[pts.length - 1].x},${graphHeight} L${pts[0].x},${graphHeight} Z`;
  }

  // 상위 이슈 이미지를 배경으로 (전체 클러스터에서 첫 번째 이미지 탐색)
  const topImageUrl = tension.top5_clusters?.find((c) => c.image_url)?.image_url ?? null;
  const hasBackground = !!topImageUrl;

  // 상위 이슈 2개 표시
  const topIssues = tension.top5_clusters.slice(0, 2).map((c) => {
    const raw = c.title_ko || c.title;
    return raw.length > 35 ? raw.slice(0, 35) + "…" : raw;
  });

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          width: "100%",
          height: "100%",
          fontFamily: "sans-serif",
          background: "linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)",
          position: "relative",
        }}
      >
        {/* 배경 이미지 (RSS) */}
        {hasBackground ? (
          <img
            src={topImageUrl!}
            width={1200}
            height={630}
            alt=""
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: 1200,
              height: 630,
              objectFit: "cover",
              filter: "brightness(0.5) saturate(0.8)",
            }}
          />
        ) : null}

        {/* 배경 패턴 — 은은한 그라데이션 (이미지 없을 때만) */}
        {!hasBackground && (
          <div
            style={{
              display: "flex",
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              background: "linear-gradient(135deg, rgba(30,41,59,0.5) 0%, transparent 50%, rgba(30,41,59,0.5) 100%)",
            }}
          />
        )}

        {/* 상단 악센트 라인 */}
        <div
          style={{
            display: "flex",
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "6px",
            background: `linear-gradient(90deg, transparent 0%, ${config.barColor} 30%, ${config.barColor} 70%, transparent 100%)`,
          }}
        />

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            width: "100%",
            height: "100%",
            padding: "44px 56px 40px",
            position: "relative",
            background: hasBackground
              ? "linear-gradient(180deg, rgba(15,23,42,0.4) 0%, rgba(15,23,42,0.75) 40%, rgba(15,23,42,0.9) 100%)"
              : "transparent",
          }}
        >
          {/* ── 상단: 로고 + 레벨 배지 ── */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
              {logoSrc ? (
                <img
                  src={logoSrc}
                  width={140}
                  height={60}
                  alt=""
                  style={{ width: "140px", height: "60px" }}
                />
              ) : null}
              <span style={{ color: "#94A3B8", fontSize: 28, fontWeight: 800, letterSpacing: "-0.3px" }}>
                WeWantPeace
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span style={{ color: "#94A3B8", fontSize: 20, fontWeight: 700 }}>
                실시간 세계정세 모니터링
              </span>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  background: config.bg,
                  color: config.bg === "#CA8A04" ? "#1A1A2E" : "#FFFFFF",
                  padding: "10px 26px",
                  borderRadius: "24px",
                  fontSize: 20,
                  fontWeight: 800,
                  letterSpacing: "0.5px",
                }}
              >
                {config.label} · {config.labelEn}
              </div>
            </div>
          </div>

          {/* ── 중앙: 국가명 + 점수 + 그래프 ── */}
          <div
            style={{
              display: "flex",
              flex: 1,
              alignItems: "center",
              gap: "48px",
              marginTop: "20px",
            }}
          >
            {/* 왼쪽: 국가명 + 점수 + 게이지 */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                flex: 1,
                gap: "4px",
              }}
            >
              <div style={{ display: "flex", alignItems: "baseline", gap: "16px" }}>
                <span
                  style={{
                    color: "#FFFFFF",
                    fontSize: 68,
                    fontWeight: 900,
                    lineHeight: 1.1,
                    letterSpacing: "-1.5px",
                  }}
                >
                  {countryKo}
                </span>
                <span style={{ color: "#94A3B8", fontSize: 28, fontWeight: 700 }}>
                  {countryEn}
                </span>
              </div>

              {/* 점수 */}
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: "12px",
                  marginTop: "16px",
                }}
              >
                <span
                  style={{
                    color: config.barColor,
                    fontSize: 88,
                    fontWeight: 900,
                    letterSpacing: "-3px",
                    lineHeight: 1,
                  }}
                >
                  {score.toFixed(1)}
                </span>
                <span style={{ color: "#94A3B8", fontSize: 24, fontWeight: 800 }}>
                  / 100
                </span>
              </div>
              <span style={{ color: "#94A3B8", fontSize: 22, fontWeight: 700, marginTop: "2px" }}>
                Tension Index
              </span>

              {/* 게이지 바 */}
              <div
                style={{
                  display: "flex",
                  width: "100%",
                  maxWidth: "360px",
                  height: "16px",
                  background: "#1E293B",
                  borderRadius: "6px",
                  marginTop: "16px",
                  overflow: "hidden",
                  border: "1px solid #334155",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    width: `${scorePercent}%`,
                    height: "100%",
                    background: `linear-gradient(90deg, ${config.barColor}88, ${config.barColor})`,
                    borderRadius: "6px",
                  }}
                />
              </div>
            </div>

            {/* 오른쪽: 7일 추이 그래프 */}
            {graphPoints.length >= 2 && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  width: "500px",
                  gap: "8px",
                }}
              >
                <span style={{ color: "#94A3B8", fontSize: 18, fontWeight: 700 }}>
                  7일 추이
                </span>
                <div
                  style={{
                    display: "flex",
                    position: "relative",
                    width: `${graphWidth}px`,
                    height: `${graphHeight}px`,
                    background: "rgba(15,23,42,0.6)",
                    borderRadius: "12px",
                    border: "1px solid #1E293B",
                    padding: "0",
                  }}
                >
                  <svg
                    width={graphWidth}
                    height={graphHeight}
                    viewBox={`0 0 ${graphWidth} ${graphHeight}`}
                    style={{ position: "absolute", top: 0, left: 0 }}
                  >
                    <defs>
                      <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={config.barColor} stopOpacity="0.3" />
                        <stop offset="100%" stopColor={config.barColor} stopOpacity="0.02" />
                      </linearGradient>
                    </defs>
                    <path d={svgAreaPath} fill="url(#areaGrad)" />
                    <path d={svgPath} fill="none" stroke={config.barColor} strokeWidth="4" />
                    {/* 마지막 포인트 강조 */}
                    {(() => {
                      const maxS = Math.max(...graphPoints.map((p) => p.raw_score), 10);
                      const lastPt = graphPoints[graphPoints.length - 1];
                      const lx = graphWidth;
                      const ly = graphHeight - (lastPt.raw_score / maxS) * (graphHeight - 8);
                      return <circle cx={lx - 1} cy={ly} r="7" fill={config.barColor} />;
                    })()}
                  </svg>
                </div>
                {/* 날짜 라벨 */}
                <div style={{ display: "flex", justifyContent: "space-between", width: `${graphWidth}px` }}>
                  <span style={{ color: "#64748B", fontSize: 15, fontWeight: 600 }}>
                    {new Date(graphPoints[0].time).toLocaleDateString("ko-KR", { month: "short", day: "numeric" })}
                  </span>
                  <span style={{ color: "#64748B", fontSize: 15, fontWeight: 600 }}>
                    {new Date(graphPoints[graphPoints.length - 1].time).toLocaleDateString("ko-KR", { month: "short", day: "numeric" })}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* ── 하단: 주요 이슈 + 브랜드 ── */}
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              justifyContent: "space-between",
              marginTop: "auto",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              {topIssues.length > 0 && (
                <span style={{ color: "#64748B", fontSize: 16, fontWeight: 700, marginBottom: "2px" }}>
                  주요 이슈
                </span>
              )}
              {topIssues.map((t, i) => (
                <span key={i} style={{ color: "#CBD5E1", fontSize: 20, fontWeight: 600 }}>
                  {i + 1}. {t}
                </span>
              ))}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ color: "#334155", fontSize: 18 }}>|</span>
              <span style={{ color: "#94A3B8", fontSize: 20, fontWeight: 700 }}>
                wewantpeace.live
              </span>
            </div>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
