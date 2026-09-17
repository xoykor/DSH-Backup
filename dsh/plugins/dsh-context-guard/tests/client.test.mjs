import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

function loadClient(options = {}) {
  const components = new Map()
  const injected = []
  const context = {
    fetch: options.fetch ?? (async () => ({ ok: true, json: async () => ({ accepted: true }) })),
    window: {
      confirm: options.confirm ?? (() => true),
      __ModuleLoader__: {
        load({ factory }) {
          context.plugin = factory((id) => {
            if (id === 'react') return {
              createElement: (type, props) => ({ type, props }),
              useState: (initial) => [initial, () => {}],
            }
            throw new Error(`unexpected dependency: ${id}`)
          })
        },
      },
    },
    document: {
      querySelector: () => null,
      createElement: () => ({ dataset: {}, remove() {} }),
      head: { appendChild() {} },
    },
  }
  vm.runInNewContext(readFileSync(new URL('../client/client.js', import.meta.url), 'utf8'), context)
  context.plugin.apply({
    effect(setup) { setup() },
    locale: { register() {} },
    settingsScope: { bind: () => ({ subscribe() {}, getSnapshot: () => ({}) }) },
    slots: {
      inject(name, setup) {
        injected.push(name)
        setup()
      },
      register(options, component) {
        components.set(options.id, component)
        return () => {}
      },
    },
  })
  return { components, injected }
}

test('registers the DSH restart action in the main composer', async () => {
  const calls = []
  const { components, injected } = loadClient({
    fetch: async (path, init) => {
      calls.push({ path, init })
      return { ok: true, json: async () => ({ message: 'Reinício solicitado.' }) }
    },
  })

  assert.ok(injected.includes('conversation.input.right'))
  const RestartButton = components.get('dsh-context-guard-restart')
  assert.equal(typeof RestartButton, 'function')
  const tree = RestartButton({})
  const button = tree.props.children

  assert.equal(button.props.disabled, false)
  await button.props.onClick()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].path, '/api/context-guard/restart')
  assert.equal(calls[0].init.method, 'POST')
})

test('does not request a restart when the confirmation is cancelled', async () => {
  let calls = 0
  const { components } = loadClient({
    confirm: () => false,
    fetch: async () => { calls += 1; return { ok: true, json: async () => ({}) } },
  })
  const button = components.get('dsh-context-guard-restart')({}).props.children

  await button.props.onClick()
  assert.equal(calls, 0)
})
