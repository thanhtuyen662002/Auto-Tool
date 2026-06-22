/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: 'var(--studio-text)',
        muted: 'var(--studio-muted)',
        line: 'var(--studio-border)',
        surface: 'var(--studio-panel-strong)',
        brand: 'var(--studio-accent-bg)',
      },
      boxShadow: {
        panel: 'var(--studio-shadow)',
      },
    },
  },
  plugins: [],
};
