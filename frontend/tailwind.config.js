/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['Cormorant Garamond', 'serif'],
        body: ['DM Sans', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      colors: {
        canvas: { DEFAULT: '#FAF9F7', dark: '#F3F1EE', deep: '#EBE8E4' },
        carbon: {
          50: '#F8F9FA', 100: '#F0F1F2', 200: '#E2E4E6', 300: '#C8CCCE',
          400: '#9DA3A7', 500: '#636E72', 600: '#4A5459', 700: '#343D42',
          800: '#2D3436', 900: '#1B2631',
        },
        sage: { DEFAULT: '#7B8B6F', light: '#A8B89F', pale: '#EEF2EB', dark: '#5A6B4F', deep: '#3D4A35' },
        terra: { DEFAULT: '#C4956A', light: '#D4B08E', pale: '#F5EDE4' },
        status: { ok: '#6B8F71', warn: '#C4956A', fail: '#B85C5C', info: '#6B8FAF' },
      },
      animation: {
        'book-open': 'bookOpen 0.7s cubic-bezier(0.22, 1, 0.36, 1) both',
        'fade-up': 'fadeUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) both',
        'fade-in': 'fadeIn 0.6s ease both',
        'slide-right': 'slideRight 0.6s cubic-bezier(0.16, 1, 0.3, 1) both',
        'scale-in': 'scaleIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) both',
        'shimmer': 'shimmer 2s infinite',
        'pulse-glow': 'pulseGlow 2s ease infinite',
      },
      keyframes: {
        bookOpen: {
          from: { opacity: '0', transform: 'perspective(1200px) rotateY(-8deg) scale(0.96)', filter: 'blur(3px)' },
          to: { opacity: '1', transform: 'perspective(1200px) rotateY(0deg) scale(1)', filter: 'blur(0)' },
        },
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(28px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        slideRight: {
          from: { opacity: '0', transform: 'translateX(-24px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        scaleIn: {
          from: { opacity: '0', transform: 'scale(0.94)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(123,139,111,0.25)' },
          '50%': { boxShadow: '0 0 0 8px rgba(123,139,111,0)' },
        },
      },
    },
  },
  plugins: [],
}
