/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#f8fafc',
        muted: '#aab3c5',
        line: 'rgba(255, 255, 255, 0.14)',
        surface: '#0b1020',
        brand: '#22d3ee',
      },
      boxShadow: {
        panel: '0 20px 60px rgba(0, 0, 0, 0.32)',
      },
    },
  },
  plugins: [],
};
