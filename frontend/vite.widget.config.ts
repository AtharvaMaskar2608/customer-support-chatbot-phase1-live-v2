import { defineConfig } from 'vite'

/**
 * Separate build entry for the framework-free corner widget embed.
 * Produces dist/widget.js (IIFE, no React) which host pages include with a
 * single script tag and drive via `ChoiceJini.init({...})`.
 *
 * Runs after the app build (see the package.json build script) with
 * emptyOutDir disabled so both artifacts land in dist/ together.
 */
export default defineConfig({
  publicDir: false,
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    lib: {
      entry: 'src/widget/widget.ts',
      name: 'ChoiceJini',
      formats: ['iife'],
      fileName: () => 'widget.js',
    },
  },
})
