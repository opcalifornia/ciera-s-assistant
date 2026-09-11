/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      colors: {
        surface: {
          DEFAULT: "#ffffff",
          dark: "#212121",
        },
        ink: {
          DEFAULT: "#0d0d0d",
          dark: "#ececec",
        },
        muted: {
          DEFAULT: "#6e6e80",
          dark: "#9b9ba3",
        },
        accent: {
          DEFAULT: "#10a37f",
        },
      },
    },
  },
  plugins: [],
};
