/**
 * Session management for paywall frequency capping.
 * PRD 6.5: 30분 이상 비활성 = 새 세션
 */

const SESSION_TIMEOUT_MS = 30 * 60 * 1000; // 30분
const STORAGE_KEY = "wwp_session";
const LAST_ACTIVE_KEY = "wwp_last_active";

interface SessionData {
  id: string;
  startedAt: number;
}

function generateSessionId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function getSession(): SessionData | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function createSession(): SessionData {
  const session: SessionData = {
    id: generateSessionId(),
    startedAt: Date.now(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
  return session;
}

/** 마지막 활동 시간 업데이트 */
export function updateLastActive(): void {
  localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
}

/** 30분 이상 비활성이면 새 세션인지 체크 */
export function isNewSession(): boolean {
  const lastActive = Number(localStorage.getItem(LAST_ACTIVE_KEY) || "0");
  if (!lastActive) return true;
  return Date.now() - lastActive >= SESSION_TIMEOUT_MS;
}

/**
 * 세션 체크 & 필요 시 리셋.
 * visibilitychange 핸들러에서 호출.
 * @returns 새 세션이 시작되었으면 true
 */
export function checkAndResetSession(): boolean {
  if (isNewSession()) {
    createSession();
    // 새 세션 시작 시 paywall cap도 리셋
    try {
      const capKeys = Object.keys(localStorage).filter((k) =>
        k.startsWith("wwp_paywall_")
      );
      for (const key of capKeys) {
        localStorage.removeItem(key);
      }
    } catch {
      // ignore
    }
    return true;
  }
  updateLastActive();
  return false;
}

/** 현재 세션 ID 반환 (없으면 생성) */
export function getSessionId(): string {
  const session = getSession();
  if (session && !isNewSession()) {
    return session.id;
  }
  return createSession().id;
}
