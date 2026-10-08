import { defineConfig } from 'vitest/config'

// Kept separate from vite.config.ts on purpose: vitest pins its own nested copy
// of Vite, and merging `test` into the main vite.config.ts caused a plugin-type
// mismatch between that nested copy and the project's top-level `vite` (used by
// `@vitejs/plugin-react`/`@tailwindcss/vite`), breaking `tsc -b`. Vitest resolves
// this file automatically instead of vite.config.ts, so the production build
// config never needs to know about tests at all.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
})
