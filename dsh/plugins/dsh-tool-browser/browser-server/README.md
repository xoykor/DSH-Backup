dsh-tool-browser — browser automation control server

Standalone Docker container mirroring how searxng is deployed here. The DSH
plugin (../index.mjs) talks to it over HTTP on localhost; the agent never
imports Playwright directly.

Lifecycle (same model as searxng):
- Started once manually: docker run -d --restart unless-stopped -p 127.0.0.1:8731:8731 <image>
- Docker restarts it if it crashes; NOT a systemd unit, does not start on host boot (unless-stopped).

API (JSON, localhost only):
GET /health -> {status, ready, pages}
POST /new -> create page/context -> {id,count}
POST /close-page -> {id} close a page
GET /list-pages -> {title,url,count}
POST /goto -> {url, waitUntil} navigate
POST /title -> current title
POST /screenshot -> {fullPage} returns base64 png
POST /evaluate -> {expression} runs JS in the page context
POST /click /fill /type -> {selector,value} interact with a form
POST /press -> {key} dispatches a keyboard event

Control from DSH: POST http://127.0.0.1:8731/<path> with JSON body
{ "action": { ... } }. The plugin exposes a native \`browser\` tool that
validates the operation and calls these routes over bounded HTTP. The bridge
does not require a WebSocket connection.
