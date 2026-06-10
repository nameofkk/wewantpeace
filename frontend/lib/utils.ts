import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { useEffect } from "react";
import { t, type Lang, type TranslationKey } from "@/lib/i18n";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 브라우저 탭 제목을 언어별로 설정하는 훅 */
export function usePageTitle(lang: Lang, key: TranslationKey) {
  useEffect(() => {
    document.title = t(lang, key);
  }, [lang, key]);
}

/**
 * 금액 표시용 단위 변환 헬퍼.
 * DB·API는 결제 금액을 "USD 센트" 정수로 다룬다 (예: 699 = $6.99, 월 매출 합계도 센트 합).
 * 화면에 그대로 뿌리면 100배로 부풀려지므로, 표시 직전에 100으로 나눠 통화 형식으로 변환한다.
 *   formatMoneyFromCents(699)            → "$6.99"
 *   formatMoneyFromCents(123400)         → "$1,234.00"
 *   formatMoneyFromCents(699, "EUR")     → "€6.99"
 */
export function formatMoneyFromCents(cents: number, currency = "USD", locale = "en-US"): string {
  return (cents / 100).toLocaleString(locale, {
    style: "currency",
    currency,
  });
}

export const TENSION_LEVELS = {
  0: { label: "안정", color: "text-emerald-400", bg: "bg-emerald-500/20", border: "border-emerald-500/50" },
  1: { label: "주의", color: "text-amber-300",   bg: "bg-amber-500/25",   border: "border-amber-400/60" },
  2: { label: "경계", color: "text-orange-300",  bg: "bg-orange-500/30",  border: "border-orange-400/70" },
  3: { label: "심각", color: "text-red-400",     bg: "bg-red-500/35",     border: "border-red-500/80" },
  4: { label: "극심", color: "text-red-100",     bg: "bg-red-900/50",     border: "border-red-800/90" },
} as const;

export const SOURCE_TIERS = {
  A: { label: "공식", color: "text-yellow-400", bg: "bg-yellow-400/10" },
  B: { label: "검증", color: "text-slate-400", bg: "bg-slate-400/10" },
  C: { label: "OSINT", color: "text-amber-700", bg: "bg-amber-700/10" },
  D: { label: "미확인", color: "text-gray-500", bg: "bg-gray-500/10" },
} as const;

/**
 * 제목 정리: "[국가] 토픽 · " 접두어 제거.
 * "[미국] 무장 충돌 · 이란 공습" → "이란 공습"
 * 일반 제목은 그대로 반환.
 */
export function stripTitlePrefix(title: string): string {
  return title.replace(/^\[.+?\]\s*.+?\s*·\s*/, "").trim();
}

/** 해시태그만으로 이루어진 쓰레기 제목인지 판별 */
export function isJunkTitle(title: string): boolean {
  const stripped = title.replace(/#\S+/g, "").trim();
  return stripped.length < 4;
}

// 영어 국가명 → 국가코드 매핑 (해시태그에서 국가 추출용)
const NAME_TO_CODE: Record<string, string> = {
  USA: "US", Iran: "IR", Iraq: "IQ", Israel: "IL", Palestine: "PS",
  Russia: "RU", Ukraine: "UA", China: "CN", Syria: "SY", Lebanon: "LB",
  Yemen: "YE", Turkey: "TR", Pakistan: "PK", Afghanistan: "AF",
  India: "IN", Japan: "JP", Korea: "KR", DPRK: "KP", Taiwan: "TW",
  Myanmar: "MM", Somalia: "SO", Sudan: "SD", Libya: "LY", Niger: "NE",
  Mali: "ML", Chad: "TD", Ethiopia: "ET", Eritrea: "ER", Congo: "CD",
  Nigeria: "NG", Egypt: "EG", Mexico: "MX", Colombia: "CO", Venezuela: "VE",
  Belarus: "BY", Georgia: "GE", Armenia: "AM", Azerbaijan: "AZ",
  Serbia: "RS", Kosovo: "XK", Philippines: "PH", Indonesia: "ID",
  Thailand: "TH", Vietnam: "VN", Cambodia: "KH", Laos: "LA",
};

/**
 * 쓰레기 제목에서 국가명 추출 + 토픽 조합으로 의미있는 제목 생성.
 * "#USA #Iran" + topic "conflict" → "미국·이란 무장 충돌" (ko) / "USA-Iran Conflict" (en)
 * countryCode: 클러스터의 country_code 필드 (해시태그 추출 실패 시 폴백)
 */
export function buildSmartTitle(
  rawTitle: string,
  topic: string,
  lang: "ko" | "en",
  getCountryNameFn: (code: string, lang: string) => string,
  countryCode?: string | null,
): string {
  // 해시태그에서 국가 추출
  const tags = rawTitle.match(/#(\w+)/g)?.map((t) => t.slice(1)) || [];

  // 국가가 아닌 해시태그 (ME, EU 등 지역 약어) 제외
  const NON_COUNTRY_CODES = new Set(["ME", "EU", "UN"]);

  const countryNames: string[] = [];
  for (const tag of tags) {
    const upper = tag.toUpperCase();
    // 직접 국가코드인 경우 (2글자) — 비-국가 약어 제외
    if (upper.length === 2 && !NON_COUNTRY_CODES.has(upper)) {
      countryNames.push(getCountryNameFn(upper, lang));
      continue;
    }
    // 영어 국가명인 경우
    const code = NAME_TO_CODE[tag] || NAME_TO_CODE[tag.charAt(0).toUpperCase() + tag.slice(1).toLowerCase()];
    if (code) {
      countryNames.push(getCountryNameFn(code, lang));
    }
  }

  // 해시태그에서 국가 못 찾았으면 cluster.country_code 사용
  if (countryNames.length === 0 && countryCode) {
    countryNames.push(getCountryNameFn(countryCode, lang));
  }

  // 중복 제거
  const unique = [...new Set(countryNames)];
  const topicLabel = lang === "ko"
    ? (TOPIC_LABELS[topic] || topic)
    : (TOPIC_LABELS_EN[topic] || topic);

  if (unique.length > 0) {
    const sep = lang === "ko" ? "·" : "-";
    return `${unique.join(sep)} ${topicLabel}`;
  }

  // 국가 추출 실패 시 토픽만
  return topicLabel;
}

export const TOPIC_LABELS: Record<string, string> = {
  conflict:  "분쟁",
  terror:    "테러",
  coup:      "쿠데타",
  sanctions: "제재",
  cyber:     "사이버",
  protest:   "시위",
  diplomacy: "외교",
  maritime:  "해상",
  disaster:  "재난·재해",
  health:    "감염병·보건",
  unknown:   "기타",
};

/**
 * 온보딩 완료 표시: localStorage + cookie 동시 설정.
 * middleware.ts(SSR)는 cookie를, client 코드는 localStorage를 체크하므로 반드시 둘 다 설정해야 함.
 */
export function markOnboardingDone() {
  localStorage.setItem("onboarding_done", "true");
  document.cookie = "onboarding_done=true; path=/; max-age=31536000; SameSite=Lax";
}

export const TOPIC_LABELS_EN: Record<string, string> = {
  conflict:  "Conflict",
  terror:    "Terror",
  coup:      "Coup",
  sanctions: "Sanctions",
  cyber:     "Cyber",
  protest:   "Protest",
  diplomacy: "Diplomacy",
  maritime:  "Maritime",
  disaster:  "Disaster",
  health:    "Health",
  unknown:   "Other",
};
