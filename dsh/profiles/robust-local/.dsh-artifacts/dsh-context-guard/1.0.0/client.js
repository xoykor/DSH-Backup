;(function () {
  'use strict'
  if (typeof window === 'undefined' || !window.__ModuleLoader__?.load) return

  window.__ModuleLoader__.load({
    id: 'dsh-context-guard',
    factory: function (require) {
      const react = require('react')
      const jsx = react.createElement

      const RATIO_FIELDS = [
        ['economyRatio', 'Modo economia'],
        ['checkpointRatio', 'Checkpoint'],
        ['compactRatio', 'Limiar de compactação'],
        ['responseRatio', 'Reserva da resposta'],
        ['summaryRatio', 'Reserva do resumo'],
        ['summaryMinRatio', 'Mínimo do resumo'],
        ['safetyRatio', 'Margem de segurança'],
        ['retainRatio', 'Retenção após compactar'],
      ]
      const RESTART_PATH = '/api/context-guard/restart'

      const number = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback
      const tokenCount = (policy, field) => Math.floor(number(policy.contextWindow, 0) * number(policy[field], 0))
      const percent = (value) => `${(number(value, 0) * 100).toFixed(1)}%`
      const tokens = (value) => `${Math.floor(number(value, 0)).toLocaleString('pt-BR')} tokens`

      function normalizeDraft(input, field, rawValue) {
        const next = { ...input }
        let value = Number(rawValue)
        if (!Number.isFinite(value)) return input
        if (field === 'contextWindow') {
          next.contextWindow = Math.round(Math.max(16_384, Math.min(1_048_576, value)))
          return next
        }
        const min = {
          economyRatio: 0.10,
          checkpointRatio: number(input.economyRatio, 0.5) + 0.01,
          compactRatio: number(input.checkpointRatio, 0.625) + 0.01,
          responseRatio: 0.02,
          summaryRatio: number(input.summaryMinRatio, 0.0078) + 0.001,
          summaryMinRatio: 0.001,
          safetyRatio: 0.01,
          retainRatio: 0.01,
        }[field] ?? 0.001
        const max = {
          economyRatio: number(input.checkpointRatio, 0.625) - 0.01,
          checkpointRatio: number(input.compactRatio, 0.7) - 0.01,
          compactRatio: 1 - number(input.responseRatio, 0.1875) - number(input.summaryRatio, 0.0625) - number(input.safetyRatio, 0.03125) - 0.01,
          responseRatio: 1 - number(input.compactRatio, 0.7) - number(input.summaryRatio, 0.0625) - number(input.safetyRatio, 0.03125) - 0.01,
          summaryRatio: 1 - number(input.compactRatio, 0.7) - number(input.responseRatio, 0.1875) - number(input.safetyRatio, 0.03125) - 0.01,
          summaryMinRatio: number(input.summaryRatio, 0.0625) - 0.001,
          safetyRatio: 1 - number(input.compactRatio, 0.7) - number(input.responseRatio, 0.1875) - number(input.summaryRatio, 0.0625) - 0.01,
          retainRatio: number(input.compactRatio, 0.7) - 0.01,
        }[field] ?? 0.99
        next[field] = Math.max(min, Math.min(max, value))
        return next
      }

      function NumericInput({ value, min, max, step, suffix, format, parse, onCommit }) {
        const [text, setText] = react.useState(() => format(value))
        react.useEffect(() => setText(format(value)), [value, format])
        const commit = () => {
          const parsed = parse(text)
          if (Number.isFinite(parsed)) onCommit(parsed)
          else setText(format(value))
        }
        return jsx('span', { className: 'dshcg-number-wrap' },
          jsx('input', {
            className: 'dshcg-number',
            type: 'number',
            inputMode: 'decimal',
            min, max, step,
            value: text,
            onChange: (event) => setText(event.target.value),
            onBlur: commit,
            onKeyDown: (event) => { if (event.key === 'Enter') { event.currentTarget.blur() } },
            'aria-label': `Valor exato (${suffix})`,
          }),
          jsx('span', { className: 'dshcg-unit' }, suffix),
        )
      }

      function SliderRow({ label, value, min, max, step, onChange, inputMin, inputMax, inputStep, inputSuffix, inputFormat, inputParse, inputValue, summary }) {
        return jsx('div', { className: 'dshcg-row' },
          jsx('span', { className: 'dshcg-label' }, label),
          jsx('div', { className: 'dshcg-control' },
            jsx('input', {
              type: 'range', min, max, step, value,
              onChange: (event) => onChange(event.target.value),
              'aria-label': label,
            }),
            jsx(NumericInput, {
              value: inputValue ?? value,
              min: inputMin ?? min,
              max: inputMax ?? max,
              step: inputStep ?? step,
              suffix: inputSuffix,
              format: inputFormat,
              parse: inputParse,
              onCommit: onChange,
            }),
          ),
          jsx('output', { className: 'dshcg-value' }, summary),
        )
      }

      async function requestRestart() {
        try {
          const response = await fetch(RESTART_PATH, { method: 'POST' })
          const body = await response.json().catch(() => ({}))
          return {
            ok: response.ok,
            message: body.message ?? (response.ok
              ? 'Reinício solicitado.'
              : 'O host não oferece reinício automático.'),
          }
        } catch (error) {
          return { ok: false, message: `Falha ao solicitar reinício: ${error instanceof Error ? error.message : String(error)}` }
        }
      }

      function RestartButton() {
        const [status, setStatus] = react.useState('idle')
        const [message, setMessage] = react.useState('')
        const disabled = status === 'requesting' || status === 'requested'
        const label = status === 'requesting'
          ? 'Reiniciando…'
          : status === 'requested'
            ? 'Reinício solicitado'
            : status === 'error'
              ? 'Reinício indisponível'
              : 'Reiniciar DSH'

        const restart = async () => {
          if (disabled || !window.confirm('Reiniciar o processo do DSH agora?')) return
          setStatus('requesting')
          const result = await requestRestart()
          setMessage(result.message)
          setStatus(result.ok ? 'requested' : 'error')
        }

        return jsx('span', {
          className: 'dshcg-restart-wrap',
          children: jsx('button', {
            type: 'button',
            className: 'dshcg-restart-button',
            'aria-label': message || 'Reiniciar o processo do DSH',
            title: message || 'Reiniciar o processo do DSH',
            disabled,
            onMouseDown: (event) => event.preventDefault(),
            onClick: restart,
            children: label,
          }),
        })
      }

      function ContextGuardSection({ scope }) {
        // The settings scope exposes class methods; pass bound wrappers so React
        // can invoke the callbacks without losing the scope receiver.
        const snapshot = react.useSyncExternalStore(
          (listener) => scope.subscribe(listener),
          () => scope.getSnapshot(),
          () => scope.getSnapshot(),
        )
        const presets = snapshot.value?.presets ?? {}
        const names = Object.keys(presets)
        const [selected, setSelected] = react.useState(names[0] ?? '')
        const [draft, setDraft] = react.useState(presets[names[0]] ?? null)
        const [saving, setSaving] = react.useState(false)
        const [message, setMessage] = react.useState('')

        react.useEffect(() => {
          if (!names.includes(selected)) setSelected(names[0] ?? '')
        }, [snapshot.value, selected])
        react.useEffect(() => {
          if (selected && presets[selected]) setDraft({ ...presets[selected] })
        }, [selected, snapshot.value])

        if (snapshot.status !== 'ready' || !draft || names.length === 0) {
          return jsx('section', { className: 'dshcg-card' },
            jsx('h2', null, 'Orçamento de contexto'),
            jsx('p', { className: 'dshcg-muted' }, snapshot.status === 'loading'
              ? 'Carregando configurações…'
              : 'Nenhum preset com janela de contexto configurada foi exposto a esta interface.'),
          )
        }

        const update = (field, value) => setDraft((current) => normalizeDraft(current, field, value))
        const guardWindow = Math.floor(number(draft.contextWindow, 0))
        const compactAt = tokenCount(draft, 'compactRatio')
        const checkpointAt = tokenCount(draft, 'checkpointRatio')
        const persist = async () => {
          setSaving(true)
          setMessage('Salvando…')
          await scope.mutate([{ op: 'set', path: ['presets', selected], value: draft }], snapshot.revision)
          setSaving(false)
          setMessage('Configuração salva.')
        }
        const restart = async () => {
          if (!window.confirm('Reiniciar o processo do DSH agora?')) return
          setMessage('Solicitando reinício…')
          setMessage((await requestRestart()).message)
        }

        return jsx('section', { className: 'dshcg-card' },
          jsx('h2', null, 'Orçamento de contexto'),
          jsx('p', { className: 'dshcg-muted' }, 'Ajuste os ratios; os valores em tokens são derivados da janela selecionada.'),
          jsx('label', { className: 'dshcg-select-label' }, 'Preset',
            jsx('select', { value: selected, onChange: (event) => setSelected(event.target.value) }, names.map((name) => jsx('option', { key: name, value: name }, name))),
          ),
          jsx(SliderRow, {
            label: 'Orçamento do guardião', value: draft.contextWindow,
            min: 16_384, max: 1_048_576, step: 1024,
            inputMin: 16_384, inputMax: 1_048_576, inputStep: 1,
            inputSuffix: 'tokens', inputValue: draft.contextWindow,
            inputFormat: (value) => String(Math.round(number(value, 0))),
            inputParse: (value) => Number(value),
            onChange: (value) => update('contextWindow', value),
            summary: `${tokens(guardWindow)} · compacta em ${tokens(compactAt)}`,
          }),
          jsx('div', { className: 'dshcg-context-note' },
            jsx('strong', null, `Guardião ativo: ${tokens(guardWindow)}`),
            jsx('span', null, `checkpoint em ${tokens(checkpointAt)} e compactação em ${tokens(compactAt)} (${percent(draft.compactRatio)}).`),
            jsx('span', null, 'O medidor nativo do DSH pode continuar mostrando 131K: ele representa a capacidade máxima do modelo, não o orçamento efetivo deste guardião.'),
          ),
          jsx('div', { className: 'dshcg-grid' }, RATIO_FIELDS.map(([field, label]) => jsx(SliderRow, {
            key: field,
            label,
            value: draft[field],
            min: field === 'summaryMinRatio' ? 0.001 : 0.01,
            max: field === 'retainRatio' ? 0.5 : 0.95,
            step: 0.001,
            inputMin: (field === 'summaryMinRatio' ? 0.001 : 0.01) * 100,
            inputMax: (field === 'retainRatio' ? 0.5 : 0.95) * 100,
            inputStep: 0.1,
            inputSuffix: '%', inputValue: number(draft[field], 0) * 100,
            inputFormat: (value) => number(value, 0).toFixed(1),
            inputParse: (value) => Number(value) / 100,
            onChange: (value) => update(field, value),
            summary: tokens(tokenCount(draft, field)),
          }))),
          jsx('p', { className: 'dshcg-muted' }, 'Ordem garantida: economia < checkpoint < compactação; as reservas também permanecem abaixo de 100%.'),
          jsx('div', { className: 'dshcg-actions' },
            jsx('button', { type: 'button', disabled: saving || !snapshot.writable, onClick: persist }, saving ? 'Salvando…' : 'Salvar'),
            jsx('button', { type: 'button', className: 'dshcg-danger', onClick: restart }, 'Reiniciar DSH'),
          ),
          message ? jsx('p', { className: 'dshcg-message' }, message) : null,
        )
      }

      function apply(ctx) {
        const scope = ctx.settingsScope.bind({ namespace: 'dsh-context-guard' })
        const style = document.createElement('style')
        style.dataset.plugin = 'dsh-context-guard'
        style.textContent = `
.dshcg-card { max-width: 860px; margin: 14px 0; padding: 18px; border: 1px solid #2b3d58; border-radius: 12px; background: #101827; color: #e5edf9; font: 14px/1.45 system-ui, sans-serif; }
.dshcg-card h2 { margin: 0 0 6px; font-size: 18px; }
.dshcg-muted { color: #9eb0ca; margin: 7px 0 14px; }
.dshcg-context-note { display: grid; gap: 3px; margin: 3px 0 14px; padding: 9px 11px; border-left: 3px solid #6da4ed; border-radius: 5px; background: rgba(109, 164, 237, .08); color: #b9cbe4; }
.dshcg-context-note strong { color: #dbe9fb; font-weight: 600; }
.dshcg-select-label { display: flex; gap: 10px; align-items: center; margin: 12px 0; color: #c8d7ec; }
.dshcg-select-label select { flex: 1; min-width: 160px; padding: 7px 9px; border: 1px solid #385170; border-radius: 6px; background: #0b1220; color: #e5edf9; }
.dshcg-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 2px; }
.dshcg-row { display: grid; grid-template-columns: minmax(190px, .9fr) minmax(300px, 1.8fr) minmax(190px, .9fr); align-items: center; gap: 12px; margin: 8px 0; }
.dshcg-label { color: #c8d7ec; }
.dshcg-control { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 10px; min-width: 0; }
.dshcg-control > input[type='range'] { accent-color: #6da4ed; min-width: 0; width: 100%; }
.dshcg-number-wrap { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.dshcg-number { box-sizing: border-box; width: 92px; padding: 5px 7px; border: 1px solid #385170; border-radius: 6px; background: #0b1220; color: #e5edf9; font: 14px/20px system-ui, sans-serif; font-variant-numeric: tabular-nums; }
.dshcg-number:focus { border-color: #6da4ed; outline: 2px solid rgba(109, 164, 237, .25); outline-offset: 1px; }
.dshcg-unit { color: #9eb0ca; font-size: 12px; }
.dshcg-value { min-width: 0; text-align: right; color: #8fb4e8; font-variant-numeric: tabular-nums; }
.dshcg-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 14px; }
.dshcg-actions button { padding: 7px 14px; border: 1px solid #416591; border-radius: 7px; background: #1a3152; color: #e5edf9; cursor: pointer; }
.dshcg-actions button:disabled { opacity: .5; cursor: default; }
.dshcg-actions .dshcg-danger { border-color: #97515b; background: #542934; }
.dshcg-message { margin: 10px 0 0; color: #a9c9ef; }
.dshcg-restart-wrap { order: 2; display: inline-flex; }
.dshcg-restart-button { box-sizing: border-box; min-height: 34px; padding: 0 12px; border: 1px solid #97515b; border-radius: 999px; background: #542934; color: #f0c6cb; cursor: pointer; font: 500 13px/20px system-ui, sans-serif; white-space: nowrap; transition: background-color .1s, color .1s; }
.dshcg-restart-button:hover:not(:disabled) { background: #713b47; color: #fff1f2; }
.dshcg-restart-button:focus-visible { outline: 2px solid var(--dsw-alias-state-business-primary); outline-offset: 2px; }
.dshcg-restart-button:disabled { cursor: default; opacity: .65; }
@media (max-width: 720px) { .dshcg-row { grid-template-columns: 1fr; gap: 5px; } .dshcg-value { text-align: left; } }
`
        document.head.appendChild(style)
        ctx.effect(() => () => style.remove(), 'dsh-context-guard: settings styles')
        ctx.effect(() => ctx.slots.inject('settings.section', () => ctx.slots.register({
          name: 'settings.section',
          id: 'dsh-context-guard',
          order: 17,
          label: 'Contexto e compactação',
          inject: () => ({ scope }),
        }, ContextGuardSection)), 'dsh-context-guard: settings section')
        ctx.effect(() => ctx.slots.inject('conversation.input.right', () => ctx.slots.register({
          name: 'conversation.input.right',
          id: 'dsh-context-guard-restart',
          order: 110,
        }, RestartButton)), 'dsh-context-guard: restart button')
      }

      return { name: 'dsh-context-guard-client', inject: ['slots', 'settingsScope'], apply }
    },
  })
})()
