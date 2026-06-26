# Defensor — componentes novos (handoff `@juridico/ui`)

Esqueleto dos 4 componentes especificados no brief. Estilo alinhado ao pacote
existente (`cn()`, tokens `@juridico/tokens`, `lucide-react`, Tailwind). Drop-in em
`packages/ui/src/patterns/`.

| Arquivo | Componente | Estados / variantes |
|---|---|---|
| `EventStatusDot.tsx` | `EventStatusDot` | `ok` · `running` (pulsa) · `pending` |
| `AgentLiveFeed.tsx` | `AgentLiveFeed` | tratamento `terminal` (escuro) · `timeline` (claro) |
| `ProtocolStatusCard.tsx` | `ProtocolStatusCard` | `SIMULADO` · `AGUARDA_CREDENCIAIS` · `ENVIADO` · `FALHA` · `CANAL_NAO_SUPORTADO` |
| `ProvenanceTag.tsx` | `ProvenanceTag` | `ia` · `parcial` · `template` |
| `StepIndicator.tsx` | `StepIndicator` | `pendente` · `ativo` · `concluído` (volta livre, sem pular adiante) |

Apoio:
- `useStaggeredReveal.ts` — hook do stagger do feed (+ fallback reduced-motion).
- `page.example.tsx` — `app/(shell)/defensor/page.tsx` de referência, já consumindo todos os componentes.

## Dependências a confirmar no barrel `packages/ui/src/index.ts`
```ts
export { EventStatusDot } from './patterns/EventStatusDot'
export { AgentLiveFeed } from './patterns/AgentLiveFeed'
export { ProtocolStatusCard } from './patterns/ProtocolStatusCard'
export { ProvenanceTag } from './patterns/ProvenanceTag'
export { StepIndicator, DEFENSOR_STEPS } from './patterns/StepIndicator'
export { useStaggeredReveal } from './hooks/useStaggeredReveal'
```
`ProtocolStatusCard` importa `SectionLabel` de `../primitives/SectionLabel` — garantir
que esse primitive existe/é exportado (já usado nas telas atuais).

## Motion

`AgentLiveFeed` usa duas mecânicas:

1. **Stagger de entrada** — controlado pelo container via a prop `revealed`
   (nº de eventos já exibidos). O componente é "burro": só renderiza `events.slice(0, revealed)`
   no terminal e marca done/running na timeline.

   ```tsx
   const [revealed, setRevealed] = useState(0)
   useEffect(() => {
     if (prefersReducedMotion) { setRevealed(events.length); return }
     setRevealed(1)
     const id = setInterval(() => {
       setRevealed(n => (n >= events.length ? (clearInterval(id), n) : n + 1))
     }, 620)
     return () => clearInterval(id)
   }, [events.length])
   ```

2. **Pulso** do dot `running` → classe `motion-safe:animate-pulse` (já respeita
   `prefers-reduced-motion`).

### Keyframe `fadeup`
O terminal aplica `motion-safe:animate-[fadeup_.32s_ease]` na entrada de cada linha.
Registrar uma vez (tailwind.config ou globals.css):

```css
@keyframes fadeup { from { transform: translateY(5px) } to { transform: none } }
```
> Importante: o keyframe **não** anima `opacity` (mantê-lo só em `transform`), para a
> linha nunca ficar invisível se a animação for interrompida/congelada.

## Tipos compartilhados
`AgentEvent` espelha `EventoAgente` de `lib/api/defensor.ts` + um `titulo?` opcional
(label legível para a timeline). `ProtocolStatusCardProps` espelha `ProtocoloResult`
(`status`, `numero_protocolo`, `mensagem`, `modo`, `url`).

## Storybook & testes
- `index.ts` — barrel do subpacote (mover exports p/ o `index.ts` raiz do `@juridico/ui`).
- `fixtures.ts` — `MOCK_EVENTS` do caso de exemplo (compartilhado por stories e testes).
- `*.stories.tsx` — Storybook: `AgentLiveFeed` (terminal/timeline + AutoPlay com stagger real),
  `ProtocolStatusCard` (5 estados + galeria `Todos`), `Selos` (dots + proveniência).
- `defensor-components.test.tsx` — Vitest + Testing Library: reveal por `revealed`,
  fallback reduced-motion, número/link só em `ENVIADO`, modo explícito, mapa de proveniência.

## Acessibilidade
- Dots têm `role="img"` + `aria-label` ("status: concluído/em execução/aguardando").
- Lista do terminal usa `aria-live="polite"` para anunciar novos eventos.
- Toda animação está sob `motion-safe:` → desliga em `prefers-reduced-motion`.
