export async function register() {
  // Edge 런타임에는 없는 process.memoryUsage/setInterval 보호
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  // ── 메모리 가드 ──────────────────────────────────────────────────────────
  // /issues/[id], /issues/[id]/og 처럼 고유 ID가 수만 개인 동적 라우트를
  // 장기 실행 프로세스 하나가 계속 처리하면서 RSS가 매일 ~0.5GB씩 늘어나
  // 정체 없이 계속 오르는 패턴이 실측됐다(2026-08-08, 2.46GB→3.77GB/2.65일).
  // og 라우트는 원격 이미지를 fetch해 base64로 인라인한 뒤 next/og(Satori+resvg
  // WASM)로 렌더링하는데, WASM 선형 메모리는 한 번 커지면 프로세스 수명 동안
  // 줄어들지 않는다 — 서로 다른 큰 이미지를 계속 처리할수록 그 최고치가 계속
  // 올라가고 절대 안 내려온다. cacheMaxMemorySize(50MB)로 Next 자체 캐시는
  // 상한을 걸었지만 이 WASM 메모리는 그 상한 밖에 있다.
  //
  // 근본 수정(자체 캐시 핸들러 구현, og 렌더링을 별도 프로세스로 분리)은 범위가
  // 크고 검증 없이 배포하기엔 위험이 커서, 대신 업계 표준 완화책을 쓴다:
  // RSS가 임계값을 넘으면 프로세스를 스스로 종료해 Railway의
  // restartPolicyType: ON_FAILURE(이미 설정됨)가 깨끗한 프로세스로 재기동하게
  // 한다.
  //
  // 임계값 2.0GB는 "비용 절감"이 아니라 "장애 예방"이 기준이다. 실제 배포
  // 로그(2026-08-06 18:49 UTC부터)에서 이 WASM 렌더러가 RSS 약 2.6GB
  // 지점부터 "RuntimeError: memory access out of bounds"로 실제 요청을
  // 계속 실패시키기 시작한 것을 확인했다(발생 후 45시간 동안 시간당
  // 30~147건, 총 수천 건 — 프로세스 자체는 안 죽어서 아무도 못 알아챈
  // 채로 SNS 카드 이미지가 조용히 계속 깨지고 있었다). 2.0GB는 그 지점보다
  // 충분히 아래라 이 크래시 자체가 발생하기 전에 재시작시킨다.
  const RSS_LIMIT_BYTES = 2.0 * 1024 * 1024 * 1024; // 2.0GB — 실측 크래시 발생점(~2.6GB) 아래로 여유
  const CHECK_INTERVAL_MS = 5 * 60 * 1000; // 5분

  setInterval(() => {
    const rss = process.memoryUsage().rss;
    if (rss >= RSS_LIMIT_BYTES) {
      console.error(
        `[memory-guard] RSS ${(rss / 1024 / 1024 / 1024).toFixed(2)}GB >= ` +
          `${(RSS_LIMIT_BYTES / 1024 / 1024 / 1024).toFixed(1)}GB 한도 — ` +
          `재시작을 위해 종료합니다 (Railway ON_FAILURE가 재기동)`,
      );
      // 정상 종료 코드(0)는 Railway가 재시작 대상으로 보지 않는다 — 반드시 비정상 종료.
      process.exit(1);
    }
  }, CHECK_INTERVAL_MS).unref();
}
