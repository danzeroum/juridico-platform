import type { Config } from 'tailwindcss'
import { colors } from './colors'

export const tailwindPreset: Partial<Config> = {
  theme: {
    extend: {
      colors: {
        bgApp: colors.bgApp,
        surface: colors.surface,
        surfaceMuted: colors.surfaceMuted,
        border: colors.border,
        borderStrong: colors.borderStrong,
        sidebarNavy: colors.sidebarNavy,
        sidebarLine: colors.sidebarLine,
        textPrimary: colors.textPrimary,
        textSecondary: colors.textSecondary,
        textMuted: colors.textMuted,
        textFaint: colors.textFaint,
        textSectionLabel: colors.textSectionLabel,
        accent: colors.accent,
        accentHover: colors.accentHover,
        accentTintBg: colors.accentTintBg,
        accentTintBorder: colors.accentTintBorder,
        riskLow: colors.riskLow,
        riskLowBg: colors.riskLowBg,
        riskLowText: colors.riskLowText,
        riskMedium: colors.riskMedium,
        riskMediumBg: colors.riskMediumBg,
        riskMediumText: colors.riskMediumText,
        riskHigh: colors.riskHigh,
        riskHighBg: colors.riskHighBg,
        riskHighText: colors.riskHighText,
        riskCritical: colors.riskCritical,
        riskCriticalBg: colors.riskCriticalBg,
        riskCriticalText: colors.riskCriticalText,
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
}
