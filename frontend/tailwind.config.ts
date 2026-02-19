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
        // Meridian Theme — all names preserved for utils.ts compatibility
        // but values remapped to the new warm editorial palette
        dark: {
          primary: '#FAF8F4',   // cream  — main background
          secondary: '#FFFFFF', // white  — card / panel surface
          tertiary: '#F2EDE6',  // parchment — recessed panels
          border: '#DDD7CF',    // warm border
          void: '#1C2B3A',      // slate  — text on accent backgrounds
          ash: '#EBE5DC',       // linen  — subtle fills / tags
        },
        light: {
          primary: '#1C2B3A',   // slate    — primary text
          secondary: '#5A6878', // smoke    — secondary text
          tertiary: '#8B98A7',  // mist     — captions / placeholders
          bright: '#2C3E50',    // charcoal — strong headings
        },
        // Clay accent (replaces ember — same API names)
        ember: {
          hot:  '#D07055', // clay-light
          warm: '#B85C38', // clay
          core: '#C4714A', // sienna
          glow: '#C98C6A', // clay-medium
          cool: '#D4A882', // clay-muted
        },
        accent: {
          gold:        '#C4714A',
          'gold-light':'#C98C6A',
          'gold-dark': '#8E3E22',
          cream:       '#F5E8E1',
        },
        // Blue replaces ice (contrast accent)
        ice: {
          bright: '#4A6FA5',
          soft:   '#6B8FBA',
        },
        metric: {
          excellent: '#4A7C59',
          good:      '#B85C38',
          warning:   '#9E7A2A',
          poor:      '#C13C2A',
        },
        primary: {
          50:  '#F5E8E1',
          100: '#EDD5C5',
          200: '#DDB89C',
          300: '#C98C6A',
          400: '#C4714A',
          500: '#B85C38',
          600: '#D07055',
          700: '#8E3E22',
          800: '#6B3020',
          900: '#4A2217',
        },
      },
      fontFamily: {
        serif: ['var(--font-cormorant)', 'Georgia', 'serif'],
        sans:  ['var(--font-outfit)',    'system-ui', 'sans-serif'],
        mono:  ['var(--font-dm-mono)',   'monospace'],
      },
      fontSize: {
        'hero':       ['5rem',    { lineHeight: '1.04', letterSpacing: '-0.025em' }],
        'section':    ['1.875rem',{ lineHeight: '1.18', letterSpacing: '-0.015em' }],
        'card-title': ['1.0625rem',{ lineHeight: '1.4' }],
        'body':       ['0.9375rem',{ lineHeight: '1.65' }],
        'caption':    ['0.8125rem',{ lineHeight: '1.5' }],
        'metric':     ['1.25rem', { lineHeight: '1.2' }],
      },
      animation: {
        'fade-in':       'fadeIn 0.45s ease-out forwards',
        'slide-down':    'slideDown 0.38s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'slide-up':      'slideUp 0.38s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'slide-in-right':'slideInRight 0.32s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'scale-in':      'scaleIn 0.38s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'shimmer':       'shimmer 2s linear infinite',
        'pulse-subtle':  'pulseSubtle 2s ease-in-out infinite',
        'border-glow':   'borderGlow 3s ease-in-out infinite',
        'float':         'float 6s ease-in-out infinite',
        'cascade':       'cardReveal 0.48s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'pulse-ring':    'pulseRing 1.5s ease-out infinite',
        'ember-pulse':   'emberPulse 2.5s ease-in-out infinite',
        'card-reveal':   'cardReveal 0.55s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'glow-breathe':  'glowBreathe 3s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideDown: {
          '0%':   { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%':   { opacity: '0', transform: 'scale(0.97)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.6' },
        },
        borderGlow: {
          '0%, 100%': { borderColor: 'rgba(184, 92, 56, 0.28)' },
          '50%':      { borderColor: 'rgba(184, 92, 56, 0.60)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%':      { transform: 'translateY(-5px)' },
        },
        cardReveal: {
          '0%':   { opacity: '0', transform: 'translateY(18px) scale(0.98)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        slideInRight: {
          '0%':   { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseRing: {
          '0%':   { boxShadow: '0 0 0 0 rgba(184, 92, 56, 0.22)' },
          '70%':  { boxShadow: '0 0 0 8px rgba(184, 92, 56, 0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(184, 92, 56, 0)' },
        },
        emberPulse: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(184, 92, 56, 0)' },
          '50%':      { boxShadow: '0 0 0 3px rgba(184, 92, 56, 0.12)' },
        },
        glowBreathe: {
          '0%, 100%': { opacity: '0.5' },
          '50%':      { opacity: '0.85' },
        },
      },
      backgroundImage: {
        'gradient-radial':  'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic':   'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'shimmer-gradient': 'linear-gradient(90deg, transparent, rgba(184, 92, 56, 0.05), transparent)',
      },
      boxShadow: {
        'glow-gold':    '0 0 0 3px rgba(184, 92, 56, 0.10)',
        'glow-gold-lg': '0 0 0 4px rgba(184, 92, 56, 0.16)',
        'glow-ember':   '0 2px 14px rgba(184, 92, 56, 0.14)',
        'card':         '0 1px 3px rgba(28, 43, 58, 0.06), 0 1px 2px rgba(28, 43, 58, 0.04)',
        'card-hover':   '0 4px 20px rgba(28, 43, 58, 0.09), 0 2px 8px rgba(28, 43, 58, 0.05)',
        'inner-glow':   'inset 0 1px 0 rgba(255, 255, 255, 0.80)',
        'ember-glow':   '0 2px 12px rgba(184, 92, 56, 0.16)',
        'ember-glow-lg':'0 4px 20px rgba(184, 92, 56, 0.20)',
      },
      backdropBlur: {
        xs: '2px',
      },
      transitionTimingFunction: {
        spring: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
};

export default config;
