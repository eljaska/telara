/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // SOC Dark Theme Colors
        'soc': {
          'bg': '#0a0e14',
          'panel': '#0d1117',
          'border': '#1c2128',
          'text': '#c9d1d9',
          'muted': '#6e7681',
        },
        'vital': {
          'normal': '#3fb950',
          'warning': '#d29922',
          'critical': '#f85149',
          'info': '#58a6ff',
        },
        'accent': {
          'cyan': '#39c5cf',
          'purple': '#a371f7',
          'orange': '#db6d28',
        }
      },
      fontFamily: {
        'mono': ['JetBrains Mono', 'Fira Code', 'monospace'],
        'display': ['Orbitron', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'slide-in': 'slideIn 0.3s ease-out',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(57, 197, 207, 0.2)' },
          '100%': { boxShadow: '0 0 20px rgba(57, 197, 207, 0.4)' },
        },
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        }
      }
    },
  },
  plugins: [],
}

