export const colors = {
  // Neutrals
  bgApp: '#f5f6f8',
  surface: '#ffffff',
  surfaceMuted: '#f7f8fa',
  border: '#e7eaee',
  borderAlt: '#e3e7ec',
  borderStrong: '#d3d8df',
  dividerLight: '#f0f2f5',

  // Sidebar
  sidebarNavy: '#0c1c33',
  sidebarLine: '#1a2d4e',
  sidebarLineAlt: '#21385f',

  // Text
  textPrimary: '#13181f',
  textSecondary: '#48515e',
  textSecondaryAlt: '#5b6573',
  textMuted: '#76808d',
  textMutedAlt: '#8a93a0',
  textFaint: '#9aa3af',
  textSidebarInactive: '#9fb0c5',
  textSectionLabel: '#6b7480',

  // Accent
  accent: '#2f6fed',
  accentHover: '#2660d8',
  accentTintBg: '#e8effe',
  accentTintBgAlt: '#eef4fe',
  accentTintBorder: '#cddcf8',
  accentActiveBg: 'rgba(47,111,237,0.16)',

  // Risk / Severity
  riskLow: '#1f8a5b',
  riskLowBg: '#e7f4ee',
  riskLowBgAlt: '#f1f9f5',
  riskLowText: '#0f5c3a',
  riskLowBorder: '#bfe3d0',

  riskMedium: '#b07d00',
  riskMediumSolid: '#caa215',
  riskMediumBg: '#fbf4e2',
  riskMediumBgAlt: '#fbf6e9',
  riskMediumText: '#7a5800',
  riskMediumBorder: '#ecdcae',

  riskHigh: '#cf6a1f',
  riskHighBg: '#fbe9da',
  riskHighText: '#9a4a12',
  riskHighBorder: '#f0cdab',

  riskCritical: '#c4382f',
  riskCriticalBg: '#fae3e1',
  riskCriticalBgAlt: '#fbeae8',
  riskCriticalText: '#8f2a22',
  riskCriticalBorder: '#f0c2bd',
} as const

export type ColorToken = keyof typeof colors

// Semantic maps for runtime use
export const RISK_COLORS = {
  BAIXO: {
    solid: colors.riskLow,
    bg: colors.riskLowBg,
    text: colors.riskLowText,
    border: colors.riskLowBorder,
  },
  MODERADO: {
    solid: colors.riskMedium,
    bg: colors.riskMediumBg,
    text: colors.riskMediumText,
    border: colors.riskMediumBorder,
  },
  ALTO: {
    solid: colors.riskHigh,
    bg: colors.riskHighBg,
    text: colors.riskHighText,
    border: colors.riskHighBorder,
  },
  CRITICO: {
    solid: colors.riskCritical,
    bg: colors.riskCriticalBg,
    text: colors.riskCriticalText,
    border: colors.riskCriticalBorder,
  },
} as const

export type RiskLevel = keyof typeof RISK_COLORS

export const FRESHNESS_COLORS = {
  fresh: {
    dot: colors.riskLow,
    bg: colors.riskLowBgAlt,
    text: colors.riskLowText,
    border: colors.riskLowBorder,
  },
  stale: {
    dot: colors.riskMedium,
    bg: colors.riskMediumBgAlt,
    text: colors.riskMediumText,
    border: colors.riskMediumBorder,
  },
  very_stale: {
    dot: colors.riskCritical,
    bg: colors.riskCriticalBgAlt,
    text: colors.riskCriticalText,
    border: colors.riskCriticalBorder,
  },
} as const

export type FreshnessBand = keyof typeof FRESHNESS_COLORS

export const DATA_CLASS_COLORS = {
  publico: {
    dot: colors.riskLow,
    bg: colors.riskLowBg,
    text: colors.riskLowText,
  },
  pessoal: {
    dot: colors.riskMedium,
    bg: colors.riskMediumBg,
    text: colors.riskMediumText,
  },
  sensivel: {
    dot: colors.riskCritical,
    bg: colors.riskCriticalBg,
    text: colors.riskCriticalText,
  },
} as const

export type DataClass = keyof typeof DATA_CLASS_COLORS

export const DELIVERY_STATUS_COLORS = {
  pending: { text: colors.riskMediumText, bg: colors.riskMediumBg },
  claimed: { text: colors.accent, bg: colors.accentTintBg },
  done: { text: colors.riskLowText, bg: colors.riskLowBg },
  failed: { text: colors.riskCriticalText, bg: colors.riskCriticalBg },
} as const

export type DeliveryStatus = keyof typeof DELIVERY_STATUS_COLORS
