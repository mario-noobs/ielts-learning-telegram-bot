/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: [
      'src/lib/**/*.test.{ts,tsx}',
      'src/components/ui/Button.test.tsx',
      'src/components/ui/Input.test.tsx',
      'src/components/MultipleChoiceQuestion.test.tsx',
      'src/components/Pagination.test.tsx',
      'src/components/AdminGate.test.tsx',
      'src/components/AppShell.test.tsx',
      'src/components/PlanBadge.test.tsx',
      'src/components/GroupJoinCTA.test.tsx',
      'src/components/admin/AdminButton.test.tsx',
      'src/components/admin/AdminInput.test.tsx',
      'src/contexts/AuthContext.test.tsx',
      'src/pages/DailyWordsPage.test.tsx',
      'src/pages/DailyFillBlankPage.test.tsx',
      'src/pages/FlashcardReviewPage.test.tsx',
      'src/pages/VocabHubPage.test.tsx',
      'src/pages/VocabHomePage.test.tsx',
      'src/pages/settings/LinkTelegramPage.test.tsx',
    ],
  },
})
