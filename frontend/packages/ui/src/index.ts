// Primitives
export { Button } from './primitives/Button'
export { Card, CardHeader, SectionLabel } from './primitives/Card'
export { Badge, MonoChip } from './primitives/Badge'
export { Input, Textarea } from './primitives/Input'
export { Tabs, TabPanel } from './primitives/Tabs'
export { Table, Thead, Tbody, Tr, Th, Td } from './primitives/Table'
export { Skeleton, SkeletonText, SkeletonCard } from './primitives/Skeleton'
export { Avatar, AvatarStack } from './primitives/Avatar'
export { Dropzone } from './primitives/Dropzone'

// Cross-cutting patterns (12)
export { TrustHeader } from './patterns/TrustHeader'
export type { TrustHeaderProps, TrustSource } from './patterns/TrustHeader'

export { FreshnessSeal } from './patterns/FreshnessSeal'

export { HeuristicBadge } from './patterns/HeuristicBadge'

export { ScoreGauge } from './patterns/ScoreGauge'
export { ProbabilityDonut } from './patterns/ProbabilityDonut'
export { SettlementRangeBar } from './patterns/SettlementRangeBar'

export { MerklePanel } from './patterns/MerklePanel'
export type { MerklePanelProps, MerkleProof } from './patterns/MerklePanel'

export { VerifiableCitationChip, AntiHallucinationGuard } from './patterns/VerifiableCitationChip'

export { AlertList } from './patterns/AlertList'
export type { AlertItem } from './patterns/AlertList'

export { ProblemJsonError } from './patterns/ProblemJsonError'
export type { ProblemJson } from './patterns/ProblemJsonError'

export { JobProgress } from './patterns/JobProgress'
export type { JobStep } from './patterns/JobProgress'

export { DegradationBanner } from './patterns/DegradationBanner'

export { RbacGate, ViewerBanner } from './patterns/RbacGate'

export { EmptyState } from './patterns/EmptyState'

// Utils
export { cn } from './lib/cn'
