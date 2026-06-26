// Defensor — componentes novos (barrel)
// Mover para packages/ui/src/patterns/ e reexportar no index.ts raiz do pacote.
export { EventStatusDot, EVENT_STATUS_COLORS, EVENT_STATUS_LABELS } from './EventStatusDot'
export type { EventStatus } from './EventStatusDot'

export { AgentLiveFeed } from './AgentLiveFeed'
export type { AgentEvent, FeedTreatment } from './AgentLiveFeed'

export { ProtocolStatusCard } from './ProtocolStatusCard'
export type { ProtocolStatus, ProtocolMode, ProtocolStatusCardProps } from './ProtocolStatusCard'

export { ProvenanceTag } from './ProvenanceTag'
export type { Provenance } from './ProvenanceTag'
