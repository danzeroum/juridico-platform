import type { Meta, StoryObj } from '@storybook/react'
import { EventStatusDot } from './EventStatusDot'
import { ProvenanceTag } from './ProvenanceTag'

const meta: Meta = { title: 'Defensor/Selos' }
export default meta
type Story = StoryObj

export const StatusDots: Story = {
  render: () => (
    <div className="flex flex-col gap-3">
      {(['ok', 'running', 'pending'] as const).map((s) => (
        <div key={s} className="flex items-center gap-2.5">
          <EventStatusDot status={s} />
          <span className="font-mono text-[12px]">{s}</span>
        </div>
      ))}
    </div>
  ),
}

export const Proveniencia: Story = {
  render: () => (
    <div className="flex gap-3">
      <ProvenanceTag value="ia" />
      <ProvenanceTag value="parcial" />
      <ProvenanceTag value="template" />
    </div>
  ),
}
