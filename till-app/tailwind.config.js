/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Matched to the real "Colonels Restaurant & Garden" logo: deep red
        // ring/script on a true-black background (sampled from assets/real logo.jpg).
        brand: {
          red: "#C61D24",
          navy: "#0A0A0A",
          surface: "#161616",
          surface2: "#212121",
        },
      },
    },
  },
  plugins: [],
};
