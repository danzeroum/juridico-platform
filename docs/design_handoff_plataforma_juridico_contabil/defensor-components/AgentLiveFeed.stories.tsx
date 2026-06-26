import type { Meta, StoryObj } from '@storybook/react'
import { useEffect, useState } from 'react'
import { AgentLiveFeed } from './AgentLiveFeed'
import { MOCK_EVENTS } from './fixtures'

const meta: Meta<typeof AgentLiveFeed> = {
  title: 'Defensor/AgentLiveFeed',
  component: AgentLiveFeed,
  parameters: { layout: 'padded' },
  args: { events: MOCK_EVENTS },
  argTypes: {
    treatment: { control: 'radio', options: ['terminal', 'timeline'] },
    revealed: { control: { type: 'range', min: 0, max: MOCK_EVENTS.length } },
  },
}
export default meta
type Story = StoryObj<typeof AgentLiveFeed>

/** Tratamento A — terminal escuro, totalmente revelado (registro estático). */
export const TerminalCompleto: Story = {
  args: { treatment: 'terminal', revealed: MOCK_EVENTS.length },
}

/** Tratamento A — meio da execução (mostra a linha `running`). */
export const TerminalRodando: Story = {
  args: { treatment: 'terminal', revealed: 6 },
}

/** Tratamento B — timeline clara, preenchimento parcial. */
export const TimelineRodando: Story = {
  args: { treatment: 'timeline', revealed: 5 },
}

export const TimelineCompleto: Story = {
  args: { treatment: 'timeline', revealed: MOCK_EVENTS.length },
}

/** Playground com stagger real (~620ms/linha) + botão re-rodar. */
export const AutoPlay: Story = {
  render: (args) => {
    const [revealed, setRevealed] = useState(1)
    const [key, setKey] = useState(0)
    useEffect(() => {
      setRevealed(1)
      const id = setInterval(() => {
        setRevealed((n) => (n >= args.events.length ? (clearInterval(id), n) : n + 1))
      }, 620)
      return () => clearInterval(id)
    }, [key, args.events.length])
    return (
      <div className="flex flex-col gap-3 max-w-[760px]">
        <button onClick={() => setKey((k) => k + 1)} className="self-start text-[12.5px] font-medium text-accent">↻ re-rodar</button>
        <AgentLiveFeed {...args} revealed={revealed} />
      </div>
    )
  },
}
