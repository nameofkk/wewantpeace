import { defineConfig } from '@apps-in-toss/web-framework/config';

export default defineConfig({
  appName: 'wewantpeace',
  brand: {
    displayName: 'Wewantpeace',
    primaryColor: '#1A1A2E',
    icon: '/logo.png',
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
