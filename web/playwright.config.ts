import { defineConfig, devices } from '@playwright/test'

const PORTA = 4317

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORTA}`,
    trace: 'on-first-retry',
    locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    // Preview do build (e não `dev`) para o service worker existir e o teste
    // offline exercitar o shell real.
    command: `npm run build && npm run preview -- --host 127.0.0.1 --port ${PORTA} --strictPort`,
    url: `http://127.0.0.1:${PORTA}`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      VITE_SUPABASE_URL: 'https://fake.supabase.co',
      VITE_SUPABASE_ANON_KEY: 'chave-anon-de-teste',
      VITE_API_URL: 'https://api.e2e.test',
    },
  },
})
