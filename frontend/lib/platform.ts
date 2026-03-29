export const isTossMiniApp = () => {
  // 1) 빌드 타임 환경변수 (build-toss.sh에서 설정)
  if (process.env.NEXT_PUBLIC_IS_TOSS_MINIAPP === 'true') return true;
  // 2) 런타임 호스트네임 감지 (빌드가 오래되어도 올바른 경로 사용)
  if (typeof window !== 'undefined' && window.location.hostname.endsWith('.tossmini.com')) return true;
  return false;
};
