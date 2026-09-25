---
name: prezi-em-pdf
description: Converter uma apresentação Prezi (view pública) em um PDF multi-página, capturando cada frame do present mode e montando o PDF a 1920x1080. Use quando o usuário peça para "percorrer a apresentação, tirar prints e montar o pdf" de um link prezi.com/view/...; não promete design livre nem captura de sites estáticos.
---

# Prezi (view) em PDF

Captura cada slide/frame do **present mode** de uma apresentação Prezi e monta um único PDF multi-página a 1920×1080 px @ 100 DPI. Fluxo: `scripts/capture.mjs` (Playwright headless Chromium) → `scripts/assemble.py` (PIL).

## Dependências nesta instalação
- Node.js + Playwright (`node_modules/playwright`, browser em `~/.cache/ms-playwright`) — `capture.mjs` resolve o pacote localmente, por `NODE_PATH`, por `PLAYWRIGHT_NODE_MODULES`, por roots compartilhados do sistema ou pelo runtime auxiliar do Codex, e roda de qualquer diretório. Se o browser empacotado pelo Playwright não estiver disponível, usa `PREZI_CHROMIUM_PATH`, `CHROMIUM_PATH` ou Chromium do sistema. `pngjs` é opcional e habilita a filtragem de quadros totalmente brancos/pretos.
- Python 3 com Pillow global; Poppler `pdfinfo` e `pdftoppm`.

## Fluxo (3 passos)
1. **Capture** os frames: `node scripts/capture.mjs [URL] [DIR_SAIDA]`. Sem args usa o view de referência e `/tmp/prezi2pdf/pages`. O script entra no present mode, navega com `ArrowRight`, escreve PNGs nomeados por índice (`000.png…`) + `manifest.json` (hash de cada frame bruto).
2. **Monte** o PDF: `python3 scripts/assemble.py [DIR_PNGS] [SAIDA.pdf]`. Lê o `manifest.json` (em `DIR_PNGS/../manifest.json` ou em `DIR_PNGS`) para a ordem autoritativa dos frames — os paths `file` são relativos a `DIR_PNGS`; sem manifest, ordena nomes numéricos como `000.png`, `001.png` por nome. Sem argumentos, usa `/tmp/prezi2pdf/pages` e `./saida.pdf`. Rotula o número da página no canto inferior-esquerdo; se um frame não for 1920×1080, encaixa preservando proporção sobre fundo branco centralizado. Salva com `save_all=True, resolution=100.0`.
3. **Verifique** (não declare pronto sem isso): conte páginas e dimensão com `pdfinfo`/`file`, renderize 1ª e última página com `pdftoppm -png`, confirme conteúdo real (não branco) e rótulos presentes.

## Gotchas que definem o workflow
- **Present mode é obrigatório**: na landing, as setas não avançam sob o overlay azul "Present". O script clica `.viewer-common-info-overlay-button-filled`, `button[aria-label="Present"]` ou o texto visível `Present`.
- **Viewer em iframe e chrome da página**: o viewer público pode estar em um iframe e a página pode exibir cabeçalho, banner de cookies e controles de navegação. O script procura o botão em todos os frames, rejeita o banner quando presente e oculta esses elementos antes de capturar.
- **Fim = terminal congelado**, não cap/deadline: este Prezi congela em um frame fixo. Detecta-se com `dupStreak>=5` frames idênticos consecutivos → para limpo. Também encerra em `null`, repetição de F0, ou os limites (`MAX_PAGES=600`, `DEADLINE_MS=180000`).
- **settle()** toma screenshots até a tela parar de mudar (poll 180ms, janela máx 2.6s) antes de registrar um frame; frames brancos/preto puros são ignorados como progresso.
- **PIL não abre PDFs**: use `file`/`pdfinfo` para contagem/dimensão e `pdftoppm -png` para rasterizar páginas; PIL lê PNG sem problema (só não PDF).
- **Ordem vem do manifest, não da lista de arquivos**: o capture pula frames duplicados/brancos, então os índices não ficam contíguos. O assemble.py usa a ordem do `manifest.json`; sem ele cai no fallback numérico por nome (`000.png…`). Os paths `file` do manifest são relativos ao `DIR_PNGS`.

## Verificação mínima
`file SAIDA.pdf` → "PDF document, version X, N page(s)"; `pdfinfo SAIDA.pdf | grep -Ei 'Pages|Page size'`; renderize e inspecione primeira/última página. Páginas esperadas = número de PNGs no diretório.

Para um teste curto, os limites podem ser reduzidos com `PREZI_MAX_PAGES`, `PREZI_DEADLINE_MS`, `PREZI_SETTLE_MAX_MS` e `PREZI_NOCHANGE_STREAK`; esses overrides não são necessários no uso normal.
