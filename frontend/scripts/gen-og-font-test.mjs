/**
 * 4개 헤드라인 폰트 × 2개 언어 = 8개 OG 이미지 생성
 * Usage: node scripts/gen-og-font-test.mjs
 */
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { writeFileSync, mkdirSync } from "fs";

const WIDTH = 1200;
const HEIGHT = 630;

// ── 폰트 URL 정의 ──
const FONTS = {
  abril: {
    name: "Abril Fatface",
    url: "https://fonts.gstatic.com/s/abrilfatface/v25/zOL64pLDlL1D99S8g8PtiKchm-A.ttf",
    weight: 400,
    label: "Abril Fatface",
  },
  anton: {
    name: "Anton",
    url: "https://fonts.gstatic.com/s/anton/v27/1Ptgg87LROyAm0K0.ttf",
    weight: 400,
    label: "Anton",
  },
  archivo: {
    name: "Archivo Black",
    url: "https://fonts.gstatic.com/s/archivoblack/v23/HTxqL289NzCGg4MzN6KJ7eW6OYs.ttf",
    weight: 400,
    label: "Archivo Black",
  },
  ultra: {
    name: "Ultra",
    url: "https://fonts.gstatic.com/s/ultra/v25/zOLy4prXmrtY-tT6.ttf",
    weight: 400,
    label: "Ultra",
  },
};

const NOTO_URL =
  "https://fonts.gstatic.com/s/notosanskr/v36/PbyxFmXiEBPT4ITbgNA5Cgms3VYcOA-vvnIzzuoyeLTq8H4hfeE.ttf";
const INTER_URL =
  "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYMZg.ttf";

async function fetchFont(url) {
  const res = await fetch(url);
  return await res.arrayBuffer();
}

