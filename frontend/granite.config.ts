import { defineConfig } from '@apps-in-toss/web-framework/config';

export default defineConfig({
  appName: 'wewantpeace',
  brand: {
    displayName: 'WeWantPeace',
    primaryColor: '#1A1A2E',
    icon: '',
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
