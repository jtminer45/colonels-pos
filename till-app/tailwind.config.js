/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          red: "#FF3B30",
          navy: "#0A0A1A",
          surface: "#151527",
          surface2: "#1D1D33",
        },
      },
    },
  },
  plugins: [],
};
