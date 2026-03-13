import { defineConfig } from '@apps-in-toss/web-framework/config';

export default defineConfig({
  appName: 'wewantpeace',
  brand: {
    displayName: '위원트피스',
    primaryColor: '#1A1A2E',
    // NOTE: 로고 미표시 시 토스 콘솔 > 앱 정보에서 이미지 우클릭 → 링크 복사한 URL로 교체
    icon: 'https://www.wewantpeace.live/toss-logo.png',
  },
  web: {
    host: 'localhost',
    port: 3000,
    commands: {
      dev: 'next dev',
      build: 'next build',
    },
  },
  webViewProps: {
    type: 'partner',
  },
  navigationBar: {
    withBackButton: true,
    withHomeButton: false,
  },
  permissions: [],
  outdir: '.next-toss',
});
