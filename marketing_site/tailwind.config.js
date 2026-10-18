/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#2563EB",
        },
        secondary: {
          DEFAULT: "#0F172A",
        },
        accent: {
          DEFAULT: "#22C55E",
        },
        df: {
          primary: "#2563EB",
          "primary-dark": "#1E40AF",
          accent: "#F97316",
          "accent-dark": "#C2410C",
          bg: "#F9FAFB",
          "bg-alt": "#FFFFFF",
          text: "#111827",
          "text-muted": "#4B5563",
          border: "#E5E7EB",
          error: "#EF4444",
          warning: "#FBBF24",
          success: "#22C55E",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
