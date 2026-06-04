const { chromium } = require("playwright");
const path = require("path");

const SCREENSHOTS_DIR = path.join(__dirname, "..", "docs", "images");
const BASE_URL = "https://www.wewantpeace.live";

// 온보딩/웰컴모달/앱배너 건너뛰기용 localStorage 주입 스크립트
const SKIP_ONBOARDING_SCRIPT = `
  localStorage.setItem("onboarding_done", "true");
  localStorage.setItem("wwp_welcome_seen", String(Date.now()));
  localStorage.setItem("wwp_lang", "en");
  localStorage.setItem("smart_app_banner_dismissed", "true");
  localStorage.setItem("pwa_install_dismissed", "true");
`;

async function capture() {
  const fs = require("fs");
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });

  // ── Desktop context ──
  const desktop = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2,
    locale: "en-US",
  });
  const page = await desktop.newPage();

  // localStorage 설정을 위해 먼저 사이트 접속 (도메인이 일치해야 localStorage 접근 가능)
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.evaluate(SKIP_ONBOARDING_SCRIPT);
  await page.waitForTimeout(500);

  // ── 1. 홈 화면 (이슈 목록) ──
  await page.goto(`${BASE_URL}/home?lang=en`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(4000);
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, "01-home-desktop.png"),
    fullPage: false,
  });
  console.log("✅ 01-home-desktop.png");

  // ── 2. 이슈 상세 페이지 (KScore 높은 이슈) ──
  await page.goto(`${BASE_URL}/issues/825a48b4-2c03-4f7f-b7ad-48f9e316b1e5?lang=en`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(4000);
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, "02-issue-detail.png"),
    fullPage: false,
  });
  console.log("✅ 02-issue-detail.png");

  // ── 3. 긴장도 지수 페이지 ──
  await page.goto(`${BASE_URL}/tension?lang=en`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(4000);
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, "03-tension-desktop.png"),
    fullPage: false,
  });
  console.log("✅ 03-tension-desktop.png");

  // ── 4. 국가별 이슈 페이지 (이스라엘) ──
  await page.goto(`${BASE_URL}/issues/country/IL?lang=en`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(4000);
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, "04-country-issues.png"),
    fullPage: false,
  });
  console.log("✅ 04-country-issues.png");

  // ── 5. 모바일 뷰 (홈) ──
  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    locale: "en-US",
    isMobile: true,
  });
  const mPage = await mobile.newPage();

  // 모바일 컨텍스트에도 localStorage 설정
  await mPage.goto(BASE_URL, { waitUntil: "domcontentloaded", timeout: 30000 });
  await mPage.evaluate(SKIP_ONBOARDING_SCRIPT);
  await mPage.waitForTimeout(500);

  await mPage.goto(`${BASE_URL}/home?lang=en`, { waitUntil: "networkidle", timeout: 30000 });
  await mPage.waitForTimeout(4000);
  await mPage.screenshot({
    path: path.join(SCREENSHOTS_DIR, "05-mobile-home.png"),
    fullPage: false,
  });
  console.log("✅ 05-mobile-home.png");

  // ── 6. 모바일 뷰 (긴장도) ──
  await mPage.goto(`${BASE_URL}/tension?lang=en`, { waitUntil: "networkidle", timeout: 30000 });
  await mPage.waitForTimeout(4000);
  await mPage.screenshot({
    path: path.join(SCREENSHOTS_DIR, "06-mobile-tension.png"),
    fullPage: false,
  });
  console.log("✅ 06-mobile-tension.png");

  await browser.close();
  console.log("\n📁 Screenshots saved to:", SCREENSHOTS_DIR);
}

capture().catch(console.error);