function buildJsx(fontName, lang) {
  const isEn = lang === "en";
  const headline = isEn ? "Ukraine" : "우크라이나";
  const subName = isEn ? "우크라이나" : "Ukraine";
  const severity = "Critical";
  const score = "72.4";
  const barColor = "#EF4444";
  const bg = "#DC2626";
  const tagline = isEn
    ? "Real-time Global Conflict Monitor"
    : "실시간 글로벌 분쟁 모니터링";
  const fontLabel = `Font: ${fontName}`;

  return {
    type: "div",
    props: {
      style: {
        display: "flex",
        width: "100%",
        height: "100%",
        fontFamily: "'Noto Sans KR', 'Inter', sans-serif",
        background:
          "linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)",
        position: "relative",
      },
      children: [
        // 상단 악센트 라인
        {
          type: "div",
          props: {
            style: {
              display: "flex",
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "6px",
              background: `linear-gradient(90deg, transparent 0%, ${barColor} 30%, ${barColor} 70%, transparent 100%)`,
            },
          },
        },
        // 메인 컨텐츠
        {
          type: "div",
          props: {
            style: {
              display: "flex",
              flexDirection: "column",
              width: "100%",
              height: "100%",
              padding: "44px 56px 40px",
              position: "relative",
            },
            children: [
              // 상단: 로고 + 뱃지
              {
                type: "div",
                props: {
                  style: {
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  },
                  children: [
                    {
                      type: "span",
                      props: {
                        style: {
                          color: "#94A3B8",
                          fontSize: 28,
                          fontWeight: 800,
                          letterSpacing: "-0.3px",
                        },
                        children: "WeWantPeace",
                      },
                    },
                    {
                      type: "div",
                      props: {
                        style: {
                          display: "flex",
                          alignItems: "center",
                          gap: "12px",
                        },
                        children: [
                          {
                            type: "span",
                            props: {
                              style: {
                                color: "#94A3B8",
                                fontSize: 20,
                                fontWeight: 700,
                              },
                              children: tagline,
                            },
                          },
                          {
                            type: "div",
                            props: {
                              style: {
                                display: "flex",
                                alignItems: "center",
                                background: bg,
                                color: "#FFFFFF",
                                padding: "10px 26px",
                                borderRadius: "24px",
                                fontSize: 20,
                                fontWeight: 800,
                              },
                              children: severity,
                            },
                          },
                        ],
                      },
                    },
                  ],
                },
              },
              // 중앙: 국가명 + 점수
              {
                type: "div",
                props: {
                  style: {
                    display: "flex",
                    flex: 1,
                    alignItems: "center",
                    gap: "48px",
                    marginTop: "20px",
                  },
                  children: [
                    {
                      type: "div",
                      props: {
                        style: {
                          display: "flex",
                          flexDirection: "column",
                          flex: 1,
                          gap: "4px",
                        },
                        children: [
                          // 국가명 헤드라인
                          {
                            type: "div",
                            props: {
                              style: {
                                display: "flex",
                                alignItems: "baseline",
                                gap: "16px",
                              },
                              children: [
                                {
                                  type: "span",
                                  props: {
                                    style: {
                                      color: "#FFFFFF",
                                      fontSize: 68,
                                      fontWeight: 400,
                                      fontFamily: `'${fontName}', 'Noto Sans KR', serif`,
                                      lineHeight: 1.1,
                                      letterSpacing: "-1.5px",
                                    },
                                    children: headline,
                                  },
                                },
                                {
                                  type: "span",
                                  props: {
                                    style: {
                                      color: "#94A3B8",
                                      fontSize: 28,
                                      fontWeight: 700,
                                    },
                                    children: subName,
                                  },
                                },
                              ],
                            },
                          },
                          // 점수
                          {
                            type: "div",
                            props: {
                              style: {
                                display: "flex",
                                alignItems: "baseline",
                                gap: "12px",
                                marginTop: "16px",
                              },
                              children: [
                                {
                                  type: "span",
                                  props: {
                                    style: {
                                      color: barColor,
                                      fontSize: 88,
                                      fontWeight: 400,
                                      fontFamily: `'${fontName}', sans-serif`,
                                      letterSpacing: "-3px",
                                      lineHeight: 1,
                                    },
                                    children: score,
                                  },
                                },
                                {
                                  type: "span",
                                  props: {
                                    style: {
                                      color: "#94A3B8",
                                      fontSize: 24,
                                      fontWeight: 800,
                                    },
                                    children: "/ 100",
                                  },
                                },
                              ],
                            },
                          },
                          {
                            type: "span",
                            props: {
                              style: {
                                color: "#94A3B8",
                                fontSize: 22,
                                fontWeight: 700,
                                marginTop: "2px",
                              },
                              children: "Tension Index",
                            },
                          },
                          // 게이지 바
                          {
                            type: "div",
                            props: {
                              style: {
                                display: "flex",
                                width: "100%",
                                maxWidth: "360px",
                                height: "16px",
                                background: "#1E293B",
                                borderRadius: "6px",
                                marginTop: "16px",
                                overflow: "hidden",
                                border: "1px solid #334155",
                              },
                              children: [
                                {
                                  type: "div",
                                  props: {
                                    style: {
                                      display: "flex",
                                      width: "72.4%",
                                      height: "100%",
                                      background: `linear-gradient(90deg, ${barColor}88, ${barColor})`,
                                      borderRadius: "6px",
                                    },
                                  },
                                },
                              ],
                            },
                          },
                        ],
                      },
                    },
                  ],
                },
              },
              // 하단: 폰트 라벨 + 브랜드
              {
                type: "div",
                props: {
                  style: {
                    display: "flex",
                    alignItems: "flex-end",
                    justifyContent: "space-between",
                    marginTop: "auto",
                  },
                  children: [
                    {
                      type: "span",
                      props: {
                        style: {
                          color: "#FBBF24",
                          fontSize: 22,
                          fontWeight: 700,
                          background: "rgba(251,191,36,0.15)",
                          padding: "6px 16px",
                          borderRadius: "8px",
                        },
                        children: fontLabel,
                      },
                    },
                    {
                      type: "span",
                      props: {
                        style: {
                          color: "#94A3B8",
                          fontSize: 20,
                          fontWeight: 700,
                        },
                        children: "wewantpeace.live",
                      },
                    },
                  ],
                },
              },
            ],
          },
        },
      ],
    },
  };
}

async function main() {
  console.log("Fetching fonts...");
  const [notoData, interData] = await Promise.all([
    fetchFont(NOTO_URL),
    fetchFont(INTER_URL),
  ]);

  const fontDataMap = {};
  for (const [key, f] of Object.entries(FONTS)) {
    console.log(`  Fetching ${f.label}...`);
    fontDataMap[key] = await fetchFont(f.url);
  }

  mkdirSync("/tmp/og-font-test", { recursive: true });

  for (const [key, f] of Object.entries(FONTS)) {
    for (const lang of ["ko", "en"]) {
      const fonts = [
        { name: f.name, data: fontDataMap[key], weight: f.weight, style: "normal" },
        { name: "Noto Sans KR", data: notoData, weight: 900, style: "normal" },
        { name: "Inter", data: interData, weight: 600, style: "normal" },
      ];

      const jsx = buildJsx(f.name, lang);
      console.log(`Rendering ${key}_${lang}...`);

      const svg = await satori(jsx, {
        width: WIDTH,
        height: HEIGHT,
        fonts,
      });

      const resvg = new Resvg(svg, {
        fitTo: { mode: "width", value: WIDTH },
      });
      const png = resvg.render().asPng();

      const filename = `/tmp/og-font-test/${key}_${lang}.png`;
      writeFileSync(filename, png);
      console.log(`  Saved: ${filename}`);
    }
  }

  console.log("Done! 8 images generated.");
}

main().catch(console.error);
