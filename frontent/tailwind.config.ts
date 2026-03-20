import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      backgroundImage: {
        grid: 'linear-gradient(rgba(15, 23, 42, 0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(15, 23, 42, 0.07) 1px, transparent 1px)',
      },
      boxShadow: {
        glow: '0 24px 80px rgba(15, 23, 42, 0.16)',
      },
      colors: {
        ink: '#102033',
        mist: '#f4f7fb',
        accent: '#f97316',
        signal: '#0f766e',
      },
    },
  },
  plugins: [],
} satisfies Config;
