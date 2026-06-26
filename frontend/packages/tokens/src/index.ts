export * from './colors'
export * from './typography'
export * from './spacing'
export * from './constants'
export * from './tailwind.preset'

// Desambiguação: RiskLevel/FreshnessBand/DataClass/DeliveryStatus são exportados
// tanto por ./colors (keyof dos mapas de cor) quanto por ./constants (uniões de
// strings de nível). constants.ts é a fonte canônica — reexport explícito vence
// o conflito de `export *` (resolve TS2308).
export type { RiskLevel, FreshnessBand, DataClass, DeliveryStatus } from './constants'
