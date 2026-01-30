/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        critical: '#ff4444',
        high: '#ff8800',
        medium: '#ffbb33',
        low: '#00C851',
      },
    },
  },
  plugins: [],
}
