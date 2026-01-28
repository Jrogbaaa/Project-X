import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Dark Editorial Theme
        dark: {
          primary: '#0a0a0b',
          secondary: '#141416',
          tertiary: '#1c1c1f',
          border: '#2a2a2e',
        },
        light: {
          primary: '#fafaf9',
          secondary: '#a1a1a6',
          tertiary: '#6b6b70',
        },
        accent: {
          gold: '#d4a574',
          'gold-light': '#e8c9a8',
          'gold-dark': '#b8895a',
          cream: '#faf7f2',
        },
        metric: {
          excellent: '#4ade80',
          good: '#d4a574',
          warning: '#fb923c',
          poor: '#f87171',
        },
        // Keep primary for compatibility
        primary: {
          50: '#fdf8f3',
          100: '#f9ede0',
          200: '#f3dcc4',
          300: '#e8c9a8',
          400: '#d4a574',
          500: '#c4915e',
          600: '#b8895a',
          700: '#9a7049',
          800: '#7d5b3d',
          900: '#664a33',
        },
      },
      fontFamily: {
        serif: ['var(--font-instrument-serif)', 'Georgia', 'serif'],
        sans: ['var(--font-dm-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-jetbrains-mono)', 'monospace'],
      },
      fontSize: {
        'hero': ['4rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        'section': ['1.5rem', { lineHeight: '1.3', letterSpacing: '-0.01em' }],
        'card-title': ['1.125rem', { lineHeight: '1.4' }],
        'body': ['0.9375rem', { lineHeight: '1.6' }],
        'caption': ['0.8125rem', { lineHeight: '1.5' }],
        'metric': ['1.25rem', { lineHeight: '1.2' }],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out forwards',
        'slide-down': 'slideDown 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'slide-up': 'slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'slide-in-right': 'slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'scale-in': 'scaleIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'shimmer': 'shimmer 2s linear infinite',
        'pulse-subtle': 'pulseSubtle 2s ease-in-out infinite',
        'border-glow': 'borderGlow 3s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
        'cascade': 'cascade 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'pulse-ring': 'pulseRing 1.5s ease-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
        borderGlow: {
          '0%, 100%': { borderColor: 'rgba(212, 165, 116, 0.3)' },
          '50%': { borderColor: 'rgba(212, 165, 116, 0.8)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        cascade: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseRing: {
          '0%': { boxShadow: '0 0 0 0 rgba(212, 165, 116, 0.4)' },
          '70%': { boxShadow: '0 0 0 8px rgba(212, 165, 116, 0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(212, 165, 116, 0)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'shimmer-gradient': 'linear-gradient(90deg, transparent, rgba(212, 165, 116, 0.1), transparent)',
        'gold-gradient': 'linear-gradient(135deg, #d4a574, #e8c9a8, #d4a574)',
      },
      boxShadow: {
        'glow-gold': '0 0 20px rgba(212, 165, 116, 0.15)',
        'glow-gold-lg': '0 0 40px rgba(212, 165, 116, 0.2)',
        'card': '0 4px 20px rgba(0, 0, 0, 0.3)',
        'card-hover': '0 8px 30px rgba(0, 0, 0, 0.4)',
        'inner-glow': 'inset 0 1px 1px rgba(255, 255, 255, 0.05)',
      },
      backdropBlur: {
        xs: '2px',
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
};

export default config;
