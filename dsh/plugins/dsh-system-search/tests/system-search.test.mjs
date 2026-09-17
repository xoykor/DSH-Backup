import assert from 'node:assert/strict'
import { promises as fs } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { apply, searchSystem } from '../index.mjs'

async function fixture(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'dsh-system-search-'))
  t.after(() => fs.rm(root, { recursive: true, force: true }))
  await fs.mkdir(path.join(root, '.local', 'share', 'PrismLauncher'), { recursive: true })
  await fs.mkdir(path.join(root, 'bin'), { recursive: true })
  const executable = path.join(root, 'bin', 'prismlauncher')
  await fs.writeFile(executable, '#!/bin/sh\n')
  await fs.chmod(executable, 0o755)
  return { root, executable }
}

test('regression: finds PrismLauncher data hidden under .local/share without a known path', async (t) => {
  const { root } = await fixture(t)
  const result = await searchSystem({ query: 'Prism Launcher', roots: [root], maxDepth: 5 })
  const match = result.matches.find((item) => item.path.endsWith(`${path.sep}PrismLauncher`))

  assert.equal(match?.type, 'directory')
  assert.equal(match?.hidden, true)
  assert.equal(match?.match, 'exact')
  assert.match(result.text, /PrismLauncher/)
  assert.equal(result.truncated, false)
})

test('can restrict results to executables', async (t) => {
  const { root, executable } = await fixture(t)
  const result = await searchSystem({ query: 'prism', kind: 'executable', roots: [root], maxDepth: 5 })

  assert.deepEqual(result.matches.map((item) => item.path), [executable])
  assert.equal(result.matches[0].executable, true)
})

test('does not classify data files as executables solely because of their mode', async (t) => {
  const { root } = await fixture(t)
  const image = path.join(root, 'prismlauncher.png')
  await fs.writeFile(image, 'not really an image')
  await fs.chmod(image, 0o755)

  const result = await searchSystem({ query: 'prismlauncher', kind: 'executable', roots: [root], maxDepth: 5 })

  assert.equal(result.matches.some((item) => item.path === image), false)
})

test('honors depth and result bounds', async (t) => {
  const { root } = await fixture(t)
  await fs.mkdir(path.join(root, 'one', 'two', 'three'), { recursive: true })
  await fs.writeFile(path.join(root, 'one', 'two', 'three', 'needle.txt'), 'x')
  await fs.writeFile(path.join(root, 'needle-a.txt'), 'x')
  await fs.writeFile(path.join(root, 'needle-b.txt'), 'x')

  const shallow = await searchSystem({ query: 'needle', roots: [root], maxDepth: 1 })
  assert.equal(shallow.matches.some((item) => item.name === 'needle.txt'), false)

  const bounded = await searchSystem({ query: 'needle', roots: [root], maxDepth: 5, maxResults: 1 })
  assert.equal(bounded.matches.length, 1)
  assert.equal(bounded.truncated, true)
  assert.equal(bounded.truncationReason, 'maxResults=1')
})

test('registers the tool and a discovery prompt', () => {
  let tool
  let section
  const ctx = {
    tools: { register(value) { tool = value } },
    inject(services, callback) {
      assert.deepEqual(services, ['systemPrompt'])
      callback({ systemPrompt: { section(value) { section = value } } })
    },
  }

  apply(ctx)

  assert.equal(tool.name, 'system_search')
  assert.match(tool.description, /\.local\/share/)
  assert.match(section.text, /system_search/)
})
