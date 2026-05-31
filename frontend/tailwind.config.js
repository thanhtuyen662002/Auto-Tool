/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#172033',
        muted: '#647084',
        line: '#d8dee8',
        surface: '#f6f8fb',
        brand: '#2563eb',
      },
      boxShadow: {
        panel: '0 10px 30px rgba(23, 32, 51, 0.08)',
      },
    },
  },
  plugins: [],
};
