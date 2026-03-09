/**
 * Paywall frequency cap — 클라이언트 로컬 제어.
 * PRD 6.4: 세션당 1회 per trigger, 기본 쿨다운 30분
 */

import { getSessionId } from "./session";

const COOLDOWN_MS = 30 * 60 * 1000; // 30분
const FALLBACK_COOLDOWN_MS = 60 * 60 * 1000; // 서버 장애 폴백: 1시간

type PaywallTrigger =
  | "map_locked"
  | "verified_locked"
  | "kscore_threshold_locked"
  | "watch_country_limit_locked";

function getSessionCapKey(trigger: string): string {
  return `wwp_paywall_session_${getSessionId()}_${trigger}`;
}

function getCooldownKey(trigger: string): string {
  return `wwp_paywall_cd_${trigger}`;
}

/**
 * 페이월 표시 가능 여부 체크
 * - 세션당 동일 trigger 1회
 * - 글로벌 쿨다운 30분
 */
export function shouldShowPaywall(trigger: PaywallTrigger): boolean {
  try {
    // 1. 세션당 동일 trigger 1회 제한
    const sessionKey = getSessionCapKey(trigger);
    if (localStorage.getItem(sessionKey)) {
      return false;
    }

    // 2. 쿨다운 체크 (모든 trigger 공유)
    const cdKey = getCooldownKey(trigger);
    const lastShown = Number(localStorage.getItem(cdKey) || "0");
    if (lastShown && Date.now() - lastShown < COOLDOWN_MS) {
      return false;
    }

    return true;
  } catch {
    // localStorage 접근 실패 시 보수적으로 미표시
    return false;
  }
}

/**
 * 페이월 표시 기록
 */
export function recordPaywallShown(trigger: PaywallTrigger): void {
  try {
    // 세션 cap 기록
    const sessionKey = getSessionCapKey(trigger);
    localStorage.setItem(sessionKey, "1");

    // 쿨다운 기록
    const cdKey = getCooldownKey(trigger);
    localStorage.setItem(cdKey, String(Date.now()));
  } catch {
    // ignore
  }
}

/**
 * 서버 장애 시 보수적 폴백 쿨다운 적용
 */
export function applyFallbackCooldown(): void {
  try {
    const now = String(Date.now());
    localStorage.setItem(getCooldownKey("map_locked"), now);
    localStorage.setItem(getCooldownKey("verified_locked"), now);
    localStorage.setItem(getCooldownKey("kscore_threshold_locked"), now);
    localStorage.setItem(getCooldownKey("watch_country_limit_locked"), now);
  } catch {
    // ignore
  }
}
