export const name = 'tool-browser'
export const inject = ['web']

// Browser automation control server — mirrors the searxng deployment pattern.
// The DSH plugin is a thin client: it fetches JSON from the localhost service
// (see browser-server/README.md) exactly like dsh-web-search-searxng does for
// its search provider. No Playwright import happens inside the agent process.

export function apply(ctx, config = {}) {
  const endpoint = String(config.baseURL || 'http://127.0.0.1:8731').replace(/\\/$/, '')

  const provider = {
    id: 'browser-automation',
    available: () => true,
    async browser(request) {
      const url = new URL(endpoint + '/browser')
      for (const [key, value] of Object.entries(request)) {
        if (value !== undefined && value !== null) url.searchParams.set(key, String(value))
      }
      const response = await fetch(url, { method: 'POST', headers: { accept: 'application/json' }, body: JSON.stringify({ action: request }) })
      if (!response.ok) throw new Error('browser returned HTTP ' + response.status)
      return response.json()
    }
  }

  // Register on the web namespace, mirroring ctx.web.registerSearchProvider.
  const register = ctx.web && typeof ctx.web.registerBrowserAutomation === 'function'
    ? ctx.web.registerBrowserAutomation
    : null
  if (register) {
    try { register(provider, { id: name, baseURL: endpoint }) } catch (e) { console.error('dsh-tool-browser: register failed', e.message) }
  } else {
    console.warn('dsh-tool-browser: ctx.web.registerBrowserAutomation not available; skipping registration')
  }
}
