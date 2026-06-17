import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    '../../packages/ui/src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bgApp: '#f5f6f8',
        surface: '#ffffff',
        surfaceMuted: '#f7f8fa',
        border: '#e7eaee',
        borderAlt: '#e3e7ec',
        borderStrong: '#d3d8df',
        dividerLight: '#f0f2f5',
        sidebarNavy: '#0c1c33',
        sidebarLine: '#1a2d4e',
        textPrimary: '#13181f',
        textSecondary: '#48515e',
        textMuted: '#76808d',
        textFaint: '#9aa3af',
        textSectionLabel: '#6b7480',
        accent: '#2f6fed',
        accentHover: '#2660d8',
        accentTintBg: '#e8effe',
        accentTintBgAlt: '#eef4fe',
        accentTintBorder: '#cddcf8',
        riskLow: '#1f8a5b',
        riskLowBg: '#e7f4ee',
        riskLowText: '#0f5c3a',
        riskLowBorder: '#bfe3d0',
        riskMedium: '#b07d00',
        riskMediumBg: '#fbf4e2',
        riskMediumText: '#7a5800',
        riskHigh: '#cf6a1f',
        riskHighBg: '#fbe9da',
        riskHighText: '#9a4a12',
        riskCritical: '#c4382f',
        riskCriticalBg: '#fae3e1',
        riskCriticalText: '#8f2a22',
      },
      fontFamily: {
        sans: ["'IBM Plex Sans'", 'system-ui', 'sans-serif'],
        mono: ["'IBM Plex Mono'", 'monospace'],
      },
      borderRadius: {
        card: '10px',
        cardLg: '12px',
        chip: '5px',
        chipLg: '6px',
        pill: '20px',
      },
      boxShadow: {
        float: '0 2px 6px rgba(12,28,51,0.18)',
        focusRing: '0 0 0 3px #e2ebfd',
      },
      maxWidth: {
        content: '1180px',
      },
      width: {
        sidebar: '238px',
      },
      height: {
        topbar: '58px',
      },
    },
  },
  plugins: [],
}

export default config
