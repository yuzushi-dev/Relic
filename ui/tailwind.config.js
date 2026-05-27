/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class", '[data-theme="dark"]'],
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--bg)",
        foreground: "var(--text)",
        card: {
          DEFAULT: "var(--s0)",
          foreground: "var(--text)",
        },
        popover: {
          DEFAULT: "var(--s1)",
          foreground: "var(--text)",
        },
        primary: {
          DEFAULT: "var(--obs)",
          foreground: "#ffffff",
        },
        secondary: {
          DEFAULT: "var(--s2)",
          foreground: "var(--text)",
        },
        muted: {
          DEFAULT: "var(--s1)",
          foreground: "var(--text-dim)",
        },
        accent: {
          DEFAULT: "var(--s2)",
          foreground: "var(--text)",
        },
        destructive: {
          DEFAULT: "var(--block)",
          foreground: "#ffffff",
        },
        border: "var(--line-med)",
        input: "var(--line)",
        ring: "var(--obs)",
        gumi: "var(--gumi)",
        success: "var(--ok)",
        warning: "var(--pend)",
      },
      borderRadius: {
        lg: "var(--r0, 2px)",
        md: "calc(var(--r0, 2px) - 1px)",
        sm: "calc(var(--r0, 2px) - 2px)",
      },
      fontFamily: {
        sans: ["var(--sans)", "system-ui", "sans-serif"],
        mono: ["var(--mono)", "monospace"],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
