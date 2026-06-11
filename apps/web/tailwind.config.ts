import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Brand (MedSave teal) — primary identity
        brand: {
          50: "#EAFBF8",
          100: "#CCF4EE",
          200: "#9BE6DD",
          300: "#5FD1C8",
          400: "#26B8AF",
          500: "#0AA39B",
          600: "#07877F",
          700: "#066A65",
          800: "#075550",
          900: "#073F3C",
          950: "#022927",
        },
        // Gold/Amber — accent for emphasis CTAs and notifications
        gold: {
          50: "#FFF8E6",
          100: "#FDECB8",
          200: "#F9DA7B",
          300: "#F5C83F",
          400: "#EFB323",
          500: "#D99B16",
          600: "#B57912",
          700: "#8F5A12",
          800: "#744816",
          900: "#623C17",
        },
        // Surface system
        surface: {
          DEFAULT: "#FBF7F0",
          subtle: "#F4EADF",
          muted: "#EADDCB",
        },
        // Expiry zone colors (preserved + semantic aliases)
        expiry: {
          green: "#16a34a",
          yellow: "#ca8a04",
          orange: "#ea580c",
          red: "#dc2626",
          safe: "#16a34a",
          notice: "#ca8a04",
          warning: "#ea580c",
          critical: "#dc2626",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      fontFamily: {
        sans: ["IBM Plex Sans Arabic", "Tajawal", "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(47,37,26,0.05), 0 1px 1px rgba(47,37,26,0.03)",
        card: "0 8px 22px -18px rgba(47,37,26,0.24), 0 1px 2px rgba(47,37,26,0.05)",
        lift: "0 24px 44px -28px rgba(47,37,26,0.32), 0 8px 18px -14px rgba(47,37,26,0.18)",
        focus: "0 0 0 4px rgba(10,163,155,0.18)",
      },
      ringWidth: {
        DEFAULT: "1px",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 220ms ease-out",
        "slide-in-right": "slide-in-right 250ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
