'use client'
import * as React from 'react'
import { cn } from '../lib/cn'

interface Tab {
  id: string
  label: string
  disabled?: boolean
}

interface TabsProps {
  tabs: Tab[]
  activeTab: string
  onTabChange: (id: string) => void
  className?: string
}

export function Tabs({ tabs, activeTab, onTabChange, className }: TabsProps) {
  const tabRefs = React.useRef<Map<string, HTMLButtonElement>>(new Map())

  function handleKeyDown(e: React.KeyboardEvent, currentId: string) {
    const enabledTabs = tabs.filter((t) => !t.disabled)
    const idx = enabledTabs.findIndex((t) => t.id === currentId)

    let nextIdx: number | null = null
    if (e.key === 'ArrowRight') nextIdx = (idx + 1) % enabledTabs.length
    if (e.key === 'ArrowLeft') nextIdx = (idx - 1 + enabledTabs.length) % enabledTabs.length
    if (e.key === 'Home') nextIdx = 0
    if (e.key === 'End') nextIdx = enabledTabs.length - 1

    if (nextIdx !== null) {
      e.preventDefault()
      const next = enabledTabs[nextIdx]
      onTabChange(next.id)
      tabRefs.current.get(next.id)?.focus()
    }
  }

  return (
    <div
      role="tablist"
      className={cn('flex gap-0 border-b border-border', className)}
      aria-label="Navegação"
    >
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab
        return (
          <button
            key={tab.id}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={isActive}
            aria-controls={`panel-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            disabled={tab.disabled}
            ref={(el) => {
              if (el) tabRefs.current.set(tab.id, el)
              else tabRefs.current.delete(tab.id)
            }}
            onClick={() => !tab.disabled && onTabChange(tab.id)}
            onKeyDown={(e) => handleKeyDown(e, tab.id)}
            className={cn(
              'px-4 py-2.5 text-[13px] font-medium border-b-2 -mb-px transition-colors duration-[120ms]',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-inset',
              isActive
                ? 'border-accent text-accent'
                : 'border-transparent text-textSecondary hover:text-textPrimary',
              tab.disabled && 'opacity-40 cursor-not-allowed',
            )}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

interface TabPanelProps {
  id: string
  activeTab: string
  children: React.ReactNode
  className?: string
}

export function TabPanel({ id, activeTab, children, className }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      id={`panel-${id}`}
      aria-labelledby={`tab-${id}`}
      hidden={id !== activeTab}
      className={className}
    >
      {id === activeTab && children}
    </div>
  )
}
