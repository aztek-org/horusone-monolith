import type { Config } from 'tailwindcss'

export default {
  content: [
    './app/**/*.{vue,js,ts}',
    './components/**/*.{vue,js,ts}',
    './layouts/**/*.{vue,js,ts}',
    './pages/**/*.{vue,js,ts}',
    './modules/**/*.{vue,js,ts}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Primary backgrounds
        horus: {
          bg: {
            primary: '#0a0f1a',
            secondary: '#111827',
            tertiary: '#1a2332',
            card: '#0d1320',
            elevated: '#151d2c',
          },
          // Accent colors
          accent: {
            cyan: '#00d4ff',
            'cyan-dim': '#0099cc',
            'cyan-glow': '#00e5ff',
          },
          // Status colors
          status: {
            success: '#10b981',
            'success-dim': '#059669',
            warning: '#f59e0b',
            'warning-dim': '#d97706',
            danger: '#ef4444',
            'danger-dim': '#dc2626',
            info: '#3b82f6',
          },
          // Text colors
          text: {
            primary: '#f8fafc',
            secondary: '#94a3b8',
            muted: '#64748b',
            accent: '#00d4ff',
          },
          // Border colors
          border: {
            subtle: '#1e293b',
            default: '#334155',
            accent: '#00d4ff33',
          }
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      fontSize: {
        'xxs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(0, 212, 255, 0.3)',
        'glow-success': '0 0 20px rgba(16, 185, 129, 0.3)',
        'glow-danger': '0 0 20px rgba(239, 68, 68, 0.3)',
        'glow-warning': '0 0 20px rgba(245, 158, 11, 0.3)',
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
        'card-elevated': '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3)',
      },
      backdropBlur: {
        'xs': '2px',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(0, 212, 255, 0.2)' },
          '100%': { boxShadow: '0 0 20px rgba(0, 212, 255, 0.4)' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'grid-pattern': 'linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px)',
      },
      backgroundSize: {
        'grid': '20px 20px',
      },
    },
  },
  plugins: [],
} satisfies Config
