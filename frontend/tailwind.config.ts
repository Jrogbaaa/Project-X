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
        // Obsidian Ember Theme
        dark: {
          primary: '#0c0c0e',
          secondary: '#16161a',
          tertiary: '#1f1f24',
          border: '#2e2e36',
          void: '#050506',
          ash: '#28282f',
        },
        light: {
          primary: '#f8f8f7',
          secondary: '#9a9aa3',
          tertiary: '#5e5e66',
          bright: '#ffffff',
        },
        // Ember accent gradient
        accent: {
          gold: '#d4845c', // ember-core (shifted warmer)
          'gold-light': '#c9956a', // ember-glow
          'gold-dark': '#b8a078', // ember-cool
          cream: '#faf7f2',
        },
        ember: {
          hot: '#ff6b4a',
          warm: '#e8734d',
          core: '#d4845c',
          glow: '#c9956a',
          cool: '#b8a078',
        },
        // Ice accent for contrast
        ice: {
          bright: '#00d4ff',
          soft: '#4ecdc4',
        },
        metric: {
          excellent: '#22d67a',
          good: '#d4845c',
          warning: '#f59e42',
          poor: '#ff5757',
        },
        // Keep primary for compatibility
        primary: {
          50: '#fdf8f3',
          100: '#f9ede0',
          200: '#f3dcc4',
          300: '#c9956a',
          400: '#d4845c',
          500: '#e8734d',
          600: '#ff6b4a',
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
        'cascade': 'cardReveal 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'pulse-ring': 'pulseRing 1.5s ease-out infinite',
        'ember-pulse': 'emberPulse 2.5s ease-in-out infinite',
        'card-reveal': 'cardReveal 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'glow-breathe': 'glowBreathe 3s ease-in-out infinite',
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
          '0%, 100%': { borderColor: 'rgba(212, 132, 92, 0.3)' },
          '50%': { borderColor: 'rgba(212, 132, 92, 0.7)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        cardReveal: {
          '0%': { opacity: '0', transform: 'translateY(24px) scale(0.97)', filter: 'blur(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)', filter: 'blur(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseRing: {
          '0%': { boxShadow: '0 0 0 0 rgba(212, 132, 92, 0.4)' },
          '70%': { boxShadow: '0 0 0 8px rgba(212, 132, 92, 0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(212, 132, 92, 0)' },
        },
        emberPulse: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(212, 132, 92, 0.15)' },
          '50%': { boxShadow: '0 0 35px rgba(212, 132, 92, 0.3)' },
        },
        glowBreathe: {
          '0%, 100%': { opacity: '0.5' },
          '50%': { opacity: '0.8' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'shimmer-gradient': 'linear-gradient(90deg, transparent, rgba(212, 132, 92, 0.1), transparent)',
        'gold-gradient': 'linear-gradient(135deg, #d4845c, #c9956a, #d4845c)',
        'ember-gradient': 'linear-gradient(135deg, #ff6b4a, #e8734d, #d4845c)',
        'ember-gradient-soft': 'linear-gradient(135deg, #d4845c 0%, #c9956a 100%)',
        'obsidian-gradient': 'linear-gradient(145deg, rgba(22, 22, 26, 0.95) 0%, rgba(31, 31, 36, 0.9) 100%)',
      },
      boxShadow: {
        'glow-gold': '0 0 20px rgba(212, 132, 92, 0.15)',
        'glow-gold-lg': '0 0 40px rgba(212, 132, 92, 0.25)',
        'glow-ember': '0 0 30px rgba(255, 107, 74, 0.2)',
        'card': '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.04)',
        'card-hover': '0 12px 40px rgba(0, 0, 0, 0.5), 0 0 60px -20px rgba(212, 132, 92, 0.15)',
        'inner-glow': 'inset 0 1px 0 rgba(255, 255, 255, 0.06)',
        'ember-glow': '0 4px 16px rgba(212, 132, 92, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2)',
        'ember-glow-lg': '0 8px 24px rgba(212, 132, 92, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.25)',
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
