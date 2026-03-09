import { defineConfig } from '@apps-in-toss/web-framework/config';

export default defineConfig({
  appName: 'wewantpeace',
  brand: {
    displayName: '위원트피스',
    primaryColor: '#1A1A2E',
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
  permissions: [],
  outdir: '.next-toss',
});
